import BPG
from bag.layout.util import BBox


class SingleModeWaveguide(BPG.PhotonicTemplateBase):
    def __init__(self, temp_db,
                 lib_name,
                 params,
                 used_names,
                 **kwargs,
                 ):
        """ Class for generating a single mode waveguide shape in Lumerical """
        BPG.PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_params_info(cls):
        return dict(
            width='Waveguide width in microns',
            length='Waveguide length in microns'
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
            width=.6,
            length=10
        )

    def draw_layout(self):
        """ Specifies the creation of the lumerical shapes """
        # Pull in parameters from dictionary for easy access
        width = self.params['width']
        length = self.params['length']

        # Add cladding
        clad = self.add_rect(layer='CLAD',
                             bbox=BBox(left=-.5 * length,
                                       bottom=-.5 * length,
                                       right=.5 * length,
                                       top=.5 * length,
                                       resolution=self.grid.resolution,
                                       unit_mode=False)
                             )

        # Add buried oxide layer
        box = self.add_rect(layer='BOX',
                            bbox=BBox(left=-.5 * length,
                                      bottom=-.5 * length,
                                      right=.5 * length,
                                      top=.5 * length,
                                      resolution=self.grid.resolution,
                                      unit_mode=False)
                            )

        # Add waveguide
        wg0 = self.add_rect(layer='SI',
                            bbox=BBox(left=-.5 * width,
                                      bottom=-.5 * length,
                                      right=0.5 * width,
                                      top=.5 * length,
                                      resolution=self.grid.resolution,
                                      unit_mode=False)
                            )

        self.add_photonic_port(name='FDEPort',
                               center=(0, 0),
                               orient='R90',
                               width=width,
                               layer='SI')


if __name__ == '__main__':
    # Load a previous BPG Project if it exists, otherwise create a new one
    local_dict = locals()
    if 'prj' not in local_dict:
        print('creating BAG project')
        bprj = BPG.PhotonicBagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    spec_file = 'BPG/examples/specs/example_spec_file.yaml'
    PLM = BPG.PhotonicLayoutManager(bprj, spec_file)
    PLM.generate_flat_gds()
    PLM.generate_lsf()
