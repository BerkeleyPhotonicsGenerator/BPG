#!/usr/bin/python
# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING, Tuple, Union, List, Optional, Dict, Any, Iterator, Iterable, Generator

dim_type = Union[float, int]
coord_type = Tuple[dim_type, dim_type]


class Port:

    def __init__(self,
                 center,  # type: coord_type
                 name,  # type: str
                 inside_point,  # type: coord_type
                 port_width,  # type: dim_type
                 layer,  # type: int
                 ):
        # type: (...) -> None

        self._center = center  # type: coord_type
        self._name = name  # type: str
        self._layer = layer  # type: int

        # Is x distance greater than y
        if abs(center[0] - inside_point[0]) > abs(center[1] - inside_point[1]):
            # Is inside to the right
            if inside_point[0] > center[0]:
                self._inside_point = (center[0] + port_width, center[1])
            else:
                self._inside_point = (center[0] - port_width, center[1])
        else:
            # Is inside up
            if inside_point[1] > center[1]:
                self._inside_point = (center[0], center[1] + port_width)
            else:
                self._inside_point = (center[0], center[1] - port_width)

    @property
    def center(self):
        # type: () -> coord_type
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
        return max(abs(self._center[0] - self._inside_point[0]), abs(self._center[1] - self._inside_point[1]))

    @property
    def orientation(self):
        # type: () -> str
        """ Returns the orientation of the port """
        diff = (self._inside_point[0] - self._center[0], self._inside_point[1] - self._center[1])
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
