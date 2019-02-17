# -*- coding: utf-8 -*-

"""This module defines various layout objects one can add and manipulate in a template.
"""
import gdspy
import numpy as np
import sys
import math
import logging
from copy import deepcopy

from bag.layout.objects import Arrayable, Rect, Path, PathCollection, TLineBus, Polygon, Blockage, Boundary, \
    ViaInfo, Via, PinInfo, Instance, InstanceInfo, Figure
from bag.layout.routing import RoutingGrid
from bag.layout.template import TemplateBase
import bag.io
from bag.layout.util import transform_point, BBox, transform_table

from BPG.geometry import Transformable2D
from BPG.compiler.point_operations import coords_cleanup, create_polygon_from_path_and_width

from typing import TYPE_CHECKING, Union, List, Tuple, Optional, Dict, Any
from BPG.bpg_custom_types import dim_type, coord_type, layer_or_lpp_type

if TYPE_CHECKING:
    from BPG.template import PhotonicTemplateBase
    from BPG.port import PhotonicPort
    from bag.layout.objects import Figure

# Load logger
logger = logging.getLogger(__name__)


class PhotonicInstanceInfo(InstanceInfo):
    """ A dictionary that represents a layout instance. """
    param_list = ['lib', 'cell', 'view', 'name', 'loc', 'orient', 'num_rows',
                  'num_cols', 'sp_rows', 'sp_cols', 'master_key']

    def __init__(self, res, change_orient=True, **kwargs):
        InstanceInfo.__init__(self, res, change_orient, **kwargs)

        if 'master_key' in kwargs:
            self['master_key'] = kwargs['master_key']

    @property
    def master_key(self) -> Tuple:
        return self['master_key']

    def copy(self):
        """Override copy method of InstanceInfo to return a PhotonicInstanceInfo instead."""
        return PhotonicInstanceInfo(self._resolution, change_orient=False, **self)

    def content(self):
        kv_iter = ((key, self[key]) for key in self.param_list)
        return dict(kv_iter)


