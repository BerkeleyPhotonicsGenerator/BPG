
import gdspy
from typing import Tuple, List, Union  #, TYPE_CHECKING,
from math import ceil  # , floor
from BPG.manh import gdspy_manh  # ,coords_cleanup
import numpy as np
import sys


################################################################################
# define parameters for testing
################################################################################
global_grid_size = 0.001
global_rough_grid_size = 0.01
global_min_width = 0.02
global_min_space = 0.05
MAX_SIZE = sys.maxsize


def polyop_gdspy_to_point_list(polygon_gdspy_in,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                               fracture=True,  # type: bool
                               ):
    # type: (...) -> List

    if fracture:
        polygon_gdspy = polygon_gdspy_in.fracture(max_points=4094, precision=0.001)
    else:
        polygon_gdspy = polygon_gdspy_in

    # TODO: Rounding properly
    output_list_of_coord_lists = []
    if isinstance(polygon_gdspy, gdspy.Polygon):
        output_list_of_coord_lists = [np.round(polygon_gdspy.points, 3)]
    elif isinstance(polygon_gdspy, gdspy.PolygonSet):
        for poly in polygon_gdspy.polygons:
            output_list_of_coord_lists.append(np.round(poly, 3))
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
    Converts list of coordinate lists into GDSPY polygon objects
    The expected input list will be a list of all polygons on a given layer

    Parameters
    ----------
    pos_neg_list_list
    manh_grid_size
    do_manh

    Returns
    -------

    """
    pos_coord_list_list = pos_neg_list_list[0]
    neg_coord_list_list = pos_neg_list_list[1]

    polygon_out = gdspy.offset(gdspy.Polygon(pos_coord_list_list[0]),
                               0, tolerance=10, max_points=MAX_SIZE, join_first=True)

    if len(pos_coord_list_list) > 1:
        for pos_coord_list in pos_coord_list_list[1:]:
            polygon_pos = gdspy.offset(gdspy.Polygon(pos_coord_list),
                                       0, tolerance=10, max_points=MAX_SIZE, join_first=True)
            polygon_out = gdspy.offset(gdspy.fast_boolean(polygon_out, polygon_pos, 'or'),
                                       0, tolerance=10, max_points=MAX_SIZE, join_first=True)
    if len(neg_coord_list_list):
        for neg_coord_list in neg_coord_list_list:
            polygon_neg = gdspy.offset(gdspy.Polygon(neg_coord_list),
                                       0, tolerance=10, max_points=MAX_SIZE, join_first=True)
            polygon_out = gdspy.offset(gdspy.fast_boolean(polygon_out, polygon_neg, 'not'),
                                       0, tolerance=10, max_points=MAX_SIZE, join_first=True)

    polygon_out = gdspy_manh(polygon_out, manh_grid_size=manh_grid_size, do_manh=do_manh)
    polygon_out = gdspy.offset(polygon_out, 0, max_points=MAX_SIZE, join_first=True)
    return polygon_out


def dataprep_oversize_gdspy(polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                            offset,  # type: float
                            ):
    # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet]

    if offset < 0:
        print('Warning: offset = %f < 0 indicates you are doing undersize')
    polygon_oversized = gdspy.offset(polygon, offset, max_points=MAX_SIZE, join_first=True)
    polygon_oversized = gdspy.offset(polygon_oversized, 0, max_points=MAX_SIZE, join_first=True)

    return polygon_oversized


def dataprep_undersize_gdspy(polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                             offset,  # type: float
                             ):
    # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet]

    if offset < 0:
        print('Warning: offset = %f < 0 indicates you are doing oversize')
    polygon_undersized = gdspy.offset(polygon, -offset, max_points=MAX_SIZE, join_first=True)
    polygon_undersized = gdspy.offset(polygon_undersized, 0, max_points=MAX_SIZE, join_first=True)
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
    polygon_extra = gdspy.offset(gdspy.fast_boolean(polygon_extended, polygon_ref, 'not'),
                                 0, max_points=MAX_SIZE, join_first=True)
    polygon_toadd = gdspy.offset(gdspy.fast_boolean(polygon_extra, polygon_ref_sized, 'and'),
                                 0, max_points=MAX_SIZE, join_first=True)

    polygon_out = gdspy.offset(gdspy.fast_boolean(polygon_toextend, polygon_toadd, 'or'),
                               0, max_points=MAX_SIZE, join_first=True)

    buffer_size = max(grid_size * ceil(0.5 * extended_amount / grid_size + 1.1), 0.0)
    polygon_out = dataprep_oversize_gdspy(dataprep_undersize_gdspy(polygon_out, buffer_size), buffer_size)

    return polygon_out


def poly_operation(polygon1,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                   polygon2,  # type: Union[gdspy.Polygon, gdspy.PolygonSet, None]
                   operation,  # type: str
                   size_amount,  # type: float
                   do_manh=False,  # type: bool
                   debug=False,  # type: bool
                   ):
    # TODO: clean up the input polygons first

    grid_size = global_grid_size
    if polygon2 is None:
        return polygon1
    else:
        if operation == 'rad':
            # if (need_new_rough_shapes == True):
            #     polygon_rough = polyop_roughsize(polygon2)
            #     need_new_rough_shapes == False
            # TODO: manh
            polygon_rough = dataprep_roughsize_gdspy(polygon2, size_amount=size_amount, do_manh=do_manh)

            buffer_size = max(size_amount - 2 * global_rough_grid_size, 0)
            polygon_rough_sized = dataprep_oversize_gdspy(polygon_rough, buffer_size)

            if polygon1 is None:
                polygon_out = polygon_rough_sized
            else:
                polygon_out = gdspy.fast_boolean(polygon1, polygon_rough_sized, 'or')
                polygon_out = gdspy.offset(polygon_out, 0, max_points=4094, join_first=True)
            # if (debug_text == True and leng(RoughShapes) > 0):
            #     print("%L --> %L  %L rough shapes added."  %(LppIn, LppOut, list(len(RoughShapes))))

        elif operation == 'add':
            if polygon1 is None:
                polygon_out = dataprep_oversize_gdspy(polygon2, size_amount)
                # shapely_plot(polygon_out)
            else:
                polygon_out = gdspy.fast_boolean(polygon1, dataprep_oversize_gdspy(polygon2, size_amount), 'or')
                polygon_out = gdspy.offset(polygon_out, 0, max_points=4094, join_first=True)
            # if (debug_text == True and leng(ShapesIn) > 0):
            #     print("%L --> %L  %L shapes added."  %(LppIn, LppOut, list(length(ShapesIn))))

        elif operation == 'sub':
            if polygon1 is None:
                polygon_out = None
            else:
                # TODO: Over or undersize the subtracted poly
                polygon_out = gdspy.fast_boolean(polygon1, dataprep_oversize_gdspy(polygon2, size_amount), 'not')
                polygon_out = gdspy.offset(polygon_out, 0, max_points=4094, join_first=True)
            # if (debug_text == True and leng(ShapesToSubtract) > 0):
            #     print("%L --> %L  %L shapes subtracted."  %(LppIn, LppOut, list(length(ShapesToSubtract))))
            # if polygon1.area == 0
            #     print("Warning in 0ProcedureDataPrep. There is nothing to substract %L from." %(LppOut))

        elif operation == 'ext':
            # TODO:
            # if (not (member(LppOut, NotToExtendOrOverUnderOrUnderOverLpps) != nil)):
            if True:
                # if (debug_text == True):
                #     print("Extending %L over %L by %s ." %(LppIn, LppOut, list(SizeAmount)))
                # else:
                #     pass
                polygon_toextend = polygon1
                polygon_ref = polygon2
                polygon_out = polyop_extend(polygon_toextend, polygon_ref, size_amount)
            else:
                pass
                # if (debug_text == True):
                #     print("Extension skipped on %L over %s by %s." %(LppIn, LppOut, list(SizeAmount)))
                # else:
                #     pass
        # TODO
        elif operation == 'ouo':
            # if (not (member(LppIn NotToExtendOrOverUnderOrUnderOverLpps) != nil)):
            if True:
                # if (debug_text == True and length(ShapesIn) > 0):
                #     print("Performing Over of Under of Under of Over on %s."  %LppIn)
                # if ():
                #     ValueError("MinWidth for %s is missing" %LppIn)
                # else:
                #     min_width = lpp_in['min_width']
                # if ():
                #     ValueError("MinSpace for %s is missing" %LppIn)
                # else:
                #     min_space = lpp_in['min_space']

                min_width = global_min_width
                min_space = global_min_width

                underofover_size = grid_size * ceil(0.5 * min_space / grid_size)
                overofunder_size = grid_size * ceil(0.5 * min_width / grid_size)
                polygon_o = dataprep_oversize_gdspy(polygon1, underofover_size)
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
