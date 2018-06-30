
from bag.layout.template import TemplateBase
from bag.layout.util import BBox
import yaml
import os
import sys

from bag.core import BagProject
from bag.layout import RoutingGrid, TemplateDB
from BPG.photonics_template import PhotonicTemplateBase, PhotonicPort, PhotonicTemplateDB
from BPG.photonic_core import PhotonicBagProject
from examples.waveguide import Waveguide, WaveguideVert, WaveguideConnectTest


def make_tdb(prj, target_lib, specs):
    grid_specs = specs['routing_grid']
    layers = grid_specs['layers']
    spaces = grid_specs['spaces']
    widths = grid_specs['widths']
    bot_dir = grid_specs['bot_dir']

    routing_grid = RoutingGrid(prj.tech_info, layers, spaces, widths, bot_dir)
    tdb = TemplateDB('template_libs.def', routing_grid, target_lib, use_cybagoa=True,
                     gds_lay_file=os.path.dirname(os.path.abspath(__file__)) + '/gds_map.yaml')
    return tdb


def generate(prj, specs, gen_layout=True):
    # Get information from YAML
    lib_name = specs['lib_name']
    cell_name = specs['cell_name']
    params = specs['params']

    temp_db = make_tdb(prj, impl_lib, specs)
    temp = temp_db.new_template(params=params, temp_cls=WaveguideConnectTest, debug=False)

    if gen_layout:
        print('creating layout')
        temp_db.batch_layout(prj, [temp], [cell_name])
        print('done')


if __name__ == '__main__':

    impl_lib = 'PhotTest'

    with open(os.path.dirname(os.path.abspath(__file__)) + '/waveguide_specs.yaml', 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'prj' not in local_dict:
        print('creating BAG project')
        bprj = PhotonicBagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    generate(bprj, block_specs, gen_layout=True)
