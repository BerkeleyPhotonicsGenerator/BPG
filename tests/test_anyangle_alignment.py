import BPG
from BPG.objects import PhotonicRound
import math
import numpy as np


class Circular90Bend(BPG.PhotonicTemplateBase):
    """
    Class that generates a circular bend. The input to the bend is at (0, 0) and the bend curves
    downwards by 90 degrees. Ports are placed at the input and output of the bend shape

    Parameters
    ----------
    width : float
        width of the waveguide to be drawn
    layer : str
        layer of the waveguide to be drawn
    radius : float
        radius of curvature of the bend shape
    """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        BPG.PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

        # Initialize the variables and dictionary of parameters.
        self.width = self.params['width']
        self.layer = self.params['layer']
        self.bend = None
        self.radius = self.params['radius']

        # Parameter checking: Make sure parameters are valid type and values
        if any(val <= 0 for val in [self.width]):
            raise ValueError("The width cannot be zero or negative")

        if any(not isinstance(val, (int, float)) for val in [self.width]):
            raise ValueError('Width must be int or float')

        if self.radius < self.width * 0.5:
            raise ValueError(f'radius less than 0.5 * width is not allowed for bends. '
                             f'This will cause self-intersecting shapes.')

    @classmethod
    def get_params_info(cls) -> dict:
        return dict(
            width='width of the waveguide',
            layer='layer on which to draw the waveguide',
            radius='radius of curvature of the bend shape',
        )

    def draw_layout(self) -> None:
        self.create_bend()
        self.create_ports()

    def create_bend(self) -> None:
        """
        Generates a bend based on the provided parameters and adds it to the db. For now, this
        simply creates a PhotonicRound. But in the future we may want to change this to do something
        more complex for better performance
        """
        self.bend = PhotonicRound(
            resolution=self.grid.resolution,
            layer=self.layer,
            center=(0, self.radius),
            rin=self.radius - 0.5 * self.params['width'],
            rout=self.radius + 0.5 * self.params['width'],
            theta0=0,
            theta1=-90,
            unit_mode=False,
        )
        self.add_obj(self.bend)

    def create_ports(self) -> None:
        """
        Places ports at the beginning and end of the waveguide
        """
        self.add_photonic_port(
            name='INPUT',
            center=(0, 0),
            orient='R0',
            width=self.width,
            layer=self.layer,
            resolution=self.grid.resolution,
            unit_mode=False,
            show=False
        )

        self.add_photonic_port(
            name='OUTPUT',
            center=(self.radius, self.radius),
            orient='R270',
            width=self.width,
            layer=self.layer,
            resolution=self.grid.resolution,
            unit_mode=False,
            show=False
        )


class SBend(BPG.PhotonicTemplateBase):
    @classmethod
    def get_params_info(cls):
        return dict(
            angle='Angle to rotate the S-bend by',
            width='width of the waveguide',
            layer='layer to draw the waveguide',
            radius='radius of the bend'
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
            angle=math.pi/4,
            width=.5,
            layer='SI',
            radius=5
        )

    def draw_layout(self):
        bend_master = self.new_template(params=self.params, temp_cls=Circular90Bend)
        inst1 = self.add_instance(bend_master, angle=self.params['angle'])
        inst2 = self.add_instance_port_to_port(inst_master=bend_master,
                                               instance_port_name='INPUT',
                                               self_port=inst1['OUTPUT'],
                                               reflect=True)


def test_rotated_alignment():
    spec_file = 'BPG/tests/specs/any_angle_alignment.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()
    # plm.generate_flat_content()
    # plm.generate_flat_gds()
    # plm.dataprep()
    # plm.generate_dataprep_gds()
    # plm.generate_lsf()


if __name__ == '__main__':
    test_rotated_alignment()
