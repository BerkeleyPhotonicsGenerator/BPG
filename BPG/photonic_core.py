import os
import bag
import bag.io

from pathlib import Path
from bag.core import BagProject, create_tech_info
from decimal import Decimal
from bag.layout.core import BagLayout
from .photonic_port import PhotonicPort
from typing import TYPE_CHECKING, List, Callable, Union, Tuple, Any
from itertools import chain

if TYPE_CHECKING:
    from BPG.photonic_objects import PhotonicRound
    from bag.layout.objects import InstanceInfo

try:
    import cybagoa
except ImportError:
    cybagoa = None


# From bag/core
class PhotonicBagProject(BagProject):
    """
    The main bag controller class.

    This class extracts user configuration variables and issues high level bag commands. Most config variables have
    defaults pointing to files in the BPG/examples/tech folder

    Parameters
    ----------
    bag_config_path : Optional[str]
        the bag configuration file path.  If None, will attempt to read from
        environment variable BAG_CONFIG_PATH.
    port : Optional[int]
        the BAG server process port number.  If not given, will read from port file.
    """

    def __init__(self, bag_config_path=None, port=None):
        BagProject.__init__(self, bag_config_path, port)
        # Get the main working directory to be used for all relative paths
        root_path = os.environ['BAG_WORK_DIR']

        # Setup bag config path from env if not provided
        if bag_config_path is None:
            if 'BAG_CONFIG_PATH' not in os.environ:
                raise EnvironmentError('BAG_CONFIG_PATH not defined')
            else:
                bag_config_path = os.environ['BAG_CONFIG_PATH']

        # Load core bpg configuration variables from bag_config file
        self.bag_config = self.load_yaml(bag_config_path)
        if 'bpg_config' in self.bag_config:
            self.bpg_config = self.bag_config['bpg_config']
        else:
            raise ValueError('bpg configuration vars not set in bag_config.yaml')

        # Extract relevant tech configuration paths

        self.layermap_path = self.bpg_config.get('layermap', root_path + '/BPG/examples/tech/gds_map.yaml')
        if not Path(self.layermap_path).is_file():
            raise ValueError(f'layermap file {self.layermap_path} does not exist!')
        print(f'Loading layermap from {self.layermap_path}')

        self.dataprep_path = self.bpg_config.get('dataprep', root_path + '/BPG/examples/tech/dataprep.yaml')
        if not Path(self.dataprep_path).is_file():
            raise ValueError(f'dataprep file {self.dataprep_path} does not exist!')
        print(f'Loading dataprep procedure from {self.dataprep_path}')

        self.lsf_export_path = self.bpg_config.get('lsf_dataprep',
                                                   root_path + '/BPG/examples/tech/lumerical_map.yaml')
        if not Path(self.lsf_export_path).is_file():
            raise ValueError(f'layermap file {self.lsf_export_path} does not exist!')
        print(f'Loading lumerical export config from {self.lsf_export_path}')

        # TODO: Create a dummy dataprep params file so that we can do a file exists check
        self.dataprep_params_path = self.bpg_config.get('dataprep_params', '')
        print(f'Loading dataprep parameters from {self.dataprep_params_path}')

        # Grab technology information
        # TODO: Make the tech class loading generic again
        print('Setting up tech info class')
        # self.tech_info = PTech()
        self.tech_info = create_tech_info(bag_config_path=bag_config_path)

    @staticmethod
    def load_yaml(filepath):
        """ Setup standardized method for yaml loading """
        return bag.core._parse_yaml_file(filepath)


