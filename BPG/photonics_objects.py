# -*- coding: utf-8 -*-

"""This module defines various layout objects one can add and manipulate in a template.
"""
from typing import TYPE_CHECKING, Union, List, Tuple, Optional, Dict, Any, Iterator, Iterable, \
    Generator

from bag.layout.objects import Rect, Path, PathCollection, TLineBus, Polygon, Blockage, Boundary, ViaInfo, Via, PinInfo

dim_type = Union[float, int]
coord_type = Tuple[dim_type, dim_type]


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
    def lsf_export(cls, bbox, layer_prop, nx=1, ny=1, spx=0.0, spy=0.0) -> List[str]:
        """
        Describes the current rectangle shape in terms of lsf parameters for lumerical use

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

        # Calculate the width and length of the rectangle
        x_span = bbox[1][0] - bbox[0][0]
        y_span = bbox[1][1] - bbox[0][1]

        # Calculate the center of the first rectangle rounded to the nearest nm
        base_x_center = round((bbox[1][0] + bbox[0][0]) / 2, 3)
        base_y_center = round((bbox[1][1] + bbox[0][1]) / 2, 3)

        # Write the lumerical code for each rectangle in the array
        lsf_code = []
        for x_count in range(nx):
            for y_count in range(ny):
                lsf_code.append('\n')
                lsf_code.append('addrect;\n')
                lsf_code.append('set("material", "{}");\n'.format(layer_prop['material']))
                lsf_code.append('set("alpha", {});\n'.format(layer_prop['alpha']))

                # Compute the x and y coordinates for each rectangle
                lsf_code.append('set("x span", {}e-6);\n'.format(x_span))
                lsf_code.append('set("x", {}e-6);\n'.format(base_x_center + spx * x_count))
                lsf_code.append('set("y span", {}e-6);\n'.format(y_span))
                lsf_code.append('set("y", {}e-6);\n'.format(base_y_center + spy * y_count))

                # Extract the thickness values from the layermap file
                lsf_code.append('set("z min", {}e-6);\n'.format(layer_prop['z_min']))
                lsf_code.append('set("z max", {}e-6);\n'.format(layer_prop['z_max']))

        return lsf_code


class PhotonicPath(Path):
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
        if isinstance(layer, str):
            layer = (layer, 'phot')
        Path.__init__(self, resolution, layer, width, points, end_style, join_style, unit_mode)


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
                 layer,  # type: Union[str, Tuple[str, str]]
                 points,  # type: List[Tuple[Union[float, int], Union[float, int]]]
                 resolution=.001,  # type: float
                 unit_mode=False,  # type: bool
                 ):
        if isinstance(layer, str):
            layer = (layer, 'phot')
        Polygon.__init__(self, resolution, layer, points, unit_mode)

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

        # Write the lumerical code for each rectangle in the array
        lsf_code = []
        lsf_code.append('\n')
        lsf_code.append('addpoly;\n')
        lsf_code.append('set("material", "{}");\n'.format(layer_prop['material']))
        lsf_code.append('set("alpha", {});\n'.format(layer_prop['alpha']))

        lsf_code.append('V = matrix({},2);\n'.format(poly_len))  # Create matrix to hold x,y coords for vertices
        lsf_code.append('V(1:{},1) = {};\n'.format(poly_len, [point[0]*1e-6 for point in vertices]))  # Add x coord
        lsf_code.append('V(1:{},2) = {};\n'.format(poly_len, [point[1]*1e-6 for point in vertices]))  # Add y coord
        lsf_code.append('set("vertices", V);\n')

        # Extract the thickness values from the layermap file
        lsf_code.append('set("z min", {}e-6);\n'.format(layer_prop['z_min']))
        lsf_code.append('set("z max", {}e-6);\n'.format(layer_prop['z_max']))

        return lsf_code


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
            self._negative_points = []  # TODO: or none?
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


class PhotonicPinInfo(PinInfo):
    """
    A dictionary that represents a layout pin.
    """

    param_list = ['net_name', 'pin_name', 'label', 'layer', 'bbox', 'make_rect']

    def __init__(self, res, **kwargs):
        PinInfo.__init__(self, res, **kwargs)
