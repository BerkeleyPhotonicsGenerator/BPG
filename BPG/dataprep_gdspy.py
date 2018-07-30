import gdspy
from typing import Tuple, List, Union # , TYPE_CHECKING,
from math import ceil, sqrt  # , floor
# from BPG.poly_simplify import simplify_coord_to_gdspy
import numpy as np
import sys
import shapely.geometry

################################################################################
# define parameters for testing
################################################################################
# TODO: Move numbers into a tech file
global_grid_size = 0.001
global_rough_grid_size = 0.01
global_min_width = 2
global_min_space = 4
GLOBAL_OPERATION_PRECISION = 0.0001
GLOBAL_CLEAN_UP_GRID_SIZE = 0.0001
# TODO: make sure we set tolerance properly. larger numbers will cut off acute angles more when oversizing
GLOBAL_OFFSET_TOLERANCE = 4.35250
GLOBAL_DO_CLEANUP = True

MAX_SIZE = sys.maxsize

################################################################################
# clean up functions for cooedinate lists and gdspy objects
################################################################################
def coords_apprx_in_line(coord1,  # type: Tuple[float, float]
                         coord2,  # type: Tuple[float, float]
                         coord3,  # type: Tuple[float, float]
                         eps_grid=1e-4,  # type: float
                         ):
    """
    Tell if three coordinates are in the same line
    Expected to have three consecutive coordinates as inputs when the function is called
    """
    dx1_2 = coord1[0] - coord2[0]
    dy1_2 = coord1[1] - coord2[1]
    dx2_3 = coord2[0] - coord3[0]
    dy2_3 = coord2[1] - coord3[1]

    # if any of the two consecutive coords are actually the same, the three coords are in a line
    if ((abs(dx1_2) < eps_grid) and (abs(dy1_2) < eps_grid)) or ((abs(dx2_3) < eps_grid) and (abs(dy2_3) < eps_grid)):
        return True
    else:
        # if x&y coords are accurate, we should have dx1_acc * dy2_acc =dx2_acc * dy1_acc,
        # because of inaccuracy in float numbers, we have
        # |dx1 * dy2 - dx2 * dy1| = |(dx1_acc + err1) * (dy2_acc + err2) - (dx2_acc + err3) * (dy1_acc + err4)|
        #                         ~ |dx1 * err2 + dy2 * err1 - dx2 * err4 - dy1 * err3|
        #                         < sum(|dx1|, |dx2|, |dy1|, |dy2|) * |err_max|
        error_abs = abs(dx1_2 * dy2_3 - dx2_3 * dy1_2)
        error_rlt = error_abs / (abs(dx1_2) + abs(dx2_3) + abs(dy1_2) + abs(dy2_3))
        return error_rlt < eps_grid


def cleanup_loop(coords_list_ori,  # type: List[Tuple[float, float]]
                 eps_grid=1e-4,  # type: float
                 ):
    # once a coordinate is deleted from the coords list, set fully_cleaned to False
    fully_cleaned = True

    # append the first two coords in the origin list to a new list
    coords_list_out = [coords_list_ori[0], coords_list_ori[1]]

    # if the last coord in the new list has the same x or y coordinate with
    # both the second last coord and the coord to append, delete this coord
    coord_1stlast = coords_list_out[-1]
    coord_2ndlast = coords_list_out[-2]
    # print(len(coords_list_ori))
    for i in range(2, len(coords_list_ori)):
        coord_to_append = coords_list_ori[i]
        if coords_apprx_in_line(coord_2ndlast, coord_1stlast, coord_to_append, eps_grid=eps_grid):
            fully_cleaned = False
            coords_list_out = coords_list_out[:-1]
            coords_list_out.append(coord_to_append)
            coord_1stlast = coord_to_append
        else:
            coords_list_out.append(coord_to_append)
            coord_2ndlast = coord_1stlast
            coord_1stlast = coord_to_append

    # print('coord_list_out', coords_list_out)
    # now all the coordinates except the first and the last (the same one) should be on a corner of the polygon,
    # unless the following appended coord has been deleted
    # check if the firsr&last coord is redundant
    if coords_apprx_in_line(coords_list_out[-2], coords_list_out[0], coords_list_out[1], eps_grid=eps_grid):
        fully_cleaned = False
        coords_list_out = coords_list_out[1:-1]
        coords_list_out.append(coords_list_out[0])

    # LAST STEP: just in case that the first and the last coord are slightly different
    coords_list_out = coords_list_out[0:-1]
    coords_list_out.append(coords_list_out[0])

    return {'coords_list_out': coords_list_out, 'fully_cleaned': fully_cleaned}


