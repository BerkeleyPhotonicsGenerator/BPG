# shapely_generator.py


class ShapelyGenerator:
    def __init__(self):
        """
        This class enables the creation of shapely data
        """
        self._boundary_list_p = []
        self._boundary_list_n = []

    def add_shapes(self,
                   tuple_of_lists,
                   ):
        # type: (...) -> None
        """
        Adds provided code to running list to be written to the final lsf file

        Parameters
        ----------
        code : List[str]
            List of strings containing lumerical script
        """
        # TODO: Make this a generator statement to speed up compute time for large codebases
        self._boundary_list_p.append(tuple_of_lists[0])
        self._boundary_list_n.append(tuple_of_lists[1])

    def final_shapes_export(self):
        """ Take all code in the database and export it to a lumerical script file """

        return (self._boundary_list_p, self._boundary_list_n)
