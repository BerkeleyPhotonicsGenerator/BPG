import gdspy
import time
import numpy as np
import sys
import shapely.geometry
import logging

from BPG.photonic_objects import PhotonicRect, PhotonicPolygon, PhotonicRound
from math import ceil, sqrt
from typing import TYPE_CHECKING, Tuple, List, Union, Dict, Any, Optional

if TYPE_CHECKING:
    from BPG.photonic_core import PhotonicTechInfo
    from bag.layout.routing import RoutingGrid

################################################################################
# define parameters for testing
################################################################################


MAX_SIZE = sys.maxsize


class Dataprep:
    def __init__(self,
                 photonic_tech_info: "PhotonicTechInfo",
                 grid: "RoutingGrid",
                 flat_content_list_by_layer,
                 flat_content_list_separate,
                 ):
        self.photonic_tech_info: PhotonicTechInfo = photonic_tech_info
        self.grid = grid
        self.flat_content_list_by_layer: Dict[Tuple(str, str), Tuple] = flat_content_list_by_layer
        self.flat_content_list_separate = flat_content_list_separate

        # Initialize dataprep related structures
        # Dictionary of layer-keyed gdspy polygonset shapes
        self.flat_gdspy_polygonsets_by_layer: Dict[Tuple(str, str), Union[gdspy.PolygonSet, gdspy.Polygon]] = {}
        self.lsf_flat_gdspy_polygonsets_by_layer : Dict[Tuple(str, str), Union[gdspy.PolygonSet, gdspy.Polygon]] = {}
        # Dictionary of layer-keyed polygon point-lists (lists of points comprising the polygons on the layer)
        self.post_dataprep_polygon_pointlist_by_layer: Dict[Tuple(str, str), Any] = {}  # TODO: Fix Any
        self.lsf_post_dataprep_polygon_pointlist_by_layer: Dict[Tuple(str, str), Any] = {}
        # BAG style content list after dataprep
        self.post_dataprep_flat_content_list: List[Tuple] = []
        self.lsf_post_dataprep_flat_content_list: List[Tuple] = []

        self.global_grid_size = self.photonic_tech_info.global_grid_size
        self.global_rough_grid_size = self.photonic_tech_info.global_rough_grid_size

        # TODO: Figure out proper operation precision. Should it be related to grid size?
        self.global_operation_precision = self.global_grid_size / 10
        self.global_clean_up_grid_size = self.global_grid_size / 10
        # TODO: make sure we set tolerance properly. larger numbers will cut off acute angles more when oversizing
        self.offset_tolerance = 4.35250
        self.do_cleanup = True

        # In skill, all shapes are created already-manhattanized.
        # Either we must do this (and can then set GLOBAL_DO_MANH_AT_BEGINNING to false, or must manhattanize here to
        #  replicate skill dataprep output)
        self.GLOBAL_DO_MANH_AT_BEGINNING = True
        # SKILL has GLOBAL_DO_MANH_DURING_OP as True. Only used during rad (and rouo?) for both skill and gdspy
        # implementations
        self.GLOBAL_DO_MANH_DURING_OP = True

        # True to ensure that final shape will be on a Manhattan grid. If GLOBAL_DO_MANH_AT_BEGINNING
        # and GLOBAL_DO_MANH_DURING_OP are set,
        # GLOBAL_DO_FINAL_MANH can be False, and we should still have Manhattanized shapes on Manhattan grid
        # if function implentations are correct
        self.GLOBAL_DO_FINAL_MANH = False

    ################################################################################
    # clean up functions for coordinate lists and gdspy objects
    ################################################################################
    @staticmethod
    def coords_apprx_in_line(coord1,  # type: Tuple[float, float]
                             coord2,  # type: Tuple[float, float]
                             coord3,  # type: Tuple[float, float]
                             eps_grid=1e-4,  # type: float
                             ):
        # type: (...) -> bool
        """
        Determines if three coordinates are in the same line
    
        Parameters
        ----------
        coord1 : Tuple[float, float]
            First coordinate
        coord2 : Tuple[float, float]
            Second coordinate
        coord3 : Tuple[float, float]
            Third coordinate
        eps_grid : float
            grid resolution below which points are considered to be the same
    
        Returns
        -------
        : bool
            True if coordinates are in a line, False if not in a line
        """
        dx1_2 = coord1[0] - coord2[0]
        dy1_2 = coord1[1] - coord2[1]
        dx2_3 = coord2[0] - coord3[0]
        dy2_3 = coord2[1] - coord3[1]
    
        # if any of the two consecutive coords are actually the same, the three coords are in a line
        if ((abs(dx1_2) < eps_grid) and (abs(dy1_2) < eps_grid)) or \
                ((abs(dx2_3) < eps_grid) and (abs(dy2_3) < eps_grid)):
            return True
        else:
            """
            if x&y coords are accurate, we should have dx1_acc * dy2_acc =dx2_acc * dy1_acc,
            because of inaccuracy in float numbers, we have
            |dx1 * dy2 - dx2 * dy1| = |(dx1_acc + err1) * (dy2_acc + err2) - (dx2_acc + err3) * (dy1_acc + err4)|
                                    ~ |dx1 * err2 + dy2 * err1 - dx2 * err4 - dy1 * err3|
                                    < sum(|dx1|, |dx2|, |dy1|, |dy2|) * |err_max|
            """
            error_abs = abs(dx1_2 * dy2_3 - dx2_3 * dy1_2)
            error_rlt = error_abs / (abs(dx1_2) + abs(dx2_3) + abs(dy1_2) + abs(dy2_3))
            return error_rlt < eps_grid

    def cleanup_loop(self,
                     coords_list_in,  # type: Union[List[Tuple[float, float]], np.ndarray]
                     eps_grid=1e-4,  # type: float
                     ):
        # type: (...) -> Dict[str]
        """
    
        Parameters
        ----------
        coords_list_in : List[Tuple[float, float]]
            The list of x-y coordinates composing a polygon shape
        eps_grid :
            grid resolution below which points are considered to be the same
    
        Returns
        -------
        output_dict : Dict[str]
            Dictionary of 'coords_list_out' and 'fully_cleaned'
        """

        if isinstance(coords_list_in, np.ndarray):
            coords_list_in = coords_list_in
        else:
            coords_list_in = np.array(coords_list_in)

        coord_set_lsh = np.roll(coords_list_in, -1, axis=0)
        coord_set_rsh = np.roll(coords_list_in, 1, axis=0)

        vec_l = coord_set_lsh - coords_list_in
        vec_r = coords_list_in - coord_set_rsh

        dx_l = vec_l[:, 0]
        dy_l = vec_l[:, 1]
        dx_r = vec_r[:, 0]
        dy_r = vec_r[:, 1]

        dx_l_abs = np.abs(dx_l)
        dy_l_abs = np.abs(dy_l)
        dx_r_abs = np.abs(dx_r)
        dy_r_abs = np.abs(dy_r)

        same_with_left = np.logical_and(dx_l_abs < eps_grid, dy_l_abs < eps_grid)
        same_with_right = np.logical_and(dx_r_abs < eps_grid, dy_r_abs < eps_grid)
        diff_from_lr = np.logical_not(np.logical_or(same_with_left, same_with_right))

        # error_abs = np.abs(dx_l * dy_r - dx_r * dy_l)
        # in_line = error_abs  < eps_grid * (dx_l_abs + dy_l_abs + dx_r_abs + dy_r_abs)
        in_line = np.logical_or(np.logical_and(dx_l_abs < eps_grid, dx_r_abs < eps_grid),
                                np.logical_and(dy_l_abs < eps_grid, dy_r_abs < eps_grid))

        delete = np.logical_or(same_with_left, np.logical_and(in_line, diff_from_lr))
        select = np.logical_not(delete)

        fully_cleaned = np.sum(delete) == 0
        coord_set_out = coords_list_in[select]

        return {'coord_set_out': coord_set_out, 'fully_cleaned': fully_cleaned}

    def cleanup_delete(self,
                       coords_list_in,  # type: Union[List[Tuple[float, float]], np.ndarray]
                       eps_grid=1e-4,  # type: float
                       ):
        # type: (...) -> np.ndarray
        """

        Parameters
        ----------
        coords_list_in : Union[List[Tuple[float, float]], np.ndarray]
            The list of x-y coordinates composing a polygon shape
        eps_grid :
            grid resolution below which points are considered to be the same

        Returns
        -------
        delete_array : np.ndarray
            Numpy array of bools telling whether to delete the coordinate or not
        """

        if isinstance(coords_list_in, np.ndarray):
            coords_list_in = coords_list_in
        else:
            coords_list_in = np.array(coords_list_in)

        coord_set_lsh = np.roll(coords_list_in, -1, axis=0)
        coord_set_rsh = np.roll(coords_list_in, 1, axis=0)

        vec_l = coord_set_lsh - coords_list_in
        vec_r = coords_list_in - coord_set_rsh

        dx_l = vec_l[:, 0]
        dy_l = vec_l[:, 1]
        dx_r = vec_r[:, 0]
        dy_r = vec_r[:, 1]

        dx_l_abs = np.abs(dx_l)
        dy_l_abs = np.abs(dy_l)
        dx_r_abs = np.abs(dx_r)
        dy_r_abs = np.abs(dy_r)

        same_with_left = np.logical_and(dx_l_abs < eps_grid, dy_l_abs < eps_grid)
        same_with_right = np.logical_and(dx_r_abs < eps_grid, dy_r_abs < eps_grid)
        diff_from_lr = np.logical_not(np.logical_or(same_with_left, same_with_right))

        # error_abs = np.abs(dx_l * dy_r - dx_r * dy_l)
        # in_line = error_abs  < eps_grid * (dx_l_abs + dy_l_abs + dx_r_abs + dy_r_abs)
        in_line = np.logical_or(np.logical_and(dx_l_abs < eps_grid, dx_r_abs < eps_grid),
                                np.logical_and(dy_l_abs < eps_grid, dy_r_abs < eps_grid))

        # situation 1: the point is the same with its left neighbor
        # situation 2: the point is not the same with its neighbors, but it is in a line with them
        delete_array = np.logical_or(same_with_left, np.logical_and(in_line, diff_from_lr))

        return delete_array

    def coords_cleanup(self,
                       coords_list_in,  # type: Union[List[Tuple[float, float]], np.ndarray]
                       eps_grid=1e-4,  # type: float
                       debug=False,  # type: bool
                       ):
        # type (...) -> List[Tuple[float, float]]
        """
        clean up coordinates in the list that are redundant or harmful for following Shapely functions
    
        Parameters
        ----------
        coords_list_in : Union[List[Tuple[float, float]], np.ndarray]
            list of coordinates that enclose a polygon
        eps_grid : float
            a size smaller than the resolution grid size,
            if the difference of x/y coordinates of two points is smaller than it,
            these two points should actually share the same x/y coordinate
        debug : bool
    
        Returns
        ----------
        coords_set_out : np.ndarray
            The cleaned coordinate set
        """
        logging.debug(f'in coords_cleanup, coords_list_in: {coords_list_in}')

        if isinstance(coords_list_in, np.ndarray):
            coord_set_out = coords_list_in
        else:
            coord_set_out = np.array(coords_list_in)

        delete_array = self.cleanup_delete(coord_set_out, eps_grid=eps_grid)
        not_cleaned = np.sum(delete_array) > 0

        # in some cases, some coordinates become on the line if the following coord is deleted,
        # need to loop until no coord is deleted during one loop
        while not_cleaned:
            select_array = np.logical_not(delete_array)
            coord_set_out = coord_set_out[select_array]
            delete_array = self.cleanup_delete(coord_set_out, eps_grid=eps_grid)
            not_cleaned = np.sum(delete_array) > 0

        logging.debug(f'in coords_cleanup, coord_set_out: {coord_set_out}')

        return coord_set_out

    def dataprep_cleanup_gdspy(self,
                               polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet, None]
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
            if polygon is None:
                clean_polygon = None
            elif isinstance(polygon, (gdspy.Polygon, gdspy.PolygonSet)):
                clean_polygon = gdspy.offset(
                    polygons=polygon,
                    distance=0,
                    tolerance=self.offset_tolerance,
                    max_points=MAX_SIZE,
                    join_first=True,
                    precision=self.global_clean_up_grid_size,
                )
    
                clean_coords = []
                if isinstance(clean_polygon, gdspy.Polygon):
                    clean_coords = self.global_grid_size * np.round(clean_polygon.points / self.global_grid_size, 0)
                    clean_polygon = gdspy.Polygon(points=clean_coords)
                elif isinstance(clean_polygon, gdspy.PolygonSet):
                    for poly in clean_polygon.polygons:
                        clean_coords.append(self.global_grid_size * np.round(poly / self.global_grid_size, 0))
                    clean_polygon = gdspy.PolygonSet(polygons=clean_coords)

    
            else:
                raise ValueError('input polygon must be a gdspy.Polygon, gdspy.PolygonSet or NonType')
    
        else:
            clean_polygon = polygon
    
        return clean_polygon

    ################################################################################
    # type-converting functions for coordlist/gdspy/shapely
    ################################################################################
    @staticmethod
    def coord_to_shapely(
            pos_neg_list_list,  # type: Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]]
    ):
        # type: (...) -> Union[shapely.geometry.Polygon, shapely.geometry.MultiPolygon]
        """
        Converts list of coordinate lists into shapely polygon objects
    
        Parameters
        ----------
        pos_neg_list_list :
            The tuple of positive and negative lists of coordinate lists
    
        Returns
        -------
        polygon_out : Union[Polygon, Multipolygon]
            The Shapely representation of the polygon
        """
        pos_coord_list_list = pos_neg_list_list[0]
        neg_coord_list_list = pos_neg_list_list[1]
    
        polygon_out = shapely.geometry.Polygon(pos_coord_list_list[0]).buffer(0, cap_style=3, join_style=2)
    
        if len(pos_coord_list_list) > 1:
            for pos_coord_list in pos_coord_list_list[1:]:
                polygon_pos = shapely.geometry.Polygon(pos_coord_list).buffer(0, cap_style=3, join_style=2)
                polygon_out = polygon_out.union(polygon_pos)
        if len(neg_coord_list_list):
            for neg_coord_list in neg_coord_list_list:
                polygon_neg = shapely.geometry.Polygon(neg_coord_list).buffer(0, cap_style=3, join_style=2)
                polygon_out = polygon_out.difference(polygon_neg)
    
        return polygon_out

    # TODO: This is slow
    def dataprep_coord_to_gdspy(
            self,
            pos_neg_list_list: Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]],
            manh_grid_size: float,
            do_manh: bool,
    ) -> Union[gdspy.Polygon, gdspy.PolygonSet]:
        """
        Converts list of polygon coordinate lists into GDSPY polygon objects
        The expected input list will be a list of all polygons on a given layer
    
        Parameters
        ----------
        pos_neg_list_list : Tuple[List, List]
            A tuple containing two lists: the list of positive polygon shapes and the list of negative polygon shapes.
            Each polygon shape is a list of point tuples
        manh_grid_size : float
            The Manhattanization grid size
        do_manh : bool
            True to perform Manhattanization
    
        Returns
        -------
        polygon_out : Union[gdspy.Polygon, gdspy.PolygonSet]
            The gdpsy.Polygon formatted polygons
        """
        pos_coord_list_list = pos_neg_list_list[0]
        neg_coord_list_list = pos_neg_list_list[1]

        polygon_out = self.dataprep_cleanup_gdspy(gdspy.PolygonSet(pos_coord_list_list),
                                                  do_cleanup=self.do_cleanup)
        if len(neg_coord_list_list):
            polygon_neg = self.dataprep_cleanup_gdspy(gdspy.PolygonSet(neg_coord_list_list),
                                                      do_cleanup=self.do_cleanup)
            polygon_out = self.dataprep_cleanup_gdspy(
                gdspy.fast_boolean(polygon_out, polygon_neg, 'not',
                                   precision=self.global_operation_precision,
                                   max_points=MAX_SIZE),
                do_cleanup=self.do_cleanup
            )

        polygon_out = self.gdspy_manh(polygon_out, manh_grid_size=manh_grid_size, do_manh=do_manh)

        # TODO: is the cleanup necessary
        # Offset by 0 to clean up shape
        polygon_out = self.dataprep_cleanup_gdspy(
            polygon_out,
            do_cleanup=self.do_cleanup
        )
    
        return polygon_out

    def shapely_to_gdspy_polygon(self,
                                 polygon_shapely,  # type: shapely.geometry.Polygon
                                 ):
        # type: (...) -> gdspy.Polygon
        """
        Converts the shapely representation of a polygon to a gdspy representation

        Parameters
        ----------
        polygon_shapely : shapely.geometry.Polygon
            The shapely representation of the polygon

        Returns
        -------
        polygon_gdspy : gdspy.Polygon
            The gdspy representation of the polygon
        """
        if not isinstance(polygon_shapely, shapely.geometry.Polygon):
            raise ValueError("input must be a Shapely Polygon")
        else:
            ext_coord_list = list(zip(*polygon_shapely.exterior.coords.xy))
            polygon_gdspy = gdspy.Polygon(ext_coord_list)
            if len(polygon_shapely.interiors):
                for interior in polygon_shapely.interiors:
                    int_coord_list = list(zip(*interior.coords.xy))
                    polygon_gdspy_int = gdspy.Polygon(int_coord_list)

                    polygon_gdspy = self.dataprep_cleanup_gdspy(
                        gdspy.fast_boolean(polygon_gdspy, polygon_gdspy_int,
                                           'not',
                                           max_points=MAX_SIZE,
                                           precision=self.global_operation_precision),
                        do_cleanup=self.do_cleanup
                    )
            else:
                pass
            return polygon_gdspy

    def shapely_to_gdspy(self,
                         geom_shapely,  # type: Union[shapely.geometry.Polygon, shapely.geometry.MultiPolygon]
                         ):
        # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet]
        """
        Convert the shapely representation of a polygon/multipolygon into the gdspy representation of the
        polygon/polygonset

        Parameters
        ----------
        geom_shapely : Union[Polygon, MultiPolygon]
            The shapely representation of the polygon

        Returns
        -------
        polygon_gdspy : Union[gdspy.Polygon, gdspy.PolygonSet]
            The gdspy representation of the polygon
        """
        if isinstance(geom_shapely, shapely.geometry.Polygon):
            return self.shapely_to_gdspy_polygon(geom_shapely)
        elif isinstance(geom_shapely, shapely.geometry.MultiPolygon):
            polygon_gdspy = self.shapely_to_gdspy_polygon(geom_shapely[0])
            for polygon_shapely in geom_shapely[1:]:
                polygon_gdspy_append = self.shapely_to_gdspy_polygon(polygon_shapely)

                polygon_gdspy = self.dataprep_cleanup_gdspy(
                    gdspy.fast_boolean(polygon_gdspy, polygon_gdspy_append,
                                       'or',
                                       max_points=MAX_SIZE,
                                       precision=self.global_operation_precision),
                    do_cleanup=self.do_cleanup)

            return polygon_gdspy
        else:
            raise ValueError("input must be a Shapely Polygon or a Shapely MultiPolygon")

    def polyop_gdspy_to_point_list(self,
                                   polygon_gdspy_in,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                                   fracture=True,  # type: bool
                                   do_manh=True,  # type: bool
                                   manh_grid_size=None,  # type: Optional[float]
                                   ):
        # type: (...) -> List[List[Tuple[float, float]]]
        """
        Converts the gdspy representation of the polygon into a list of fractured polygon point lists

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

        if manh_grid_size is None:
            manh_grid_size = self.global_grid_size
        # TODO: Consider doing fracture to precision 0.0004, rounding explicitly to 0.001, then cleaning up duplicates

        if do_manh:
            start = time.time()
            polygon_gdspy_in = self.gdspy_manh(polygon_gdspy_in, manh_grid_size=manh_grid_size, do_manh=do_manh)
            end = time.time()
            logging.debug(f'polyop_gdspy_to_point_list: gdspy_manh took: {end-start}s')

        if fracture:
            start = time.time()
            # TODO: Magic numbers
            polygon_gdspy = polygon_gdspy_in.fracture(max_points=4094, precision=self.global_grid_size)
            end = time.time()
            logging.debug(f'polyop_gdspy_to_point_list: fracturing took: {end-start}s')
        else:
            polygon_gdspy = polygon_gdspy_in

        output_list_of_coord_lists = []
        if isinstance(polygon_gdspy, gdspy.Polygon):
            output_list_of_coord_lists = [np.round(polygon_gdspy.points, 3)]
            # TODO: Magic number. round based on layout_unit and resolution

            non_manh_edge = self.not_manh(polygon_gdspy.points)
            if non_manh_edge:
                print('Warning: a non-Manhattanized polygon is created in polyop_gdspy_to_point_list, '
                      'number of non-manh edges is', non_manh_edge)

        elif isinstance(polygon_gdspy, gdspy.PolygonSet):
            for poly in polygon_gdspy.polygons:
                output_list_of_coord_lists.append(np.round(poly, 3))
                # TODO: Magic number. round based on layout_unit and resolution

                non_manh_edge = self.not_manh(poly)
                if non_manh_edge:
                    print('Warning: a non-Manhattanized polygon is created in polyop_gdspy_to_point_list, '
                          'number of non-manh edges is', non_manh_edge)
        else:
            raise ValueError('polygon_gdspy must be a gdspy.Polygon or gdspy.PolygonSet')

        return output_list_of_coord_lists

    ################################################################################
    # Manhattanization related functions
    ################################################################################
    @staticmethod
    def merge_adjacent_duplicate(coord_set,
                                 eps_grid=1e-6):
        if isinstance(coord_set, np.ndarray):
            coords_list_in = coord_set
        else:
            coords_list_in = np.array(coord_set)

        coord_set_shift = np.roll(coords_list_in, 1, axis=0)
        # 2D array: array of [abs(deltax) > eps, abs(deltay) > eps]
        coord_cmp_eq = np.abs(coord_set_shift - coords_list_in) < eps_grid
        # 1D array: array of [this point is not a duplicate]
        select = np.sum(coord_cmp_eq, axis=1) <= 1

        coord_set_merged = coord_set[select]

        return coord_set_merged

    @staticmethod
    def not_manh(coord_list,  # type: np.ndarray[Tuple[float, float]]
                 eps_grid=1e-6,  # type: float
                 ):
        # type (...) -> int
        """
        Checks whether the passed coordinate list is Manhattanized

        Parameters
        ----------
        coord_list : List[Tuple[float, float]]
            The coordinate list to check
        eps_grid : float
            The grid tolerance below which points are considered the same

        Returns
        -------
        non_manh_edge : int
            The count of number of edges that are non-Manhattan in this shape
        """
        if isinstance(coord_list, np.ndarray):
            coord_set_in = coord_list
        else:
            coord_set_in = np.array(coord_list)

        coord_set_shift = np.roll(coord_set_in, 1, axis=0)
        # 2D array: array of [deltax > eps, deltay > eps]
        coord_cmp = np.abs(coord_set_shift - coord_set_in) > eps_grid
        # 1D array: array of [this edge is not manhattanized]
        edge_not_manh = np.sum(coord_cmp, axis=1) > 1

        non_manh_edge = np.sum(edge_not_manh, axis=0)

        return non_manh_edge

    @staticmethod
    def manh_edge_tran(p1,
                       dx,
                       dy,
                       nstep,
                       inc_x_first,
                       manh_grid_size,
                       eps_grid = 1e-4,
                       ):
        """
        Converts pointlist of an edge (ie 2 points), to a pointlist of a Manhattanized edge

        Parameters
        ----------
        p1
        dx
        dy
        nstep
        inc_x_first
        manh_grid_size

        Returns
        -------

        """
        # this point and the next point can form a manhattanized edge, no need to create new points
        if (abs(dx) < eps_grid) or (abs(dy) < eps_grid):
            edge_coord_set = np.array([p1.tolist()])
            # print("debug", p1, dx, dy, nstep, inc_x_first, manh_grid_size,)
        # if nstep == 0:
        #     if inc_x_first:
        #         edge_coord_set = np.round(
        #             np.array([p1.tolist(), [p1[0] + dx, p1[1]]]) / manh_grid_size) * manh_grid_size
        #     else:
        #         edge_coord_set = np.round(
        #             np.array([p1.tolist(), [p1[0], p1[1] + dy]]) / manh_grid_size) * manh_grid_size
        # otherwise we need to insert new points, dx or dy might not be on manh grid, need to
        else:
            x_set = np.empty((2 * nstep,), dtype=p1.dtype)
            y_set = np.empty((2 * nstep,), dtype=p1.dtype)
            if inc_x_first:
                x_set_pre = np.round(
                    np.linspace(p1[0], p1[0] + nstep * dx, nstep + 1) / manh_grid_size) * manh_grid_size
                y_set_pre = np.round(
                    np.linspace(p1[1], p1[1] + (nstep - 1) * dy, nstep) / manh_grid_size) * manh_grid_size
                x_set[0::2] = x_set_pre[:-1]
                x_set[1::2] = x_set_pre[1:]
                y_set[0::2] = y_set_pre
                y_set[1::2] = y_set_pre
            else:
                x_set_pre = np.round(
                    np.linspace(p1[0], p1[0] + (nstep - 1) * dx, nstep) / manh_grid_size) * manh_grid_size
                y_set_pre = np.round(
                    np.linspace(p1[1], p1[1] + nstep * dy, nstep + 1) / manh_grid_size) * manh_grid_size
                x_set[0::2] = x_set_pre
                x_set[1::2] = x_set_pre
                y_set[0::2] = y_set_pre[:-1]
                y_set[1::2] = y_set_pre[1:]

            edge_coord_set = np.stack((x_set, y_set), axis=-1)

        return edge_coord_set

    def manh_skill(self,
                   poly_coords,  # type: np.ndarray[Tuple[float, float]]
                   manh_grid_size,  # type: float
                   manh_type,  # type: str
                   ):
        # type: (...) -> np.ndarray[Tuple[float, float]]
        """
        Convert a polygon into a polygon with orthogonal edges (ie, performs Manhattanization)

        Parameters
        ----------
        poly_coords : List[Tuple[float, float]]
            list of coordinates that enclose a polygon
        manh_grid_size : float
            grid size for Manhattanization, edge length after Manhattanization should be larger than it
        manh_type : str
            'inc' : the Manhattanized polygon is larger compared to the one on the manh grid
            'dec' : the Manhattanized polygon is smaller compared to the one on the manh grid
            'non' : additional feature, only map the coords to the manh grid but do no Manhattanization

        Returns
        ----------
        poly_coords_cleanup : List[Tuple[float, float]]
            The Manhattanized list of coordinates describing the polygon
        """

        def apprx_equal(float1,  # type: float
                        float2,  # type: float
                        eps_grid=1e-9  # type: float
                        ):
            return abs(float1 - float2) < eps_grid

        def apprx_equal_coord(coord1,  # type: Tuple[float, float]
                              coord2,  # type: Tuple[float, float]
                              eps_grid=1e-9  # type: float
                              ):
            return apprx_equal(coord1[0], coord2[0], eps_grid) and (apprx_equal(coord1[1], coord2[0], eps_grid))

        # map the coordinates to the manh grid
        if isinstance(poly_coords, np.ndarray):
            poly_coords_ori = poly_coords
        else:
            poly_coords_ori = np.array(poly_coords)

        logging.debug(f'in manh_skill, manh_grid_size: {manh_grid_size}')
        logging.debug(f'in manh_skill, poly_coords before mapping to manh grid: {poly_coords_ori}')

        if poly_coords_ori.size == 0:
            return poly_coords_ori

        poly_coords_manhgrid = manh_grid_size * np.round(poly_coords_ori / manh_grid_size)

        logging.debug(f'in manh_skill, poly_coords after mapping to manh grid: {poly_coords_manhgrid}')

        # poly_coords_manhgrid = self.coords_cleanup(poly_coords_manhgrid)
        poly_coords_manhgrid = self.merge_adjacent_duplicate(poly_coords_manhgrid)

        # adding the first point to the last if polygon is not closed
        if not apprx_equal_coord(poly_coords_manhgrid[0], poly_coords_manhgrid[-1]):
            poly_coords_manhgrid = np.append(poly_coords_manhgrid, [poly_coords_manhgrid[0]], axis=0)

        # do Manhattanization if manh_type is 'inc'
        if manh_type == 'non':
            return poly_coords  # coords_cleanup(poly_coords_manhgrid)
        elif (manh_type == 'inc') or (manh_type == 'dec'):
            # Determining the coordinate of a point which is likely to be inside the convex envelope of the polygon
            # (a kind of "center-of-mass")

            n_coords = poly_coords_manhgrid.size / poly_coords_manhgrid[0].size
            coord_in = np.sum(poly_coords_manhgrid, axis=0) / n_coords

            poly_coords_manhgrid_leftshift = np.roll(poly_coords_manhgrid, -1, axis=0)
            edge_vec_set = poly_coords_manhgrid_leftshift - poly_coords_manhgrid
            p2c_vec_set = coord_in - poly_coords_manhgrid

            deltax_set = edge_vec_set[:, 0]
            deltay_set = edge_vec_set[:, 1]

            nstep_set = np.round(np.minimum(np.abs(deltax_set), np.abs(deltay_set)) / manh_grid_size).astype(int)
            nstep_fordivide_set = nstep_set + (nstep_set == 0)
            dx_set = deltax_set / nstep_fordivide_set
            dy_set = deltay_set / nstep_fordivide_set
            p2c_x_set = p2c_vec_set[:, 0]
            p2c_y_set = p2c_vec_set[:, 1]
            product1_set = deltax_set * p2c_y_set - deltay_set * p2c_x_set
            product2_set = deltax_set * 0.0 - deltax_set * deltay_set
            inc_x_first_set = (product1_set * product2_set < 0) == (manh_type == 'inc')

            # Scanning all the points of the orinal set and adding points in-between.
            poly_coords_orth = []
            t1 = time.time()
            # print('len(poly_coords_manhgrid)', len(poly_coords_manhgrid))
            for i in range(0, len(poly_coords_manhgrid)):
                # BE CAREFUL HERE WITH THE INDEX
                coord_curr = poly_coords_manhgrid[i]
                if i == len(poly_coords_manhgrid) - 1:
                    coord_next = poly_coords_manhgrid[0]
                else:
                    coord_next = poly_coords_manhgrid[i + 1]

                edge_coords_set = self.manh_edge_tran(coord_curr, dx_set[i], dy_set[i], nstep_set[i],
                                                      inc_x_first_set[i],
                                                      manh_grid_size)

                poly_coords_orth.append(edge_coords_set)

            poly_coords_orth = np.concatenate(poly_coords_orth, axis=0)

            poly_coords_orth_manhgrid = poly_coords_orth
            # poly_coords_orth_manhgrid = manh_grid_size * np.round(poly_coords_orth / manh_grid_size)

            # clean up the coords
            nonmanh_edge_pre = self.not_manh(poly_coords_orth_manhgrid)

            # If this is true, we should fail, so loop and help with debug
            if nonmanh_edge_pre:
                # print(poly_coords_orth_manhgrid)
                for i in range(0, len(poly_coords_orth_manhgrid) - 1):
                    p1 = poly_coords_orth_manhgrid[i]
                    p2 = poly_coords_orth_manhgrid[i + 1]
                    if p1[0] != p2[0] and p1[1] != p2[1]:
                        print('non_manh_edge:', p1, p2)

                raise ValueError(f'Manhattanization failed before the clean-up, '
                                 f'number of non-manh edges is {nonmanh_edge_pre}')

            poly_coords_cleanup = self.coords_cleanup(poly_coords_orth_manhgrid)
            if poly_coords_cleanup.size != 0:
                poly_coords_cleanup = np.append(poly_coords_cleanup, [poly_coords_cleanup[0]], axis=0)
            nonmanh_edge_post = self.not_manh(poly_coords_cleanup)
            if nonmanh_edge_post:
                for i in range(0, len(poly_coords_cleanup)):
                    p1 = poly_coords_cleanup[i]
                    if i == len(poly_coords_cleanup) - 1:
                        p2 = poly_coords_cleanup[0]
                    else:
                        p2 = poly_coords_orth_manhgrid[i+1]
                    if p1[0] != p2[0] and p1[1] != p2[1]:
                        print('non_manh_edge:', p1, p2)
                raise ValueError(f'Manhattanization failed after the clean-up, '
                                 f'number of non-manh edges is {nonmanh_edge_post}')

            return poly_coords_cleanup
        else:
            raise ValueError('manh_type = {} should be either "non", "inc" or "dec"'.format(manh_type))

    def gdspy_manh(self,
                   polygon_gdspy,  # type: Union[gdspy.Polygon, gdspy.PolygonSet, None]
                   manh_grid_size,  # type: float
                   do_manh,  # type: bool
                   ):
        # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet]
        """
        Performs Manhattanization on a gdspy representation of a polygon, and returns a gdspy representation of the
        Manhattanized polygon

        Parameters
        ----------
        polygon_gdspy : Union[gdspy.Polygon, gdspy.PolygonSet, None]
            The gdspy representation of the polygons to be Manhattanized
        manh_grid_size : float
            grid size for Manhattanization, edge length after Manhattanization should be larger than it
        do_manh : bool
            True to perform Manhattanization

        Returns
        -------
        polygon_out : Union[gdspy.Polygon, gdspy.PolygonSet]
            The Manhattanized polygon, in gdspy representation
        """
        start = time.time()

        if do_manh:
            manh_type = 'inc'
        else:
            manh_type = 'non'

        if polygon_gdspy is None:
            polygon_out = None
        elif isinstance(polygon_gdspy, gdspy.Polygon):
            coord_list = self.manh_skill(polygon_gdspy.points, manh_grid_size, manh_type)
            polygon_out = self.dataprep_cleanup_gdspy(gdspy.Polygon(coord_list),
                                                      do_cleanup=self.do_cleanup)
        elif isinstance(polygon_gdspy, gdspy.PolygonSet):
            polygon_list = []
            for poly in polygon_gdspy.polygons:
                coord_list = self.manh_skill(poly, manh_grid_size, manh_type)
                polygon_list.append(coord_list)
            polygon_out = self.dataprep_cleanup_gdspy(gdspy.PolygonSet(polygon_list),
                                                      do_cleanup=self.do_cleanup)
        else:
            raise ValueError('polygon_gdspy should be either a Polygon or PolygonSet')

        end = time.time()
        logging.debug(f'gdspy_man took {end-start}s')

        return polygon_out

    ################################################################################
    # Simplify function
    ################################################################################
    def simplify_coord_to_gdspy(
            self,
            pos_neg_list_list,  # type: Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]]
            tolerance=5e-4,  # type: float
    ):
        # type: (...) -> Union[gdspy.PolygonSet, gdspy.Polygon]
        """
        Simplifies a polygon coordinate-list representation of a complex polygon (multiple shapes, with holes, etc) and
        converts the simplified polygon into gdspy representation. Simplification involves reducing the number of points
        in the shape based on a tolerance of how far the points are from being collinear.

        Parameters
        ----------
        pos_neg_list_list : Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]]
            Tuple containing the positive and negative list of polygon point-lists
        tolerance : float
            The tolerance within which a set of points are deemed collinear

        Returns
        -------
        poly_gdspy_simplified : Union[gdspy.PolygonSet, gdspy.Polygon]
            The simplified polygon in gdspy representation
        """
        poly_shapely = self.coord_to_shapely(pos_neg_list_list)
        poly_shapely_simplified = poly_shapely.simplify(tolerance)
        poly_gdspy_simplified = self.shapely_to_gdspy(poly_shapely_simplified)

        return poly_gdspy_simplified

    ################################################################################
    # Dataprep related operations
    ################################################################################
    def dataprep_oversize_gdspy(self,
                                polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet, None]
                                offset,  # type: float
                                ):
        # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet, None]
        """
        Grow a polygon by an offset. Perform cleanup to ensure proper polygon shape.

        Parameters
        ----------
        polygon : Union[gdspy.Polygon, gdspy.PolygonSet, None]
            The polygon to size, in gdspy representation
        offset : float
            The amount to grow the polygon

        Returns
        -------
        polygon_oversized : Union[gdspy.Polygon, gdspy.PolygonSet, None]
            The oversized polygon
        """
        if polygon is None:
            return None
        else:
            if offset < 0:
                print('Warning: offset = %f < 0 indicates you are doing undersize')
            polygon_oversized = gdspy.offset(polygon, offset, max_points=MAX_SIZE, join_first=True,
                                             join='miter',
                                             tolerance=self.offset_tolerance,
                                             precision=self.global_operation_precision)
            polygon_oversized = self.dataprep_cleanup_gdspy(polygon_oversized, do_cleanup=self.do_cleanup)

            return polygon_oversized

    def dataprep_undersize_gdspy(self,
                                 polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet, None]
                                 offset,  # type: float
                                 ):
        # type: (...) -> Union[gdspy.Polygon, gdspy.PolygonSet, None]
        """
        Shrink a polygon by an offset. Perform cleanup to ensure proper polygon shape.

        Parameters
        ----------
        polygon : Union[gdspy.Polygon, gdspy.PolygonSet, None]
            The polygon to size, in gdspy representation
        offset : float
            The amount to shrink the polygon

        Returns
        -------
        polygon_undersized : Union[gdspy.Polygon, gdspy.PolygonSet, None]
            The undersized polygon
        """

        if polygon is None:
            return None
        else:
            if offset < 0:
                print('Warning: offset = %f < 0 indicates you are doing oversize')
            polygon_undersized = gdspy.offset(polygon, -offset, max_points=MAX_SIZE, join_first=True,
                                              join='miter',
                                              tolerance=self.offset_tolerance,
                                              precision=self.global_operation_precision)
            polygon_undersized = self.dataprep_cleanup_gdspy(polygon_undersized, do_cleanup=self.do_cleanup)

            return polygon_undersized

    def dataprep_roughsize_gdspy(self,
                                 polygon,  # type: Union[gdspy.Polygon, gdspy.PolygonSet]
                                 size_amount,  # type: float
                                 do_manh,  # type: bool
                                 ):
        # type (...) -> Union[gdspy.Polygon, gdspy.PolygonSet]
        """
        Add a new polygon that is rough sized by 'size_amount' from the provided polygon.
        Rough sizing entails:
         - oversize by 2x the global rough grid size
         - undersize by 2x the global rough grid size
         - oversize by the global rough grid size
         - Manhattanize to the global rough grid
         - undersize by the fine global fine grid size
         - oversize by the fine global fine grid size
         - oversize by 'size_amount' less the 2x global grid size already used

        Parameters
        ----------
        polygon : Union[gdspy.Polygon, gdspy.PolygonSet]
            polygon to be used as the base shape for the rough add, in gdspy representation
        size_amount : float
            amount to oversize (undersize is not supported, will be set to 0 if negative) the rough added shape
        do_manh : bool
            True to perform Manhattanization of after the oouuo shape

        Returns
        -------
        polygon_roughsized : Union[gdspy.Polygon, gdspy.PolygonSet]
            the rough added polygon shapes, in gdspy representation
        """

        # ORIGINAL SKILL: oversize twice, then undersize twice and oversize again
        # No need for this as it doesnt actually clean up min width violations
        # Just do Over twice then under once
        polygon_oo = self.dataprep_oversize_gdspy(polygon, 2 * self.global_rough_grid_size)
        polygon_oouuo = self.dataprep_undersize_gdspy(polygon_oo, self.global_rough_grid_size)
        # Manhattanize to the rough grid
        polygon_oouuo_rough = self.gdspy_manh(polygon_oouuo, self.global_rough_grid_size, do_manh)
        # undersize then oversize, then oversize again, combine these stages
        # TODO: Original skill does O_UU_OO and then subtracts 2xglobal_rough.
        # TODO: Why 2xglobal rough if we only oversized effictivley by 1x?
        polygon_roughsized = self.dataprep_oversize_gdspy(
            self.dataprep_undersize_gdspy(polygon_oouuo_rough, self.global_grid_size),
            self.global_grid_size + max(size_amount - 2 * self.global_rough_grid_size, 0))

        return polygon_roughsized

    def poly_operation(self,
                       lpp_out: Union[str, Tuple[str, str]],
                       polygon1: Union[gdspy.Polygon, gdspy.PolygonSet, None],
                       polygon2: Union[gdspy.Polygon, gdspy.PolygonSet, None],
                       operation: str,
                       size_amount: Union[float, Tuple[float, float]],
                       do_manh: bool = False,
                       ) -> Union[gdspy.Polygon, gdspy.PolygonSet, None]:
        """

        Parameters
        ----------
        lpp_out : Union[str, Tuple[str, str]]
            The layer on which the shapes are being
        polygon1 : Union[gdspy.Polygon, gdspy.PolygonSet, None]
            The shapes currently on the output layer
        polygon2 : Union[gdspy.Polygon, gdspy.PolygonSet, None]
            The shapes on the input layer that will be added/subtracted to/from the output layer
        operation : str
            The operation to perform:  'rad', 'add', 'sub', 'ext', 'ouo', 'del'
        size_amount : Union[float, Tuple[Float, Float]]
            The amount to over/undersize the shapes to be added/subtracted.
            For ouo and rouo, the 0.5*minWidth related over and under size amount
        do_manh : bool
            True to perform Manhattanization during the 'rad' operation

        Returns
        -------
        polygons_out : Union[gdspy.Polygon, gdspy.PolygonSet, None]
            The new polygons present on the output layer
        """
        # TODO: clean up the input polygons first ?

        # If there are no shapes to operate on, return the shapes currently on the output layer
        if polygon2 is None:
            return polygon1
        else:
            if operation == 'rad':
                # TODO: THIS IS SLOW
                # TODO: manh ?
                polygon_rough_sized = self.dataprep_roughsize_gdspy(polygon2, size_amount=size_amount, do_manh=do_manh)

                if polygon1 is None:
                    polygon_out = polygon_rough_sized
                else:
                    polygon_out = gdspy.fast_boolean(polygon1, polygon_rough_sized, 'or')
                    polygon_out = self.dataprep_cleanup_gdspy(polygon_out, do_cleanup=self.do_cleanup)

            elif operation == 'add':
                if polygon1 is None:
                    polygon_out = self.dataprep_oversize_gdspy(polygon2, size_amount)
                else:
                    polygon_out = gdspy.fast_boolean(polygon1,
                                                     self.dataprep_oversize_gdspy(polygon2, size_amount),
                                                     'or')
                    polygon_out = self.dataprep_cleanup_gdspy(polygon_out, do_cleanup=self.do_cleanup)

            elif operation == 'sub':
                if polygon1 is None:
                    polygon_out = None
                else:
                    polygon_out = gdspy.fast_boolean(polygon1,
                                                     self.dataprep_oversize_gdspy(polygon2, size_amount),
                                                     'not')
                    polygon_out = self.dataprep_cleanup_gdspy(polygon_out, self.do_cleanup)

            elif operation == 'ext':
                # TODO:
                # if (not (member(LppOut, NotToExtendOrOverUnderOrUnderOverLpps) != nil)):
                if True:
                    polygon_toextend = polygon1
                    polygon_ref = polygon2
                    extended_amount = size_amount

                    # Round the amount to extend up based on global grid size
                    extended_amount = self.global_grid_size * ceil(extended_amount / self.global_grid_size)

                    polygon_ref_sized = self.dataprep_oversize_gdspy(polygon_ref, extended_amount)
                    polygon_extended = self.dataprep_oversize_gdspy(polygon_toextend, extended_amount)
                    polygon_extra = self.dataprep_cleanup_gdspy(gdspy.fast_boolean(polygon_extended,
                                                                                   polygon_ref,
                                                                                   'not'),
                                                                do_cleanup=self.do_cleanup)
                    polygon_toadd = self.dataprep_cleanup_gdspy(gdspy.fast_boolean(polygon_extra,
                                                                                   polygon_ref_sized,
                                                                                   'and'),
                                                                do_cleanup=self.do_cleanup)

                    polygon_out = self.dataprep_cleanup_gdspy(gdspy.fast_boolean(polygon_toextend,
                                                                                 polygon_toadd,
                                                                                 'or'),
                                                              do_cleanup=self.do_cleanup)

                    # TODO: replace 1.1 with non-magic number
                    buffer_size = max(
                        self.global_grid_size * ceil(0.5 * extended_amount / self.global_grid_size + 1.1),
                        0.0
                    )
                    polygon_out = self.dataprep_oversize_gdspy(self.dataprep_undersize_gdspy(polygon_out, buffer_size),
                                                               buffer_size)
                else:
                    pass

            elif operation == 'ouo':
                # TODO
                # if (not (member(LppIn NotToExtendOrOverUnderOrUnderOverLpps) != nil)):
                if True:
                    underofover_size = \
                        self.global_grid_size * ceil(0.5 * self.photonic_tech_info.min_space(lpp_out) /
                                                     self.global_grid_size)
                    overofunder_size = \
                        self.global_grid_size * ceil(0.5 * self.photonic_tech_info.min_width(lpp_out) /
                                                     self.global_grid_size)
                    logging.info(f'OUO on layer {lpp_out} performed with underofover_size = {underofover_size} and'
                                 f'overofunder_size = {overofunder_size}')

                    polygon_o = self.dataprep_oversize_gdspy(polygon2, underofover_size)
                    polygon_ou = self.dataprep_undersize_gdspy(polygon_o, underofover_size)
                    polygon_ouu = self.dataprep_undersize_gdspy(polygon_ou, overofunder_size)
                    polygon_out = self.dataprep_oversize_gdspy(polygon_ouu, overofunder_size)

                    # # debug
                    # polygon_out = polygon2

                else:
                    pass

            elif operation == 'rouo':
                # TODO: THIS IS SLOW
                # TODO: Check this function?
                if polygon2 is None:
                    polygon_out = None
                else:
                    min_space = self.photonic_tech_info.min_space(lpp_out)
                    min_width = self.photonic_tech_info.min_width(lpp_out)
                    underofover_size = \
                        self.global_grid_size * ceil(0.5 * min_space / self.global_grid_size)
                    overofunder_size = \
                        self.global_grid_size * ceil(0.5 * min_width / self.global_grid_size)

                    min_space_width = min(min_space, min_width)
                    simplify_tolerance = 0.999 * min_space_width * self.global_rough_grid_size / sqrt(
                        min_space_width ** 2 + self.global_rough_grid_size ** 2)
                    # simplify_tolerance = 1.4 * rough_grid_size

                    # TODO: see if do_manh should always be True here
                    polygon_manh = self.gdspy_manh(polygon2, self.global_rough_grid_size, do_manh=True)

                    polygon_o = self.dataprep_oversize_gdspy(polygon_manh, underofover_size)
                    polygon_ou = self.dataprep_undersize_gdspy(polygon_o, underofover_size)
                    polygon_ouu = self.dataprep_undersize_gdspy(polygon_ou, overofunder_size)
                    polygon_ouuo = self.dataprep_oversize_gdspy(polygon_ouu, overofunder_size)

                    # Todo: global grid or rough global grid?
                    coord_list = self.polyop_gdspy_to_point_list(polygon_ouuo,
                                                                 fracture=False,
                                                                 do_manh=False,
                                                                 manh_grid_size=self.global_rough_grid_size,
                                                                 )
                    polygon_simplified = self.simplify_coord_to_gdspy([coord_list, []],
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

    ################################################################################
    # content list manimulations
    ################################################################################
    def get_polygon_point_lists_on_layer(self,
                                         layer,  # type: Tuple[str, str]
                                         debug=False,  # type: bool
                                         ):
        """
        Returns a list of all shapes

        Parameters
        ----------
        layer : Tuple[str, str]
            the layer purpose pair to get all shapes in shapely format
        debug : bool
            true to print debug info

        Returns
        -------

        """
        content = [self.get_content_on_layer(layer)]
        return self.to_polygon_pointlist_from_content_list(content_list=content, debug=debug)

    def get_content_on_layer(self,
                             layer,  # type: Tuple[str, str]
                             ):
        # type: (...) -> Tuple
        """Returns only the content that exists on a given layer

        Parameters
        ----------
        layer : Tuple[str, str]
            the layer whose content is desired

        Returns
        -------
        content : Tuple
            the shape content on the provided layer
        """
        if layer not in self.flat_content_list_by_layer.keys():
            return ()
        else:
            return self.flat_content_list_by_layer[layer]

    def to_polygon_pointlist_from_content_list(self,
                                               content_list: List,
                                               debug: bool = False,
                                               ) -> Tuple[List, List]:
        """
        Convert the provided content list into two lists of polygon pointlists.
        The first returned list represents the positive boundaries of polygons.
        The second returned list represents the 'negative' boundaries of holes in polygons.
        All shapes in the passed content list are converted, regardless of layer.
        It is expected that the content list passed to this function only has a single LPP's content

        Parameters
        ----------
        content_list : List
            The content list to be converted to a polygon pointlist
        debug : bool
            True to print debug information

        Returns
        -------
        positive_polygon_pointlist, negative_polygon_pointlist : Tuple[List, List]
            The positive shape and negative shape (holes) polygon boundaries
        """

        positive_polygon_pointlist = []
        negative_polygon_pointlist = []

        start = time.time()
        for content in content_list:
            (cell_name, inst_tot_list, rect_list, via_list, pin_list,
             path_list, blockage_list, boundary_list, polygon_list, round_list,
             sim_list, source_list, monitor_list) = content

            # add instances
            for inst_info in inst_tot_list:
                pass

            # add rectangles
            for rect in rect_list:
                nx, ny = rect.get('arr_nx', 1), rect.get('arr_ny', 1)
                if nx > 1 or ny > 1:
                    polygon_pointlist_pos_neg = PhotonicRect.polygon_pointlist_export(
                        rect['bbox'], nx, ny,
                        spx=rect['arr_spx'], spy=rect['arr_spy']
                    )
                else:
                    polygon_pointlist_pos_neg = PhotonicRect.polygon_pointlist_export(
                        rect['bbox']
                    )

                positive_polygon_pointlist.extend(polygon_pointlist_pos_neg[0])
                negative_polygon_pointlist.extend(polygon_pointlist_pos_neg[1])

            # add vias
            for via in via_list:
                pass

            # add pins
            for pin in pin_list:
                pass

            for path in path_list:
                # Treat like polygons
                polygon_pointlist_pos_neg = PhotonicPolygon.polygon_pointlist_export(path['polygon_points'])
                positive_polygon_pointlist.extend(polygon_pointlist_pos_neg[0])
                negative_polygon_pointlist.extend(polygon_pointlist_pos_neg[1])

            for blockage in blockage_list:
                pass

            for boundary in boundary_list:
                pass

            for polygon in polygon_list:
                polygon_pointlist_pos_neg = PhotonicPolygon.polygon_pointlist_export(polygon['points'])
                positive_polygon_pointlist.extend(polygon_pointlist_pos_neg[0])
                negative_polygon_pointlist.extend(polygon_pointlist_pos_neg[1])

            for round_obj in round_list:
                polygon_pointlist_pos_neg = PhotonicRound.polygon_pointlist_export(
                    rout=round_obj['rout'],
                    rin=round_obj['rin'],
                    theta0=round_obj['theta0'],
                    theta1=round_obj['theta1'],
                    center=round_obj['center'],
                    nx=round_obj.get('nx', 1),
                    ny=round_obj.get('ny', 1),
                    spx=round_obj.get('spx', 0.0),
                    spy=round_obj.get('spy', 0.0),
                    resolution=self.grid.resolution,
                )

                positive_polygon_pointlist.extend(polygon_pointlist_pos_neg[0])
                negative_polygon_pointlist.extend(polygon_pointlist_pos_neg[1])

        end = time.time()
        if debug:
            print('layout instantiation took %.4g seconds' % (end - start))

        return positive_polygon_pointlist, negative_polygon_pointlist

    def by_layer_polygon_list_to_flat_for_gds_export(self):
        """Converts a LPP-keyed dictionary of polygon pointlists to a flat content list format for GDS export"""
        polygon_content_list = []
        for layer, polygon_pointlists in self.post_dataprep_polygon_pointlist_by_layer.items():
            for polygon_points in polygon_pointlists:
                polygon_content_list.append(
                    dict(
                        layer=(layer[0], layer[1]),
                        points=polygon_points,
                    )
                )
        # TODO: get the right name?
        self.post_dataprep_flat_content_list = [('dummy_name', [], [], [], [], [], [], [],
                                                 polygon_content_list, [], [], [], [])]

    def get_manhattanization_size_on_layer(self,
                                           layer: Union[str, Tuple[str, str]]
                                           ):
        """
        Finds the layer-specific Manhattanization size.

        Parameters
        ----------
        layer

        Returns
        -------

        """
        if isinstance(layer, tuple):
            layer = layer[0]

        per_layer_manh = self.photonic_tech_info.dataprep_routine_data['manh_size_per_layer']
        if per_layer_manh is None:
            per_layer_manh = {}

        if layer not in per_layer_manh:
            logging.info(f'Layer {layer} is not in the manh_size_per_layer dictionary in dataprep_routine file.\n'
                         f'Defaulting to global_grid_size')
            manh_size = self.global_grid_size
        else:
            manh_size = per_layer_manh[layer]

        # return 0.001
        return manh_size

    def dataprep(self,
                 push_portshapes_through_dataprep: bool = False,
                 ) -> List:
        """
        Takes the flat content list and performs the specified transformations on the shapes for the purpose
        of cleaning DRC and prepping tech specific functions.

        Notes
        -----
        1) Take the shapes in the flattened content list and convert them to gdspy format
        2) Perform each dataprep operation on the provided layers in order. dataprep_groups is a list
        where each element contains 2 other lists:
            2a) lpp_in defines the layers that the operation will be performed on
            2b) lpp_ops defines the operation to be performed
            2c) Maps the operation in the spec file to its gdspy implementation and performs it
        3) Performs a final over_under_under_over operation
        4) Take the dataprepped gdspy shapes and import them into a new post-dataprep content list

        Parameters
        ----------
        push_portshapes_through_dataprep : bool
            True to perform dataprep and convert the port indicator shapes
        """

        # 1) Convert layer shapes to gdspy polygon format
        for layer, gds_shapes in self.flat_content_list_by_layer.items():
            start = time.time()
            # TODO: fix Manhattan size
            if push_portshapes_through_dataprep or (layer[1] != 'port' and layer[1] != 'label'):
                # TODO: This is slow
                self.flat_gdspy_polygonsets_by_layer[layer] = self.dataprep_coord_to_gdspy(
                    self.get_polygon_point_lists_on_layer(layer),
                    manh_grid_size=self.get_manhattanization_size_on_layer(layer),
                    do_manh=self.GLOBAL_DO_MANH_AT_BEGINNING,
                )
                end = time.time()
                logging.info(f'Converting {layer} content to gdspy took: {end - start}s')
            else:
                logging.info(f'Did not converting {layer} content to gdspy')

        # 3) Perform each dataprep operation in the list on the provided layers in order
        start0 = time.time()
        dataprep_groups = self.photonic_tech_info.dataprep_routine_data.get('dataprep_groups', [])
        if dataprep_groups is None:
            dataprep_groups = []
        for dataprep_group in dataprep_groups:
            # 3a) Iteratively perform operations on all layers in lpp_in
            for lpp_in in dataprep_group['lpp_in']:
                shapes_in = self.flat_gdspy_polygonsets_by_layer.get(lpp_in, None)
                # 3b) Iteratively perform each operation on the current lpp_in
                for lpp_op in dataprep_group['lpp_ops']:
                    start = time.time()
                    out_layer = (lpp_op[0], lpp_op[1])
                    operation = lpp_op[2]
                    amount = lpp_op[3]

                    logging.info(f'Performing dataprep operation: {operation}  on layer: {lpp_in}  '
                                 f'to layer: {out_layer}  with size {amount}')

                    # 3c) Maps the operation in the spec file to the desired gdspy implementation and performs it
                    new_out_layer_polygons = self.poly_operation(
                        lpp_out=out_layer,
                        polygon1=self.flat_gdspy_polygonsets_by_layer.get(out_layer, None),
                        polygon2=shapes_in,
                        operation=operation,
                        size_amount=amount,
                        do_manh=self.GLOBAL_DO_MANH_DURING_OP,
                    )

                    # Update the layer's content
                    if new_out_layer_polygons is not None:
                        self.flat_gdspy_polygonsets_by_layer[out_layer] = new_out_layer_polygons

                    end = time.time()
                    logging.info(f'{operation} on {lpp_in} to {out_layer} by {amount} took: {end-start}s')
        end0 = time.time()
        logging.info(f'All dataprep layer operations took {end0 - start0}s')

        # 4) Perform a final over_under_under_over operation
        start0 = time.time()
        ouuo_list = self.photonic_tech_info.dataprep_routine_data.get('over_under_under_over', [])
        if ouuo_list is None:
            ouuo_list = []

        for lpp in ouuo_list:
            logging.info(f'Performing OUUO on {lpp}')
            start = time.time()
            new_out_layer_polygons = self.poly_operation(
                lpp_out=lpp,
                polygon1=None,
                polygon2=self.flat_gdspy_polygonsets_by_layer.get(lpp, None),
                operation='ouo',
                size_amount=0,
                do_manh=self.GLOBAL_DO_MANH_AT_BEGINNING,
            )

            if new_out_layer_polygons is not None:
                self.flat_gdspy_polygonsets_by_layer[lpp] = new_out_layer_polygons
            end = time.time()
            logging.info(f'OUUO on {lpp} took: {end-start}s')

        end0 = time.time()
        logging.info(f'All OUUO operations took a total of : {end0 - start0}s')

        # 5) Take the dataprepped gdspy shapes and import them into a new post-dataprep content list
        start0 = time.time()
        # TODO: Replace the below code by having polyop_gdspy_to_point_list directly draw the gds... ?
        for layer, gdspy_polygons in self.flat_gdspy_polygonsets_by_layer.items():
            start = time.time()
            output_shapes = self.polyop_gdspy_to_point_list(gdspy_polygons,
                                                            fracture=True,
                                                            do_manh=self.GLOBAL_DO_FINAL_MANH,
                                                            manh_grid_size=self.grid.resolution,
                                                            )
            new_shapes = []
            for shape in output_shapes:
                shape = tuple(map(tuple, shape))
                new_shapes.append([coord for coord in shape])
            self.post_dataprep_polygon_pointlist_by_layer[layer] = new_shapes

            end = time.time()
            logging.info(f'Converting {layer} from gdspy to point list took: {end - start}s')

        self.by_layer_polygon_list_to_flat_for_gds_export()

        end0 = time.time()
        logging.info(f'Converting all layers from gdspy to point list took a total of: {end0 - start0}s')

        return self.post_dataprep_flat_content_list

    def generate_lsf_flat_content_list_from_dataprep(self,
                                                     poly_list_by_layer,
                                                     sim_obj_list
                                                     ):
        """
        Takes the output of dataprep and converts it into a flat content list

        Parameters
        ----------
        poly_list_by_layer : Dict[Str, List]
            A dictionary containing lists all dataprepped polygons organized by layername
        sim_obj_list : Tuple[List, List, List]
            A tuple of lists containing all simulation objects to be used
        """
        polygon_content_list = []
        for layer, polygon_pointlists in poly_list_by_layer.items():
            for polygon_points in polygon_pointlists:
                polygon_content_list.append(
                    dict(
                        layer=(layer[0], layer[1]),
                        points=polygon_points,
                    )
                )
        self.lsf_post_dataprep_flat_content_list = [('dummy_name', [], [], [], [], [], [], [],
                                                     polygon_content_list, [],
                                                     sim_obj_list[0],
                                                     sim_obj_list[1],
                                                     sim_obj_list[2])]

    def lsf_dataprep(self,
                     push_portshapes_through_dataprep: bool = False,
                     ) -> List:
        """
        Takes the flat content list and prepares the shapes to be exported to lumerical.

        Notes
        -----
        1) Take the shapes in the flattened content list and convert them to gdspy format
        2) Parse the dataprep spec file to extract the desired procedure defined through dataprep_groups
        3) Perform each dataprep operation on the provided layers in order. dataprep_groups is a list
        where each element contains 2 other lists:
            3a) lpp_in defines the layers that the operation will be performed on
            3b) lpp_ops defines the operation to be performed
            3c) Maps the operation in the spec file to its gdspy implementation and performs it
        4) Performs a final over_under_under_over operation
        5) Take the dataprepped gdspy shapes and import them into a new post-dataprep content list

        Parameters
        ----------
        push_portshapes_through_dataprep : bool
            True to perform dataprep and convert the port indicator shapes
        """

        # 1) Convert layer shapes to gdspy polygon format
        for layer, gds_shapes in self.flat_content_list_by_layer.items():
            # If shapes on the layer need to be dataprepped, convert them to gdspy polygons and add to list
            if push_portshapes_through_dataprep or (layer[1] != 'port' and layer[1] != 'label' and layer[1] != 'sim'):
                self.lsf_flat_gdspy_polygonsets_by_layer[layer] = self.dataprep_coord_to_gdspy(
                    self.get_polygon_point_lists_on_layer(layer),
                    manh_grid_size=self.get_manhattanization_size_on_layer(layer),
                    do_manh=False,  # TODO: Pavan had this set to false
                )

        # 3) Perform each dataprep operation in the list on the provided layers in order
        dataprep_groups = self.photonic_tech_info.lsf_export_parameters.get('dataprep_groups', [])
        if dataprep_groups is None:
            dataprep_groups = []

        for dataprep_group in dataprep_groups:
            # 3a) Iteratively perform operations on all layers in lpp_in
            for lpp_in in dataprep_group['lpp_in']:
                shapes_in = self.lsf_flat_gdspy_polygonsets_by_layer.get(lpp_in, None)
                # 3b) Iteratively perform each operation on the current lpp_in
                for lpp_op in dataprep_group['lpp_ops']:
                    out_layer = (lpp_op[0], lpp_op[1])
                    operation = lpp_op[2]
                    amount = lpp_op[3]
                    # 3c) Maps the operation in the spec file to the desired gdspy implementation and performs it
                    new_out_layer_polygons = self.poly_operation(
                        lpp_out=out_layer,
                        polygon1=self.flat_gdspy_polygonsets_by_layer.get(out_layer, None),
                        polygon2=shapes_in,
                        operation=operation,
                        size_amount=amount,
                        do_manh=False,
                    )

                    # Update the layer's content
                    if new_out_layer_polygons is not None:
                        self.lsf_flat_gdspy_polygonsets_by_layer[out_layer] = new_out_layer_polygons

        # 4) Perform a final over_under_under_over operation
        ouuo_list = self.photonic_tech_info.lsf_export_parameters.get('over_under_under_over', [])
        if ouuo_list is None:
            ouuo_list = []

        for lpp in ouuo_list:
            new_out_layer_polygons = self.poly_operation(
                lpp_out=lpp,
                polygon1=None,
                polygon2=self.lsf_flat_gdspy_polygonsets_by_layer.get(lpp, None),
                operation='ouo',
                size_amount=0,
                do_manh=False,
            )

            if new_out_layer_polygons is not None:
                self.lsf_flat_gdspy_polygonsets_by_layer[lpp] = new_out_layer_polygons

        # 5) Take the dataprepped gdspy shapes and import them into a new post-dataprep content list
        # TODO: Replace the below code by having polyop_gdspy_to_point_list directly draw the gds... ?
        for layer, gdspy_polygons in self.lsf_flat_gdspy_polygonsets_by_layer.items():
            output_shapes = self.polyop_gdspy_to_point_list(gdspy_polygons,
                                                            fracture=True,
                                                            do_manh=False,
                                                            manh_grid_size=self.grid.resolution,
                                                            )
            new_shapes = []
            for shape in output_shapes:
                shape = tuple(map(tuple, shape))
                new_shapes.append([coord for coord in shape])
            self.lsf_post_dataprep_polygon_pointlist_by_layer[layer] = new_shapes

        # Reconstructs content list from dataprepped polygons and with simulation objects
        # TODO: Support creation of multiple masters
        self.generate_lsf_flat_content_list_from_dataprep(self.lsf_post_dataprep_polygon_pointlist_by_layer,
                                                          [self.flat_content_list_separate[0][10],
                                                           self.flat_content_list_separate[0][11],
                                                           self.flat_content_list_separate[0][12]])

        return self.lsf_post_dataprep_flat_content_list
