import BPG
from BPG.objects import PhotonicRound
from bag.layout.objects import BBox


class DataprepShapes(BPG.PhotonicTemplateBase):
    def __init__(self, temp_db,
                 lib_name,
                 params,
                 used_names,
                 **kwargs,
                 ):
        BPG.PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_params_info(cls):
        return dict(
            layerA='',
            layerB='',
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
        )

    def draw_layout(self):
        self.add_obj(
            PhotonicRound(
                layer=self.params['layerA'],
                resolution=self.grid.resolution,
                rout=1,
                center=(0, 0),
                rin=0,
                unit_mode=False,
            )
        )

        self.add_rect(
            layer=self.params['layerB'],
            coord1=(0.5, 0.25),
            coord2=(2, 3),
            unit_mode=False,
        )


class DataprepOpsTest(BPG.PhotonicTemplateBase):
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

    @classmethod
    def get_default_param_values(cls):
        return dict(
        )

    def draw_layout(self):
        # Add the DataprepShapes in multiple places, and add labels

        spx = 10
        label_list = ['add', 'sub', 'xor', 'and', 'rad', ]

        for i, el in enumerate(label_list):
            shapes_master = self.new_template(temp_cls=DataprepShapes,
                                              params=dict(
                                                  layerA=(f'layerA_{el}', 'drawing'),
                                                  layerB=(f'layerB_{el}', 'drawing'))
                                              )

            self.add_instance(
                master=shapes_master,
                loc=(spx * i, 0),
                orient='R0',
                unit_mode=False,
            )

            self.add_label(
                label=el,
                layer=('text', 'drawing'),
                bbox=BBox(
                    left=spx * i,
                    bottom=5,
                    right=spx * i + 0.001,
                    top=5.001,
                    resolution=self.grid.resolution,
                    unit_mode=False,
                )
            )

        self.add_label(
            label='Circle is on layerA_op. Rectangle is on layerB_op.  Dataprep does B (+/-/xor/and) A',
            layer=('text', 'drawing'),
            bbox=BBox(
                left=0,
                bottom=-5,
                right=0.001,
                top=-4.999,
                resolution=self.grid.resolution,
                unit_mode=False,
            )
        )


def test_dataprep():
    spec_file = 'BPG/tests/specs/dataprep_specs_op.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()
    plm.generate_flat_content()
    plm.generate_flat_gds()

    plm.dataprep()
    plm.generate_dataprep_gds()


if __name__ == '__main__':
    test_dataprep()
