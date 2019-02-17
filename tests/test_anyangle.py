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

        self.add_rect(
            layer='SI',
            coord1=(5, 6),
            coord2=(10, 8),
        )

        self.add_photonic_port(
            name="PORT0",
            center=(5, 7),
            orient='R0',
            angle=0,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )

        self.add_photonic_port(
            name="SubLevel1Type1Port0",
            center=(9, 2),
            orient='R90',
            angle=0,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )

        self.add_photonic_port(
            name="SubLevel1Type1Port1",
            center=(9, 2),
            orient='R90',
            angle=np.pi/5,
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

        self.add_polygon(
            layer='SI',
            points=[
                (0, 0),
                (5, 1),
                (7, 7),
                (3, 6),
            ],
            resolution=self.grid.resolution

        )
        self.add_rect(
            layer='SI',
            coord1=(10, 10),
            coord2=(12, 15),
            unit_mode=False,
        )
        print('AnyAngleNoHierarchy  Before first port')
        self.add_photonic_port(
            name="BasePort",
            center=(15, 15),
            orient='R0',
            angle=np.pi / 6,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )
        print('AnyAngleNoHierarchy  After first port')

        self.add_photonic_port(
            name="DummyTopPort",
            center=(10, 2),
            orient='R0',
            angle=5 * np.pi / 7,
            width=0.4,
            layer='SI',
            resolution=self.grid.resolution,
            unit_mode=False,
        )

        subinst_master = self.new_template(temp_cls=AnyAngleNoHierarchyPortToPortLevel1Type1)
        self.add_instances_port_to_port(
            inst_master=subinst_master,
            instance_port_name='PORT0',
            self_port_name='BasePort',
            instance_name='SubInstLevel1Inst1',
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
    plm.generate_template()
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
    plm.generate_template()
    plm.generate_content()
    plm.generate_gds()
    #plm.generate_flat_content()
    #plm.generate_flat_gds()
    #plm.dataprep()
    #plm.generate_dataprep_gds()
    #plm.generate_lsf()


if __name__ == '__main__':
    # test_anyangle_conversion_functions()
    # test_rectangle_rotation()
    test_instance_port_to_port_at_angle_no_hierarchy()