def coords_cleanup(coords_list_ori,  # type: List[Tuple[float, float]]
                   eps_grid=1e-4,  # type: float
                   debug=False,  # type: bool
                   ):
    """
    clean up coordinates in the list that are redundant or harmful for following Shapely functions

    Parameters
    ----------
    coords_list_ori : list[tuple[float, float]]
        list of coordinates that enclose a polygon
    eps_grid : float
        a size smaller than the resolution grid size,
        if the difference of x/y coordinates of two points is smaller than it,
        these two points should actually share the same x/y coordinate
    debug : bool
    """
    if debug:
        print('coord_list_ori', coords_list_ori)

    fully_cleaned = False
    coords_list_out = coords_list_ori

    # in some cases, some coordinates become on the line if the following coord is deleted,
    # need to loop until no coord is deleted during one loop
    while not fully_cleaned:
        cleaned_result = cleanup_loop(coords_list_out, eps_grid=eps_grid)
        coords_list_out = cleaned_result['coords_list_out']
        fully_cleaned = cleaned_result['fully_cleaned']

    return coords_list_out


def dataprep_cleanup_gdspy(polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet, None]
                           do_cleanup=True  # type: bool
                           ):
    # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet, None]
    """
    Clean up a gdspy Polygon/PolygonSet by performing offset with size = 0

    First offsets by size 0 with precision higher than the global grid size.
    Then calls an explicit rounding function to the grid size.
    This is done because it is unclear how the clipper/gdspy library handles precision

    Parameters
    ----------
    polygon : Union[gdspy.Polygon, gdspy.PolygonSet]
        The polygon to clean
    do_cleanup : bool
        True to perform the cleanup. False will return input polygon unchanged
    Returns
    -------
    clean_polygon : Union[gdspy.Polygon, gdspy.PolygonSet]
        The cleaned up polygon
    """
    if do_cleanup:
        if (polygon == None):
            clean_polygon = None
        elif isinstance(polygon, (gdspy.Polygon, gdspy.PolygonSet)):
            clean_polygon = gdspy.offset(
                polygons=polygon,
                distance=0,
                tolerance=GLOBAL_OFFSET_TOLERANCE,
                max_points=MAX_SIZE,
                join_first=True,
                precision=GLOBAL_CLEAN_UP_GRID_SIZE
            )

            clean_coords = []
            if isinstance(clean_polygon, gdspy.Polygon):
                clean_coords = global_grid_size * np.round(clean_polygon.points / global_grid_size, 0)
                clean_polygon = gdspy.Polygon(points=clean_coords)
            elif isinstance(clean_polygon, gdspy.PolygonSet):
                for poly in clean_polygon.polygons:
                    clean_coords.append(global_grid_size * np.round(poly / global_grid_size, 0))
                clean_polygon = gdspy.PolygonSet(polygons=clean_coords)

        else:
            raise ValueError('input polygon must be a gdspy.Polygon, gdspy.PolygonSet or NonType')

    else:
        clean_polygon = polygon

    return clean_polygon


################################################################################
# type-converting functions for coordlist/gdspy/shapely
################################################################################
def coord_to_shapely(
        pos_neg_list_list,  # type: Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]]
        ):
    # type: (...) -> Union[Polygon, MultiPolygon]
    """
    Converts list of coordinate lists into shapely polygon objects

    Parameters
    ----------
    pos_neg_list_list

    Returns
    -------

    """
    pos_coord_list_list = pos_neg_list_list[0]
    neg_coord_list_list = pos_neg_list_list[1]

    polygon_out = shapely.geometry.Polygon(pos_coord_list_list[0]).buffer(0, cap_style=3, join_style=2)

    # print(pos_coord_list_list)
    # asgege
    if len(pos_coord_list_list) > 1:
        for pos_coord_list in pos_coord_list_list[1:]:
            polygon_pos = shapely.geometry.Polygon(pos_coord_list).buffer(0, cap_style=3, join_style=2)
            polygon_out = polygon_out.union(polygon_pos)
    if len(neg_coord_list_list):
        for neg_coord_list in neg_coord_list_list:
            polygon_neg = shapely.geometry.Polygon(neg_coord_list).buffer(0, cap_style=3, join_style=2)
            polygon_out = polygon_out.difference(polygon_neg)

    return polygon_out


