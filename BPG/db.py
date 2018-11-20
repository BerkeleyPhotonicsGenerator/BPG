import os
import yaml
import time
import logging
from collections import OrderedDict
from numpy import pi
from memory_profiler import memory_usage

# BAG Imports
from bag.core import BagProject, RoutingGrid
from bag.io import get_encoding
from bag.layout.template import TemplateDB
from bag.util.cache import _get_unique_name, DesignMaster

# BPG Imports
from BPG.compiler.dataprep_gdspy import Dataprep
from .objects import PhotonicRect, PhotonicPolygon, PhotonicRound, \
    PhotonicVia, PhotonicBlockage, PhotonicBoundary, PhotonicPath, PhotonicPinInfo
from BPG import LumericalDesignGenerator
from .lumerical.core import LumericalPlugin

from typing import TYPE_CHECKING, Union, Dict, Any, Optional, Tuple, Sequence
if TYPE_CHECKING:
    from bag.layout.objects import ViaInfo, PinInfo
    from bag.layout.objects import InstanceInfo
    from BPG.photonic_core import PhotonicTechInfo

try:
    import gdspy
except ImportError:
    gdspy = None
try:
    import cybagoa
except ImportError:
    cybagoa = None

dim_type = Union[float, int]
coord_type = Tuple[dim_type, dim_type]


