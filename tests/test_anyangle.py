import BPG
from BPG.geometry import Transformable2D
import random
import math
import numpy as np


class AnyAngleBase(BPG.PhotonicTemplateBase):

    @classmethod
    def get_params_info(cls):
        return dict(
            point1='Rectangle corner 1',
            point2='Rectangle corner 2',
        )

    def draw_layout(self):
        self.add_rect(
            layer='SI',
            coord1=self.params['point1'],
            coord2=self.params['point2'],
            unit_mode=False,
        )


class AnyAngleTest(BPG.PhotonicTemplateBase):

    @classmethod
    def get_params_info(cls):
        return dict(
            point1='Rectangle corner 1',
            point2='Rectangle corner 2',
        )

    def draw_layout(self):
        master = self.new_template(params=self.params, temp_cls=AnyAngleBase)
        self.add_instance(master)
        self.add_instance(master, loc=(0, 5), angle=math.pi/4, unit_mode=False)


class AnyAngleNoHierarchyPortToPortLevel1Type1(BPG.PhotonicTemplateBase):
    """
    For test:  test_instance_port_to_port_at_angle_no_hierarchy

    Sub hiearchy level.
    """
    @classmethod
    def get_params_info(cls):
        return dict()

    def draw_layout(self):

        self.add_polygon(
            layer='SI',
            points=[
                (0, -0.2),
                (0, 0.2),
                (1, 0)
            ]
        )

        self.add_photonic_port(
            name="PORT0",
            center=(0, 0),
            orient='R0',
            angle=0,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )

        self.add_photonic_port(
            name="PORT1",
            center=(1, 0),
            orient='R0',
            angle=0,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )


class AnyAngleNoHierarchyPortToPortLevel1Type2(BPG.PhotonicTemplateBase):
    """
    For test:  test_instance_port_to_port_at_angle_no_hierarchy

    Sub hiearchy level.
    """
    @classmethod
    def get_params_info(cls):
        return dict(
            port_angle='Angle at which to place the port',
            top_angle='Angle of the port to which this port is being connected'
        )

    def draw_layout(self):
        angle = self.params['port_angle']
        top_angle = self.params['top_angle']

        # Make polygon point in direction of original port, after it will be rotated. Makes checking easy
        self.add_polygon(
            layer='SI',
            points=[
                (0, -0.2),
                (0, 0.2),
                (np.cos(-(np.pi + top_angle - angle) + angle), np.sin(-(np.pi + top_angle - angle) + angle))
            ]
        )

        self.add_photonic_port(
            name="PORT0",
            center=(0, 0),
            orient='R0',
            angle=angle,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )


class AnyAngleNoHierarchyPortToPort(BPG.PhotonicTemplateBase):
    """
    For test:  test_instance_port_to_port_at_angle_no_hierarchy

    Add a port at an angle, add an instance port to port and make sure it is where we expect.

    Add ports and objects at both levels of hierarchy to make sure that things that should not rotate do not.
    """
    @classmethod
    def get_params_info(cls):
        return dict()

    def draw_layout(self):
        #####
        # Row 0:  Add an array of ports with nothing connected.
        #####
        angle_step = 2*np.pi/36
        num_tests = int(round(2*np.pi/angle_step)) + 1
        port_port_pitch = 4
        for ind in range(num_tests):

            port_name = f'TopPort_Test0_{np.rad2deg(ind * angle_step):.2f}_deg'

            port_angle = ind*angle_step

            port = self.add_photonic_port(
                name=port_name,
                center=(ind*port_port_pitch, 0),
                orient='R0',
                angle=port_angle,
                width=0.4,
                layer='SI',
                resolution=self.grid.resolution,
                unit_mode=False,
            )

            if abs(port_angle % (np.pi/2)) < Transformable2D.SMALL_ANGLE_TOLERANCE :
                assert port.is_cardinal
            else:
                assert not port.is_cardinal

        #####
        # Row 1:  Add an array of ports.
        #   Connect a small rectangle with port at R0 using port-to-port
        #####
        sub_inst_master = self.new_template(temp_cls=AnyAngleNoHierarchyPortToPortLevel1Type1)

        angle_step = 2 * np.pi / 36
        num_tests = int(round(2 * np.pi / angle_step)) + 1
        port_port_pitch = 4
        for ind in range(num_tests):

            port_name = f'TopPort_Test1_{np.rad2deg(ind * angle_step):.2f}_deg'

            port_angle = ind * angle_step

            port = self.add_photonic_port(
                name=port_name,
                center=(ind * port_port_pitch, 10),
                orient='R0',
                angle=port_angle,
                width=0.4,
                layer='SI',
                resolution=self.grid.resolution,
                unit_mode=False,
            )

            self.add_instance_port_to_port(
                inst_master=sub_inst_master,
                instance_port_name='PORT0',
                self_port=port,
                instance_name='SubInstLevel1Inst1',
            )

        #####
        # Row 2:  Add an array of ports.
        #   Connect a small rectangle with port at R0 using port-to-port
        #   Have the port in the subinst be at an arbitrary angle
        #   add a port pointing to the random direction at the top level
        #####

        angle_step = 2 * np.pi / 36
        num_tests = int(round(2 * np.pi / angle_step)) + 1
        port_port_pitch = 4
        for ind in range(num_tests):
            port_name = f'TopPort_Test2_{np.rad2deg(ind * angle_step):.2f}_deg'
            port_angle = ind * angle_step

            sub_inst_angle = random.uniform(0, 2*np.pi)
            sub_inst_master = self.new_template(
                params=dict(
                    port_angle=sub_inst_angle,
                    top_angle=port_angle
                ),
                temp_cls=AnyAngleNoHierarchyPortToPortLevel1Type2
            )

            port = self.add_photonic_port(
                name=port_name,
                center=(ind * port_port_pitch, 20),
                orient='R0',
                angle=port_angle,
                width=0.4,
                layer='SI',
                resolution=self.grid.resolution,
                unit_mode=False,
            )

            self.add_instance_port_to_port(
                inst_master=sub_inst_master,
                instance_port_name='PORT0',
                self_port=port,
                instance_name='SubInstLevel1Inst1',
            )

            self.add_photonic_port(
                name=f'{port_name}_angle',
                center=(ind * port_port_pitch, 21),
                orient='R0',
                angle=sub_inst_angle,
                width=0.4,
                layer='SI',
                resolution=self.grid.resolution,
                unit_mode=False,
            )


