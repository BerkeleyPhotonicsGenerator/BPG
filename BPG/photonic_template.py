# -*- coding: utf-8 -*-


from typing import TYPE_CHECKING, Union, Dict, Any, List, Set, TypeVar, Type, \
    Optional, Tuple, Iterable, Sequence, Callable, Generator

import abc
import numpy as np
import yaml
import time

from bag.core import BagProject, RoutingGrid
from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.util import transform_point, BBox, BBoxArray, transform_loc_orient
from bag.util.cache import _get_unique_name, DesignMaster
from bag.layout.objects import Instance, InstanceInfo

from .photonic_port import PhotonicPort
from .photonic_objects import PhotonicRect, PhotonicPolygon, PhotonicAdvancedPolygon, PhotonicInstance
from BPG import LumericalGenerator
from BPG import ShapelyGenerator
from collections import OrderedDict

dim_type = Union[float, int]
coord_type = Tuple[dim_type, dim_type]


class PhotonicTemplateDB(TemplateDB):
    def __init__(self,  # type: TemplateDB
                 lib_defs,  # type: str
                 routing_grid,  # type: RoutingGrid
                 libname,  # type: str
                 prj=None,  # type: Optional[BagProject]
                 name_prefix='',  # type: str
                 name_suffix='',  # type: str
                 use_cybagoa=False,  # type: bool
                 gds_lay_file='',  # type: str
                 flatten=False,  # type: bool
                 gds_filepath='',  # type: str
                 lsf_filepath='',  # type: str
                 **kwargs,
                 ):
        TemplateDB.__init__(self, lib_defs, routing_grid, libname, prj,
                            name_prefix, name_suffix, use_cybagoa, gds_lay_file,
                            flatten, **kwargs)

        self.content_list = None  # Variable where all generated layout content will be stored
        self.gds_filepath = gds_filepath
        self.lsf_filepath = lsf_filepath

    def instantiate_masters(self,
                            master_list,  # type: Sequence[DesignMaster]
                            name_list=None,  # type: Optional[Sequence[Optional[str]]]
                            lib_name='',  # type: str
                            debug=False,  # type: bool
                            rename_dict=None,  # type: Optional[Dict[str, str]]
                            ) -> None:
        """
        Create all given masters in the database. Currently, this is being overridden so that the content_list is stored
        This is a little hacky, and may need to be changed pending further testing

        Parameters
        ----------
        master_list : Sequence[DesignMaster]
            list of masters to instantiate.
        name_list : Optional[Sequence[Optional[str]]]
            list of master cell names.  If not given, default names will be used.
        lib_name : str
            Library to create the masters in.  If empty or None, use default library.
        debug : bool
            True to print debugging messages
        rename_dict : Optional[Dict[str, str]]
            optional master cell renaming dictionary.
        """
        if name_list is None:
            name_list = [None] * len(master_list)  # type: Sequence[Optional[str]]
        else:
            if len(name_list) != len(master_list):
                raise ValueError("Master list and name list length mismatch.")

        # configure renaming dictionary.  Verify that renaming dictionary is one-to-one.
        rename = self._rename_dict
        rename.clear()
        reverse_rename = {}
        if rename_dict:
            for key, val in rename_dict.items():
                if key != val:
                    if val in reverse_rename:
                        raise ValueError('Both %s and %s are renamed '
                                         'to %s' % (key, reverse_rename[val], val))
                    rename[key] = val
                    reverse_rename[val] = key

        for master, name in zip(master_list, name_list):
            if name is not None and name != master.cell_name:
                cur_name = master.cell_name
                if name in reverse_rename:
                    raise ValueError('Both %s and %s are renamed '
                                     'to %s' % (cur_name, reverse_rename[name], name))
                rename[cur_name] = name
                reverse_rename[name] = cur_name

                if name in self._used_cell_names:
                    # name is an already used name, so we need to rename it to something else
                    name2 = _get_unique_name(name, self._used_cell_names, reverse_rename)
                    rename[name] = name2
                    reverse_rename[name2] = name

        if debug:
            print('Retrieving master contents')

        # use ordered dict so that children are created before parents.
        info_dict = OrderedDict()  # type: Dict[str, DesignMaster]
        start = time.time()
        for master, top_name in zip(master_list, name_list):
            self._instantiate_master_helper(info_dict, master)
        end = time.time()

        if not lib_name:
            lib_name = self.lib_name
        if not lib_name:
            raise ValueError('master library name is not specified.')

        self.content_list = [master.get_content(lib_name, self.format_cell_name)
                             for master in info_dict.values()]

        if debug:
            print('master content retrieval took %.4g seconds' % (end - start))

        self.create_masters_in_db(lib_name, self.content_list, debug=debug)

    def _create_gds(self, lib_name, content_list, debug=False):
        """ Use the superclass' create gds function, but point its output to a filepath provided by the spec file """
        TemplateDB._create_gds(self, self.gds_filepath, content_list, debug)

    def to_lumerical(self, debug=False):
        """ Export the drawn layout to the LSF format """
        lsfwriter = LumericalGenerator()
        tech_info = self.grid.tech_info
        lay_unit = tech_info.layout_unit
        res = tech_info.resolution

        with open(self._gds_lay_file, 'r') as f:
            lay_info = yaml.load(f)
            lay_map = lay_info['layer_map']
            prop_map = lay_info['lumerical_prop_map']

        if debug:
            print('Creating Lumerical Script File')

        start = time.time()
        for content in self.content_list:
            (cell_name, inst_tot_list, rect_list, via_list, pin_list,
             path_list, blockage_list, boundary_list, polygon_list) = content

            # add instances
            for inst_info in inst_tot_list:
                pass

                # TODO: Determine how useful this section really is...
                # if inst_info.params is not None:
                #     raise ValueError('Cannot instantiate PCells in GDS.')
                # num_rows = inst_info.num_rows
                # num_cols = inst_info.num_cols
                # angle, reflect = inst_info.angle_reflect
                # if num_rows > 1 or num_cols > 1:
                #     cur_inst = gdspy.CellArray(cell_dict[inst_info.cell], num_cols, num_rows,
                #                                (inst_info.sp_cols, inst_info.sp_rows),
                #                                origin=inst_info.loc, rotation=angle,
                #                                x_reflection=reflect)
                # else:
                #     cur_inst = gdspy.CellReference(cell_dict[inst_info.cell], origin=inst_info.loc,
                #                                    rotation=angle, x_reflection=reflect)
                # gds_cell.add(cur_inst)

            # add rectangles
            for rect in rect_list:
                nx, ny = rect.get('arr_nx', 1), rect.get('arr_ny', 1)
                layer_prop = prop_map[tuple(rect['layer'])]
                if nx > 1 or ny > 1:
                    lsf_repr = PhotonicRect.lsf_export(rect['bbox'], layer_prop, nx, ny,
                                                       spx=rect['arr_spx'], spy=rect['arr_spy'])
                else:
                    lsf_repr = PhotonicRect.lsf_export(rect['bbox'], layer_prop)

                lsfwriter.add_code(lsf_repr)

            # add vias
            for via in via_list:
                pass

            # add pins
            for pin in pin_list:
                pass

            for path in path_list:
                pass

            for blockage in blockage_list:
                pass

            for boundary in boundary_list:
                pass

            for polygon in polygon_list:
                layer_prop = prop_map[tuple(polygon['layer'])]
                lsf_repr = PhotonicPolygon.lsf_export(polygon['points'], layer_prop)
                lsfwriter.add_code(lsf_repr)


                # lay_id, purp_id = lay_map[polygon['layer']]
                # cur_poly = gdspy.Polygon(polygon['points'], layer=lay_id, datatype=purp_id,
                #                          verbose=False)
                # gds_cell.add(cur_poly.fracture(precision=res))

        lsfwriter.export_to_lsf(self.lsf_filepath)
        end = time.time()
        if debug:
            print('layout instantiation took %.4g seconds' % (end - start))

    def to_shapely(self, debug=False):
        """ Export the drawn layout to the Shapely format """
        shapelywriter = ShapelyGenerator()
        # lay_unit = tech_info.layout_unit
        # res = tech_info.resolution

        start = time.time()
        for content in self.content_list:
            (cell_name, inst_tot_list, rect_list, via_list, pin_list,
             path_list, blockage_list, boundary_list, polygon_list) = content

            # add instances
            for inst_info in inst_tot_list:
                pass

                # TODO: Determine how useful this section really is...
                # if inst_info.params is not None:
                #     raise ValueError('Cannot instantiate PCells in GDS.')
                # num_rows = inst_info.num_rows
                # num_cols = inst_info.num_cols
                # angle, reflect = inst_info.angle_reflect
                # if num_rows > 1 or num_cols > 1:
                #     cur_inst = gdspy.CellArray(cell_dict[inst_info.cell], num_cols, num_rows,
                #                                (inst_info.sp_cols, inst_info.sp_rows),
                #                                origin=inst_info.loc, rotation=angle,
                #                                x_reflection=reflect)
                # else:
                #     cur_inst = gdspy.CellReference(cell_dict[inst_info.cell], origin=inst_info.loc,
                #                                    rotation=angle, x_reflection=reflect)
                # gds_cell.add(cur_inst)

            # add rectangles
            for rect in rect_list:
                nx, ny = rect.get('arr_nx', 1), rect.get('arr_ny', 1)
                if nx > 1 or ny > 1:
                    shapely_representation = PhotonicRect.shapely_export(rect['bbox'], nx, ny,
                                                       spx=rect['arr_spx'], spy=rect['arr_spy'])
                else:
                    shapely_representation = PhotonicRect.shapely_export(rect['bbox'])

                shapelywriter.add_shapes(shapely_representation)

            # add vias
            for via in via_list:
                pass

            # add pins
            for pin in pin_list:
                pass

            for path in path_list:
                pass

            for blockage in blockage_list:
                pass

            for boundary in boundary_list:
                pass

            # for polygon in polygon_list:
            #     layer_prop = prop_map[tuple(polygon['layer'])]
            #     shapely_representation = PhotonicPolygon.lsf_export(polygon['points'], layer_prop)
            #     lsfwriter.add_code(shapely_representation)


                # lay_id, purp_id = lay_map[polygon['layer']]
                # cur_poly = gdspy.Polygon(polygon['points'], layer=lay_id, datatype=purp_id,
                #                          verbose=False)
                # gds_cell.add(cur_poly.fracture(precision=res))

        end = time.time()
        if debug:
            print('layout instantiation took %.4g seconds' % (end - start))

        return shapelywriter.final_shapes_export()



