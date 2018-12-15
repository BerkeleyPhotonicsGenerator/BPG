import BPG
from bag.layout.util import BBox


class TestPolygon(BPG.PhotonicTemplateBase):
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
            length=4
        )

    def draw_layout(self):
        """ Specifies the creation of the lumerical shapes """
        # Add cladding
        self.add_rect(layer='Clad',
                      bbox=BBox(left=-5,
                                bottom=-5,
                                right=5,
                                top=5,
                                resolution=self.grid.resolution,
                                unit_mode=False)
                      )

        # Add buried oxide layer
        self.add_rect(layer='BOX',
                      bbox=BBox(left=-5,
                                bottom=-5,
                                right=5,
                                top=5,
                                resolution=self.grid.resolution,
                                unit_mode=False)
                      )

        # Add a Si polygon
        self.add_polygon(layer='Si',
                         points=[
                             (0, 0),
                             (2, 0),
                             (2, 3)
                         ])


if __name__ == '__main__':
    spec_file = './specs/LumericalPolygon_spec_file.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()
    plm.generate_flat_content()
    plm.generate_lsf()
