import BPG
from bag.layout.util import BBox


class AddSubRect(BPG.PhotonicTemplateBase):
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
            length='Length of Rectangle',
            width='Width of Rectangle',
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
        )

    def draw_layout(self):
        """ Specifies the creation of the lumerical shapes """

        self.add_rect(
            layer='SI',
            bbox=BBox(
                left=0,
                bottom=0,
                right=self.params['width'],
                top=self.params['length'],
                resolution=self.grid.resolution,
                unit_mode=False
            ),
            unit_mode=False
        )


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
            length='Length of Rectangle',
            width='Width of Rectangle',
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
        )

    def draw_layout(self):
        """ Specifies the creation of the lumerical shapes """

        self.add_rect(
            layer='SI',
            bbox=BBox(
                left=0,
                bottom=0,
                right=self.params['width'],
                top=self.params['length'],
                resolution=self.grid.resolution,
                unit_mode=False
            ),
            unit_mode=False
        )
        sub_master = self.new_template(params={'length': self.params['width'],
                                               'width': self.params['length']},
                                       temp_cls=AddSubRect)
        self.add_instance(master=sub_master)


def test_add_rect():
    spec_file = 'BPG/tests/specs/sweep_specs.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    # Sweep the length and width of the rectangle
    size = 1
    num = 10
    for count in range(num):
        plm.generate_template(temp_cls=AddRect, params={
            'length': size,
            'width': size * (count + 1)
        })
    plm.generate_content()
    plm.generate_gds()
    plm.generate_flat_content()
    plm.generate_flat_gds()
    plm.dataprep()
    plm.generate_dataprep_gds()
    plm.generate_lsf()


if __name__ == '__main__':
    test_add_rect()
