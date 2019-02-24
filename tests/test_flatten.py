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

        self.add_rect(
            layer='SI',
            coord1=(0, 0),
            coord2=(2, 4),
            unit_mode=False
        )
        self.add_photonic_port(name='Sublevel2',
                               center=(0, 0),
                               orient='R0',
                               layer='SI',
                               width=1)


class SubLevel1(BPG.PhotonicTemplateBase):
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

        self.add_rect(
            layer='SI',
            coord1=(0, 0),
            coord2=(2, 4),
            unit_mode=False
        )

        sublevel2_master = self.new_template(params={}, temp_cls=SubLevel2)
        self.add_instance(
            master=sublevel2_master,
            inst_name='sub2_1',
            loc=(0, 5),
            orient='R0'
        )

        self.add_photonic_port(name='Sublevel1',
                               center=(0, 0),
                               orient='R0',
                               layer='SI',
                               width=1)


class TopLevel(BPG.PhotonicTemplateBase):
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

        self.add_rect(
            layer='SI',
            coord1=(0, 0),
            coord2=(2, 4),
            unit_mode=False
        )
        self.add_photonic_port(name='TopLevel',
                               center=(0, 0),
                               orient='R0',
                               layer='SI',
                               width=1)

        sub_master1 = self.new_template(params={}, temp_cls=SubLevel1)
        sub_master2 = self.new_template(params={}, temp_cls=SubLevel2)

        self.add_instance(
            master=sub_master1,
            inst_name='sub1_1',
            loc=(6, 0),
            orient='R0',
        )

        self.add_instance(
            master=sub_master1,
            inst_name='sub1_2',
            loc=(10, 0),
            orient='R0'
        )

        self.add_instance(
            master=sub_master2,
            inst_name='sub2_2',
            loc=(14, 0),
            orient='R0'
        )


def test_flatten():
    spec_file = 'BPG/tests/specs/flatten_test_specs.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()
    plm.generate_flat_content()
    plm.generate_flat_gds()
    plm.dataprep()
    plm.generate_dataprep_gds()
    plm.generate_lsf()


if __name__ == '__main__':
    test_flatten()
