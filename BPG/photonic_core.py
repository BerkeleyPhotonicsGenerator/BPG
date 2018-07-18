import bag
import bag.io
from bag.core import BagProject
from bag.layout.core import BagLayout
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
    """The main bag controller class.

    This class mainly stores all the user configurations, and issue
    high level bag commands.

    Parameters
    ----------
    bag_config_path : Optional[str]
        the bag configuration file path.  If None, will attempt to read from
        environment variable BAG_CONFIG_PATH.
    port : Optional[int]
        the BAG server process port number.  If not given, will read from port file.
    """

    def __init__(self, bag_config_path=None, port=None):
        self.tech_info = PTech()


# From bag/layout/core
class PhotonicBagLayout(BagLayout):
    """This class contains layout information of a cell.

    Parameters
    ----------
    grid : :class:`bag.layout.routing.RoutingGrid`
        the routing grid instance.
    use_cybagoa : bool
        True to use cybagoa package to accelerate layout.
    """

    def __init__(self, grid, use_cybagoa=False):
        BagLayout.__init__(self, grid, use_cybagoa)
        self._round_list = []  # type: List[PhotonicRound]

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
        path_list, polygon_list, blockage_list, boundary_list, via_list, round_list = [], [], [], [], [], []
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
                             ]

        if (not inst_list and not self._inst_primitives and not rect_list and not blockage_list and
                not boundary_list and not via_list and not self._pin_list and not path_list and
                not polygon_list and not round_list):
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
         path_list, blockage_list, boundary_list, polygon_list, round_list) = self._raw_content

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
                   blockage_list, boundary_list, polygon_list, round_list, ]
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
                         self._polygon_list, self._round_list, ):
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
