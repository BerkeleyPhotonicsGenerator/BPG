# lumerical_generator.py
import yaml
from pathlib import Path
from .shapes import Rectangle
from .layerstack import techInfo


class LumericalGenerator:
    def __init__(self, specfile):
        """
        This class enables the creation of lumerical .lsf files
        """
        self.specfile_path = specfile
        self.specfile = self.load_yaml(specfile)

        # Setup relevant files and directories
        self.project_dir = Path(self.specfile['project_dir']).expanduser()
        self.scripts_dir = self.project_dir/self.specfile['scripts']
        self.data_dir = self.project_dir/self.specfile['data']

        # Make the directories if they do not exists
        self.project_dir.mkdir(exist_ok=True)
        self.scripts_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True)

        # Note: techfile is not in a subdirectory of project_dir
        self.techfile = Path(self.specfile['techfile']).expanduser()

        # Store technology information in an object for easy access
        self.techInfo = techInfo(self.techfile)

        self.lsf_filename = self.specfile['lsf_filename']
        self._db = []

    def add_rect(self, name, layer) -> Rectangle:
        """
        Creates a new rectangle shape, adds it to the database and returns it for further modification
        """
        material_info = self.techInfo[layer]
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

        filename = self.scripts_dir / self.lsf_filename
        with open(filename, 'w') as stream:
            stream.writelines(file)

    @staticmethod
    def load_yaml(filepath):
        """ Setup standardized method for yaml loading """
        with open(filepath, 'r') as stream:
            temp = yaml.safe_load(stream)
        return temp

