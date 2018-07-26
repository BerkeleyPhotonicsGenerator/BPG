import importlib
import abc

from .photonic_template import PhotonicTemplateBase
from .lumerical_sim import *


class LumericalTB(PhotonicTemplateBase, metaclass=abc.ABCMeta):
    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        """
        This class enables the creation of Lumerical testbenches
        """
        PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self.layout_package = params['layout_package']
        self.layout_class = params['layout_class']
        self.layout_params = params['layout_params']

        # Contains the master and instance of the design to be tested
        self.dut_master = None
        self.dut_inst = None

        # Store the simulation objects to be created
        self._sim_db = []
        self._source_db = []
        self._monitor_db = []

    @classmethod
    def get_params_info(cls):
        return dict(
            layout_package='Python package containing the photonic layout generator class',
            layout_class='Python class that generates the photonic layout',
            layout_params='Dictionary containing all parameters to be passed to the layout class'
        )

    @abc.abstractmethod
    def construct_tb(self):
        """
        Override this method to specify the procedure for generating the testbench and simulation.
        YOU MUST IMPLEMENT THIS METHOD TO CREATE A TESTBENCH!
        """
        pass

    ''' Simulation Solvers '''
    def add_FDTD_solver(self):
        pass

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
        self.construct_tb()  # Run the user provided code

        # Generate the code for each sim region
        for sim in self._sim_db:
            continue

        # Generate the lsf code for each source
        for source in self._source_db:
            continue

        # Generate the lsf code for each monitor
        for monitor in self._monitor_db:
            continue

    def create_dut(self):
        """
        Create and place the provided layout class and parameters at the origin and export the simulation objects
        """
        layout_module = importlib.import_module(self.layout_package)
        template_class = getattr(layout_module, self.layout_class)
        self.dut_master = self.new_template(params=self.layout_params, temp_cls=template_class)
        self.dut_inst = self.add_instance(self.dut_master)