class PhotonicTemplateBase(TemplateBase, metaclass=abc.ABCMeta):
    def __init__(self,
                 temp_db,  # type: TemplateDB
                 lib_name,  # type: str
                 params,  # type: Dict[str, Any]
                 used_names,  # type: Set[str]
                 **kwargs,
                 ):
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._photonic_ports = {}
        self._advanced_polygons = {}

    @abc.abstractmethod
    def draw_layout(self):
        pass

    def photonic_ports_names_iter(self):
        # type: () -> Iterable[str]
        return self._photonic_ports.keys()

    def add_rect(self,
                 layer,  # type: Union[str, Tuple[str, str]]
                 x_span=None,  # type: dim_type
                 y_span=None,  # type: dim_type
                 center=None,  # type: coord_type
                 coord1=None,  # type: coord_type
                 coord2=None,  # type: coord_type
                 bbox=None,  # type: Union[BBox, BBoxArray]
                 nx=1,  # type: int
                 ny=1,  # type: int
                 spx=0,  # type: Union[float, int]
                 spy=0,  # type: Union[float, int]
                 unit_mode=False,  # type: bool
                 ):
        """Add a new (arrayed) rectangle.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            the layer name, or the (layer, purpose) pair.
        x_span : Union[int, float]
            horizontal span of the rectangle.
        y_span : Union[int, float]
            vertical span of the rectangle.
        center : Union[int, float]
            coordinate defining center point of the rectangle.
        coord1 : Tuple[Union[int, float], Union[int, float]]
            point defining one corner of rectangle boundary.
        coord2 : Tuple[Union[int, float], Union[int, float]]
            opposite corner from coord1 defining rectangle boundary.
        bbox : bag.layout.util.BBox or bag.layout.util.BBoxArray
            the base bounding box.  If this is a BBoxArray, the BBoxArray's
            arraying parameters are used.
        nx : int
            number of columns.
        ny : int
            number of rows.
        spx : float
            column pitch.
        spy : float
            row pitch.
        unit_mode : bool
            True if layout dimensions are specified in resolution units.

        Returns
        -------
        rect : PhotonicRect
            the added rectangle.
        """
        # Define by center, x_span, and y_span
        if x_span is not None or y_span is not None or center is not None:
            # Ensure all three are defined
            if x_span is None or y_span is None or center is None:
                raise ValueError("If defining by x_span, y_span, and center, all three parameters must be specified.")

            # Define the BBox
            bbox = BBox(
                left=center[0] - x_span / 2,
                right=center[0] + x_span / 2,
                bottom=center[1] - y_span / 2,
                top=center[1] + y_span / 2,
                resolution=self.grid.resolution,
                unit_mode=unit_mode
            )

        # Define by two coordinate points
        elif coord1 is not None or coord2 is not None:
            # Ensure both points are defined
            if coord1 is None or coord2 is None:
                raise ValueError("If defining by two points, both must be specified.")

            # Define the BBox
            bbox = BBox(
                left=min(coord1[0], coord2[0]),
                right=max(coord1[0], coord2[0]),
                bottom=min(coord1[1], coord2[1]),
                top=max(coord1[1], coord2[1]),
                resolution=self.grid.resolution,
                unit_mode=unit_mode
            )

        rect = PhotonicRect(layer, bbox, nx=nx, ny=ny, spx=spx, spy=spy, unit_mode=unit_mode)
        self._layout.add_rect(rect)
        self._used_tracks.record_rect(self.grid, layer, rect.bbox_array)
        return rect

    def add_polygon(self,
                    polygon=None,  # type: Optional[PhotonicPolygon]
                    layer=None,  # type: Union[str, Tuple[str, str]]
                    points=None,  # type: List[coord_type]
                    resolution=None,  # type: float
                    unit_mode=False,  # type: bool
                    ):
        # type: (...) -> PhotonicPolygon
        """

        Parameters
        ----------
        polygon : Optional[PhotonicPolygon]
            the polygon to add
        layer : Union[str, Tuple[str, str]]
            the layer of the polygon
        resolution : float
            the layout grid resolution
        points : List[coord_type]
            the points defining the polygon
        unit_mode : bool
            True if the points are given in resolution units

        Returns
        -------
        polygon : PhotonicPolygon
            the added polygon object
        """
        # If user passes points and layer instead of polygon object, define the new polygon
        if polygon is None:
            # Ensure proper arguments are passed
            if layer is None or points is None:
                raise ValueError("If adding polygon by layer and points, both layer and points list must be defined.")

            if resolution is None:
                resolution = self.grid.resolution

            polygon = PhotonicPolygon(
                resolution=resolution,
                layer=layer,
                points=points,
                unit_mode=unit_mode,
            )

        self._layout.add_polygon(polygon)
        return polygon

    def add_advancedpolygon(self,
                            polygon,  # type: PhotonicAdvancedPolygon
                            ):
        # Maybe have an ordered list of operations like add polygon 1, subtract polygon 2, etc
        self._layout.add_polygon(polygon)
        return polygon

    def finalize(self):
        """

        Returns
        -------

        """
        # TODO: Implement port polygon adding here?
        # Need to remove match port's polygons?
        # Anything else?

        # Call super finalize routine
        TemplateBase.finalize(self)

    def add_photonic_port(self,
                          name=None,  # type: str
                          center=None,  # type: coord_type
                          orient=None,  # type: str
                          width=None,  # type: dim_type
                          layer=None,  # type: Union[str, Tuple[str, str]]
                          resolution=None,  # type: Union[float, int]
                          unit_mode=False,  # type: bool
                          port=None,  # type: PhotonicPort
                          force_append=False,  # type: bool
                          ):
        # TODO: Add support for renaming?
        # TODO: Remove force append?

        # Create a temporary port object unless one is passed as an argument
        if port is None:
            if resolution is None:
                resolution = self.grid.resolution

            if isinstance(layer, str):
                layer = (layer, 'port')

            # Check arguments for validity
            if all([name, center, orient, width, layer]) is None:
                raise ValueError('User must define name, center, orient, width, and layer')

            port = PhotonicPort(name, center, orient, width, layer, resolution, unit_mode)

        # Add port to port list. If name already is taken, remap port if force_append is true
        if port.name not in self._photonic_ports.keys() or force_append:
            self._photonic_ports[port.name] = port
        else:
            raise ValueError('Port "{}" already exists in cell.'.format(name))

        if port.name is not None:
            self.add_label(
                label=port.name,
                layer=port.layer,
                bbox=BBox(
                    bottom=port.center_unit[1],
                    left=port.center_unit[0],
                    top=port.center_unit[1] + self.grid.resolution,
                    right=port.center_unit[0] + self.grid.resolution,
                    resolution=port.resolution,
                    unit_mode=True
                ),
            )

        # Draw port shape
        center = port.center_unit
        orient_vec = np.array(port.width_vec(unit_mode=True, normalized=False))

        self.add_polygon(
            layer=layer,
            points=[center,
                    center + orient_vec // 2 + np.flip(orient_vec, 0) // 2,
                    center + 2 * orient_vec,
                    center + orient_vec // 2 - np.flip(orient_vec, 0) // 2,
                    center],
            resolution=port.resolution,
            unit_mode=True,
        )

    def has_photonic_port(self,
                          port_name,  # type: str
                          ):
        return port_name in self._photonic_ports

    def get_photonic_port(self,
                          port_name='',  # type: str
                          ):
        # type: (...) -> PhotonicPort
        """ Returns the photonic port object with the given name

        Parameters
        ----------
        port_name : str
            the photonic port terminal name. If None or empty, check if this photonic template has only one port,
            and return it

        Returns
        -------
        port : PhotonicsPort
            The photonic port object
        """
        if not self.has_photonic_port(port_name):
            raise ValueError('Port "{}" does not exist in {}'.format(port_name, self.__class__.__name__))

        if not port_name:
            if len(self._photonic_ports) != 1:
                raise ValueError(
                    'Template "{}" has {} ports != 1. Must get port by name.'.format(self.__class__.__name__,
                                                                                     len(self._photonic_ports)
                                                                                     )
                )
        return self._photonic_ports[port_name]

    def add_instances_port_to_port(self,
                                   inst_master,  # type: PhotonicTemplateBase
                                   instance_port_name,  # type: str
                                   self_port_name,  # type: str
                                   instance_name=None,  # type: str
                                   reflect=False,  # type: bool
                                   ):
        # type: (...) -> None
        """
        Rotates new instance about the new instance's master's ORIGIN until desired port is aligned
        Reflect effectively performs a flip about the port direction axis after rotation

        Parameters
        ----------
        inst_master : PhotonicTemplateBase
            the template master to be added
        instance_port_name : str
            the name of the port in the added instance to connect to
        self_port_name : str
            the name of the port in the current structure to connect to
        instance_name : str
            the name to give the new instance
        reflect : bool
            True to flip the added instance
        Returns
        -------

        """

        # TODO: If ports dont have same width/layer, do we return error?

        if not self.has_photonic_port(self_port_name):
            raise ValueError('Photonic port ' + self_port_name + ' does not exist in '
                             + self.__class__.__name__)

        if not inst_master.has_photonic_port(instance_port_name):
            raise ValueError('Photonic port ' + instance_port_name + ' does not exist in '
                             + inst_master.__class__.__name__)

        my_port = self.get_photonic_port(self_port_name)
        new_port = inst_master.get_photonic_port(instance_port_name)
        tmp_port_point = new_port.center()

        # Non-zero if new port is aligned with current port
        # > 0 if ports are facing same direction (new instance must be rotated
        # < 0 if ports are facing opposite direction (new instance should not be rotated)
        dp = np.dot(my_port.width_vec(), new_port.width_vec())

        # Non-zero if new port is orthogonal with current port
        # > 0 if new port is 90 deg CCW from original, < 0 if new port is 270 deg CCW from original
        cp = np.cross(my_port.width_vec(), new_port.width_vec())

        # new_port_orientation = my_port.orientation

        if abs(dp) > abs(cp):
            # New port orientation is parallel to current port

            if dp < 0:
                # Ports are already facing opposite directions

                if reflect:
                    # Reflect port. Determine if port is horizontal or vertical
                    if new_port.is_horizontal():
                        # Port is horizontal: reflect about x axis
                        trans_str = 'MX'
                    else:
                        # Port is vertical: reflect about x axis
                        trans_str = 'MY'

                else:
                    # Do not reflect port
                    trans_str = 'R0'
            else:
                # Ports are facing same direction, new instance must be rotated

                if reflect:
                    # Reflect port. Determine if port is horizontal or vertical
                    if new_port.is_horizontal():
                        # RX + R180 = MY
                        trans_str = 'MY'
                    else:
                        # RY + R180 = MX
                        trans_str = 'MX'
                else:
                    # Do not reflect port
                    trans_str = 'R180'
        else:
            # New port orientation is perpendicular to current port
            if cp > 0:
                # New port is 90 deg CCW wrt current port

                if reflect:
                    # Reflect port. Determine if port is horizontal or vertical
                    if new_port.is_horizontal():
                        # Port is horizontal: reflect about x axis
                        trans_str = 'MXR90'
                    else:
                        # Port is vertical: reflect about x axis
                        trans_str = 'MYR90'

                else:
                    # Do not reflect port
                    trans_str = 'R90'
            else:
                # New port is 270 deg CCW wrt current port

                if reflect:
                    # Reflect port. Determine if port is horizontal or vertical
                    if new_port.is_horizontal():
                        # RX + R180 = MY
                        trans_str = 'MYR90'
                    else:
                        # RY + R180 = MX
                        trans_str = 'MXR90'
                else:
                    # Do not reflect port
                    trans_str = 'R270'

        # Compute the new reflected/rotated port location
        rotated_tmp_port_point = transform_point(tmp_port_point[0], tmp_port_point[1], (0, 0), trans_str)

        # Calculate and round translation vector to the resolution unit
        translation_vec = np.round(my_port.center() - rotated_tmp_port_point)

        new_inst = self.add_instance(
            master=inst_master,
            inst_name=instance_name,
            loc=(int(translation_vec[0]), int(translation_vec[1])),
            orient=trans_str,
            unit_mode=True
        )

        return new_inst

    def delete_port(self,
                    port_names,  # type: Union[str, List[str]]
                    ):
        # type: (...) -> None
        """ Removes the given ports from this instances list of ports. Raises error if given port does not exist.

        Parameters
        ----------
        port_names : Union[str, List[str]]

        Returns
        -------

        """
        if isinstance(port_names, str):
            port_names = [port_names]

        for port_name in port_names:
            if self.has_photonic_port(port_name):
                del self._photonic_ports[port_name]
            else:
                raise ValueError('Photonic port ' + port_name + ' does not exist in '
                                 + self.__class__.__name__)

    def update_port(self):
        # TODO: Implement me.  Deal with matching here?
        pass

    def _get_unused_port_name(self,
                              port_name,  # type: str
                              ):
        if port_name is None:
            port_name = 'PORT'
        new_name = port_name
        if port_name in self._photonic_ports:
            cnt = 0
            new_name = port_name + '_' + str(cnt)
            while new_name in self._photonic_ports:
                cnt += 1
                new_name = port_name + '_' + str(cnt)

        return new_name

    def extract_photonic_ports(self,
                               inst,  # type: PhotonicInstance
                               port_names=None,  # type: Optional[Union[str, List[str]]]
                               port_renaming=None,  # type: Dict[str, str]
                               unmatched_only=True,  # type: bool
                               ):
        # type: (...) -> None
        """

        Parameters
        ----------
        inst :
        port_names :
            the port to re-export. If not given, export all unmatched ports.
        port_renaming :

        Returns
        -------

        """
        # TODO: matched vs non-matched ports.  IE, if two ports are already matched, do we export them
        if port_names is None:
            port_names = inst.master.photonic_ports_names_iter()

        if port_renaming is None:
            port_renaming = {}

        for port_name in port_names:
            old_port = inst.master.get_photonic_port(port_name)
            translation = inst.location_unit
            rotation = inst.orientation

            # Find new port location
            new_location, new_orient = transform_loc_orient(old_port.center_unit,
                                                            old_port.orientation,
                                                            translation,
                                                            rotation,
                                                            )

            # Get new desired name
            if port_name in port_renaming.keys():
                new_name = port_renaming[port_name]
            else:
                new_name = port_name

            # If name is already used
            if new_name in self._photonic_ports:
                # Prepend instance name __   and append unique number
                new_name = self._get_unused_port_name(inst.content.name + '__' + new_name)

            new_port = self.add_photonic_port(
                name=new_name,
                center=new_location,
                orient=new_orient,
                width=old_port.width_unit,
                layer=old_port.layer,
                unit_mode=True,
            )
