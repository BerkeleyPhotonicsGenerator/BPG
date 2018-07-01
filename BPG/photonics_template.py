# -*- coding: utf-8 -*-


from typing import TYPE_CHECKING, Union, Dict, Any, List, Set, TypeVar, Type, \
    Optional, Tuple, Iterable, Sequence, Callable, Generator

import abc
import numpy as np
import yaml
import time

from bag.core import BagProject, RoutingGrid
from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.util import transform_point, BBox, BBoxArray
from bag.util.cache import _get_unique_name, DesignMaster
from .photonics_port import PhotonicPort
from .photonics_objects import *
from BPG import LumericalGenerator
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
                pass
                # TODO: Write Lumerical implementation of polygon code

                # lay_id, purp_id = lay_map[polygon['layer']]
                # cur_poly = gdspy.Polygon(polygon['points'], layer=lay_id, datatype=purp_id,
                #                          verbose=False)
                # gds_cell.add(cur_poly.fracture(precision=res))

        lsfwriter.export_to_lsf(self.lsf_filepath)
        end = time.time()
        if debug:
            print('layout instantiation took %.4g seconds' % (end - start))


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

    def add_rect(self,  # type: TemplateBase
                 layer,  # type: Union[str, Tuple[str, str]]
                 bbox,  # type: Union[BBox, BBoxArray]
                 nx=1,  # type: int
                 ny=1,  # type: int
                 spx=0,  # type: Union[float, int]
                 spy=0,  # type: Union[float, int]
                 unit_mode=False,  # type: bool
                 ):
        rect = PhotonicRect(layer, bbox, nx=nx, ny=ny, spx=spx, spy=spy, unit_mode=unit_mode)
        self._layout.add_rect(rect)
        self._used_tracks.record_rect(self.grid, layer, rect.bbox_array)
        return rect

    def add_polygon(self,
                    polygon,  # type: PhotonicPolygon
                    ):
        self._layout.add_polygon(polygon)
        return polygon

    def add_advancedpolygon(self,
                            polygon,  # type: PhotonicAdvancedPolygon
                            ):
        self._layout.add_polygon(polygon)
        return polygon

    def add_photonic_port(self,
                          name,  # type: str
                          center,  # type: coord_type
                          inside_point,  # type: coord_type
                          width,  # type: dim_type
                          layer,  # type: Union[str, Tuple[str, str]]
                          resolution=None,  # type: Union[float, int]
                          unit_mode=False,  # type: bool
                          force_append=False,  # type: bool
                          ):
        if resolution is None:
            resolution = self.grid.resolution

        if isinstance(layer, str):
            layer = (layer, 'port')

        if name not in self._photonic_ports.keys():
            self._photonic_ports[name] = PhotonicPort(name, center, inside_point, width, layer, resolution, unit_mode)
        elif force_append:

            self._photonic_ports[name] = PhotonicPort(name, center, inside_point, width, layer, resolution, unit_mode)
        else:
            raise ValueError('Port "{}" already exists in cell.'.format(name))

        print('port center:' + str(center))
        # TODO: Remove or fix this code
        self.add_label(
            label=name,
            layer=layer,
            bbox=BBox(
                bottom=center[1],
                left=center[0],
                top=center[1] + self.grid.resolution,
                right=center[0] + self.grid.resolution,
                resolution=resolution,
                unit_mode=unit_mode
            )
        )
        self.add_rect(
            layer=layer,
            bbox=BBox(
                bottom=center[1],
                left=center[0],
                top=center[1] + 1,
                right=center[0] + 1,
                resolution=resolution,
                unit_mode=unit_mode
            )
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
        inst_master
        instance_port_name
        self_port_name
        instance_name
        reflect

        Returns
        -------

        """

        if not self.has_photonic_port(self_port_name):
            raise ValueError('Photonic cell ' + self_port_name + ' does not exist in '
                             + self.__class__.__name__)

        if not inst_master.has_photonic_port(instance_port_name):
            raise ValueError('Photonic cell ' + instance_port_name + ' does not exist in '
                             + inst_master.__class__.__name__)

        # TODO: think about params
        # inst_master  # = self.new_template(temp_cls=instance)  # type: PhotonicTemplateBase

        my_port = self.get_photonic_port(self_port_name)
        new_port = inst_master.get_photonic_port(instance_port_name)

        print('myport name:  ' + my_port.name)
        print('newport name:  ' + new_port.name)

        tmp_port_point = new_port.center()
        print('newport default center:  ' + str(tmp_port_point))

        # Non-zero if new port is aligned with current port
        # > 0 if ports are facing same direction (new instance must be rotated
        # < 0 if ports are facing opposite direction (new instance should not be rotated)
        dp = np.dot(my_port.orient_vec(), new_port.orient_vec())

        # Non-zero if new port is orthogonal with current port
        # > 0 if
        cp = np.cross(my_port.orient_vec(), new_port.orient_vec())

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
            # TODO:  Verify the new inst rot for reflected cases here:
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
        # rotated_tmp_port_point = np.dot(rot_mat, tmp_port_point)
        print('trans_str:  ' + trans_str)

        rotated_tmp_port_point = transform_point(tmp_port_point[0], tmp_port_point[1], (0, 0), trans_str)

        print('rotated new temp point:  ' + str(rotated_tmp_port_point))

        # Calculate and round translation vector to the resolution unit
        translation_vec = np.round(my_port.center() - rotated_tmp_port_point)

        print('translation vec:  ' + str(translation_vec))

        new_inst = self.add_instance(
            inst_master,
            instance_name,
            loc=(int(translation_vec[0]), int(translation_vec[1])),
            orient=trans_str,
            unit_mode=True
        )

        '''
        # Loop over the ports of the newly added structure and reexport them (translated and rotated) to current design
        for port_name in new_inst.master.photonic_ports_names_iter():
            port = new_inst.master.get_photonic_port(port_name)
            (new_center, new_center_orient) = transform_loc_orient(port.center(), 'R0', translation_vec, trans_str)
            (new_inside_point, new_inside_point_orient) = transform_loc_orient(port.inside_point(), 'R0', translation_vec, trans_str)
            new_port = PhotonicPort(name=port.name,
                                    center=new_center,
                                    inside_point=new_inside_point,
                                    width=port.width(),
                                    layer=port.layer,
                                    resolution=self.grid.resolution,
                                    unit_mode=True,
                                    )
        '''