def dataprep_coord_to_gdspy(pos_neg_list_list,  # type: Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]]
                            manh_grid_size,  # type: float
                            do_manh,  # type: bool
                            ):
    # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet]
    """
    Converts list of polygon coordinate lists into GDSPY polygon objects
    The expected input list will be a list of all polygons on a given layer

    Parameters
    ----------
    pos_neg_list_list : Tuple[List, List]
        A tuple containing two lists: the list of positive polygon shapes and the list of negative polygon shapes.
        Each polygon shape is a list of point tuples
    manh_grid_size : float
        The manhattanization grid size
    do_manh : bool
        True to perform Manhattanization

    Returns
    -------
    polygon_out : Union[gdspy.Polygon, gdspy.PolygonSet]
        The gdpsy.Polygon formatted polygons
    """
    pos_coord_list_list = pos_neg_list_list[0]
    neg_coord_list_list = pos_neg_list_list[1]

    # Offset by 0 to clean up shape
    polygon_out = dataprep_cleanup_gdspy(gdspy.Polygon(pos_coord_list_list[0]), do_cleanup=GLOBAL_DO_CLEANUP)

    if len(pos_coord_list_list) > 1:
        for pos_coord_list in pos_coord_list_list[1:]:
            polygon_pos = dataprep_cleanup_gdspy(gdspy.Polygon(pos_coord_list), do_cleanup=GLOBAL_DO_CLEANUP)

            polygon_out = dataprep_cleanup_gdspy(
                gdspy.fast_boolean(polygon_out, polygon_pos, 'or',
                                   precision=GLOBAL_OPERATION_PRECISION,
                                   max_points=MAX_SIZE),
                do_cleanup=GLOBAL_DO_CLEANUP
            )
    if len(neg_coord_list_list):
        for neg_coord_list in neg_coord_list_list:
            polygon_neg = dataprep_cleanup_gdspy(
                gdspy.Polygon(neg_coord_list),
                do_cleanup=GLOBAL_DO_CLEANUP
            )

            # Offset by 0 to clean up shape
            polygon_out = dataprep_cleanup_gdspy(
                gdspy.fast_boolean(polygon_out, polygon_neg, 'not',
                                   precision=GLOBAL_OPERATION_PRECISION,
                                   max_points=MAX_SIZE),
                do_cleanup=GLOBAL_DO_CLEANUP
            )

    polygon_out = gdspy_manh(polygon_out, manh_grid_size=manh_grid_size, do_manh=do_manh)

    # TODO: is the cleanup necessary
    # Offset by 0 to clean up shape
    polygon_out = dataprep_cleanup_gdspy(
        polygon_out,
        do_cleanup=GLOBAL_DO_CLEANUP
    )

    return polygon_out


def shapely_to_gdspy_polygon(polygon_shapely,  # type: shapely.geometry.Polygon
                             ):
    if not isinstance(polygon_shapely, shapely.geometry.Polygon):
        raise ValueError("input must be a Shapely Polygon")
    else:
        ext_coord_list = list(zip(*polygon_shapely.exterior.coords.xy))
        polygon_gdspy = gdspy.Polygon(ext_coord_list)
        if len(polygon_shapely.interiors):
            for interior in polygon_shapely.interiors:
                int_coord_list = list(zip(*interior.coords.xy))
                polygon_gdspy_int = gdspy.Polygon(int_coord_list)

                polygon_gdspy = dataprep_cleanup_gdspy(gdspy.fast_boolean(polygon_gdspy, polygon_gdspy_int, 'not',
                                                                          max_points=MAX_SIZE,
                                                                          precision=GLOBAL_OPERATION_PRECISION),
                                                       do_cleanup=GLOBAL_DO_CLEANUP)
        else:
            pass
        return polygon_gdspy


