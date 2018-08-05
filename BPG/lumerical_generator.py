"""
Module containing various classes used to systematically generate clean Lumerical script code
"""


class LumericalCodeGenerator:
    def __init__(self, filepath):
        """
        This class enables the creation of lumerical .lsf files
        """
        self.filepath = filepath
        self._code = []

    @property
    def code(self):
        return self._code

    def add_code(self, code) -> None:
        """
        Adds provided code to the running list of code to be written. Adds a semicolon and a new
        line character to each line to match standard LSF syntax

        Parameters
        ----------
        code : List[str]
            List of strings containing lumerical script
        """
        self.code.append(code + ';\n')

    def set(self, key, value) -> None:
        """
        Conveniently adds a set statement to the LSF file

        Parameters
        ----------
        key : str
            parameter to be changed with the set statement
        value : any
            value that the parameter will be assigned
        """
        if isinstance(value, str):
            self.add_code('set("{}", "{}")'.format(key, value))
        else:
            self.add_code('set("{}", {})'.format(key, value))

    def export_to_lsf(self):
        """ Take all code in the database and export it to a lumerical script file """
        file = list('# Created by the {} Python Class\n'.format(self.__class__.__name__))
        file += self.code

        with open(self.filepath + '.lsf', 'w') as stream:
            stream.writelines(file)


class LumericalDesignGenerator:
    def __init__(self, filepath):
        """
        This class enables the creation of lumerical .lsf files
        """
        self.filepath = filepath
        self._db = []

    def add_code(self, code) -> None:
        """
        Adds provided code to running list to be written to the final lsf file

        Parameters
        ----------
        code : List[str]
            List of strings containing lumerical script
        """
        self._db += code

    def export_to_lsf(self):
        """ Take all code in the database and export it to a lumerical script file """
        file = list('# Created by the {} Python Class\n'.format(self.__class__.__name__))
        file += self._db

        with open(self.filepath + '.lsf', 'w') as stream:
            stream.writelines(file)


class LumericalSweepGenerator:
    def __init__(self, filepath):
        """
        This class enables the creation of lumerical .lsf files
        """
        self.filepath = filepath
        self._db = []
        self._script_list = []

    def add_sweep_point(self, script_name):
        """
        Adds a given script name to the be run in the main sweep loop. Scripts are executed in the
        order in which they are added

        Parameters
        ----------
        script_name : str
            Name of script to be executed
        """
        self._script_list += script_name

    def add_code(self, code) -> None:
        """
        Adds provided code to running list to be written to the final lsf file

        Parameters
        ----------
        code : List[str]
            List of strings containing lumerical script
        """
        self._db += code

    def export_to_lsf(self):
        """ Take all code in the database and export it to a lumerical script file """
        # Create file header
        file = list('# Created by the {} Python Class\n'.format(self.__class__.__name__))
        file.append('clear; redrawoff;\n')

        # Create the list of layout scripts to be run
        sweep_len = len(self._script_list)
        file.append('sweep_len={};\n'.format(sweep_len))
        file.append('script_list=cell({});\n'.format(sweep_len))
        for count, name in enumerate(self._script_list):
            file.append('script_list{}="{}";\n'.format(count + 1, name))

        # Run a loop over all of the layout scripts
        file.append('for(i=1:sweep_len){\n')
        file.append('addanalysisgroup;\n')
        file.append('set("name", script_list{i});\n')
        file.append('groupscope(script_list{i});\n')
        file.append('\tfeval(script_list{i});\n')
        file.append('switchtolayout;\n')
        file.append('groupscope(script_list{i});\n')
        file.append('delete;')
        file.append('groupscope("::model");\n')
        file.append('}\n')

        # Add the rest of the stored code to the file
        file += self._db

        with open(self.filepath, 'w') as stream:
            stream.writelines(file)
