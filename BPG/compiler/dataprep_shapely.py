# import BPG
# from bag.layout.util import BBox

# from matplotlib import pyplot
# from descartes import PolygonPatch
# from shapely.ops import cascaded_union
# from shapely.ops import polygonize, polygonize_full

# import importlib
# from figures import SIZE, BLUE, GRAY, set_limits
from typing import Tuple, List, Union, Optional
from math import ceil
from shapely.geometry import Polygon, MultiPolygon
from BPG.compiler.manh_shapely import polyop_manh
from BPG.shapely_debug import shapely_plot


################################################################################
# define parameters for testing
################################################################################
global_grid_size = 0.001
global_rough_grid_size = 0.01
global_do_manh = True
global_min_width = 0.02
global_min_space = 0.05


def dataprep_coord_to_poly(
        pos_neg_list_list,  # type: Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]]
        manh_grid_size,  # type: float
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

    polygon_out = polyop_manh(polygon_out, do_manh=True, manh_grid_size=manh_grid_size)
    return polygon_out

def polyop_roughsize(polygon: Union[Polygon, MultiPolygon],
                     size_amount: float,
                     do_manh: bool
                     ):

    rough_grid_size = global_rough_grid_size

    # oversize twice, then undersize twice and oversize again
    polygon_oo = polyop_oversize(polygon, 2 * rough_grid_size)
    polygon_oouu = polyop_undersize(polygon_oo, 2 * rough_grid_size)
    polygon_oouuo = polyop_oversize(polygon_oouu, rough_grid_size)

    # manhattanize to the rough grid
    polygon_oouuo_rough = polyop_manh(polygon_oouuo, rough_grid_size, do_manh)

    # undersize then oversize
    polygon_roughsized = polyop_oversize(polyop_undersize(polygon_oouuo_rough, global_grid_size), global_grid_size)

    polygon_roughsized = polyop_oversize(polygon_roughsized, max(size_amount - 2 * global_grid_size, 0))

    return polygon_roughsized


def polyop_oversize(polygon: Union[Polygon, MultiPolygon],
                    offset: float
                    ):
    if offset < 0:
        print('Warning: offset = %f < 0 indicates you are doing undersize')
    polygon_oversized = polygon.buffer(offset, cap_style=3, join_style=2)
    return polygon_oversized


def polyop_undersize(polygon: Union[Polygon, MultiPolygon],
                     offset: float
                     ):
    if offset < 0:
        print('Warning: offset = %f < 0 indicates you are doing oversize')
    polygon_undersized = polygon.buffer(-offset, cap_style=3, join_style=2)
    return polygon_undersized


def polyop_extend(polygon_toextend: Union[Polygon, Multipolygon],
                  polygon_ref: Union[Polygon, MultiPolygon],
                  extended_amount: float
                  ):
    grid_size = global_grid_size
    extended_amount = grid_size * ceil(extended_amount / grid_size)
    polygon_ref_sized = polyop_oversize(polygon_ref, extended_amount)
    polygon_extended = polyop_oversize(polygon_toextend, extended_amount)
    polygon_extra = polygon_extended.difference(polygon_ref)
    polygon_toadd = polygon_extra.intersection(polygon_ref_sized)

    polygon_out = polygon_toextend.union(polygon_toadd)
    buffer_size = max(grid_size * ceil(0.5 * extended_amount / grid_size + 1.1), 0.0)
    polygon_out = polyop_oversize(polyop_undersize(polygon_out, buffer_size), buffer_size)
    return polygon_out


def poly_operation(polygon1: Union[Polygon, Multipolygon],
                   polygon2: Optional[Union[Polygon, MultiPolygon]],
                   operation: str,
                   size_amount: float,
                   debug_text: bool = False
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
            polygon_rough = polyop_roughsize(polygon2, size_amount=size_amount, do_manh=True)

            buffer_size = max(size_amount - 2 * global_rough_grid_size, 0)
            polygon_rough_sized = polyop_oversize(polygon_rough, buffer_size)

            if polygon1 is None:
                polygon_out = polygon_rough_sized
            else:
                polygon_out = polygon1.union(polygon_rough_sized)
            # if (debug_text == True and leng(RoughShapes) > 0):
            #     print("%L --> %L  %L rough shapes added."  %(LppIn, LppOut, list(len(RoughShapes))))

        elif operation == 'add':
            if polygon1 is None:
                polygon_out = polyop_oversize(polygon2, size_amount)
                shapely_plot(polygon_out)
            else:
                polygon_out = polygon1.union(polyop_oversize(polygon2, size_amount))
                shapely_plot(polygon_out)
            # if (debug_text == True and leng(ShapesIn) > 0):
            #     print("%L --> %L  %L shapes added."  %(LppIn, LppOut, list(length(ShapesIn))))

        elif operation == 'sub':
            if polygon1 is None:
                polygon_out = None
            else:
                # TODO: Over or undersize the subtracted poly
                polygon_out = polygon1.difference(polyop_oversize(polygon2, size_amount))
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
                poly_o = polyop_oversize(polygon2, underofover_size)
                poly_ou = polyop_undersize(poly_o, underofover_size)
                poly_ouu = polyop_undersize(poly_ou, overofunder_size)
                poly_out = polyop_oversize(poly_ouu, overofunder_size)

            else:
                pass

        elif operation == 'del':
            # TODO
            pass

        return polygon_out



