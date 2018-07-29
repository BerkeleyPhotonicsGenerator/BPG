import BPG
from BPG.photonic_objects import PhotonicPath
import numpy as np
from BPG.photonic_objects import PhotonicPolygon


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
            points=np.array(path.points) + np.array((1, 0)).tolist()
        )

        self.add_polygon(poly2)

        x2 = np.arange(0, 6, 0.001)
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


if __name__ == '__main__':
    # Load a previous BPG Project if it exists, otherwise create a new one
    local_dict = locals()
    if 'prj' not in local_dict:
        print('creating BAG project')
        bprj = BPG.PhotonicBagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    spec_file = 'BPG/tests/specs/path_test_specs.yaml'
    PLM = BPG.PhotonicLayoutManager(bprj, spec_file)
    PLM.generate_gds()
    # PLM.generate_lsf()
    # PLM.generate_flat_gds(debug=True, generate_gds=True)
    # PLM.dataprep(debug=True)
