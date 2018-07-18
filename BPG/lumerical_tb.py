import importlib
import abc

from .photonic_template import PhotonicTemplateBase


class LumericalTB(PhotonicTemplateBase, metaclass=abc.ABCMeta):
    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        """
        This class enables the creation of Lumerical testbenches
        """
        PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self.layout_package = params['layout_package']
        self.layout_class = params['layout_class']
        self.layout_params = params['layout_params']
        self.dsn_master = None

        # Initialization procedure
        self.create_dut()  # Create the design to be tested by Lumerical

    @classmethod
    def get_params_info(cls):
        return dict(
            layout_package='Python package containing the photonic layout generator class',
            layout_class='Python class that generates the photonic layout',
            layout_params='Dictionary containing all parameters to be passed to the layout class'
        )

    @abc.abstractmethod
    def draw_layout(self):
        """ Code the procedure for generating the testbench and simulation here """
        pass

    def create_dut(self):
        """ Simply place the provided layout class and parameters at the origin and export the simulation objects """
        layout_module = importlib.import_module(self.layout_package)
        template_class = getattr(layout_module, self.layout_class)
        self.dsn_master = self.new_template(params=self.layout_params, temp_cls=template_class)

    ''' Simulation Solvers '''
    def add_FDTD_solver(self):
        pass

    def add_FDTD_port(self):
        pass

    def add_FDE_solver(self):
        pass

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

