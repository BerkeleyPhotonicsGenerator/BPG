# LumericalProject.py
import os
from pathlib import Path
from .shapes import Rectangle
from .layerstack import techInfo
from .paths import LumericalPath


class LumericalProject:
    def __init__(self, project_name):
        """
        This class organizes the creation of all lumerical files, technology information, and directories
        """
        self.project_name = project_name
        self.paths = LumericalPath()
        self.root = self.paths.root
        self.scripts = self.paths.scripts
        self.data = self.paths.data
        self.techfile = self.paths.techfile
        self.techInfo = techInfo(self.techfile)  # Extract technology information for easy use

        # This is the directory where all generated scripts will be placed
        self.proj_dir = Path(self.scripts) / self.project_name

        if not os.path.exists(self.proj_dir):
            os.makedirs(self.proj_dir)

        #self._db = []  # database containing all created shapes
        #self.lsf_gen = LumericalGenerator()

        # Check if the project already exists
        # If it exists and the operation is to create a new project, throw error
        # If it exists and the operation is to open the project, import all the file data
        # If it does not exist and the operation is the create a new project, create a blank directory
        # If it does not exist and the operation is to read, throw error


class LumericalGenerator:
    def __init__(self,
                 project,  # type: LumericalProject
                 name  # type: str
                 ):
        """
        This class enables the creation of lumerical .lsf files
        """
        self.prj = project
        self.path = self.prj.proj_dir  # directory where this script will be stored
        self.name = name  # name of the file to be created
        self._db = []

    def add_rect(self, name, layer) -> Rectangle:
        """
        Creates a new rectangle shape, adds it to the database and returns it for further modification
        """
        material_info = self.prj.techInfo[layer]
        temp = Rectangle(name, material_info)
        self._db.append(temp)
        return temp

    def export_to_lsf(self):
        """
        Take all shapes in the database and export them to lumerical script
        """
        file = ['# Created by the {} lumerical generator\n'.format(self.__class__.__name__)]
        file.append('clear; newmode; redrawoff;\n')
        for shape in self._db:
            file += shape.export()
            file += '\n'

        filename = Path(self.path) / self.name
        with open(filename, 'w') as stream:
            stream.writelines(file)


if __name__ == '__main__':
    prj = LumericalProject('Single_Mode_Waveguide')
    test_file = LumericalGenerator(prj, 'testfile.lsf')
    rect1 = test_file.add_rect('test_rect', 'rx')
    rect1.set_center_span('x', 0, .5)
    rect1.set_center_span('y', 0, 4)
    test_file.export_to_lsf()
