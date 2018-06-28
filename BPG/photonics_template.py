# -*- coding: utf-8 -*-


from typing import TYPE_CHECKING, Union, Dict, Any, List, Set, TypeVar, Type, \
    Optional, Tuple, Iterable, Sequence, Callable, Generator

import abc
import numpy as np

from bag.layout.template import TemplateBase, TemplateDB
from .photonics_port import PhotonicsPort
from .photonics_objects import *

dim_type = Union[float, int]
coord_type = Tuple[dim_type, dim_type]


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
        self._photonic_ports = {}

    @abc.abstractmethod
    def draw_layout(self):
        pass

    def add_rect(self,  # type: TemplateBase
                 layer,  # type: Union[str, Tuple[str, str]]
                 bbox,  # type: Union[BBox, BBoxArray]
                 nx=1,  # type: int
                 ny=1,  # type: int
                 spx=0,  # type: Union[float, int]
                 spy=0,  # type: Union[float, int]
                 unit_mode=False,  # type: bool
                 ):
        rect = PhotonicRect(layer, bbox, nx=nx, ny=ny, spx=spx, spy=spy, unit_mode=unit_mode)
        self._layout.add_rect(rect)
        self._used_tracks.record_rect(self.grid, layer, rect.bbox_array)
        return rect

    def add_photonic_port(self,
                          name,  # type: str
                          center,  # type: coord_type
                          inside_point,  # type: coord_type
                          width,  # type: dim_type
                          layer,  # type: Union[str, Tuple[str, str]]
                          ):
        if name in self._photonic_ports.keys():
            raise ValueError('Port "{}" already exists in cell.'.format(name))

        self._photonic_ports[name] = PhotonicsPort(name, center, inside_point, width, layer)

    def has_photonic_port(self,
                          port_name,  # type: str
                          ):
        return port_name in self._photonic_ports

    def get_photonic_port(self,
                          port_name='',  # type: str
                          ):
        # type: (...) -> PhotonicsPort
        """Returns the photonic port object with the given name

        Parameters
        ----------
        :param port_name: str
            the photonic port terminal name. If None or empty, check if this photonic template has only one port,
            and return it

        Returns
        -------
        :return: photonicPort : PhotonicsPort
            The photonic port object
        """
        if not self.has_photonic_port(port_name):
            raise ValueError('Port "{}" does not exist in {}'.format(port_name, self.__class__.__name__))

        if not port_name:
            if len(self._photonic_ports) != 1:
                raise ValueError(
                    'Template "{}" has {} ports != 1. Must get port by name.'.format(self.__class__.__name__,
                                                                                     len(self._photonic_ports)
                                                                                     )
                )
        return self._photonic_ports[port_name]

    def add_instances_port_to_port(self,
                                   instance,  # type: PhotonicsTemplateBase
                                   instance_port_name,  # type: str
                                   self_port_name,  # type: str
                                   instance_name=None,  # type: str
                                   ):
        if not self.has_photonic_port(self_port_name):
            raise ValueError('Photonic cell ' + self_port_name + 'does not exist in ' + self.__class__.__name__)

        if not instance.has_photonic_port(instance_port_name):
            raise ValueError('Photonic cell ' + instance_port_name + 'does not exist in ' + instance.__class__.__name__)

        # TODO: think about params
        inst_master = self.new_template(temp_cls=instance)  # type: PhotonicsTemplateBase

        my_port = self.get_photonic_port(self_port_name)
        new_port = inst_master.get_photonic_port(instance_port_name)

        scalar_product = np.dot(my_port.orient_vec, new_port.orient_vec)
        vector_product = np



        self.add_instance(
            inst_master,
            instance_name,
            loc,
            orient,
        )

