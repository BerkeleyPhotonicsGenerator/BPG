"""
Module containing simulation objects that can be added in lumerical
"""
# Base imports
import abc

# BPG imports
from BPG.geometry import Box, CoordBase
from BPG.lumerical.code_generator import LumericalCodeGenerator

# Type checking imports
from typing import List, Tuple, Any
from BPG.port import PhotonicPort


class LumericalSimObj(LumericalCodeGenerator, metaclass=abc.ABCMeta):
    """
    Abstract Base Class for all simulation/monitor objects in Lumerical

    Notes
    -----
    * All simulation objects are treated as dictionaries that store their properties and values. These can be modified
    directly by users so that the code looks similar to standard lumerical script, or specialized methods can be used
    to simplify common operations like convergence tests.

    * Because only specific properties are available for each type of simulation object, the built-in dict's keys are
    set to be immutable. The available properties and their default values are defined by the abstract method
    get_default_property_values().

    * Since geometry manipulation is such a common operation for simulation classes, an abstract property
    self.geometry is provided. This property will contain an object that enables quick and easy functions like
    alignment to ports.

    * The final abstract method is lsf_export. The method is called at the end of the build process to convert all of
    the values in the property dictionary into their corresponding lumerical code.
    """

    def __init__(self):
        LumericalCodeGenerator.__init__(self)

        # Initialize the property dictionary with the default values
        self._prop_dict = self.get_default_property_values().copy()

        # By default attach simulation objects to a special layer
        # TODO: Figure out the correct way to place these objects on layers...
        self._prop_dict['layer'] = ('SI', 'sim')

    def __setitem__(self, key, value) -> None:
        """
        The available properties are governed by Lumerical syntax and features, so users are prevented from adding
        arbitrary keys to the property dict
        """
        if key in self._prop_dict:
            self._prop_dict[key] = value
        else:
            raise KeyError(f'{key} is not a valid property of {self.__class__.__name__}')

    def __getitem__(self, item):
        return self._prop_dict[item]

    @property
    def valid(self):
        """ For now all objects are valid. TODO: Add syntax check here to confirm all properties are specified """
        return True

    @classmethod
    @abc.abstractmethod
    def get_default_property_values(cls) -> dict:
        """
        Returns a dictionary containing available properties and their corresponding default values
        This method is called upon initialization of a LumericalSimObj to populate the property dictionary
        """
        return dict()

    @property
    def content(self):
        """
        Calls the lsf_export method to convert the object properties to lumerical code, then formats it into a
        content dictionary
        """
        self.lsf_export()
        content = dict(layer=self._prop_dict['layer'], code=self._code)
        return content

    @property
    @abc.abstractmethod
    def geometry(self):
        """
        This property returns an object that describes the sizing and placement of the lumerical object. This enables
        users to easily access this object for more complex geometric manipulation.
        """
        pass

    @abc.abstractmethod
    def lsf_export(self) -> List[str]:
        """
        Returns a list of Lumerical code strings describing the creation of the simulation object. All lumerical
        objects must implement this method in order to convert their internal object representation into valid
        code
        """
        pass