def shapely_to_gdspy(geom_shapely,  # type: Polygon, MultiPolygon
                     ):
    if isinstance(geom_shapely, shapely.geometry.Polygon):
        return shapely_to_gdspy_polygon(geom_shapely)
    elif isinstance(geom_shapely, shapely.geometry.MultiPolygon):
        polygon_gdspy = shapely_to_gdspy_polygon(geom_shapely[0])
        for polygon_shapely in geom_shapely[1:]:
            polygon_gdspy_append = shapely_to_gdspy_polygon(polygon_shapely)

            polygon_gdspy = dataprep_cleanup_gdspy(gdspy.fast_boolean(polygon_gdspy, polygon_gdspy_append, 'or',
                                                                      max_points=MAX_SIZE,
                                                                      precision=GLOBAL_OPERATION_PRECISION),
                                                   do_cleanup=GLOBAL_DO_CLEANUP)

        return polygon_gdspy
    else:
        raise ValueError("input must be a Shapely Polygon or a Shapely MultiPolygon")


def polyop_gdspy_to_point_list(polygon_gdspy_in,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                               fracture=True,  # type: bool
                               do_manh=True,  # type: bool
                               manh_grid_size=global_grid_size,  # type: float
                               debug=False,  # type: bool
                               # TODO: manh grid size is magic number
                               ):
    # type: (...) -> List[List[Tuple[float, float]]]
    """

    Parameters
    ----------
    polygon_gdspy_in : Union[gdspy.Polygon, gdspy.PolygonSet]
        The gdspy polygons to be converted to lists of coordinates
    fracture : bool
        True to fracture shapes
    do_manh : bool
        True to perform Manhattanization
    manh_grid_size : float
        The Manhattanization grid size
    debug : bool
        True to print debug information

    Returns
    -------
    output_list_of_coord_lists : List[List[Tuple[float, float]]]
        A list containing the polygon point lists that compose the input gdspy polygon
    """
    # TODO: Perhaps consider doing fracture to precision 0.0004, rounding explicitly to 0.001, then cleaning up duplicates
    if debug:
        print("Performing final Manhattanization")

    if do_manh:
        polygon_gdspy_in = gdspy_manh(polygon_gdspy_in, manh_grid_size=manh_grid_size, do_manh=do_manh)

    if debug:
        print("Performing final fracturing")

    if fracture:
        polygon_gdspy = polygon_gdspy_in.fracture(max_points=4094, precision=0.001)  # TODO: Magic numbers
    else:
        polygon_gdspy = polygon_gdspy_in

    output_list_of_coord_lists = []
    if isinstance(polygon_gdspy, gdspy.Polygon):
        output_list_of_coord_lists = [np.round(polygon_gdspy.points, 3)]  # TODO: Magic number?

        non_manh_edge = not_manh(polygon_gdspy.points)
        if non_manh_edge:
            print('Warning: a non-manhattanized polygon is created in polyop_gdspy_to_point_list, '
                  'number of non-manh edges is', non_manh_edge)

    elif isinstance(polygon_gdspy, gdspy.PolygonSet):
        for poly in polygon_gdspy.polygons:
            output_list_of_coord_lists.append(np.round(poly, 3))  # TODO: Magic number?

            non_manh_edge = not_manh(poly)
            if non_manh_edge:
                print('Warning: a non-manhattanized polygon is created in polyop_gdspy_to_point_list, '
                      'number of non-manh edges is', non_manh_edge)
    else:
        raise ValueError('polygon_gdspy must be a gdspy.Polygon or gdspy.PolygonSet')

    return output_list_of_coord_lists


################################################################################
# Manhattanization related functions
################################################################################
def not_manh(coord_list,  # type: List[Tuple[float, float]])
             eps_grid=1e-6,  # type: float
             ):
    non_manh_edge = 0
    if isinstance(coord_list, np.ndarray):
        coord_list_new = coord_list.tolist()
    else:
        coord_list_new = coord_list

    coord_list_new.append(coord_list_new[0])

    for i in range(len(coord_list_new) - 1):
        coord_curr = coord_list_new[i]
        coord_next = coord_list_new[i + 1]

        if (abs(coord_curr[0] - coord_next[0]) > eps_grid) and (abs(coord_curr[1] - coord_next[1]) > eps_grid):
            non_manh_edge = non_manh_edge + 1
            print(coord_curr, coord_next)
            # break

    return non_manh_edge


