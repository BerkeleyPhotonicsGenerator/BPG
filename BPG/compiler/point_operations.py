import numpy as np
import math

from typing import Tuple, Union


def cleanup_delete(coords_list_in: np.ndarray,
                   eps_grid: float = 1e-4,
                   cyclic_points: bool = True,
                   check_inline: bool = True,
                   ) -> np.ndarray:
    """
    From the passed coordinate list, returns a numpy array of bools of the same length where each value indicates
    whether that point should be deleted from the coord_list.

    Points that should be removed are either adjacent points that are the same, or points that are in a line.

    Parameters
    ----------
    coords_list_in : np.ndarray
        The list of x-y coordinates composing a polygon shape
    eps_grid :
        grid resolution below which points are considered to be the same
    cyclic_points : bool
        True if the coords_list forms a closed polygon. If True, the start/end points might be removed.
        False if the coords_list is not a closed polygon (ie, a path). If False, the start and end points will never be
        removed.
    check_inline : bool
        True [default] to check for and remove center points that are in a line with their two adjacent neighbors.
        False to skip this check

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

    if check_inline:
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

        in_line_and_diff_from_lr = np.logical_and(in_line, diff_from_lr)
    else:
        # If not checking for inline points, default all values of inline check to false
        in_line_and_diff_from_lr = np.full_like(same_with_left, False)

    # situation 1: the point is the same with its left neighbor
    # situation 2: the point is not the same with its neighbors, but it is in a line with them
    delete_array = np.logical_or(same_with_left, in_line_and_diff_from_lr)

    # If cleaning a path rather than a polygon, never delete the first or last point
    if not cyclic_points:
        delete_array[0] = False
        delete_array[-1] = False

    return delete_array


def coords_cleanup(coords_list: np.ndarray,
                   eps_grid: float = 1e-4,
                   cyclic_points: bool = True,
                   check_inline: bool = True,
                   ) -> np.ndarray:
    """
    clean up coordinates in the list that are redundant or harmful for following geometry manipulation functions

    Points that are cleaned are:
        - Adjacent coincident points
        - Collinear points (middle points removed)

    Parameters
    ----------
    coords_list : np.ndarray
        list of coordinates that enclose a polygon
    eps_grid : float
        a size smaller than the resolution grid size,
        if the difference of x/y coordinates of two points is smaller than it,
        these two points should actually share the same x/y coordinate
    cyclic_points : bool
        True [default] if the coords_list forms a closed polygon. If True, the start/end points might be removed.
        False if the coords_list is not a closed polygon (ie, a path). If False, the start and end points will never be
        removed.
    check_inline : bool
        True [default] to check for and remove center points that are in a line with their two adjacent neighbors.
        False to skip this check

    Returns
    ----------
    coords_set_out : np.ndarray
        The cleaned coordinate set
    """
    delete_array = cleanup_delete(coords_list, eps_grid=eps_grid,
                                  cyclic_points=cyclic_points, check_inline=check_inline)
    not_cleaned = np.sum(delete_array) > 0

    # in some cases, some coordinates become on the line if the following coord is deleted,
    # need to loop until no coord is deleted during one loop
    while not_cleaned:
        select_array = np.logical_not(delete_array)
        coords_list = coords_list[select_array]
        delete_array = cleanup_delete(coords_list, eps_grid=eps_grid,
                                      cyclic_points=cyclic_points, check_inline=check_inline)
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


def create_polygon_from_path_and_width(points_list: np.ndarray,
                                       width: Union[float, int],
                                       eps: float = 1e-4
                                       ) -> np.ndarray:
    """
    Given a path (a numpy array of 2-D points) and a width (constant along the path), return the set of points forming
    the polygon.

    Checks to see if the radius of curvature is smaller than half the width. If so, the polygon will be self
    intersecting, so raise an error.

    Does not perform any rounding/snapping of points to a grid.

    Parameters
    ----------
    points_list : np.ndarray
        A numpy array of points (n x 2) representing the center of the path.
    width : Union[float, int]
        The width of the path
    eps : float
        The tolerance for determining whether two points are coincident.

    Returns
    -------
    polygon_points : np.ndarray
        The polygon formed by the center path and width.

    """

    tangent_vec = np.gradient(points_list, axis=0)
    tangent_normalized_vec = tangent_vec / np.tile(np.linalg.norm(tangent_vec, axis=1, keepdims=True), (1, 2))

    perpendicular_vec = np.gradient(tangent_normalized_vec, axis=0)
    perpendicular_normalized_vec = perpendicular_vec / np.tile(np.linalg.norm(perpendicular_vec, axis=1, keepdims=True), (1, 2))

    invalid_perp = np.isnan(perpendicular_normalized_vec)


    second_deriv = np.gradient(tangent_vec, axis=0)
    curvature_radius = np.abs(
        second_deriv[:, 0] * tangent_vec[:, 1] - tangent_vec[:, 0] * second_deriv[:, 1]
    ) / np.power(
        np.power(tangent_vec[:, 0], 2) + np.power(tangent_vec[:, 1], 2),
        1.5
    )

    # if np.any(curvature_radius < width / 2):
    #     raise ValueError(f'Radius of curvature too tight')

    # Calculate the cross product to know which side is 'up' vs 'down'
    cross_z = np.cross(tangent_vec, perpendicular_vec)

    # Calculate the polygon points forming the path
    pts0 = points_list + np.tile(np.sign(cross_z), (2, 1)).transpose() * perpendicular_normalized_vec * width / 2
    pts1 = points_list - np.tile(np.sign(cross_z), (2, 1)).transpose() * perpendicular_normalized_vec * width / 2

    # Concatenate into a polygon
    points_out = np.concatenate((pts0, np.flipud(pts1)), axis=0)

    # Clean up the polygon
    polygon_points = coords_cleanup(points_out, eps_grid=eps, cyclic_points=True)
    # asdf
    return polygon_points
