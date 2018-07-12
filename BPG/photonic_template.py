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
from BPG.photonic_core import PhotonicBagLayout

from .photonic_port import PhotonicPort
from .photonic_objects import PhotonicRect, PhotonicPolygon, PhotonicAdvancedPolygon, PhotonicInstance, PhotonicRound
from BPG import LumericalGenerator
from BPG import ShapelyGenerator
from collections import OrderedDict

from numpy import pi

if TYPE_CHECKING:
    from bag.layout.objects import ViaInfo, PinInfo

try:
    import gdspy
except ImportError:
    gdspy = None

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
        self.flat_content_list = None  # Variable where flattened layout content will be stored

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
        # type: (str, Sequence[Any], bool) -> None
        """Create a GDS file containing the given layouts

        Parameters
        ----------
        lib_name : str
            library to create the designs in.
        content_list : Sequence[Any]
            a list of the master contents.  Must be created in this order.
        debug : bool
            True to print debug messages
        """
        tech_info = self.grid.tech_info
        lay_unit = tech_info.layout_unit
        res = tech_info.resolution

        with open(self._gds_lay_file, 'r') as f:
            lay_info = yaml.load(f)
            lay_map = lay_info['layer_map']
            via_info = lay_info['via_info']

        out_fname = self.gds_filepath + '%s.gds' % lib_name
        gds_lib = gdspy.GdsLibrary(name=lib_name)
        cell_dict = gds_lib.cell_dict
        if debug:
            print('Instantiating layout')

        start = time.time()
        for content in content_list:
            (cell_name, inst_tot_list, rect_list, via_list, pin_list,
             path_list, blockage_list, boundary_list, polygon_list, round_list) = content
            gds_cell = gdspy.Cell(cell_name, exclude_from_current=True)
            gds_lib.add(gds_cell)

            # add instances
            for inst_info in inst_tot_list:  # type: InstanceInfo
                if inst_info.params is not None:
                    raise ValueError('Cannot instantiate PCells in GDS.')
                num_rows = inst_info.num_rows
                num_cols = inst_info.num_cols
                angle, reflect = inst_info.angle_reflect
                if num_rows > 1 or num_cols > 1:
                    cur_inst = gdspy.CellArray(cell_dict[inst_info.cell], num_cols, num_rows,
                                               (inst_info.sp_cols, inst_info.sp_rows),
                                               origin=inst_info.loc, rotation=angle,
                                               x_reflection=reflect)
                else:
                    cur_inst = gdspy.CellReference(cell_dict[inst_info.cell], origin=inst_info.loc,
                                                   rotation=angle, x_reflection=reflect)
                gds_cell.add(cur_inst)

            # add rectangles
            for rect in rect_list:
                nx, ny = rect.get('arr_nx', 1), rect.get('arr_ny', 1)
                (x0, y0), (x1, y1) = rect['bbox']
                lay_id, purp_id = lay_map[tuple(rect['layer'])]

                if nx > 1 or ny > 1:
                    spx, spy = rect['arr_spx'], rect['arr_spy']
                    for xidx in range(nx):
                        dx = xidx * spx
                        for yidx in range(ny):
                            dy = yidx * spy
                            cur_rect = gdspy.Rectangle((x0 + dx, y0 + dy), (x1 + dx, y1 + dy),
                                                       layer=lay_id, datatype=purp_id)
                            gds_cell.add(cur_rect)
                else:
                    cur_rect = gdspy.Rectangle((x0, y0), (x1, y1), layer=lay_id, datatype=purp_id)
                    gds_cell.add(cur_rect)

            # add vias
            for via in via_list:  # type: ViaInfo
                via_lay_info = via_info[via.id]

                nx, ny = via.arr_nx, via.arr_ny
                x0, y0 = via.loc
                if nx > 1 or ny > 1:
                    spx, spy = via.arr_spx, via.arr_spy
                    for xidx in range(nx):
                        xc = x0 + xidx * spx
                        for yidx in range(ny):
                            yc = y0 + yidx * spy
                            self._add_gds_via(gds_cell, via, lay_map, via_lay_info, xc, yc)
                else:
                    self._add_gds_via(gds_cell, via, lay_map, via_lay_info, x0, y0)

            # add pins
            for pin in pin_list:  # type: PinInfo
                lay_id, purp_id = lay_map[pin.layer]
                bbox = pin.bbox
                label = pin.label
                if pin.make_rect:
                    cur_rect = gdspy.Rectangle((bbox.left, bbox.bottom), (bbox.right, bbox.top),
                                               layer=lay_id, datatype=purp_id)
                    gds_cell.add(cur_rect)
                angle = 90 if bbox.height_unit > bbox.width_unit else 0
                cur_lbl = gdspy.Label(label, (bbox.xc, bbox.yc), rotation=angle,
                                      layer=lay_id, texttype=purp_id)
                gds_cell.add(cur_lbl)

            for path in path_list:
                pass

            for blockage in blockage_list:
                pass

            for boundary in boundary_list:
                pass

            for polygon in polygon_list:
                lay_id, purp_id = lay_map[polygon['layer']]
                cur_poly = gdspy.Polygon(polygon['points'], layer=lay_id, datatype=purp_id,
                                         verbose=False)
                gds_cell.add(cur_poly.fracture(precision=res))

            for round_obj in round_list:
                nx, ny = round_obj.get('arr_nx', 1), round_obj.get('arr_ny', 1)
                lay_id, purp_id = lay_map[tuple(round_obj['layer'])]
                x0, y0 = round_obj['center']

                if nx > 1 or ny > 1:
                    spx, spy = round_obj['arr_spx'], round_obj['arr_spy']
                    for xidx in range(nx):
                        dx = xidx * spx
                        for yidx in range(ny):
                            dy = yidx * spy
                            cur_round = gdspy.Round((x0 + dx, y0 + dy), radius=round_obj['rout'],
                                                    inner_radius=round_obj['rin'],
                                                    initial_angle=round_obj['theta0'] * pi / 180,
                                                    final_angle=round_obj['theta1'] * pi / 180,
                                                    number_of_points=self.grid.resolution,
                                                    layer=lay_id, datatype=purp_id)
                            gds_cell.add(cur_round)
                else:
                    cur_round = gdspy.Round((x0, y0), radius=round_obj['rout'],
                                            inner_radius=round_obj['rin'],
                                            initial_angle=round_obj['theta0'] * pi / 180,
                                            final_angle=round_obj['theta1'] * pi / 180,
                                            number_of_points=self.grid.resolution,
                                            layer=lay_id, datatype=purp_id)
                    gds_cell.add(cur_round)

        gds_lib.write_gds(out_fname, unit=lay_unit, precision=res * lay_unit)

        end = time.time()
        if debug:
            print('layout instantiation took %.4g seconds' % (end - start))

    def _add_gds_via(self, gds_cell, via, lay_map, via_lay_info, x0, y0):
        blay, bpurp = lay_map[via_lay_info['bot_layer']]
        tlay, tpurp = lay_map[via_lay_info['top_layer']]
        vlay, vpurp = lay_map[via_lay_info['via_layer']]
        cw, ch = via.cut_width, via.cut_height
        if cw < 0:
            cw = via_lay_info['cut_width']
        if ch < 0:
            ch = via_lay_info['cut_height']

        num_cols, num_rows = via.num_cols, via.num_rows
        sp_cols, sp_rows = via.sp_cols, via.sp_rows
        w_arr = num_cols * cw + (num_cols - 1) * sp_cols
        h_arr = num_rows * ch + (num_rows - 1) * sp_rows
        x0 -= w_arr / 2
        y0 -= h_arr / 2
        bl, br, bt, bb = via.enc1
        tl, tr, tt, tb = via.enc2
        bot_p0, bot_p1 = (x0 - bl, y0 - bb), (x0 + w_arr + br, y0 + h_arr + bt)
        top_p0, top_p1 = (x0 - tl, y0 - tb), (x0 + w_arr + tr, y0 + h_arr + tt)

        cur_rect = gdspy.Rectangle(bot_p0, bot_p1, layer=blay, datatype=bpurp)
        gds_cell.add(cur_rect)
        cur_rect = gdspy.Rectangle(top_p0, top_p1, layer=tlay, datatype=tpurp)
        gds_cell.add(cur_rect)

        for xidx in range(num_cols):
            dx = xidx * (cw + sp_cols)
            for yidx in range(num_rows):
                dy = yidx * (ch + sp_rows)
                cur_rect = gdspy.Rectangle((x0 + dx, y0 + dy), (x0 + cw + dx, y0 + ch + dy),
                                           layer=vlay, datatype=vpurp)
                gds_cell.add(cur_rect)

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
             path_list, blockage_list, boundary_list, polygon_list, round_list, ) = content

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

            for round_obj in round_list:
                nx, ny = round_obj.get('arr_nx', 1), round_obj.get('arr_ny', 1)
                layer_prop = prop_map[tuple(round_obj['layer'])]

                if nx > 1 or ny > 1:
                    lsf_repr = PhotonicRound.lsf_export(
                        rout=round_obj['rout'],
                        rin=round_obj['rin'],
                        theta0=round_obj['theta0'],
                        theta1=round_obj['theta1'],
                        layer_prop=layer_prop,
                        center=round_obj['center'],
                        nx=nx,
                        ny=ny,
                        spx=round_obj['arr_spx'],
                        spy=round_obj['arr_spy'],
                    )
                else:
                    lsf_repr = PhotonicRound.lsf_export(
                        rout=round_obj['rout'],
                        rin=round_obj['rin'],
                        theta0=round_obj['theta0'],
                        theta1=round_obj['theta1'],
                        layer_prop=layer_prop,
                        center=round_obj['center'],
                    )
                lsfwriter.add_code(lsf_repr)

        lsfwriter.export_to_lsf(self.lsf_filepath)
        end = time.time()
        if debug:
            print('layout instantiation took %.4g seconds' % (end - start))

    def instantiate_flat_masters(self,
                                 master_list,  # type: Sequence[DesignMaster]
                                 name_list=None,  # type: Optional[Sequence[Optional[str]]]
                                 lib_name='',  # type: str
                                 debug=False,  # type: bool
                                 rename_dict=None,  # type: Optional[Dict[str, str]]
                                 ) -> None:
        """
        Create all given masters in the database to a flat hierarchy.

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
            self._flatten_instantiate_master_helper(info_dict, master)
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

    def _flatten_instantiate_master_helper(self,
                                           info_dict,
                                           master,
                                           loc=(0, 0),
                                           orient='R0'
                                           ):
        """
        For each passed master:
           get content
           for each child instance:
              call _flatten instantiate again

           transform all content by the child position & orientation


        Parameters
        ----------
        info_dict
        master

        Returns
        -------

        """
        for child_master_key in master.children:
            print("in _flatten_instance_master_helper")

            child_content = self._master_lookup[child_master_key].get_content()



            print("content_list: ")

            input_content_list = content_list

            if debug:
                print('Flattening design')

            start = time.time()

            # Need to loop over content_list.
            # For each content, if it has instances, need to add the polygons of that instance at the transformed loc

            new_rect_list = []
            new_via_list = []
            new_pin_list = []
            new_path_list = []
            new_blockage_list = []
            new_polygon_list = []
            new_round_list = []

            # content_list is a list of content structures. Each content is the content of a particular instance
            for content in input_content_list:
                print("in content loop")
                (cell_name, inst_tot_list, rect_list, via_list, pin_list,
                 path_list, blockage_list, boundary_list, polygon_list, round_list,) = content

                asdf
                self.register_master()
                for inst_info in inst_tot_list:
                    print("in inst loop")
                    # Need to flatten this cell too after it has been transformed
                    # Get the polygons from the subcell
                    (sub_rect_list, sub_via_list, sub_pin_list, sub_path_list,
                     sub_blockage_list, sub_polygon_list, sub_round_list) = self._flatten_helper(
                        content_list=inst_info.,
                        loc=inst_info.loc,
                        orient=inst_info.orient,
                        unit_mode=False,
                        debug=debug
                    )

                    rect_list.extend(sub_rect_list)
                    via_list.extend(sub_via_list)
                    pin_list.extend(sub_pin_list)
                    path_list.extend(sub_path_list)
                    blockage_list.extend(sub_blockage_list)
                    polygon_list.extend(sub_polygon_list)
                    round_list.extend(sub_round_list)

                # add rectangles
                for rect in rect_list:
                    new_rect_list.append(
                        PhotonicRect.from_content(
                            content=rect,
                            resolution=self.grid.resolution
                        ).transform(
                            loc=loc,
                            orient=orient,
                            unit_mode=unit_mode,
                            copy=False
                        ).content
                    )

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
                    # new_poly = PhotonicPolygon.from_content(
                    #         content=polygon,
                    #         resolution=self.grid.resolution
                    #     )
                    # new_poly = new_poly.transform(
                    #         loc=loc,
                    #         orient=orient,
                    #         unit_mode=unit_mode,
                    #         copy=False
                    #     )
                    # new_poly_content = new_poly.content
                    #
                    # new_polygon_list.append(new_poly_content)

                    new_polygon_list.append(
                        PhotonicPolygon.from_content(
                            content=polygon,
                            resolution=self.grid.resolution
                        ).transform(
                            loc=loc,
                            orient=orient,
                            unit_mode=unit_mode,
                            copy=False
                        ).content
                    )

                for round_obj in round_list:
                    new_round_list.append(
                        PhotonicRound.from_content(
                            content=round_obj,
                            resolution=self.grid.resolution
                        ).transform(
                            loc=loc,
                            orient=orient,
                            unit_mode=unit_mode,
                            copy=False
                        ).content
                    )

                new_content_list = (new_rect_list, new_via_list, new_pin_list, new_path_list,
                                    new_blockage_list, new_polygon_list, new_round_list)

                return new_content_list

    def flatten(self,
                debug=False
                ):
        print("in flatten")
        self.flat_content_list = self._flatten_helper(
            content_list=self.content_list,
            loc=(0, 0),
            orient='R0',
            unit_mode=False,
            debug=debug
        )

    def _flatten_helper(self,
                        content_list,  # type: List[Tuple]
                        loc,
                        orient='R0',
                        unit_mode=False,
                        debug=False,
                        ):
        # type: (...) -> Tuple
        """Flattens all elements in the design hierarchy

        Parameters
        ----------
        content_list
        loc
        orient
        unit_mode
        debug

        Returns
        -------

        """
        print("in _flatten_helper")
        print("content_list: ")
        print(content_list)

        input_content_list = content_list

        if debug:
            print('Flattening design')

        start = time.time()

        # Need to loop over content_list.
        # For each content, if it has instances, need to add the polygons of that instance at the transformed loc

        new_rect_list = []
        new_via_list = []
        new_pin_list = []
        new_path_list = []
        new_blockage_list = []
        new_polygon_list = []
        new_round_list = []

        # content_list is a list of content structures. Each content is the content of a particular instance
        for content in input_content_list:
            print("in content loop")
            (cell_name, inst_tot_list, rect_list, via_list, pin_list,
             path_list, blockage_list, boundary_list, polygon_list, round_list, ) = content

            asdf
            self.register_master()
            for inst_info in inst_tot_list:
                print("in inst loop")
                # Need to flatten this cell too after it has been transformed
                # Get the polygons from the subcell
                (sub_rect_list, sub_via_list, sub_pin_list, sub_path_list,
                 sub_blockage_list, sub_polygon_list, sub_round_list) = self._flatten_helper(
                    content_list=inst_info.,
                    loc=inst_info.loc,
                    orient=inst_info.orient,
                    unit_mode=False,
                    debug=debug
                )

                rect_list.extend(sub_rect_list)
                via_list.extend(sub_via_list)
                pin_list.extend(sub_pin_list)
                path_list.extend(sub_path_list)
                blockage_list.extend(sub_blockage_list)
                polygon_list.extend(sub_polygon_list)
                round_list.extend(sub_round_list)

            # add rectangles
            for rect in rect_list:
                new_rect_list.append(
                    PhotonicRect.from_content(
                        content=rect,
                        resolution=self.grid.resolution
                    ).transform(
                        loc=loc,
                        orient=orient,
                        unit_mode=unit_mode,
                        copy=False
                    ).content
                )

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
                # new_poly = PhotonicPolygon.from_content(
                #         content=polygon,
                #         resolution=self.grid.resolution
                #     )
                # new_poly = new_poly.transform(
                #         loc=loc,
                #         orient=orient,
                #         unit_mode=unit_mode,
                #         copy=False
                #     )
                # new_poly_content = new_poly.content
                #
                # new_polygon_list.append(new_poly_content)

                new_polygon_list.append(
                    PhotonicPolygon.from_content(
                        content=polygon,
                        resolution=self.grid.resolution
                    ).transform(
                        loc=loc,
                        orient=orient,
                        unit_mode=unit_mode,
                        copy=False
                    ).content
                )

            for round_obj in round_list:
                new_round_list.append(
                    PhotonicRound.from_content(
                        content=round_obj,
                        resolution=self.grid.resolution
                    ).transform(
                        loc=loc,
                        orient=orient,
                        unit_mode=unit_mode,
                        copy=False
                    ).content
                )

            new_content_list = (new_rect_list, new_via_list, new_pin_list, new_path_list,
                                new_blockage_list, new_polygon_list, new_round_list)

            return new_content_list

        end = time.time()
        if debug:
            print('layout instantiation took %.4g seconds' % (end - start))

    def get_layer_shapes(self,
                         layer,  # type: Tuple[str, str]
                         ):
        # type: (...) -> List
        """Returns only the content that exists on a given layer

        Parameters
        ----------
        layer

        Returns
        -------

        """

    def to_shapely(self, debug=False):
        """ Export the drawn layout to the Shapely format """
        shapelywriter = ShapelyGenerator()
        # lay_unit = tech_info.layout_unit
        # res = tech_info.resolution

        start = time.time()
        for content in self.content_list:
            (cell_name, inst_tot_list, rect_list, via_list, pin_list,
             path_list, blockage_list, boundary_list, polygon_list, round_list) = content

            # add instances
            for inst_info in inst_tot_list:
                pass

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

            #     lay_id, purp_id = lay_map[polygon['layer']]
            #     cur_poly = gdspy.Polygon(polygon['points'], layer=lay_id, datatype=purp_id,
            #                          verbose=False)
            #     gds_cell.add(cur_poly.fracture(precision=res))

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

        use_cybagoa = kwargs.get('use_cybagoa', False)

        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self._photonic_ports = {}
        self._advanced_polygons = {}
        self._layout = PhotonicBagLayout(self._grid, use_cybagoa=use_cybagoa)

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

    def add_round(self,
                  round_obj=None,  # type: Optional[PhotonicRound]
                  layer=None,  # type: Union[str, Tuple[str, str]]
                  center=None,  # type: coord_type
                  rout=None,  # type: dim_type
                  rin=None,  # type: Optional[dim_type]
                  theta0=None,  # type: Optional[dim_type]
                  theta1=None,  # type: Optional[dim_type]
                  resolution=None,  # type: float
                  unit_mode=False,  # type: bool
                  ):
        # type: (...) -> PhotonicRound
        """

        Parameters
        ----------
        round_obj : Optional[PhotonicRound]
            the polygon to add
        layer : Union[str, Tuple[str, str]]
            the layer of the polygon
        rout : dim_type
            the outer radius
        rin : dim_type
            Optional: the inner radius
        theta0 : dim_type
            Optional: the starting angle
        theta1 : dim_type
            Optional: the ending angle
        resolution : float
            the layout grid resolution
        unit_mode : bool
            True if the points are given in resolution units

        Returns
        -------
        polygon : PhotonicRound
            the added round object
        """
        # If user passes points and layer instead of polygon object, define the new polygon
        if round_obj is None:
            # Ensure proper arguments are passed
            if all([layer, rout]) is None:
                raise ValueError("If adding round by radius, then layer and radius must be defined.")

            if resolution is None:
                resolution = self.grid.resolution

            round_obj = PhotonicRound(
                layer=layer,
                resolution=resolution,
                center=center,
                rout=rout,
                rin=rin,
                theta0=theta0,
                theta1=theta1,
                unit_mode=unit_mode,
            )

        self._layout.add_round(round_obj)
        return round_obj

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
