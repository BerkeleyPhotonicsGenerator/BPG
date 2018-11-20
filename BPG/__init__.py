# Expose the LumericalGenerator class, which is the superclass of all lsf files
from .lumerical.code_generator import LumericalDesignGenerator, LumericalSweepGenerator

# Expose PhotonicTemplateBase so that all Generators can subclass it
from .template import PhotonicTemplateBase

# Expose PhotonicLayoutManager to encapsulate gds and lsf export
from .photonic_layout_manager import PhotonicLayoutManager
from .photonic_core import PhotonicBagProject

__version__ = '0.0.1'
print(f'Successfully imported BPG v{__version__}')
