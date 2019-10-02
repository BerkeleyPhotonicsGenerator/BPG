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