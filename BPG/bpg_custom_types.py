from typing import Union, Tuple, TypeVar

dim_type = Union[float, int]
coord_type = Tuple[dim_type, dim_type]
lpp_type = Tuple[str, str]
layer_or_lpp_type = Union[str, Tuple[str, str]]
PhotonicTemplateType = TypeVar('PhotonicTemplateType', bound="PhotonicTemplateBase")