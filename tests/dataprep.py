import BPG
from bag.layout.util import BBox

from math import ceil, floor
from matplotlib import pyplot
from shapely.geometry import Point, LineString, Polygon, MultiPolygon
from descartes import PolygonPatch
from shapely.ops import union, cascaded_union
from shapely.ops import polygonize, polygonize_full


# from figures import SIZE, BLUE, GRAY, set_limits

def manh_skill_origin(poly_coords,     # type: list[tuple(float, float)]
                      manh_grid_size,  # type: float
                      ) -> list[tuple(float, float)]:

    """
    Convert a polygon into the polygon with orthogonal edges,
    detailed flavors are the same as it is in the SKILL code

    Parameters
    ----------
    poly_coords : list[tuple(float, float)]
        list of coordinates that enclose a polygon
    manh_grid_size : float
        grid size for manhattanization, edge length after manhattanization should be larger than it
    """

    #### Snapping original coordinates to manhattan grid (by rounding)
    poly_coords_manhgrid = []
    for coord in poly_coords:
        xcoord_manhgrid = manh_grid_size * round(coord[0] / manh_grid_size)
        ycoord_manhgrid = manh_grid_size * round(coord[1] / manh_grid_size)
        poly_coords_manhgrid.append((xcoord_manhgrid, ycoord_manhgrid))

    #### adding the first point to the last if polygon is not closed
    if (poly_coords_manhgrid[0] != poly_coords_manhgrid[-1]):
        poly_coords_manhgrid.append(poly_coords_manhgrid[0])
    # Determining the coordinate of a point which is certainly inside the convex envelope of the polygon
    # (a kind of "center-of-mass")
    xcoord_sum = 0
    ycoord_sum = 0
    for coord_manhgrid in poly_coords_manhgrid:
        xcoord_sum = xcoord_sum + coord_manhgrid[0]
        ycoord_sum = ycoord_sum + coord_manhgrid[1]
    xcoord_in = xcoord_sum / len(poly_coords_manhgrid)
    ycoord_in = ycoord_sum / len(poly_coords_manhgrid)
    # print("point INSIDE the shape (x,y) =  (%f, %f)" %(xcoord_in, ycoord_in))

    #### Scanning all the points of the orinal list and adding points in-between.
    poly_coords_orth = [poly_coords_manhgrid[0]]
    for i in range(0, len(poly_coords_manhgrid)):
        #### BE CAREFUL HERE WITH THE INDEX
        coord_curr = poly_coords_manhgrid[i]
        if (i == len(poly_coords_manhgrid)-1):
            coord_next = coord_curr
        else:
            coord_next = poly_coords_manhgrid[i+1]
        delta_x = coord_next[0] - coord_curr[0]
        delta_y = coord_next[1] - coord_curr[1]
        poly_coords_orth.append(coord_curr)
        # current coord and the next coord create an orthogonal edge
        if ((delta_x == 0.0) or (delta_y == 0.0)):
            # print("This point has orthogonal neighbour", coord_curr, coord_next)
            poly_coords_orth.append(coord_next)
        elif(abs(delta_x) > abs(delta_y)):
            num_point_add = int(abs(round(delta_y / manh_grid_size)))
            for j in range(0, num_point_add):
                xstep = round(delta_y/abs(delta_y)) * manh_grid_size * (delta_x/delta_y)
                ystep = round(delta_y/abs(delta_y)) * manh_grid_size
                x0 = coord_curr[0] + j * xstep
                y0 = coord_curr[1] + j * ystep
                #  if positive, the center if the shape is on the left
                vec_product1 = xstep * (ycoord_in - coord_curr[1]) - ystep * (xcoord_in - coord_curr[0])
                #  if positive the vector ( StepX, 0.0) is on the left too
                vec_product2 = xstep * 0.0 - ystep * xstep
                #  If both are positive, incrememnting in X first is the bad choice:
                #  incrememnting X first
                if ((vec_product1 * vec_product2) < 0):
                    poly_coords_orth.append((x0+xstep, y0))
                    poly_coords_orth.append((x0+xstep, y0+ystep))
                #  incrememnting Y first
                else:
                    poly_coords_orth.append((x0      , y0+ystep))
                    poly_coords_orth.append((x0+xstep, y0+ystep))
        else:
            num_point_add = int(abs(round(delta_x / manh_grid_size)))
            # print(num_point_add)
            for j in range(0, num_point_add):
                ystep = round(delta_x/abs(delta_x)) * manh_grid_size * delta_y/delta_x
                xstep = round(delta_x/abs(delta_x)) * manh_grid_size
                x0 = coord_curr[0] + j * xstep
                y0 = coord_curr[1] + j * ystep
                ####  if positive, the center if the shape is on the left
                vec_product1 = xstep * (ycoord_in - coord_curr[1])- ystep * (xcoord_in - coord_curr[0])
                #  if positive the vector ( StepX, 0.0) is on the left too
                vec_product2 = xstep * 0.0 - ystep * xstep
                #  If both are positive, incrememnting in X first is the bad choice:
                #  incrememnting X first
                if ((vec_product1 * vec_product2) < 0):
                    poly_coords_orth.append((x0+xstep, y0))
                    poly_coords_orth.append((x0+xstep, y0+ystep))
                #  incrememnting Y first
                else:
                    poly_coords_orth.append((x0      , y0+ystep))
                    poly_coords_orth.append((x0+xstep, y0+ystep))


    return poly_coords_orth


