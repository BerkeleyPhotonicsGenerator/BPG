import BPG
from bag.layout.util import BBox


class AddViaStack(BPG.PhotonicTemplateBase):
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
        )

    def draw_layout(self):
        """ Specifies the creation of the lumerical shapes """

        metal_stack_info: dict = self.photonic_tech_info.dataprep_parameters['MetalStack']
        layer_names = list(metal_stack_info.keys())

        top_metal_name = layer_names[0]
        for metal_name, metal_info in metal_stack_info.items():
            if metal_info['index'] > metal_stack_info[top_metal_name]['index']:
                top_metal_name = metal_name

        dx = 10
        for ind, metal_name in enumerate(layer_names):
            if metal_name != top_metal_name:
                self.add_via_stack(
                    bot_layer=metal_name,
                    top_layer=top_metal_name,
                    loc=(dx * ind, 0),
                    unit_mode=False
                )


def test_add_via_stack():
    """
    Unit test definition
    """
    spec_file = 'bpg_test_suite/specs/add_via_stack.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()


if __name__ == '__main__':
    test_add_via_stack()
