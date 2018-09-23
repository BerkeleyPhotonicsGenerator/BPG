from .lumerical_generator import LumericalCodeGenerator


class LumericalMaterialGenerator(LumericalCodeGenerator):
    """ This class enables BPG to create a custom set of materials for use in Lumerical """
    def __init__(self, filepath):
        LumericalCodeGenerator.__init__(self)
        self.filepath = filepath

    def add_material(self, name) -> None:
        """
        Each time this is called a new material with the provided name is created

        Parameters
        ----------
        name : str
            name of the new material being created
        """
        self.add_code(f'matname = {name}')
        self.add_code('newmaterial = addmaterial("Lorentz")')  # TODO: What is Lorentz, do we need other options here?
        self.add_code(f'setmaterial(newmaterial, "name", matname)')

    def add_property(self, prop_name, prop_value) -> None:
        """
        Each time this method is called, an lsf line setting the property value to the property name is added

        Parameters
        ----------
        prop_name : str
            name of the property to be set
        prop_value : Any
            value of the property to be set
        """
        if isinstance(prop_value, str):
            self.add_code(f'setmaterial(matname,"{prop_name}","{prop_value}")')
        else:
            self.add_code(f'setmaterial(matname,"{prop_name}",{prop_value})')

    def import_material_from_dict(self, material_name: str, prop_dict: dict) -> None:
        """
        Creates and configures a new material given the properties inside the dictionary.

        Parameters
        ----------
        material_name : str
            the name of the new material to be created
        prop_dict : dict
            dict containing all the property info necessary to define the material
        """
        self.add_material(material_name)
        for key, value in prop_dict.items():
            self.add_property(key, value)

    def import_material_file(self, material_dict) -> None:
        """
        Takes a dictionary containing other dictionaries and creates an lsf file that defines all of the materials and
        their properties. Each key in the top level dict is the name of the material, and each value is a dictionary
        containing the material properties.

        Parameters
        ----------
        material_dict : dict
            dict of dicts specifying the materials to be created
        """
        for key, value in material_dict.items():
            self.import_material_from_dict(material_name=key, prop_dict=value)

    def export_to_lsf(self):
        file = self.get_file_header()
        file += self._code
        with open(self.filepath, 'w+') as stream:
            stream.writelines(file)
