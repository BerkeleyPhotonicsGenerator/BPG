# -*- coding: utf-8 -*-

"""This module defines various layout objects one can add and manipulate in a template.
"""
from typing import TYPE_CHECKING, Union, List, Tuple, Optional, Dict, Any

from bag.layout.objects import Arrayable, Rect, Path, PathCollection, TLineBus, Polygon, Blockage, Boundary, \
    ViaInfo, Via, PinInfo, Instance, InstanceInfo, Figure
from bag.layout.routing import RoutingGrid
from bag.layout.template import TemplateBase
import bag.io
from bag.layout.util import transform_point, BBox, transform_table
from .photonic_core import CoordBase
import gdspy
import numpy as np
import sys
import math
from copy import deepcopy

if TYPE_CHECKING:
    from BPG.photonic_template import PhotonicTemplateBase
    from BPG.photonic_port import PhotonicPort
    from bag.layout.objects import Figure

ldim = Union[float, int]
dim_type = Union[float, int]
coord_type = Tuple[dim_type, dim_type]


class PhotonicInstanceInfo(InstanceInfo):
    """ A dictionary that represents a layout instance. """

    def __init__(self, res, change_orient=True, **kwargs):
        InstanceInfo.__init__(self, res, change_orient, **kwargs)

        if 'master_key' in kwargs:
            self['master_key'] = kwargs['master_key']

    @property
    def master_key(self):
        # type: () -> Tuple
        return self['master_key']

    def copy(self):
        """Override copy method of InstanceInfo to return a PhotonicInstanceInfo instead."""
        return PhotonicInstanceInfo(self._resolution, change_orient=False, **self)