class PhotonicInstance(Instance):
    """
    A photonic layout instance, with optional arraying parameters. This class adds the ability
    to read

    Parameters
    ----------
    parent_grid : RoutingGrid
        the parent RoutingGrid object.
    lib_name : str
        the layout library name.
    master : TemplateBase
        the master template of this instance.
    loc : Tuple[Union[float, int], Union[float, int]]
        the origin of this instance.
    orient : str
        the orientation of this instance.
    name : Optional[str]
        name of this instance.
    nx : int
        number of columns.
    ny : int
        number of rows.
    spx : Union[float, int]
        column pitch.
    spy : Union[float, int]
        row pitch.
    unit_mode : bool
        True if layout dimensions are specified in resolution units.
    """

    def __init__(self,
                 parent_grid: RoutingGrid,
                 lib_name: str,
                 master,
                 loc: coord_type,
                 orient: str,
                 name: str = None,
                 nx: int = 1,
                 ny: int = 1,
                 spx: int = 0,
                 spy: int = 0,
                 unit_mode: bool = False,
                 angle: float = 0,
                 mirrored: bool = False,
                 ) -> None:
        Instance.__init__(self, parent_grid, lib_name, master, loc, orient,
                          name, nx, ny, spx, spy, unit_mode)

        self._photonic_port_list: Dict[str, "PhotonicPort"] = {}

        self._origin = Transformable2D(
            center=loc,
            resolution=parent_grid.resolution,
            orientation=orient,
            angle=0,
            mirrored=False,
            is_cardinal=False,  # TODO
            unit_mode=unit_mode,
        )
        self._import_photonic_ports()

        # If the angle of this instance is not 0, rotate the instance
        # TODO: is_cardinal / close enough to cardinal?
        if angle != 0.0:
            logging.debug(f'PhotonicInstance with master {master} is at angle {angle}')
            self.rotate(
                loc=self.location_unit,
                angle=self.master.angle + angle,
                mirror=mirrored,
                unit_mode=unit_mode
            )

    def __repr__(self):
        return f'PhotonicInstance(master={self.master}, name={self._inst_name}, loc={self.location}, ' \
            f'angle={np.rad2deg(self.angle)}, orientation={self.orientation}'

    def __str__(self):
        return self.__repr__()

    def __getitem__(self, item: str):
        """ Allow dictionary syntax to grab photonic ports """
        return self.get_photonic_port(name=item)

    @property
    def content(self) -> Dict:
        """A dictionary representation of this instance."""
        return PhotonicInstanceInfo(self.resolution,
                                    lib=self._lib_name,
                                    cell=self.master.cell_name,
                                    view='layout',
                                    name=self._inst_name,
                                    loc=list(self.location),
                                    orient=self.orientation,
                                    num_rows=self.ny,
                                    num_cols=self.nx,
                                    sp_rows=self.spy,
                                    sp_cols=self.spx,
                                    master_key=self.master.key
                                    )

    @property
    def master(self) -> "PhotonicTemplateBase":
        """ The master template of this instance. """
        return self._master

    @property
    def orientation(self) -> str:
        """ Return the orientation string of this instance"""
        return self._origin.orientation

    @orientation.setter
    def orientation(self, val) -> None:
        logging.warning('PhotonicInstance does not allow orientation to be set directly')

    @property
    def location(self) -> coord_type:
        return self._origin.center

    @location.setter
    def location(self, val) -> None:
        logging.warning('PhotonicInstance does not allow location to be changed directly, use transform()')

    @property
    def location_unit(self) -> coord_type:
        return self._origin.center_unit

    @location_unit.setter
    def location_unit(self, val) -> None:
        logging.warning('PhotonicInstance does not allow location to be changed directly, use transform()')

    @property
    def angle(self) -> float:
        return self._origin.angle

    @property
    def mod_angle(self) -> float:
        return self._origin.mod_angle

    @property
    def mirrored(self) -> bool:
        return self._origin.mirrored

    def _import_photonic_ports(self) -> None:
        """
        Takes all ports from the provided master and adds them to this instance. Transformations are
        performed to match the current orientation and location.
        """
        for port_name in self._master.photonic_ports_names_iter():
            port_copy: "PhotonicPort" = deepcopy(self._master.get_photonic_port(port_name))
            self._photonic_port_list[port_name] = port_copy.mirror_rotate_translate(
                translation=self.location_unit,
                rotation=self.angle,
                mirror=self.mirrored,
                is_cardinal=False,  # TODO,
                unit_mode=True
            )

    def get_all_photonic_ports(self) -> Dict[str, "PhotonicPort"]:
        return self._photonic_port_list

    def get_photonic_port(self,
                          name: str,
                          row: int = 0,
                          col: int = 0,
                          ) -> "PhotonicPort":
        """
        Returns the photonic port object associated with the provided port name

        Parameters
        ----------
        name : str
            name of the port to be returned
        row : int
            row in the array of instances to be accessed
        col : int
            column in the array of instances to be accessed

        Returns
        -------
        port : PhotonicPort
            photonic port object associated with the provided name
        """
        # TODO: Confirm that this works for arrayable instances
        return self._photonic_port_list[name]

    def get_bound_box_of(self,
                         row: int = 0,
                         col: int = 0,
                         ) -> BBox:
        """Returns the bounding box of an instance in this mosaic."""
        dx, dy = self.get_item_location(row=row, col=col, unit_mode=True)
        xshift, yshift = self._loc_unit
        xshift += dx
        yshift += dy
        return self._master.bound_box.transform((xshift, yshift), self.orientation, unit_mode=True)

    def move_by(self,
                dx: dim_type = 0,
                dy: dim_type = 0,
                unit_mode: bool = False
                ) -> None:
        """
        Move this instance by the given amount. This movement is relative to the instances current location.

        Parameters
        ----------
        dx : dim_type
            the X shift.
        dy : dim_type
            the Y shift.
        unit_mode : bool
            True if shifts are given in resolution units
        """
        if not unit_mode:
            dx, dy = int(round(dx / self.resolution)), int(round(dy / self.resolution))

        # Move the origin
        self._origin.move_by(translation=(dx, dy), unit_mode=True)
        # import ports with the new locations
        self._import_photonic_ports()

    def transform(self,
                  loc: coord_type = (0, 0),
                  orient: str = 'R0',
                  unit_mode: bool = False,
                  copy: bool = False
                  ) -> "PhotonicInstance":
        """
        Moves the Instance to the provided location and orientation values.
        This transformation method cannot perform anyAngle rotation!
        Can perform the transformation on a copy of the Instance and return it.

        Note all location and orientation transformations are performed relative to the
        master's origin and angle, not the current instance's origin and angle.

        Parameters
        ----------
        loc : tuple
            (x, y) coordinates where the Instance origin should be placed
        orient : str
            represents the new orientation of the Instance
        unit_mode : bool
            If true, loc should be an integer representing multiples of the unit_size
        copy : bool
            If true, this method performs a transformation on a copy of the instance instead

        Returns
        -------
        instance : PhotonicInstance
            The transformed instance. If copy is true, this is a newly created instance. If false, returns itself
        """
        logging.debug(f'CALLING TRANSFORM ON {self.master.__class__.__name__}')
        if not unit_mode:
            loc = int(round(loc[0] / self.resolution)), int(round(loc[1] / self.resolution))

        if not copy:
            # Modify the origin's location and orientation
            self._origin.center_unit = loc
            self._origin.orientation = orient

            # Now that origin is correctly placed, regenerate the ports accordingly
            self._import_photonic_ports()
            return self

        else:
            return PhotonicInstance(parent_grid=self._parent_grid,
                                    lib_name=self._lib_name,
                                    master=self.master,
                                    loc=self.location_unit,
                                    orient=self.orientation,
                                    name=self._inst_name,
                                    nx=self.nx, ny=self.ny,
                                    spx=self.spx_unit, spy=self.spy_unit,
                                    unit_mode=True)

    def rotate(self,
               loc: "coord_type" = (0, 0),
               angle: float = 0.0,
               mirror: bool = False,
               unit_mode=False
               ) -> None:
        """
        This method regenerates the instance's master to rotate the shapes and ports given an angle. The provided angle
        and loc values are all relative to R0 and (0, 0) of the master placing this instance
        Parameters
        ----------
        loc : coord_type
            (x, y) location about which all rotation is performed
        angle : float
            angle in radians of the rotation to be performed
        mirror : bool
            if true, flip the instance
        unit_mode : bool
            if True, the provided coordinates are assumed to be in unit-mode
        """
        if not unit_mode:
            loc = int(round(loc[0] / self.resolution)), int(round(loc[1] / self.resolution))

        logging.debug(f'Calling rotate loc={loc}, angle={angle}')
        logging.debug(f'Origin is {self._origin}')
        # Rotate and translate the origin of the instance
        self._origin.mirror_rotate_translate(
            translation=loc,
            rotation=angle,
            mirror=mirror,
            is_cardinal=False,  # TODO
            unit_mode=True
        )
        logging.debug(f'Origin is {self._origin}')

        # Regenerate the master based on the new origin
        self.new_master_with(angle=self.mod_angle)

        # Re-extract the port locations
        self._import_photonic_ports()


