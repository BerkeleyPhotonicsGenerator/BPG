#!/usr/bin/python
# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING, Tuple, Union, List, Optional, Dict, Any, Iterator, Iterable, Generator
import numpy as np

dim_type = Union[float, int]
coord_type = Tuple[dim_type, dim_type]


class Port:
    # TODO:  __slots__ =
    def __init__(self,
                 center,  # type: coord_type
                 name,  # type: str
                 inside_point,  # type: coord_type
                 port_width,  # type: dim_type
                 layer,  # type: int
                 ):
        # type: (...) -> None

        self._center = np.array([center[0], center[1]])  # type: np.array
        self._name = name  # type: str
        self._layer = layer  # type: int

        # Convert to np array
        inside_point = np.array([inside_point[0], inside_point[1]])

        # Is x distance greater than y
        if abs(self._center - inside_point)[0] > abs(self._center - inside_point)[1]:
            # Is inside to the right
            if inside_point[0] > center[0]:
                self._inside_point = self._center + np.array([port_width, 0])
            else:
                self._inside_point = self._center - np.array([port_width, 0])
        else:
            # Is inside up
            if inside_point[1] > center[1]:
                self._inside_point = self._center + np.array([0, port_width])
            else:
                self._inside_point = self._center - np.array([0, port_width])

    @property
    def center(self):
        # type: () -> np.array
        """ Returns the center of the port """
        return self._center

    @property
    def name(self):
        # type: () -> str
        """ Returns the name of the port """
        return self._name

    def set_name(self,
                 name,  # type: str
                 ):
        # type: (...) -> None
        self._name = name

    @property
    def layer(self):
        # type: () -> int
        """ Returns the layer of the port """
        return self._layer

    @property
    def width(self):
        # type: () -> dim_type
        """ Returns the width of the port """
        return np.linalg.norm(self._center - self._inside_point)

    @property
    def orientation(self):
        # type: () -> str
        """ Returns the orientation of the port """
        diff = self._inside_point - self._center
        # Horizontally oriented port
        if abs(diff[0]) > 0:
            if diff[0] > 0:
                orient = 'R0'
            else:
                orient = 'R180'
        else:
            if diff[1] > 0:
                orient = 'R90'
            else:
                orient = 'R270'

        return orient

    @classmethod
    def from_dict(cls,
                  center,  # type: coord_type
                  name,  # type: str
                  inside_point,  # type: coord_type
                  port_width,  # type: dim_type
                  layer,  # type: int
                  ):
        # type: (...) -> Port

        port = Port(center, name, inside_point, port_width, layer)
        return port


class Ports:

    def __init__(self,
                 port=None,  # type: Optional[Port]
                 ):
        if port is None:
            self._ports = []
        else:
            self._ports = [Port]

    def get_port_by_name(self,
                         name,  # type: str
                         ):
        # type: (...) -> Union[Port, None]
        for port in self._ports:
            if port.name == name:
                return port

        # Could not find port with that name
        # TODO: Raise error or return none?
        return None

    def rename_port(self,
                    old_name,  # type: str
                    new_name,  # type: str
                    ):
        # type: (...) -> bool

        ret_val = False
        for port in self._ports:
            if port.name == old_name:
                ret_val = True
                port.set_name(new_name)

        return ret_val

    def add_port(self,
                 port,  # type: Port
                 ):
        self._ports.append(Port)