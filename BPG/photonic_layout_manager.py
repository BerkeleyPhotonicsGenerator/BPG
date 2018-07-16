import yaml
import importlib
import os

from pathlib import Path
from bag.layout import RoutingGrid
from bag.simulation.core import DesignManager
from BPG.photonic_template import PhotonicTemplateDB


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
        self.project_dir = Path(self.specs['project_dir']).expanduser()
        self.scripts_dir = self.project_dir / 'scripts'
        self.data_dir = self.project_dir / 'data'

        # Setup the technology files
        if 'layermap' in self.specs:
            bag_work_dir = Path(os.environ['BAG_WORK_DIR'])
            self.layermap = bag_work_dir / self.specs['layermap']
        elif 'BAG_PHOT_LAYERMAP' in os.environ:
            self.layermap = os.environ['BAG_PHOT_LAYERMAP']
        else:
            raise EnvironmentError('Technology layermap not provided')

        # Make the directories if they do not exists
        self.project_dir.mkdir(exist_ok=True, parents=True)
        self.scripts_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)

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
        layers = [3, 4, 5]
        spaces = [0.1, 0.1, 0.2]
        widths = [0.1, 0.1, 0.2]
        bot_dir = 'y'
        routing_grid = RoutingGrid(self.prj.tech_info, layers, spaces, widths, bot_dir)

        self.tdb = PhotonicTemplateDB('template_libs.def', routing_grid, lib_name, use_cybagoa=True,
                                      gds_lay_file=self.layermap, gds_filepath=self.gds_path,
                                      lsf_filepath=self.lsf_path)

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
            cell_name_list = [self.specs['impl_cell']]

        print('Generating .gds file')
        cls_package = self.specs['layout_package']
        cls_name = self.specs['layout_class']

        lay_module = importlib.import_module(cls_package)
        temp_cls = getattr(lay_module, cls_name)

        temp_list = []
        for lay_params in layout_params_list:
            template = self.tdb.new_template(params=lay_params, temp_cls=temp_cls, debug=False)
            temp_list.append(template)

        self.tdb.batch_layout(self.prj, temp_list, cell_name_list)

    def generate_lsf(self):
        """ Converts generated layout to lsf format for lumerical import """
        print('Generating .lsf file')
        self.tdb.to_lumerical()

    def generate_shapely(self):
        return self.tdb.to_shapely()

    @staticmethod
    def load_yaml(filepath):
        """ Setup standardized method for yaml loading """
        with open(filepath, 'r') as stream:
            temp = yaml.safe_load(stream)
        return temp
