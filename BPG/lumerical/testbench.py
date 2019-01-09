import BPG
import importlib
import abc
import logging

from typing import Dict, Any, List
from .simulation import *

logger = logging.getLogger(__name__)


class LumericalTB(BPG.PhotonicTemplateBase, metaclass=abc.ABCMeta):
    """
    Abstract base class for all lumerical testbench generators. This class is structured similarly
    to layout generators, allowing users to add lumerical objects to a running database. These objects
    can then be manipulated by the user to setup the desired properties as needed.
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        BPG.PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self.layout_package: str = params['layout_package']
        self.layout_class: str = params['layout_class']
        self.layout_params: Dict[str, Any] = params['layout_params']
        self.params: Dict[str, Any] = params['tb_params']

        # Contains the master and instance of the design to be tested
        self.dut_master = None
        self.dut_inst = None

        # Store the simulation objects to be created
        self._sim_db: List[LumericalSimObj] = []
        self._source_db: List[LumericalSimObj] = []
        self._monitor_db: List[LumericalSimObj] = []

    @classmethod
    def get_params_info(cls):
        return dict(
            layout_package='Python package containing the photonic layout generator class',
            layout_class='Python class that generates the photonic layout',
            layout_params='Dictionary containing all parameters to be passed to the layout class',
            tb_params='Parameters to be used in your testbench'
        )

    @abc.abstractmethod
    def construct_tb(self):
        """
        Override this method to specify the procedure for generating the testbench and simulation.
        YOU MUST IMPLEMENT THIS METHOD TO CREATE A TESTBENCH!
        """
        pass

    def add_code_obj(self):
        """ Create an object that simplifies the process of adding arbitrary lumerical code """
        temp_code = LumericalCodeObj()
        self._sim_db.append(temp_code)
        return temp_code

    ''' Simulation Solvers '''
    def add_FDTD_solver(self) -> FDTDSolver:
        """ Create a blank FDTD solver, add it to the db, and return it to the user for manipulation """
        temp_fdtd = FDTDSolver()
        self._sim_db.append(temp_fdtd)
        return temp_fdtd

    def add_FDTD_port(self):
        pass

    def add_FDE_solver(self) -> FDESolver:
        """ Create a blank FDE solver, add it to the db, and return it to the user for manipulation """
        temp_fde = FDESolver()
        self._sim_db.append(temp_fde)
        return temp_fde

    def add_var_FDTD_solver(self):
        pass

    def add_EME_solver(self):
        pass

    def add_EME_port(self):
        pass

    ''' Simulation Sources '''
    def add_mode_source(self):
        pass

    def add_point_source(self):
        pass

    def add_gaussian_source(self):
        pass

    def plane_wave_source(self):
        pass

    def add_total_field_source(self):
        pass

    ''' Simulation Monitors '''
    def add_index_monitor(self):
        pass

    def add_effective_index_monitor(self):
        pass

    def add_time_domain_monitor(self):
        pass

    def add_movie_monitor(self):
        pass

    def add_freq_domain_monitor(self):
        pass

    def add_eme_profile(self):
        pass

    def add_mode_expansion_monitor(self):
        pass

    def draw_layout(self):
        """ This method is used internally to assemble the instance and the TB sources. DO NOT CALL THIS """
        self.create_dut()  # First create the layout to be tested
        self.construct_tb()  # Run the user provided TB setup code

        # Add each sim object in db to the layout
        for sim in self._sim_db:
            self.add_sim_obj(sim)

        # Add each source object in db to the layout
        for source in self._source_db:
            self.add_source_obj(source)

        # Add each monitor object in db to the layout
        for monitor in self._monitor_db:
            self.add_monitor_obj(monitor)

    def create_dut(self):
        """
        Create and place the provided layout class and parameters at the origin
        """
        layout_module = importlib.import_module(self.layout_package)
        template_class = getattr(layout_module, self.layout_class)
        self.dut_master = self.new_template(params=self.layout_params, temp_cls=template_class)
        self.dut_inst = self.add_instance(self.dut_master)
