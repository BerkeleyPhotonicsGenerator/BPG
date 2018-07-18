from .photonic_layout_manager import PhotonicLayoutManager


class LumericalTB(PhotonicLayoutManager):
    def __init__(self, bprj, spec_file):
        """
        This class enables the creation of Lumerical testbenches
        """
        PhotonicLayoutManager.__init__(self, bprj, spec_file)

    def generate_lsf(self):
        """ Overrides the superclass function to create both the design LSF and TB LSF """
        # TODO: Export TB monitors/sources to LSF script
        PhotonicLayoutManager.generate_lsf(self)

    """
    
    """

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

