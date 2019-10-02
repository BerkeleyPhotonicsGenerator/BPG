import abc
import importlib
from copy import deepcopy


import emopt

import BPG.PhotonicTemplateBase

class EmoptFDFD_TETestbench(BPG.PhotonicTemplateBase, metaclass=abc.ABCMeta):
    """This class is meant to be extended in testbenches meant to use emopt.
    """

    @abc.abstractmethod
    def construct_tb(self):
        """Override this with a method placing the DuT for your simulation."""
        raise NotImplementedError

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        BPG.PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self.layout_package: str = params['layout_package']
        self.layout_class: str = params['layout_class']
        self.layout_params: Dict[str, Any] = params['layout_params']
        self.tb_params: Dict[str, Any] = params['tb_params']

        # Contains the master and instance of the design to be tested
        self.dut_master = None
        self.dut_inst: "PhotonicInstance" = None

        # The internal emopt simulation object won't be added until the user calls add_sim
        self.sim = None
        self._real_sim_dimensions = {"X": 0,
                                     "Y": 0,
                                     "dX": 0,
                                     "dY": 0}
        self._abs_sim_dimensions = {"Xleft": 0,
                                    "Xright": 0,
                                    "Yleft": 0,
                                    "Yright": 0,
                                    "dX": 0,
                                    "dY": 0}

    def add_sim(self, dim):
        """Instantiates the internal emopt simulation object for the testbench. This method
        takes arguments rather than reading from yaml to enable
        programmatic simulation bounds (i.e. computed based on DUT layout parameters).

        Parameters
        ----------
        dim : Dict
            A dictionary containing the corners and spatial resolution of the simulation rectangle
        """
        wlen = self.tb_params["wavelength"]
        X = abs(dim["X1"] - dim["X2"])
        Y = abs(dim["Y1"] - dim["Y2"])
        dX = dim["dX"]
        dY = dim["dY"]

        self.sim = emopt.fdfd.FDFD_TE(X,Y,dX,dY,wlen)

        self._abs_sim_dimensions = deepcopy(dim)

        self._real_sim_dimensions["X"]  = self.sim.X
        self._real_sim_dimensions["Y"]  = self.sim.Y
        self._real_sim_dimensions["dX"] = self.sim.dX
        self._real_sim_dimensions["dY"] = self.sim.dY


    @classmethod
    def get_params_info(cls):
        return dict(
            layout_package='Python package containing the photonic layout generator class',
            layout_class='Python class name within the package that generates the photonic layout',
            layout_params='Dictionary containing all parameters to be passed to the layout class',
            tb_params='Parameters to be used in your testbench'
        )

    def extend_waveguide(self,
                         port: "PhotonicPort",
                         length: float,
                         ) -> "PhotonicPort":
        """
        Extends a constant-width waveguide of the DUT by some length.  Useful for adding sources and monitors and
        distances away from the DUT.
        Returns the PhotonicPort on the end of the newly added waveguide

        Parameters
        ----------
        port : PhotonicPort
            The PhotonicPort to which the waveguide should be added.
        length : float
            The length of the

        Returns
        -------

        """
        taper_params = dict(
            width0=port.width,
            width1=port.width,
            length=length,
            layer=(port.layer[0], 'drawing')
        )
        taper_master = self.new_template(params=taper_params, temp_cls=LinearTaper)

        wg_inst = self.add_instances_port_to_port(
            inst_master=taper_master,
            instance_port_name='PORT1',
            self_port=port,
        )

        return wg_inst['PORT0']


    def create_dut(self):
        """
        Create and place the provided layout class and parameters at the origin
        """
        layout_module = importlib.import_module(self.layout_package)
        template_class = getattr(layout_module, self.layout_class)
        self.dut_master = self.new_template(params=self.layout_params, temp_cls=template_class)
        self.dut_inst = self.add_instance(self.dut_master,
                                          loc=(self._real_sim_dimensions["X"]/2,self._real_sim_dimensions["Y"]/2)
                                          )


