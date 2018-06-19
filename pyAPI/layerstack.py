"""
layerstack.py
Created by Pavan Bhargava 05/07/2018
Contains a class that receives process technology information and enables easy access to it for other functions
"""

import yaml


class techInfo:
    def __init__(self, spec_path):
        self.spec_path = spec_path
        with open(spec_path, 'r') as stream:
            self._tech_info = yaml.load(stream)
        self.layers = self._tech_info.keys()

    def __getitem__(self, layer_name):
        """
        Method returning a dictionary containing material type and thicknesses from tech info

        Parameters:
        ----------
        layername : str
            string representing the technology layer name

        Returns:
        -------
        layerinfo : dict
            dictionary containing material and z span information
        """
        if layer_name not in self._tech_info.keys():
            raise ValueError('Provided layer {} is not part of this technology'.format(layer_name))

        return self._tech_info[layer_name]


if __name__ == '__main__':
    spec_path = '/users/pvnbhargava/lumerical/tech/layerstack.yaml'
    test = techInfo(spec_path)
    print(test['box'])
