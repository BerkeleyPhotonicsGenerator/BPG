import BPG
import os
import yaml

from bag.layout.util import BBox
from BPG.photonic_core import PhotonicBagProject
from BPG.photonics_template import PhotonicTemplateDB
from bag.layout import RoutingGrid


class SingleModeWaveguide(BPG.PhotonicTemplateBase):
    def __init__(self, temp_db,
                 lib_name,
                 params,
                 used_names,
                 **kwargs,
                 ):
        """ Class for generating a single mode waveguide shape in Lumerical """
        BPG.PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    def get_params_info(cls):
        return dict(
            width='Waveguide width in microns',
            length='Waveguide legnth in microns'
        )

    def get_default_param_values(cls):
        return dict(
            width=.6,
            length=4
        )

    def draw_layout(self):
        """ Specifies the creation of the lumerical shapes """
        # Add cladding
        clad = self.add_rect(layer='Clad',
                             bbox=BBox(left=-2,
                                       bottom=-2,
                                       right=2,
                                       top=2,
                                       resolution=self.grid.resolution,
                                       unit_mode=False)
                             )

        # Add buried oxide layer
        box = self.add_rect(layer='BOX',
                            bbox=BBox(left=-2,
                                      bottom=-2,
                                      right=2,
                                      top=2,
                                      resolution=self.grid.resolution,
                                      unit_mode=False)
                            )

        # Add waveguide
        wg0 = self.add_rect(layer='Si',
                            bbox=BBox(left=-2,
                                      bottom=.5,
                                      right=2,
                                      top=1.5,
                                      resolution=self.grid.resolution,
                                      unit_mode=False)
                            )


def make_tdb(prj, target_lib, specs):
    grid_specs = specs['routing_grid']
    layers = grid_specs['layers']
    spaces = grid_specs['spaces']
    widths = grid_specs['widths']
    bot_dir = grid_specs['bot_dir']

    routing_grid = RoutingGrid(prj.tech_info, layers, spaces, widths, bot_dir)
    tdb = PhotonicTemplateDB('template_libs.def', routing_grid, target_lib, use_cybagoa=True,
                     gds_lay_file=os.path.dirname(os.path.abspath(__file__)) + '/gds_map.yaml')
    return tdb


def generate(prj, specs, spec_file, gen_layout=True):
    # Get information from YAML
    lib_name = specs['lib_name']
    cell_name = specs['cell_name']
    params = specs['params']

    temp_db = make_tdb(prj, impl_lib, specs)
    temp = temp_db.new_template(params=params, temp_cls=SingleModeWaveguide, debug=False)

    if gen_layout:
        print('creating layout')
        temp_db.batch_layout(prj, [temp], [cell_name])
        print('done')

    print('Creating LSF')
    temp_db.to_lumerical(spec_file)


if __name__ == '__main__':
    impl_lib = 'PhotTest1'

    spec_file = os.path.dirname(os.path.abspath(__file__)) + '/example_spec_file.yaml'

    with open(spec_file, 'r') as f:
        block_specs = yaml.load(f)

    local_dict = locals()
    if 'prj' not in local_dict:
        print('creating BAG project')
        bprj = PhotonicBagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    generate(bprj, block_specs, spec_file, gen_layout=True)
