import yaml
import importlib
import logging

# BAG imports
from bag.layout import RoutingGrid
from BPG.photonic_core import PhotonicBagProject

# Plugin imports
from .db import PhotonicTemplateDB
from .lumerical.code_generator import LumericalSweepGenerator
from .lumerical.code_generator import LumericalMaterialGenerator
from .gds.core import GDSPlugin
from .lumerical.core import LumericalPlugin

from .logger import setup_logger

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from BPG.photonic_core import PhotonicBagProject
    from BPG.content_list import ContentList


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
        self.gds_plugin = None
        self.lsf_plugin = None
        self.template_plugin: 'PhotonicTemplateDB' = None
        self.init_plugins()  # Initializes all of the built-in plugins

        # Content List init
        self.content_list: "ContentList" = None
        self.content_list_flat: "ContentList" = None
        self.content_list_post_dataprep: "ContentList" = None
        self.content_list_post_lsf_dataprep: "ContentList" = None
        self.content_list_lumerical_tb: List["ContentList"] = []

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
                                                  gds_filepath=self.gds_path,
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
                         ) -> 'ContentList':
        """
        Generates a content list from the specified design class, layout params, and cell_name. If not provided,
        get these variables from the spec file

        Parameters
        ----------
        layout_params : dict
            dictionary of parameters to be sent to the layout generator class
        cell_name : str
            name of the cell to be created from the layout generator

        Returns
        -------
        content_list : ContentList
            A db of all generated shapes
        """
        logging.info('--- Generating content list ---')
        if layout_params is None:
            layout_params = self.specs['layout_params']
        if cell_name is None:
            cell_name = self.specs['impl_cell']

        if isinstance(layout_params, list):
            raise ValueError('Dataprep on content list created from multiple masters is not yet supported')

        # Import the class listed in the spec file
        cls_package = self.specs['layout_package']
        cls_name = self.specs['layout_class']
        lay_module = importlib.import_module(cls_package)
        temp_cls = getattr(lay_module, cls_name)

        # Generate the content list
        template = self.template_plugin.new_template(params=layout_params,
                                                     temp_cls=temp_cls,
                                                     debug=False)
        self.content_list = self.template_plugin.generate_content_list(master_list=[template],
                                                                       name_list=[cell_name])
        return self.content_list

    def generate_gds(self, layout_params=None, cell_name=None) -> None:
        """
        Generates content for the specified layout generator and exports it to GDS format

        Parameters
        ----------
        layout_params : dict
            Optional dict corresponding to layout parameters passed to the generator class
        cell_name : str
            Optional string corresponding to the name given to the generated layout
        """
        self.generate_content(layout_params=layout_params, cell_name=cell_name)
        logging.info('--- Generating .gds ---')
        self.gds_plugin.export_content_list(content_list=self.content_list)

    def generate_flat_content(self,
                              layout_params: dict = None,
                              cell_name: str = None,
                              ) -> 'ContentList':
        """
        Generates a layout with the layout package/class in the spec file with the parameters set by
        layout_params and names it cell_name.

        Parameters
        ----------
        layout_params : dict
            Optional dict corresponding to layout parameters passed to the generator class
        cell_name : str
            Optional string corresponding to the name given to the layout
        """
        logging.info('---Generating flat .gds file---')
        # TODO: Implement the gen_full/gen_design/gen_physical
        # If no list is provided, extract layout params from the provided spec file
        if layout_params is None:
            layout_params = self.specs['layout_params']
        if cell_name is None:
            cell_name = self.specs['impl_cell']

        if isinstance(layout_params, list):
            raise ValueError('generating flat content list created from multiple masters is not yet supported')

        cls_package = self.specs['layout_package']
        cls_name = self.specs['layout_class']

        lay_module = importlib.import_module(cls_package)
        temp_cls = getattr(lay_module, cls_name)

        template = self.template_plugin.new_template(params=layout_params, temp_cls=temp_cls)

        self.content_list_flat = self.template_plugin.generate_flat_content_list(master_list=[template],
                                                                                 name_list=[cell_name],
                                                                                 lib_name='_flat',
                                                                                 rename_dict=None,
                                                                                 )
        return self.content_list_flat

    def generate_flat_gds(self,
                          layout_params: dict = None,
                          cell_name: str = None
                          ) -> None:
        """
        Generates content for the specified layout generator and exports it to GDS format

        Parameters
        ----------
        layout_params : dict
            Optional dict corresponding to layout parameters passed to the generator class
        cell_name : str
            Optional string corresponding to the name given to the generated layout
        """
        self.generate_flat_content(layout_params=layout_params, cell_name=cell_name)
        logging.info('--- Generating .gds ---')
        self.gds_plugin.export_content_list(content_list=self.content_list_flat)

    def generate_lsf(self, create_materials=True):
        """ Converts generated layout to lsf format for lumerical import """
        logging.info('---Generating the design .lsf file---')
        if create_materials is True:
            self.create_materials_file()

        if not self.content_list_flat:
            raise ValueError('Please generate a flat GDS before exporting to Lumerical')

        if len(self.content_list_flat) > 1:
            raise ValueError('Dataprep on content list created from multiple masters is not yet supported')

        self.content_list_post_lsf_dataprep = self.template_plugin.dataprep(flat_content_list=self.content_list_flat,
                                                                            is_lsf=True)
        self.lsf_plugin.export_content_list(content_list=self.content_list_post_lsf_dataprep)

    def generate_tb(self, debug=False):
        """ Generates the lumerical testbench lsf """
        logging.info('---Generating the tb .lsf file---')
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
        self.lsf_plugin.export_content_list(tb_content_post_dataprep)

        # Create the sweep LSF file
        filepath = self.template_plugin.lsf_filepath + '_sweep'
        lsfwriter = LumericalSweepGenerator(filepath)
        for script in cell_name_list:
            lsfwriter.add_sweep_point(script_name=script)
        lsfwriter.export_to_lsf()

    def dataprep(self):
        logging.info('---Running dataprep---')
        if not self.content_list_flat:
            raise ValueError('Please generate a flat GDS before running dataprep')
        self.content_list_post_dataprep = self.template_plugin.dataprep(
            flat_content_list=self.content_list_flat,
            is_lsf=False
        )

    # TODO: Define export dataprep GDS

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