'''
Hierarchy test
'''


class AnyAngleHierarchyLevel1(BPG.PhotonicTemplateBase):
    """
    For test:  test_instance_port_to_port_at_angle_no_hierarchy

    Sub hiearchy level.
    """
    @classmethod
    def get_params_info(cls):
        return dict()

    def draw_layout(self):
        print(f'sub instance 1 draw layout:   self.angle: {np.rad2deg(self.angle)}')
        self.add_rect(
            layer='SI',
            coord1=(3, 5),
            coord2=(40, 7)
        )

        self.add_photonic_port(
            name="PORT0_level1",
            center=(3, 6),
            orient='R0',
            angle=0,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )

        p1 = self.add_photonic_port(
            name="PORT1_level1",
            center=(9, 7),
            orient='R270',
            angle=np.pi/6,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )

        p2 = self.add_photonic_port(
            name="PORT2_level1",
            center=(39, 7),
            orient='R270',
            angle=np.pi / 6,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )

        l2master = self.new_template(temp_cls=AnyAngleHierarchyLevel2)

        inst2 = self.add_instance_port_to_port(
            inst_master=l2master,
            instance_port_name='PORT0_level2',
            self_port=p1,
            instance_name='LEVEL2'
        )

        inst2b = self.add_instance_port_to_port(
            inst_master=l2master,
            instance_port_name='PORT0_level2',
            self_port=p2,
            instance_name='LEVEL2'
        )

        self.extract_photonic_ports(
            inst=inst2,
            port_names='PORT0_level2',
            port_renaming={'PORT0_level2': 'DEBUGPORT'}
        )

        self.extract_photonic_ports(
            inst=inst2b,
            port_names='PORT0_level2',
            port_renaming={'PORT0_level2': 'DEBUGPORT2'}
        )


class AnyAngleHierarchyLevel2(BPG.PhotonicTemplateBase):
    """
    For test:  test_instance_port_to_port_at_angle_no_hierarchy

    Sub hiearchy level.
    """
    @classmethod
    def get_params_info(cls):
        return dict()

    def draw_layout(self):
        print(f'sub instance 2 draw layout:   self.angle: {np.rad2deg(self.angle)}')
        self.add_rect(
            layer='SI',
            coord1=(1, -0.5),
            coord2=(6, 4.5)
        )

        self.add_photonic_port(
            name="PORT0_level2",
            center=(1, 2),
            orient='R0',
            angle=0,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )

        self.add_photonic_port(
            name="PORT1_level2",
            center=(5, 4.5),
            orient='R270',
            angle=0,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )


