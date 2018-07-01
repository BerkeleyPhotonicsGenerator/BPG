# lumerical_generator.py


class LumericalGenerator:
    def __init__(self):
        """
        This class enables the creation of lumerical .lsf files
        """
        self._db = []

    def add_code(self, code) -> None:
        """
        Adds provided code to running list to be written to the final lsf file

        Parameters
        ----------
        code : List[str]
            List of strings containing lumerical script
        """
        # TODO: Make this a generator statement to speed up compute time for large codebases
        self._db += code

    def export_to_lsf(self, filepath):
        """ Take all code in the database and export it to a lumerical script file """
        file = list('# Created by the {} lumerical generator\n'.format(self.__class__.__name__))
        file.append('clear; newmode; redrawoff;\n')
        file += self._db

        with open(filepath, 'w') as stream:
            stream.writelines(file)
