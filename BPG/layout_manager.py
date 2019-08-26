import yaml
import importlib
import logging
import time
import json
from pathlib import Path
from collections import UserDict
import os


# BAG imports
from bag.layout import RoutingGrid
from bag.util.cache import _get_unique_name
import BPG
from BPG.photonic_core import PhotonicBagProject

# Plugin imports
from .db import PhotonicTemplateDB
from .lumerical.code_generator import LumericalMaterialGenerator
from .gds.core import GDSPlugin
from .lumerical.core import LumericalPlugin

from typing import TYPE_CHECKING, List, Optional, Dict, Any

try:
    from DataprepPlugin.Calibre.calibre import CalibreDataprep
except ImportError:
    CalibreDataprep = None

try:
    from PLVS.PLVS import PLVS
except ImportError:
    PLVS = None

if TYPE_CHECKING:
    from BPG.photonic_core import PhotonicBagProject
    from BPG.content_list import ContentList
    from .bpg_custom_types import PhotonicTemplateType
    from gdspy import GdsLibrary

timing_logger = logging.getLogger('timing')


class PhotonicLayoutManager(PhotonicBagProject):
    """
    User-facing class that enables encapsulated dispatch of layout operations such as generating gds, oa, lsf, etc
    """

    def __init__(self,
                 spec_file: str,
                 bag_config_path: Optional[str] = None,
                 port: Optional[int] = None,
                 **kwargs: Dict[str, Any],
                 ) -> None:
        """
        Parameters
        ----------
        spec_file : str
            The path to the specification file for the layout.
        bag_config_path : str
            path to a bag_config.yaml file to use instead of the path in the env var
        port : int
            port to communicate with cadence
        kwargs : Dict[Any]
            keyword arguments to update any key from the spec file.
            Values passed here will overwrite those in the spec_file upon initialization of PhotonicLayoutManager
        """
        PhotonicBagProject.__init__(self, bag_config_path=bag_config_path, port=port)

        self.load_spec_file_paths(spec_file=spec_file, **kwargs)

        self.tdb: "PhotonicTemplateDB" = None
        self.impl_lib = None  # Virtuoso Library where generated cells are stored

        # Plugin initialization
        self.gds_plugin: "GDSPlugin" = None
        self.lsf_plugin: "LumericalPlugin" = None
        self.template_plugin: 'PhotonicTemplateDB' = None
        self.calibre_dataprep_plugin: 'CalibreDataprep' = None
        self.init_plugins()  # Initializes all of the built-in plugins

        # Template init
        self.template_list: List["PhotonicTemplateType"] = []
        self.cell_name_list: List[str] = []

        # Content List init
        self.content_list: List["ContentList"] = None
        self.content_list_flat: List["ContentList"] = None
        self.content_list_post_dataprep: List["ContentList"] = None
        self.content_list_post_lsf_dataprep: List["ContentList"] = None
        self.content_list_lumerical_tb: List["ContentList"] = []

        self.content_list_types = ['content_list', 'content_list_flat', 'content_list_post_dataprep',
                                   'content_list_post_lsf_dataprep', 'content_list_lumerical_tb']

    def init_plugins(self) -> None:
        """
        Creates all built-in plugins based on the provided configuration and tech-info
        """
        lib_name = BPG.run_settings['impl_lib']
        self.impl_lib = lib_name

        # Extract routing grid information from spec file if provided. If not, default to dummy values
        if 'routing_grid' in BPG.run_settings:
            grid_specs = BPG.run_settings['routing_grid']
        else:
            grid_specs = self.photonic_tech_info.photonic_tech_params['default_routing_grid']

        layers = grid_specs['layers']
        spaces = grid_specs['spaces']
        widths = grid_specs['widths']
        bot_dir = grid_specs['bot_dir']
        routing_grid = RoutingGrid(self.tech_info, layers, spaces, widths, bot_dir)

        self.template_plugin = PhotonicTemplateDB('template_libs.def',
                                                  routing_grid=routing_grid,
                                                  lib_name=lib_name,
                                                  use_cybagoa=True,
                                                  gds_lay_file=self.photonic_tech_info.layermap_path,
                                                  photonic_tech_info=self.photonic_tech_info)
        self.template_plugin._prj = self
        print(f'GDS layermap is: {self.photonic_tech_info.layermap_path}')
        self.gds_plugin = GDSPlugin(grid=routing_grid,
                                    gds_layermap=self.photonic_tech_info.layermap_path,
                                    gds_filepath=self.gds_path,
                                    lib_name=self.impl_lib)

        self.lsf_plugin = LumericalPlugin(lsf_export_config=self.photonic_tech_info.lsf_export_path,
                                          )
        if CalibreDataprep:
            self.calibre_dataprep_plugin = CalibreDataprep(
                calibre_run_dir=str(Path(self.data_dir) / 'DataprepRunDir'),
                photonic_tech_info=self.photonic_tech_info,
                grid=self.template_plugin.grid
            )
        else:
            self.calibre_dataprep_plugin = None

    def generate_template(self,
                          temp_cls: "PhotonicTemplateType" = None,
                          params: dict = None,
                          cell_name: str = None
                          ) -> None:
        """
        Adds a single generator template to the queue for future content creation. If no arguments are provided,
        parameters are extracted from the provided spec file

        Parameters
        ----------
        temp_cls : PhotonicTemplateType
            A generator class to run with the provided parameters
        params : dict
            A dictionary of parameters to pass to the generator class
        cell_name : str
            Name of the cell to be associated with the template
        """
        logging.info(f'\n\n{"Generating template":-^80}')
        if params is None:
            params = BPG.run_settings['layout_params']
        if temp_cls is None:
            cls_package = BPG.run_settings['layout_package']
            cls_name = BPG.run_settings['layout_class']
            lay_module = importlib.import_module(cls_package)
            temp_cls = getattr(lay_module, cls_name)
        if cell_name is None:
            cell_name = BPG.run_settings['impl_cell']

        start_time = time.time()
        self.template_list.append(self.template_plugin.new_template(params=params,
                                                                    temp_cls=temp_cls,
                                                                    debug=False))
        if cell_name in self.cell_name_list:
            cell_name = _get_unique_name(cell_name, self.cell_name_list)
        self.cell_name_list.append(cell_name)
        end_time = time.time()

        timing_logger.info(f'{end_time - start_time:<15.6g} | {temp_cls.__name__} Template generation')

    def generate_content(self,
                         save_content: bool = True,
                         ) -> List['ContentList']:
        """
        Generates a set of content lists from all of the templates in the queue.

        Returns
        -------
        content_list : List[ContentList]
            A list of databases that contain all generated shapes
        """
        if not self.template_list:
            self.generate_template()

        logging.info(f'\n\n{"Generating content list":-^80}')

        start_time = time.time()
        self.content_list = self.template_plugin.generate_content_list(master_list=self.template_list,
                                                                       name_list=self.cell_name_list)
        end_time_contentgen = time.time()

        # Save the content
        if save_content:
            self.save_content_list('content_list')
        end_time_save = time.time()

        timing_logger.info(f'{end_time_save - start_time:<15.6g} | Content list creation')
        timing_logger.info(f'  {end_time_contentgen - start_time:<13.6g} | - Content list generation')
        if save_content:
            timing_logger.info(f'  {end_time_save - end_time_contentgen:<13.6g} | - Content list saving')

        return self.content_list

    def generate_gds(self,
                     max_points_per_polygon: Optional[int] = None,
                     ) -> "GdsLibrary":
        """
        Exports the content list to gds format
        """
        logging.info(f'\n\n{"Generating .gds":-^80}')
        if not self.content_list:
            raise ValueError('Must call PhotonicLayoutManager.generate_content before calling generate_gds')

        start = time.time()
        gdspy_lib = self.gds_plugin.export_content_list(content_lists=self.content_list,
                                                        max_points_per_polygon=max_points_per_polygon)
        end = time.time()
        timing_logger.info(f'{end - start:<15.6g} | GDS export, not flat')

        return gdspy_lib

    def generate_flat_content(self,
                              save_content: bool = True,
                              ) -> List["ContentList"]:
        """
        Generates a flattened content list from generated templates.

        Returns
        -------
        content_list : ContentList
            A db of all generated shapes
        """
        logging.info(f'\n\n{"Generating flat content list":-^80}')

        if not self.template_list:
            raise ValueError('Must call PhotonicLayoutManager.generate_template before calling generate_flat_content')

        start_time = time.time()
        self.content_list_flat = self.template_plugin.generate_flat_content_list(master_list=self.template_list,
                                                                                 name_list=self.cell_name_list,
                                                                                 rename_dict=None,
                                                                                 )
        end_time_contentgen = time.time()

        # Save the content
        if save_content:
            self.save_content_list('content_list_flat')
        end_time_save = time.time()

        timing_logger.info(f'{end_time_save - start_time:<15.6g} | Generate flat content')
        timing_logger.info(f'  {end_time_contentgen - start_time:<13.6g} | Flattening and flat content list creation')
        timing_logger.info(f'  {end_time_save - end_time_contentgen:<13.6g} | - Content list saving')

        return self.content_list_flat

    def generate_flat_gds(self) -> None:
        """
        Exports flattened content list of design to gds format
        """
        logging.info(f'\n\n{"Generating flat .gds":-^80}')

        if not self.content_list_flat:
            raise ValueError('Must call PhotonicLayoutManager.generate_flat_content before calling generate_flat_gds')

        start = time.time()
        self.gds_plugin.export_content_list(content_lists=self.content_list_flat, name_append='_flat')  # TODO:name
        end = time.time()
        timing_logger.info(f'{end - start:<15.6g} | GDS export, flat')

    def generate_lsf(self,
                     create_materials=True,
                     export_dir: Optional[Path] = None
                     ):
        """ Converts generated layout to lsf format for lumerical import """
        logging.info(f'\n\n{"Generating the design .lsf file":-^80}')

        if create_materials is True:
            self.create_materials_file()

        if not self.content_list_flat:
            raise ValueError('Must call PhotonicLayoutManager.generate_flat_content before calling generate_lsf')

        # if isinstance(self.content_list_flat, list):
        #     raise ValueError('LSF / dataprep on content list created from multiple masters is not supported in BPG.')

        self.content_list_post_lsf_dataprep = self.template_plugin.dataprep(
            flat_content_list=self.content_list_flat,
            name_list=self.cell_name_list,
            is_lsf=True
        )
        # TODO: Fix naming here as well
        self.lsf_plugin.export_content_list(content_lists=self.content_list_post_lsf_dataprep,
                                            name_list=self.cell_name_list,
                                            export_dir=export_dir if export_dir else self.scripts_dir
                                            )

    def generate_lsf_calibre(self,
                             create_materials: bool = True,
                             file_in: Optional[str] = None,
                             file_out: Optional[str] = None,
                             export_dir: Optional[Path] = None,
                             ):
        """ Converts generated layout to lsf format for lumerical import """
        logging.info(f'\n\n{"Generating the design .lsf file via Calibre":-^80}')

        if create_materials is True:
            self.create_materials_file()

        if file_in:
            file_in = os.path.abspath(file_in)
            if not Path(file_in).is_file():
                raise ValueError(f'Input file cannot be found: {file_in}')
        else:
            file_in = self.gds_path + '.gds'

        if file_out:
            file_out = os.path.abspath(file_out)
        else:
            file_out = self.gds_path + '_lsf_dataprep.gds'

        self.calibre_dataprep_plugin.run_dataprep(file_in=file_in, file_out=file_out,
                                                  is_lumerical_dataprep=True)

        self.content_list_post_lsf_dataprep = self.gds_plugin.import_content_list(gds_filepath=file_out)

        self.content_list_post_lsf_dataprep.extend_content_list(
            self.content_list[-1].optical_design_content()
        )
        self.content_list_post_lsf_dataprep = [self.content_list_post_lsf_dataprep]

        # TODO: Fix naming here as well
        self.lsf_plugin.export_content_list(content_lists=self.content_list_post_lsf_dataprep,
                                            name_list=self.cell_name_list,
                                            export_dir=export_dir if export_dir else self.scripts_dir
                                            )

    def dataprep(self):
        """
        Performs dataprep on the design
        """
        logging.info(f'\n\n{"Running dataprep":-^80}')

        if not self.content_list_flat:
            raise ValueError('Must call PhotonicLayoutManager.generate_flat_content before calling dataprep')

        start = time.time()
        self.content_list_post_dataprep = self.template_plugin.dataprep(
            flat_content_list=self.content_list_flat,
            name_list=self.cell_name_list,
            is_lsf=False
        )
        end = time.time()
        timing_logger.info(f'{end - start:<15.6g} | Dataprep')

    def dataprep_calibre(self,
                         file_in=None,
                         file_out=None,
                         ):
        """
        Performs dataprep on the design
        """
        if not self.calibre_dataprep_plugin:
            raise ValueError(f'Calibre Dataprep plugin is not initialized. '
                             f'Ensure the DataprepCalibre plugin is installed.')

        logging.info(f'\n\n{"Running dataprep calibre":-^80}')

        start = time.time()

        if file_in:
            file_in = os.path.abspath(file_in)
            if not Path(file_in).is_file():
                raise ValueError(f'Input file cannot be found: {file_in}')
        else:
            file_in = self.gds_path + '.gds'

        if file_out:
            file_out = os.path.abspath(file_out)
        else:
            file_out = self.gds_path + '_dataprep_calibre.gds'

        self.calibre_dataprep_plugin.run_dataprep(file_in=file_in, file_out=file_out)

        end = time.time()
        timing_logger.info(f'{end - start:<15.6g} | Dataprep_calibre')

    def generate_dataprep_gds(self) -> None:
        """
        Exports the dataprep content to GDS format
        """
        logging.info(f'\n\n{"Generating dataprep .gds":-^80}')

        if not self.content_list_post_dataprep:
            raise ValueError('Must call PhotonicLayoutManager.dataprep before calling generate_dataprep_gds')

        start = time.time()
        # TODO: name
        self.gds_plugin.export_content_list(content_lists=self.content_list_post_dataprep, name_append='_dataprep')
        end = time.time()
        timing_logger.info(f'{end - start:<15.6g} | GDS export, dataprep')

    def create_materials_file(self):
        """
        Takes the custom materials stated in the lumerical_map and generates a Lumerical lsf file that defines the
        materials for use in simulation.
        """
        # 1) load the lumerical map file

        inpath = self.photonic_tech_info.lsf_export_path
        outpath = self.scripts_dir / 'materials.lsf'
        with open(inpath, 'r') as f:
            lumerical_map = yaml.load(f)

        # 2) Extract the custom materials under the materials key
        mat_map = lumerical_map['materials']

        # 3) Create the LumericalMaterialGenerator class and load the data in
        lmg = LumericalMaterialGenerator(str(outpath))
        lmg.import_material_file(mat_map)

        # 4) Export to LSF
        lmg.export_to_lsf()

    def generate_schematic(self) -> None:
        """
        Generate the schematic.

        Returns
        -------

        """
        logging.info(f'\n\n{"Schematic generation":-^80}')

        if not self.template_list:
            raise RuntimeError(f'Must call PhotonicLayoutManager.generate_content before calling generate_schematic')

        # TODO: Need to implement support for a list of templates
        if len(self.template_list) > 1:
            raise ValueError(f'schematic generation currently does not support multiple templates')
        else:
            template = self.template_list[0]
            impl_cell = self.cell_name_list[0]

        start_time = time.time()

        # Get name of schematic template's library and cell
        sch_lib = BPG.run_settings['sch_lib']
        sch_cell = BPG.run_settings['sch_cell']

        dsn = self.create_design_module(lib_name=sch_lib, cell_name=sch_cell)
        end_create_design_module = time.time()

        dsn.design(**template.sch_params)
        end_design = time.time()

        dsn.implement_design(lib_name=self.impl_lib, top_cell_name=impl_cell)
        end_implement = time.time()

        timing_logger.info(f'{end_implement - start_time:<15.6g} | Schematic Generation')
        timing_logger.info(f'  {end_create_design_module - start_time:<13.6g} | - Creating schematic design module')
        timing_logger.info(f'  {end_design - end_create_design_module:<13.6g} | - Designing schematic')
        timing_logger.info(f'  {end_implement - end_design:<13.6g} | - Instantiating schematic')

    def run_photonic_lvs(self,
                         gds_layout_path=None,
                         plvs_runset_template=None,
                         ):

        if not PLVS:
            raise ValueError(f'PLVS plugin is not initialized. '
                             f'Ensure the PLVS plugin is installed.')

        logging.info(f'\n\n{"Photonic LVS":-^80}')
        start_time = time.time()

        if not gds_layout_path:
            gds_layout_path = self.gds_path + '_dataprep_calibre.gds'

        if not plvs_runset_template:
            plvs_runset_template = self.photonic_tech_info.plvs_runset_template

        if not plvs_runset_template:
            raise ValueError(f'plvs_runset_template not specified in function call, '
                             f'and no default provided in the photonic tech config yaml')

        plvs = PLVS(self, gds_layout_path, plvs_runset_template)
        ret_codes, log_files = plvs.run_plvs()

        end_time = time.time()
        timing_logger.info(f'{end_time - start_time:<13.6g} | Photonic LVS')

        return ret_codes, log_files

    def save_content_list(self,
                          content_list: str,
                          filepath: str = None,
                          ):
        """
        Saves the provided content list to the passed filepath, or to the PLM default filepath.

        Parameters
        ----------
        content_list : str
            Which content list to save
        filepath : Optional[str]
            Filepath (directory and filename) (relative to where bpg was started) where to store the file.
            If not specified, defaults to the directory provided in the current PhotonicLayoutManager instance.
        Returns
        -------

        """
        logging.info(f'\n\n{"Save content list":-^80}')
        start = time.time()

        if content_list not in self.content_list_types:
            raise ValueError(f'content_list parameter must be one of {self.content_list_types}.')

        # If filepath not passed, use the default one
        if not filepath:
            filepath = self.content_dir / content_list

        with open(filepath, 'w') as f:
            test = json.dumps(self.__dict__[content_list],
                              # f,
                              indent=4,
                              default=_json_convert_to_dict,
                              )
            f.write(test)

        end = time.time()
        logging.info(f'Saving content list: {content_list}  : {end-start:0.6g}s')

    def load_content_list(self,
                          content_list: str,
                          filepath: str = None,
                          ):
        """
        Loads the specified content list from the passed filepath, or the PLM default filepath.

        Parameters
        ----------
        content_list : str
            Which content list to load
        filepath : Optional[str]
            Filepath (directory and filename) (relative to where bpg was started) to which content list file to load.
            If not specified, defaults to the directory provided in the current PhotonicLayoutManager instance.
        Returns
        -------

        """
        logging.info(f'\n\n{"Load content list":-^80}')
        start = time.time()

        if content_list not in self.content_list_types:
            raise ValueError(f'content_list parameter must be one of {self.content_list_types}.')

        # If filepath not passed, get the default content location for this PLM
        if not filepath:
            filepath = Path(self.content_dir) / content_list

        with open(filepath, 'r') as f:
            content = json.load(f, object_hook=_json_convert_from_dict)

        self.__dict__[content_list] = content

        end = time.time()
        logging.info(f'Loading content list: {content_list}  : {end - start:0.6g}s')

        return content


