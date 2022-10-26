#!/usr/bin/env python3

from typing import List, Any, Tuple
import re
import os
import string
from pathlib import Path
import yaml


class LayerInfo(dict):
    items = ['cad_layer_num', 'cad_purpose_num', 'color', 'stipple_path', 'stipple', 'name', 'layer', 'purpose', ]

    def __init__(self,
                 **kwargs: Any,
                 ) -> None:
        # Check that the kwargs are valid. If not, raise an error
        for key in kwargs:
            if key not in self.items:
                raise ValueError(f'Unknown key: {key}')

        # If key is not specified, content list should have an empty list, not None
        kv_iter = ((key, kwargs.get(key, [])) for key in self.items)
        dict.__init__(self, kv_iter)

    @property
    def cad_layer_num(self):
        return self['cad_layer_num']

    @property
    def cad_purpose_num(self):
        return self['cad_purpose_num']

    @property
    def color(self):
        return self['color']

    @property
    def stipple_path(self):
        return self['stipple_path']

    @property
    def stipple(self):
        return self['stipple']

    @property
    def name(self):
        return self['name']

    @property
    def layer(self):
        return self['layer']

    @property
    def purpose(self):
        return self['purpose']


def parse_gds_map(layer_map: dict):
    layer_info_list = list()
    for cad_lpp, gds_lpp in layer_map.items():
        layer_info_list.append(
            LayerInfo(layer=cad_lpp[0],
                      purpose=cad_lpp[1],
                      cad_layer_num=gds_lpp[0],
                      cad_purpose_num=gds_lpp[1])
        )
    return layer_info_list


def dump_klayout_layerprops(outfile: str,
                            layer_list: List[LayerInfo],
                            stipple_paths: List[Tuple[str, str]],
                            ):
    with open(outfile, 'w') as file:
        file.write(f'<?xml version="1.0" encoding="utf-8"?>\n')
        file.write(f'<layer-properties>\n')
        # Write the layers
        for layer in layer_list:
            file.write(f' <properties>\n')
            # file.write(f'  <frame-color>{layer.color}</frame-color>\n')
            # file.write(f'  <fill-color>{layer.color}</fill-color>\n')
            # file.write(f'  <frame-brightness>0</frame-brightness>\n')
            # file.write(f'  <fill-brightness>0</fill-brightness>\n')
            # file.write(f'  <dither-pattern>C{find_stipple_ind(layer.stipple, stipple_paths)}</dither-pattern>\n')		# Dither-pattern must be the index of the custom stipple
            file.write(f'  <valid>true</valid>\n')
            file.write(f'  <visible>true</visible>\n')
            file.write(f'  <transparent>false</transparent>\n')
            file.write(f'  <width>1</width>\n')
            file.write(f'  <marked>false</marked>\n')
            file.write(f'  <animation>0</animation>\n')
            file.write(f'  <name>{layer.layer}.{layer.purpose} - {layer.cad_layer_num}/{layer.cad_purpose_num}</name>\n')
            file.write(f'  <source>{layer.cad_layer_num}/{layer.cad_purpose_num}@1</source>\n')
            file.write(f' </properties>\n')

        # Write a default display so that all layers will be shown in the layer panel without clicking "Add Other Layer Entries"
        file.write(f' <properties>\n')
        file.write(f'  <source>*/*@*</source>\n')
        file.write(f' </properties>\n')

        # file.write(f' <name/>\n')
        # # Write the stipples
        # for ind, (stipple_path, stipple) in enumerate(stipple_paths):
        #     stipple_lines = parse_stipple_file(stipple_path)
        #
        #     file.write(f' <custom-dither-pattern>\n')
        #     file.write(f'  <pattern>\n')
        #     for line in stipple_lines:
        #         file.write(f'   <line>{line}</line>\n')
        #     file.write(f'  </pattern>\n')
        #     file.write(f'  <order>{ind}</order>\n')
        #     file.write(f'  <name>{stipple}</name>\n')
        #     file.write(f' </custom-dither-pattern>\n')

        file.write(f'</layer-properties>\n')


if __name__ == '__main__':
    src_file = '../gds_map.yaml'

    outfile = '../layerprops.lyp'

    with open(src_file, 'r') as f:
        src_info = yaml.load(f, Loader=yaml.CFullLoader if yaml.__with_libyaml__ else yaml.FullLoader)

    layer_map = src_info['layer_map']
    layer_info = parse_gds_map(layer_map)

    dump_klayout_layerprops(outfile, layer_info, None)
