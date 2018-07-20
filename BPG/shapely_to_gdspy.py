# from math import ceil, floor
# from matplotlib import pyplot
# from descartes import PolygonPatch
# from shapely.ops import cascaded_union
# from shapely.ops import polygonize_full, polygonize
from typing import TYPE_CHECKING, List
import shapely.geometry
import gdspy
import numpy as np

if TYPE_CHECKING:
    pass

# import os

# from figures import SIZE, BLUE, GRAY, set_limits


def plot_coords(ax, x, y, color='#999999', zorder=1):
    ax.plot(x, y, 'o', color=color, zorder=zorder)


def plot_line(ax, ob, color='r'):
    parts = hasattr(ob, 'geoms') and ob or [ob]
    for part in parts:
        x, y = part.xy
        ax.plot(x, y, color=color, linewidth=3, solid_capstyle='round', zorder=1)


def polyop_shapely2gdspy_polygon(polygon_shapely,  # type: shapely.geometry.Polygon
                                 ):
    # type: (...) -> List

    if polygon_shapely.type != 'Polygon':
        raise ValueError('Unhandled geometry type: ' + repr(polygon_shapely.type) + ', type should be Polygon')

    coords_ext_shapely = list(zip(*polygon_shapely.exterior.coords.xy))
    # delete the last coord in the shapely coord list which is the same as the first coord,
    # since it is not needed in gdspy
    coords_ext_gdspy = coords_ext_shapely[:-1]
    # create the initial polygon in gdspy
    polygon_gdspy = gdspy.Polygon(coords_ext_gdspy)

    # do subtract for each hole in the polygon
    if len(polygon_shapely.interiors):
        for interior in polygon_shapely.interiors:
            coords_int_shapely = list(zip(*interior.coords.xy))
            coords_int_gdspy = coords_int_shapely[:-1]
            polygon_int_gdspy = gdspy.Polygon(coords_int_gdspy)
            polygon_gdspy = gdspy.fast_boolean(polygon_gdspy, polygon_int_gdspy, 'not')

    # TODO: Rounding properly
    output_list_of_coord_lists = []
    if isinstance(polygon_gdspy, gdspy.Polygon):
        output_list_of_coord_lists = [np.round(polygon_gdspy.points, 3)]
    elif isinstance(polygon_gdspy, gdspy.PolygonSet):
        for poly in polygon_gdspy.polygons:
            output_list_of_coord_lists.append(np.round(poly, 3))
    else:
        raise ValueError('got bad return type from gdspy.fast_boolean in polyop_shapely2gdspy_Polygon')
    return output_list_of_coord_lists


def polyop_shapely2gdspy(geom_shapely,  # type: shapely.geometry.Polygon, shapely.geometry.MultiPolygon
                         ):
    # type: (...) -> List
    """
    This function converts a Shapely Polygon/MultiPolygon object to a gdspy Polygon/PolygonSet object

    The returned List is a list of coordinate lists, that composes the set of all polygons that form all objects on a
    layer. The polygons are already fractured, so holes are "keyholed", and no further manipulation needs to be done
    """
    # TODO: round properly
    if geom_shapely.type == 'Polygon':
        return polyop_shapely2gdspy_polygon(geom_shapely)
    elif geom_shapely.type == 'MultiPolygon':
        # geom_gdspy = polyop_shapely2gdspy_Polygon(geom_shapely[0])
        # for polygon_shapely in geom_shapely[1:]:
        #     geom_new = polyop_shapely2gdspy_Polygon(polygon_shapely)
        #     geom_gdspy = gdspy.fast_boolean(geom_gdspy, geom_new, 'or')
        #
        # coords_out = []
        # for coords in geom_gdspy.polygons:
        #     coords_out.append(np.round(coords, 3))
        # return coords_out
        coords_out = []
        for polygon_shapely in geom_shapely:
            coords_out.extend(polyop_shapely2gdspy_polygon(polygon_shapely))
        return coords_out

    else:
        raise ValueError('Unhandled geometry type: ' + repr(geom_shapely.type) +
                         'type should be either "Polygon" or "MultiPolygon"')


