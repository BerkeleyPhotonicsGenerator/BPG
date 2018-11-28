"""
Module containing simulation objects that can be added in lumerical
"""
# Base imports
import abc

# BPG imports
from BPG.photonic_core import Box, CoordBase
from BPG.lumerical.code_generator import LumericalCodeGenerator

# Type checking imports
from typing import List, Tuple
from BPG.port import PhotonicPort


class LumericalSimObj(Box, LumericalCodeGenerator, metaclass=abc.ABCMeta):
    """
    Abstract Base Class for all simulation/monitor objects in Lumerical

    All simulation objects have a common representation for geometry and generate lsf code, so LumericalSimObj
    inherits both from Box and from LumericalCodeGenerator
    """

    def __init__(self):
        Box.__init__(self)
        LumericalCodeGenerator.__init__(self)

        self.layer = ('SI', 'sim')  # Attach simulation objects to a separate layer

    ''' Properties '''

    def __getitem__(self, item):
        """ Set up getitem to return layer info when content dict is prompted """
        if item == 'layer':
            return self.layer

    @property
    def content(self):
        """ Return self so that lsf_export can be called by BAG from the content list """
        return self

    @abc.abstractmethod
    def lsf_export(self) -> List[str]:
        """
        Returns a list of Lumerical code describing the creation of the simulation object

        Unlike the export_lsf method for photonic objects, this method is not a classmethod, and relies
        on internal access to the instances attributes
        """
        pass

    def _export_geometry(self):
        """ Adds code to specify the geometry of a simulation region """
        # First set the center of the simulation region
        self.set('x', self.geometry['x']['center'])
        self.set('y', self.geometry['y']['center'])
        self.set('z', self.geometry['z']['center'])

        # Then set the span of each dimension
        self.set('x span', self.geometry['x']['span'])
        self.set('y span', self.geometry['y']['span'])
        self.set('z span', self.geometry['z']['span'])


class FDESolver(LumericalSimObj):
    """ Lumerical Simulation Object for Finite-Difference Eigenmode Solver """

    def __init__(self):
        LumericalSimObj.__init__(self)

        # Initialize simulator variables
        self.wavelength = None
        self.num_modes = 2
        self._mesh_size = CoordBase(.01)
        self._orientation = 'x'

    ''' Configuration Methods '''
    ''' USE THESE METHODS TO SETUP THE SIMULATION '''
    def align_to_port(self,
                      port,  # type: PhotonicPort
                      offset=(0, 0),  # type: Tuple,
                      align_orient=True  # type: bool
                      ):
        """
        Moves the center of the simulation object to align to the provided photonic port.
        Overrides the superclass method to support setting the orientation to match port

        Parameters
        ----------
        port : PhotonicPort
            Photonic port for the simulation object to be aligned to
        offset : Tuple
            (x, y) offset relative to the port location
        align_orient : bool
            True to set the orientation to match the port orientation, False to ignore port orientation
        """
        LumericalSimObj.align_to_port(self, port, offset)
        if align_orient is True:
            if port.orientation == 'R0' or port.orientation == 'R180':
                self.orientation = 'x'
            else:
                self.orientation = 'y'

    ''' Properties '''

    @property
    def orientation(self):
        return self._orientation

    @orientation.setter
    def orientation(self, value):
        if any([value == 'x', value == 'y', value == 'z']):
            self._orientation = value
        else:
            raise ValueError('Provided FDE orientation {} is not valid; please set'
                             'to x, y, or z'.format(self.orientation))

    @property
    def mesh_size(self):
        return self._mesh_size

    @mesh_size.setter
    def mesh_size(self, value):
        self._mesh_size = CoordBase(value)

    ''' LSF Export Methods '''
    ''' DO NOT CALL THESE METHODS DIRECTLY '''

    def lsf_export(self):
        """
        Returns a list of Lumerical code describing the creation of a FDESolver object

        Returns
        -------
        lsf_code : List[str]
            list of Lumerical code to create the FDESolver object
        """
        self.add_code('\naddfde')
        self._export_solver_type()
        self._export_geometry()
        self._export_mesh_settings()
        self.add_formatted_line('\n# Simulation Settings')
        self._export_sim_settings()
        self.add_formatted_line('\n# Run Simulation')
        self.add_code('findmodes')  # Start the mode simulation
        self.add_formatted_line('\n# Save Data')
        self._export_data()

        return self._code

    def _export_solver_type(self):
        """ Adds Lumerical code for setting the solver type """
        self.set('solver type', '2D {} normal'.format(self.orientation))

    def _export_geometry(self):
        """ Overrides base method to support 2D sim region """
        # First set the center of the simulation region
        self.set('x', self.geometry['x']['center'])
        self.set('y', self.geometry['y']['center'])
        self.set('z', self.geometry['z']['center'])

        # Next, set the span of each dimension perpendicular to the wave propagation
        if self.orientation != 'x':
            self.set('x span', self.geometry['x']['span'])
        if self.orientation != 'y':
            self.set('y span', self.geometry['y']['span'])
        if self.orientation != 'z':
            self.set('z span', self.geometry['z']['span'])

    def _export_mesh_settings(self):
        """ Adds code for the mesh settings """
        if self.orientation != 'x':
            self.set("define x mesh by", "maximum mesh step")
            self.set("dx", self.mesh_size.meters)
        if self.orientation != 'y':
            self.set("define y mesh by", "maximum mesh step")
            self.set("dy", self.mesh_size.meters)
        if self.orientation != 'z':
            self.set("define z mesh by", "maximum mesh step")
            self.set("dz", self.mesh_size.meters)

    def _export_sim_settings(self):
        """ Adds code for setting the simulation variables """
        if self.wavelength is None:
            raise ValueError('Please set the wavelength for the FDE sim to be run')
        self.set('wavelength', self.wavelength)
        self.set('number of trial modes', self.num_modes)

    def _export_data(self):
        """ Sets which results should be exported """
        self.add_code('neff=getresult("FDE::data::mode1", "neff")')
        self.add_code('write("../data/data", num2str(neff))')


class FDTDSolver(LumericalSimObj):
    """ Lumerical Simulation Object for Finite-Difference Time Domain Solver """

    def __init__(self):
        super(FDTDSolver, self).__init__()

        # Initialize simulator variables
        self._bc = {
            'xmin': 'PML',
            'xmax': 'PML',
            'ymin': 'PML',
            'ymax': 'PML',
            'zmin': 'PML',
            'zmax': 'PML',
        }
        self.mesh_accuracy = 3

    ''' LSF Export Methods '''
    ''' DO NOT CALL THESE METHODS DIRECTLY '''

    def lsf_export(self):
        """
        Returns a list of Lumerical code describing the creation of a FDESolver object

        Returns
        -------
        lsf_code : List[str]
            list of Lumerical code to create the FDESolver object
        """
        self.add_code('\naddfdtd')
        self._export_geometry()
        self._export_sim_settings()

        return self._code

    def _export_sim_settings(self):
        """ Adds code for setting the simulation variables """
        self.set("mesh accuracy", self.mesh_accuracy)
        self.set("x min bc", self._bc['xmin'])
        self.set("x max bc", self._bc['xmax'])
        self.set("y min bc", self._bc['ymin'])
        self.set("y max bc", self._bc['ymax'])
        self.set("z min bc", self._bc['zmin'])
        self.set("z max bc", self._bc['zmax'])
