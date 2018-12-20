
import BPG
from BPG.objects import PhotonicRound, PhotonicRect
from bag.layout.objects import BBox
from bag.layout.template import TemplateBase


class DataprepShapes(BPG.PhotonicTemplateBase):
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
            layerA='',
            layerB='',
        )


    @classmethod
    def get_default_param_values(cls):
        return dict(
        )

    def draw_layout(self):
        self.add_round(
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



class SubLevel2(BPG.PhotonicTemplateBase):
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
        """ Specifies the creation of the lumerical shapes """
        circ = BPG.objects.PhotonicRound(
            layer='SI',
            resolution=self.grid.resolution/100,
            center=(40, 30),
            rout=10,
            rin=5,
            # theta0=45,
            # theta1=60,
            unit_mode=False
        )
        self.add_round(circ)

        self.add_rect(
            layer='SI',
            coord1=(10, 10),
            coord2=(20, 24),
        )

        self.add_rect(
            layer='POLY',
            coord1=(-100, -100),
            coord2=(-50, -70),
        )

        self.add_polygon(
            layer='POLY',
            points=[(0, 0), (10, 0), (10, 5), (0, 5)]
        )

        self.add_polygon(
            layer='SI',
            points=[(0, 0), (20, 0), (20, 10)]
        )

        self.add_polygon(
            layer='SI',
            points=[(30, 0), (40, 10), (50, 0), (40, -10)]
        )

        # This rectangle should disappear as it is minimum width
        self.add_rect(
            layer='SI',
            x_span=self.photonic_tech_info.max_width('SI'),
            y_span=self.photonic_tech_info.min_width('SI'),
            center=(40, -10)
        )
        # This rectangle should NOT disappear as it is minimum width + eps
        self.add_rect(
            layer='SI',
            x_span=self.photonic_tech_info.max_width('SI'),
            y_span=self.photonic_tech_info.min_width('SI') + self.grid.resolution,
            center=(40, -20)
        )

        self.add_photonic_port(
            name='Port1',
            center=(-10, -10),
            orient='R0',
            width=1,
            layer='SI'
        )

        self.add_photonic_port(
            name='Port2',
            center=(-10, -10),
            orient='R0',
            width=1,
            layer='POLY'
        )

        has_failed = False
        try:
            self.photonic_tech_info.min_width('LayerDoesNotExist')
        except ValueError:
            has_failed = True

        assert has_failed is True


def test_dataprep():
    # spec_file = 'BPG/tests/specs/dataprep_debug_specs.yaml'
    spec_file = 'BPG/tests/specs/dataprep_specs.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)

    plm.generate_content()
    plm.generate_gds()
    plm.generate_flat_content()
    plm.generate_flat_gds()

    plm.dataprep()
    plm.generate_dataprep_gds()


if __name__ == '__main__':
    test_dataprep()