class PhotonicRound(Arrayable):
    """A layout round object, with optional arraying parameters.

    Parameters
    ----------
    layer : string or (string, string)
        the layer name, or a tuple of layer name and purpose name.
        If pupose name not given, defaults to 'drawing'.
    rout :
    rin :
    theta0 :
    theta1 :

    nx : int
        number of columns.
    ny : int
        number of rows.
    spx : float
        column pitch.
    spy : float
        row pitch.
    unit_mode : bool
        True if layout dimensions are specified in resolution units.
    """

    def __init__(self,
                 layer: layer_or_lpp_type,
                 resolution: float,
                 rout: dim_type,
                 center: coord_type = (0, 0),
                 rin: dim_type = 0,
                 theta0: dim_type = 0,
                 theta1: dim_type = 360,
                 nx: int = 1,
                 ny: int = 1,
                 spx: dim_type = 0,
                 spy: dim_type = 0,
                 unit_mode: bool = False,
                 ):
        # python 2/3 compatibility: convert raw bytes to string.
        layer = bag.io.fix_string(layer)
        if isinstance(layer, str):
            layer = (layer, 'phot')
        self._layer = layer[0], layer[1]

        self._res = resolution

        if not unit_mode:
            self._rout_unit = int(round(rout / resolution))
            self._rin_unit = int(round(rin / resolution))
            self._center_unit = (int(round(center[0] / resolution)), int(round(center[1] / resolution)))
        else:
            self._rout_unit = int(round(rout))
            self._rin_unit = int(round(rin))
            self._center_unit = (int(round(center[0])), int(round(center[1])))

        self._theta0 = theta0
        self._theta1 = theta1

        Arrayable.__init__(self, self._res, nx=nx, ny=ny,
                           spx=spx, spy=spy, unit_mode=unit_mode)

    @classmethod
    def from_content(cls, content, resolution):
        return PhotonicRound(
            layer=content['layer'],
            rout=content['rout'],
            rin=content['rin'],
            theta0=content['theta0'],
            theta1=content['theta1'],
            center=content['center'],
            nx=content.get('arr_nx', 1),
            ny=content.get('arr_ny', 1),
            spx=content.get('arr_spx', 0),
            spy=content.get('arr_spy', 0),
            unit_mode=False,
            resolution=resolution
        )

    @property
    def rout(self):
        """The outer radius in layout units"""
        return self._rout_unit * self._res

    @property
    def rout_unit(self):
        """The outer radius in resolution units"""
        return self._rout_unit

    @rout.setter
    def rout(self,
             val: dim_type,
             ):
        """Sets the outer radius in layout units"""
        self._rout_unit = int(round(val / self._res))

    @rout_unit.setter
    def rout_unit(self,
                  val: int,
                  ):
        """Sets the outer radius in resolution units"""
        self._rout_unit = int(round(val))

    @property
    def center(self):
        """The center in layout units"""
        return self._center_unit[0] * self._res, self._center_unit[1] * self._res

    @property
    def center_unit(self):
        """The center in resolution units"""
        return self._center_unit

    @center.setter
    def center(self,
               val: coord_type,
               ):
        """Sets the center in layout units"""
        self._center_unit = (int(round(val[0] / self._res)), int(round(val[1] / self._res)))

    @center_unit.setter
    def center_unit(self,
                    val: Tuple[int, int],
                    ):
        """Sets the center in resolution units"""
        self._center_unit = (int(round(val[0])), int(round(val[1])))

    @property
    def rin(self):
        """The inner radius in layout units"""
        return self._rin_unit * self._res

    @property
    def rin_unit(self):
        """The inner radius in resolution units"""
        return self._rin_unit

    @rin.setter
    def rin(self,
            val: dim_type,
            ):
        """Sets the inner radius in layout units"""
        self._rin_unit = int(round(val / self._res))

    @rin_unit.setter
    def rin_unit(self,
                 val: int,
                 ):
        """Sets the inner radius in resolution units"""
        self._rin_unit = int(round(val))

    @property
    def theta0(self):
        """The starting angle, in degrees"""
        return self._theta0

    @theta0.setter
    def theta0(self,
               val: dim_type,
               ):
        """Sets the start angle in degrees"""
        self._theta0 = val

    @property
    def theta1(self):
        """The ending angle, in degrees"""
        return self._theta1

    @theta1.setter
    def theta1(self,
               val: dim_type,
               ):
        """Sets the start angle in degrees"""
        self._theta1 = val

    @property
    def layer(self):
        """The rectangle (layer, purpose) pair."""
        return self._layer

    @layer.setter
    def layer(self, val):
        """Sets the rectangle layer."""
        self.check_destroyed()
        # python 2/3 compatibility: convert raw bytes to string.
        val = bag.io.fix_string(val)
        if isinstance(val, str):
            val = (val, 'drawing')
        self._layer = val[0], val[1]
        print("WARNING: USING THIS BREAKS POWER FILL ALGORITHM.")

    @property
    def bound_box(self) -> BBox:
        return BBox(
            left=self.center_unit[0] - self.rout_unit,
            bottom=self.center_unit[1] - self.rout_unit,
            right=self.center_unit[0] + self.rout_unit,
            top=self.center_unit[1] + self.rout_unit,
            resolution=self._res,
            unit_mode=True
        )

    @property
    def content(self):
        """A dictionary representation of this rectangle."""
        content = dict(layer=list(self.layer),
                       rout=self.rout,
                       rin=self.rin,
                       theta0=self.theta0,
                       theta1=self.theta1,
                       center=self.center,
                       )
        if self.nx > 1 or self.ny > 1:
            content['arr_nx'] = self.nx
            content['arr_ny'] = self.ny
            content['arr_spx'] = self.spx
            content['arr_spy'] = self.spy

        return content

    def move_by(self,
                dx: dim_type = 0,
                dy: dim_type = 0,
                unit_mode: bool = False,
                ):
        """Moves the round object"""
        if unit_mode:
            self.center_unit = (self.center_unit[0] + int(round(dx)), self.center_unit[1] + int(round(dy)))
        else:
            self.center_unit = (
                self.center_unit[0] + int(round(dx / self._res)),
                self.center_unit[1] + int(round(dy / self._res))
            )

    def transform(self,
                  loc: coord_type = (0, 0),
                  orient: str = 'R0',
                  unit_mode: bool = False,
                  copy: bool = False,
                  ) -> Optional["PhotonicRound"]:
        """Transform this figure."""

        if not unit_mode:
            loc = int(round(loc[0] / self._res)), int(round(loc[1] / self._res))

        new_center_unit = transform_point(self.center_unit[0], self.center_unit[1], loc=loc, orient=orient)

        if orient == 'R0':
            new_theta0 = self.theta0
            new_theta1 = self.theta1
        elif orient == 'R90':
            new_theta0 = self.theta0 + 90
            new_theta1 = self.theta1 + 90
        elif orient == 'R180':
            new_theta0 = self.theta0 + 180
            new_theta1 = self.theta1 + 180
        elif orient == 'R270':
            new_theta0 = self.theta0 + 270
            new_theta1 = self.theta1 + 270
        elif orient == 'MX':
            new_theta0 = -1 * self.theta1
            new_theta1 = -1 * self.theta0
        elif orient == 'MY':
            new_theta0 = 180 - self.theta1
            new_theta1 = 180 - self.theta0
        elif orient == 'MXR90':
            # MX, then R90
            new_theta0 = -1 * self.theta1 + 90
            new_theta1 = -1 * self.theta0 + 90
        else:  # orient == 'MYR90'
            new_theta0 = 180 - self.theta1 + 90
            new_theta1 = 180 - self.theta0 + 90

        if not copy:
            ans = self
        else:
            ans = deepcopy(self)

        ans.center_unit = new_center_unit
        ans.theta0 = new_theta0
        ans.theta1 = new_theta1
        return ans

    @staticmethod
    def num_of_sparse_point_round(radius: float,
                                  res_grid_size: float,
                                  ) -> int:
        return int(math.ceil(math.pi / math.sqrt(res_grid_size / radius)))

    @classmethod
    def polygon_pointlist_export(cls,
                                 rout: dim_type,
                                 rin: dim_type,
                                 theta0: dim_type,
                                 theta1: dim_type,
                                 center: coord_type,
                                 nx: int = 1,
                                 ny: int = 1,
                                 spx: dim_type = 0.0,
                                 spy: dim_type = 0.0,
                                 resolution: float = 0.001,
                                 ):
        # Get the base polygons
        round_polygons = gdspy.Round(center=center,
                                     layer=0,
                                     radius=rout,
                                     inner_radius=rin,
                                     initial_angle=theta0 * np.pi / 180,
                                     final_angle=theta1 * np.pi / 180,
                                     number_of_points=cls.num_of_sparse_point_round(rout, resolution),
                                     max_points=sys.maxsize,
                                     datatype=0).polygons

        output_list_p = []
        output_list_n = []
        for x_count in range(nx):
            for y_count in range(ny):
                for polygon in round_polygons:
                    polygon_points = polygon
                    polygon_points[:, 0] += x_count * spx
                    polygon_points[:, 1] += y_count * spy
                    polygon_points = np.vstack([polygon_points, polygon_points[0]])

                    output_list_p.append(polygon_points.copy())

        return output_list_p, output_list_n

    def export_to_polygon(self):
        """
        Convert the PhotonicRound geometry to a PhotonicPolygon and returns it
        Returns
        -------
        poly : List[PhotonicPolygon]
            polygon representation of the given rectangle
        """
        [list_p, _] = PhotonicRound.polygon_pointlist_export(self.rout,
                                                             self.rin,
                                                             self.theta0,
                                                             self.theta1,
                                                             self.center,
                                                             nx=self.nx,
                                                             ny=self.ny,
                                                             spx=self.spx,
                                                             spy=self.spy,
                                                             resolution=self.resolution,
                                                             )

        poly_list = []
        for points in list_p:
            poly = PhotonicPolygon(resolution=self.resolution,
                                   layer=self.layer,
                                   points=points,
                                   unit_mode=False,
                                   )
            poly_list.append(poly)
        return poly_list


