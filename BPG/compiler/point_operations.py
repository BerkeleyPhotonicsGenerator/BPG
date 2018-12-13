import numpy as np
import math

from typing import Tuple, Union


def cleanup_delete(coords_list_in: np.ndarray,
                   eps_grid: float = 1e-4,
                   ) -> np.ndarray:
    """
    From the passed coordinate list, returns a numpy array of bools of the same length where each value indicates
    whether that point should be deleted from the coord_list

    Parameters
    ----------
    coords_list_in : np.ndarray
        The list of x-y coordinates composing a polygon shape
    eps_grid :
        grid resolution below which points are considered to be the same

    Returns
    -------
    delete_array : np.ndarray
        Numpy array of bools telling whether to delete the coordinate or not
    """

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

    """
    if x&y coords are accurate, we should have dy2_acc/dx2_acc = dy1_acc/dx1_acc
    equivalent to    dx1_acc * dy2_acc =dx2_acc * dy1_acc,
    because of inaccuracy in float numbers, we have
    |dx1 * dy2 - dx2 * dy1| = |(dx1_acc + err1) * (dy2_acc + err2) - (dx2_acc + err3) * (dy1_acc + err4)|
                           ~ |dx1 * err2 + dy2 * err1 - dx2 * err4 - dy1 * err3|
                           < sum(|dx1|, |dx2|, |dy1|, |dy2|) * |err_max|

    # error_abs = np.abs(dx_l * dy_r - dx_r * dy_l)
    # in_line = error_abs  < eps_grid * (dx_l_abs + dy_l_abs + dx_r_abs + dy_r_abs)
    """
    in_line = np.logical_or(np.logical_and(dx_l_abs < eps_grid, dx_r_abs < eps_grid),
                            np.logical_and(dy_l_abs < eps_grid, dy_r_abs < eps_grid))

    # situation 1: the point is the same with its left neighbor
    # situation 2: the point is not the same with its neighbors, but it is in a line with them
    delete_array = np.logical_or(same_with_left, np.logical_and(in_line, diff_from_lr))

    return delete_array


def coords_cleanup(coords_list: np.ndarray,
                   eps_grid: float = 1e-4,
                   ) -> np.ndarray:
    """
    clean up coordinates in the list that are redundant or harmful for following geometry manipulation functions

    Parameters
    ----------
    coords_list : np.ndarray
        list of coordinates that enclose a polygon
    eps_grid : float
        a size smaller than the resolution grid size,
        if the difference of x/y coordinates of two points is smaller than it,
        these two points should actually share the same x/y coordinate

    Returns
    ----------
    coords_set_out : np.ndarray
        The cleaned coordinate set
    """
    delete_array = cleanup_delete(coords_list, eps_grid=eps_grid)
    not_cleaned = np.sum(delete_array) > 0

    # in some cases, some coordinates become on the line if the following coord is deleted,
    # need to loop until no coord is deleted during one loop
    while not_cleaned:
        select_array = np.logical_not(delete_array)
        coords_list = coords_list[select_array]
        delete_array = cleanup_delete(coords_list, eps_grid=eps_grid)
        not_cleaned = np.sum(delete_array) > 0

    return coords_list


# TODO: Implement parallelized version via numpy
def radius_of_curvature(pt0,  # type: Tuple[int, int]
                        pt1,  # type: Tuple[int, int]
                        pt2,  # type: Tuple[int, int]
                        eps,  # type: float
                        ) -> float:

    ma = -(pt1[0] - pt0[0]) / (pt1[1] - pt0[1]) if abs(pt1[1] - pt0[1]) > eps else 'v'
    mb = -(pt2[0] - pt1[0]) / (pt2[1] - pt1[1]) if abs(pt2[1] - pt1[1]) > eps else 'v'

    xa, ya = (pt0[0] + pt1[0]) / 2, (pt0[1] + pt1[1]) / 2
    xb, yb = (pt1[0] + pt2[0]) / 2, (pt1[1] + pt2[1]) / 2

    # First two points form a horizontal line
    if ma == 'v':
        center = (xa, mb * (xa - xb) + yb)
    # Second two points form a horizontal line
    elif mb == 'v':
        center = (xb, ma * (xb - xa) + ya)
    else:
        center = ((mb * xb - ma * xa - (yb - ya)) / (mb - ma), (ma * mb * (xb - xa) - (ma * yb - mb * ya)) / (mb - ma))

    point = center[0] - pt1[0], center[1] - pt1[1]
    radius = math.sqrt(math.pow(point[0], 2) + math.pow(point[1], 2))

    return radius


# TODO: implement parallelized version via numpy
def create_polygon_from_path_and_width(pts: np.ndarray,
                                       width: Union[float, int],
                                       ) -> np.ndarray:
    pass
