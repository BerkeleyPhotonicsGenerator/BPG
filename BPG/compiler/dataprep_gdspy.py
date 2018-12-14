import warnings
import gdspy
import time
import numpy as np
import sys
import logging
import re

from BPG.objects import PhotonicRect, PhotonicPolygon, PhotonicRound
from BPG.compiler.point_operations import coords_cleanup
from BPG.content_list import ContentList

from math import ceil
from typing import TYPE_CHECKING, Tuple, List, Union, Dict, Optional, Pattern, Iterable

if TYPE_CHECKING:
    from BPG.photonic_core import PhotonicTechInfo
    from bag.layout.routing import RoutingGrid
    from BPG.bpg_custom_types import lpp_type

################################################################################
# define parameters for testing
################################################################################

# GDSPY should use the largest possible number of points before fracturing in its computations
MAX_SIZE = sys.maxsize

# Create a separate logger for large dataprep debug information
dataprep_logger = logging.getLogger('dataprep')

# Suppress warnings from GDSPY about polygons with more than 199 points
warnings.filterwarnings(
    action='ignore',
    message='.*polygon with more than 199 points was created.*',
)

# List of
IMPLEMENTED_DATAPREP_OPERATIONS = ['rad', 'add', 'manh', 'ouo', 'sub', 'ext']