class PhotonicRect(Rect):
    """
    A layout rectangle, with optional arraying parameters.

    Parameters
    ----------
    layer : string or (string, string)
        the layer name, or a tuple of layer name and purpose name.
        If pupose name not given, defaults to 'drawing'.
    bbox : bag.layout.util.BBox or bag.layout.util.BBoxArray
        the base bounding box.  If this is a BBoxArray, the BBoxArray's
        arraying parameters are used.
    nx : int
        number of columns.
    ny : int
        number of rows.
    spx : float
        column pitch.
    spy : float
        row pitch.
    unit_mode : bool
        True if layout dimensions are specified in resolution units.
    """

    def __init__(self, layer, bbox, nx=1, ny=1, spx=0, spy=0, unit_mode=False):
        if isinstance(layer, str):
            layer = (layer, 'phot')
        Rect.__init__(self, layer, bbox, nx, ny, spx, spy, unit_mode)

    @classmethod
    def from_content(cls, content, resolution):
        return PhotonicRect(
            layer=content['layer'],
            bbox=BBox(
                left=content['bbox'][0][0],
                bottom=content['bbox'][0][1],
                right=content['bbox'][1][0],
                top=content['bbox'][1][1],
                unit_mode=False,
                resolution=resolution,
            ),
            nx=content.get('arr_nx', 1),
            ny=content.get('arr_ny', 1),
            spx=content.get('arr_spx', 0),
            spy=content.get('arr_spy', 0),
            unit_mode=False,
        )

    @property
    def bound_box(self) -> BBox:
        return BBox(*self.bbox.get_bounds(unit_mode=True), resolution=self._res, unit_mode=True)

    def transform(self,
                  loc: coord_type = (0, 0),
                  orient: str = 'R0',
                  unit_mode: bool = False,
                  copy: bool = False,
                  ) -> Optional[Figure]:
        """Transform this figure."""
        if not copy:
            ans = self
        else:
            ans = deepcopy(self)

        ans._bbox = ans._bbox.transform(loc=loc, orient=orient, unit_mode=unit_mode)

        return ans

    @classmethod
    def polygon_pointlist_export(cls,
                                 bbox: [[int, int], [int, int]],
                                 nx: int = 1,
                                 ny: int = 1,
                                 spx: dim_type = 0.0,
                                 spy: dim_type = 0.0,
                                 ) -> Tuple[List, List]:
        """
        Convert the PhotonicRect geometry to a list of polygon pointlists.

        Parameters
        ----------
        bbox : [[float, float], [float, float]]
            lower left and upper right corner xy coordinates
        nx : int
            number of arrayed rectangles in the x-direction
        ny : int
            number of arrayed rectangles in the y-direction
        spx : float
            space between arrayed rectangles in the x-direction
        spy : float
            space between arrayed rectangles in the y-direction

        Returns
        -------
        output_list : Tuple[List, List]
            The positive and negative polygon pointlists describing the photonicRect
        """

        # Calculate the width and length of the rectangle

        x_span = bbox[1][0] - bbox[0][0]  # type: int
        y_span = bbox[1][1] - bbox[0][1]  # type: int

        # Calculate the center of the first rectangle rounded to the nearest nm
        x_base = bbox[0][0]  # type: int
        y_base = bbox[0][1]  # type: int

        # Write the lumerical code for each rectangle in the array
        output_list_p = []
        output_list_n = []
        for x_count in range(nx):
            for y_count in range(ny):
                polygon_list = [(x_base + x_count * spx, y_base + y_count * spy),
                                (x_base + x_span + x_count * spx, y_base + y_count * spy),
                                (x_base + x_span + x_count * spx, y_base + y_span + y_count * spy),
                                (x_base + x_count * spx, y_base + y_span + y_count * spy),
                                (x_base + x_count * spx, y_base + y_count * spy)]
                output_list_p.append(polygon_list)

        return output_list_p, output_list_n

    def export_to_polygon(self):
        """
        Convert the PhotonicRect geometry to a PhotonicPolygon and returns it

        Returns
        -------
        poly : List[PhotonicPolygon]
            polygon representation of the given rectangle
        """
        bbox = [[self.bbox.left, self.bbox.bottom], [self.bbox.right, self.bbox.top]]
        [list_p, _] = PhotonicRect.polygon_pointlist_export(bbox=bbox,
                                                            nx=self.nx,
                                                            ny=self.ny,
                                                            spx=self.spx,
                                                            spy=self.spy,
                                                            )
        poly_list = []
        for points in list_p:
            poly = PhotonicPolygon(resolution=self.resolution,
                                   layer=self.layer,
                                   points=points,
                                   unit_mode=False,
                                   )
            poly_list.append(poly)
        return poly_list


