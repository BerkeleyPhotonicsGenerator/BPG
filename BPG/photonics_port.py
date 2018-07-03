#!/usr/bin/python
# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING, Tuple, Union, List, Optional, Dict, Any, Iterator, Iterable, Generator
import numpy as np

dim_type = Union[float, int]
coord_type = Tuple[dim_type, dim_type]


class PhotonicPort:
    # TODO:  __slots__ =
    def __init__(self,
                 name,  # type: str
                 center,  # type: coord_type
                 inside_point,  # type: coord_type
                 width,  # type: dim_type
                 layer,  # type: Tuple[str, str]
                 resolution,  # type: Union[float, int]
                 unit_mode=False,  # type: bool
                 ):
        # type: (...) -> None

        self._res = resolution
        if not unit_mode:
            center = (int(round(center[0] / resolution)), int(round(center[1] / resolution)))
            width = int(round(width / resolution))
            inside_point = (int(round(inside_point[0] / resolution)), int(round(inside_point[1] / resolution)))

        self._center_unit = np.array([center[0], center[1]])  # type: np.array
        self._name = name  # type: str
        self._layer = layer  # type: int
        self._matched = False

        # Convert to np array
        inside_point = np.array([inside_point[0], inside_point[1]])

        # Is x distance greater than y
        if abs(self._center_unit - inside_point)[0] > abs(self._center_unit - inside_point)[1]:
            # Is inside to the right
            if inside_point[0] > center[0]:
                self._inside_point_unit = self._center_unit + np.array([width, 0])
            else:
                self._inside_point_unit = self._center_unit - np.array([width, 0])
        else:
            # Is inside up
            if inside_point[1] > center[1]:
                self._inside_point_unit = self._center_unit + np.array([0, width])
            else:
                self._inside_point_unit = self._center_unit - np.array([0, width])

    @property
    def matched(self):
        return self._matched

    @matched.setter
    def matched(self,
                new_match  # type: bool
                ):
        self._matched = new_match

    #@property
    def center(self,
               unit_mode=True,  # type: bool
               ):
        # type: (...) -> np.array
        """ Returns the center of the port """
        if unit_mode:
            return self._center_unit
        else:
            return self._center_unit * self._res

    #@property
    def inside_point(self,
                     unit_mode=True,  # type: bool
                     ):
        # type: (...) -> np.array
        """ Returns the interior point for port orientation"""
        if unit_mode:
            return self._inside_point_unit
        else:
            return self._inside_point_unit * self._res

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

    # @property
    def width(self,
              unit_mode=True,  # type: bool
              ):
        # type: () -> dim_type
        """ Returns the width of the port """
        if unit_mode:
            return int(round(np.linalg.norm(self._center_unit - self._inside_point_unit)))
        else:
            return int(round(np.linalg.norm(self._center_unit - self._inside_point_unit))) * self._res

    # @property
    def orient_vec(self,
                   unit_mode=True,  # type: bool
                   normalized=True,  # type: bool
                   ):
        # type: (...) -> np.array
        """Returns a normalized vector pointing into the port object

        Parameters
        ----------
        unit_mode : bool
            True to return vector in resolution units
        normalized : bool
            True to normalize the vector. If False, vector magnitude is wg width

        Returns
        -------

        """

        vec = (self._inside_point_unit - self._center_unit)

        if normalized:
            vec = np.round(vec / np.linalg.norm(vec)).astype(int)

        if unit_mode:
            return vec
        else:
            return vec * self._res

    @property
    def orientation(self):
        # type: () -> str
        """ Returns the orientation of the port """
        diff = self._inside_point_unit - self._center_unit
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

    def is_horizontal(self):
        if self.orientation == 'R0' or self.orientation == 'R180':
            return True
        else:
            return False

    def is_vertical(self):
        return not self.is_horizontal()

    @classmethod
    def from_dict(cls,
                  center,  # type: coord_type
                  name,  # type: str
                  inside_point,  # type: coord_type
                  port_width,  # type: dim_type
                  layer,  # type: Union[str, Tuple[str, str]]
                  resolution,  # type: Union[float, int]
                  unit_mode=True,  # type: bool
                  ):
        # type: (...) -> PhotonicPort

        if isinstance(layer, str):
            layer = (layer, 'port')

        port = PhotonicPort(name, center, inside_point, port_width, layer, resolution, unit_mode)
        return port


'''
class Ports:

    def __init__(self,
                 port=None,  # type: Optional[Port]
                 ):
        if port is None:
            self._ports = []
        else:
            self._ports = [PhotonicPort]

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
        self._ports.append(PhotonicPort)
'''
