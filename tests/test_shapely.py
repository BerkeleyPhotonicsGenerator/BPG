"""
This file currently does not fit the standard automated test setup format...it will be ignored by pytest
"""

from matplotlib import pyplot
from shapely.geometry import LineString
# from descartes import PolygonPatch
from shapely.ops import cascaded_union
from shapely.ops import polygonize_full, polygonize
import BPG
from bag.layout.util import BBox


def plot_coords(ax, x, y, color='#999999', zorder=1):
    ax.plot(x, y, 'o', color=color, zorder=zorder)


def plot_line(ax, ob, color='r'):
    parts = hasattr(ob, 'geoms') and ob or [ob]
    for part in parts:
        x, y = part.xy
        ax.plot(x, y, color=color, linewidth=3, solid_capstyle='round', zorder=1)


def get_polygon(boundary_list):
    # this function cannot handle situations with islands in the hole
    boundary_list_shapely = []
    for sgboundary in boundary_list:
        boundary_list_shapely.append(sgboundary[0])
    polygon = cascaded_union(polygonize_full(boundary_list_shapely))
    return polygon


def get_polygon_sglayer(bdry_sglayer_list):
    # this function cannot handle situations with islands in the hole
    bdry_sglayer_list_shapely = []

    for bdry_sglayer in bdry_sglayer_list:
        print('bdry_sglayer', bdry_sglayer)
        # print(bdry_sglayer[0])
        if (bdry_sglayer):
            bdry_sglayer_list_shapely.append(bdry_sglayer[0])
    polygon = cascaded_union(polygonize_full(bdry_sglayer_list_shapely))
    return polygon


def get_polygon_mtlayer(bdry_mtlayer_list):
    polygon_list = []
    for bdry_sglayer_list in bdry_mtlayer_list:
        print(bdry_sglayer_list)
        # if bdry_sglayer_list:
        polygon = get_polygon_sglayer(bdry_sglayer_list)
        polygon_list.append(polygon)
    return polygon_list


def oversize(polygon, offset):
    # this function cannot handle situations with islands in the hole
    if (offset < 0):
        print('Warning: offset = %f < 0 indicates you are doing undersize')
    polygon_oversized = polygon.buffer(offset, cap_style=3, join_style=2)
    return polygon_oversized


def undersize(polygon, offset):
    # this function cannot handle situations with islands in the hole
    if (offset < 0):
        print('Warning: offset = %f < 0 indicates you are doing oversize')
    polygon_undersized = polygon.buffer(-offset, cap_style=3, join_style=2)
    return polygon_undersized


class AddRectTest(BPG.PhotonicTemplateBase):
    """ Class for generating rectangles for dataprep testing """
    def __init__(self, temp_db,
                 lib_name,
                 params,
                 used_names,
                 **kwargs,
                 ):
        BPG.PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_params_info(cls):
        return dict(
            x='Rectangle x span in microns',
            y='Rectangle y span in microns',
            center='Rectangle center coord',
            point1='Rectangle corner 1',
            point2='Rectangle corner 2',
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
        )

    def draw_layout(self):
        """ Specifies the creation of the lumerical shapes """

        r1 = self.add_rect(
            layer='Si',
            x_span=self.params['x'],
            y_span=self.params['y'],
            center=self.params['center'],
            unit_mode=False,
        )

        r2 = self.add_rect(
            layer='Si',
            coord1=self.params['point1'],
            coord2=self.params['point2'],
            unit_mode=False,
        )

        r3 = self.add_rect(
            layer='Si',
            bbox=BBox(
                left=1,
                bottom=-10,
                right=10,
                top=-7,
                resolution=self.grid.resolution,
                unit_mode=False
            ),
            unit_mode=False
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

    spec_file = './specs/add_rect_specs.yaml'
    # spec_file = '/tools/projects/ruocheng_wang/Photonics_Dev/BPG/tests/specs/add_rect_specs.yaml'
    PLM = BPG.PhotonicLayoutManager(bprj, spec_file)
    PLM.generate_gds()
    test = PLM.generate_polygon_point_list()
    print('PLM.generate_shapely', test)

    poly_list = get_polygon_mtlayer(test)
    poly_origin = poly_list[0]
    # poly_origin = get_polygon_sglayer(test[0])

    fig = pyplot.figure(1, dpi=90)

    offset = 1
    poly_oversize = oversize(poly_origin, offset)
    poly_undersize = undersize(poly_origin, offset)
    poly_oversize_undersize = undersize(poly_oversize, offset)
    poly_undersize_oversize = oversize(poly_undersize, offset)
    # 1
    ax = fig.add_subplot(231)
    plot_coords(ax, 0, 0)

    plot_line(ax, poly_origin.boundary, color='b')
    ax.add_patch(PolygonPatch(poly_origin.__geo_interface__, fc='b', ec='b', alpha=0.5, zorder=2))
    ax.set_title('1) original polygon')

    # 2
    ax = fig.add_subplot(232)
    plot_coords(ax, 0, 0)

    plot_line(ax, poly_undersize.boundary, color='b')
    ax.add_patch(PolygonPatch(poly_undersize.__geo_interface__, fc='b', ec='b', alpha=0.5, zorder=2))
    ax.set_title('2) undersized polygon')

    # 3
    ax = fig.add_subplot(233)
    plot_coords(ax, 0, 0)

    plot_line(ax, poly_oversize.boundary, color='b')
    ax.add_patch(PolygonPatch(poly_oversize.__geo_interface__, fc='b', ec='b', alpha=0.5, zorder=2))
    ax.set_title('3) oversized polygon')

    # 4
    ax = fig.add_subplot(235)
    plot_coords(ax, 0, 0)

    plot_line(ax, poly_undersize_oversize.boundary, color='b')
    ax.add_patch(PolygonPatch(poly_undersize_oversize.__geo_interface__, fc='b', ec='b', alpha=0.5, zorder=2))
    ax.set_title('4) undersized then oversized polygon')

    # 5
    ax = fig.add_subplot(236)
    plot_coords(ax, 0, 0)

    plot_line(ax, poly_oversize_undersize.boundary, color='b')
    ax.add_patch(PolygonPatch(poly_oversize_undersize.__geo_interface__, fc='b', ec='b', alpha=0.5, zorder=2))
    ax.set_title('5) oversized then undersized polygon')

    pyplot.show()