class PhotonicPath(Figure):
    """
    A path defined by a list of x,y points and a width.

    User beware!  If the points in the path are specified too finely (ie, change between multiple consecutive points is
    less than the eps value), then the path may actually lose precision.
    If this occurs, try specifying the points less finely.

    Parameters
    ----------
    resolution : float
        the layout grid resolution.
    layer : string or (string, string)
        the layer name, or a tuple of layer name and purpose name.
        If purpose name not given, defaults to 'drawing'.
    width : float
        width of this path, in layout units.
    points : List[Tuple[float, float]]
        list of path points.
    unit_mode : bool
        True if width, points, and tolerance are given as resolution units instead of layout units.
    eps : float
        The tolerance for determining whether two points are coincident or colinear.

    """

    def __init__(self,
                 resolution: float,
                 layer: layer_or_lpp_type,
                 width: dim_type,
                 points: List[coord_type],
                 unit_mode: bool = False,
                 eps: float = None,
                 ) -> None:
        # If only a layer name is passed, assume 'phot' purpose
        if isinstance(layer, str):
            layer = (layer, 'phot')
        Figure.__init__(self, resolution)

        self._layer = layer
        self._destroyed = False

        if width <= 0:
            raise ValueError(f'PhotonicPath: width argument must be a positive number')

        if eps is None:
            self._eps_unit = 0.1
        else:
            if unit_mode:
                self._eps_unit = eps
            else:
                self._eps_unit = eps / resolution

        if unit_mode:
            self._width_unit = int(width)
        else:
            self._width_unit = int(round(width / resolution))

        # Scale to resolution unit, but do not snap input points to a grid.
        if unit_mode:
            points_unit = np.array(points)
        else:
            points_unit = np.array(points) / self._res

        # Remove coincident points from the passed list
        self._points_unit_scale = coords_cleanup(
            points_unit,
            eps_grid=self._eps_unit,
            cyclic_points=False,
            check_inline=False,
        )

        self._polygon_points_unit = self.process_points(
            points=self._points_unit_scale,
            width=self._width_unit,
            eps=self._eps_unit,
        )

    @staticmethod
    def process_points(points: np.ndarray,
                       width: dim_type,
                       eps: float = 1e-4,
                       ) -> np.ndarray:
        """
        Takes a width and center point list, and returns the points describing the polygon of the path.

        While the center points are not rounded to a grid, the points describing the polygon are snapped to the layout
        grid.

        The returned polygon points are in unit_mode (grid resolution units).

        Parameters
        ----------
        points : np.ndarray
            A numpy array of points describing the center of the path.
        width : Union[int, float]
            The width of the path
        eps : float
            The tolerance for determining whether two points are coincident

        Returns
        -------
        polygon_points : np.ndarray
            The numpy array of points describing the polygon of the path, rounded to the layout grid, and expressed in
            resolution units (ints).

        """
        # Create the polygon shape, not rounded to a grid.
        poly_pts = create_polygon_from_path_and_width(points_list=points, width=width, eps=eps)
        # Round to the grid and return
        return np.round(poly_pts).astype(int)

    @property
    def layer(self) -> Tuple[str, str]:
        """The rectangle (layer, purpose) pair."""
        return self._layer

    @Figure.valid.getter
    def valid(self) -> bool:
        """Returns True if this instance is valid."""
        return not self.destroyed and len(self._points_unit_scale) >= 2 and self._width_unit > 0

    @property
    def width(self):
        return self._width_unit * self._res

    @property
    def width_unit(self) -> int:
        return self._width_unit

    @property
    def eps(self):
        return self._eps_unit * self._res

    @property
    def eps_unit(self):
        return self._eps_unit

    @property
    def points(self):
        """ Return non-unit mode python list of points"""
        return (self._points_unit_scale * self._res).tolist()

    @property
    def polygon_points(self):
        """ Return non-unit_mode python list of points"""
        return (self._polygon_points_unit * self._res).tolist()

    @property
    def content(self) -> Dict[str, Any]:
        """A dictionary representation of this path."""
        content = dict(layer=self.layer,
                       width=self._width_unit * self._res,
                       points=self.points,
                       polygon_points=self.polygon_points
                       )
        return content

    @property
    def bound_box(self) -> BBox:
        left, bottom = np.amin(self._polygon_points_unit, axis=0)
        right, top = np.amax(self._polygon_points_unit, axis=0)
        return BBox(left, bottom, right, top, resolution=self._res, unit_mode=True)

    def move_by(self,
                dx: dim_type = 0,
                dy: dim_type = 0,
                unit_mode: bool = False,
                ) -> None:
        """Move this path by the given amount.

        Parameters
        ----------
        dx : float
            the X shift.
        dy : float
            the Y shift.
        unit_mode : bool
            True if shifts are given in resolution units.
        """
        if not unit_mode:
            dx = int(round(dx / self._res))
            dy = int(round(dy / self._res))
        self._points_unit_scale += np.array([dx, dy])
        self._polygon_points_unit += np.array([dx, dy])

    def transform(self,
                  loc: coord_type = (0, 0),
                  orient: str = 'R0',
                  unit_mode: bool = False,
                  copy: bool = False,
                  ) -> Figure:
        """Transform this figure."""
        res = self.resolution
        if unit_mode:
            dx, dy = loc
        else:
            dx = int(round(loc[0] / res))
            dy = int(round(loc[1] / res))
        dvec = np.array([dx, dy])
        mat = transform_table[orient]
        new_points = np.dot(mat, self._points_unit_scale.T).T + dvec
        new_polypoints = np.dot(mat, self._polygon_points_unit.T).T + dvec

        if not copy:
            ans = self
        else:
            ans = deepcopy(self)

        ans._points_unit_scale = new_points
        ans._polygon_points_unit = new_polypoints

        return ans

    @classmethod
    def from_content(cls,
                     content,
                     resolution,
                     ):
        return PhotonicPath(
            resolution=resolution,
            layer=content['layer'],
            width=content['width'],
            points=content['points'],
            unit_mode=False,
        )

    @classmethod
    def polygon_pointlist_export(cls,
                                 vertices: List[Tuple[float, float]],
                                 ) -> Tuple[List, List]:
        """

        Parameters
        ----------
        vertices : List[Tuple[float, float]
            The verticies from the content list of this polygon

        Returns
        -------
        output_list : Tuple[List, List]
            The positive and negative polygon pointlists describing this polygon
        """
        return [vertices], []

    def export_to_polygon(self) -> 'PhotonicPolygon':
        return PhotonicPolygon(
            layer=self.layer,
            resolution=self.resolution,
            points=self._polygon_points_unit,
            unit_mode=True,
        )


