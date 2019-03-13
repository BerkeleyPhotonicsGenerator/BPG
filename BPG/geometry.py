from decimal import Decimal
import numpy as np
import math
import warnings
import logging

from bag.layout.util import BBox

from typing import TYPE_CHECKING, Tuple, Union, Optional
if TYPE_CHECKING:
    from BPG.bpg_custom_types import coord_type
    from BPG.port import PhotonicPort


class CoordBase:
    """
    A class representing the basic unit of measurement for all objects in BPG.

    All user-facing values are assumed to be floating point numbers in units of microns. BAG internal functions
    assume that we receive 'unit-mode' numbers, which are integers in units of nanometers. Both formats are supported.
    """

    res = Decimal('1e-3')  # resolution for all numbers in BPG is 1nm
    micron = Decimal('1e-6')  # size of 1 micron in meters
    __slots__ = ['_value']

    def __new__(cls, value, *args, **kwargs):
        """ Assumes a floating point input value in microns, stores an internal integer representation on grid """
        self = object.__new__(cls)  # Create the immutable instance
        self._value = round(Decimal(str(value)) / CoordBase.res)
        return self

    def __repr__(self):
        return f'CoordBase({self.float})'

    @property
    def value(self):
        return self._value

    @property
    def unit_mode(self):
        return self._value

    @property
    def float(self):
        """ Returns the rounded floating point number closest to a valid point on the resolution grid """
        return float(self._value * CoordBase.res)

    @property
    def microns(self):
        return self.float

    @property
    def meters(self):
        """ Returns the rounded floating point number in meters closest to a valid point on the resolution grid """
        return float(self._value * CoordBase.res * CoordBase.micron)


class XY:
    """
    A class representing a single point on the XY plane
    """

    __slots__ = ['_x', '_y']

    def __new__(cls, xy, *args, **kwargs):
        """ Assumes a floating point input value in microns for each dimension """
        self = object.__new__(cls)  # Create the immutable instance
        self._x = CoordBase(xy[0])
        self._y = CoordBase(xy[1])
        return self

    @property
    def x(self):
        return self._x.unit_mode

    @property
    def y(self):
        return self._y.unit_mode

    @property
    def xy(self):
        return [self.x, self.y]

    @property
    def xy_float(self):
        return [self._x.float, self._y.float]

    @property
    def x_float(self):
        return self._x.float

    @property
    def y_float(self):
        return self._y.float

    @property
    def xy_meters(self):
        return [self._x.meters, self._y.meters]

    @property
    def x_meters(self):
        return self._x.meters

    @property
    def y_meters(self):
        return self._y.meters


class XYZ:
    """
    A class representing a single point on the XYZ space
    """

    __slots__ = ['_x', '_y', '_z']

    def __new__(cls, xyz, *args, **kwargs):
        """ Assumes a floating point input value in microns for each dimension """
        self = object.__new__(cls)  # Create the immutable instance
        self._x = CoordBase(xyz[0])
        self._y = CoordBase(xyz[1])
        self._z = CoordBase(xyz[2])
        return self

    @property
    def x(self):
        return self._x.unit_mode

    @property
    def y(self):
        return self._y.unit_mode

    @property
    def z(self):
        return self._z.unit_mode

    @property
    def xyz(self):
        return [self.x, self.y, self.z]

    @property
    def x_float(self):
        return self._x.float

    @property
    def y_float(self):
        return self._y.float

    @property
    def z_float(self):
        return self._z.float

    @property
    def xyz_float(self):
        return [self._x.float, self._y.float, self._z.float]

    @property
    def x_meters(self):
        return self._x.meters

    @property
    def y_meters(self):
        return self._y.meters

    @property
    def z_meters(self):
        return self._z.meters

    @property
    def xyz_meters(self):
        return [self._x.meters, self._y.meters, self._z.meters]


class Plane:
    """
    A class representing a plane that is orthogonal to one of the cardinal axes

    TODO: Implement this class
    """
    def __init__(self):
        pass


