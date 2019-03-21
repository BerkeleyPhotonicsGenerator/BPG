from typing import Union, Tuple, TypeVar

# Type representing a dimension.
# Types in BAG/BPG can be floats or ints depending on whether or not
# unit_mode is set.
# Using float vs int depends on the exact usecases.
dim_type = Union[float, int]

# A coordinate is a pair of dim_types.
coord_type = Tuple[dim_type, dim_type]

# A layer-purpose pair.
lpp_type = Tuple[str, str]

# Either a layer or a layer-purpose pair.
layer_or_lpp_type = Union[str, Tuple[str, str]]

PhotonicTemplateType = TypeVar('PhotonicTemplateType', bound="PhotonicTemplateBase")
