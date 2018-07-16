import BPG


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

        r1 = self.add_rect(
            layer='Si',
            coord1=(0, 0),
            coord2=(10, 20),
            unit_mode=False,
        )

        p1 = self.add_photonic_port(
            name='Port1',
            center=(0, 1),
            orient='R0',
            width=1,
            layer=('Si', 'phot'),
        )

        p2 = self.add_photonic_port(
            name='Port2',
            center=(0, 10),
            orient='R0',
            width=1,
            layer=('Si', 'phot'),
        )

        p3 = self.add_photonic_port(
            name='Port3',
            center=(5, 0),
            orient='R90',
            width=1,
            layer=('Si', 'phot'),
        )

        p4 = self.add_photonic_port(
            name='Port4',
            center=(8, 20),
            orient='R270',
            width=1,
            layer=('Si', 'phot'),
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

        r1 = self.add_rect(
            layer='Si',
            coord1=(-5, -5),
            coord2=(-2, -3),
            unit_mode=False,
        )

        subobj_master = self.new_template(temp_cls=SubObject)

        inst1 = self.add_instance(
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


if __name__ == '__main__':
    # Load a previous BPG Project if it exists, otherwise create a new one
    local_dict = locals()
    if 'prj' not in local_dict:
        print('creating BAG project')
        bprj = BPG.PhotonicBagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    spec_file = './specs/port_extraction_specs.yaml'
    PLM = BPG.PhotonicLayoutManager(bprj, spec_file)
    PLM.generate_gds()
    # PLM.generate_lsf()