def _json_convert_to_dict(obj: object) -> dict:
    """
    Takes in a custom object and returns a dictionary representation of the object.
    The dict representation includes meta data such as the object's module and class names.

    Parameters
    ----------
    obj : object
        The object to convert to a dict

    Returns
    -------
    obj_dict : dict
        The dict form of the object
    """
    # Initialize the object dictionary with its class and module
    obj_dict = dict(
        __class__=obj.__class__.__name__,
        __module__=obj.__module__,
    )

    # Update object dictionary with the obj's properties
    if isinstance(obj, UserDict):
        obj_dict.update(obj.data)
    else:
        obj_dict.update(obj.__dict__)

    return obj_dict


def _json_convert_from_dict(obj_dict: dict) -> object:
    """
    Takes in a dict and returns an object associated with the dict.
    The function uses the "__module__" and "__class__" metadata in the dictionary to know which object to create.

    Parameters
    ----------
    obj_dict : dict
        The object dictionary to convert to an object

    Returns
    -------
    obj : object
        The object
    """
    if "__class__" in obj_dict and "__module__" in obj_dict:
        class_name = obj_dict.pop("__class__")

        module_name = obj_dict.pop("__module__")

        module = importlib.import_module(module_name)
        obj_class = getattr(module, class_name)

        obj = obj_class(**obj_dict)
    else:
        obj = obj_dict

    return obj