def manh_skill(poly_coords,  # type: List[Tuple[float, float]]
               manh_grid_size,  # type: float
               manh_type,  # type: str
               ):
    """
    Convert a polygon into the polygon with orthogonal edges,
    detailed flavors are the same as it is in the SKILL code


    Parameters
    ----------
    poly_coords : list[tuple[float, float]]
        list of coordinates that enclose a polygon
    manh_grid_size : float
        grid size for manhattanization, edge length after manhattanization should be larger than it
    manh_type : str
        'inc' : the manhattanized polygon is larger compared to the one on the manh grid
        'dec' : the manhattanized polygon is smaller compared to the one on the manh grid
        'non' : additional feature, only map the coords to the manh grid but do no manhattanization
    """

    # Snapping original coordinates to manhattan grid (by rounding)

    def apprx_equal(float1,  # type: float
                    float2,  # type: float
                    eps_grid=1e-9  # type: float
                    ):
        return abs(float1 - float2) < eps_grid

    def apprx_equal_coord(coord1,  # type: Tuple(float, float)
                          coord2,  # type: Tuple(float, float)
                          eps_grid=1e-9  # type: float
                          ):
        return apprx_equal(coord1[0], coord2[0], eps_grid) and (apprx_equal(coord1[1], coord2[0], eps_grid))

    # map the coordinates to the manh grid
    poly_coords_manhgrid = []
    for coord in poly_coords:
        xcoord_manhgrid = manh_grid_size * round(coord[0] / manh_grid_size)
        ycoord_manhgrid = manh_grid_size * round(coord[1] / manh_grid_size)
        poly_coords_manhgrid.append((xcoord_manhgrid, ycoord_manhgrid))

    # adding the first point to the last if polygon is not closed
    if not apprx_equal_coord(poly_coords_manhgrid[0], poly_coords_manhgrid[-1]):
        poly_coords_manhgrid.append(poly_coords_manhgrid[0])

    # do manhattanization if manh_type is 'inc'
    if manh_type == 'non':
        return poly_coords  # coords_cleanup(poly_coords_manhgrid)
    elif (manh_type == 'inc') or (manh_type == 'dec'):
        # Determining the coordinate of a point which is likely to be inside the convex envelope of the polygon
        # (a kind of "center-of-mass")
        xcoord_sum = 0
        ycoord_sum = 0
        for coord_manhgrid in poly_coords_manhgrid:
            xcoord_sum = xcoord_sum + coord_manhgrid[0]
            ycoord_sum = ycoord_sum + coord_manhgrid[1]
        xcoord_in = xcoord_sum / len(poly_coords_manhgrid)
        ycoord_in = ycoord_sum / len(poly_coords_manhgrid)
        # print("point INSIDE the shape (x,y) =  (%f, %f)" %(xcoord_in, ycoord_in))

        # Scanning all the points of the orinal list and adding points in-between.
        poly_coords_orth = [poly_coords_manhgrid[0]]
        # print('len(poly_coords_manhgrid)', len(poly_coords_manhgrid))
        for i in range(0, len(poly_coords_manhgrid) - 1):
            # BE CAREFUL HERE WITH THE INDEX
            coord_curr = poly_coords_manhgrid[i]
            if i == len(poly_coords_manhgrid) - 1:
                coord_next = coord_curr
            else:
                coord_next = poly_coords_manhgrid[i + 1]

            delta_x = coord_next[0] - coord_curr[0]
            delta_y = coord_next[1] - coord_curr[1]
            eps_float = 1e-9
            # current coord and the next coord create an orthogonal edge
            if (abs(delta_x) < eps_float) or (abs(delta_y) < eps_float):
                # print("This point has orthogonal neighbour", coord_curr, coord_next)
                poly_coords_orth.append(coord_next)
            else:
                if abs(delta_x) > abs(delta_y):
                    num_point_add = int(abs(round(delta_y / manh_grid_size)))
                    xstep = round(delta_y / abs(delta_y)) * manh_grid_size * (delta_x / delta_y)
                    ystep = round(delta_y / abs(delta_y)) * manh_grid_size
                else:
                    num_point_add = int(abs(round(delta_x / manh_grid_size)))
                    ystep = round(delta_x / abs(delta_x)) * manh_grid_size * delta_y / delta_x
                    xstep = round(delta_x / abs(delta_x)) * manh_grid_size
                # if positive, the center if the shape is on the left
                vec_product1 = xstep * (ycoord_in - coord_curr[1]) - ystep * (xcoord_in - coord_curr[0])
                # if positive the vector ( StepX, 0.0) is on the left too
                vec_product2 = xstep * 0.0 - ystep * xstep
                for j in range(0, num_point_add):
                    x0 = coord_curr[0] + j * xstep
                    y0 = coord_curr[1] + j * ystep
                    # If both are positive, incrememnting in X first will make the polygon smaller:
                    # incrememnting X first if manh_type is 'inc'
                    if ((vec_product1 * vec_product2) < 0) == (manh_type == 'inc'):
                        poly_coords_orth.append((x0 + xstep, y0))
                        poly_coords_orth.append((x0 + xstep, y0 + ystep))
                    # else incrememnting Y first
                    else:
                        poly_coords_orth.append((x0, y0 + ystep))
                        poly_coords_orth.append((x0 + xstep, y0 + ystep))

        # clean up the coords
        non_manh_edge_pre_cleanup = not_manh(poly_coords_orth)
        if non_manh_edge_pre_cleanup:
            raise ValueError('Manhattanization failed before the clean-up, number of non-manh edges is',
                             non_manh_edge_pre_cleanup)

        poly_coords_cleanup = coords_cleanup(poly_coords_orth)
        non_manh_edge_post_cleanup = not_manh(poly_coords_cleanup)
        if non_manh_edge_post_cleanup:
            raise ValueError('Manhattanization failed after the clean-up, number of non-manh edges is',
                             non_manh_edge_post_cleanup)

        return poly_coords_cleanup
    else:
        raise ValueError('manh_type = {} should be either "non", "inc" or "dec"'.format(manh_type))