'''
ring_ext = gdspy.Polygon([(0, -8), (0, -4), (4, -4), (4, 4), (-4, 4), (-4, -4), (0, -4),
                       (0, -8), (-8, -8), (-8, 8), (8, 8), (8, -8)])
ring_origin = ring_ext
ring_int = gdspy.Polygon([(-6, -6), (-6, 6), (6, 6), (6, -6)])
ring_origin = gdspy.fast_boolean(ring_origin, ring_int, 'not')

ring_origin = gdspy.fast_boolean(gdspy.Round((8, 8), 4), gdspy.Round((8, 8), 2), 'not')

island = gdspy.Polygon([(-4, -4), (-4, 4), (4, 4), (4, -4)])
ring_origin = gdspy.fast_boolean(ring_origin, island, 'or')


# shape = gdspy.offset(ring_origin, distance=1)

shape = ring_origin
shape = gdspy.offset(ring_origin, 0, tolerance=100, max_points=4000)
# shape = gdspy.offset(shape, 1, tolerance=100, max_points=4000)


ring_origin = (shapely.geometry.Point(8.0, 8.0).buffer(32, resolution=128)).difference\
              (shapely.geometry.Point(0.00, 0.00).buffer(11, resolution=128).union
              (shapely.geometry.Point(16.00, 16.00).buffer(11, resolution=128).difference
              (shapely.geometry.Point(16.00, 16.00).buffer(7, resolution=128))\
                                                           ))


geom_shapely = ring_origin.buffer(2, cap_style=3, join_style=2)
shape = polyop_shapely2gdspy(geom_shapely)


print('shape', shape)
gdslib = gdspy.GdsLibrary(name='gdslib')
gdscell = gdspy.Cell(name='ring', exclude_from_current=True)
gdscell.add(shape)
gdslib.add(gdscell)

try:
    os.remove('gds_ring.gds')
except:
    pass
gdslib.write_gds('gds_ring.gds', unit=1.0e-6, precision=1.0e-9)

# gdspy.LayoutViewer()

# dgssg

# ring_origin = Polygon([(0, -8), (0, -4), (4, -4), (4, 4), (-4, 4), (-4, -4), (0, -4),
#                        (0, -8), (-8, -8), (-8, 8), (8, 8), (8, -8), (0, -8)]).buffer(0).difference(
#               Polygon([(-6, -6), (-6, 6), (6, 6), (6, -6), (-6, -6)]))
#
#
# ring_origin = Polygon([(0, -8), (0, -12), (0, -8), (-8, -8), (-8, 8), (8, 8), (8, -8), (0, -8)]).difference(
#               Polygon([(-6, -6), (-6, 6), (6, 6), (6, -6), (-6, -6)]))
#
#
# ring_ext = Polygon([(-40, -40), (-40, 40), (40, 40), (40, -40), (-40, -40)])
# ring_int = Polygon([(-20, -20), (-20, 20), (20, 20), (20, -20), (-20, -20)])
# ring_origin = ring_ext.difference(ring_int)
#
#
# ring_origin = (Point(8.0, 8.0).buffer(32, cap_style=3, join_style=2)).difference\
#               (Point(00.00, 00.00).buffer(8, cap_style=3, join_style=2).union
#               (Point(16.00, 16.00).buffer(8, cap_style=3, join_style=2)))


# print(ring_origin)

# manh_grid_size = [2, 1, 0.5, 0.25, 0.1]
#
# ring_manh1 = polyop_manh(ring_origin, manh_grid_size[0], do_manh=True)
# ring_manh2 = polyop_manh(ring_origin, manh_grid_size[1], do_manh=True)
# ring_manh3 = polyop_manh(ring_origin, manh_grid_size[2], do_manh=True)
# ring_manh4 = polyop_manh(ring_origin, manh_grid_size[3], do_manh=True)
# ring_manh5 = polyop_manh(ring_origin, manh_grid_size[4], do_manh=True)
#
# ring_manh1_pre = polyop_manh(ring_origin, manh_grid_size[0], do_manh=False)
# ring_manh2_pre = polyop_manh(ring_origin, manh_grid_size[1], do_manh=False)
# ring_manh3_pre = polyop_manh(ring_origin, manh_grid_size[2], do_manh=False)
# ring_manh4_pre = polyop_manh(ring_origin, manh_grid_size[3], do_manh=False)
# ring_manh5_pre = polyop_manh(ring_origin, manh_grid_size[4], do_manh=False)
#
#
#
#
#
#
# fig = pyplot.figure(1, dpi=90)
#
# #1
# ax = fig.add_subplot(231)
# plot_coords(ax, 0, 0)
#
# plot_line(ax, ring_origin.boundary, color='b')
# ax.add_patch(PolygonPatch(ring_origin.__geo_interface__, fc='b', ec='b', alpha=0.5, zorder=2))
# ax.set_title('1) original polygon')
# # print(poly_origin)
#
#
# #2
# ax = fig.add_subplot(232)
# plot_coords(ax, 0, 0)
#
# plot_line(ax, ring_manh1.boundary, color='b')
# ax.add_patch(PolygonPatch(ring_manh1.__geo_interface__, fc='b', ec='b', alpha=0.5, zorder=2))
# plot_line(ax, ring_manh1_pre.boundary, color='r')
# ax.add_patch(PolygonPatch(ring_manh1_pre.__geo_interface__, fc='r', ec='r', alpha=0.5, zorder=2))
# ax.set_title('2) ')
#
#
# #3
# ax = fig.add_subplot(233)
# plot_coords(ax, 0, 0)
#
# plot_line(ax, ring_manh2.boundary, color='b')
# ax.add_patch(PolygonPatch(ring_manh2.__geo_interface__, fc='b', ec='b', alpha=0.5, zorder=2))
# plot_line(ax, ring_manh2_pre.boundary, color='r')
# ax.add_patch(PolygonPatch(ring_manh2_pre.__geo_interface__, fc='r', ec='r', alpha=0.5, zorder=2))
# ax.set_title('3) ')
#
#
# #4
# ax = fig.add_subplot(234)
# plot_coords(ax, 0, 0)
#
# plot_line(ax, ring_manh3.boundary, color='b')
# ax.add_patch(PolygonPatch(ring_manh3.__geo_interface__, fc='b', ec='b', alpha=0.5, zorder=2))
# plot_line(ax, ring_manh3_pre.boundary, color='r')
# ax.add_patch(PolygonPatch(ring_manh3_pre.__geo_interface__, fc='r', ec='r', alpha=0.5, zorder=2))
# ax.set_title('4) ')
#
#
# #5
# ax = fig.add_subplot(235)
# plot_coords(ax, 0, 0)
#
# plot_line(ax, ring_manh4.boundary, color='b')
# ax.add_patch(PolygonPatch(ring_manh4.__geo_interface__, fc='b', ec='b', alpha=0.5, zorder=2))
# plot_line(ax, ring_manh4_pre.boundary, color='r')
# ax.add_patch(PolygonPatch(ring_manh4_pre.__geo_interface__, fc='r', ec='r', alpha=0.5, zorder=2))
# ax.set_title('5) ')
#
# #6
# ax = fig.add_subplot(236)
# plot_coords(ax, 0, 0)
#
# plot_line(ax, ring_manh5.boundary, color='b')
# ax.add_patch(PolygonPatch(ring_manh5.__geo_interface__, fc='b', ec='b', alpha=0.5, zorder=2))
# plot_line(ax, ring_manh5_pre.boundary, color='r')
# ax.add_patch(PolygonPatch(ring_manh5_pre.__geo_interface__, fc='r', ec='r', alpha=0.5, zorder=2))
# ax.set_title('6) ')
#
#
#
#
# pyplot.show()
'''