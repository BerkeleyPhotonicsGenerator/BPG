# -*- coding: utf-8 -*-


from typing import TYPE_CHECKING, Union, Dict, Any, List, Set, \
    Optional, Tuple, Iterable, Sequence

import abc
import numpy as np
import yaml
import time

from bag.core import BagProject, RoutingGrid
import bag.io
from bag.layout.template import TemplateBase, TemplateDB
from bag.layout.util import transform_point, BBox, BBoxArray, transform_loc_orient
from bag.util.cache import _get_unique_name, DesignMaster
from BPG.photonic_core import PhotonicBagLayout

from .photonic_port import PhotonicPort
from .photonic_objects import PhotonicRect, PhotonicPolygon, PhotonicAdvancedPolygon, PhotonicInstance, PhotonicRound, \
    PhotonicVia, PhotonicBlockage, PhotonicBoundary, PhotonicPath
from BPG import LumericalDesignGenerator
from collections import OrderedDict
from BPG.dataprep_gdspy import dataprep_coord_to_gdspy, poly_operation, polyop_gdspy_to_point_list

from numpy import pi

if TYPE_CHECKING:
    from bag.layout.objects import ViaInfo, PinInfo
    from bag.layout.objects import InstanceInfo, Instance

try:
    import gdspy
except ImportError:
    gdspy = None

dim_type = Union[float, int]
coord_type = Tuple[dim_type, dim_type]

# SKILL has DO_MANH_AT_BEGINNING effectively set to True (all shapes are first Manhattanized). We can do this, but it
# will be slow. Instead, we think it is OK to NOT Manhattanize pre-data-prep, perform the growth/shrink functions on
# non-Manhattanized shapes, then Manhattanize at the very end. This should be faster
GLOBAL_DO_MANH_AT_BEGINNING = False

# SKILL has GLOBAL_DO_MANH_DURING_OP as True. Only used during rad
GLOBAL_DO_MANH_DURING_OP = True

