import BPG
import importlib
import logging
from copy import deepcopy
from .code_generator import LumericalSweepGenerator

from typing import Dict, List, Optional
from BPG.bpg_custom_types import *

logger = logging.getLogger(__name__)


class LumericalDesignManager(BPG.PhotonicLayoutManager):
    """
    This class is a drop-in replacement for PhotonicLayoutManager, and allows users to generate batches of designs
    to be simulated in Lumerical. Note that using this class requires that the user has both a layout generator and a
    LumericalTB class prepared.

    Notes
    -----
    * This class first sets a 'base_dut' and a 'base testbench' to be simulated. The parameters for these are
    extracted from the provided spec file. The base dut layout and base testbench can be manually reset by calling
    `set_base_dut()` or `set_base_tb()`.

    * The user can then add any additional variations of the base layout and base testbench to be simulated by adding
    sweep points. Sweep points allow you to modify subsets of the parameters without re-specifying the entire
    parameter dictionary.

    * When all sweep points have been created, the user can export generate the actual layout and testbench lsf's by
    calling `generate_batch()`. The name provided to generate_batch will be used as the prefix for all .lsf files in
    the batch. A `main` .lsf will also be provided to automatically run all points in the batch

    * Sweep point creation and batch generation can be run multiple times to perform more complex simulation
    operations, like closed loop optimization.
    """

    def __init__(self, spec_file: str, bag_config_path: Optional[str] = None, port: Optional[int] = None) -> None:
        BPG.PhotonicLayoutManager.__init__(self, spec_file, bag_config_path, port)
        self.design_list: List = []
        self.base_tb_class = None
        self.base_tb_params = None
        self.base_layout_package = None
        self.base_layout_class = None
        self.base_layout_params = None

        # Initialize the design manager with the layout and tb classes from the specification file
        self.set_base_tb()
        self.set_base_dut()

    def set_base_dut(self,
                     layout_module: str = None,
                     layout_class: str = None,
                     layout_params: str = None
                     ) -> None:
        """
        Fix a new layout generator class as the base device under test. Any subsequently added sweep points will be
        based on this dut and parameter set. If some arguments are not provided, the value will be extracted from the
        spec file.

        Parameters
        ----------
        layout_module : str
            Name of the Python module containing the DUT class
        layout_class : str
            Name of the DUT layout generator class contained within layout_module
        layout_params : dict
            Dictionary of parameters to be sent to the layout generator
        """
        if layout_module is None or layout_class is None:
            self.base_layout_package = BPG.run_settings['layout_package']
            self.base_layout_class = BPG.run_settings['layout_class']
        else:
            self.base_layout_package = layout_module
            self.base_layout_class = layout_class
        if layout_params is None:
            self.base_layout_params = BPG.run_settings['layout_params']
        else:
            self.base_layout_params = layout_params

    def set_base_tb(self,
                    tb_cls: PhotonicTemplateType = None,
                    tb_params: dict = None,
                    ) -> None:
        """
        Fix a new LumericalTB class as the base testbench. Any subsequently added sweep points will be based on this
        dut and parameter set. If some arguments are not provided, the value will be extracted from the spec file.

        Parameters
        ----------
        tb_cls : PhotonicTemplateType
            generator class that will be used to set the testbench structure
        tb_params : dict
            dictionary of testbench parameters to the sent to the generator class
        """
        if tb_cls is None:
            self.base_tb_class = self.get_cls_from_str(module_name=BPG.run_settings['tb_package'],
                                                       cls_name=BPG.run_settings['tb_class'])
        else:
            self.base_tb_class = tb_cls
        if tb_params is None:
            self.base_tb_params = BPG.run_settings['tb_params']
        else:
            self.base_tb_params = tb_params

    def add_sweep_point(self, layout_params: dict = None, tb_params: dict = None) -> None:
        """
        Generates a template class / parameter dictionary tuple and stores it in a running list of all designs to be
        generated in this batch.

        By default the class and parameters from the spec file are used, but the tech class and any subset of the
        parameters can be updated by the arguments of this function.

        Parameters
        ----------
        layout_params : Dict
            dictionary of parameters to be sent to the layout generator class
        tb_params : Dict
            dictionary of parameters to be sent to the testbench generator class
        """
        if layout_params is None:
            design_layout_params = self.base_layout_params
        else:
            design_layout_params = deepcopy(self.base_layout_params)
            design_layout_params.update(layout_params)
        if tb_params is None:
            design_tb_params = self.base_tb_params
        else:
            design_tb_params = deepcopy(self.base_tb_params)
            design_tb_params.update(tb_params)

        # Assemble final parameter dictionary to be sent to tb class
        params = dict(
            layout_package=self.base_layout_package,
            layout_class=self.base_layout_class,
            layout_params=design_layout_params,
            tb_params=design_tb_params
        )

        # Add the tb class and associated design parameters to the list
        self.design_list.append((self.base_tb_class, params))

    def generate_batch(self,
                       batch_name: str,
                       generate_gds: bool = False,

                       ) -> None:
        """
        Generates the batch of content lists and lsf files from all of the current designs in the design_list. Also
        generates a sweep lsf file that automatically serially executes all of the individual lsf files.

        Parameters
        ----------
        batch_name : str
            This is the base name of the lumerical sweep files we will be generating.
        generate_gds : bool
            If True
        """
        # Clear the lists to prevent contamination
        self.template_list = []
        self.cell_name_list = []

        # Set the root name for all files in this batch
        root_path = self.scripts_dir

        # Generate templates from all of the sweep points
        for dsn in self.design_list:
            self.generate_template(temp_cls=dsn[0], params=dsn[1], cell_name=batch_name)

        # Generate all of the lsf files
        self.generate_flat_content()
        if generate_gds:
            self.generate_flat_gds()
        self.generate_lsf()

        # Create the sweep LSF file
        batch_sweep_name = batch_name + '_main'
        sweep_filename = str(root_path / batch_sweep_name)
        lsfwriter = LumericalSweepGenerator(sweep_filename)
        for script in self.cell_name_list:
            lsfwriter.add_sweep_point(script_name=script)
        lsfwriter.export_to_lsf()

        # Reset the lists after generating scripts
        self.design_list = []

    def generate_batch_calibre(self,
                               batch_name: str,
                               export_dir = None,
                               ) -> None:
        """
        Generates the batch of content lists and lsf files from all of the current designs in the design_list. Also
        generates a sweep lsf file that automatically serially executes all of the individual lsf files.

        Parameters
        ----------
        batch_name : str
            This is the base name of the lumerical sweep files we will be generating.
        """
        # Clear the lists to prevent contamination
        self.template_list = []
        self.cell_name_list = []

        temp_list = []

        # Set the root name for all files in this batch
        root_path = self.scripts_dir

        # Generate templates from all of the sweep points
        for dsn in self.design_list:
            self.template_list = []
            self.cell_name_list = []
            self.generate_template(temp_cls=dsn[0], params=dsn[1], cell_name=batch_name)
            self.generate_content(save_content=False)
            self.generate_gds()
            self.generate_lsf_calibre(export_dir=export_dir)

        # Create the sweep LSF file
        batch_sweep_name = batch_name + '_main'
        sweep_filename = str(root_path / batch_sweep_name)
        lsfwriter = LumericalSweepGenerator(sweep_filename)
        for script in self.cell_name_list:
            lsfwriter.add_sweep_point(script_name=script)
        lsfwriter.export_to_lsf()

        # Reset the lists after generating scripts
        self.design_list = []

    @staticmethod
    def get_cls_from_str(module_name: str, cls_name: str):
        """
        Returns the Python class specified by the provided module name and class name

        Parameters
        ----------
        module_name : str
            Name of the module that contains the class
        cls_name : str
            Name of the class to be imported
        """
        lay_module = importlib.import_module(module_name)
        return getattr(lay_module, cls_name)
