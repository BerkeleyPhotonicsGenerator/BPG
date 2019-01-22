import numpy as np

from typing import Union


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

    coord_set_next = np.roll(coords_list_in, -1, axis=0)
    coord_set_prev = np.roll(coords_list_in, 1, axis=0)

    vec_to_next = coord_set_next - coords_list_in
    vec_from_prev = coords_list_in - coord_set_prev

    dx_next = vec_to_next[:, 0]
    dy_next = vec_to_next[:, 1]
    dx_prev = vec_from_prev[:, 0]
    dy_prev = vec_from_prev[:, 1]

    dx_next_abs = np.abs(dx_next)
    dy_next_abs = np.abs(dy_next)
    dx_prev_abs = np.abs(dx_prev)
    dy_prev_abs = np.abs(dy_prev)

    same_as_next = np.logical_and(dx_next_abs < eps_grid, dy_next_abs < eps_grid)

    if check_inline:
        same_as_prev = np.logical_and(dx_prev_abs < eps_grid, dy_prev_abs < eps_grid)
        diff_from_lr = np.logical_not(np.logical_or(same_as_next, same_as_prev))

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
        in_line = np.logical_or(np.logical_and(dx_next_abs < eps_grid, dx_prev_abs < eps_grid),
                                np.logical_and(dy_next_abs < eps_grid, dy_prev_abs < eps_grid))

        in_line_and_diff_from_lr = np.logical_and(in_line, diff_from_lr)
    else:
        # If not checking for inline points, default all values of inline check to false
        in_line_and_diff_from_lr = np.full_like(same_as_next, False)

    # situation 1: the point is the same with its left neighbor
    # situation 2: the point is not the same with its neighbors, but it is in a line with them
    delete_array = np.logical_or(same_as_next, in_line_and_diff_from_lr)

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
    tangent_normalized_vec = \
        tangent_vec / np.tile(np.linalg.norm(tangent_vec, axis=1, keepdims=True), (1, 2)) * width/2

    # Find the points using the perpendicular to tangent line
    pts0 = points_list + np.column_stack([-1 * tangent_normalized_vec[:, 1], tangent_normalized_vec[:, 0]])
    pts1 = points_list + np.column_stack([tangent_normalized_vec[:, 1], -1 * tangent_normalized_vec[:, 0]])

    # Concatenate into a polygon
    points_out = np.concatenate((pts0, np.flipud(pts1)), axis=0)

    # Clean up the polygon
    polygon_points = coords_cleanup(points_out, eps_grid=eps, cyclic_points=True)

    return polygon_points