class AnyAngleWithHierarchyPortToPort(BPG.PhotonicTemplateBase):
    """
    Add multiple leves of hierarchy.
    See what happens.
    """
    @classmethod
    def get_params_info(cls):
        return dict()

    def draw_layout(self):
        p1 = self.add_photonic_port(
            name='P1',
            center=(10, 0),
            orient='R180',
            angle=np.pi/4,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )

        p2 = self.add_photonic_port(
            name='P2',
            center=(0, 10),
            orient='R0',
            angle=0,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )

        l1master = self.new_template(temp_cls=AnyAngleHierarchyLevel1)
        l2master = self.new_template(temp_cls=AnyAngleHierarchyLevel2)

        self.add_instance_port_to_port(
            inst_master=l1master,
            instance_port_name='PORT0_level1',
            self_port=p1,
            instance_name='L1'
        )
        self.add_instance_port_to_port(
            inst_master=l2master,
            instance_port_name='PORT0_level2',
            self_port=p2,
            instance_name='L2'
        )

        l3master = self.new_template(temp_cls=AnyAngleHierarchyLevel1)#, angle=5*np.pi/3)

        self.add_instance(
            master=l3master,
            inst_name='NewTemplateWithDirectAngle',
            loc=(-100, 0),
            orient='R0',
            angle=0,
        )

        self.add_instance(
            master=l3master,
            inst_name='NewTemplateWithDirectAngle2',
            loc=(-100, 30),
            orient='R90',
            angle=0,
        )

        self.add_instance(
            master=l3master,
            inst_name='NewTemplateWithDirectAngle3',
            loc=(-100, 50),
            orient='R0',
            angle=0.01,
        )

        self.add_instance(
            master=l3master,
            inst_name='NewTemplateWithDirectAngle4',
            loc=(-10, 50),
            orient='R0',
            angle=0.0,
        )


def test_anyangle_conversion_functions():
    iterations = 100

    angle_min = -10 * math.pi / 2
    angle_max = 10 * math.pi / 2
    for orient in Transformable2D.OrientationsAll:
        for ind in range(iterations):
            mod_angle = random.uniform(angle_min, angle_max)

            angle, mirrored = Transformable2D.orient2angle(orient, mod_angle)
            new_orient, new_mod_angle, _, num_90 = Transformable2D.angle2orient(angle, mirrored)

            # Difficult to check orientation and mod angle. Instead, check that the produced angle, mirror are good
            new_angle, new_mirrored = Transformable2D.orient2angle(new_orient, new_mod_angle)
            assert (new_mirrored == mirrored and math.isclose(new_angle, angle % (2 * math.pi))), \
                f'{ind}: (or, mod_ang) = ({orient}, {mod_angle / math.pi:.3}pi) -> ' \
                f'(ang, mir) = ({angle / math.pi:.3}pi, {mirrored}) -> ' \
                f'(or, mod_ang) = ({new_orient}, {new_mod_angle / math.pi:.3}pi)'

    angle_min = -10 * math.pi
    angle_max = 10 * math.pi
    for mirrored in [True, False]:
        for ind in range(iterations):
            angle = random.uniform(angle_min, angle_max)

            orient, mod_angle, _, _ = Transformable2D.angle2orient(angle, mirrored)
            new_angle, new_mirrored = Transformable2D.orient2angle(orient, mod_angle)

            # Check that the new mod angle is bounded by 0<mod_angle<pi/2
            assert (0 <= mod_angle < math.pi / 2), \
                f'{ind}: (ang, mir) = ({angle / math.pi:.3}pi, {mirrored}) -> ' \
                f'(or, mod_ang) = ({orient}, {mod_angle / math.pi:.3}pi) -> ' \
                f'MOD_ANGLE NOT WITHIN [0, pi/2)'

            # Check that input and output are equivalent
            assert (new_mirrored == mirrored and math.isclose(new_angle, angle % (2 * math.pi))), \
                f'{ind}: (ang, mir) = ({angle / math.pi:.3}pi, {mirrored}) -> ' \
                f'(or, mod_ang) = ({orient}, {mod_angle / math.pi:.3}pi) -> ' \
                f'(ang, mir) = ({new_angle / math.pi:.3}pi, {new_mirrored})'


def test_rectangle_rotation():
    spec_file = 'BPG/tests/specs/any_angle_specs.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()
    plm.generate_flat_content()
    plm.generate_flat_gds()
    plm.dataprep()
    plm.generate_dataprep_gds()
    plm.generate_lsf()


def test_instance_port_to_port_at_angle_no_hierarchy():
    spec_file = 'BPG/tests/specs/any_angle_port_to_port_at_angle_no_hierarchy_specs.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()
    # plm.generate_flat_content()
    # plm.generate_flat_gds()
    # plm.dataprep()
    # plm.generate_dataprep_gds()
    # plm.generate_lsf()


def test_instance_port_to_port_at_angle_hierarchy():
    spec_file = 'BPG/tests/specs/any_angle_port_to_port_at_angle_hierarchy_specs.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()
    plm.generate_flat_content()
    plm.generate_flat_gds()
    # plm.dataprep()
    # plm.generate_dataprep_gds()
    # plm.generate_lsf()


if __name__ == '__main__':
    test_anyangle_conversion_functions()
    test_rectangle_rotation()
    test_instance_port_to_port_at_angle_no_hierarchy()
    test_instance_port_to_port_at_angle_hierarchy()
