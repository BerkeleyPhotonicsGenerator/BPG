import yaml
import time
import logging
from collections import OrderedDict
from memory_profiler import memory_usage

# BAG Imports
from bag.layout.template import TemplateDB
from bag.util.cache import _get_unique_name

# BPG Imports
from .content_list import ContentList

# Plugin Imports
from .lumerical.core import LumericalPlugin
from .gds.core import GDSPlugin
from .compiler.dataprep_gdspy import Dataprep

# Typing Imports
from typing import TYPE_CHECKING, Dict, Optional, Sequence, List

if TYPE_CHECKING:
    from BPG.photonic_core import PhotonicTechInfo
    from bag.util.cache import DesignMaster
    from bag.core import RoutingGrid
    from bag.core import BagProject
    from BPG.template import PhotonicTemplateBase


class PhotonicTemplateDB(TemplateDB):
    def __init__(self,
                 lib_defs: str,
                 routing_grid: 'RoutingGrid',
                 lib_name: str,
                 prj: Optional['BagProject'] = None,
                 use_cybagoa: bool = False,
                 gds_lay_file: str = '',
                 gds_filepath: str = '',
                 photonic_tech_info: 'PhotonicTechInfo' = None,
                 **kwargs,
                 ):
        TemplateDB.__init__(self,
                            lib_defs=lib_defs,
                            routing_grid=routing_grid,
                            lib_name=lib_name,
                            prj=prj,
                            use_cybagoa=use_cybagoa,
                            gds_lay_file=gds_lay_file,
                            **kwargs
                            )
        # Keys are LPPs and values are BAG content list format
        self.lsf_post_dataprep_flat_content_list = []

        # Path to output gds and lsf storage
        self.gds_filepath = gds_filepath

        self.photonic_tech_info = photonic_tech_info
        self.dataprep_routine_filepath = photonic_tech_info.dataprep_routine_filepath
        self.dataprep_params_filepath = photonic_tech_info.dataprep_parameters_filepath
        self._export_gds = True
        self.impl_cell = None  # TODO: impl_cell??

    def to_gds_plugin(self,
                      lib_name: str,
                      content_list: List["ContentList"],
                      ) -> None:
        """
        Generates a GDS file from the provided content list using the built-in GDS plugin

        Parameters
        ----------
        lib_name : str
            Name of the library to be created in the GDS
        content_list : List[ContentList]
            The main db containing all of the physical design information
        """
        plugin = GDSPlugin(grid=self.grid,
                           gds_layermap=self._gds_lay_file,
                           gds_filepath=self.gds_filepath,
                           lib_name=lib_name)
        plugin.export_content_list(content_lists=content_list)

    def dataprep(self,
                 flat_content_list: "ContentList",
                 is_lsf: bool = False,
                 ) -> ContentList:
        """
        Initializes the dataprep plugin with the standard tech info and runs the dataprep procedure

        Parameters
        ----------
        flat_content_list : ContentList
            The flattened Contentlist of the master
        is_lsf : bool
            True if running LSF dataprep. False if running standard dataprep.
        Returns
        -------
        post_dataprep_flat_content_list : ContentList
            The ContentList object (no longer layer separated) after running dataprep
        """
        logging.info(f'In PhotonicTemplateDB.dataprep with is_lsf set to {is_lsf}')
        dataprep_object = Dataprep(photonic_tech_info=self.photonic_tech_info,
                                        grid=self.grid,
                                        content_list_flat=flat_content_list,
                                        is_lsf=is_lsf,
                                        impl_cell=self.impl_cell,  # TODO: impl_cell??
                                        )
        start = time.time()
        post_dataprep_flat_content_list = dataprep_object.dataprep()
        end = time.time()
        logging.info(f'All dataprep operations completed in {end - start:.4g} s')
        return post_dataprep_flat_content_list

    def generate_content_list(self,
                              master_list,  # type: Sequence[DesignMaster]
                              name_list=None,  # type: Optional[Sequence[Optional[str]]]
                              lib_name='',  # type: str
                              debug=False,  # type: bool
                              rename_dict=None,  # type: Optional[Dict[str, str]]
                              ) -> List[ContentList]:
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
        content_list : List[ContentList]
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

    def generate_flat_content_list(self,
                                   master_list: Sequence['PhotonicTemplateBase'],
                                   name_list: Optional[Sequence[Optional[str]]] = None,
                                   lib_name: str = '',
                                   rename_dict: Optional[Dict[str, str]] = None,
                                   ) -> List["ContentList"]:
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
        """
        logging.info(f'In PhotonicTemplateDB.instantiate_flat_masters')

        # TODO: Implement support for multiple flat masters. Do we flatten all the objects together into 1 layout?
        #  Probably not... Each master is a separate 'layout' and should each be flattened on its own.
        #  This would require making flat_content_list a list of dicts each corresponding to a different master, etc
        if len(master_list) > 1:
            raise ValueError(f'Support for generation of multiple flat masters is not yet implemented.')

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

        flat_content_lists = []
        start = time.time()
        for master, top_name in zip(master_list, name_list):
            flat_content_lists.append(
                self._flatten_instantiate_master_helper(master)
            )
        end = time.time()
        logging.info(f'Master content flattening took {end-start:.4g}s')

        # TODO: ?? what is going on here
        if not lib_name:
            lib_name = self.lib_name + '_flattened'
        if not lib_name:
            raise ValueError('master library name is not specified.')

        # TODO: ?? what is going on here
        if len(name_list) == 1:
            # If called from generate_flat_gds, name_list is just [self.specs['impl_cell']]
            self.impl_cell = name_list[0]

        return flat_content_lists

    def _flatten_instantiate_master_helper(self,
                                           master: 'PhotonicTemplateBase',  # DesignMaster
                                           hierarchy_name: Optional[str] = None,
                                           ) -> ContentList:
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
        master_content : ContentList
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
            transformed_child_content = child_content.transform_content(
                res=self.grid.resolution,
                loc=child_instance_info['loc'],
                orient=child_instance_info['orient'],
                via_info=via_info,
                unit_mode=False,
            )

            master_content.extend_content_list(transformed_child_content)

        master_content['inst_list'] = []
        end = time.time()

        logging.debug(f'PhotonicTemplateDB._flatten_instantiate_master_helper finished on '
                      f'{hierarchy_name}: \n'
                      f'\t\t\t\t\t\t\t\t\t\tflattening took {end - start:.4g}s.\n'
                      f'\t\t\t\t\t\t\t\t\t\tCurrent memory usage: {memory_usage(-1)} MiB')

        return master_content
