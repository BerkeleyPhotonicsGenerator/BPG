import BPG
from BPG.photonic_objects import PhotonicRound


class AddRound(BPG.PhotonicTemplateBase):
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
            center='Circle center coord',
            rout='Circle outer radius',
            rin='Circle inner radius',
            theta0='Circle start angle (deg)',
            theta1='Circle stop angle (deg)',
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
        )

    def draw_layout(self):
        """ Specifies the creation of the lumerical shapes """

        circle = PhotonicRound(
            layer='SI',
            resolution=self.grid.resolution,
            center=(0, 0),
            rout=1,
            rin=0.1,
            theta0=45,
            theta1=190,
            unit_mode=False
        )

        self.add_round(
            round_obj=circle
        )
        
        self.add_round(
            round_obj=circle.transform((0, 10), 'R90')
        )
        self.add_round(
            round_obj=circle.transform((10, 10), 'R180')
        )
        self.add_round(
            round_obj=circle.transform((20, 10), 'R270')
        )
        self.add_round(
            round_obj=circle.transform((30, 10), 'MX')
        )
        self.add_round(
            round_obj=circle.transform((40, 10), 'MY')
        )
        self.add_round(
            round_obj=circle.transform((50, 10), 'MXR90')
        )
        self.add_round(
            round_obj=circle.transform((60, 10), 'MYR90')
        )


def test_add_round():
    """
    Unit Test
    """
    # Load a previous BPG Project if it exists, otherwise create a new one
    local_dict = locals()
    if 'prj' not in local_dict:
        print('creating BAG project')
        bprj = BPG.PhotonicBagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    spec_file = 'BPG/tests/specs/add_round_specs.yaml'
    PLM = BPG.PhotonicLayoutManager(bprj, spec_file)
    PLM.generate_gds()
    PLM.generate_flat_gds()
    PLM.generate_lsf()


if __name__ == '__main__':
    test_add_round()
