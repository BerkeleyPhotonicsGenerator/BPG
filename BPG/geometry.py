from decimal import Decimal
from BPG.port import PhotonicPort

from typing import Tuple


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
        return 'CoordBase({})'.format(self.float)

    @property
    def value(self):
        return self._value

    @property
    def unit_mode(self):
        return self.value

    @property
    def float(self):
        """ Returns the rounded floating point number closest to a valid point on the resolution grid """
        return float(self.value * CoordBase.res)

    @property
    def microns(self):
        return self.float

    @property
    def meters(self):
        """ Returns the rounded floating point number in meters closest to a valid point on the resolution grid """
        return float(self.value * CoordBase.res * CoordBase.micron)


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
                      port,  # type: PhotonicPort
                      offset=(0, 0),  # type: Tuple,
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