class PhotonicTemplateDB(TemplateDB):
    def __init__(self: "PhotonicTemplateDB",
                 lib_defs: str,
                 routing_grid: "RoutingGrid",
                 libname: str,
                 prj: Optional[BagProject] = None,
                 name_prefix: str = '',
                 name_suffix: str = '',
                 use_cybagoa: bool = False,
                 gds_lay_file: str = '',
                 flatten: bool = False,
                 gds_filepath: str = '',
                 lsf_filepath: str = '',
                 photonic_tech_info: "PhotonicTechInfo" = None,
                 **kwargs,
                 ):
        TemplateDB.__init__(self, lib_defs, routing_grid, libname, prj,
                            name_prefix, name_suffix, use_cybagoa, gds_lay_file,
                            flatten, **kwargs)

        # Where all generated layout content will be stored, in BAG content list format
        self.content_list = None
        # Where flattened layout content will be stored, in BAG content list format
        self.flat_content_list = None
        self.flat_content_list_separate = None
        # Variable where flattened layout content will be stored, by layer.
        # Format is a dictionary whose keys are LPPs, and whose values are BAG content list format
        self.flat_content_list_by_layer = {}  # type: Dict[Tuple[str, str], Tuple]
        self.flat_gdspy_polygonsets_by_layer = {}
        self.post_dataprep_polygon_pointlist_by_layer = {}
        self.post_dataprep_flat_content_list = []
        self.lsf_post_dataprep_flat_content_list = []

        self.gds_filepath = gds_filepath
        self.lsf_filepath = lsf_filepath

        self.photonic_tech_info = photonic_tech_info
        self.dataprep_routine_filepath = photonic_tech_info.dataprep_routine_filepath
        self.dataprep_params_filepath = photonic_tech_info.dataprep_parameters_filepath
        self.lsf_export_file = photonic_tech_info.lsf_export_path
        self._export_gds = True
        self.dataprep_object = None
        self.lsf_dataprep_object = None
        self.impl_cell = None

    @property
    def export_gds(self):
        # type: () -> bool
        return self._export_gds

    @export_gds.setter
    def export_gds(self, val):
        # type: (bool) -> None
        self._export_gds = val

    def create_masters_in_db(self, lib_name, content_list, export_gds=None):
        # type: (str, Sequence[Any], bool) -> None
        """Create the masters in the design database.

        Parameters
        ----------
        lib_name : str
            library to create the designs in.
        content_list : Sequence[Any]
            a list of the master contents.  Must be created in this order.
        export_gds : bool
            True to export the gds.
            False to not export a gds even if a gds layermap is provided.
        """
        if self._prj is None:
            raise ValueError('BagProject is not defined.')
        if export_gds is None:
            export_gds = self._export_gds

        if self._gds_lay_file and export_gds:
            self._create_gds(lib_name, content_list)
        elif self._use_cybagoa:
            # remove write locks from old layouts
            cell_view_list = [(item[0], 'layout') for item in content_list]
            if self._pure_oa:
                pass
            else:
                # create library if it does not exist
                self._prj.create_library(self._lib_name)
                self._prj.release_write_locks(self._lib_name, cell_view_list)

            logging.info(f'Instantiating layout')

            # create OALayouts
            start = time.time()
            if 'CDSLIBPATH' in os.environ:
                cds_lib_path = os.path.abspath(os.path.join(os.environ['CDSLIBPATH'], 'cds.lib'))
            else:
                cds_lib_path = os.path.abspath('./cds.lib')
            with cybagoa.PyOALayoutLibrary(cds_lib_path, self._lib_name, self._prj.default_lib_path,
                                           self._prj.tech_info.via_tech_name,
                                           get_encoding()) as lib:
                lib.add_layer('prBoundary', 235)
                lib.add_purpose('label', 237)
                lib.add_purpose('drawing1', 241)
                lib.add_purpose('drawing2', 242)
                lib.add_purpose('drawing3', 243)
                lib.add_purpose('drawing4', 244)
                lib.add_purpose('drawing5', 245)
                lib.add_purpose('drawing6', 246)
                lib.add_purpose('drawing7', 247)
                lib.add_purpose('drawing8', 248)
                lib.add_purpose('drawing9', 249)
                lib.add_purpose('boundary', 250)
                lib.add_purpose('pin', 251)

                for cell_name, oa_layout in content_list:
                    lib.create_layout(cell_name, 'layout', oa_layout)
            end = time.time()
            logging.info(f'Layout instnatiation took {end-start:.4g}s')
        else:
            # create library if it does not exist
            self._prj.create_library(self._lib_name)

            logging.info(f'Instantiating layout')

            via_tech_name = self._grid.tech_info.via_tech_name
            start = time.time()
            self._prj.instantiate_layout(self._lib_name, 'layout', via_tech_name, content_list)
            end = time.time()
            logging.info(f'Layout instnatiation took {end-start:.4g}s')

    def instantiate_masters(self,
                            master_list,  # type: Sequence[DesignMaster]
                            name_list=None,  # type: Optional[Sequence[Optional[str]]]
                            lib_name='',  # type: str
                            debug=False,  # type: bool
                            rename_dict=None,  # type: Optional[Dict[str, str]]
                            ) -> None:
        """
        Create all given masters in the database. Currently, this is being overridden so that the content_list is stored
        locally. This is a little hacky, and may need to be changed pending further testing

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

        self.create_masters_in_db(lib_name, self.content_list)

    def _create_gds(self,
                    lib_name: str,
                    content_list: Sequence[Any],
                    debug: bool = False,
                    ) -> None:
        """Create a GDS file containing the given layouts

        Parameters
        ----------
        lib_name : str
            library to create the designs in.
        content_list : Sequence[Any]
            a list of the master contents.  Must be created in this order.
        """
        logging.info(f'In PhotonicTemplateDB._create_gds')

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
        logging.info(f'Instantiating gds layout')

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
        logging.info(f'Layout gds instantiation took {end - start:.4g}s')

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

    def to_lumerical_plugin(self,
                            gds_layermap: str,
                            lsf_export_config: str,
                            lsf_filepath: str,
                            ) -> None:
        config = dict(gds_layermap=gds_layermap,
                      lsf_export_config=lsf_export_config,
                      lsf_filepath=lsf_filepath)
        plugin = LumericalPlugin(config)

        # Generate the dataprepped content list
        if self.flat_content_list_separate is None:
            raise ValueError('Please generate a flat GDS before exporting to Lumerical')

        # Run the lsf_dataprep procedure in lsf_export_config and generate a gds from the content list
        self.lsf_dataprep()
        content_list = self.lsf_post_dataprep_flat_content_list
        self.create_masters_in_db(lib_name='_lsf_dp', content_list=content_list)

        # Export the actual data to LSF
        plugin.export_content_list(content_list)

    def instantiate_flat_masters(self,
                                 master_list: Sequence[DesignMaster],
                                 name_list: Optional[Sequence[Optional[str]]] = None,
                                 lib_name: str = '',
                                 rename_dict: Optional[Dict[str, str]] = None,
                                 draw_flat_gds: bool = True,
                                 sort_by_layer: bool = True,
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
        rename_dict : Optional[Dict[str, str]]
            optional master cell renaming dictionary.
        draw_flat_gds : bool
            If true, this method will also create a gds file
        sort_by_layer : bool
            If true, this method will also generate a content list organized by layer
        """
        logging.info(f'In PhotonicTemplateDB.instantiate_flat_masters')

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

        logging.debug('Retreiving master contents')

        content_list = []
        start = time.time()
        for master, top_name in zip(master_list, name_list):
            content_list.append(
                (
                    master.cell_name,
                    [],
                    *self._flatten_instantiate_master_helper(
                        master=master,
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

        logging.info(f'Master content retrieval took {end - start:.4g}s')

        # TODO: put here or in different function?
        if draw_flat_gds:
            self.create_masters_in_db(lib_name, self.flat_content_list)

        if (len(name_list) == 1):
            # If called from generate_flat_gds, name_list is just [self.specs['impl_cell']]
            self.impl_cell = name_list[0]

    def _flatten_instantiate_master_helper(self,
                                           master: DesignMaster,
                                           hierarchy_name: Optional[str] = None,
                                           ) -> Tuple:
        """Recursively passes through layout elements, and transforms (translation and rotation) all sub-hierarchy
        elements to create a flat design

        Parameters
        ----------
        master : DesignMaster
            The master that should be flattened.
        hierarchy_name : Optional[str]
            The name describing the hierarchy to get the the particular master being flattened.
            Should only be None when a top level cell is being flattened in PhotonicTemplateDB.instantiate_flat_masters.
        Returns
        -------
        new_content_list : Tuple
            The content list of the flattened master
        """
        # If hierarchy_name is not provided, get the name from the master itself. This shoul
        if hierarchy_name is None:
            hierarchy_name = master.__class__.__name__

        logging.debug(f'PhotonicTemplateDB._flatten_instantiate_master_helper called on {hierarchy_name}')

        start = time.time()

        master_content = master.get_content(self.lib_name, self.format_cell_name)

        (master_name, master_subinstances, new_rect_list, new_via_list, new_pin_list, new_path_list,
         new_blockage_list, new_boundary_list, new_polygon_list, new_round_list,
         new_sim_list, new_source_list, new_monitor_list) = master_content

        with open(self._gds_lay_file, 'r') as f:
            lay_info = yaml.load(f)
            via_info = lay_info['via_info']

        for via in new_via_list:

            # TODO:
            via_lay_info = via_info[via.id]

            nx, ny = via.arr_nx, via.arr_ny
            x0, y0 = via.loc
            if nx > 1 or ny > 1:
                spx, spy = via.arr_spx, via.arr_spy
                for xidx in range(nx):
                    xc = x0 + xidx * spx
                    for yidx in range(ny):
                        yc = y0 + yidx * spy
                        new_polygon_list.extend(self.via_to_polygon_list(via, via_lay_info, xc, yc))

            else:
                new_polygon_list.extend(self.via_to_polygon_list(via, via_lay_info, x0, y0))

        # TODO: do we need to clean up the new_via_list here or just keep it?
        new_via_list = []

        new_content_list = (new_rect_list.copy(),
                            new_via_list.copy(),
                            new_pin_list.copy(),
                            new_path_list.copy(),
                            new_blockage_list.copy(),
                            new_boundary_list.copy(),
                            new_polygon_list.copy(),
                            new_round_list.copy(),
                            new_sim_list.copy(),
                            new_source_list.copy(),
                            new_monitor_list.copy()
                            )

        # For each instance in this level, recurse to get all its content
        for child_instance_info in master_subinstances:
            child_master_key = child_instance_info['master_key']
            child_master = self._master_lookup[child_master_key]
            hierarchy_name_addon = f'{child_master.__class__.__name__}'
            if child_instance_info['name'] is not None:
                hierarchy_name_addon += f'(inst_name={child_instance_info["name"]})'

            child_content = self._flatten_instantiate_master_helper(
                master=child_master,
                hierarchy_name=f'{hierarchy_name}.{hierarchy_name_addon}'
            )
            transformed_child_content = self._transform_child_content(
                content=child_content,
                loc=child_instance_info['loc'],
                orient=child_instance_info['orient'],
                child_name=f'{hierarchy_name}.{hierarchy_name_addon}'
            )

            # We got the children's info. Now append it to polygons within the current master
            for master_shapes, child_shapes in zip(new_content_list, transformed_child_content):
                master_shapes.extend(child_shapes)

        end = time.time()

        logging.debug(f'PhotonicTemplateDB._flatten_instantiate_master_helper finished on '
                      f'{hierarchy_name}: \n'
                      f'\t\t\t\t\t\t\t\t\t\tflattening took {end - start:.4g}s.\n'
                      f'\t\t\t\t\t\t\t\t\t\tCurrent memory usage: {memory_usage(-1)} MiB')

        return new_content_list

    def _transform_child_content(self,
                                 content: Tuple,
                                 loc: coord_type = (0, 0),
                                 orient: str = 'R0',
                                 unit_mode: bool = False,
                                 child_name: Optional[str] = None,
                                 ) -> Tuple:
        """
        Translates and rotates the passed content list

        Parameters
        ----------
        content : Tuple
            The content list to be transformed.
        loc : Tuple[Union[float, int], Union[float, int]]
            The translation vector.
        orient : str
            The rotation string.
        unit_mode : bool
            True if translation vector is in layout resolution units.
        child_name : Optional[str]
            The hierarchy name of the instance being transformed.

        Returns
        -------
        new_content_list : tuple
            The translated and rotated content list.
        """
        logging.debug(f'PhotonicTemplateDB._transform_child_content called on {child_name}')

        (rect_list, via_list, pin_list, path_list, blockage_list, boundary_list, polygon_list, round_list,
         sim_list, source_list, monitor_list) = content

        new_rect_list = []
        new_via_list = []  # via list which can not be handled by DataPrep
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

            # TODO:
            with open(self._gds_lay_file, 'r') as f:
                lay_info = yaml.load(f)
                via_info = lay_info['via_info']
            via_lay_info = via_info[via.id]

            nx, ny = via.arr_nx, via.arr_ny
            x0, y0 = via.loc
            if nx > 1 or ny > 1:
                spx, spy = via.arr_spx, via.arr_spy
                for xidx in range(nx):
                    xc = x0 + xidx * spx
                    for yidx in range(ny):
                        yc = y0 + yidx * spy
                        polygon_list.extend(self.via_to_polygon_list(via, via_lay_info, xc, yc))

            else:
                polygon_list.extend(self.via_to_polygon_list(via, via_lay_info, x0, y0))

        # add pins
        for pin in pin_list:
            new_pin_list.append(
                PhotonicPinInfo.from_content(
                    content=pin,
                    resolution=self.grid.resolution
                ).transform(
                    loc=loc,
                    orient=orient,
                    unit_mode=unit_mode,
                    copy=False
                )
            )

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

        # TODO: do we need to clean up the new_via_list here or just keep it?
        new_via_list = []
        new_content_list = (new_rect_list, new_via_list, new_pin_list, new_path_list,
                            new_blockage_list, new_boundary_list, new_polygon_list, new_round_list,
                            new_sim_list, new_source_list, new_monitor_list)

        return new_content_list

    @staticmethod
    def via_to_polygon_list(via, via_lay_info, x0, y0):
        blay = via_lay_info['bot_layer']
        tlay = via_lay_info['top_layer']
        vlay = via_lay_info['via_layer']
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

        bot_left, bot_bot, bot_right, bot_top = x0 - bl, y0 - bb, x0 + w_arr + br, y0 + h_arr + bt
        top_left, top_bot, top_right, top_top = x0 - tl, y0 - tb, x0 + w_arr + tr, y0 + h_arr + tt

        bot_polygon = {
            'layer': blay,
            'points': [(bot_left, bot_bot), (bot_left, bot_top), (bot_right, bot_top), (bot_right, bot_bot)]
        }
        top_polygon = {
            'layer': tlay,
            'points': [(top_left, top_bot), (top_left, top_top), (top_right, top_top), (top_right, top_bot)]
        }

        polygon_list = [bot_polygon, top_polygon]

        for xidx in range(num_cols):
            dx = xidx * (cw + sp_cols)
            via_left, via_right = x0 + dx, x0 + cw + dx
            for yidx in range(num_rows):
                dy = yidx * (ch + sp_rows)
                via_bot, via_top = y0 + dy, y0 + ch + dy
                via_polygon = {
                    'layer': vlay,
                    'points': [(via_left, via_bot), (via_left, via_top), (via_right, via_top), (via_right, via_bot)]
                }
                polygon_list.append(via_polygon)

        return polygon_list

    def sort_flat_content_by_layers(self):
        """
        Sorts the flattened content list into a dictionary of content lists, with keys corresponding to a given lpp

        Notes
        -----
        1) Unpack the flattened content list
        2) Loop over objects in the content list, ignoring vias
        3) Create new layer dictionary key if object layer is new, and whose value is a content list style array
        4) Append object to proper location in the per-layer content list array

        Returns
        -------

        """

        # 1) Unpack the flattened content list
        (cell_name, _, rect_list, via_list, pin_list, path_list,
         blockage_list, boundary_list, polygon_list, round_list,
         sim_list, source_list, monitor_list) = self.flat_content_list[0]

        used_layers = []
        offset = 2

        # 2) Loop over objects in the content list, ignoring vias
        for list_type_ind, list_content in enumerate([rect_list, via_list, pin_list, path_list,
                                                      blockage_list, boundary_list, polygon_list, round_list,
                                                      sim_list, source_list, monitor_list]):
            # Ignore vias
            if list_type_ind != 1:
                # 3) Create new layer dictionary key if object layer is new,
                # and whose value is a content list style array
                for content_item in list_content:
                    layer = tuple(content_item['layer'])
                    if layer not in used_layers:
                        used_layers.append(layer)
                        self.flat_content_list_by_layer[layer] = (
                            cell_name, [], [], [], [], [], [], [], [], [], [], [], []
                        )
                    # 4) Append object to proper location in the per-layer content list array
                    self.flat_content_list_by_layer[layer][offset + list_type_ind].append(content_item)

    def dataprep(self):
        # Initialize dataprep structure
        # Call dataprep method
        logging.info(f'In PhotonicTemplateDB.dataprep')
        self.dataprep_object = Dataprep(self.photonic_tech_info,
                                        self.grid,
                                        self.flat_content_list_by_layer,
                                        self.flat_content_list_separate,
                                        is_lsf=False,
                                        impl_cell=self.impl_cell)
        start = time.time()
        self.post_dataprep_flat_content_list = self.dataprep_object.dataprep()
        end = time.time()
        logging.info(f'All dataprep operations completed in {end - start:.4g} s')

    def lsf_dataprep(self):
        logging.info(f'In PhotonicTemplateDB.lsf_dataprep')
        self.lsf_dataprep_object = Dataprep(self.photonic_tech_info,
                                            self.grid,
                                            self.flat_content_list_by_layer,
                                            self.flat_content_list_separate,
                                            is_lsf=True
                                            )
        start = time.time()
        self.lsf_post_dataprep_flat_content_list = self.lsf_dataprep_object.dataprep()
        end = time.time()
        logging.info(f'All LSF dataprep operations completed in {end - start:.4g} s')