# From bag/layout/core
class PhotonicBagLayout(BagLayout):
    """
    This class contains layout information of a cell.

    Parameters
    ----------
    grid : :class:`bag.layout.routing.RoutingGrid`
        the routing grid instance.
    use_cybagoa : bool
        True to use cybagoa package to accelerate layout.
    """

    def __init__(self, grid, use_cybagoa=False):
        BagLayout.__init__(self, grid, use_cybagoa)

        # Add new features to be supported in content list
        self._round_list = []  # type: List[PhotonicRound]
        self._sim_list = []
        self._source_list = []
        self._monitor_list = []

    def finalize(self):
        # type: () -> None
        """Prevents any further changes to this layout.
        """
        self._finalized = True

        # get rectangles
        rect_list = []
        for obj in self._rect_list:
            if obj.valid:
                if not obj.bbox.is_physical():
                    print('WARNING: rectangle with non-physical bounding box found.', obj.layer)
                else:
                    obj_content = obj.content
                    rect_list.append(obj_content)

        # filter out invalid geometries
        path_list = []
        polygon_list = []
        blockage_list = []
        boundary_list = []
        via_list = []
        round_list = []
        for targ_list, obj_list in ((path_list, self._path_list),
                                    (polygon_list, self._polygon_list),
                                    (blockage_list, self._blockage_list),
                                    (boundary_list, self._boundary_list),
                                    (via_list, self._via_list),
                                    (round_list, self._round_list)):
            for obj in obj_list:
                if obj.valid:
                    targ_list.append(obj.content)

        # get via primitives
        via_list.extend(self._via_primitives)

        # get instances
        inst_list = []  # type: List[InstanceInfo]
        for obj in self._inst_list:
            if obj.valid:
                obj_content = self._format_inst(obj)
                inst_list.append(obj_content)

        # Assemble raw content list from all
        self._raw_content = [inst_list,
                             self._inst_primitives,
                             rect_list,
                             via_list,
                             self._pin_list,
                             path_list,
                             blockage_list,
                             boundary_list,
                             polygon_list,
                             round_list,
                             self._sim_list,
                             self._source_list,
                             self._monitor_list
                             ]

        if (not inst_list and not self._inst_primitives and not rect_list and not blockage_list and
                not boundary_list and not via_list and not self._pin_list and not path_list and
                not polygon_list and not round_list and not self._sim_list and not self._source_list
                and not self._monitor_list):
            self._is_empty = True
        else:
            self._is_empty = False

    def get_content(self,  # type: BagLayout
                    lib_name,  # type: str
                    cell_name,  # type: str
                    rename_fun,  # type: Callable[[str], str]
                    ):
        # type: (...) -> Union[List[Any], Tuple[str, 'cybagoa.PyOALayout']]
        """returns a list describing geometries in this layout.

        Parameters
        ----------
        lib_name : str
            the layout library name.
        cell_name : str
            the layout top level cell name.
        rename_fun : Callable[[str], str]
            the layout cell renaming function.

        Returns
        -------
        content : Union[List[Any], Tuple[str, 'cybagoa.PyOALayout']]
            a list describing this layout, or PyOALayout if cybagoa package is enabled.
        """

        if not self._finalized:
            raise Exception('Layout is not finalized.')

        cell_name = rename_fun(cell_name)
        (inst_list, inst_prim_list, rect_list, via_list, pin_list,
         path_list, blockage_list, boundary_list, polygon_list, round_list,
         sim_list, source_list, monitor_list) = self._raw_content

        # update library name and apply layout cell renaming on instances
        inst_tot_list = []
        for inst in inst_list:
            inst_temp = inst.copy()
            inst_temp['lib'] = lib_name
            inst_temp['cell'] = rename_fun(inst_temp['cell'])
            inst_tot_list.append(inst_temp)
        inst_tot_list.extend(inst_prim_list)

        if self._use_cybagoa and cybagoa is not None:
            encoding = bag.io.get_encoding()
            oa_layout = cybagoa.PyLayout(encoding)

            for obj in inst_tot_list:
                oa_layout.add_inst(**obj)
            for obj in rect_list:
                oa_layout.add_rect(**obj)
            for obj in via_list:
                oa_layout.add_via(**obj)
            for obj in pin_list:
                oa_layout.add_pin(**obj)
            for obj in path_list:
                oa_layout.add_path(**obj)
            for obj in blockage_list:
                oa_layout.add_blockage(**obj)
            for obj in boundary_list:
                oa_layout.add_boundary(**obj)
            for obj in polygon_list:
                oa_layout.add_polygon(**obj)
            for obj in round_list:
                oa_layout.add_round(**obj)

            return cell_name, oa_layout
        else:
            ans = [cell_name, inst_tot_list, rect_list, via_list, pin_list, path_list,
                   blockage_list, boundary_list, polygon_list, round_list,
                   sim_list, source_list, monitor_list]
            return ans

    def move_all_by(self, dx=0.0, dy=0.0, unit_mode=False):
        # type: (Union[float, int], Union[float, int], bool) -> None
        """Move all layout objects in this layout by the given amount.

        Parameters
        ----------
        dx : Union[float, int]
            the X shift.
        dy : Union[float, int]
            the Y shift.
        unit_mode : bool
            True if shift values are given in resolution units.
        """
        if self._finalized:
            raise Exception('Layout is already finalized.')

        for obj in chain(self._inst_list, self._inst_primitives, self._rect_list,
                         self._via_primitives, self._via_list, self._pin_list,
                         self._path_list, self._blockage_list, self._boundary_list,
                         self._polygon_list, self._round_list,
                         self._sim_list, self._source_list, self._monitor_list):
            obj.move_by(dx=dx, dy=dy, unit_mode=unit_mode)

    def add_round(self,
                  round_obj  # type: PhotonicRound
                  ):
        """Add a new (arrayed) round shape.

        Parameters
        ----------
        round_obj : BPG.photonic_objects.PhotonicRound
            the round object to add.
        """
        if self._finalized:
            raise Exception('Layout is already finalized.')

        self._round_list.append(round_obj)

    def add_sim_obj(self, sim_obj):
        """ Add a new Lumerical simulation object to the db """
        if self._finalized:
            raise Exception('Layout is already finalized.')

        self._sim_list.append(sim_obj)

    def add_source_obj(self, source_obj):
        """ Add a new Lumerical source object to the db """
        if self._finalized:
            raise Exception('Layout is already finalized.')

        self._source_list.append(source_obj)

    def add_monitor_obj(self, monitor_obj):
        """ Add a new Lumerical monitor object to the db """
        if self._finalized:
            raise Exception('Layout is already finalized.')

        self._monitor_list.append(monitor_obj)


