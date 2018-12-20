import BPG


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
        ll = (40, -10)
        ur = (ll[0] + self.photonic_tech_info.max_width('SI'), ll[1] + self.photonic_tech_info.min_width('SI'))
        # This rectangle should disappear as it is minimum width
        self.add_rect(
            layer='SI',
            coord1=ll,
            coord2=ur
        )
        ll = (40, -20)
        ur = (ll[0] + self.photonic_tech_info.max_width('SI'),
              ll[1] + self.photonic_tech_info.min_width('SI') + self.grid.resolution)
        # This rectangle should NOT disappear as it is minimum width + eps
        self.add_rect(
            layer='SI',
            coord1=ll,
            coord2=ur
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
    spec_file = 'BPG/tests/specs/dataprep_debug_specs.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()
    plm.generate_flat_content()
    plm.generate_flat_gds()
    plm.dataprep()
    plm.generate_dataprep_gds()


if __name__ == '__main__':
    test_dataprep()
