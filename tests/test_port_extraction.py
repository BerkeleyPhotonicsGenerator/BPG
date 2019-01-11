import BPG
from BPG.port import PhotonicPort


class SubObject(BPG.PhotonicTemplateBase):
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
            coord2=(10, 20),
            unit_mode=False,
        )

        self.add_photonic_port(
            name='Port1',
            center=(0, 1),
            orient='R0',
            width=1,
            layer=('SI', 'phot'),
        )

        port2 = PhotonicPort(
            name='Port2',
            center=(0, 10),
            orient='R0',
            width=1,
            layer=('SI', 'phot'),
            resolution=self.grid.resolution
        )
        self.add_photonic_port(
            port=port2
        )

        self.add_photonic_port(
            name='Port3',
            center=(5, 0),
            orient='R90',
            width=1,
            layer=('SI', 'phot'),
        )

        self.add_photonic_port(
            name='Port4',
            center=(8, 20),
            orient='R270',
            width=1,
            layer=('SI', 'phot'),
        )


class PortExtraction(BPG.PhotonicTemplateBase):
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
            coord1=(-5, -5),
            coord2=(-2, -3),
            unit_mode=False,
        )

        subobj_master = self.new_template(temp_cls=SubObject)

        self.add_instance(
            master=subobj_master,
            inst_name='inst1',
            loc=(0, 0),
            orient='R0',
            unit_mode=False,
        )

        inst2 = self.add_instance(
            master=subobj_master,
            inst_name='inst2_reexport_these',
            loc=(20, 0),
            orient='R0',
            unit_mode=False,
        )

        self.extract_photonic_ports(
            inst=inst2,
        )

        inst3 = self.add_instance(
            master=subobj_master,
            inst_name='inst3_reexport_these_with_new_names',
            loc=(40, 0),
            orient='R180',
            unit_mode=False,
        )

        self.extract_photonic_ports(
            inst=inst3,
            port_renaming=dict(Port2='New2', Port3='New3',)
        )

        inst4 = self.add_instance(
            master=subobj_master,
            inst_name='inst4_export_some_names',
            loc=(60, 0),
            orient='R0',
            unit_mode=False,
        )

        self.extract_photonic_ports(
            inst=inst4,
            port_names=['Port1', 'Port4'],
            port_renaming=dict(Port1='inst4_Port1', Port2='inst4_port2')
        )


def test_port_extraction():
    spec_file = 'BPG/tests/specs/port_extraction_specs.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()
    plm.generate_flat_content()
    plm.generate_flat_gds()
    plm.generate_lsf()


if __name__ == '__main__':
    test_port_extraction()