class PhotonicInstance(Instance):
    """A photonic layout instance, with optional arraying parameters.

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
                 parent_grid,  # type: RoutingGrid
                 lib_name,  # type: str
                 master,  # type: PhotonicTemplateBase
                 loc,  # type: Tuple[ldim, ldim]
                 orient,  # type: str
                 name=None,  # type: Optional[str]
                 nx=1,  # type: int
                 ny=1,  # type: int
                 spx=0,  # type: ldim
                 spy=0,  # type: ldim
                 unit_mode=False,  # type: bool
                 ):
        # type: (...) -> None
        Instance.__init__(self, parent_grid, lib_name, master, loc, orient,
                          name, nx, ny, spx, spy, unit_mode)

        self._photonic_port_list = {}  # type: Dict[str, PhotonicPort]
        self._photonic_port_creator()

    def __getitem__(self,
                    item,  # type: str
                    ):
        # type: (...) -> PhotonicPort
        """ Allow dictionary syntax to grab photonic ports """
        return self.get_photonic_port(name=item)

    @property
    def content(self):
        # type: () -> PhotonicInstanceInfo
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

    def _photonic_port_creator(self):
        # type: (...) -> None
        """
        Helper for creating the photonic ports of this instance
        Returns
        -------

        """
        for port_name in self._master.photonic_ports_names_iter():
            self._photonic_port_list[port_name] = self._master.get_photonic_port(port_name).transform(
                loc=self._loc_unit,
                orient=self._orient,
                unit_mode=True
            )

    def set_port_used(self,
                      port_name,  # type: str
                      ):
        # type: (...) -> None
        if port_name not in self._photonic_port_list:
            raise ValueError("Photonic port {} not in instance {}", port_name, self._inst_name)

        self._photonic_port_list[port_name].used(True)

    def get_port_used(self,
                      port_name,  # type: str
                      ):
        # type: (...) -> bool
        if port_name not in self._photonic_port_list:
            raise ValueError("Photonic port {} not in instance {}", port_name, self._inst_name)

        return self._photonic_port_list[port_name].used()

    def get_photonic_port(self,
                          name,  # type: str
                          row=0,  # type: int
                          col=0,  # type: int
                          ):
        # type: (...) -> PhotonicPort
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

    @property
    def master(self):
        # type: () -> PhotonicTemplateBase
        """The master template of this instance."""
        return self._master

    def get_bound_box_of(self, row=0, col=0):
        """Returns the bounding box of an instance in this mosaic."""
        dx, dy = self.get_item_location(row=row, col=col, unit_mode=True)
        xshift, yshift = self._loc_unit
        xshift += dx
        yshift += dy
        return self._master.bound_box.transform((xshift, yshift), self.orientation, unit_mode=True)

    def move_by(self, dx=0, dy=0, unit_mode=False):
        # type: (Union[float, int], Union[float, int], bool) -> None
        """Move this instance by the given amount.

        Parameters
        ----------
        dx : Union[float, int]
            the X shift.
        dy : Union[float, int]
            the Y shift.
        unit_mode : bool
            True if shifts are given in resolution units
        """
        if not unit_mode:
            dx = int(round(dx / self.resolution))
            dy = int(round(dy / self.resolution))
        self._loc_unit = self._loc_unit[0] + dx, self._loc_unit[1] + dy

        # Translate each port in the instance as well
        for port in self._photonic_port_list.values():
            port.transform(
                loc=(dx, dy),
                orient='R0',
                unit_mode=True
            )

    def transform(self, loc=(0, 0), orient='R0', unit_mode=False, copy=False):
        # type: (Tuple[ldim, ldim], str, bool, bool) -> Optional[Figure]
        """Transform this figure."""
        if not unit_mode:
            res = self.resolution
            loc = int(round(loc[0] / res)), int(round(loc[1] / res))

        if not copy:
            self._loc_unit = loc
            self._orient = orient
            return self
        else:
            return Instance(self._parent_grid, self._lib_name, self._master, self._loc_unit,
                            self._orient, name=self._inst_name, nx=self.nx, ny=self.ny,
                            spx=self.spx_unit, spy=self.spy_unit, unit_mode=True)


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
                 layer,
                 resolution,
                 center,
                 rout,
                 rin=0,
                 theta0=0,
                 theta1=360,
                 nx=1,
                 ny=1,
                 spx=0,
                 spy=0,
                 unit_mode=False,
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
             val,  # type: Union[float, int]
             ):
        """Sets the outer radius in layout units"""
        self._rout_unit = int(round(val / self._res))

    @rout_unit.setter
    def rout_unit(self,
                  val,  # type: int
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
               val,  # type: coord_type
               ):
        """Sets the center in layout units"""
        self._center_unit = (int(round(val[0] / self._res)), int(round(val[1] / self._res)))

    @center_unit.setter
    def center_unit(self,
                    val,  # type: coord_type
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
            val,  # type: Union[float, int]
            ):
        """Sets the inner radius in layout units"""
        self._rin_unit = int(round(val / self._res))

    @rin_unit.setter
    def rin_unit(self,
                 val,  # type: int
                 ):
        """Sets the inner radius in resolution units"""
        self._rin_unit = int(round(val))

    @property
    def theta0(self):
        """The starting angle, in degrees"""
        return self._theta0

    @theta0.setter
    def theta0(self,
               val,  # type: Union[float, int]
               ):
        """Sets the start angle in degrees"""
        self._theta0 = val

    @property
    def theta1(self):
        """The ending angle, in degrees"""
        return self._theta1

    @theta1.setter
    def theta1(self,
               val,  # type: Union[float, int]
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
                dx=0,  # type: dim_type
                dy=0,  # type: dim_type
                unit_mode=False,  # type: bool
                ):
        """Moves the round object"""
        if unit_mode:
            self.center_unit = (self.center_unit[0] + int(round(dx)), self.center_unit[1] + int(round(dy)))
        else:
            self.center_unit = (self.center_unit[0] + int(round(dx / self._res)),
                                self.center_unit[1] + int(round(dy / self._res))
                                )

    def transform(self, loc=(0, 0), orient='R0', unit_mode=False, copy=False):
        # type: (Tuple[ldim, ldim], str, bool, bool) -> Optional[PhotonicRound]
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

        if copy:
            print("WARNING: USING THIS BREAKS POWER FILL ALGORITHM.")
            self.center_unit = new_center_unit
            self.theta0 = new_theta0
            self.theta1 = new_theta1
            return self
        else:
            return PhotonicRound(
                layer=self.layer,
                resolution=self.resolution,
                center=new_center_unit,
                rout=self.rout_unit,
                rin=self.rin_unit,
                theta0=new_theta0,
                theta1=new_theta1,
                nx=self.nx,
                ny=self.ny,
                spx=self.spx_unit,
                spy=self.spy_unit,
                unit_mode=True
            )

    @classmethod
    def lsf_export(cls,
                   rout,  # type: dim_type
                   rin,  # type: dim_type
                   theta0,  # type: dim_type
                   theta1,  # type: dim_type
                   layer_prop,
                   center,  # type: coord_type
                   nx=1,  # type: int
                   ny=1,  # type: int
                   spx=0.0,  # type: dim_type
                   spy=0.0,  # type: dim_type
                   ):
        # type: (...) -> List(str)
        """

        Parameters
        ----------
        rout
        rin
        theta0
        theta1
        layer_prop
        center
        nx
        ny
        spx
        spy

        Returns
        -------

        """
        x0, y0 = center[0] * 1e-6, center[1] * 1e-6
        spx, spy = spx * 1e-6, spy * 1e-6
        lsf_code = []

        if rin == 0:
            for x_count in range(nx):
                for y_count in range(ny):
                    lsf_code.append('\n')
                    lsf_code.append('addcircle;\n')

                    # Set material properties
                    lsf_code.append('set("material", "{}");\n'.format(layer_prop['material']))
                    lsf_code.append('set("alpha", {});\n'.format(layer_prop['alpha']))

                    # Set radius
                    lsf_code.append('set(radius, {});\n'.format(rout * 1e-6))

                    # Compute the x and y coordinates for each rectangle
                    lsf_code.append('set("x", {});\n'.format(x0 + spx * x_count))
                    lsf_code.append('set("y", {});\n'.format(y0 + spy * y_count))

                    # Extract the thickness values from the layermap file
                    lsf_code.append('set("z min", {});\n'.format(layer_prop['z_min'] * 1e-6))
                    lsf_code.append('set("z max", {});\n'.format(layer_prop['z_max'] * 1e-6))
        else:
            for x_count in range(nx):
                for y_count in range(ny):
                    lsf_code.append('\n')
                    lsf_code.append('addring;\n')

                    # Set material properties
                    lsf_code.append('set("material", "{}");\n'.format(layer_prop['material']))
                    lsf_code.append('set("alpha", {});\n'.format(layer_prop['alpha']))

                    # Set dimensions/angles
                    lsf_code.append('set("outer radius", {});\n'.format(rout * 1e-6))
                    lsf_code.append('set("inner radius", {});\n'.format(rin * 1e-6))
                    lsf_code.append('set("theta start", {});\n'.format(theta0))
                    lsf_code.append('set("theta stop", {});\n'.format(theta1))

                    # Compute the x and y coordinates for each rectangle
                    lsf_code.append('set("x", {});\n'.format(x0 + spx * x_count))
                    lsf_code.append('set("y", {});\n'.format(y0 + spy * y_count))

                    # Extract the thickness values from the layermap file
                    lsf_code.append('set("z min", {});\n'.format(layer_prop['z_min'] * 1e-6))
                    lsf_code.append('set("z max", {});\n'.format(layer_prop['z_max'] * 1e-6))

        return lsf_code

    @staticmethod
    def num_of_sparse_point_round(radius,  # type: float
                                  res_grid_size,  # type: float
                                  ):
        # type: (...) -> int
        return int(math.ceil(math.pi / math.sqrt(res_grid_size / radius)))

    @classmethod
    def polygon_pointlist_export(cls,
                                 rout,  # type: dim_type
                                 rin,  # type: dim_type
                                 theta0,  # type: dim_type
                                 theta1,  # type: dim_type
                                 center,  # type: coord_type
                                 nx=1,  # type: int
                                 ny=1,  # type: int
                                 spx=0.0,  # type: dim_type
                                 spy=0.0,  # type: dim_type
                                 resolution=0.001  # type: float
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

    @classmethod
    def lsf_export(cls, bbox, layer_prop, nx=1, ny=1, spx=0.0, spy=0.0) -> List[str]:
        """
        Describes the current rectangle shape in terms of lsf parameters for lumerical use.
        Note that Lumerical uses meters as the base unit, and all input coords are assumed to be in
        microns. This method inherently resizes

        Parameters
        ----------
        bbox : [[float, float], [float, float]]
            lower left and upper right corner xy coordinates
        layer_prop : dict
            dictionary containing material properties for the desired layer
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
        lsf_code : List[str]
            list of str containing the lsf code required to create specified rectangles
        """

        # Calculate the width and length of the rectangle in meters
        x_span = CoordBase(bbox[1][0] - bbox[0][0]).meters
        y_span = CoordBase(bbox[1][1] - bbox[0][1]).meters

        # Calculate the center of the first rectangle in meters
        base_x_center = CoordBase((bbox[1][0] + bbox[0][0]) / 2).meters
        base_y_center = CoordBase((bbox[1][1] + bbox[0][1]) / 2).meters

        # Get vertical dimensions
        z_min = CoordBase(layer_prop['z_min']).meters
        z_max = CoordBase(layer_prop['z_max']).meters

        # Write the lumerical code for each rectangle in the array
        lsf_code = []
        for x_count in range(nx):
            for y_count in range(ny):
                lsf_code.append('\n')
                lsf_code.append('addrect;\n')
                lsf_code.append('set("material", "{}");\n'.format(layer_prop['material']))
                lsf_code.append('set("alpha", {});\n'.format(layer_prop['alpha']))

                # Compute the x and y coordinates for each rectangle
                lsf_code.append('set("x span", {});\n'.format(x_span))
                lsf_code.append('set("x", {});\n'.format(base_x_center + CoordBase(spx * x_count).meters))
                lsf_code.append('set("y span", {});\n'.format(y_span))
                lsf_code.append('set("y", {});\n'.format(base_y_center + CoordBase(spy * y_count).meters))

                # Extract the thickness values from the layermap file
                lsf_code.append('set("z min", {});\n'.format(z_min))
                lsf_code.append('set("z max", {});\n'.format(z_max))

                if 'mesh_order' in layer_prop:
                    lsf_code.append('set("override mesh order from material database", 1);\n')
                    lsf_code.append('set("mesh order", {});\n'.format(layer_prop['mesh_order']))

        return lsf_code

    @classmethod
    def polygon_pointlist_export(cls,
                                 bbox,  # type: [[int, int], [int, int]]
                                 nx=1,  # type: int
                                 ny=1,  # type: int
                                 spx=0.0,  # type: int
                                 spy=0.0,  # type: int
                                 ):
        # type: (...) -> Tuple[List, List]
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


class PhotonicPath(Figure):
    """
    A layout path.  Only 45/90 degree turns are allowed.

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
    end_style : str
        the path ends style.  Currently support 'truncate', 'extend', and 'round'.
    join_style : str
        the ends style at intermediate points of the path.  Currently support 'extend' and 'round'.
    unit_mode : bool
        True if width and points are given as resolution units instead of layout units.
    """

    def __init__(self,
                 resolution,  # type: float
                 layer,  # type: Union[str, Tuple[str, str]]
                 width,  # type: Union[int, float]
                 points,  # type: List[Tuple[Union[int, float], Union[int, float]]]
                 end_style='truncate',  # type: str
                 join_style='extend',  # type: str
                 unit_mode=False,  # type: bool
                 ):
        # type (...) -> None
        if isinstance(layer, str):
            layer = (layer, 'phot')
        Figure.__init__(self, resolution)

        self._layer = layer
        self._end_style = end_style
        self._join_style = join_style
        self._destroyed = False
        self._width = 0
        self._points_unit = None

        if unit_mode:
            self._width = int(width)
        else:
            self._width = int(round(width / resolution))

        center_unit, upper_unit, lower_unit = self.process_points(
            pts=points,
            width=width,
            eps=0.00001,
            unit_mode=unit_mode,
        )

        self._points_unit = np.array(center_unit, dtype=int)
        self._upper_unit = np.array(upper_unit, dtype=int)
        self._lower_unit = np.array(lower_unit, dtype=int)

    def process_points(self,
                       pts,
                       width,  # type: int
                       eps=0.00001,  # type: float
                       unit_mode=False,  # type: bool
                       ):
        """



        Parameters
        ----------
        pts
        width
        eps
        unit_mode

        Returns
        -------

        """

        # TODO: add points at end and beginning to make sure path ends are vertical/horizontal
        # type: (...) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]], List[Tuple[int, int]]]
        pts_center = []

        if unit_mode:
            pts_unit = ((int(pt[0]), int(pt[1])) for pt in pts)
        else:
            pts_unit = ((int(round(pt[0] / self.resolution)), int(round(pt[1] / self.resolution))) for pt in pts)

        # First pass gets rid of collinear and duplicate points.
        # Also returns an error if radius of curvature is smaller than width / 2
        for x, y in pts_unit:
            if len(pts_center) == 0:
                pts_center.append((x, y))
            else:
                x_prev, y_prev = pts_center[-1]

                # Make sure new point is different from previous
                if x != x_prev or y != y_prev:
                    # Delete middle point if new segment is collinear with old segment
                    if len(pts_center) > 2:
                        # Get new slope and old slope
                        dx, dy = x - x_prev, y - y_prev
                        dx_prev, dy_prev = x_prev - pts_center[-2][0], y_prev - pts_center[-2][1]

                        m = dy / dx if abs(dx) > eps else 'v'
                        m_prev = dy_prev / dx_prev if abs(dx_prev) > eps else 'v'

                        # If slopes are the same, points are collinear, remove the middle one, and add the new
                        if m == m_prev:
                            del pts_center[-1]
                            pts_center.append((x, y))
                        # If this is a new non-collinear point, make sure it abides by minimum radius of curvature
                        else:
                            # radius = self._radius_of_curvature(pts_center[-2], pts_center[-1], (x, y), eps=eps)
                            # if radius >= self.width / 2:
                            #     pts_center.append((x, y))
                            # print(radius)
                            # TODO: Does this always work properly if input points are super dense and therefore already
                            # manhattanized?
                            pts_center.append((x, y))
                    else:
                        # This is the second point in the list, so as long as it is different, add it
                        pts_center.append((x, y))

        print("PhotonicPath.__init__:  length of pts_center: {}".format(
            len(pts_center)
        ))

        # Add the polygon boundary based on the ideal curve
        # Now that center points are clean, create the upper and lower points by finding perpendicular
        pts_upper = []
        pts_lower = []

        for ind, (x, y) in enumerate(pts):
            prev_point = pts[max(ind - 1, 0)]
            next_point = pts[min(ind + 1, len(pts) - 1)]

            dx, dy = next_point[0] - prev_point[0], next_point[1] - prev_point[1]
            norm = math.sqrt(math.pow(dx, 2) + math.pow(dy, 2))
            tangent_vec = (dx / norm, dy / norm)

            if abs(dx) > eps:
                # Form a triangle with dx = 1, dy = m, and hypotenuse = sqrt(1+m^2)
                m = dy / dx
                hypotenuse = math.sqrt(1 + math.pow(m, 2))

                point_dx, point_dy = -(width / 2) * (m / hypotenuse), (width / 2) * (1 / hypotenuse)

                if dx > 0:
                    new_upper = x + point_dx, y + point_dy
                    new_lower = x - point_dx, y - point_dy
                else:
                    new_upper = x - point_dx, y - point_dy
                    new_lower = x + point_dx, y + point_dy
            else:
                # Points are on a vertical line
                if dy > 0:
                    new_upper = x - width / 2, y
                    new_lower = x + width / 2, y
                else:
                    new_upper = x + width / 2, y
                    new_lower = x - width / 2, y

            # Round the potential new upper and lower points to the resolution grid
            if unit_mode:
                new_upper = (int(new_upper[0]), int(new_upper[1]))
                new_lower = (int(new_lower[0]), int(new_lower[1]))
            else:
                new_upper = (int(round(new_upper[0] / self.resolution)), int(round(new_upper[1] / self.resolution)))
                new_lower = (int(round(new_lower[0] / self.resolution)), int(round(new_lower[1] / self.resolution)))

            # Check that the new points on the left and right do not create a reentrant polygon
            # This just means make sure that
            if ind == 0:
                pts_upper.append(new_upper)
                pts_lower.append(new_lower)
            else:
                new_upper_vec = new_upper[0] - pts_upper[-1][0], new_upper[1] - pts_upper[-1][1]
                new_lower_vec = new_lower[0] - pts_lower[-1][0], new_lower[1] - pts_lower[-1][1]

                new_upper_dp = new_upper_vec[0] * tangent_vec[0] + new_upper_vec[1] * tangent_vec[1]
                new_lower_dp = new_lower_vec[0] * tangent_vec[0] + new_lower_vec[1] * tangent_vec[1]

                # TODO: can we always add, or should we check that the points are far enough away?
                if new_upper != pts_upper[-1] : # and new_upper_dp > 0.5 :
                    pts_upper.append(new_upper)
                if new_lower != pts_lower[-1] : # and new_lower_dp > 0.5:
                    pts_lower.append(new_lower)

        return pts_center, pts_upper, pts_lower

    @staticmethod
    def _radius_of_curvature(pt0,  # type: Tuple[int, int]
                             pt1,  # type: Tuple[int, int]
                             pt2,  # type: Tuple[int, int]
                             eps,  # type: float
                             ):
        # type: (...) -> float

        ma = -(pt1[0] - pt0[0]) / (pt1[1] - pt0[1]) if abs(pt1[1] - pt0[1]) > eps else 'v'
        mb = -(pt2[0] - pt1[0]) / (pt2[1] - pt1[1]) if abs(pt2[1] - pt1[1]) > eps else 'v'

        xa, ya = (pt0[0] + pt1[0]) / 2, (pt0[1] + pt1[1]) / 2
        xb, yb = (pt1[0] + pt2[0]) / 2, (pt1[1] + pt2[1]) / 2

        # First two points form a horizontal line
        if ma == 'v':
            center = (xa, mb * (xa - xb) + yb)
        # Second two points form a horizontal line
        elif mb == 'v':
            center = (xb, ma * (xb - xa) + ya)
        else:
            center = ((mb * xb - ma * xa - (yb - ya))/(mb - ma), (ma * mb * (xb - xa) - (ma * yb - mb * ya))/(mb - ma))

        point = center[0] - pt1[0], center[1] - pt1[1]
        radius = math.sqrt(math.pow(point[0], 2) + math.pow(point[1], 2))

        return radius

    @property
    def layer(self):
        # type: () -> Tuple[str, str]
        """The rectangle (layer, purpose) pair."""
        return self._layer

    @Figure.valid.getter
    def valid(self):
        # type: () -> bool
        """Returns True if this instance is valid."""
        return not self.destroyed and len(self._points_unit) >= 2 and self._width > 0

    @property
    def width(self):
        return self._width * self._res

    @property
    def width_unit(self):
        # type: () -> int
        return self._width

    @property
    def points(self):
        return [(self._points_unit[idx][0] * self._res, self._points_unit[idx][1] * self._res)
                for idx in range(self._points_unit.shape[0])]

    @property
    def lower(self):
        return [(self._lower_unit[idx][0] * self._res, self._lower_unit[idx][1] * self._res)
                for idx in range(self._lower_unit.shape[0])]

    @property
    def upper(self):
        return [(self._upper_unit[idx][0] * self._res, self._upper_unit[idx][1] * self._res)
                for idx in range(self._upper_unit.shape[0])]

    @property
    def points_unit(self):
        return [(self._points_unit[idx][0], self._points_unit[idx][1])
                for idx in range(self._points_unit.shape[0])]

    @property
    def polygon_points(self):
        out = self.upper
        out.extend(self.lower[::-1])

        return out

    @property
    def content(self):
        # type: () -> Dict[str, Any]
        """A dictionary representation of this path."""
        content = dict(layer=self.layer,
                       width=self._width * self._res,
                       points=self.points,
                       end_style=self._end_style,
                       join_style=self._join_style,
                       polygon_points=self.polygon_points
                       )
        return content

    def move_by(self, dx=0, dy=0, unit_mode=False):
        # type: (ldim, ldim, bool) -> None
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
        self._points_unit += np.array([dx, dy])
        self._upper_unit += np.array([dx, dy])
        self._lower_unit += np.array([dx, dy])

    def transform(self, loc=(0, 0), orient='R0', unit_mode=False, copy=False):
        # type: (Tuple[ldim, ldim], str, bool, bool) -> Figure
        """Transform this figure."""
        res = self.resolution
        if unit_mode:
            dx, dy = loc
        else:
            dx = int(round(loc[0] / res))
            dy = int(round(loc[1] / res))
        dvec = np.array([dx, dy])
        mat = transform_table[orient]
        new_points = np.dot(mat, self._points_unit.T).T + dvec
        new_upper = np.dot(mat, self._upper_unit.T).T + dvec
        new_lower = np.dot(mat, self._lower_unit.T).T + dvec

        if not copy:
            ans = self
        else:
            ans = deepcopy(self)

        ans._points_unit = new_points
        ans._upper_unit = new_upper
        ans._lower_unit = new_lower

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
            end_style=content['end_style'],
            join_style=content['join_style'],
            unit_mode=False,
        )

    @classmethod
    def polygon_pointlist_export(cls,
                                 vertices,  # type: List[Tuple[float, float]]
                                 ):
        # type: (...) -> Tuple[List, List]
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


class PhotonicPolygon(Polygon):
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
                 resolution,  # type: float
                 layer,  # type: Union[str, Tuple[str, str]]
                 points,  # type: List[Tuple[Union[float, int], Union[float, int]]]
                 unit_mode=False,  # type: bool
                 ):
        if isinstance(layer, str):
            layer = (layer, 'phot')
        Polygon.__init__(self, resolution, layer, points, unit_mode)

    @classmethod
    def from_content(cls, content, resolution):
        return PhotonicPolygon(
            resolution=resolution,
            layer=content['layer'],
            points=content['points'],
            unit_mode=False,
        )

    @classmethod
    def lsf_export(cls, vertices, layer_prop) -> List[str]:
        """
        Describes the current polygon shape in terms of lsf parameters for lumerical use

        Parameters
        ----------
        vertices : List[Tuple[float, float]]
            ordered list of x,y coordinates representing the points of the polygon
        layer_prop : dict
            dictionary containing material properties for the desired layer

        Returns
        -------
        lsf_code : List[str]
            list of str containing the lsf code required to create specified rectangles
        """
        # Grab the number of vertices in the polygon to preallocate Lumerical matrix size
        poly_len = len(vertices)

        # Write the lumerical code for the polygon
        lsf_code = ['\n',
                    'addpoly;\n',
                    'set("material", "{}");\n'.format(layer_prop['material']),
                    'set("alpha", {});\n'.format(layer_prop['alpha']),

                    # Create matrix to hold vertices, Note that the Lumerical uses meters as the base unit
                    'V = matrix({},2);\n'.format(poly_len),
                    'V(1:{},1) = {};\n'.format(poly_len, [CoordBase(point[0]).meters for point in vertices]),
                    'V(1:{},2) = {};\n'.format(poly_len, [CoordBase(point[1]).meters for point in vertices]),
                    'set("vertices", V);\n',

                    # Set the thickness values from the layermap file
                    'set("z min", {});\n'.format(CoordBase(layer_prop['z_min']).meters),
                    'set("z max", {});\n'.format(CoordBase(layer_prop['z_max']).meters)
                    ]

        return lsf_code

    @classmethod
    def polygon_pointlist_export(cls,
                                 vertices,  # type: List[Tuple[float, float]]
                                 ):
        # type: (...) -> Tuple[List, List]
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
                 resolution,  # type: float
                 layer,  # type: Union[str, Tuple[str, str]]
                 points,  # type: List[Tuple[Union[float, int], Union[float, int]]]
                 negative_points,  # type: Union[List[coord_type], List[List[coord_type]]]
                 unit_mode=False,  # type: bool
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

    def __init__(self, resolution, boundary_type, points, unit_mode=False):
        # type: (float, str, List[Tuple[Union[float, int], Union[float, int]]], bool) -> None
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
                     content,
                     ):
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
                     content,
                     resolution
                     ):
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
                  loc,
                  orient,
                  unit_mode,
                  copy,
                  ):
        new_box = self.bbox.transform(loc=loc, orient=orient, unit_mode=unit_mode)
        new_box = [[new_box.left, new_box.bottom], [new_box.right, new_box.top]]
        if copy:
            self.bbox = new_box
            return self
        else:
            return PhotonicPinInfo(
                res=self._resolution,
                net_name=self.net_name,
                pin_name=self.pin_name,
                label=self.label,
                layer=self.layer,
                bbox=new_box,
                make_rect=self.make_rect
            )
