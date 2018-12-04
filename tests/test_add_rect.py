import BPG
from bag.layout.util import BBox


class AddRect(BPG.PhotonicTemplateBase):
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
            x='Rectangle x span in microns',
            y='Rectangle y span in microns',
            center='Rectangle center coord',
            point1='Rectangle corner 1',
            point2='Rectangle corner 2',
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
        )

    def draw_layout(self):
        """ Specifies the creation of the lumerical shapes """

        r1 = self.add_rect(
            layer='SI',
            x_span=self.params['x'],
            y_span=self.params['y'],
            center=self.params['center'],
            unit_mode=False,
        )

        r2 = self.add_rect(
            layer='SI',
            coord1=self.params['point1'],
            coord2=self.params['point2'],
            unit_mode=False,
        )

        r3 = self.add_rect(
            layer='SI',
            bbox=BBox(
                left=1,
                bottom=-10,
                right=10,
                top=-7,
                resolution=self.grid.resolution,
                unit_mode=False
            ),
            unit_mode=False
        )


def test_add_rect():
    """
    Unit test definition
    """
    # # Load a previous BPG Project if it exists, otherwise create a new one
    # local_dict = locals()
    # if 'prj' not in local_dict:
    #     print('Creating BAG project')
    #     bprj = BPG.PhotonicBagProject()
    #
    # else:
    #     print('Loading BAG project')
    #     bprj = local_dict['bprj']

    spec_file = 'BPG/tests/specs/add_rect_specs.yaml'
    # PLM = BPG.PhotonicLayoutManager(bprj, spec_file)
    PLM = BPG.PhotonicLayoutManager(spec_file)
    PLM.generate_gds()
    PLM.generate_flat_gds()
    PLM.dataprep()
    PLM.generate_lsf()


if __name__ == '__main__':
    test_add_rect()
