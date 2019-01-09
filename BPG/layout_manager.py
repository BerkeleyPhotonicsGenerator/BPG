import yaml
import importlib
import logging
import time
import json
from pathlib import Path
from collections import UserDict

# BAG imports
from bag.layout import RoutingGrid
from BPG.photonic_core import PhotonicBagProject

# Plugin imports
from .db import PhotonicTemplateDB
from .lumerical.code_generator import LumericalSweepGenerator
from .lumerical.code_generator import LumericalMaterialGenerator
from .gds.core import GDSPlugin
from .lumerical.core import LumericalPlugin

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from BPG.photonic_core import PhotonicBagProject
    from BPG.content_list import ContentList
    from .bpg_custom_types import PhotonicTemplateType

timing_logger = logging.getLogger('timing')


class PhotonicLayoutManager(PhotonicBagProject):
    """
    User-facing class that enables encapsulated dispatch of layout operations such as generating gds, oa, lsf, etc
    """

    def __init__(self,
                 spec_file: str,
                 bag_config_path: str = None,
                 port: int = None,
                 ):
        """
        Parameters
        ----------
        spec_file : str
            The path to the specification file for the layout.
        bag_config_path : str
            path to a bag_config.yaml file to use instead of the path in the env var
        port : int
            port to communicate with cadence
        """
        PhotonicBagProject.__init__(self, bag_config_path=bag_config_path, port=port)
        self.load_paths(spec_file=spec_file)
        self.photonic_tech_info.load_tech_files()

        self.tdb: "PhotonicTemplateDB" = None
        self.impl_lib = None  # Virtuoso Library where generated cells are stored

        # Plugin initialization
        self.gds_plugin: "GDSPlugin" = None
        self.lsf_plugin: "LumericalPlugin" = None
        self.template_plugin: 'PhotonicTemplateDB' = None
        self.init_plugins()  # Initializes all of the built-in plugins

        # Template init
        self.template: "PhotonicTemplateType" = None
        self.cell_name: str = ''

        # Content List init
        self.content_list: List["ContentList"] = None
        self.content_list_flat: "ContentList" = None
        self.content_list_post_dataprep: "ContentList" = None
        self.content_list_post_lsf_dataprep: "ContentList" = None
        self.content_list_lumerical_tb: List["ContentList"] = []

        self.content_list_types = ['content_list', 'content_list_flat', 'content_list_post_dataprep',
                                   'content_list_post_lsf_dataprep', 'content_list_lumerical_tb']

    def init_plugins(self) -> None:
        """
        Creates all built-in plugins based on the provided configuration and tech-info
        """
        lib_name = self.specs['impl_lib']
        self.impl_lib = lib_name

        # Extract routing grid information from spec file if provided. If not, default to dummy values
        if 'routing_grid' in self.specs:
            grid_specs = self.specs['routing_grid']
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

        self.gds_plugin = GDSPlugin(grid=routing_grid,
                                    gds_layermap=self.photonic_tech_info.layermap_path,
                                    gds_filepath=self.gds_path,
                                    lib_name=self.impl_lib)

        self.lsf_plugin = LumericalPlugin(lsf_export_config=self.photonic_tech_info.lsf_export_path,
                                          lsf_filepath=self.lsf_path)

    def generate_content(self,
                         layout_params: dict = None,
                         cell_name: str = None,
                         ) -> List['ContentList']:
        """
        Generates a content list.
        If layout params and cell name are passed, use these parameters.
        If not provided, get these variables from the spec file

        Parameters
        ----------
        layout_params : dict
            Optional dictionary of parameters to be sent to the layout generator class.
        cell_name : str
            Optional name of the cell to be created from the layout generator.

        Returns
        -------
        content_list : ContentList
            A db of all generated shapes
        """
        logging.info(f'\n\n{"Generating content list":-^80}')
        if layout_params is None:
            layout_params = self.specs['layout_params']
        if cell_name is None:
            cell_name = self.specs['impl_cell']

        if isinstance(layout_params, list):
            raise ValueError('Content generation from multiple masters is not supported in BPG.')

        # Import the class listed in the spec file
        cls_package = self.specs['layout_package']
        cls_name = self.specs['layout_class']
        lay_module = importlib.import_module(cls_package)
        temp_cls = getattr(lay_module, cls_name)

        start_time = time.time()
        # Generate the template
        self.template = self.template_plugin.new_template(params=layout_params,
                                                          temp_cls=temp_cls,
                                                          debug=False)
        self.cell_name = cell_name
        end_time_newtemp = time.time()

        # Generate the content list
        self.content_list = self.template_plugin.generate_content_list(master_list=[self.template],
                                                                       name_list=[cell_name])
        end_time_contentgen = time.time()

        # Save the content
        self.save_content_list('content_list')
        end_time_save = time.time()

        timing_logger.info(f'{end_time_save - start_time:<15.6g} | Content list creation')
        timing_logger.info(f'  {end_time_newtemp - start_time:<13.6g} | - New template generation')
        timing_logger.info(f'  {end_time_contentgen - end_time_newtemp:<13.6g} | - Content list generation')
        timing_logger.info(f'  {end_time_save - end_time_contentgen:<13.6g} | - Content list saving')

        return self.content_list

    def generate_gds(self) -> None:
        """
        Exports the content list to gds format
        """
        logging.info(f'\n\n{"Generating .gds":-^80}')
        if not self.content_list:
            raise ValueError('Must call PhotonicLayoutManager.generate_content before calling generate_gds')

        start = time.time()
        self.gds_plugin.export_content_list(content_lists=self.content_list)
        end = time.time()
        timing_logger.info(f'{end - start:<15.6g} | GDS export, not flat')

    def generate_flat_content(self,
                              ) -> 'ContentList':
        """
        Generates a flattened content list from the template passed to generate_content.

        Parameters
        ----------

        Returns
        -------
        content_list : ContentList
            A db of all generated shapes
        """
        logging.info(f'\n\n{"Generating flat content list":-^80}')

        if not self.template:
            raise ValueError('Must call PhotonicLayoutManager.generate_content before calling generate_flat_content')

        start_time = time.time()
        self.content_list_flat = self.template_plugin.generate_flat_content_list(master_list=[self.template],
                                                                                 name_list=[self.cell_name],
                                                                                 lib_name='_flat',
                                                                                 rename_dict=None,
                                                                                 )[0]
        end_time_contentgen = time.time()

        # Save the content
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
        self.gds_plugin.export_content_list(content_lists=[self.content_list_flat], name_append='_flat')  # TODO:name
        end = time.time()
        timing_logger.info(f'{end - start:<15.6g} | GDS export, flat')

    def generate_lsf(self, create_materials=True):
        """ Converts generated layout to lsf format for lumerical import """
        logging.info(f'\n\n{"Generating the design .lsf file":-^80}')

        if create_materials is True:
            self.create_materials_file()

        if not self.content_list_flat:
            raise ValueError('Must call PhotonicLayoutManager.generate_flat_content before calling generate_lsf')

        if isinstance(self.content_list_flat, list):
            raise ValueError('LSF / dataprep on content list created from multiple masters is not supported in BPG.')

        self.content_list_post_lsf_dataprep = self.template_plugin.dataprep(
            flat_content_list=self.content_list_flat,
            is_lsf=True
        )
        # TODO: Fix naming here as well
        self.lsf_plugin.export_content_list(content_lists=[self.content_list_post_lsf_dataprep])

    def generate_tb(self, debug=False):
        """ Generates the lumerical testbench lsf """
        logging.info(f'\n\n{"Generating the tb .lsf file":-^80}')

        # Grab the parameters to be passed to the TB
        tb_params = self.specs['tb_params']
        if tb_params is None:
            tb_params = {}

        if not isinstance(self.specs['layout_params'], list):
            self.specs['layout_params'] = [self.specs['layout_params']]

        # Construct the parameter list
        layout_params_list = []
        cell_name_list = []
        for count, params in enumerate(self.specs['layout_params']):
            temp_params = dict()
            temp_params['layout_package'] = self.specs['layout_package']
            temp_params['layout_class'] = self.specs['layout_class']
            temp_params['layout_params'] = params
            temp_params['tb_params'] = tb_params
            layout_params_list.append(temp_params)
            cell_name_list.append(self.specs['lsf_filename'] + '_' + str(count))

        # Try importing the TB package and class
        cls_package = self.specs['tb_package']
        cls_name = self.specs['tb_class']
        lay_module = importlib.import_module(cls_package)
        temp_cls = getattr(lay_module, cls_name)

        # Create TB lsf file
        temp_list = []
        for lay_params in layout_params_list:
            template = self.template_plugin.new_template(params=lay_params, temp_cls=temp_cls, debug=debug)
            temp_list.append(template)

        self.content_list_lumerical_tb = self.template_plugin.generate_flat_content_list(
            master_list=temp_list,
            name_list=cell_name_list,
            lib_name='_tb',
            rename_dict=None,
        )

        tb_content_post_dataprep = []
        for content_list in self.content_list_lumerical_tb:
            tb_content_post_dataprep.append(self.template_plugin.dataprep(flat_content_list=content_list, is_lsf=True))

        # Export the actual data to LSF
        self.lsf_plugin.export_content_list(tb_content_post_dataprep)       # TODO : fix naming here as well

        # Create the sweep LSF file
        filepath = self.lsf_plugin.lsf_filepath + '_sweep'
        lsfwriter = LumericalSweepGenerator(filepath)
        for script in cell_name_list:
            lsfwriter.add_sweep_point(script_name=script)
        lsfwriter.export_to_lsf()

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
            is_lsf=False
        )
        end = time.time()
        timing_logger.info(f'{end - start:<15.6g} | Dataprep')

    def generate_dataprep_gds(self) -> None:
        """
        Exports the dataprep content to GDS format
        """
        logging.info(f'\n\n{"Generating dataprep .gds":-^80}')

        if not self.content_list_post_dataprep:
            raise ValueError('Must call PhotonicLayoutManager.dataprep before calling generate_dataprep_gds')

        start = time.time()
        # TODO: name
        self.gds_plugin.export_content_list(content_lists=[self.content_list_post_dataprep], name_append='_dataprep')
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

            print(f'json str:  {test}')

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
        if content_list not in self.content_list_types:
            raise ValueError(f'content_list parameter must be one of {self.content_list_types}.')

        # If filepath not passed, get the default content location for this PLM
        if not filepath:
            filepath = Path(self.content_dir) / content_list

        with open(filepath, 'r') as f:
            content = json.load(f, object_hook=_json_convert_from_dict)

        self.__dict__[content_list] = content
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
    print(f'_json_convert_to_dict       obj={obj}')
    print(f'obj.__dict__=    {obj.__dict__}')
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

    print(f'obj_dict=    {obj_dict}')
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
    print(obj_dict)
    if "__class__" in obj_dict and "__module__" in obj_dict:
        class_name = obj_dict.pop("__class__")

        module_name = obj_dict.pop("__module__")

        module = importlib.import_module(module_name)
        obj_class = getattr(module, class_name)

        obj = obj_class(**obj_dict)
    else:
        obj = obj_dict

    return obj
