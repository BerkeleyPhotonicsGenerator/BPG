# shapely_generator.py


class ShapelyGenerator:
    def __init__(self):
        """
        This class enables the creation of shapely data
        """
        self._boundary_list_p = []
        self._boundary_list_n = []

    def add_shapes(self,
                   positive_shape_list,  # type: list
                   negative_shape_list,  # type: list
                   ):
        # type: (...) -> None

        # TODO: Make this a generator statement to speed up compute time for large codebases
        self._boundary_list_p.extend(positive_shape_list)
        self._boundary_list_n.extend(negative_shape_list)

    def final_shapes_export(self):
        """
        Export a two flat lists of the positive and negative spaces as polygons

        Returns
        -------

        """
        return self._boundary_list_p, self._boundary_list_n
