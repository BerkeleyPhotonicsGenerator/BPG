
import gdspy
from typing import Tuple, List, Union  #, TYPE_CHECKING,
from math import ceil  # , floor
from BPG.manh_gdspy import gdspy_manh, not_manh  # ,coords_cleanup
import numpy as np
import sys


################################################################################
# define parameters for testing
################################################################################
# TODO: Move numbers into a tech file
global_grid_size = 0.001
global_rough_grid_size = 0.1
global_min_width = 0.1
global_min_space = 0.05
GLOBAL_OPERATION_PRECISION = 0.0001
GLOBAL_CLEAN_UP_GRID_SIZE = 0.0001
# TODO: make sure we set tolerance properly. larger numbers will cut off acute angles more when oversizing
GLOBAL_OFFSET_TOLERANCE = 10
GLOBAL_DO_CLEANUP = True

MAX_SIZE = sys.maxsize


def polyop_gdspy_to_point_list(polygon_gdspy_in,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                               fracture=True,  # type: bool
                               do_manh=True,  # type: bool
                               manh_grid_size=global_grid_size  # type: float
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

    Returns
    -------
    output_list_of_coord_lists : List[List[Tuple[float, float]]]
        A list containing the polygon point lists that compose the input gdspy polygon
    """
    # TODO: Perhaps consider doing fraction to precision 0.0004, rounding explicitly to 0.001, then cleaning up duplicates
    if do_manh:
        polygon_gdspy_in = gdspy_manh(polygon_gdspy_in, manh_grid_size=manh_grid_size, do_manh=do_manh)




    fracture = False
    if fracture:
        polygon_gdspy = polygon_gdspy_in.fracture(max_points=4094, precision=0.001)  # TODO: Magic numbers
    else:
        polygon_gdspy = polygon_gdspy_in


    # #### debug: check if the polygons are manhattanized
    # if isinstance(polygon_gdspy, gdspy.Polygon):
    #     non_manh_edge = not_manh(polygon_gdspy.points)
    #     if non_manh_edge:
    #         print('Warning: a non-manhattanized polygon is created in polyop_gdspy_to_point_list, '
    #               'number of non-manh edges is', non_manh_edge)
    # elif isinstance(polygon_gdspy, gdspy.PolygonSet):
    #         non_manh_edge = not_manh(poly)
    #         if non_manh_edge:
    #             print('Warning: a non-manhattanized polygon is created in polyop_gdspy_to_point_list, '
    #                   'number of non-manh edges is', non_manh_edge)
    # else:
    #     raise ValueError('polygon_gdspy must be a gdspy.Polygon or gdspy.PolygonSet')
    #

    output_list_of_coord_lists = []
    if isinstance(polygon_gdspy, gdspy.Polygon):
        output_list_of_coord_lists = [np.round(polygon_gdspy.points, 3)]  # TODO: Magic number?
        # print('check ismanh for the output')
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


def dataprep_coord_to_gdspy(
        pos_neg_list_list,  # type: Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]]
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


def dataprep_cleanup_gdspy(polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                           do_cleanup=True  # type: bool
                           ):
    # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet]
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
            clean_polygon = gdspy.Polygon(points = clean_coords)
        elif isinstance(clean_polygon, gdspy.PolygonSet):
            for poly in clean_polygon.polygons:
                clean_coords.append(global_grid_size * np.round(poly / global_grid_size, 0))
            clean_polygon = gdspy.PolygonSet(polygons=clean_coords)
        else:
            raise ValueError('clean polygon must be a gdspy.Polygon or gdspy.PolygonSet')

    else:
        clean_polygon = polygon

    return clean_polygon


def dataprep_oversize_gdspy(polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                            offset,  # type: float
                            ):
    # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet]

    if offset < 0:
        print('Warning: offset = %f < 0 indicates you are doing undersize')
    polygon_oversized = gdspy.offset(polygon, offset, max_points=MAX_SIZE, join_first=True,
                                     join='miter', tolerance=4, precision=GLOBAL_OPERATION_PRECISION)
    polygon_oversized = dataprep_cleanup_gdspy(polygon_oversized, do_cleanup=GLOBAL_DO_CLEANUP)

    return polygon_oversized


def dataprep_undersize_gdspy(polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                             offset,  # type: float
                             ):
    # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet]

    if offset < 0:
        print('Warning: offset = %f < 0 indicates you are doing oversize')
    polygon_undersized = gdspy.offset(polygon, -offset, max_points=MAX_SIZE, join_first=True,
                                      join='miter', precision=GLOBAL_OPERATION_PRECISION)
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


def polyop_extend(polygon_toextend,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                  polygon_ref,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                  extended_amount,  # type: float
                  ):
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

    return polygon_out


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
                polygon_out = polyop_extend(polygon_toextend, polygon_ref, size_amount)
            else:
                pass

        elif operation == 'ouo':
            # TODO
            # if (not (member(LppIn NotToExtendOrOverUnderOrUnderOverLpps) != nil)):
            if True:
                min_width = global_min_width
                min_space = global_min_width

                underofover_size = grid_size * ceil(0.5 * min_space / grid_size)
                overofunder_size = grid_size * ceil(0.5 * min_width / grid_size)
                polygon_o = dataprep_oversize_gdspy(polygon2, underofover_size)
                polygon_ou = dataprep_undersize_gdspy(polygon_o, underofover_size)
                polygon_ouu = dataprep_undersize_gdspy(polygon_ou, overofunder_size)
                polygon_out = dataprep_oversize_gdspy(polygon_ouu, overofunder_size)

            else:
                pass

        elif operation == 'del':
            # TODO
            polygon_out = None
            pass

        return polygon_out