# True to ensure that final shape will be on a Manhattan grid. If GLOBAL_DO_MANH_AT_BEGINNING and _..._DIRUING_OP are
# set, GLOBAL_DO_FINAL_MANH can be False, and we will still have Manhattanized shapes on Manhattan grid
GLOBAL_DO_FINAL_MANH = False


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
                 dataprep_file='',  # type: str
                 **kwargs,
                 ):
        TemplateDB.__init__(self, lib_defs, routing_grid, libname, prj,
                            name_prefix, name_suffix, use_cybagoa, gds_lay_file,
                            flatten, **kwargs)

        # Variable where all generated layout content will be stored, in BAG content list format
        self.content_list = None
        # Variable where flattened layout content will be stored, in BAG content list format
        self.flat_content_list = None
        self.flat_content_list_separate = None
        # Variable where flattened layout content will be stored, by layer.
        # Format is a dictionary whose keys are LPPs, and whose values are BAG content list format
        self.flat_content_list_by_layer = {}  # type: Dict[Tuple(str, str), List]
        # Shapely format (shapely Polygon objects)
        self.flat_gdspy_polygonsets_by_layer = {}
        self.post_dataprep_polygon_pointlist_by_layer = {}
        self.post_dataprep_flat_content_list = []

        self.gds_filepath = gds_filepath
        self.lsf_filepath = lsf_filepath
        self.dataprep_file = dataprep_file

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
        if debug:
            print("In PhotonicTemplateDB._create_gds")

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
             path_list, blockage_list, boundary_list, polygon_list, round_list,
             sim_list, source_list, monitor_list) = content
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
                # Photonic paths should be treated like polygons
                lay_id, purp_id = lay_map[path['layer']]
                cur_path = gdspy.Polygon(path['polygon_points'], layer=lay_id, datatype=purp_id,
                                         verbose=False)
                gds_cell.add(cur_path.fracture(precision=res))

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
        tech_info = self.grid.tech_info

        with open(self._gds_lay_file, 'r') as f:
            lay_info = yaml.load(f)
            lay_map = lay_info['layer_map']
            prop_map = lay_info['lumerical_prop_map']

        if debug:
            print('Creating Lumerical Script File')

        start = time.time()
        if self.flat_content_list is None:
            raise ValueError('Please generate a flat GDS before exporting to Lumerical')

        for count, content in enumerate(self.flat_content_list_separate):
            lsfwriter = LumericalDesignGenerator(self.lsf_filepath + '_' + str(count))

            (cell_name, inst_tot_list, rect_list, via_list, pin_list,
             path_list, blockage_list, boundary_list, polygon_list, round_list,
             sim_list, source_list, monitor_list) = content

            # add rectangles if they are valid lumerical layers
            if len(rect_list) != 0:
                lsfwriter.add_line(' ')
                lsfwriter.add_line('#------------------ ')
                lsfwriter.add_line('# Adding Rectangles ')
                lsfwriter.add_line('#------------------ ')
            for rect in rect_list:
                nx, ny = rect.get('arr_nx', 1), rect.get('arr_ny', 1)
                if tuple(rect['layer']) in prop_map:
                    layer_prop = prop_map[tuple(rect['layer'])]
                    if nx > 1 or ny > 1:
                        lsf_repr = PhotonicRect.lsf_export(rect['bbox'], layer_prop, nx, ny,
                                                           spx=rect['arr_spx'], spy=rect['arr_spy'])
                    else:
                        lsf_repr = PhotonicRect.lsf_export(rect['bbox'], layer_prop)
                    lsfwriter.add_code_block(lsf_repr)

            for via in via_list:
                pass

            for pin in pin_list:
                pass

            for path in path_list:
                # Treat like polygons
                if tuple(path['layer']) in prop_map:
                    layer_prop = prop_map[tuple(path['layer'])]
                    lsf_repr = PhotonicPolygon.lsf_export(path['polygon_points'], layer_prop)
                    lsfwriter.add_code(lsf_repr)

            # add polygons if they are valid lumerical layers
            if len(polygon_list) != 0:
                lsfwriter.add_line(' ')
                lsfwriter.add_line('#---------------- ')
                lsfwriter.add_line('# Adding Polygons ')
                lsfwriter.add_line('#---------------- ')
            for polygon in polygon_list:
                if tuple(polygon['layer']) in prop_map:
                    layer_prop = prop_map[tuple(polygon['layer'])]
                    lsf_repr = PhotonicPolygon.lsf_export(polygon['points'], layer_prop)
                    lsfwriter.add_code_block(lsf_repr)

            # add rounds if they are valid lumerical layers
            if len(round_list) != 0:
                lsfwriter.add_line(' ')
                lsfwriter.add_line('#-------------- ')
                lsfwriter.add_line('# Adding Rounds ')
                lsfwriter.add_line('#-------------- ')
            for round_obj in round_list:
                if tuple(round_obj['layer']) in prop_map:
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
                    lsfwriter.add_code_block(lsf_repr)

            # Add simulation objects
            if len(sim_list) != 0:
                lsfwriter.add_line(' ')
                lsfwriter.add_line('#-------------------------- ')
                lsfwriter.add_line('# Adding Simulation Objects ')
                lsfwriter.add_line('#-------------------------- ')
            for sim in sim_list:
                lsf_repr = sim.lsf_export()
                lsfwriter.add_code_block(lsf_repr)

            # Add simulation sources
            if len(source_list) != 0:
                lsfwriter.add_line(' ')
                lsfwriter.add_line('#---------------------- ')
                lsfwriter.add_line('# Adding Source Objects ')
                lsfwriter.add_line('#---------------------- ')
            for source in source_list:
                lsf_repr = source.lsf_export()
                lsfwriter.add_code_block(lsf_repr)

            # Add simulation monitors
            if len(monitor_list) != 0:
                lsfwriter.add_line(' ')
                lsfwriter.add_line('#----------------------- ')
                lsfwriter.add_line('# Adding Monitor Objects ')
                lsfwriter.add_line('#----------------------- ')
            for monitor in monitor_list:
                lsf_repr = monitor.lsf_export()
                lsfwriter.add_code_block(lsf_repr)

            lsfwriter.export_to_lsf()

        end = time.time()
        if debug:
            print('LSF Generation took %.4g seconds' % (end - start))

    def instantiate_flat_masters(self,
                                 master_list,  # type: Sequence[DesignMaster]
                                 name_list=None,  # type: Optional[Sequence[Optional[str]]]
                                 lib_name='',  # type: str
                                 debug=False,  # type: bool
                                 rename_dict=None,  # type: Optional[Dict[str, str]],
                                 draw_flat_gds=True,  # type: bool
                                 sort_by_layer=True,  # type: bool
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

        content_list = []
        start = time.time()
        for master, top_name in zip(master_list, name_list):
            content_list.append(
                (
                    master.cell_name,
                    [],
                    *self._flatten_instantiate_master_helper(
                        master=master,
                        debug=debug
                    )
                )
            )
        end = time.time()

        if not lib_name:
            lib_name = self.lib_name + '_flattened'
        if not lib_name:
            raise ValueError('master library name is not specified.')

        list_of_contents = ['', [], [], [], [], [], [], [], [], [], [], [], []]
        for content in content_list:
            for i, data in enumerate(content):
                list_of_contents[i] += data

        list_of_contents = [(list_of_contents[0], list_of_contents[1], list_of_contents[2],
                             list_of_contents[3], list_of_contents[4], list_of_contents[5],
                             list_of_contents[6], list_of_contents[7], list_of_contents[8],
                             list_of_contents[9], list_of_contents[10], list_of_contents[11],
                             list_of_contents[12])]

        self.flat_content_list = list_of_contents
        self.flat_content_list_separate = content_list

        if sort_by_layer is True:
            self.sort_flat_content_by_layers()

        if debug:
            print('master content retrieval took %.4g seconds' % (end - start))
        # TODO: put here or in different function?
        if draw_flat_gds:
            self.create_masters_in_db(lib_name, self.flat_content_list, debug=debug)

    def _flatten_instantiate_master_helper(self,
                                           master,  # type:
                                           debug=False,
                                           ):
        """Recursively passes through layout elements, and transforms (translation and rotation) all sub-hierarchy
        elements to create a flat design

        Parameters
        ----------
        master :
        debug

        Returns
        -------

        """
        start = time.time()

        master_content = master.get_content(self.lib_name, self.format_cell_name)

        (master_name, master_subinstances, new_rect_list, new_via_list, new_pin_list, new_path_list,
         new_blockage_list, new_boundary_list, new_polygon_list, new_round_list,
         new_sim_list, new_source_list, new_monitor_list) = master_content

        new_content_list = (new_rect_list, new_via_list, new_pin_list, new_path_list,
                            new_blockage_list, new_boundary_list, new_polygon_list, new_round_list,
                            new_sim_list, new_source_list, new_monitor_list)

        # For each instance in this level, recurse to get all its content
        for child_instance_info in master_subinstances:
            child_master_key = child_instance_info['master_key']
            child_master = self._master_lookup[child_master_key]

            child_content = self._flatten_instantiate_master_helper(
                master=child_master,
                debug=debug
            )

            transformed_child_content = self._transform_child_content(
                content=child_content,
                loc=child_instance_info['loc'],
                orient=child_instance_info['orient'],
                debug=debug,
            )

            # We got the children's info. Now append it to polygons within the current master
            for master_shapes, child_shapes in zip(new_content_list, transformed_child_content):
                master_shapes.extend(child_shapes)

        end = time.time()

        if debug:
            print("Done with _flatten_instance_master_helper.  Took " + str(end - start) + "s")

        return new_content_list

    def _transform_child_content(self,
                                 content,  # type: Tuple
                                 loc=(0, 0),  # type: coord_type
                                 orient='R0',  # type: str
                                 unit_mode=False,  # type: bool
                                 debug=False,  # type: bool
                                 ):
        """
        Translates and rotates the passed content list

        Parameters
        ----------
        content : Tuple
            The content list to be transformed
        loc : Tuple[Union[float, int], Union[float, int]]
            The translation vector
        orient : str
            The rotation string
        unit_mode : bool
            True if translation vector is in layout resolution units
        debug : bool
            True to print debug messages

        Returns
        -------
        new_content_list : tuple
            The translated and rotated content list
        """
        if debug:
            print('In _transform_child_content')

        (rect_list, via_list, pin_list, path_list, blockage_list, boundary_list, polygon_list, round_list,
         sim_list, source_list, monitor_list) = content

        new_rect_list = []
        new_via_list = []
        new_pin_list = []
        new_path_list = []
        new_blockage_list = []
        new_boundary_list = []
        new_polygon_list = []
        new_round_list = []
        new_sim_list = []
        new_source_list = []
        new_monitor_list = []

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
            new_via_list.append(
                PhotonicVia.from_content(
                    content=via,
                ).transform(
                    loc=loc,
                    orient=orient,
                    unit_mode=unit_mode,
                    copy=False
                ).content
            )

        # add pins
        for pin in pin_list:
            # TODO: pins...
            new_pin_list.append(pin)

        for path in path_list:
            new_path_list.append(
                PhotonicPath.from_content(
                    content=path,
                    resolution=self.grid.resolution
                ).transform(
                    loc=loc,
                    orient=orient,
                    unit_mode=unit_mode,
                    copy=False
                ).content
            )

        for blockage in blockage_list:
            new_blockage_list.append(
                PhotonicBlockage.from_content(
                    content=blockage,
                    resolution=self.grid.resolution
                ).transform(
                    loc=loc,
                    orient=orient,
                    unit_mode=unit_mode,
                    copy=False
                ).content
            )

        for boundary in boundary_list:
            new_boundary_list.append(
                PhotonicBoundary.from_content(
                    content=boundary,
                    resolution=self.grid.resolution
                ).transform(
                    loc=loc,
                    orient=orient,
                    unit_mode=unit_mode,
                    copy=False
                ).content
            )

        for polygon in polygon_list:
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

        for sim in sim_list:
            new_sim_list.append(sim)

        for source in source_list:
            new_sim_list.append(source)

        for monitor in monitor_list:
            new_sim_list.append(monitor)

        new_content_list = (new_rect_list, new_via_list, new_pin_list, new_path_list,
                            new_blockage_list, new_boundary_list, new_polygon_list, new_round_list,
                            new_sim_list, new_source_list, new_monitor_list)

        return new_content_list

    def get_polygon_point_lists_on_layer(self,
                                         layer,  # type: Tuple[str, str]
                                         debug=False,  # type: bool
                                         ):
        """
        Returns a list of all shapes

        Parameters
        ----------
        layer : Tuple[str, str]
            the layer purpose pair to get all shapes in shapely format
        debug : bool
            true to print debug info

        Returns
        -------

        """
        content = [self.get_content_on_layer(layer)]
        return self.to_polygon_pointlist_from_content_list(content_list=content, debug=debug)

    def get_content_on_layer(self,
                             layer,  # type: Tuple[str, str]
                             ):
        # type: (...) -> Tuple
        """Returns only the content that exists on a given layer

        Parameters
        ----------
        layer : Tuple[str, str]
            the layer whose content is desired

        Returns
        -------
        content : Tuple
            the shape content on the provided layer
        """
        if layer not in self.flat_content_list_by_layer.keys():
            return ()
        else:
            return self.flat_content_list_by_layer[layer]

    def sort_flat_content_by_layers(self):
        """
        Sorts the flattened content list into a dictionary of content lists, with keys corresponding to a given lpp

        Returns
        -------

        """

        (cell_name, _, rect_list, via_list, pin_list, path_list,
         blockage_list, boundary_list, polygon_list, round_list,
         sim_list, source_list, monitor_list) = self.flat_content_list[0]

        used_layers = []
        offset = 2

        for list_type_ind, list_content in enumerate([rect_list, via_list, pin_list, path_list,
                                                      blockage_list, boundary_list, polygon_list, round_list,
                                                      sim_list, source_list, monitor_list]):
            for content_item in list_content:
                layer = tuple(content_item['layer'])
                if layer not in used_layers:
                    used_layers.append(layer)
                    self.flat_content_list_by_layer[layer] = (cell_name, [], [], [], [], [], [], [], [], [], [], [], [])
                self.flat_content_list_by_layer[layer][offset + list_type_ind].append(content_item)

    def to_polygon_pointlist_from_content_list(self,
                                               content_list,  # type: List
                                               debug=False,  # type: bool
                                               ):
        # type: (...) -> Tuple[List, List]
        """
        Convert the provided content list into two lists of polygon pointlists.
        The first returned list represents the positive boundaries of polygons.
        The second returned list represents the 'negative' boundaries of holes in polygons.
        All shapes in the passed content list are converted, regardless of layer.
        It is expected that the content list passed to this function only has a single LPP's content

        Parameters
        ----------
        content_list : List
            The content list to be converted to a polygon pointlist
        debug : bool
            True to print debug information

        Returns
        -------
        positive_polygon_pointlist, negative_polygon_pointlist : Tuple[List, List]
            The positive shape and negative shape (holes) polygon boundaries
        """

        positive_polygon_pointlist = []
        negative_polygon_pointlist = []

        start = time.time()
        for content in content_list:
            (cell_name, inst_tot_list, rect_list, via_list, pin_list,
             path_list, blockage_list, boundary_list, polygon_list, round_list,
             sim_list, source_list, monitor_list) = content

            # add instances
            for inst_info in inst_tot_list:
                pass

            # add rectangles
            for rect in rect_list:
                nx, ny = rect.get('arr_nx', 1), rect.get('arr_ny', 1)
                if nx > 1 or ny > 1:
                    polygon_pointlist_pos_neg = PhotonicRect.polygon_pointlist_export(
                        rect['bbox'], nx, ny,
                        spx=rect['arr_spx'], spy=rect['arr_spy']
                    )
                else:
                    polygon_pointlist_pos_neg = PhotonicRect.polygon_pointlist_export(
                        rect['bbox']
                    )

                positive_polygon_pointlist.extend(polygon_pointlist_pos_neg[0])
                negative_polygon_pointlist.extend(polygon_pointlist_pos_neg[1])

            # add vias
            for via in via_list:
                pass

            # add pins
            for pin in pin_list:
                pass

            for path in path_list:
                # Treat like polygons
                polygon_pointlist_pos_neg = PhotonicPolygon.polygon_pointlist_export(path['polygon_points'])
                positive_polygon_pointlist.extend(polygon_pointlist_pos_neg[0])
                negative_polygon_pointlist.extend(polygon_pointlist_pos_neg[1])

            for blockage in blockage_list:
                pass

            for boundary in boundary_list:
                pass

            for polygon in polygon_list:
                polygon_pointlist_pos_neg = PhotonicPolygon.polygon_pointlist_export(polygon['points'])
                positive_polygon_pointlist.extend(polygon_pointlist_pos_neg[0])
                negative_polygon_pointlist.extend(polygon_pointlist_pos_neg[1])

            for round_obj in round_list:
                polygon_pointlist_pos_neg = PhotonicRound.polygon_pointlist_export(
                    rout=round_obj['rout'],
                    rin=round_obj['rin'],
                    theta0=round_obj['theta0'],
                    theta1=round_obj['theta1'],
                    center=round_obj['center'],
                    nx=round_obj.get('nx', 1),
                    ny=round_obj.get('ny', 1),
                    spx=round_obj.get('spx', 0.0),
                    spy=round_obj.get('spy', 0.0),
                    resolution=self.grid.resolution,
                )

                positive_polygon_pointlist.extend(polygon_pointlist_pos_neg[0])
                negative_polygon_pointlist.extend(polygon_pointlist_pos_neg[1])

        end = time.time()
        if debug:
            print('layout instantiation took %.4g seconds' % (end - start))

        return positive_polygon_pointlist, negative_polygon_pointlist

    def by_layer_polygon_list_to_flat_for_gds_export(self):
        """Converts a LPP-keyed dictionary of polygon pointlists to a flat content list format for GDS export"""
        polygon_content_list = []
        for layer, polygon_pointlists in self.post_dataprep_polygon_pointlist_by_layer.items():
            for polygon_points in polygon_pointlists:
                polygon_content_list.append(
                    dict(
                        layer=(layer[0], layer[1]),
                        points=polygon_points,
                    )
                )
        # TODO: get the right name
        self.post_dataprep_flat_content_list = [('dummy_name', [], [], [], [], [], [], [],
                                                 polygon_content_list, [])]

    def dataprep(self,
                 debug: bool=False,
                 push_portshapes_through_dataprep: bool=False,
                 ) -> None:
        """
        Takes the flat content list and performs the specified transformations on the shapes for the purpose
        of cleaning DRC and prepping tech specific functions.

        Algorithm
        ---------
        1) Take the shapes in the flattened content list and convert them to gdspy format
        2) Parse the dataprep spec file to extract the desired procedure defined through dataprep_groups
        3) Perform each dataprep operation on the provided layers in order. dataprep_groups is a list
        where each element contains 2 other lists:
            3a) lpp_in defines the layers that the operation will be performed on
            3b) lpp_ops defines the operation to be performed
            3c) Maps the operation in the spec file to its gdspy implementation and performs it
        4) Performs a final over_under_under_over operation
        5) Take the dataprepped gdspy shapes and import them into a new post-dataprep content list

        Parameters
        ----------
        debug : bool
            True to print debug information
        push_portshapes_through_dataprep : bool
            True to perform dataprep and convert the port indicator shapes
        """

        # 1) Convert layer shapes to gdspy polygon format
        start = time.time()
        for layer, gds_shapes in self.flat_content_list_by_layer.items():
            if debug:
                print("Converting layer content to gdspy:  Layer {}".format(layer))
            # TODO: fix Manhattan size
            if push_portshapes_through_dataprep or layer[1] != 'port' or layer[1] != 'label':
                self.flat_gdspy_polygonsets_by_layer[layer] = dataprep_coord_to_gdspy(
                    self.get_polygon_point_lists_on_layer(layer),
                    manh_grid_size=0.001,
                    do_manh=GLOBAL_DO_MANH_AT_BEGINNING,
                )
            if debug:
                end = time.time()
                print("Converting layer coordinate list to gdspy:  Layer {}  took {}s".format(layer, end - start))

        # 2) Parse the dataprep specification file
        with open(self.dataprep_file, 'r') as f:
            dataprep_info = yaml.load(f)

        # 3) Perform each dataprep operation in the list on the provided layers in order
        start = time.time()
        for dataprep_group in dataprep_info['dataprep_groups']:
            # 3a) Iteratively perform operations on all layers in lpp_in
            for lpp_in in dataprep_group['lpp_in']:
                shapes_in = self.flat_gdspy_polygonsets_by_layer.get(lpp_in, None)
                # 3b) Iteratively perform each operation on the current lpp_in
                for lpp_op in dataprep_group['lpp_ops']:
                    out_layer = (lpp_op[0], lpp_op[1])
                    operation = lpp_op[2]
                    amount = lpp_op[3]

                    if debug:
                        print("Doing dataprep op: {}  on layer {}  to "
                              "layer  {}  with size  {}".format(operation, lpp_in, out_layer, amount))

                    # 3c) Maps the operation in the spec file to the desired gdspy implementation and performs it
                    new_out_layer_polygons = poly_operation(
                        polygon1=self.flat_gdspy_polygonsets_by_layer.get(out_layer, None),
                        polygon2=shapes_in,
                        operation=operation,
                        size_amount=amount,
                        do_manh=GLOBAL_DO_MANH_DURING_OP,
                    )

                    # Update the layer's content
                    if new_out_layer_polygons is not None:
                        self.flat_gdspy_polygonsets_by_layer[out_layer] = new_out_layer_polygons
        if debug:
            end = time.time()
            print('All dataprep polygon operations took {}s'.format(end-start))

        # 4) Perform a final over_under_under_over operation
        start = time.time()
        if dataprep_info['over_under_under_over'] is None:
            dataprep_info['over_under_under_over'] = []

        for lpp in dataprep_info['over_under_under_over']:
            if debug:
                print("Doing final OUUO on layer {}".format(lpp))

            new_out_layer_polygons = poly_operation(
                polygon1=None,
                polygon2=self.flat_gdspy_polygonsets_by_layer.get(lpp, None),
                operation='ouo',
                size_amount=0,
                do_manh=GLOBAL_DO_MANH_AT_BEGINNING,
            )

            if new_out_layer_polygons is not None:
                self.flat_gdspy_polygonsets_by_layer[lpp] = new_out_layer_polygons
        if debug:
            end = time.time()
            print('Final OUUO took  {}s'.format(end-start))
            print('Starting gdspy/shapely polygon to polygon pointlist conversion')

        # 5) Take the dataprepped gdspy shapes and import them into a new post-dataprep content list
        start = time.time()
        # TODO: Replace the below code by having polyop_gdspy_to_point_list directly draw the gds... ?
        for layer, gdspy_polygons in self.flat_gdspy_polygonsets_by_layer.items():
            output_shapes = polyop_gdspy_to_point_list(gdspy_polygons,
                                                       fracture=True,
                                                       do_manh=GLOBAL_DO_FINAL_MANH,
                                                       manh_grid_size=self.grid.resolution,
                                                       debug=debug,
                                                       )
            new_shapes = []
            for shape in output_shapes:
                shape = tuple(map(tuple, shape))
                new_shapes.append([coord for coord in shape])
            self.post_dataprep_polygon_pointlist_by_layer[layer] = new_shapes

        self.by_layer_polygon_list_to_flat_for_gds_export()

        end = time.time()
        if debug:
            print('Converting from gdspy polygon manipulation format to a '
                  'flat list of polygon coords took {}s'.format(end-start))


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
        """Add a polygon to the layout. If photonic polygon object is passed, use it. User can also pass information to
        create a new photonic polygon.

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
                  round_obj,  # type: PhotonicRound
                  ):
        # type: (...) -> PhotonicRound
        """

        Parameters
        ----------
        round_obj : Optional[PhotonicRound]
            the polygon to add

        Returns
        -------
        polygon : PhotonicRound
            the added round object
        """

        self._layout.add_round(round_obj)
        return round_obj

    def add_path(self,
                 path,  # type: PhotonicPath
                 ):
        # type: (...) -> PhotonicPath
        """
        Adds a PhotonicPath to the layout object

        Parameters
        ----------
        path : PhotonicPath

        Returns
        -------
        path : PhotonicPath
        """
        self._layout.add_path(path)
        return path

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
                          overwrite=False,  # type: bool
                          show=True  # type: bool
                          ):
        # type: (...) -> PhotonicPort
        """Adds a photonic port to the current hierarchy.
        A PhotonicPort object can be passed, or will be constructed if the proper arguments are passed to this funciton.

        Parameters
        ----------
        name : str
            name to give the new port
        center : coord_type
            (x, y) location of the port
        orient : str
            orientation pointing INTO the port
        width : dim_type
            the port width
        layer : Union[str, Tuple[str, str]]
            the layer on which the port should be added. If only a string, the purpose is defaulted to 'port'
        resolution : Union[float, int]
            the grid resolution
        unit_mode : bool
            True if layout dimensions are specified in resolution units
        port : Optional[PhotonicPort]
            the PhotonicPort object to add. This argument can be provided in lieu of all the others.
        overwrite : bool
            True to add the port with the specified name even if another port with that name already exists in this
            level of the design hierarchy.
        show : bool
            True to draw the port indicator shape

        Returns
        -------
        port : PhotonicPort
            the added photonic port object
        """
        # TODO: Add support for renaming?
        # TODO: Remove force append?
        # TODO: Require layer name as input

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

        # Add port to port list. If name already is taken, remap port if overwrite is true
        if port.name not in self._photonic_ports.keys() or overwrite:
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

        if show is True:
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

        return port

    def has_photonic_port(self,
                          port_name,  # type: str
                          ):
        # type: (...) -> bool
        """Checks if the given port name exists in the current hierarchy level.

        Parameters
        ----------
        port_name : str
            the name of the port

        Returns
        -------
            : boolean
            true if port exists in current hierarchy level
        """
        return port_name in self._photonic_ports

    def get_photonic_port(self,
                          port_name='',  # type: Optional[str]
                          ):
        # type: (...) -> PhotonicPort
        """ Returns the photonic port object with the given name

        Parameters
        ----------
        port_name : Optional[str]
            the photonic port terminal name. If None or empty, check if this photonic template has only one port,
            and return it

        Returns
        -------
        port : PhotonicPort
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

    def add_instance(self,  # type: PhotonicTemplateBase
                     master,  # type: PhotonicTemplateBase
                     inst_name=None,  # type: Optional[str]
                     loc=(0, 0),  # type: Tuple[Union[float, int], Union[float, int]]
                     orient="R0",  # type: str
                     nx=1,  # type: int
                     ny=1,  # type: int
                     spx=0,  # type: Union[float, int]
                     spy=0,  # type: Union[float, int]
                     unit_mode=False,  # type: bool
                     ):
        # type: (...) -> PhotonicInstance
        """Adds a new (arrayed) instance to layout.

        Parameters
        ----------
        master : TemplateBase
            the master template object.
        inst_name : Optional[str]
            instance name.  If None or an instance with this name already exists,
            a generated unique name is used.
        loc : Tuple[Union[float, int], Union[float, int]]
            instance location.
        orient : str
            instance orientation.  Defaults to "R0"
        nx : int
            number of columns.  Must be positive integer.
        ny : int
            number of rows.  Must be positive integer.
        spx : Union[float, int]
            column pitch.  Used for arraying given instance.
        spy : Union[float, int]
            row pitch.  Used for arraying given instance.
        unit_mode : bool
            True if dimensions are given in resolution units.

        Returns
        -------
        inst : Instance
            the added instance.
        """
        res = self.grid.resolution
        if not unit_mode:
            loc = int(round(loc[0] / res)), int(round(loc[1] / res))
            spx = int(round(spx / res))
            spy = int(round(spy / res))

        inst = PhotonicInstance(self.grid, self._lib_name, master, loc=loc, orient=orient,
                                name=inst_name, nx=nx, ny=ny, spx=spx, spy=spy, unit_mode=True)

        self._layout.add_instance(inst)
        return inst

    def add_sim_obj(self, sim_obj):
        """ Add a new Lumerical simulation object to the db """
        self._layout.add_sim_obj(sim_obj)

    def add_source_obj(self, source_obj):
        """ Add a new Lumerical source object to the db """
        self._layout.add_sim_obj(source_obj)

    def add_monitor_obj(self, monitor_obj):
        """ Add a new Lumerical monitor object to the db """
        self._layout.add_sim_obj(monitor_obj)

    def add_instances_port_to_port(self,
                                   inst_master,  # type: PhotonicTemplateBase
                                   instance_port_name,  # type: str
                                   self_port_name,  # type: str
                                   instance_name=None,  # type: Optional[str]
                                   reflect=False,  # type: bool
                                   ):
        # type: (...) -> PhotonicInstance
        """
        Instantiates a new instance of the inst_master template.
        The new instance is placed such that its port named 'instance_port_name' is aligned-with and touching the
        'self_port_name' port of the current hierarchy level.

        The new instance is rotated about the new instance's master's origin until desired port is aligned.
        Optional reflection is performed after rotation, about the port axis.

        Parameters
        ----------
        inst_master : PhotonicTemplateBase
            the template master to be added
        instance_port_name : str
            the name of the port in the added instance to connect to
        self_port_name : str
            the name of the port in the current hierarchy to connect to
        instance_name : Optional[str]
            the name to give the new instance
        reflect : bool
            True to flip the added instance after rotation
        Returns
        -------
        new_inst : PhotonicInstance
            the newly added instance
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
        tmp_port_point = new_port.center_unit

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
        translation_vec = my_port.center_unit - rotated_tmp_port_point

        new_inst = self.add_instance(
            master=inst_master,
            inst_name=instance_name,
            loc=(translation_vec[0], translation_vec[1]),
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
                              port_name,  # type: Optional[str]
                              ):
        # type: (...) -> str
        """Returns a new unique name for a port in the current hierarchy level

        Parameters
        ----------
        port_name : Optional[str]
            base port name. If no value is supplied, 'PORT' is used as the base name

        Returns
        -------
        new_name : str
            new unique port name
        """

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
                               inst,  # type: Union[PhotonicInstance, Instance]
                               port_names=None,  # type: Optional[Union[str, List[str]]]
                               port_renaming=None,  # type: Optional[Dict[str, str]]
                               unmatched_only=True,  # type: bool
                               show=True  # type: bool
                               ):
        # type: (...) -> None
        """Brings ports from lower level of hierarchy to the current hierarchy level

        Parameters
        ----------
        inst : PhotonicInstance
            the instance that contains the ports to be extracted
        port_names : Optional[Union[str, List[str]]
            the port name or list of port names re-export. If not supplied, all ports of the inst will be extracted
        port_renaming : Optional[Dict[str, str]]
            a dictionary containing key-value pairs mapping inst's port names (key)
            to the new desired port names (value).
            If not supplied, extracted ports will be given their original names
        unmatched_only : bool
        show : bool

        Returns
        -------

        """
        # TODO: matched vs non-matched ports.  IE, if two ports are already matched, do we export them
        if port_names is None:
            port_names = inst.master.photonic_ports_names_iter()

        if isinstance(port_names, str):
            port_names = [port_names]

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
                # Append unique number
                new_name = self._get_unused_port_name(new_name)

            self.add_photonic_port(
                name=new_name,
                center=new_location,
                orient=new_orient,
                width=old_port.width_unit,
                layer=old_port.layer,
                unit_mode=True,
                show=show
            )

    def add_via_stack(self,
                      bot_layer,  # type: str
                      top_layer,  # type: str
                      loc,  # type: Tuple[Union[float, int], Union[float, int]]
                      min_area_on_bot_top_layer=False,  # type: bool
                      unit_mode=False,  # type: bool
                      ):
        """
        Adds a via stack with one via in each layer at the provided location.
        All intermediate layers will be enclosed with an enclosure that satisfies both via rules and min area rules

        Parameters
        ----------
        bot_layer : str
            Name of the bottom layer
        top_layer : str
            Name of the top layer
        loc :
            (x, y) location of the center of the via stack
        min_area_on_bot_top_layer : bool
            True to have enclosures on top and bottom layer satisfy minimum area constraints
        unit_mode
            True if input argument is specified in layout resolution units

        Returns
        -------

        """
        if not unit_mode:
            loc = (int(round(loc[0] / self.grid.resolution)), int(round(loc[1] / self.grid.resolution)))

        bot_layer = bag.io.fix_string(bot_layer)
        top_layer = bag.io.fix_string(top_layer)

        bot_layer_id_global = self.grid.tech_info.get_layer_id(bot_layer)
        top_layer_id_global = self.grid.tech_info.get_layer_id(top_layer)

        for bot_lay_id in range(bot_layer_id_global, top_layer_id_global):

            bot_lay_name = self.grid.tech_info.get_layer_name(bot_lay_id)
            if isinstance(bot_lay_name, list):
                bot_lay_name = bot_layer
            bot_lay_type = self.grid.tech_info.get_layer_type(bot_lay_name)

            top_lay_name = self.grid.tech_info.get_layer_name(bot_lay_id + 1)
            top_lay_type = self.grid.tech_info.get_layer_type(top_lay_name)

            via_name = self.grid.tech_info.get_via_name(bot_lay_id)
            via_type_list = self.grid.tech_info.get_via_types(bmtype=bot_lay_type,
                                                              tmtype=top_lay_type)

            for via_type, weight in via_type_list:
                try:
                    (sp, sp2_list, sp3, dim, enc_b, arr_enc_b, arr_test_b) = self.grid.tech_info.get_via_drc_info(
                        vname=via_name,
                        vtype=via_type,
                        mtype=bot_lay_type,
                        mw_unit=0,
                        is_bot=True,
                    )

                    (_, _, _, _, enc_t, arr_enc_t, arr_test_t) = self.grid.tech_info.get_via_drc_info(
                        vname=via_name,
                        vtype=via_type,
                        mtype=top_lay_type,
                        mw_unit=0,
                        is_bot=True,
                    )
                # Didnt get valid via info
                except ValueError:
                    continue

                # Got valid via info. just draw the first one we get, then break
                # Need to find the right extensions. Want the centered one? all are valid...
                # TODO: for now taking the first
                enc_b = enc_b[0]
                enc_t = enc_t[0]

                # Fix minimum area violations:
                if bot_lay_id > bot_layer_id_global or min_area_on_bot_top_layer:
                    min_area = self.grid.tech_info.get_min_area(bot_lay_type)
                    if (2 * enc_b[0] + dim[0]) * (2 * enc_b[1] + dim[1]) < min_area:
                        min_side_len_unit = int(np.ceil(np.sqrt(min_area)))
                        enc_b = [np.ceil((min_side_len_unit - dim[0]) / 2), np.ceil((min_side_len_unit - dim[1]) / 2)]

                if bot_lay_id + 1 < top_layer_id_global or min_area_on_bot_top_layer:
                    min_area = self.grid.tech_info.get_min_area(top_lay_type)
                    if (2 * enc_t[0] + dim[0]) * (2 * enc_t[1] + dim[1]) < min_area:
                        min_side_len_unit = int(np.ceil(np.sqrt(min_area)))
                        enc_t = [np.ceil((min_side_len_unit - dim[0]) / 2), np.ceil((min_side_len_unit - dim[1]) / 2)]

                self.add_via_primitive(
                    via_type=self.grid.tech_info.get_via_id(bot_layer=bot_lay_name, top_layer=top_lay_name),
                    loc=loc,
                    num_rows=1,
                    num_cols=1,
                    sp_rows=0,
                    sp_cols=0,
                    enc1=[enc_b[0], enc_b[0], enc_b[1], enc_b[1]],
                    enc2=[enc_t[0], enc_t[0], enc_t[1], enc_t[1]],
                    orient='R0',
                    cut_width=dim[0],
                    cut_height=dim[1],
                    nx=1,
                    ny=1,
                    spx=0,
                    spy=0,
                    unit_mode=True,
                )

    def add_via_stack_by_ind(self,
                             bot_layer_ind,  # type: int
                             top_layer_ind,  # type: int
                             loc,  # type: Tuple[Union[float, int], Union[float, int]]
                             min_area_on_bot_top_layer=False,  # type: bool
                             unit_mode=False,  # type: bool
                             ):
        return self.add_via_stack(
            bot_layer=self.grid.tech_info.get_layer_name(bot_layer_ind),
            top_layer=self.grid.tech_info.get_layer_name(top_layer_ind),
            loc=loc,
            min_area_on_bot_top_layer=min_area_on_bot_top_layer,
            unit_mode=unit_mode
        )
