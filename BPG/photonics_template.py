# -*- coding: utf-8 -*-


from typing import TYPE_CHECKING, Union, Dict, Any, List, Set, TypeVar, Type, \
    Optional, Tuple, Iterable, Sequence, Callable, Generator

import abc

from bag.layout.template import TemplateBase, TemplateDB


class PhotonicsTemplateDB(TemplateDB):
    def __init__(self,  # type: TemplateDB
                 lib_defs,  # type: str
                 routing_grid,  # type: RoutingGrid
                 lib_name,  # type: str
                 prj=None,  # type: Optional[BagProject]
                 name_prefix='',  # type: str
                 name_suffix='',  # type: str
                 use_cybagoa=False,  # type: bool
                 gds_lay_file='',  # type: str
                 flatten=False,  # type: bool
                 **kwargs,
                 ):
        TemplateDB.__init__(self, lib_defs, routing_grid, lib_name, prj,
                            name_prefix, name_suffix, use_cybagoa, gds_lay_file,
                            flatten, **kwargs)

    def to_lumerical(self):
        pass


class PhotonicsTemplateBase(TemplateBase, metaclass=abc.ABCMeta):
    def __init__(self,
                 temp_db,  # type: TemplateDB
                 lib_name,  # type: str
                 params,  # type: Dict[str, Any]
                 used_names,  # type: Set[str]
                 **kwargs,
                 ):
        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @abc.abstractmethod
    def draw_layout(self):
        pass

    def add_photonic_port(self):
        pass

    def add_instances_port_to_port(self):
        pass

