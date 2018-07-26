from shapely.geometry import Polygon, MultiPolygon
from typing import Union, Tuple, List
from math import ceil, sqrt
import sys
import gdspy

MAX_POINTS = sys.maxsize




def coord_to_shapely(
        pos_neg_list_list,  # type: Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]]
        ):
    # type: (...) -> Union[Polygon, MultiPolygon]
    """
    Converts list of coordinate lists into shapely polygon objects

    Parameters
    ----------
    pos_neg_list_list
    manh_grid_size

    Returns
    -------

    """
    pos_coord_list_list = pos_neg_list_list[0]
    neg_coord_list_list = pos_neg_list_list[1]

    polygon_out = Polygon(pos_coord_list_list[0]).buffer(0, cap_style=3, join_style=2)

    # print(pos_coord_list_list)
    # asgege
    if len(pos_coord_list_list) > 1:
        for pos_coord_list in pos_coord_list_list[1:]:
            polygon_pos = Polygon(pos_coord_list).buffer(0, cap_style=3, join_style=2)
            polygon_out = polygon_out.union(polygon_pos)
    if len(neg_coord_list_list):
        for neg_coord_list in neg_coord_list_list:
            polygon_neg = Polygon(neg_coord_list).buffer(0, cap_style=3, join_style=2)
            polygon_out = polygon_out.difference(polygon_neg)

    return polygon_out


def shapely_to_gdspy_polygon(polygon_shapely, # type: Polygon
                             ):
    if not isinstance(polygon_shapely, Polygon):
        raise ValueError("input must be a Shapely Polygon")
    else:
        ext_coord_list = list(zip(*polygon_shapely.exterior.coords.xy))
        polygon_gdspy = gdspy.Polygon(ext_coord_list)
        if len(polygon_shapely.interiors):
            for interior in polygon_shapely.interiors:
                int_coord_list = list(zip(*interior.coords.xy))
                polygon_gdspy_int = gdspy.Polygon(int_coord_list)

                polygon_gdspy = gdspy.fast_boolean(polygon_gdspy, polygon_gdspy_int, 'not', max_points=MAX_POINTS)
        else:
            pass
        return polygon_gdspy


def shapely_to_gdspy(geom_shapely, # type: Polygon, MultiPolygon
                     ):
    if isinstance(geom_shapely, Polygon):
        return shapely_to_gdspy_polygon(geom_shapely)
    elif isinstance(geom_shapely, MultiPolygon):
        polygon_gdspy = shapely_to_gdspy_polygon(geom_shapely[0])
        for polygon_shapely in geom_shapely[1:]:
            polygon_gdspy_append = shapely_to_gdspy_polygon(polygon_shapely)

            polygon_gdspy = gdspy.fast_boolean(polygon_gdspy, polygon_gdspy_append, 'or', max_points=MAX_POINTS)

        return polygon_gdspy
    else:
        raise ValueError("input must be a Shapely Polygon or a Shapely MultiPolygon")



def num_of_sparse_point_round(radius, # type: float
                              res_grid_size, # type: float
                              ):
    # type: (...) -> int

    pi = 355 / 113
    return int(ceil(pi / sqrt(res_grid_size / radius)))

def simplify_coord_to_gdspy(pos_neg_list_list,  # type: Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]]
                            tolerance=5e-4,     # type: float
                            ):
    poly_shapely = coord_to_shapely(pos_neg_list_list)
    poly_shapely_simplified = poly_shapely.simplify(tolerance)
    poly_gdspy_simplified = shapely_to_gdspy(poly_shapely_simplified)

    return poly_gdspy_simplified