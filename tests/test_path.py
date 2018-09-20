import BPG
from BPG.photonic_objects import PhotonicPath
import numpy as np
from BPG.photonic_objects import PhotonicPolygon
from BPG.poly_simplify import simplify_coord_to_gdspy
from BPG.dataprep_gdspy import polyop_gdspy_to_point_list


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

        self.add_path(path)

        poly = PhotonicPolygon(
            resolution=self.grid.resolution,
            layer='M1',
            points=points
        )

        self.add_polygon(polygon=poly)

        poly2 = PhotonicPolygon(
            resolution=self.grid.resolution,
            layer='POLY',
            points=(np.array(path.points) + np.array((1, 0))).tolist()
        )

        self.add_polygon(poly2)

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

        self.add_path(path2)

        # gdspy_poly = simplify_coord_to_gdspy(
        #     (path2.polygon_points, []),
        #     tolerance=1e-3
        # )
        #
        # simplified_points = polyop_gdspy_to_point_list(
        #     gdspy_poly, fracture=False, do_manh=False, manh_grid_size=0.001, debug=False
        # )
        #
        # path3 = PhotonicPolygon(
        #     resolution=self.grid.resolution,
        #     layer='M2',
        #     points=simplified_points[0]
        # )


def test_path():
    """
    Unit Test
    """
    # Load a previous BPG Project if it exists, otherwise create a new one
    local_dict = locals()
    if 'prj' not in local_dict:
        print('creating BAG project')
        bprj = BPG.PhotonicBagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    spec_file = 'BPG/tests/specs/path_test_specs.yaml'
    plm = BPG.PhotonicLayoutManager(bprj, spec_file)
    plm.generate_gds()
    plm.generate_flat_gds()
    plm.generate_lsf()


if __name__ == '__main__':
    test_path()
