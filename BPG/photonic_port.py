#!/usr/bin/python
# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING, Tuple, Union, List, Optional, Dict, Any, Iterator, Iterable, Generator
import numpy as np
from bag.layout.util import transform_point, transform_loc_orient

dim_type = Union[float, int]
coord_type = Tuple[dim_type, dim_type]


class PhotonicPort:
    # TODO:  __slots__ =
    # TODO: Ensure unit mode is rounded properly
    def __init__(self,
                 name,  # type: str
                 center,  # type: coord_type
                 orientation,  # type: str
                 width,  # type: dim_type
                 layer,  # type: Tuple[str, str]
                 resolution,  # type: float
                 unit_mode=False,  # type: bool
                 ):
        # type: (...) -> None

        self._res = resolution
        if not unit_mode:
            center = (int(round(center[0] / resolution)), int(round(center[1] / resolution)))
            width = int(round(width / resolution))

        self._center_unit = np.array([center[0], center[1]])  # type: np.array
        self._name = name
        self._layer = layer
        self._used = False
        self._width_unit = width
        self._orientation = orientation

    @property
    def used(self):
        return self._used

    @used.setter
    def used(self,
             new_used  # type: bool
             ):
        self._used = new_used

    @property
    def center(self):
        # type: (...) -> np.array
        """Return the center coordinates as np array"""
        return self._center_unit * self._res

    @property
    def center_unit(self):
        # type: (...) -> np.array
        """Return the center coordinates as np array in resolution units"""
        return self._center_unit

    @property
    def resolution(self):
        # type (...) -> float
        """Returns the layout resolution of the port object"""
        return self._res

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
        # type: () -> Tuple[str, str]
        """Returns the layer of the port """
        return self._layer

    @property
    def width(self):
        # type: () -> float
        """Returns the width of the port """
        return self._width_unit * self._res

    @property
    def width_unit(self):
        # type: () -> int
        """Returns the width of the port in layout units"""
        return self._width_unit

    @width.setter
    def width(self, new_width):
        # type: (float) -> None
        """Sets the port width"""
        self._width_unit = int(round(new_width / self._res))

    @width_unit.setter
    def width_unit(self, new_width):
        # type: (int) -> None
        """Sets the port width"""
        self._width_unit = new_width

    def width_vec(self,
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

        # Create R0 vector of proper magnitude
        if normalized:
            point = (int(round(1 / self._res)), 0)
        else:
            point = (self._width_unit, 0)

        # Rotate vector by port orientation
        point = transform_point(point[0], point[1], (0, 0), self._orientation)

        if unit_mode:
            return point
        else:
            return point * self._res

    @property
    def orientation(self):
        # type: () -> str
        """ Returns the orientation of the port """
        return self._orientation

    def is_horizontal(self):
        if self.orientation == 'R0' or self.orientation == 'R180':
            return True
        else:
            return False

    def is_vertical(self):
        return not self.is_horizontal()

    def transform(self,
                  loc=(0, 0),  # type: coord_type
                  orient='R0',  # type: str
                  unit_mode=False,  # type: bool
                  ):
        """Return a new transformed photonic port

        Parameters
        ----------
        loc
        orient
        unit_mode

        Returns
        -------

        """
        # Convert to nearest int unit mode value
        if not unit_mode:
            res = self._res
            loc = (int(round(loc[0] / res)), int(round(loc[1] / res)))

        new_center, new_orient = transform_loc_orient(
            loc=self._center_unit,
            orient=self._orientation,
            trans_loc=loc,
            trans_orient=orient,
        )

        return PhotonicPort(name=self._name,
                            center=new_center,
                            orientation=new_orient,
                            width=self._width_unit,
                            layer=self._layer,
                            resolution=self._res,
                            unit_mode=True)

    @classmethod
    def from_dict(cls,
                  center,  # type: coord_type
                  name,  # type: str
                  orient,  # type: str
                  port_width,  # type: dim_type
                  layer,  # type: Union[str, Tuple[str, str]]
                  resolution,  # type: Union[float, int]
                  unit_mode=True,  # type: bool
                  ):
        # type: (...) -> PhotonicPort

        if isinstance(layer, str):
            layer = (layer, 'port')

        port = PhotonicPort(name, center, orient, port_width, layer, resolution, unit_mode)
        return port