class Dataprep:
    def __init__(self,
                 photonic_tech_info: "PhotonicTechInfo",
                 grid: "RoutingGrid",
                 content_list_flat: "ContentList",
                 is_lsf: bool = False,
                 impl_cell=None,
                 ):
        """

        Parameters
        ----------
        photonic_tech_info
        grid : RoutingGrid
            The bag routingGrid object for this layout.
        content_list_flat : ContentList
            The flattened content list
        is_lsf : bool = False
            True if the Dataprep object is being used for LSF dataprep flow.
            False if the Dataprep object is being used for standard dataprep.

        """
        self.photonic_tech_info: PhotonicTechInfo = photonic_tech_info
        self.grid = grid
        self.content_list_flat: "ContentList" = content_list_flat
        self.is_lsf = is_lsf

        # Sort the flattened content list into the different layers
        start = time.time()
        self.content_list_flat_sorted_by_layer = content_list_flat.sort_content_list_by_layers()
        end = time.time()
        logging.info(f'Sorting flat content list by layer took {end - start:.4g}s')

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
        self.GLOBAL_DO_MANH_AT_BEGINNING = False
        # SKILL has GLOBAL_DO_MANH_DURING_OP as True. Only used during rad for both skill and gdspy
        # implementations
        self.GLOBAL_DO_MANH_DURING_OP = True

        # True to ensure that final shape will be on a Manhattan grid. If GLOBAL_DO_MANH_AT_BEGINNING
        # and GLOBAL_DO_MANH_DURING_OP are set,
        # GLOBAL_DO_FINAL_MANH can be False, and we should still have Manhattanized shapes on Manhattan grid
        # if function implementations are correct
        self.GLOBAL_DO_FINAL_MANH = False

        # Initialize dataprep related structures
        # Dictionary of layer-keyed gdspy polygonset shapes
        self.flat_gdspy_polygonsets_by_layer: Dict[Tuple[str, str], Union[gdspy.PolygonSet, gdspy.Polygon]] = {}
        # Dictionary of layer-keyed polygon point-lists (lists of points comprising the polygons on the layer)
        self.post_dataprep_polygon_pointlist_by_layer: Dict[Tuple[str, str], List] = {}
        # BAG style content list after dataprep
        self.content_list_flat_post_dataprep: "ContentList" = None

        # Dataprep custom configuration
        # bypass and ignore lists are lists of LPP pairs in tuple state.
        self.dataprep_ignore_list: List[Tuple[str, str]] = []
        self.dataprep_bypass_list: List[Tuple[str, str]] = []

        dataprep_ignore_list_temp = self.photonic_tech_info.dataprep_routine_data.get(
            'dataprep_ignore_list', [])
        dataprep_bypass_list_temp = self.photonic_tech_info.dataprep_routine_data.get(
            'dataprep_bypass_list', [])

        # If ignore/bypass were not specified in the yaml, handle appropriately. If they were specified
        # reformat ignore and bypass lists, as they are specified as dictionaries in the yaml
        if dataprep_ignore_list_temp is None:
            self.dataprep_ignore_list = []
        else:
            # lpp entries can be regex. Find all layers to ignore now
            for lpp_entry in dataprep_ignore_list_temp:
                self.dataprep_ignore_list.extend(
                    self.regex_search_lpps(
                        regex=self._check_input_lpp_entry_and_convert_to_regex(lpp_entry),
                        keys=self.content_list_flat_sorted_by_layer.keys()
                    )
                )

        if dataprep_bypass_list_temp is None:
            self.dataprep_bypass_list = []
        else:
            # lpp entries can be regex. Find all layers to bypass now
            for lpp_entry in dataprep_bypass_list_temp:
                self.dataprep_bypass_list.extend(
                    self.regex_search_lpps(
                        regex=self._check_input_lpp_entry_and_convert_to_regex(lpp_entry),
                        keys=self.content_list_flat_sorted_by_layer.keys()
                    )
                )

        # Load the dataprep operations list and OUUO list
        self.ouuo_regex_list: List[Tuple[Pattern, Pattern]] = []
        self.dataprep_groups: List[Dict] = []
        if self.is_lsf:
            dataprep_groups_temp = self.photonic_tech_info.lsf_export_parameters.get('dataprep_groups', [])
            ouuo_list_temp = self.photonic_tech_info.lsf_export_parameters.get('over_under_under_over', [])
        else:
            dataprep_groups_temp = self.photonic_tech_info.dataprep_routine_data.get('dataprep_groups', [])
            ouuo_list_temp = self.photonic_tech_info.dataprep_routine_data.get('over_under_under_over', [])

        if dataprep_groups_temp is None:
            self.dataprep_groups = []
        else:
            for dataprep_group in dataprep_groups_temp:
                self.dataprep_groups.append(self._check_dataprep_ops(dataprep_group))

        if ouuo_list_temp is None:
            self.ouuo_regex_list = []
        else:
            # lpp entries can be regex. Keep as regex, as the final list of used layers is not known at this time
            for lpp_entry in ouuo_list_temp:
                self.ouuo_regex_list.append(self._check_input_lpp_entry_and_convert_to_regex(lpp_entry))

        # cache list of polygons
        self.polygon_cache: Dict[Tuple, Union[gdspy.Polygon, gdspy.PolygonSet]] = {}

        # Set the cell name for flattened gds output
        if type(impl_cell) is str:
            self.impl_cell = impl_cell
        else:
            self.impl_cell = "dummy_name"

    @staticmethod
    def _check_input_lpp_entry_and_convert_to_regex(lpp_entry,
                                                    ) -> Tuple[Pattern, Pattern]:
        """
        Checks whether the lpp entry is a dictionary with an 'lpp' key, whose value is a list composed of 2 strings
        Raises an error if the lpp entry is not valid.

        Parameters
        ----------
        lpp_entry :
            The lpp entry from the yaml file to check

        Returns
        -------
        lpp_key : Tuple[Pattern, Pattern]
            The valid lpp as a tuple of two regex patterns.
        """
        if not isinstance(lpp_entry, dict):
            raise ValueError(f'lpp list entries must be dictionaries.\n'
                             f'Entry {lpp_entry} violates this.')
        lpp_layer = lpp_entry.get('lpp', None)
        if lpp_layer is None:
            raise ValueError(f'List entries must be dictionaries with an lpp key:'
                             f'  - {{lpp: [layer, purpose]}}\n'
                             f'Entry {lpp_entry} violates this.')

        if len(lpp_layer) != 2:
            raise ValueError(f'lpp entry must specify a layer and a purpose, in that order.\n'
                             f'Specified lpp {lpp_layer} does not meet this criteria.')
        if not (isinstance(lpp_layer[0], str) and isinstance(lpp_layer[1], str)):
            raise ValueError(f'Lpp layers and purposes must be specified as a list of two strings.\n'
                             f'Entry {lpp_layer} does not meet this criteria.')

        # Try to compile the lpp entries to ensure they are valid regexes
        layer_regex = re.compile(lpp_layer[0])
        purpose_regex = re.compile(lpp_layer[1])

        return layer_regex, purpose_regex

    def _check_dataprep_ops(self,
                            dataprep_group,
                            ) -> Dict[str, List]:
        """
        Checks whether the passed dataprep group is valid.
        Raises an error if the dataprep group is not valid.

        Parameters
        ----------
        dataprep_group :
            The dataprep_group entry from the yaml file to check.

        Returns
        -------
        dataprep_group_clean : Dict[str, List]
            The clean
        """
        # Check that lpp_in and lpp_ops are specified, and that they are both lists
        if 'lpp_in' not in dataprep_group:
            raise ValueError(f'Dataprep group entry must be a dictionary containing a key named \'lpp_in\'.\n'
                             f'Dataprep group {dataprep_group} does not meet this criteria.')
        if 'lpp_ops' not in dataprep_group:
            raise ValueError(f'Dataprep group entry must be a dictionary containing a key named \'lpp_ops\'.\n'
                             f'Dataprep group {dataprep_group} does not meet this criteria.')
        if not (isinstance(dataprep_group['lpp_in'], list)):
            raise ValueError(f'lpp_in must be a list of dictionaries.\n'
                             f'Dataprep group {dataprep_group} does not meet this criteria.')
        if not (isinstance(dataprep_group['lpp_ops'], list)):
            raise ValueError(f'lpp_ops must be a list of dictionaries.\n'
                             f'Dataprep group {dataprep_group} does not meet this criteria.')

        # Check the lpp_in entries
        lpp_in_clean = []
        for lpp_in_entry in dataprep_group['lpp_in']:
            lpp_in_clean.append(self._check_input_lpp_entry_and_convert_to_regex(lpp_in_entry))

        # Check the lpp_ops entries
        lpp_op_clean = []
        for lpp_op_entry in dataprep_group['lpp_ops']:
            # Check entry is a dict
            if not isinstance(lpp_op_entry, dict):
                raise ValueError(f'lpp_ops entries must be dictionaries.\n'
                                 f'Dataprep group {dataprep_group} does not meet this criteria.')
            # Check that 'operation' is specified and valid
            if 'operation' not in lpp_op_entry:
                raise ValueError(f'lpp_ops entry must specify a value for the key \'operation\'\n'
                                 f'Dataprep group {dataprep_group} does not meet this criteria.')
            if lpp_op_entry['operation'] not in IMPLEMENTED_DATAPREP_OPERATIONS:
                raise ValueError(f'The following dataprep operations are implemented at this '
                                 f'time: {IMPLEMENTED_DATAPREP_OPERATIONS}\n'
                                 f'Dataprep group {dataprep_group} uses an unsupported dataprep '
                                 f'operation {lpp_op_entry["operation"]}.')

            operation = lpp_op_entry['operation']

            # Check amount is specified and valid, if necessary
            amount = lpp_op_entry.get('amount', None)
            if (amount is None) and (operation != 'manh'):
                raise ValueError(f'Amount must be specified for operation \'{operation}\' '
                                 f'in dataprep group {dataprep_group}')
            if (amount is not None) and not (isinstance(amount, int) or isinstance(amount, float)):
                raise ValueError(f'amount must be a float or int.\n'
                                 f'Operation \'{operation}\' in dataprep group {dataprep_group} '
                                 f'does not meet this criteria.')

            out_layer = lpp_op_entry.get('lpp', None)
            if (out_layer is None) and (operation != 'manh'):
                raise ValueError(f'output lpp must be specified for operation \'{operation}\' '
                                 f'in dataprep group {dataprep_group}')
            if out_layer is not None:
                if len(out_layer) != 2:
                    raise ValueError(f'lpp entry must specify a layer and a purpose, in that order.\n'
                                     f'Specified entry {out_layer} does not meet this criteria.')
                if not (isinstance(out_layer[0], str) and isinstance(out_layer[1], str)):
                    raise ValueError(f'Lpp layers and purposes must be specified as a list of two strings.\n'
                                     f'{out_layer} in dataprep group {dataprep_group} does not meet this criteria.')
                out_layer = (out_layer[0], out_layer[1])

            lpp_op_clean.append(
                dict(
                    operation=operation,
                    amount=amount,
                    lpp=out_layer,
                )
            )

        return dict(
            lpp_in=lpp_in_clean,
            lpp_ops=lpp_op_clean,
        )

    ################################################################################
    # clean up functions for coordinate lists and gdspy objects
    ################################################################################
    def dataprep_cleanup_gdspy(self,
                               polygon: Union[gdspy.Polygon, gdspy.PolygonSet, None],
                               do_cleanup: bool = True,
                               ) -> Union[gdspy.Polygon, gdspy.PolygonSet, None]:
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
    # type-converting functions for coordlist/gdspy
    ################################################################################

    def dataprep_coord_to_gdspy(
            self,
            pos_neg_list_list: Tuple[List[List[Tuple[float, float]]], List[List[Tuple[float, float]]]],
            manh_grid_size: float,
            do_manh: bool,  # TODO: Remove this argument?
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

    def polyop_gdspy_to_point_list(self,
                                   polygon_gdspy_in: Union[gdspy.Polygon, gdspy.PolygonSet],
                                   fracture: bool = True,
                                   do_manh: bool = True,
                                   manh_grid_size: Optional[float] = None,
                                   ) -> List[List[Tuple[float, float]]]:
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
            dataprep_logger.debug(f'polyop_gdspy_to_point_list: gdspy_manh took: {end-start}s')

        if fracture:
            start = time.time()
            # TODO: Magic numbers
            polygon_gdspy = polygon_gdspy_in.fracture(max_points=4094, precision=self.global_grid_size)
            end = time.time()
            dataprep_logger.debug(f'polyop_gdspy_to_point_list: fracturing took: {end-start}s')
        else:
            polygon_gdspy = polygon_gdspy_in

        output_list_of_coord_lists = []
        if isinstance(polygon_gdspy, gdspy.Polygon):
            output_list_of_coord_lists = [np.round(polygon_gdspy.points, 3)]
            # TODO: Magic number. round based on layout_unit and resolution

            non_manh_edge = self.not_manh(polygon_gdspy.points)
            if non_manh_edge:
                logging.debug(f'Warning: a non-Manhattanized polygon is created in polyop_gdspy_to_point_list, '
                              f'number of non-manh edges is {non_manh_edge}')

        elif isinstance(polygon_gdspy, gdspy.PolygonSet):
            for poly in polygon_gdspy.polygons:
                output_list_of_coord_lists.append(np.round(poly, 3))
                # TODO: Magic number. round based on layout_unit and resolution

                non_manh_edge = self.not_manh(poly)
                if non_manh_edge:
                    logging.debug(f'Warning: a non-Manhattanized polygon is created in polyop_gdspy_to_point_list, '
                                  f'number of non-manh edges is {non_manh_edge}')
        else:
            raise ValueError('polygon_gdspy must be a gdspy.Polygon or gdspy.PolygonSet')

        return output_list_of_coord_lists

    ################################################################################
    # Manhattanization related functions
    ################################################################################
    @staticmethod
    def merge_adjacent_duplicate(coord_set: np.ndarray,
                                 eps_grid: float = 1e-6,
                                 ) -> np.ndarray:
        """
        Merges all points in the passed list of coordinates that are duplicate adjacent points.

        Parameters
        ----------
        coord_set : np.ndarray
            The input list of coordinates to check for adjacent duplicates.
        eps_grid : float
            The grid tolerance below which points are considered the same.

        Returns
        -------
        coord_set_merged : np.ndarray
            The coordinate list with all adjacent duplicate points removed.
        """

        coord_set_shift = np.roll(coord_set, 1, axis=0)
        # 2D array: array of [abs(deltax) > eps, abs(deltay) > eps]
        coord_cmp_eq = np.abs(coord_set_shift - coord_set) < eps_grid
        # 1D array: array of [this point is not a duplicate]
        select = np.sum(coord_cmp_eq, axis=1) <= 1

        coord_set_merged = coord_set[select]

        return coord_set_merged

    @staticmethod
    def not_manh(coord_list: np.ndarray,
                 eps_grid: float = 1e-6,
                 ) -> int:
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

        coord_set_shift = np.roll(coord_list, 1, axis=0)
        # 2D array: array of [deltax > eps, deltay > eps]
        coord_cmp = np.abs(coord_set_shift - coord_list) > eps_grid
        # 1D array: array of [this edge is not manhattanized]
        edge_not_manh = np.sum(coord_cmp, axis=1) > 1

        non_manh_edge = int(np.sum(edge_not_manh, axis=0))

        return non_manh_edge

    @staticmethod
    def manh_edge_tran(p1: np.ndarray,
                       dx: float,
                       dy: float,
                       nstep: int,
                       inc_x_first: bool,
                       manh_grid_size: float,
                       eps_grid: float = 1e-4,
                       ) -> np.ndarray:
        """
        Converts pointlist of an edge (ie 2 points), to a pointlist of a Manhattanized edge.

        Parameters
        ----------
        p1 : np.ndarray
            The starting point of the non-Manhattan edge.
        dx : float
            The x distance to the next point.
        dy : float
            The y distance to the next point.
        nstep : int
            The number of steps (each consisting of one horizontal and one vertical segment) that must be added.
        inc_x_first : bool
            True if the first segment should be horizontal.
        manh_grid_size : float
            The grid size on which to quantize the steps.
        eps_grid : float
            The size below which points are considered the same.

        Returns
        -------
        edge_coord_set : np.ndarray
            The array of coordinates that define the new Manhattanized edge.
        """
        # this point and the next point can form a manhattanized edge, no need to create new points
        if (abs(dx) < eps_grid) or (abs(dy) < eps_grid):
            edge_coord_set = np.array([p1.tolist()])
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
                   poly_coords: Union[List[Tuple[float, float]], np.ndarray],
                   manh_grid_size: float,
                   manh_type: str,
                   ) -> np.ndarray:
        """
        Convert a polygon into a polygon with orthogonal edges (ie, performs Manhattanization)

        Parameters
        ----------
        poly_coords : Union[List[Tuple[float, float]], np.ndarray]
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

        def apprx_equal(float1: float,
                        float2: float,
                        eps_grid: float = 1e-9,
                        ) -> bool:
            return abs(float1 - float2) < eps_grid

        def apprx_equal_coord(coord1: Tuple[float, float],
                              coord2: Tuple[float, float],
                              eps_grid: float = 1e-9,
                              ) -> bool:
            return apprx_equal(coord1[0], coord2[0], eps_grid) and (apprx_equal(coord1[1], coord2[0], eps_grid))

        # map the coordinates to the manh grid
        if isinstance(poly_coords, np.ndarray):
            poly_coords_ori = poly_coords
        else:
            poly_coords_ori = np.array(poly_coords)

        dataprep_logger.debug(f'in manh_skill, manh_grid_size: {manh_grid_size}')
        dataprep_logger.debug(f'in manh_skill, poly_coords before mapping to manh grid: {poly_coords_ori}')

        if poly_coords_ori.size == 0:
            return poly_coords_ori

        poly_coords_manhgrid = manh_grid_size * np.round(poly_coords_ori / manh_grid_size)

        dataprep_logger.debug(f'in manh_skill, poly_coords after mapping to manh grid: {poly_coords_manhgrid}')

        # poly_coords_manhgrid = self.coords_cleanup(poly_coords_manhgrid)
        poly_coords_manhgrid = self.merge_adjacent_duplicate(poly_coords_manhgrid)

        # adding the first point to the last if polygon is not closed
        if not apprx_equal_coord(poly_coords_manhgrid[0], poly_coords_manhgrid[-1]):
            poly_coords_manhgrid = np.append(poly_coords_manhgrid, [poly_coords_manhgrid[0]], axis=0)

        # do Manhattanization if manh_type is 'inc'
        if manh_type == 'non':
            return poly_coords
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

            # Scanning all the points of the original set and adding points in-between.
            poly_coords_orth = []
            for i in range(0, len(poly_coords_manhgrid)):
                coord_curr = poly_coords_manhgrid[i]
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
                for i in range(0, len(poly_coords_orth_manhgrid) - 1):
                    p1 = poly_coords_orth_manhgrid[i]
                    p2 = poly_coords_orth_manhgrid[i + 1]
                    if p1[0] != p2[0] and p1[1] != p2[1]:
                        print('non_manh_edge:', p1, p2)

                raise ValueError(f'Manhattanization failed before the clean-up, '
                                 f'number of non-manh edges is {nonmanh_edge_pre}')

            poly_coords_cleanup = coords_cleanup(poly_coords_orth_manhgrid)
            if poly_coords_cleanup.size != 0:
                poly_coords_cleanup = np.append(poly_coords_cleanup, [poly_coords_cleanup[0]], axis=0)
            nonmanh_edge_post = self.not_manh(poly_coords_cleanup)
            if nonmanh_edge_post:
                for i in range(0, len(poly_coords_cleanup)):
                    p1 = poly_coords_cleanup[i]
                    if i == len(poly_coords_cleanup) - 1:
                        p2 = poly_coords_cleanup[0]
                    else:
                        p2 = poly_coords_orth_manhgrid[i + 1]
                    if p1[0] != p2[0] and p1[1] != p2[1]:
                        print('non_manh_edge:', p1, p2)
                raise ValueError(f'Manhattanization failed after the clean-up, '
                                 f'number of non-manh edges is {nonmanh_edge_post}')

            return poly_coords_cleanup
        else:
            raise ValueError(f'manh_type = {manh_type} should be either "non", "inc" or "dec"')

    def gdspy_manh(self,
                   polygon_gdspy: Union[gdspy.Polygon, gdspy.PolygonSet, None],
                   manh_grid_size: float,
                   do_manh: bool,
                   ) -> Union[gdspy.Polygon, gdspy.PolygonSet]:
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
        dataprep_logger.debug(f'gdspy_man took {end-start}s')

        return polygon_out

    ################################################################################
    # Dataprep related operations
    ################################################################################
    def dataprep_oversize_gdspy(self,
                                polygon: Union[gdspy.Polygon, gdspy.PolygonSet, None],
                                offset: float,
                                ) -> Union[gdspy.Polygon, gdspy.PolygonSet, None]:
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
                                 polygon: Union[gdspy.Polygon, gdspy.PolygonSet, None],
                                 offset: float,
                                 ) -> Union[gdspy.Polygon, gdspy.PolygonSet, None]:
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
                                 polygon: Union[gdspy.Polygon, gdspy.PolygonSet],
                                 size_amount: float,
                                 do_manh: bool,
                                 ) -> Union[gdspy.Polygon, gdspy.PolygonSet]:
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
                       lpp_in: Union[str, Tuple[str, str]],
                       lpp_out: Union[str, Tuple[str, str]],
                       polygon1: Union[gdspy.Polygon, gdspy.PolygonSet, None],
                       polygon2: Union[gdspy.Polygon, gdspy.PolygonSet, None],
                       operation: str,
                       size_amount: Union[float, Tuple[float, float]],
                       do_manh_in_rad: bool = False,
                       ) -> Union[gdspy.Polygon, gdspy.PolygonSet, None]:
        """
        Performs a dataprep operation on the input shapes passed by polygon2, and merges (adds/subtracts to/from,
        replaces, etc) with the shapes currently on the layer passed by polygon1.

        The operations implemented in this function must be kept up to date with IMPLEMENTED_DATAPREP_OPERATIONS.

        Parameters
        ----------
        lpp_in : Union[str, Tuple[str, str]]
            The source layer on which the shapes being added/subtracted are located
        lpp_out : Union[str, Tuple[str, str]]
            The destination layer on which the shapes are being added to / subtracted from
        polygon1 : Union[gdspy.Polygon, gdspy.PolygonSet, None]
            The shapes currently on the output layer
        polygon2 : Union[gdspy.Polygon, gdspy.PolygonSet, None]
            The shapes on the input layer that will be added/subtracted to/from the output layer
        operation : str
            The operation to perform:  'manh', 'rad', 'add', 'sub', 'ext', 'ouo'. The implemented functions must match
            the variable IMPLEMENTED_DATAPREP_OPERATIONS.
        size_amount : Union[float, Tuple[Float, Float]]
            The amount to over/undersize the shapes to be added/subtracted.
            For ouo, the 0.5*minWidth related over and under size amount
        do_manh_in_rad : bool
            True to perform Manhattanization during the 'rad' operation

        Returns
        -------
        polygons_out : Union[gdspy.Polygon, gdspy.PolygonSet, None]
            The new polygons present on the output layer
        """

        # If there are no shapes to operate on, return the shapes currently on the output layer
        if polygon2 is None:
            return polygon1
        else:
            # Create the key for the polygon cache
            polygon_key = (lpp_in, operation, size_amount, do_manh_in_rad)

            if operation == 'manh':
                # Manhattanize the shape.
                # Overwrite any shapes currently on the output layer, so disregard polygon1
                polygon_out = self.dataprep_cleanup_gdspy(
                    polygon=self.gdspy_manh(
                        polygon_gdspy=polygon2,
                        manh_grid_size=size_amount,
                        do_manh=True  # TODO: Remove this argument?
                    ),
                    do_cleanup=self.do_cleanup
                )

            elif operation == 'rad':
                # Rough add the shape

                # Try to find the polygon in the cache list
                if polygon_key in self.polygon_cache:
                    polygon_rough_sized = self.polygon_cache[polygon_key]
                else:
                    # Need to compute the roughadd shape and update the cache
                    polygon_rough_sized = self.dataprep_roughsize_gdspy(polygon2,
                                                                        size_amount=size_amount,
                                                                        do_manh=do_manh_in_rad)
                    self.polygon_cache[polygon_key] = polygon_rough_sized

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

            elif operation == 'ouo':
                # Perform an over of under of under of over on the shapes

                min_space = self.photonic_tech_info.min_space(lpp_out)
                min_width = self.photonic_tech_info.min_width(lpp_out)
                underofover_size = self.global_grid_size * ceil(0.5 * min_space / self.global_grid_size)
                overofunder_size = self.global_grid_size * ceil(0.5 * min_width / self.global_grid_size)

                logging.info(f'OUO on layer {lpp_out} performed with underofover_size = {underofover_size} and'
                             f'overofunder_size = {overofunder_size}')

                polygon_o = self.dataprep_oversize_gdspy(polygon2, underofover_size)
                polygon_ou = self.dataprep_undersize_gdspy(polygon_o, underofover_size)
                polygon_ouu = self.dataprep_undersize_gdspy(polygon_ou, overofunder_size)
                polygon_out = self.dataprep_oversize_gdspy(polygon_ouu, overofunder_size)

            elif operation == 'del':
                # TODO
                polygon_out = None
                pass
            else:
                raise ValueError(f'Operation {operation} specified in dataprep algorithm, but is not implemented.')

            # Invalidate the cache for the current output layer, as it has changed, and future dataprep operations must
            # use the new shapes
            # Delete the key from the polygon cache if it exists
            if lpp_out in [key[0] for key in self.polygon_cache.keys()]:
                self.polygon_cache.pop(polygon_key, None)

            return polygon_out

    ################################################################################
    # content list manipulations
    ################################################################################
    def get_polygon_point_lists_on_layer(self,
                                         layer: "lpp_type",
                                         ) -> Tuple[List, List]:
        """
        Returns a list of all shapes

        Parameters
        ----------
        layer : Tuple[str, str]
            the layer purpose pair on which to get all shapes

        Returns
        -------
        positive_polygon_pointlist, negative_polygon_pointlist : Tuple[List, List]
            The lists of positive shape and negative shape (holes) polygon boundaries
        """
        content = self.get_content_on_layer(layer)
        return self.to_polygon_pointlist_from_content_list(content_list=content)

    def get_content_on_layer(self,
                             layer: Tuple[str, str],
                             ) -> "ContentList":
        """Returns only the content that exists on a given layer

        Parameters
        ----------
        layer : Tuple[str, str]
            the layer whose content is desired

        Returns
        -------
        content : ContentList
            the shape content on the provided layer
        """
        if layer not in self.content_list_flat_sorted_by_layer.keys():
            # Return an empty content list
            return ContentList()
        else:
            return self.content_list_flat_sorted_by_layer[layer]

    def to_polygon_pointlist_from_content_list(self,
                                               content_list: "ContentList",
                                               ) -> Tuple[List, List]:
        """
        Convert the provided content list into two lists of polygon pointlists.
        The first returned list represents the positive boundaries of polygons.
        The second returned list represents the 'negative' boundaries of holes in polygons.
        All shapes in the passed content list are converted, regardless of layer.
        It is expected that the content list passed to this function only has a single LPP's content

        Parameters
        ----------
        content_list : ContentList
            The content list to be converted to a polygon pointlist

        Returns
        -------
        positive_polygon_pointlist, negative_polygon_pointlist : Tuple[List, List]
            The positive shape and negative shape (holes) polygon boundaries

        Notes
        -----
        No need to loop over content_list, as dataprep only handles a single master at a time
        No need to handle instance looping, as there are no instances in the flattened content list
        """

        positive_polygon_pointlist = []
        negative_polygon_pointlist = []

        start = time.time()

        # add rectangles
        for rect in content_list.rect_list:
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
        for via in content_list.via_list:
            pass

        # add pins
        for pin in content_list.pin_list:
            pass

        for path in content_list.path_list:
            # Treat like polygons
            polygon_pointlist_pos_neg = PhotonicPolygon.polygon_pointlist_export(path['polygon_points'])
            positive_polygon_pointlist.extend(polygon_pointlist_pos_neg[0])
            negative_polygon_pointlist.extend(polygon_pointlist_pos_neg[1])

        for blockage in content_list.blockage_list:
            pass

        for boundary in content_list.boundary_list:
            pass

        for polygon in content_list.polygon_list:
            polygon_pointlist_pos_neg = PhotonicPolygon.polygon_pointlist_export(polygon['points'])
            positive_polygon_pointlist.extend(polygon_pointlist_pos_neg[0])
            negative_polygon_pointlist.extend(polygon_pointlist_pos_neg[1])

        for round_obj in content_list.round_list:
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
        logging.debug(f'Conversion from ContentList to polygon pointlist format took {end-start:.4g}')

        return positive_polygon_pointlist, negative_polygon_pointlist

    @staticmethod
    def polygon_list_by_layer_to_flat_content_list(poly_list_by_layer: Dict["lpp_type", List],
                                                   sim_list: List,
                                                   source_list: List,
                                                   monitor_list: List,
                                                   impl_cell: str = 'no_name_cell',         # TODO: get the right name?
                                                   ) -> "ContentList":
        """
        Converts a LPP-keyed dictionary of polygon pointlists to a flat ContentList format

        Parameters
        ----------
        poly_list_by_layer : Dict[Str, List]
            A dictionary containing lists all dataprepped polygons organized by layername
        sim_list : List
            The list of simulation boundary content
        source_list : List
            The list of source object content
        monitor_list : List
            The list of monitor object content
        impl_cell : str
            Name of cell in flat gds output

        Returns
        -------
        flat_content_list : ContentList
            The data in flat content-list-format.

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

        # TODO: get the right name?
        return ContentList(cell_name=impl_cell,
                           polygon_list=polygon_content_list,
                           sim_list=sim_list,
                           source_list=source_list,
                           monitor_list=monitor_list
                           )

    def get_manhattanization_size_on_layer(self,
                                           layer: Union[str, Tuple[str, str]]
                                           ) -> float:
        """
        Finds the layer-specific Manhattanization size.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer or LPP being Manhattanized.

        Returns
        -------
        manh_size : float
            The Manhattanization size for the layer.
        """
        if isinstance(layer, tuple):
            layer = layer[0]

        per_layer_manh = self.photonic_tech_info.dataprep_routine_data['manh_size_per_layer']
        if per_layer_manh is None:
            logging.warning(f'\'manh_size_per_layer\' dictionary is not specified in the dataprep_routine.yaml file.'
                            f'Defaulting to empty dictionary.')
            per_layer_manh = {}

        if layer not in per_layer_manh:
            logging.info(f'Layer {layer} is not in the manh_size_per_layer dictionary in dataprep_routine file.\n'
                         f'Defaulting to global_grid_size')
            manh_size = self.global_grid_size
        else:
            manh_size = per_layer_manh[layer]

        return manh_size

    @staticmethod
    def regex_search_lpps(regex: Tuple[Pattern, Pattern],
                          keys: Iterable[Tuple[str, str]],
                          ) -> List[Tuple[str, str]]:
        """
        Returns a list of all keys in the dictionary that match the passed lpp regex.
        Searches for a match in both the layer and purpose regex.

        Parameters
        ----------
        regex : Tuple[Pattern, Pattern]
            The lpp regex patterns to match
        keys : Iterable[Tuple[str, str]]
            The iterable containing the keys of the dictionary.

        Returns
        -------
        matches : List[Tuple[str, str]]
            The list of dictionary keys that match the provided regex
        """
        matches = []
        for key in keys:
            if regex[0].fullmatch(key[0]) and regex[1].fullmatch(key[1]):
                matches.append(key)

        return matches

    def dataprep(self) -> ContentList:
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
        """

        start0 = time.time()
        # 1) Convert layer shapes to gdspy polygon format
        logging.info(f'-------- Converting polygons from content list to gdspy format --------')
        for layer, gds_shapes in self.content_list_flat_sorted_by_layer.items():
            start = time.time()
            # Don't dataprep port layers, label layers, or any layers in the ignore/bypass list
            if (layer[1] != 'port' and layer[1] != 'label' and layer[1] != 'sim') and (
                    layer not in self.dataprep_ignore_list and layer not in self.dataprep_bypass_list):

                self.flat_gdspy_polygonsets_by_layer[layer] = self.dataprep_coord_to_gdspy(
                    self.get_polygon_point_lists_on_layer(layer),
                    manh_grid_size=self.get_manhattanization_size_on_layer(layer),
                    do_manh=self.GLOBAL_DO_MANH_AT_BEGINNING,  # TODO: Remove this argument?
                )
                end = time.time()
                logging.info(f'Converting {layer} content to gdspy took: {end - start}s')
            else:
                logging.info(f'{layer} was excluded from dataprep')
        end0 = time.time()
        logging.info(f'All pointlist to gdspy conversions took total of {end0 - start0}s')

        # 3) Perform each dataprep operation in the list on the provided layers in order
        start0 = time.time()
        logging.info(f'-------- Performing Dataprep Procedure --------')
        # self.dataprep_group has lpp_in as list of regex
        for dataprep_group in self.dataprep_groups:
            # 3a) Iteratively perform operations on all layers in lpp_in
            for lpp_in_regex in dataprep_group['lpp_in']:
                # Loop over all lpps that match the lpp_in regex
                lpp_in_list = self.regex_search_lpps(lpp_in_regex, self.flat_gdspy_polygonsets_by_layer.keys())
                for lpp_in in lpp_in_list:

                    shapes_in = self.flat_gdspy_polygonsets_by_layer.get(lpp_in, None)

                    # 3b) Iteratively perform each operation on the current lpp_in
                    for lpp_op in dataprep_group['lpp_ops']:
                        start = time.time()

                        operation = lpp_op['operation']
                        amount = lpp_op['amount']
                        if (amount is None) and (operation == 'manh'):
                            amount = self.get_manhattanization_size_on_layer(lpp_in)
                            logging.info(f'manh size amount not specified in operation. Setting to {amount}')

                        out_layer = lpp_op['lpp']
                        if (out_layer is None) and (operation == 'manh'):
                            out_layer = lpp_in
                            logging.info(f'manh output layer not specified in operation. Setting to {out_layer}')

                        logging.info(f'Performing dataprep operation: {operation}  on layer: {lpp_in}  '
                                     f'to layer: {out_layer}  with size {amount}')

                        # 3c) Maps the operation in the spec file to the desired gdspy implementation and performs it
                        new_out_layer_polygons = self.poly_operation(
                            lpp_in=lpp_in,
                            lpp_out=out_layer,
                            polygon1=self.flat_gdspy_polygonsets_by_layer.get(out_layer, None),
                            polygon2=shapes_in,
                            operation=operation,
                            size_amount=amount,
                            do_manh_in_rad=(False if self.is_lsf else self.GLOBAL_DO_MANH_DURING_OP),
                        )

                        # Update the layer's content.
                        # Do not add new layer if no shapes are on it.
                        if new_out_layer_polygons is not None:
                            self.flat_gdspy_polygonsets_by_layer[out_layer] = new_out_layer_polygons
                        elif ((new_out_layer_polygons is None) and
                              (out_layer in self.flat_gdspy_polygonsets_by_layer.keys())):
                            logging.debug(f'Dataprep operation {operation} on layer {out_layer} from layer {lpp_in} '
                                          f'resulted in no shapes on the output layer (an empty layer). '
                                          f'Popping the output layer from flat_gdspy_polygonsets_by_layer')
                            self.flat_gdspy_polygonsets_by_layer.pop(out_layer, None)

                        end = time.time()
                        logging.info(f'{operation} on {lpp_in} to {out_layer} by {amount} took: {end-start}s')

        end0 = time.time()
        logging.info(f'All dataprep layer operations took {end0 - start0}s')

        # 4) Perform a final over_under_under_over operation
        start0 = time.time()
        logging.info(f'-------- Performing OUUO Procedure --------')
        for lpp_regex in self.ouuo_regex_list:
            lpp_list = self.regex_search_lpps(lpp_regex, self.flat_gdspy_polygonsets_by_layer.keys())
            for lpp in lpp_list:
                logging.info(f'Performing OUUO on {lpp}')
                start = time.time()

                new_out_layer_polygons = self.poly_operation(
                    lpp_in=lpp,
                    lpp_out=lpp,
                    polygon1=None,
                    polygon2=self.flat_gdspy_polygonsets_by_layer.get(lpp, None),
                    operation='ouo',
                    size_amount=0,
                    do_manh_in_rad=self.GLOBAL_DO_MANH_AT_BEGINNING,
                )

                if new_out_layer_polygons is not None:
                    self.flat_gdspy_polygonsets_by_layer[lpp] = new_out_layer_polygons
                elif ((new_out_layer_polygons is None) and
                      (lpp in self.flat_gdspy_polygonsets_by_layer.keys())):
                    logging.debug(f'OUUO on layer {lpp} '
                                  f'resulted in no shapes on the output layer (an empty layer). '
                                  f'Popping the output layer from flat_gdspy_polygonsets_by_layer')
                    self.flat_gdspy_polygonsets_by_layer.pop(lpp, None)

                end = time.time()
                logging.info(f'OUUO on {lpp} took: {end - start}s')

        end0 = time.time()
        logging.info(f'All OUUO operations took a total of : {end0 - start0}s')

        # 5) Take the dataprepped gdspy shapes and import them into a new post-dataprep content list
        start0 = time.time()
        logging.info(f'-------- Converting gdspy shapes to content list --------')
        # TODO: Replace the below code by having polyop_gdspy_to_point_list directly draw the gds... ?
        # TODO: IE, implement direct GDS export from dataprep to avoid going back to contentlist land
        for layer, gdspy_polygons in self.flat_gdspy_polygonsets_by_layer.items():
            start = time.time()
            # Convert gdspy polygonset to list of pointlists
            output_shapes = self.polyop_gdspy_to_point_list(gdspy_polygons,
                                                            fracture=True,
                                                            do_manh=self.GLOBAL_DO_FINAL_MANH,
                                                            manh_grid_size=self.grid.resolution,
                                                            )
            new_shapes = []
            for shape in output_shapes:
                shape = tuple(map(tuple, shape))
                new_shapes.append([coord for coord in shape])
            # Assign pointlists to a per-layer dictionary
            self.post_dataprep_polygon_pointlist_by_layer[layer] = new_shapes

            end = time.time()
            logging.info(f'Converting {layer} from gdspy to point list took: {end - start}s')

        # Convert per-layer pointlist dictionary into content list format
        self.content_list_flat_post_dataprep = self.polygon_list_by_layer_to_flat_content_list(
            poly_list_by_layer=self.post_dataprep_polygon_pointlist_by_layer,
            sim_list=self.content_list_flat.sim_list,
            source_list=self.content_list_flat.source_list,
            monitor_list=self.content_list_flat.monitor_list,
            impl_cell=self.impl_cell
        )

        # 6) Add shapes on layers from the bypass list back in
        # TODO: Properly support batch dataprep, i.e. cases where there are mulitple gds cells
        logging.info(f'-------- Adding bypass layer objects back into the content list --------')
        # dataprep_bypass_list is the post-regex-search list of lpps
        for layer in self.dataprep_bypass_list:
            logging.info(f'Adding bypass layer {layer} back into post-dataprep content list')
            self.content_list_flat_post_dataprep.extend_content_list(self.get_content_on_layer(layer))

        end0 = time.time()
        logging.info(f'Converting all layers from gdspy to point list took a total of: {end0 - start0}s')

        return self.content_list_flat_post_dataprep
