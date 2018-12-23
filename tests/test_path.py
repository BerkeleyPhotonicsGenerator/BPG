import BPG
from BPG.objects import PhotonicPath
import numpy as np
from BPG.objects import PhotonicPolygon


class Path(BPG.PhotonicTemplateBase):
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

        x = np.arange(0, 2*np.pi, 0.01)
        y = np.cos(x)

        points = [(x[ind], y[ind]) for ind in range(x.shape[0])]
        print("Number of input points:  {}".format(x.shape[0]))

        path = PhotonicPath(
            resolution=self.grid.resolution,
            layer='SI',
            width=0.4,
            points=points,
            unit_mode=False
        )

        self.add_obj(path)

        poly = PhotonicPolygon(
            resolution=self.grid.resolution,
            layer='M1',
            points=points
        )

        self.add_obj(poly)

        poly2 = PhotonicPolygon(
            resolution=self.grid.resolution,
            layer='POLY',
            points=(np.array(path.points) + np.array((1, 0))).tolist()
        )

        self.add_obj(poly2)

        x2 = np.arange(0, 6, 0.0001)
        y2 = np.polyval([0.5,-2,1], x2)
        points2 = [(x2[ind], y2[ind]) for ind in range(x2.shape[0])]
        path2 = PhotonicPath(
            resolution=self.grid.resolution,
            layer='SI',
            width=0.4,
            points=points2,
            unit_mode=False
        )

        self.add_obj(path2)


def test_path():
    spec_file = 'BPG/tests/specs/path_test_specs.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()
    plm.generate_flat_content()
    plm.generate_flat_gds()
    plm.generate_lsf()


if __name__ == '__main__':
    test_path()
