import BPG
import yaml
import importlib
import os

from pathlib import Path
from bag.layout import RoutingGrid
from bag.simulation.core import DesignManager
from .photonic_template import PhotonicTemplateDB
from .lumerical_generator import LumericalSweepGenerator
from .lumerical_materials import LumericalMaterialGenerator


class PhotonicLayoutManager(DesignManager):
    """
    Class that manages the creation of Photonic Layouts and Lumerical LSF files
    """
    def __init__(self, bprj, spec_file):
        DesignManager.__init__(self, bprj, spec_file)

        """
        [ Relevant Inherited Variables ]
        self.prj: contains the BagProject instance
        self.specs: contains the specs passed in spec_file
        """

        self.tdb = None  # PhotonicTemplateDB instance for layout creation
        self.impl_lib = None  # Virtuoso Library where generated cells are stored
        self.cell_name_list = None  # list of names for each created cell
        self.layout_params_list = None  # list of dicts containing layout design parameters

        # Setup relevant output files and directories
        if 'project_dir' in self.specs:
            self.project_dir = Path(self.specs['project_dir']).expanduser()
        else:
            default_path = Path(self.prj.bag_config['database']['default_lib_path'])
            self.project_dir = default_path / self.specs['project_name']
        self.scripts_dir = self.project_dir / 'scripts'
        self.data_dir = self.project_dir / 'data'

        # Make the directories if they do not exists
        self.project_dir.mkdir(exist_ok=True, parents=True)
        self.scripts_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)

        # Setup the abstract tech layermap
        if 'layermap' in self.specs:
            bag_work_dir = Path(os.environ['BAG_WORK_DIR'])
            self.layermap_path = bag_work_dir / self.specs['layermap']
        else:
            self.layermap_path = self.prj.layermap_path

        # Setup the dataprep procedure
        if 'dataprep' in self.specs:
            bag_work_dir = Path(os.environ['BAG_WORK_DIR'])
            self.dataprep_path = bag_work_dir / self.specs['dataprep']
        else:
            self.dataprep_path = self.prj.dataprep_path

        # Setup the lumerical export map
        if 'lsf_export_map' in self.specs:
            bag_work_dir = Path(os.environ['BAG_WORK_DIR'])
            self.lsf_export_path = bag_work_dir / self.specs['lsf_export_map']
        else:
            self.lsf_export_path = self.prj.lsf_export_path

        # Set the paths of the output files
        self.lsf_path = str(self.scripts_dir / self.specs['lsf_filename'])
        self.gds_path = str(self.data_dir / self.specs['gds_filename'])

        # Make the PhotonicTemplateDB
        self.make_tdb()

    def make_tdb(self) -> None:
        """
        Makes a new PhotonicTemplateDB instance assuming all contained layouts are generated independently of the grid
        """
        lib_name = self.specs['impl_lib']
        # Input dummy values for these parameters, we wont be using the grid in BPG
        # TODO: Allow layer properties to be extracted from the spec file
        layers = [3, 4, 5]
        spaces = [0.1, 0.1, 0.2]
        widths = [0.1, 0.1, 0.2]
        bot_dir = 'y'
        routing_grid = RoutingGrid(self.prj.tech_info, layers, spaces, widths, bot_dir)

        self.tdb = PhotonicTemplateDB('template_libs.def', routing_grid, lib_name, use_cybagoa=True,
                                      gds_lay_file=self.layermap_path, gds_filepath=self.gds_path,
                                      lsf_filepath=self.lsf_path, dataprep_file=self.dataprep_path,
                                      lsf_export_filepath=self.lsf_export_path)

    def generate_gds(self, layout_params_list=None, cell_name_list=None) -> None:
        """
        Generates a batch of layouts with the layout package/class in the spec file with the parameters set by
        layout_params_list and names them according to cell_name_list. Each dict in the layout_params_list creates a
        new layout

        Parameters
        ----------
        layout_params_list : List[dict]
            Optional list of dicts corresponding to layout parameters passed to the generator class
        cell_name_list : List[str]
            Optional list of strings corresponding to the names given to each generated layout
        """
        # If no list is provided, extract layout params from the provided spec file
        if layout_params_list is None:
            layout_params_list = [self.specs['layout_params']]
        if cell_name_list is None:
            cell_name_list = [self.specs['impl_cell']+str(count) for count in range(len(layout_params_list))]

        print('\n---Generating .gds file---')
        cls_package = self.specs['layout_package']
        cls_name = self.specs['layout_class']

        lay_module = importlib.import_module(cls_package)
        temp_cls = getattr(lay_module, cls_name)

        temp_list = []
        for lay_params in layout_params_list:
            template = self.tdb.new_template(params=lay_params, temp_cls=temp_cls, debug=False)
            temp_list.append(template)

        self.tdb.batch_layout(self.prj,
                              template_list=temp_list,
                              name_list=cell_name_list,
                              lib_name='',
                              )

    def generate_lsf(self, debug=False, create_materials=True):
        """ Converts generated layout to lsf format for lumerical import """
        print('\n---Generating the design .lsf file---')
        if create_materials is True:
            self.create_materials_file()

        self.tdb.to_lumerical(gds_layermap=self.layermap_path,
                              lsf_export_config=self.lsf_export_path,
                              lsf_filepath=self.lsf_path,
                              debug=debug,
                              )

    def generate_tb(self, generate_gds=False, debug=False):
        """ Generates the lumerical testbench lsf """
        print('\n---Generating the tb .lsf file---')
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
            layout_params_list.append(temp_params)
            cell_name_list.append(self.specs['lsf_filename'] + '_' + str(count))

        # Try importing the TB package and class
        cls_package = self.specs['tb_package']
        cls_name = self.specs['tb_class']
        lay_module = importlib.import_module(cls_package)
        temp_cls = getattr(lay_module, cls_name)

        # Create TB lsf file
        self.tdb._prj = self.prj
        temp_list = []
        for lay_params in layout_params_list:
            template = self.tdb.new_template(params=lay_params, temp_cls=temp_cls, debug=debug)
            temp_list.append(template)
        self.tdb.instantiate_flat_masters(master_list=temp_list,
                                          name_list=cell_name_list,
                                          lib_name='_tb',
                                          debug=debug,
                                          rename_dict=None,
                                          draw_flat_gds=generate_gds,
                                          )

        # Create the design LSF file
        self.tdb.to_lumerical(gds_layermap=self.layermap_path,
                              lsf_export_config=self.lsf_export_path,
                              lsf_filepath=self.lsf_path,
                              debug=debug,
                              )

        # Create the sweep LSF file
        filepath = self.tdb.lsf_filepath + '_sweep'
        lsfwriter = LumericalSweepGenerator(filepath)
        for script in cell_name_list:
            lsfwriter.add_sweep_point(script_name=script)
        lsfwriter.export_to_lsf()

    def generate_flat_gds(self,
                          generate_gds=True,
                          layout_params_list=None,
                          cell_name_list=None,
                          gen_full_gds=False,
                          gen_design_gds=True,
                          gen_physical_gds=True,
                          debug=False) -> None:
        """
        Generates a batch of layouts with the layout package/class in the spec file with the parameters set by
        layout_params_list and names them according to cell_name_list. Each dict in the layout_params_list creates a
        new layout

        Parameters
        ----------
        generate_gds : Optional[bool]
            Optional parameter: True (default) to generate the GDS
        layout_params_list : List[dict]
            Optional list of dicts corresponding to layout parameters passed to the generator class
        cell_name_list : List[str]
            Optional list of strings corresponding to the names given to each generated layout
        gen_full_gds : bool
            True to generate a gds with both physical and design layers
        gen_design_gds : bool
            True to generate the gds with only photonic design (and port) layers
        gen_physical_gds : bool
            True to generate the gds with only physical layers
        debug : bool
            True to print debug information
        """
        # TODO: Implement the gen_full/gen_design/gen_physical
        # If no list is provided, extract layout params from the provided spec file
        if layout_params_list is None:
            layout_params_list = [self.specs['layout_params']]
        if cell_name_list is None:
            cell_name_list = [self.specs['impl_cell']]

        print('\n---Generating flat .gds file---')
        cls_package = self.specs['layout_package']
        cls_name = self.specs['layout_class']

        lay_module = importlib.import_module(cls_package)
        temp_cls = getattr(lay_module, cls_name)

        temp_list = []
        for lay_params in layout_params_list:
            template = self.tdb.new_template(params=lay_params, temp_cls=temp_cls, debug=debug)
            temp_list.append(template)

        self.tdb._prj = self.prj
        self.tdb.instantiate_flat_masters(master_list=temp_list,
                                          name_list=cell_name_list,
                                          lib_name='_flat',
                                          debug=debug,
                                          rename_dict=None,
                                          draw_flat_gds=generate_gds,
                                          )

    def dataprep(self, debug=False):
        """
        Parameters
        ----------
        debug : bool
            True to print debug information
        Returns
        -------
        """
        print('\n---Performing dataprep---')
        self.generate_flat_gds(generate_gds=False)
        self.tdb.dataprep(dataprep_file=self.dataprep_path,
                          debug=debug,
                          push_portshapes_through_dataprep=False,
                          )
        self.tdb.create_masters_in_db(lib_name='_dataprep',
                                      content_list=self.tdb.post_dataprep_flat_content_list,
                                      debug=debug,
                                      )

    def create_materials_file(self):
        """
        Takes the custom materials stated in the lumerical_map and generates a Lumerical lsf file that defines the
        materials for use in simulation.
        """
        # 1) load the lumerical map file
        inpath = self.lsf_export_path
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

    @staticmethod
    def load_yaml(filepath):
        """ Setup standardized method for yaml loading """
        with open(filepath, 'r') as stream:
            temp = yaml.safe_load(stream)
        return temp
