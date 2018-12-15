# Expose the LumericalGenerator class, which is the superclass of all lsf files
from .lumerical.code_generator import LumericalDesignGenerator, LumericalSweepGenerator

# Expose PhotonicTemplateBase so that all Generators can subclass it
from .template import PhotonicTemplateBase

# Expose PhotonicLayoutManager/PhotonicBagProject to encapsulate gds and lsf export
from .layout_manager import PhotonicLayoutManager
from .photonic_core import PhotonicBagProject

# Expose base shapes that can be drawn
from . import objects

__version__ = '0.2.0'
print(f'Successfully imported BPG v{__version__}')