class PhotonicPathCollection(PathCollection):
    """
    A layout figure that consists of one or more paths.

    This class make it easy to draw bus/trasmission line objects.

    Parameters
    ----------
    resolution : float
        layout unit resolution.
    paths : List[Path]
        paths in this collection.
    """

    def __init__(self, resolution, paths):
        PathCollection.__init__(self, resolution, paths)


class PhotonicTLineBus(TLineBus):
    """
    A transmission line bus drawn using Path.

    assumes only 45 degree turns are used, and begin and end line segments are straight.

    Parameters
    ----------
    resolution : float
        layout unit resolution.
    layer : Union[str, Tuple[str, str]]
        the bus layer.
    points : List[Tuple[Union[float, int], Union[float, int]]]
        list of center points of the bus.
    widths : List[Union[float, int]]
        list of wire widths.  0 index is left/bottom most wire.
    spaces : List[Union[float, int]]
        list of wire spacings.
    end_style : str
        the path ends style.  Currently support 'truncate', 'extend', and 'round'.
    unit_mode : bool
        True if width and points are given as resolution units instead of layout units.
    """

    def __init__(self, resolution, layer, points, widths, spaces, end_style='truncate',
                 unit_mode=False):
        if isinstance(layer, str):
            layer = (layer, 'phot')
        TLineBus.__init__(self, resolution, layer, points, widths, spaces, end_style, unit_mode)


