try:
    from .context import BPG
except:
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
            point1='Rectangle corner 1',
            point2='Rectangle corner 2',
        )

    def draw_layout(self):
        """ Specifies the creation of the lumerical shapes """

        self.add_rect(
            layer='SI',
            coord1=self.params['point1'],
            coord2=self.params['point2'],
            unit_mode=False,
        )
        print("Hello world")

        self.add_rect(
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
    spec_file = 'BPG/tests/specs/add_rect_specs.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()
    plm.generate_flat_content()
    plm.generate_flat_gds()
    plm.dataprep()
    plm.generate_dataprep_gds()
    plm.generate_lsf()


if __name__ == '__main__':
    test_add_rect()
