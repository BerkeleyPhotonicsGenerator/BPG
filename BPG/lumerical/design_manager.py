import BPG
import importlib
import logging
from copy import deepcopy
from .code_generator import LumericalSweepGenerator

from typing import Dict, Any, List
from BPG.bpg_custom_types import *

logger = logging.getLogger(__name__)


class LumericalDesignManager(BPG.PhotonicLayoutManager):
    """
    This class is a drop-in replacement for PhotonicLayoutManager, and allows users to generate batches of designs
    to be simulated in Lumerical.
    """

    def __init__(self, spec_file: str, bag_config_path: str = None, port: int = None):
        BPG.PhotonicLayoutManager.__init__(self, spec_file, bag_config_path, port)
        self.design_list: List = []
        self.base_params: Dict[str, Any] = self.specs['layout_params']
        self.base_class: PhotonicTemplateType = self.get_cls_from_str(module_name=self.specs['layout_package'],
                                                                      cls_name=self.specs['layout_class'])

    def add_sweep_point(self, temp_cls: PhotonicTemplateType = None, params: dict = None) -> None:
        """
        Generates a template class / parameter dictionary tuple and stores it in a running list of all designs to be
        generated in this batch.

        By default the class and parameters from the spec file are used, but the tech class and any subset of the
        parameters can be updated by the arguments of this function.

        Parameters
        ----------
        temp_cls : PhotonicTemplateBase
            Class that will be used to generate the template
        params : Dict
            dictionary of parameters to be sent to the generator class
        """
        # If a template class is not given, one from the spec file will be used
        if temp_cls is None:
            cls_package = self.specs['layout_package']
            cls_name = self.specs['layout_class']
            lay_module = importlib.import_module(cls_package)
            temp_cls = getattr(lay_module, cls_name)
            # Parameters from the spec file will be used, and updated with any user provided values
            if params is None:
                design_params = self.base_params
            else:
                design_params = deepcopy(self.base_params)
                design_params.update(params)
        # If you are providing your own template class, parameters from the spec file will not be used.
        else:
            if params is None:
                raise ValueError('Parameter dictionary cannot be empty if you provide your own class')
            design_params = params

        # Add the template class and associated design parameters to the list
        self.design_list.append((temp_cls, design_params))

    def generate_batch(self, batch_name: str):
        """
        Generates the batch of content lists and lsf files from all of the current

        Parameters
        ----------
        batch_name : str
            This is the base name of the lumerical sweep files we will be generating.
        """
        # Set the root name for all files in this batch
        root_path = self.scripts_dir

        # Generate templates from all of the sweep points
        for dsn in self.design_list:
            self.generate_template(temp_cls=dsn[0], params=dsn[1], cell_name=batch_name)

        # Generate all of the lsf files
        self.generate_flat_content()
        self.generate_lsf()

        # Create the sweep LSF file
        batch_sweep_name = batch_name + '_main'
        sweep_filename = str(root_path / batch_sweep_name)
        lsfwriter = LumericalSweepGenerator(sweep_filename)
        for script in self.cell_name_list:
            lsfwriter.add_sweep_point(script_name=script)
        lsfwriter.export_to_lsf()

    @staticmethod
    def get_cls_from_str(module_name: str, cls_name: str):
        """
        Returns the class specified by the provided module name and class name

        Parameters
        ----------
        module_name : str
            Name of the module that contains the class
        cls_name : str
            Name of the class to be imported

        Returns
        -------

        """
        lay_module = importlib.import_module(module_name)
        return getattr(lay_module, cls_name)
