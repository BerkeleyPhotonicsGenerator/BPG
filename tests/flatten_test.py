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

        circ = BPG.photonic_objects.PhotonicRound(
            layer='Si',
            resolution=self.grid.resolution,
            center=(3,3),
            rout=2,
            theta0=45,
            theta1=60,
            unit_mode=False
        )
        self.add_round(circ)


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

        self.add_polygon(
            layer='Si',
            points=[(0, 0), (3, 0), (2, 6), (0, 4)]
        )

        sublevel2_master = self.new_template(params={}, temp_cls=SubLevel2)
        self.add_instance(
            master=sublevel2_master,
            inst_name='sub2_name',
            loc=(5, 1),
            orient='R180'
        )



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
            layer='Si',
            coord1=(5, 3),
            coord2=(6, 6),
            unit_mode=False
        )

        sub_master = self.new_template(params={}, temp_cls=SubLevel1)

        self.add_instance(
            master=sub_master,
            inst_name='sub_inst_name',
            loc=(-10, 9),
            orient='R0',
        )

        self.add_instance(
            master=sub_master,
            inst_name='sub2',
            loc=(20, 20),
            orient='MXR90'
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

    spec_file = './specs/flatten_test_specs.yaml'
    PLM = BPG.PhotonicLayoutManager(bprj, spec_file)
    PLM.generate_gds()
    # PLM.generate_lsf()
    PLM.generate_flat_gds(debug=False)