class Box:
    """
    A class representing a 3D rectangle
    """
    def __init__(self):
        self.geometry = {
            'x': {'center': 0.0, 'span': 0.0},
            'y': {'center': 0.0, 'span': 0.0},
            'z': {'center': 0.0, 'span': 0.0}
        }

    ''' Configuration Methods '''
    ''' USE THESE METHODS TO SETUP THE SIMULATION '''

    def move_by(self, dx, dy, unit_mode=False):
        if unit_mode is True:
            raise ValueError('Boxes dont currently support unit mode movement')

        self.geometry['x']['center'] += dx
        self.geometry['y']['center'] += dy

    def set_center_span(self, dim, center, span):
        """
        Sets the center and span of a given geometry dimension

        Parameters
        ----------
        dim : str
            'x', 'y', or 'z' for the corresponding dimension
        center : float
            coordinate location of the center of the geometry
        span : float
            length of the geometry along the dimension
        """

        self.geometry[dim]['center'] = center
        self.geometry[dim]['span'] = span

    def set_span(self, dim, span):
        """
        Sets the span of a given geometry dimension

        Parameters
        ----------
        dim : str
            'x', 'y', or 'z' for the corresponding dimension
        span : float
            length of the geometry along the dimension
        """
        self.geometry[dim]['span'] = span

    def align_to_port(self,
                      port: "PhotonicPort",
                      offset: Tuple = (0, 0),
                      ):
        """
        Moves the center of the simulation object to align to the provided photonic port

        Parameters
        ----------
        port : PhotonicPort
            Photonic port for the simulation object to be aligned to
        offset : Tuple
            (x, y) offset relative to the port location
        """
        center = port.center_unit
        self.geometry['x']['center'] = center[0] + offset[0]
        self.geometry['y']['center'] = center[1] + offset[1]


class BBoxMut(BBox):
    """
    A special bounding box that mutates is own properties instead of returning a new object.
    This is useful when performing a large number of transformations of the same boundary.
    """

    def merge(self, bbox: Union[BBox, 'BBoxMut']) -> 'BBoxMut':
        """
        Returns a new bounding box that's the union of this bounding box and the given one.
        BBoxMut is often initialized with 0 area, so in this case a merge should cause the
        BBoxMut to inherit the same size as the given BBox.

        Parameters
        ----------
        bbox : bag.layout.util.BBox
            the bounding box to merge with.

        Returns
        -------
        total : bag.layout.util.BBox
            the merged bounding box.
        """
        if not self.is_physical():
            self._left_unit = bbox._left_unit
            self._right_unit = bbox._right_unit
            self._bot_unit = bbox._bot_unit
            self._top_unit = bbox._top_unit
            return self
        elif not bbox.is_valid():
            return self

        self._left_unit = min(self._left_unit, bbox._left_unit)
        self._right_unit = max(self._right_unit, bbox._right_unit)
        self._bot_unit = min(self._bot_unit, bbox._bot_unit)
        self._top_unit = max(self._top_unit, bbox._top_unit)
        return self


