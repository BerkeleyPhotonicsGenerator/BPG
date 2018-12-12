import yaml
import time
import logging
from collections import OrderedDict
from memory_profiler import memory_usage
from copy import deepcopy

# BAG Imports
from bag.layout.template import TemplateDB
from bag.util.cache import _get_unique_name

# BPG Imports
from .objects import PhotonicRect, PhotonicPolygon, PhotonicRound, PhotonicVia, PhotonicBlockage, PhotonicBoundary, \
    PhotonicPath, PhotonicPinInfo
from .content_list import ContentList

# Plugin Imports
from .lumerical.core import LumericalPlugin
from .gds.core import GDSPlugin
from .compiler.dataprep_gdspy import Dataprep

# Typing Imports
from typing import TYPE_CHECKING, Union, Dict, Any, Optional, Tuple, Sequence

if TYPE_CHECKING:
    from BPG.photonic_core import PhotonicTechInfo
    from bag.util.cache import DesignMaster
    from bag.core import RoutingGrid
    from bag.core import BagProject
    from BPG.template import PhotonicTemplateBase

dim_type = Union[float, int]
coord_type = Tuple[dim_type, dim_type]


class PhotonicTemplateDB(TemplateDB):
    def __init__(self,
                 lib_defs: str,
                 routing_grid: 'RoutingGrid',
                 libname: str,
                 prj: Optional['BagProject'] = None,
                 name_prefix: str = '',
                 name_suffix: str = '',
                 use_cybagoa: bool = False,
                 gds_lay_file: str = '',
                 flatten: bool = False,
                 gds_filepath: str = '',
                 lsf_filepath: str = '',
                 photonic_tech_info: 'PhotonicTechInfo' = None,
                 **kwargs,
                 ):
        TemplateDB.__init__(self,
                            lib_defs,
                            routing_grid,
                            libname, prj,
                            name_prefix,
                            name_suffix,
                            use_cybagoa,
                            gds_lay_file,
                            flatten,
                            **kwargs)
        # Content list vars
        self.content_list = None
        self.flat_content_list = None
        self.flat_content_list_separate = None
        # Keys are LPPs and values are BAG content list format
        self.flat_content_list_by_layer = {}  # type: Dict[Tuple[str, str], Tuple]
        self.flat_gdspy_polygonsets_by_layer = {}
        self.post_dataprep_polygon_pointlist_by_layer = {}
        self.post_dataprep_flat_content_list = []
        self.lsf_post_dataprep_flat_content_list = []

        # Path to output gds and lsf storage
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

    def to_gds_plugin(self,
                      lib_name: str,
                      content_list: Sequence[Any],
                      ) -> None:
        """
        Generates a GDS file from the provided content list using the built-in GDS plugin

        Parameters
        ----------
        lib_name : str
            Name of the library to be created in the GDS
        content_list : Sequence[Any]
            The main db containing all of the physical design information
        """
        plugin = GDSPlugin(grid=self.grid,
                           gds_layermap=self._gds_lay_file,
                           gds_filepath=self.gds_filepath,
                           lib_name=lib_name)
        plugin.export_content_list(content_list=content_list)

    def to_lumerical_plugin(self,
                            lsf_export_config: str,
                            lsf_filepath: str,
                            ) -> None:
        """
        Runs lsf_dataprep on the current content list and generates an LSF file

        Parameters
        ----------
        lsf_export_config : str
            path to yaml file with all of the configuration for lumerical support
        lsf_filepath : str
            path to where the output lsf files will be stored
        """
        plugin = LumericalPlugin(lsf_export_config=lsf_export_config,
                                 lsf_filepath=lsf_filepath)

        # Generate the dataprepped content list
        if self.flat_content_list_separate is None:
            raise ValueError('Please generate a flat GDS before exporting to Lumerical')

        # Run the lsf_dataprep procedure in lsf_export_config and generate a gds from the content list
        self.lsf_dataprep()
        content_list = self.lsf_post_dataprep_flat_content_list  # TODO: Remove implicit storage of content
        self.to_gds_plugin(lib_name='_lsf_dp', content_list=content_list)

        # Export the actual data to LSF
        plugin.export_content_list(content_list)

    def dataprep(self) -> None:
        """
        Initializes the dataprep plugin with the standard tech info and runs the dataprep procedure
        """
        logging.info(f'In PhotonicTemplateDB.dataprep')
        self.dataprep_object = Dataprep(photonic_tech_info=self.photonic_tech_info,
                                        grid=self.grid,
                                        flat_content_list_by_layer=self.flat_content_list_by_layer,
                                        flat_content_list_separate=self.flat_content_list_separate,
                                        is_lsf=False,
                                        impl_cell=self.impl_cell)
        start = time.time()
        self.post_dataprep_flat_content_list = self.dataprep_object.dataprep()
        end = time.time()
        logging.info(f'All dataprep operations completed in {end - start:.4g} s')

    def lsf_dataprep(self) -> None:
        """
        Initializes the dataprep plugin with the lumerical tech info and runs the dataprep procedure
        """
        logging.info(f'In PhotonicTemplateDB.lsf_dataprep')
        self.lsf_dataprep_object = Dataprep(photonic_tech_info=self.photonic_tech_info,
                                            grid=self.grid,
                                            flat_content_list_by_layer=self.flat_content_list_by_layer,
                                            flat_content_list_separate=self.flat_content_list_separate,
                                            is_lsf=True)
        start = time.time()
        self.lsf_post_dataprep_flat_content_list = self.lsf_dataprep_object.dataprep()
        end = time.time()
        logging.info(f'All LSF dataprep operations completed in {end - start:.4g} s')

    def generate_content_list(self,
                              master_list,  # type: Sequence[DesignMaster]
                              name_list=None,  # type: Optional[Sequence[Optional[str]]]
                              lib_name='',  # type: str
                              debug=False,  # type: bool
                              rename_dict=None,  # type: Optional[Dict[str, str]]
                              ) -> Sequence[ContentList]:
        """
        Create the content list from the provided masters and returns it.

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

        Returns
        -------
        content_list : Sequence[Any]
            Generated content list of the provided masters
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
        for master, top_name in zip(master_list, name_list):
            self._instantiate_master_helper(info_dict, master)

        if not lib_name:
            lib_name = self.lib_name
        if not lib_name:
            raise ValueError('master library name is not specified.')

        content_list = [master.get_content(lib_name, self.format_cell_name)
                        for master in info_dict.values()]
        return content_list

    def instantiate_flat_masters(self,
                                 master_list: Sequence['PhotonicTemplateBase'],
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

        if draw_flat_gds:
            self.to_gds_plugin(lib_name, self.flat_content_list)

        if len(name_list) == 1:
            # If called from generate_flat_gds, name_list is just [self.specs['impl_cell']]
            self.impl_cell = name_list[0]

    def _flatten_instantiate_master_helper(self,
                                           master: 'PhotonicTemplateBase', # DesignMaster
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

        master_content: ContentList = master.get_content(self.lib_name, self.format_cell_name).copy()

        with open(self._gds_lay_file, 'r') as f:
            lay_info = yaml.load(f)
            via_info = lay_info['via_info']

        # Convert vias into polygons on the via and enclosure layers
        master_content.via_to_polygon_and_delete(via_info)

        new_content_list = master_content.copy_layout_shapes()

        # For each instance in this level, recurse to get all its content
        for child_instance_info in master_content.inst_list:
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
