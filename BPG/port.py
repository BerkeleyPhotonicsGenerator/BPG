from typing import TYPE_CHECKING, Tuple
import numpy as np
from bag.layout.util import transform_point, transform_loc_orient

if TYPE_CHECKING:
    from BPG.bpg_custom_types import dim_type, coord_type, lpp_type, layer_or_lpp_type


class PhotonicPort:
    # TODO:  __slots__ =
    # TODO: Ensure unit mode is rounded properly
    def __init__(self,
                 name: str,
                 center: "coord_type",
                 orientation: str,
                 width: "dim_type",
                 layer: "lpp_type",
                 resolution: float,
                 unit_mode: bool = False,
                 ) -> None:
        """Creates a new PhotonicPort object

        Parameters
        ----------
        name : str
            the name of the port
        center : Tuple[Union[float, int], Union[float, int]]
            the (x, y) point of the port
        orientation : str
            the orientation pointing into the object of the port
        width : Union[float, int]
            the port width
        layer : Tuple[str, str]
            the layer / layer purpose pair on which the port should be drawn
        resolution : float
            the grid resolution
        unit_mode : bool
            True if layout dimensions are specified in resolution units

        Returns
        -------
        """

        self._res = resolution
        if not unit_mode:
            center = (int(round(center[0] / resolution)), int(round(center[1] / resolution)))
            width = int(round(width / resolution))

        self._center_unit = np.array(center)  # type: np.array
        self._name = name

        if not (isinstance(layer, tuple) and (len(layer) == 2) and
                isinstance(layer[0], str) and isinstance(layer[1], str)):
            raise ValueError(f'LPP {layer} into PhotonicPort is not valid. Must be a tuple of 2 strings.')

        self._layer = layer
        self._used = False
        self._width_unit = width
        self._orientation = orientation

    def __repr__(self):
        return "PhotonicPort: name: {}, layer: {}, location: ({}, {})".format(
            self.name, self.layer, self.center[0], self.center[1]
        )

    @property
    def used(self) -> bool:
        """Returns True if port is used"""
        # TODO: Implement?
        return self._used

    @used.setter
    def used(self,
             new_used: bool
             ) -> None:
        self._used = new_used

    @property
    def center(self) -> np.array:
        """Return the center coordinates as np array"""
        return self._center_unit * self._res

    @property
    def center_unit(self) -> np.array:
        """Return the center coordinates as np array in resolution units"""
        return self._center_unit

    @property
    def resolution(self) -> float:
        """Returns the layout resolution of the port object"""
        return self._res

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
        return self._width_unit * self._res

    @property
    def width_unit(self) -> int:
        """Returns the width of the port in layout units"""
        return self._width_unit

    @width.setter
    def width(self, new_width: float) -> None:
        """Sets the port width"""
        self._width_unit = int(round(new_width / self._res))

    @width_unit.setter
    def width_unit(self, new_width: int) -> None:
        """Sets the port width"""
        self._width_unit = new_width

    def width_vec(self,
                  unit_mode: bool = True,
                  normalized: bool = True,
                  ) -> np.array:
        """Returns a normalized vector pointing into the port object

        Parameters
        ----------
        unit_mode : bool
            True to return vector in resolution units
        normalized : bool
            True to normalize the vector. If False, vector magnitude is the port width

        Returns
        -------
        vec : np.array
            a vector whos orientation points into the port and whos magnitude is either 1 or the waveguide port width
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
    def orientation(self) -> str:
        """ Returns the orientation of the port """
        return self._orientation

    def is_horizontal(self) -> bool:
        """Returns True if port orientation is R0 or R180"""
        if self.orientation == 'R0' or self.orientation == 'R180':
            return True
        else:
            return False

    def is_vertical(self) -> bool:
        """Returns True if port orientation is vertical (R90 or R270)"""
        return not self.is_horizontal()

    def transform(self,
                  loc: "coord_type" = (0, 0),
                  orient: str = 'R0',
                  unit_mode: bool= False,
                  ) -> "PhotonicPort":
        """Return a new transformed photonic port

        Parameters
        ----------
        loc : Tuple[Union[float, int], Union[float, int]]
            the x, y coordinate to move the port
        orient : str
            the orientation to rotate the port
        unit_mode : bool
            true if layout dimensions are specified in resolution units

        Returns
        -------
        port : PhotonicPort
            the transformed photonic port object
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