class Transformable2D:
    """
    This class represents a 2D position on a Cartesian grid and angle. Contains several convenience methods for
    supporting quick translation and rotation of the point.
    """

    # small deviation in angle assumed to be cardinal
    # An error of 1.0e-9 radians is sufficient to have <1nm snapping error at 30mm distance
    SMALL_ANGLE_TOLERANCE = 1.0e-9

    OrientationsNoFlip = ['R0', 'R90', 'R180', 'R270']
    OrientationsWithFlip = ['MX', 'MXR90', 'MY', 'MYR90']  # Mirror first, then rotate if applicable
    OrientationsAll = OrientationsNoFlip + OrientationsWithFlip

    def __init__(self,
                 center: "coord_type",
                 resolution: float,
                 orientation: str = 'R0',
                 angle: float = 0.0,
                 mirrored: bool = False,
                 force_cardinal: bool = False,
                 unit_mode: bool = False,
                 ):
        """
        Creates a new Transformable object following the position-orientation convention

        Parameters
        ----------
        center : Tuple[Union[float, int], Union[float, int]]
            the (x, y) point of the port
        resolution : float
            the grid resolution
        orientation : str
            the orientation string of the port.
        angle : float
            angle in radians [0, pi/2) representing the angle at which this port is placed
        mirrored : bool
            If true, specifies a reflection across the x-axis (y-->-y) before any rotation
            This operation (coupled with the orientation) more generally indicates that a block has been mirrored.
        force_cardinal : bool
            Tracks whether the angle is cardinal and should be snapped to 90deg where applicable
        unit_mode : bool
            True if layout dimensions are specified in resolution units
        """
        # Initialize variables
        self._resolution = resolution
        self._mod_angle = 0.0
        if unit_mode:
            self._center_unit = np.array([int(round(center[0])), int(round(center[1]))])
        else:
            self._center_unit = np.array([int(round(center[0] / resolution)), int(round(center[1] / resolution))])

        # Convert the input angle+orientation to angle+invert representation
        angle, temp_invert_y = self.orient2angle(orient=orientation, mod_angle=angle)
        mirrored = mirrored ^ temp_invert_y

        # Store information internally in mod_angle and cadence orientation format
        orient, mod_angle, is_cardinal, _ = self.angle2orient(angle, mirrored)
        self._orient = orient
        self.mod_angle = mod_angle  # Set using setter to ensure mod_angle < pi/2

        # Handle the case where the object may or may not be cardinal
        if force_cardinal:
            self._force_cardinal = True
            if not is_cardinal:
                warnings.warn(f'Transformable2D initialized as is_cardinal=True, but angle seems non-cardinal. \n' 
                              f'mod_angle={mod_angle}')
        else:
            self._force_cardinal = False

    @property
    def center(self) -> np.array:
        """ Return the center coordinates as np array """
        return self._center_unit * self._resolution

    @property
    def center_unit(self) -> np.array:
        """Return the center coordinates as np array in resolution units"""
        return self._center_unit

    @center.setter
    def center(self,
               center: Tuple[float, float]
               ) -> None:
        """ This setter is used if the input is not in unit_mode """
        self._center_unit = np.array([int(round(center[0] / self._resolution)),
                                      int(round(center[1] / self._resolution))])

    @center_unit.setter
    def center_unit(self,
                    center: Tuple[int, int]
                    ):
        """ This setter is used if the input is already in unit_mode """
        self._center_unit = np.array([int(round(center[0])), int(round(center[1]))])

    @property
    def x_unit(self) -> int:
        """Return the x coordinate of the center in resolution units"""
        return int(self._center_unit[0])

    @property
    def x(self) -> float:
        """Return the x coordinate of the center"""
        return float(self._center_unit[0] * self._resolution)

    @property
    def y_unit(self) -> int:
        """Return the y coordinate of the center in resolution units"""
        return int(self._center_unit[1])

    @property
    def y(self) -> float:
        """Return the y coordinate of the center"""
        return float(self._center_unit[1] * self._resolution)

    @property
    def mod_angle(self) -> float:
        """ Angle between [0, pi/2) of the object """
        return self._mod_angle

    @mod_angle.setter
    def mod_angle(self, value: float) -> None:
        """ Check that the provided value is mod pi/2 """
        if value > math.pi / 2 or value < 0:
            raise ValueError(f'{value} is not [0, pi/2), cannot be used as a mod_angle')
        else:
            self._mod_angle = value

    @property
    def angle(self) -> float:
        """ Angle between [0, 2pi) of the object """
        temp_angle, _ = self.orient2angle(self._orient, self._mod_angle)
        return temp_angle

    @property
    def mirrored(self) -> bool:
        """ If true, the object has been mirrored across the x-axis """
        _, temp_mirrored = self.orient2angle(self._orient, self._mod_angle)
        return temp_mirrored

    @property
    def orientation(self) -> str:
        """ Current Cadence-style orientation repr """
        return self._orient

    @orientation.setter
    def orientation(self, val) -> None:
        """
        Orientation can be directly set, although this is a bit dangerous since angle will change when doing this
        """
        if val not in Transformable2D.OrientationsAll:
            raise ValueError('Unsupported orientation: %s' % val)
        self._orient = val

    @property
    def is_cardinal(self) -> bool:
        """ If true, the object is pointing in one of the cardinal directions """
        return self.is_horizontal or self.is_vertical

    @property
    def is_horizontal(self) -> bool:
        """ Returns True if angle is 0, 180deg, etc. Sin(theta) = theta approximation """
        return abs(self.unit_vec[1]) <= Transformable2D.SMALL_ANGLE_TOLERANCE

    @property
    def is_vertical(self) -> bool:
        """ Returns True if angle is 90deg, 270deg, etc. Sin(theta) = theta approximation """
        return abs(self.unit_vec[0]) <= Transformable2D.SMALL_ANGLE_TOLERANCE

    @property
    def resolution(self) -> float:
        """Returns the layout resolution of the port object"""
        return self._resolution

    @property
    def unit_vec(self) -> np.ndarray:
        """ Returns a unit vector pointing in the direction of the angle """
        # convert angle to unit-vector, including snap-to-90deg when is_cardinal=True to avoid little errors
        return np.array([np.cos(self.angle), np.sin(self.angle)])

    ''' Coordinate Manipulation Methods '''

    def rotate(self,
               rotation: float,
               mirror: bool,
               force_cardinal: Optional[bool] = None,
               ) -> np.array:
        """
        Perform a rotation relative to the current position and angle of the Transformable2D object
        First mirror, then rotate, to be consistent with Cadence orient + transform

        Returns the new position after the rotation is performed.

        Parameters
        ----------
        rotation : float
            angle in radians to rotate this point
        mirror : bool
            if true, the y-coordinate is flipped to perform a mirror across the x-axis
        force_cardinal : Optional[bool]
            If True and the result of the rotation is not cardinal, raise a runtime error.
            If False, do not care about cardinality of result.
            If left unset, use the Transformable2D's current force_cardinal value.

        Returns
        -------
        new_center : np.array
            new position of the center in unit_mode
        """
        # Flip the current inversion state if invertY is true
        if mirror is True:
            y_inv = -1
            new_mirrored_state = not self.mirrored
        else:
            y_inv = 1
            new_mirrored_state = self.mirrored

        # Mirror (if needed) and rotate by the provided angle
        new_center_x = math.cos(rotation) * self._center_unit[0] - math.sin(rotation) * self._center_unit[1] * y_inv
        new_center_y = math.sin(rotation) * self._center_unit[0] + math.cos(rotation) * self._center_unit[1] * y_inv
        new_center_unit = np.array([new_center_x, new_center_y])

        # Compute the new angle
        new_angle = y_inv * self.angle + rotation

        # Convert to mod_angle and orient
        orient, mod_angle, seems_cardinal, _ = self.angle2orient(new_angle, new_mirrored_state)

        # Store new values
        self.orientation = orient
        self.mod_angle = mod_angle
        self._center_unit = new_center_unit

        if force_cardinal is None:
            force_cardinal = self._force_cardinal

        if force_cardinal:
            # Transformation is explicitly cardinal, so do not change is_cardinal flag
            if np.abs(np.cos(rotation) * np.sin(rotation)) > Transformable2D.SMALL_ANGLE_TOLERANCE:
                raise RuntimeError('rotation specified as cardinal, but angle is not a multiple of pi/2')

        return np.array([int(round(new_center_x)), int(round(new_center_y))])

    def move_by(self,
                translation: Tuple[int, int],
                unit_mode: bool = False,
                ) -> "Transformable2D":
        """
        Returns the new position after the translation is performed

        Parameters
        ----------
        translation : Tuple[int, int]
            (x, y) coordinates of the translation vector to be applied to the current center. Assumed to be in unit_mode
        unit_mode : bool
            if true, translation tuple is assumed to be in unit_mode

        Returns
        -------
        new_center : np.array
            new position of the center in unit_mode
        """
        if not unit_mode:
            translation = np.round(
                np.array([translation[0] / self.resolution, translation[1] / self.resolution])
            ).astype(int)
        else:
            translation = np.round(np.round(translation)).astype(int)
        self._center_unit += translation

        return self

    def transform(self,
                  loc: "coord_type" = (0, 0),
                  orient: str = 'R0',
                  unit_mode: bool = False,
                  ) -> "Transformable2D":
        """
        Sets the current center and orientation to the provided values.
        This method does not accept arbitrary angles, but is limited to just the orientation vector.

        Parameters
        ----------
        loc : Tuple[]
            Location at which the center should be placed
        orient : str
            Orientation at which the Transformable2D should be set
        unit_mode : bool
            True if loc is provided in resolution units, False if loc is provided in layout units.
        """
        if not unit_mode:
            self._center_unit = np.round(
                np.array([loc[0] / self.resolution, loc[1] / self.resolution])
            ).astype(int)
        else:
            self._center_unit = np.round(np.round(loc)).astype(int)

        self._orient = orient

        return self

    def mirror_rotate_translate(self,
                                translation: "coord_type" = (0.0, 0.0),
                                rotation: float = 0.0,
                                mirror: bool = False,
                                force_cardinal: bool = False,
                                unit_mode: bool = False,
                                ) -> "Transformable2D":
        """
        Perform a rotation and a translation relative to the current position and angle of the Transformable2D object
        First mirror, then rotate, then translate to be consistent with Cadence orient + transform

        Parameters
        ----------
        translation : coord_type
            displacement vector that the current Transformable2D object will be translated by
        rotation : float
            angle in radians to rotate the current point by
        mirror : bool
            if true, mirror the block
        force_cardinal : bool
            if true, restrict to cardinal rotations
        unit_mode : bool
            if true, translation tuple is assumed to be in unit_mode
        """
        # Mirror and rotate
        self.rotate(
            rotation=rotation,
            mirror=mirror,
            force_cardinal=force_cardinal
        )

        # Translate
        self.move_by(
            translation=translation,
            unit_mode=unit_mode
        )

        return self

    @staticmethod
    def angle2orient(angle: float,
                     mirrored: bool,
                     ) -> Tuple[str, float, bool, int]:
        """
        Converts an unbounded floating-point angle and mirrored into an equivalent
        bounded [0, pi/2) angle rotation (mod_angle) and cadence orientation string.

        Parameters
        ----------
        angle : float
            The unbounded angle (radians) of the orientation
        mirrored : bool
            True if the orientation is mirrored.

        Returns
        -------
        out_tuple : Tuple[str, float, bool, int]
            (orient, mod_angle, is_cardinal, num_90deg)
            orient : the Cadence orientation string
            mod_angle : the [0, pi/2) bounded angle
            is_cardinal : True if the angle is within error tolerance of being cardinal
            num_90deg : The number of 90 degree rotations (rounded down) that fit into the angle.
        """
        if mirrored:
            num_90deg = -int(np.floor(-angle / (np.pi / 2)))  
            mod_angle = -(angle - num_90deg * (np.pi / 2))
        else:
            num_90deg = int(np.floor(angle / (np.pi / 2)))
            mod_angle = angle - num_90deg * (np.pi / 2)

        if np.abs(mod_angle) < Transformable2D.SMALL_ANGLE_TOLERANCE:
            mod_angle = 0
            is_cardinal = True
            num_90deg = int(np.round(angle / (np.pi / 2)))
        elif np.abs( mod_angle - np.pi / 2) < Transformable2D.SMALL_ANGLE_TOLERANCE:
            mod_angle = 0
            num_90deg = int(np.round(angle / (np.pi / 2)))
            is_cardinal = True
        elif (mod_angle >= np.pi / 2) or (mod_angle < 0):
            raise RuntimeError(f'mod_angle: {mod_angle} should be >=0 and < pi/2')
        else:
            is_cardinal = False
        index = (num_90deg % 4) + mirrored * 4
        orient = Transformable2D.OrientationsAll[index]
        return orient, mod_angle, is_cardinal, num_90deg

    @staticmethod
    def orient2angle(orient: str,
                     mod_angle: float,
                     ) -> Tuple[float, bool]:
        """
        Converts a small-angle [0, pi/2) rotation mod_angle and Cadence orientation vector into
        an equivalent [0, 2pi) angle and mirrored representation.

        Parameters
        ----------
        orient : str
            A Cadence format orientation string ('R0', 'R90', 'MX', etc).
        mod_angle : float
            The small angle [0, pi/2) rotation

        Returns
        -------
        out_tuple : Tuple[float, bool]
            (angle, mirrored)
            angle : the [0, 2pi) equivalent angle
            mirrored : True if the orientation string indicated a mirroring orientation, False if it did not.

        """
        if orient not in Transformable2D.OrientationsAll:
            raise ValueError(f'orient {orient} is not a permitted orientation string.')

        if orient in Transformable2D.OrientationsNoFlip:  # ['R0','R90','R180','R270']):
            rotate_by = Transformable2D.OrientationsNoFlip.index(orient) * np.pi / 2
            mirrored = False
            angle = rotate_by + mod_angle
        else:  # Transformable2D.OrientationsWithFlip  ['MX','MXR90','MY','MYR90']):
            # The list above is MX followed by   ['R0','R90','R180','R270'], so
            rotate_by = Transformable2D.OrientationsWithFlip.index(orient) * np.pi / 2
            mirrored = True
            angle = rotate_by - mod_angle

        angle = angle % (2 * np.pi)
        return angle, mirrored