class LumericalCodeObj(LumericalSimObj):
    """
    Class that enables the easy addition of arbitrary lumerical code. No restrictions on which properties can be set
    are enforced. All set statements and code blocks are executed in the order in which they are written.
    """

    def __init__(self):
        LumericalSimObj.__init__(self)

    def __setitem__(self, key: str, value: Any):
        """
        Unlike the base class LumericalSimObj, this class allows you to assign arbitrary properties, so allow
        users to add anything to the property dict. This assumes that all __setitem__ calls are equivalent to
        lumerical set statements.
        """
        self.set(key, value)
        self._prop_dict[key] = value

    @property
    def geometry(self):
        return None

    @classmethod
    def get_default_property_values(cls):
        """ This class is designed to enable arbitrary code execution so there are no default properties """
        return dict()

    def lsf_export(self):
        """ Simply return code that the user has explicitly added """
        return self._code


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
        raise NotImplementedError('This method has been deprecated')
        # LumericalSimObj.align_to_port(self, port, offset)
        # if align_orient is True:
        #     if port.orientation == 'R0' or port.orientation == 'R180':
        #         self.orientation = 'x'
        #     else:
        #         self.orientation = 'y'

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
        self.set('x', self['x'])
        self.set('y', self['y'])
        self.set('z', self['z'])

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

    @classmethod
    def get_default_property_values(cls) -> dict:
        return {
            "x": 0,
            "y": 0,
            "z": 0,
            "x span": 0,
            "y span": 0,
            "z span": 0,
            "mesh accuracy": 3,
            "x min bc": 'PML',
            "x max bc": 'PML',
            "y min bc": 'PML',
            "y max bc": 'PML',
            "z min bc": 'PML',
            "z max bc": 'PML',
        }

    @property
    def geometry(self):
        return None

    ''' LSF Export Methods '''
    ''' DO NOT CALL THESE METHODS DIRECTLY '''

    def lsf_export(self) -> List[str]:
        """
        Returns a list of Lumerical code describing the creation of a FDESolver object

        Returns
        -------
        lsf_code : List[str]
            list of Lumerical code to create the FDESolver object
        """
        self.add_code('\naddfdtd')

        # Set the geometry
        self.set('x', self['x'])
        self.set('y', self['y'])
        self.set('z', self['z'])
        self.set('x span', self['x span'])
        self.set('y span', self['y span'])
        self.set('z span', self['z span'])

        # Finally set the meshing and boundary condition settings
        self.set("mesh accuracy", self['mesh accuracy'])
        self.set("x min bc", self['x min bc'])
        self.set("x max bc", self['x max bc'])
        self.set("y min bc", self['y min bc'])
        self.set("y max bc", self['y max bc'])
        self.set("z min bc", self['z min bc'])
        self.set("z max bc", self['z max bc'])

        return self._code


class PowerMonitor(LumericalSimObj):
    """ Lumerical Simulation Object that describes a power monitor """

    def __init__(self):
        super(PowerMonitor, self).__init__()

    @classmethod
    def get_default_property_values(cls) -> dict:
        return {
            "name": None,
            "monitor type": None,
            "x": None,
            "y": None,
            "z": None,
            "x span": None,
            "y span": None,
            "z span": None,
        }

    @property
    def geometry(self):
        return None

    def lsf_export(self) -> List[str]:
        """
        Returns a list of Lumerical code describing the creation of a PowerMonitor object

        Returns
        -------
        lsf_code : List[str]
            list of Lumerical code to create the FDESolver object
        """
        self.add_code('\naddmode')
        self.set("name", self['name'])
        self.set("monitor type", self['monitor type'])

        # Set the geometry
        self.set('x', self['x'])
        self.set('y', self['y'])
        self.set('z', self['z'])
        self.set('x span', self['x span'])
        self.set('y span', self['y span'])
        self.set('z span', self['z span'])

        return self._code


class ModeSource(LumericalSimObj):
    """ Lumerical Simulation Object that controls and places a power monitor """

    def __init__(self):
        super(ModeSource, self).__init__()

    @classmethod
    def get_default_property_values(cls) -> dict:
        return {
            "name": None,
            "injection axis": "x",
            "direction": "forward",
            "x": None,
            "y": None,
            "z": None,
            "x span": None,
            "y span": None,
            "z span": None,
        }

    @property
    def geometry(self):
        return None

    def lsf_export(self):
        self.add_code('\naddmode')
        self.set("name", self['name'])
        self.set("injection axis", self['injection axis'])
        self.set("direction", self['direction'])

        # Set the geometry
        self.set('x', self['x'])
        self.set('y', self['y'])
        self.set('z', self['z'])
        self.set('x span', self['x span'])
        self.set('y span', self['y span'])
        self.set('z span', self['z span'])
