
import os
import pkg_resources

import yaml

from typing import List, Tuple, Union, Optional, Callable, TYPE_CHECKING

from bag.layout.tech import TechInfoConfig
from bag.layout.util import BBox

# from abs_templates_ec.analog_mos.soi import MOSTechSOIGenericBC
# from abs_templates_ec.resistor.planar import ResTechPlanarGeneric

if TYPE_CHECKING:
    from bag.layout.template import TemplateBase


_yaml_file = pkg_resources.resource_filename(__name__, os.path.join('tech_params.yaml'))

with open(_yaml_file, 'r') as f:
    config = yaml.load(f)


class TechInfoGeneric(TechInfoConfig):
    def __init__(self, tech_params):
        TechInfoConfig.__init__(self, config, tech_params,
                                mos_entry_name='mos_analog')

        # tech_params['layout']['mos_tech_class'] = MOSTechSOIGenericBC(config, self)
        # tech_params['layout']['res_tech_class'] = ResTechPlanarGeneric(config, self)

    def get_layer_id(self, layer_name):
        # type: (str) -> int
        for key, val in self.config['layer_name'].items():
            if not isinstance(val, list):
                val = [val]
            for val_item in val:
                if val_item == layer_name:
                    return key
        raise ValueError('Unknown layer: %s' % layer_name)

    def get_metal_idc(self, mtype, w, l, dc_temp):
        if mtype == 'x':
            ilim_ma = 1 * w
            imax_ma = 2 * w
            wmin = 0.1
        elif mtype == 'y':
            ilim_ma = 1.1 * w
            imax_ma = 2.2 * w
            wmin = 0.15
        elif mtype == 'z':
            ilim_ma = 1.3 * w
            imax_ma = 2.3 * w
            wmin = 0.3
        else:
            raise ValueError('Unknown metal type: %s' % mtype)

        scale = self.get_idc_scale_factor(dc_temp, mtype, is_res=False)
        return scale * ilim_ma * 1e-3

    @classmethod
    def get_metal_irms(cls, mtype, w):
        if mtype == 'x':
            ilim_ma = 2 * w
        elif mtype == 'y':
            ilim_ma = 3 * w
        elif mtype == 'z':
            ilim_ma = 4 * w
        else:
            raise ValueError('Unknown metal type: %s' % mtype)

        return ilim_ma * 1e-3

    def get_metal_em_specs(self, layer_name, w, l=-1, vertical=False, **kwargs):
        dc_temp = kwargs.get('dc_temp', self.idc_temp)
        mtype = self.get_layer_type(layer_name)
        idc = self.get_metal_idc(mtype, w, l, dc_temp)
        irms = self.get_metal_irms(mtype, w)
        return idc, irms, float('inf')

    def get_via_em_specs(self, via_name, bm_layer, tm_layer, via_type='square',
                         bm_dim=(-1, -1), tm_dim=(-1, -1), array=False, **kwargs):
        dc_temp = kwargs.get('dc_temp', self.idc_temp)
        if (bm_layer == 'SI' or bm_layer == 'POLY' or bm_layer == 'M1' or
            bm_layer == 'M2' or bm_layer == 'M3'):
            idc_ma = 0.1
        elif bm_layer == 'M4' or bm_layer == 'M5':
            idc_ma = 0.2
        else:
            raise ValueError('Unknown bottom layer name: %s' % bm_layer)

        bm_type = self.get_layer_type(bm_layer)
        scale = self.get_idc_scale_factor(dc_temp, bm_type, is_res=False)
        return scale * idc_ma * 1e-3, float('inf'), float('inf')

    def get_res_em_specs(self, res_type, w, l=-1, **kwargs):
        irms_ma = 0.1 + 3 * w
        return float('inf'), irms_ma * 1e-3, float('inf')

    def add_cell_boundary(self, template, box):
        # type: (TemplateBase, BBox) -> None
        pass

    def draw_device_blockage(self, template):
        # type: (TemplateBase) -> None
        pass

    def get_via_arr_enc(self, vname, vtype, mtype, mw_unit, is_bot):
        # type: (...) -> Tuple[Optional[List[Tuple[int, int]]], Optional[Callable[[int, int], bool]]]
        return None, None

    def finalize_template(self, template):
        # type: (TemplateBase) -> None
        pass

    def get_min_area_unit(self,
                          layer_type,  # type: str
                          ):
        """
        Returns the minimum area on the provided layer

        Parameters
        ----------
        layer_type : str
            The layer type

        Returns
        -------
        min_area: float
            The minimum area
        """
        len_min_config = self.config['len_min']
        if layer_type not in len_min_config:
            raise ValueError('Unsupported layer type: %s' % layer_type)

        w_al_list = len_min_config[layer_type]['w_al_list']

        min_area = w_al_list[0][0]

        return min_area

    def get_min_area(self,
                     layer_type,
                     ):
        min_area_unit = self.get_min_area_unit(layer_type)

        return min_area_unit * self.resolution * self.resolution

    def get_min_width_unit(self,
                           layer_type,
                           ):
        len_min_config = self.config['len_min']
        if layer_type not in len_min_config:
            raise ValueError('Unsupported layer type: %s' % layer_type)

        w_al_list = len_min_config[layer_type]['w_al_list']

        min_width = w_al_list[0][1]

        return min_width

    def get_min_width(self,
                      layer_type,
                      ):
        return self.resolution * self.get_min_width_unit(layer_type)