class PhotonicPolygon(Figure):
    """
    A layout polygon object.

    Parameters
    ----------
    resolution : float
        the layout grid resolution.
    layer : Union[str, Tuple[str, str]]
        the layer name, or a tuple of layer name and purpose name.
        If purpose name not given, defaults to 'drawing'.
    points : List[Tuple[Union[float, int], Union[float, int]]]
        the points defining the polygon.
    unit_mode : bool
        True if the points are given in resolution units.
    """

    def __init__(self,
                 resolution: float,
                 layer: layer_or_lpp_type,
                 points: List[coord_type],
                 unit_mode: bool = False,
                 ):
        Figure.__init__(self, resolution)
        layer = bag.io.fix_string(layer)
        if isinstance(layer, str):
            layer = (layer, 'phot')
        self._layer = layer

        # Points are stored internally as full precision floating points
        if not unit_mode:
            self._points = np.array(points)
        else:
            self._points = np.array(points) * self._res

    @property
    def layer(self):
        return self._layer

    @property
    def points(self):
        return self._points

    @property
    def points_unit(self):
        return np.round(self._points / self._res).astype(int)

    @property
    def content(self) -> Dict[str, Any]:
        quantized_points = self.points_unit * self._res
        return dict(layer=self.layer,
                    points=[(quantized_points[idx][0], quantized_points[idx][1])
                            for idx in range(quantized_points.shape[0])],
                    )

    @property
    def bound_box(self):
        left, bottom = np.amin(self._points, axis=0)
        right, top = np.amax(self._points, axis=0)
        return BBox(left, bottom, right, top, resolution=self._res, unit_mode=False)

    @classmethod
    def from_content(cls, content, resolution):
        return PhotonicPolygon(
            resolution=resolution,
            layer=content['layer'],
            points=content['points'],
            unit_mode=False,
        )

    def move_by(self, dx=0, dy=0, unit_mode=False):
        if unit_mode:
            dx = dx * self._res
            dy = dy * self._res
        self._points += np.array([dx, dy])

    def transform(self, loc=(0, 0), orient='R0', unit_mode=False, copy=False):
        if unit_mode:
            loc = np.array([loc[0] * self._res, loc[1] * self._res])
        mat = transform_table[orient]
        new_points = np.dot(mat, self._points.T).T + loc

        if not copy:
            ans = self
        else:
            ans = deepcopy(self)

        ans._points = new_points
        return ans

    @classmethod
    def polygon_pointlist_export(cls,
                                 vertices: List[Tuple[float, float]],
                                 ) -> Tuple[List, List]:
        """

        Parameters
        ----------
        vertices : List[Tuple[float, float]
            The verticies from the content list of this polygon

        Returns
        -------
        output_list : Tuple[List, List]
            The positive and negative polygon pointlists describing this polygon
        """
        return [vertices], []

    def rotate(self, angle: float = 0.0) -> None:
        """
        Rotates the polygon about the given axis by the given angle

        Parameters
        ----------
        angle : float
            the amount in radians that the polygon will be rotated
        """
        self._points = np.column_stack(
            [
                np.cos(angle) * self._points[:, 0] - np.sin(angle) * self._points[:, 1],
                np.sin(angle) * self._points[:, 0] + np.cos(angle) * self._points[:, 1]
            ]
        )


class PhotonicAdvancedPolygon(Polygon):
    """
    A layout polygon object.

    Parameters
    ----------
    resolution : float
        the layout grid resolution.
    layer : Union[str, Tuple[str, str]]
        the layer name, or a tuple of layer name and purpose name.
        If purpose name not given, defaults to 'drawing'.
    points : List[Tuple[Union[float, int], Union[float, int]]]
        the points defining the polygon.
    unit_mode : bool
        True if the points are given in resolution units.
    """

    def __init__(self,
                 resolution: float,
                 layer: layer_or_lpp_type,
                 points: List[coord_type],
                 negative_points: Union[List[coord_type], List[List[coord_type]]],
                 unit_mode: bool = False,
                 ):
        if isinstance(layer, str):
            layer = (layer, 'phot')
        Polygon.__init__(self, resolution, layer, points, unit_mode)
        if not negative_points:
            self._negative_points = []
        elif isinstance(negative_points[0], List):
            self._negative_points = negative_points
        else:
            self._negative_points = [negative_points]


