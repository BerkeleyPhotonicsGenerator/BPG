from BPG.photonic_core import PhotonicTechInfo
from typing import Union, Tuple

'''
Sample PhotonicTechInfo implementation file
'''


class PhotonicTechInfoExample(PhotonicTechInfo):
    def __init__(self, photonic_tech_params, resolution, layout_unit):
        PhotonicTechInfo.__init__(self, photonic_tech_params, resolution, layout_unit)

    def min_width_unit(self,
                       layer,  # type: Union[str, Tuple[str, str]]
                       ):
        # type: (...) -> int
        """
        Returns the minimum width (in resolution units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_width_unit : float
            The minimum width in resolution units for shapes on the layer
        """
        # If a tuple, look only at the layer of the LPP
        if isinstance(layer, tuple):
            layer = layer[0]

        layer_values = self.dataprep_parameters['MinWidth']
        if layer not in layer_values:
            raise ValueError('Layer {layer} not present in parameters for MinWidth'.format(layer=layer))

        return int(round(layer_values[layer] / self._resolution))

    def min_width(self,
                  layer,  # type: Union[str, Tuple[str, str]]
                  ):
        # type: (...) -> float
        """
        Returns the minimum width (in layout units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_width : float
            The minimum width for shapes on the layer
        """

        return self.min_width_unit(layer) * self._resolution

    def min_space_unit(self,
                       layer,  # type: Union[str, Tuple[str, str]]
                       ):
        # type: (...) -> int
        """
        Returns the minimum space (in resolution units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_space_unit : float
            The minimum space in resolution units for shapes on the layer
        """
        # If a tuple, look only at the layer of the LPP
        if isinstance(layer, tuple):
            layer = layer[0]

        layer_values = self.dataprep_parameters['MinSpace']
        if layer not in layer_values:
            raise ValueError('Layer {layer} not present in parameters for MinSpace'.format(layer=layer))

        return int(round(layer_values[layer] / self._resolution))

    def min_space(self,
                  layer,  # type: Union[str, Tuple[str, str]]
                  ):
        # type: (...) -> float
        """
        Returns the minimum space (in layout units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_space : float
            The minimum space for shapes on the layer
        """

        return self.min_space_unit(layer) * self._resolution

    def max_width_unit(self,
                       layer,  # type: Union[str, Tuple[str, str]]
                       ):
        # type: (...) -> int
        """
        Returns the maximum width (in resolution units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        max_width_unit : float
            The maximum width in resolution units for shapes on the layer
        """
        # If a tuple, look only at the layer of the LPP
        if isinstance(layer, tuple):
            layer = layer[0]

        layer_values = self.dataprep_parameters['MaxWidth']
        if layer not in layer_values:
            raise ValueError('Layer {layer} not present in parameters for MaxWidth'.format(layer=layer))

        return int(round(layer_values[layer] / self._resolution))

    def max_width(self,
                  layer,  # type: Union[str, Tuple[str, str]]
                  ):
        # type: (...) -> float
        """
        Returns the maximum width (in layout units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        max_width : float
            The maximum width for shapes on the layer
        """

        return self.max_width_unit(layer) * self._resolution

    def min_area_unit(self,
                      layer,  # type: Union[str, Tuple[str, str]]
                      ):
        # type: (...) -> int
        """
        Returns the minimum area (in resolution units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_area_unit : float
            The minimum area in resolution units for shapes on the layer
        """
        # If a tuple, look only at the layer of the LPP
        if isinstance(layer, tuple):
            layer = layer[0]

        layer_values = self.dataprep_parameters['MinArea']
        if layer not in layer_values:
            raise ValueError('Layer {layer} not present in parameters for MinArea'.format(layer=layer))

        return int(round(layer_values[layer] / (self._resolution * self._resolution)))

    def min_area(self,
                 layer,  # type: Union[str, Tuple[str, str]]
                 ):
        # type: (...) -> float
        """
        Returns the minimum area (in layout units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_area : float
            The minimum area for shapes on the layer
        """

        return self.min_area_unit(layer) * self._resolution * self._resolution

    def min_edge_length_unit(self,
                             layer: Union[str, Tuple[str, str]],
                             ):
        # type: (...) -> int
        """
        Returns the minimum edge length (in resolution units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_edge_length : float
            The minimum edge length in resolution units for shapes on the layer
        """
        # If a tuple, look only at the layer of the LPP
        if isinstance(layer, tuple):
            layer = layer[0]

        layer_values = self.dataprep_parameters['MinEdgeLength']
        if layer not in layer_values:
            raise ValueError(f'Layer {layer} not present in parameters for MinEdgeLength')

        return int(round(layer_values[layer] / self._resolution))

    def min_edge_length(self,
                        layer: Union[str, Tuple[str, str]],
                        ):
        # type: (...) -> float
        """
        Returns the minimum edge length (in layout units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_edge_length : float
            The minimum edge length for shapes on the layer
        """

        return self.min_edge_length_unit(layer) * self._resolution

    def height_unit(self,
                    layer,  # type: Union[str, Tuple[str, str]]
                    ):
        # type: (...) -> int
        """
        Returns the height from the top of the silicon region (defined as 0) to the bottom surface of the given
        layer, in resolution units.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        height_unit : float
            The height of the bottom surface in resolution units for shapes on the layer
        """
        # If a tuple, look only at the layer of the LPP
        if isinstance(layer, tuple):
            layer = layer[0]

        layer_values = self.dataprep_parameters['Height']
        if layer not in layer_values:
            raise ValueError('Layer {layer} not present in parameters for Height'.format(layer=layer))

        return int(round(layer_values[layer] / self._resolution))

    def height(self,
               layer,  # type: Union[str, Tuple[str, str]]
               ):
        # type: (...) -> float
        """
        Returns the height from the top of the silicon region (defined as 0) to the bottom surface of the given
        layer, in layout units.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        height : float
            The height of the bottom surface for shapes on the layer
        """

        return self.height_unit(layer) * self._resolution

    def thickness_unit(self,
                       layer,  # type: Union[str, Tuple[str, str]]
                       ):
        # type: (...) -> int
        """
        Returns the thickness of the layer, in resolution units

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        thickness_unit : float
            The thickness in resolution units for shapes on the layer
        """
        # If a tuple, look only at the layer of the LPP
        if isinstance(layer, tuple):
            layer = layer[0]

        layer_values = self.dataprep_parameters['Thickness']
        if layer not in layer_values:
            raise ValueError('Layer {layer} not present in parameters for Thickness'.format(layer=layer))

        return int(round(layer_values[layer] / self._resolution))

    def thickness(self,
                  layer,  # type: Union[str, Tuple[str, str]]
                  ):
        # type: (...) -> float
        """
        Returns the thickness of the layer, in layout units.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        thickness : float
            The thickness of shapes on the layer
        """

        return self.thickness_unit(layer) * self._resolution

    def sheet_resistance(self,
                         layer  # type: Union[str, Tuple[str, str]]
                         ):
        # type: (...) -> float
        """
        Returns the sheet resistance of the layer, in Ohm/sq.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        rs : float
            The sheet resistance of the layer in Ohm/sq
        """
        # If a tuple, look only at the layer of the LPP
        if isinstance(layer, tuple):
            layer = layer[0]

        rs_values = self.dataprep_parameters['Rs']
        if layer not in rs_values:
            raise ValueError('Layer {layer} not present in parameters for sheet resistance (Rs)'.format(layer=layer))

        return rs_values[layer]

    def via_max_width(self,
                      layer: Union[str, Tuple[str, str]],
                      ) -> float:
        if isinstance(layer, tuple):
            layer = layer[0]

        width_values = self.dataprep_parameters['MaxWidth']
        if layer not in width_values:
            raise ValueError(f'Layer {layer} not present in parameters for via_max_width.  In dummy technology, '
                             f'via_max_width = MaxWidth')

        return width_values[layer]