def gdspy_manh(polygon_gdspy,  # type: Union[gdspy.Polygon, gdspy.PolygonSet, None]
               manh_grid_size,  # type: float
               do_manh,  # type: bool
               ):
    if do_manh:
        manh_type = 'inc'
    else:
        manh_type = 'non'

    if polygon_gdspy == None:
        polygon_out = None
    elif isinstance(polygon_gdspy, gdspy.Polygon):
        coord_list = manh_skill(polygon_gdspy.points, manh_grid_size, manh_type)
        polygon_out = dataprep_cleanup_gdspy(gdspy.Polygon(coord_list),
                                             do_cleanup=GLOBAL_DO_CLEANUP)
    elif isinstance(polygon_gdspy, gdspy.PolygonSet):
        coord_list = manh_skill(polygon_gdspy.polygons[0], manh_grid_size, manh_type)
        polygon_out = dataprep_cleanup_gdspy(gdspy.Polygon(coord_list),
                                             do_cleanup=GLOBAL_DO_CLEANUP)
        for poly in polygon_gdspy.polygons:
            coord_list = manh_skill(poly, manh_grid_size, manh_type)
            polygon_append = dataprep_cleanup_gdspy(gdspy.Polygon(coord_list),
                                                    do_cleanup=GLOBAL_DO_CLEANUP)
            polygon_out = dataprep_cleanup_gdspy(gdspy.fast_boolean(polygon_out, polygon_append, 'or'),
                                                 do_cleanup=GLOBAL_DO_CLEANUP)
    else:
        raise ValueError('polygon_gdspy should be either a Polygon or PolygonSet')

    return polygon_out


################################################################################
# Simplify function
################################################################################
def simplify_coord_to_gdspy(pos_neg_list_list,
                            # type: Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]]
                            tolerance=5e-4,  # type: float
                            ):
    poly_shapely = coord_to_shapely(pos_neg_list_list)
    poly_shapely_simplified = poly_shapely.simplify(tolerance)
    poly_gdspy_simplified = shapely_to_gdspy(poly_shapely_simplified)

    return poly_gdspy_simplified


################################################################################
# Dataprep related operations
################################################################################
def dataprep_oversize_gdspy(polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet, None]
                            offset,  # type: float
                            ):
    # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet, None]

    if (polygon == None):
        return None
    else:
        if offset < 0:
            print('Warning: offset = %f < 0 indicates you are doing undersize')
        polygon_oversized = gdspy.offset(polygon, offset, max_points=MAX_SIZE, join_first=True,
                                         join='miter', tolerance=GLOBAL_OFFSET_TOLERANCE, precision=GLOBAL_OPERATION_PRECISION)
        polygon_oversized = dataprep_cleanup_gdspy(polygon_oversized, do_cleanup=GLOBAL_DO_CLEANUP)

        return polygon_oversized


