import abc

# Type checking imports
from typing import List, Tuple
from .photonic_port import PhotonicPort


class LumericalSimObj(metaclass=abc.ABCMeta):
    """
    Abstract Base Class for all simulation/monitor objects in Lumerical

    All simulation objects have a common representation for geometry and common code syntax. These are
    implemented here
    """

    def __init__(self):
        self._lsfcode = ['\n']  # Start the code block with a newline
        # Store the geometric properties of the simulation object
        self.geometry = {
            'x': {'center': 0.0, 'span': 0.0},
            'y': {'center': 0.0, 'span': 0.0},
            'z': {'center': 0.0, 'span': 0.0}
        }

    ''' Configuration Methods '''
    ''' USE THESE METHODS TO SETUP THE SIMULATION '''

    def set_center_span(self, dim, center, span):
        """
        Sets the center and span of a given geometry dimension

        Parameters
        ----------
        dim : str
            'x', 'y', or 'z' for the corresponding dimension
        center : float
            coordinate location of the center of the geometry
        span : float
            length of the geometry along the dimension
        """
        self.geometry[dim]['center'] = center
        self.geometry[dim]['span'] = span

    def set_span(self, dim, span):
        """
        Sets the span of a given geometry dimension

        Parameters
        ----------
        dim : str
            'x', 'y', or 'z' for the corresponding dimension
        center : float
            coordinate location of the center of the geometry
        span : float
            length of the geometry along the dimension
        """
        self.geometry[dim]['span'] = span

    def align_to_port(self,
                      port,  # type: PhotonicPort
                      offset=(0, 0),  # type: Tuple,
                      ):
        """
        Moves the center of the simulation object to align to the provided photonic port

        Parameters
        ----------
        port : PhotonicPort
            Photonic port for the simulation object to be aligned to
        offset : Tuple
            (x, y) offset relative to the port location
        """
        center = port.center_unit
        self.geometry['x']['center'] = center[0]
        self.geometry['y']['center'] = center[1]

    ''' Properties '''

    @property
    def lsf_code(self):
        """ Restrict direct access to directly modifying the lsf code to enforce basic code syntax """
        return self._lsfcode

    @abc.abstractmethod
    def export_lsf(self) -> List[str]:
        """
        Returns a list of Lumerical code describing the creation of the simulation object

        Unlike the export_lsf method for photonic objects, this method is not a classmethod, and relies
        on internal access to the instances attributes
        """
        pass

    def add_code(self, code):
        """
        Use this method to add a single line of code to the LSF file. This enforces basic code syntax
        and styling for the generated LSF file
        """
        self._lsfcode.append(code.join(';\n'))

    def set(self, key, value):
        """
        Use this method to conveniently add a set statement to the LSF file

        Parameters
        ----------
        key : str
            parameter to be changed with the set statement
        value : any
            value that the parameter will be assigned
        """
        if isinstance(value, str):
            self.add_code('set("{}", "{}")'.format(key, value))
        else:
            self.add_code('set("{}", {})'.format(key, value))

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
        super(FDESolver, self).__init__()

        # Initialize simulator variables
        self.wavelength = None
        self.num_modes = 4
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
        super(FDESolver, self).align_to_port(port, offset)
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

    ''' LSF Export Methods '''
    ''' DO NOT CALL THESE METHODS DIRECTLY '''

    def export_lsf(self):
        """
        Returns a list of Lumerical code describing the creation of a FDESolver object

        Returns
        -------
        lsf_code : List[str]
            list of Lumerical code to create the FDESolver object
        """
        self.add_code('addfde')
        self._export_solver_type()
        self._export_geometry()
        self._export_sim_settings()
        self.add_code('findmodes')  # Start the mode simulation

        return self.lsf_code

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

    def _export_sim_settings(self):
        """ Adds code for setting the simulation variables """
        if self.wavelength is None:
            raise ValueError('Please set the wavelength for the FDE sim to be run')
        self.set('wavelength', self.wavelength)
        self.set('number of trial modes', self.num_modes)