class PhotonicBlockage(Blockage):
    """
    A blockage object.

    Subclass Polygon for code reuse.

    Parameters
    ----------
    resolution : float
        the layout grid resolution.
    block_type : str
        the blockage type.  Currently supports 'routing' and 'placement'.
    block_layer : str
        the blockage layer.  This value is ignored if blockage type is 'placement'.
    points : List[Tuple[Union[float, int], Union[float, int]]]
        the points defining the blockage.
    unit_mode : bool
        True if the points are given in resolution units.
    """

    def __init__(self, resolution, block_type, block_layer, points, unit_mode=False):
        # type: (float, str, str, List[Tuple[Union[float, int], Union[float, int]]], bool) -> None
        Blockage.__init__(self, resolution, block_type, block_layer, points, unit_mode)

    @classmethod
    def from_content(cls,
                     content,
                     resolution,
                     ):
        return PhotonicBlockage(
            resolution=resolution,
            block_type=content['btype'],
            block_layer=content['blayer'],
            points=content['points'],
            unit_mode=False,
        )


class PhotonicBoundary(Boundary):
    """
    A boundary object.

    Subclass Polygon for code reuse.

    Parameters
    ----------
    resolution : float
        the layout grid resolution.
    boundary_type : str
        the boundary type.  Currently supports 'PR', 'snap', and 'area'.
    points : List[Tuple[Union[float, int], Union[float, int]]]
        the points defining the blockage.
    unit_mode : bool
        True if the points are given in resolution units.
    """

    def __init__(self,
                 resolution: float,
                 boundary_type: str,
                 points: List[coord_type],
                 unit_mode: bool = False,
                 ) -> None:
        Boundary.__init__(self, resolution, boundary_type, points, unit_mode)

    @classmethod
    def from_content(cls,
                     content,
                     resolution,
                     ):
        return PhotonicBoundary(
            resolution=resolution,
            boundary_type=content['btype'],
            points=content['points'],
            unit_mode=False,
        )


class PhotonicViaInfo(ViaInfo):
    """
    A dictionary that represents a layout via.
    """

    param_list = ['id', 'loc', 'orient', 'num_rows', 'num_cols', 'sp_rows', 'sp_cols',
                  'enc1', 'enc2']

    def __init__(self, res, **kwargs):
        ViaInfo.__init__(self, res, **kwargs)


class PhotonicVia(Via):
    """
    A layout via, with optional arraying parameters.

    Parameters
    ----------
    tech : bag.layout.core.TechInfo
        the technology class used to calculate via information.
    bbox : bag.layout.util.BBox or bag.layout.util.BBoxArray
        the via bounding box, not including extensions.
        If this is a BBoxArray, the BBoxArray's arraying parameters are used.
    bot_layer : str or (str, str)
        the bottom layer name, or a tuple of layer name and purpose name.
        If purpose name not given, defaults to 'drawing'.
    top_layer : str or (str, str)
        the top layer name, or a tuple of layer name and purpose name.
        If purpose name not given, defaults to 'drawing'.
    bot_dir : str
        the bottom layer extension direction.  Either 'x' or 'y'.
    nx : int
        arraying parameter.  Number of columns.
    ny : int
        arraying parameter.  Mumber of rows.
    spx : float
        arraying parameter.  Column pitch.
    spy : float
        arraying parameter.  Row pitch.
    extend : bool
        True if via extension can be drawn outside of bounding box.
    top_dir : Optional[str]
        top layer extension direction.  Can force to extend in same direction as bottom.
    unit_mode : bool
        True if array pitches are given in resolution units.
    """

    def __init__(self, tech, bbox, bot_layer, top_layer, bot_dir,
                 nx=1, ny=1, spx=0, spy=0, extend=True, top_dir=None, unit_mode=False):
        Via.__init__(self, tech, bbox, bot_layer, top_layer, bot_dir, nx, ny, spx, spy, extend, top_dir, unit_mode)

    @classmethod
    def from_content(cls,
                     content: Dict,
                     ) -> "PhotonicVia":
        return PhotonicVia(
            tech=content['tech'],
            bbox=content['bbox'],
            bot_layer=content['bot_layer'],
            top_layer=content['top_layer'],
            bot_dir=content['bot_dir'],
            nx=content.get('arr_nx', 1),
            ny=content.get('arr_ny', 1),
            spx=content.get('arr_spx', 0),
            spy=content.get('arr_spy', 0),
            extend=content['extend'],
            top_dir=content['top_dir'],
            unit_mode=False,
        )


class PhotonicPinInfo(PinInfo):
    """
    A dictionary that represents a layout pin.
    """

    param_list = ['net_name', 'pin_name', 'label', 'layer', 'bbox', 'make_rect']

    def __init__(self, res, **kwargs):
        PinInfo.__init__(self, res, **kwargs)

    @classmethod
    def from_content(cls,
                     content: Dict,
                     resolution: float,
                     ) -> "PhotonicPinInfo":
        return PhotonicPinInfo(
            res=resolution,
            net_name=content['net_name'],
            pin_name=content['pin_name'],
            label=content['label'],
            layer=content['layer'],
            bbox=content['bbox'],
            make_rect=content['make_rect']
        )

    def transform(self,
                  loc: coord_type,
                  orient: str,
                  unit_mode: bool,
                  copy: bool,
                  ):
        new_box = self.bbox.transform(loc=loc, orient=orient, unit_mode=unit_mode)
        new_box = [[new_box.left, new_box.bottom], [new_box.right, new_box.top]]
        if not copy:
            ans = self
        else:
            ans = deepcopy(self)

        ans['bbox'] = new_box
        return ans