def dataprep_undersize_gdspy(polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet, None]
                             offset,  # type: float
                             ):
    # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet, None]

    if (polygon == None):
        return None
    else:
        if offset < 0:
            print('Warning: offset = %f < 0 indicates you are doing oversize')
        polygon_undersized = gdspy.offset(polygon, -offset, max_points=MAX_SIZE, join_first=True,
                                          join='miter', tolerance=GLOBAL_OFFSET_TOLERANCE, precision=GLOBAL_OPERATION_PRECISION)
        polygon_undersized = dataprep_cleanup_gdspy(polygon_undersized, do_cleanup=GLOBAL_DO_CLEANUP)

        return polygon_undersized


def dataprep_roughsize_gdspy(polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                             size_amount,  # type: float
                             do_manh,  # type: bool
                             ):
    rough_grid_size = global_rough_grid_size

    # oversize twice, then undersize twice and oversize again
    polygon_oo = dataprep_oversize_gdspy(polygon, 2 * rough_grid_size)
    polygon_oouu = dataprep_undersize_gdspy(polygon_oo, 2 * rough_grid_size)
    polygon_oouuo = dataprep_oversize_gdspy(polygon_oouu, rough_grid_size)

    # manhattanize to the rough grid
    polygon_oouuo_rough = gdspy_manh(polygon_oouuo, rough_grid_size, do_manh)

    # undersize then oversize
    polygon_roughsized = dataprep_oversize_gdspy(dataprep_undersize_gdspy(polygon_oouuo_rough, global_grid_size),
                                                 global_grid_size)

    polygon_roughsized = dataprep_oversize_gdspy(polygon_roughsized, max(size_amount - 2 * global_grid_size, 0))

    return polygon_roughsized