class PTech:
    def __init__(self):
        self.resolution = 0.001
        self.layout_unit = 0.000001
        self.via_tech_name = ''
        self.pin_purpose = None

    def get_layer_id(self, layer):
        pass

    def finalize_template(self, a):
        pass

    def use_flip_parity(self):
        pass


class CoordBase:
    """
    A class representing the basic unit of measurement for all objects in BPG.

    All user-facing values are assumed to be floating point numbers in units of microns. BAG internal functions
    assume that we receive 'unit-mode' numbers, which are integers in units of nanometers. Both formats are supported.
    """

    res = Decimal('1e-3')  # resolution for all numbers in BPG is 1nm
    micron = Decimal('1e-6')  # size of 1 micron in meters
    __slots__ = ['_value']

    def __new__(cls, value, *args, **kwargs):
        """ Assumes a floating point input value in microns, stores an internal integer representation on grid """
        self = object.__new__(cls)  # Create the immutable instance
        self._value = round(Decimal(str(value)) / CoordBase.res)
        return self

    def __repr__(self):
        return 'CoordBase({})'.format(self.float)

    @property
    def value(self):
        return self._value

    @property
    def unit_mode(self):
        return self.value

    @property
    def float(self):
        """ Returns the rounded floating point number closest to a valid point on the resolution grid """
        return float(self.value * CoordBase.res)

    @property
    def microns(self):
        return self.float

    @property
    def meters(self):
        """ Returns the rounded floating point number in meters closest to a valid point on the resolution grid """
        return float(self.value * CoordBase.res * CoordBase.micron)


class XY:
    """
    A class representing a single point on the XY plane
    """

    __slots__ = ['_x', '_y']

    def __new__(cls, xy, *args, **kwargs):
        """ Assumes a floating point input value in microns for each dimension """
        self = object.__new__(cls)  # Create the immutable instance
        self._x = CoordBase(xy[0])
        self._y = CoordBase(xy[1])
        return self

    @property
    def x(self):
        return self._x.unit_mode

    @property
    def y(self):
        return self._y.unit_mode

    @property
    def xy(self):
        return [self.x, self.y]

    @property
    def xy_float(self):
        return [self._x.float, self._y.float]

    @property
    def x_float(self):
        return self._x.float

    @property
    def y_float(self):
        return self._y.float

    @property
    def xy_meters(self):
        return [self._x.meters, self._y.meters]

    @property
    def x_meters(self):
        return self._x.meters

    @property
    def y_meters(self):
        return self._y.meters


class XYZ:
    """
    A class representing a single point on the XYZ space
    """

    __slots__ = ['_x', '_y', '_z']

    def __new__(cls, xyz, *args, **kwargs):
        """ Assumes a floating point input value in microns for each dimension """
        self = object.__new__(cls)  # Create the immutable instance
        self._x = CoordBase(xyz[0])
        self._y = CoordBase(xyz[1])
        self._z = CoordBase(xyz[2])
        return self

    @property
    def x(self):
        return self._x.unit_mode

    @property
    def y(self):
        return self._y.unit_mode

    @property
    def z(self):
        return self._z.unit_mode

    @property
    def xyz(self):
        return [self.x, self.y, self.z]

    @property
    def x_float(self):
        return self._x.float

    @property
    def y_float(self):
        return self._y.float

    @property
    def z_float(self):
        return self._z.float

    @property
    def xyz_float(self):
        return [self._x.float, self._y.float, self._z.float]

    @property
    def x_meters(self):
        return self._x.meters

    @property
    def y_meters(self):
        return self._y.meters

    @property
    def z_meters(self):
        return self._z.meters

    @property
    def xyz_meters(self):
        return [self._x.meters, self._y.meters, self._z.meters]


class Plane:
    """
    A class representing a plane that is orthogonal to one of the cardinal axes

    TODO: Implement this class
    """
    def __init__(self):
        pass


class Box:
    """
    A class representing a 3D rectangle
    """
    def __init__(self):
        self.geometry = {
            'x': {'center': 0.0, 'span': 0.0},
            'y': {'center': 0.0, 'span': 0.0},
            'z': {'center': 0.0, 'span': 0.0}
        }

    ''' Configuration Methods '''
    ''' USE THESE METHODS TO SETUP THE SIMULATION '''

    def move_by(self, dx, dy, unit_mode=False):
        if unit_mode is True:
            raise ValueError('Boxes dont currently support unit mode movement')

        self.geometry['x']['center'] += dx
        self.geometry['y']['center'] += dy

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
        self.geometry['x']['center'] = center[0] + offset[0]
        self.geometry['y']['center'] = center[1] + offset[1]