# TODO: roughsize
def polyop_roughsize(polygon,       # type: Polygon, MultiPolygon
                     size_amount,   # type: float
                     ) -> tuple[Polygon, MultiPolygon]:
    rough_grid_size = global_rough_grid_size

    # oversize twice, then undersize twice and oversize again
    polygon_oo = polyop_oversize(polygon, 2 * rough_grid_size)
    polygon_oouu = polyop_undersize(polygon_oo, 2 * rough_grid_size)
    polygon_oouuo = polyop_oversize(polygon_oouu, rough_grid_size)

    # extract the coordinate list and do manhattanization
    polygon_oouuo_coords = polygon_oouuo.list(zip(*polygon_oouuo.exterior.coords.xy))
    polygon_oouuo_rough = Polygon(manh_skill_origin(polygon_oouuo_coords, rough_grid_size))

    # undersize then oversize
    polygon_roughsized = polyop_oversize(polyop_undersize(polygon_oouuo_rough, global_grid_size), global_grid_size)

    polygon_roughsized = polyop_oversize(polygon_roughsized, max(size_amount - 2 * global_grid_size, 0))

    return polygon_roughsized

def polyop_oversize(polygon,        # type: Polygon, MultiPolygon
                    offset,         # type: float
                    ) -> tuple[Polygon, MultiPolygon]:
    if (offset < 0):
        print('Warning: offset = %f < 0 indicates you are doing undersize')
    polygon_oversized = polygon.buffer(offset, cap_style=3, join_style=2)
    return polygon_oversized

def polyop_undersize(polygon,        # type: Polygon, MultiPolygon
                     offset,         # type: float
                    ) -> tuple[Polygon, MultiPolygon]:
    if (offset < 0):
        print('Warning: offset = %f < 0 indicates you are doing oversize')
    polygon_undersized = polygon.buffer(-offset, cap_style=3, join_style=2)
    return polygon_undersized

def polyop_extend(polygon_toextend, # type: Polygon, Multipolygon
                  polygon_ref,      # type: Polygon, MultiPolygon
                  extended_amount,  # type: float
                  ) ->tuple[Polygon,MultiPolygon]:

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



def poly_operation(polygon1,        # type: Polygon, Multipolygon
                   polygon2,        # type: Polygon, MultiPolygon
                   operation,       # type: str
                   size_amount,     # type: float
                   debug_text=False,# type: bool
                   ) ->tuple[Polygon,MultiPolygon]:
    if (operation == 'rad'):
        if (need_new_rough_shapes == True):
            polygon_rough = polyop_roughsize(polygon2)
            need_new_rough_shapes == False

        buffer_size = max(size_amount - 2 * global_rough_grid_size, 0)
        polygon_rough_sized = polyop_oversize(polygon_rough, buffer_size)
        polygon_out = polygon1.union(polygon_rough_sized)
        if (debug_text == True and leng(RoughShapes) > 0):
            print("%L --> %L  %L rough shapes added."  %(LppIn, LppOut, list(len(RoughShapes))))

    elif (operation == 'add'):
        polygon_out = polygon1.union(polygon2)
        if (debug_text == True and leng(ShapesIn) > 0):
            print("%L --> %L  %L shapes added."  %(LppIn, LppOut, list(length(ShapesIn))))

    elif (operation == 'sub'):
        polygon_out = polygon1.difference(polygon2)
        if (debug_text == True and leng(ShapesToSubtract) > 0):
            print("%L --> %L  %L shapes subtracted."  %(LppIn, LppOut, list(length(ShapesToSubtract))))
        if polygon1.area == 0
            print("Warning in 0ProcedureDataPrep. There is nothing to substract %L from." %(LppOut))

    elif (operation == 'ext'):
        if (not (member(LppOut, NotToExtendOrOverUnderOrUnderOverLpps) != nil)):
            if (debug_text == True):
                print("Extending %L over %L by %s ." %(LppIn, LppOut, list(SizeAmount)))
            else:
                pass
            polygon_toextend = polygon1
            polygon_ref = polygon2
            polygon_out = polyop_extend(polygon_toextend, polygon_ref, size_amount)
        else:
            if (debug_text == True):
                print("Extension skipped on %L over %s by %s." %(LppIn, LppOut, list(SizeAmount)))
            else:
                pass
    #### TODO
    elif (operation == 'ouo'):
        if (not (member(LppIn NotToExtendOrOverUnderOrUnderOverLpps) != nil)):
            if (debug_text == True and length(ShapesIn) > 0):
                print("Performing Over of Under of Under of Over on %s."  %LppIn)
                if ():
                    ValueError("MinWidth for %s is missing" %LppIn)
                else:
                    min_width = lpp_in['min_width']
                if ():
                    ValueError("MinSpace for %s is missing" %LppIn)
                else:
                    min_space = lpp_in['min_space']
                underofover_size = grid_size * ceil(0.5 * min_space / grid_size)
                overofunder_size = grid_size * ceil(0.5 * min_width / grid_size)
                poly_o = polyop_oversize(polygon1, underofover_size)
                poly_ou = polyop_undersize(poly_o, underofover_size)
                poly_ouu = polyop_undersize(poly_ou, overofunder_size)
                poly_out = polyop_oversize(poly_ouu, overofunder_size)

        else:
            pass


    elif (operation == 'del'):
        pass