def poly_operation(polygon1,  # type: Union[gdspy.Polygon, gdspy.PolygonSet, None]
                   polygon2,  # type: Union[gdspy.Polygon, gdspy.PolygonSet, None]
                   operation,  # type: str
                   size_amount,  # type: float
                   do_manh=False,  # type: bool
                   ):
    # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet]
    """

    Parameters
    ----------
    polygon1 : Union[gdspy.Polygon, gdspy.PolygonSet, None]
        The shapes currently on the output layer
    polygon2 : Union[gdspy.Polygon, gdspy.PolygonSet, None]
        The shapes on the input layer that will be added/subtracted to/from the output layer
    operation : str
        The operation to perform:  'rad', 'add', 'sub', 'ext', 'ouo', 'del'
    size_amount : float
        The amount to over/undersize the shapes to be added/subtracted
    do_manh : bool
        True to perform manhattanization during the 'rad' operation

    Returns
    -------
    polygons_out : Union[gdspy.Polygon, gdspy.PolygonSet]
        The new polygons present on the output layer
    """
    # TODO: clean up the input polygons first ?

    # TODO: properly get the grid size from a tech file
    grid_size = global_grid_size

    # If there are no shapes to operate on, return the shapes currently on the output layer
    if polygon2 is None:
        return polygon1
    else:
        if operation == 'rad':
            # TODO: manh ?
            polygon_rough = dataprep_roughsize_gdspy(polygon2, size_amount=size_amount, do_manh=do_manh)

            buffer_size = max(size_amount - 2 * global_rough_grid_size, 0)
            polygon_rough_sized = dataprep_oversize_gdspy(polygon_rough, buffer_size)

            if polygon1 is None:
                polygon_out = polygon_rough_sized
            else:
                polygon_out = gdspy.fast_boolean(polygon1, polygon_rough_sized, 'or')
                polygon_out = dataprep_cleanup_gdspy(polygon_out, do_cleanup=GLOBAL_DO_CLEANUP)

        elif operation == 'add':
            if polygon1 is None:
                polygon_out = dataprep_oversize_gdspy(polygon2, size_amount)
            else:
                polygon_out = gdspy.fast_boolean(polygon1, dataprep_oversize_gdspy(polygon2, size_amount), 'or')
                polygon_out = dataprep_cleanup_gdspy(polygon_out, do_cleanup=GLOBAL_DO_CLEANUP)

        elif operation == 'sub':
            if polygon1 is None:
                polygon_out = None
            else:
                # TODO: Over or undersize the subtracted poly
                polygon_out = gdspy.fast_boolean(polygon1, dataprep_oversize_gdspy(polygon2, size_amount), 'not')
                polygon_out = dataprep_cleanup_gdspy(polygon_out, GLOBAL_DO_CLEANUP)

        elif operation == 'ext':
            # TODO:
            # if (not (member(LppOut, NotToExtendOrOverUnderOrUnderOverLpps) != nil)):
            if True:
                polygon_toextend = polygon1
                polygon_ref = polygon2
                extended_amount = size_amount

                grid_size = global_grid_size
                extended_amount = grid_size * ceil(extended_amount / grid_size)
                polygon_ref_sized = dataprep_oversize_gdspy(polygon_ref, extended_amount)
                polygon_extended = dataprep_oversize_gdspy(polygon_toextend, extended_amount)
                polygon_extra = dataprep_cleanup_gdspy(gdspy.fast_boolean(polygon_extended, polygon_ref, 'not'),
                                                       do_cleanup=GLOBAL_DO_CLEANUP)
                polygon_toadd = dataprep_cleanup_gdspy(gdspy.fast_boolean(polygon_extra, polygon_ref_sized, 'and'),
                                                       do_cleanup=GLOBAL_DO_CLEANUP)

                polygon_out = dataprep_cleanup_gdspy(gdspy.fast_boolean(polygon_toextend, polygon_toadd, 'or'),
                                                     do_cleanup=GLOBAL_DO_CLEANUP)

                # TODO: replace 1.1 with non-magic number
                buffer_size = max(grid_size * ceil(0.5 * extended_amount / grid_size + 1.1), 0.0)
                polygon_out = dataprep_oversize_gdspy(dataprep_undersize_gdspy(polygon_out, buffer_size), buffer_size)


            else:
                pass

        elif operation == 'ouo':
            # TODO
            # if (not (member(LppIn NotToExtendOrOverUnderOrUnderOverLpps) != nil)):
            if True:
                min_width = global_min_width
                min_space = global_min_space

                underofover_size = grid_size * ceil(0.5 * min_space / grid_size)
                overofunder_size = grid_size * ceil(0.5 * min_width / grid_size)
                print('ouuo size:', underofover_size, overofunder_size)
                polygon_o = dataprep_oversize_gdspy(polygon2, underofover_size)
                polygon_ou = dataprep_undersize_gdspy(polygon_o, underofover_size)
                polygon_ouu = dataprep_undersize_gdspy(polygon_ou, overofunder_size)
                polygon_out = dataprep_oversize_gdspy(polygon_ouu, overofunder_size)

            else:
                pass

        elif operation == 'rouo':
            if (polygon2 == None):
                polygon_out = None
            else:
                rough_grid_size = global_rough_grid_size
                grid_size = global_grid_size
                min_width = global_min_width
                min_space = global_min_space
                underofover_size = grid_size * ceil(0.5 * min_space / grid_size)
                overofunder_size = grid_size * ceil(0.5 * min_width / grid_size)

                min_space_width = min(min_space, min_width)
                simplify_tolerance = 0.999 * min_space_width * rough_grid_size / sqrt(
                    min_space_width ** 2 + rough_grid_size ** 2)
                # simplify_tolerance = 1.4 * rough_grid_size

                # TODO: see if do_manh should always be True here
                polygon_manh = gdspy_manh(polygon2, rough_grid_size, do_manh=True)

                polygon_o = dataprep_oversize_gdspy(polygon_manh, underofover_size)
                polygon_ou = dataprep_undersize_gdspy(polygon_o, underofover_size)
                polygon_ouu = dataprep_undersize_gdspy(polygon_ou, overofunder_size)
                polygon_ouuo = dataprep_oversize_gdspy(polygon_ouu, overofunder_size)

                coord_list = polyop_gdspy_to_point_list(polygon_ouuo,
                                                        fracture=False,
                                                        do_manh=False,
                                                        manh_grid_size=global_grid_size,
                                                        debug=False
                                                        )
                polygon_simplified = simplify_coord_to_gdspy([coord_list, []],
                                                             # TODO: Figure out the magic number
                                                             tolerance=simplify_tolerance,
                                                             )
                # polygon_simplified = polygon_ouuo

                polygon_out = polygon_simplified


        elif operation == 'del':
            # TODO
            polygon_out = None
            pass

        return polygon_out





