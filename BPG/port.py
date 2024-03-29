from BPG.geometry import Transformable2D

from typing import TYPE_CHECKING, Tuple
import numpy as np
from bag.layout.util import transform_point, transform_loc_orient

if TYPE_CHECKING:
    from BPG.bpg_custom_types import dim_type, coord_type, lpp_type, layer_or_lpp_type


class PhotonicPort(Transformable2D):
    # TODO:  __slots__ =
    def __init__(self,
                 name: str,
                 center: "coord_type",
                 orient: str,
                 width: "dim_type",
                 layer: "lpp_type",
                 resolution: float,
                 angle: float = 0.0,
                 mirrored: bool = False,
                 force_cardinal: bool = False,
                 unit_mode: bool = False,
                 info: dict = None,
                 ) -> None:
        """Creates a new PhotonicPort object

        Parameters
        ----------
        name : str
            the name of the port
        center : Tuple[Union[float, int], Union[float, int]]
            the (x, y) point of the port
        orient : str
            the orientation pointing into the object of the port
        width : Union[float, int]
            the port width
        layer : Tuple[str, str]
            the LPP on which the port should be drawn
        resolution : float
            the grid resolution
        angle : float
            The offset angle of the port, within [0, pi/2). Defaults to 0.0
        mirrored : bool
            True if the port orientation is mirrored. Defaults to False.
        force_cardinal : bool
            Tracks whether the angle is cardinal and should be snapped to 90deg where applicable
        unit_mode : bool
            True if layout dimensions are specified in resolution units
        info : dict
            A dictionary that can contain additional information that should be stored / associated with a PhotonicPort

        """
        # Set up _resolution, _mod_angle, _center_unit, _orient, _is_cardinal
        Transformable2D.__init__(self,
                                 center=center,
                                 resolution=resolution,
                                 orientation=orient,
                                 angle=angle,
                                 mirrored=mirrored,
                                 force_cardinal=force_cardinal,
                                 unit_mode=unit_mode
                                 )
        self._name = name

        if not (isinstance(layer, tuple) and (len(layer) == 2) and
                isinstance(layer[0], str) and isinstance(layer[1], str)):
            raise ValueError(f'LPP {layer} into PhotonicPort is not valid. Must be a tuple of 2 strings.')

        self._layer = layer
        self._used = False
        self._orientation = orient
        if unit_mode:
            self._width_unit = int(round(width))
        else:
            self._width_unit = int(round(width / self.resolution))

        if info is None:
            self.info = dict()
        else:
            self.info = info

    def __repr__(self):
        return (f'PhotonicPort(name={self.name}, layer=({self.layer}), location=({self.center}), '
                f'angle={np.rad2deg(self.angle)} deg')

    def __str__(self):
        return self.__repr__()

    def __copy__(self):
        return PhotonicPort(
            name=self.name,
            center=self.center_unit,
            orient=self.orientation,
            width=self.width_unit,
            layer=self.layer,
            resolution=self.resolution,
            angle=self.mod_angle,
            mirrored=self.mirrored,
            unit_mode=True,
            info=self.info,
        )

    @property
    def name(self) -> str:
        """ Returns the name of the port """
        return self._name

    @name.setter
    def name(self,
             name: str,
             ):
        """Sets the port name"""
        self._name = name

    @property
    def layer(self) -> "lpp_type":
        """Returns the layer of the port """
        return self._layer

    @property
    def width(self) -> float:
        """Returns the width of the port """
        return self._width_unit * self._resolution

    @property
    def width_unit(self) -> int:
        """Returns the width of the port in layout units"""
        return self._width_unit

    @width.setter
    def width(self, new_width: float) -> None:
        """Sets the port width"""
        self._width_unit = int(round(new_width / self._resolution))

    @width_unit.setter
    def width_unit(self, new_width: int) -> None:
        """Sets the port width"""
        self._width_unit = int(round(new_width))

    @property
    def width_vec_unit(self):
        """A vector pointing in the direction of the port, whose length is the width of the port."""
        return self.width_unit * np.cos(self.angle), self.width_unit * np.sin(self.angle)

    @classmethod
    def from_dict(cls,
                  center: "coord_type",
                  name: str,
                  orient: str,
                  port_width: "dim_type",
                  layer: "layer_or_lpp_type",
                  resolution: float,
                  unit_mode: bool = True,
                  ) -> "PhotonicPort":
        """Creates a new PhotonicPort object from a set of arguments

        Parameters
        ----------
        center : Tuple[Union[float, int], Union[float, int]]
            the (x, y) point of the port
        name : str
            the name of the port
        orient : str
            the orientation pointing into the object of the port
        port_width : Union[float, int]
            the port width
        layer : Union[Tuple[str, str], str]
            the layer / layer purpose pair on which the port should be drawn. If the purpose is not specified, it is
            defaulted to the 'port' purpose
        resolution : float
            the grid resolution
        unit_mode : bool
            True if layout dimensions are specified in resolution units

        Returns
        -------
        port : PhotonicPort
            the generated port
        """
        if isinstance(layer, str):
            layer = (layer, 'port')

        port = PhotonicPort(name, center, orient, port_width, layer, resolution, unit_mode)
        return port
