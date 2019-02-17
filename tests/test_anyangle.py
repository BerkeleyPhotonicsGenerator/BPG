import BPG
from BPG.geometry import Transformable2D
import random
import math


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


if __name__ == '__main__':
    test_anyangle_conversion_functions()
    test_rectangle_rotation()
