import time
import logging
import yaml
import gdspy

from BPG.content_list import ContentList
from BPG.abstract_plugin import AbstractPlugin
from BPG.objects import PhotonicRound

from typing import TYPE_CHECKING, List, Optional
if TYPE_CHECKING:
    from bag.layout.objects import ViaInfo, PinInfo, InstanceInfo


class GDSPlugin(AbstractPlugin):
    def __init__(self,
                 grid,
                 gds_layermap,
                 gds_filepath,
                 lib_name,
                 max_points_per_polygon: int = 199
                 ):
        self.grid = grid
        self.gds_layermap = gds_layermap
        self.gds_filepath = gds_filepath
        self.lib_name = lib_name
        self.max_points_per_polygon = max_points_per_polygon

        with open(self.gds_layermap, 'r') as f:
            lay_info = yaml.load(f, Loader=yaml.CFullLoader if yaml.__with_libyaml__ else yaml.FullLoader)
            self.lay_map = lay_info['layer_map']
            self.via_info = lay_info['via_info']

    def export_content_list(self,
                            content_lists: List["ContentList"],
                            name_append: str = '',
                            max_points_per_polygon: Optional[int] = None,
                            write_gds: bool = True,
                            ):
        """
        Exports the physical design to GDS

        Parameters
        ----------
        content_lists : List[ContentList]
            A list of ContentList objects that represent the layout.
        name_append : str
            A suffix to add to the end of the generated gds filename
        max_points_per_polygon : Optional[int]
            Maximum number of points allowed per polygon shape in the gds.
            Defaults to value set in the init of GDSPlugin if not specified.
        write_gds : bool
            Default True.  True to write out the gds file.
            False to create the gdspy object, but not write out the gds.

        """
        logging.info(f'In GDSPlugin.export_content_list')

        tech_info = self.grid.tech_info
        lay_unit = tech_info.layout_unit
        res = tech_info.resolution

        if not max_points_per_polygon:
            max_points_per_polygon = self.max_points_per_polygon

        # TODO: fix
        out_fname = self.gds_filepath + f'{name_append}.gds'
        gds_lib = gdspy.GdsLibrary(name=self.lib_name, unit=lay_unit, precision=res * lay_unit)
        cell_dict = gds_lib.cell_dict
        logging.info(f'Instantiating gds layout')

        start = time.time()
        for content_list in content_lists:
            gds_cell = gdspy.Cell(content_list.cell_name, exclude_from_current=True)
            gds_lib.add(gds_cell)

            # add instances
            for inst_info in content_list.inst_list:  # type: InstanceInfo
                if inst_info.params is not None:
                    raise ValueError('Cannot instantiate PCells in GDS.')
                num_rows = inst_info.num_rows
                num_cols = inst_info.num_cols
                angle, reflect = inst_info.angle_reflect
                if num_rows > 1 or num_cols > 1:
                    cur_inst = gdspy.CellArray(cell_dict[inst_info.cell], num_cols, num_rows,
                                               (inst_info.sp_cols, inst_info.sp_rows),
                                               origin=inst_info.loc, rotation=angle,
                                               x_reflection=reflect)
                else:
                    cur_inst = gdspy.CellReference(cell_dict[inst_info.cell], origin=inst_info.loc,
                                                   rotation=angle, x_reflection=reflect)
                gds_cell.add(cur_inst)

            # add rectangles
            for rect in content_list.rect_list:
                nx, ny = rect.get('arr_nx', 1), rect.get('arr_ny', 1)
                (x0, y0), (x1, y1) = rect['bbox']
                lay_id, purp_id = self.lay_map[tuple(rect['layer'])]

                if nx > 1 or ny > 1:
                    spx, spy = rect['arr_spx'], rect['arr_spy']
                    for xidx in range(nx):
                        dx = xidx * spx
                        for yidx in range(ny):
                            dy = yidx * spy
                            cur_rect = gdspy.Rectangle((x0 + dx, y0 + dy), (x1 + dx, y1 + dy),
                                                       layer=lay_id, datatype=purp_id)
                            gds_cell.add(cur_rect)
                else:
                    cur_rect = gdspy.Rectangle((x0, y0), (x1, y1), layer=lay_id, datatype=purp_id)
                    gds_cell.add(cur_rect)

            # add vias
            for via in content_list.via_list:  # type: ViaInfo
                via_lay_info = self.via_info[via.id]

                nx, ny = via.arr_nx, via.arr_ny
                x0, y0 = via.loc
                if nx > 1 or ny > 1:
                    spx, spy = via.arr_spx, via.arr_spy
                    for xidx in range(nx):
                        xc = x0 + xidx * spx
                        for yidx in range(ny):
                            yc = y0 + yidx * spy
                            self._add_gds_via(gds_cell, via, self.lay_map, via_lay_info, xc, yc)
                else:
                    self._add_gds_via(gds_cell, via, self.lay_map, via_lay_info, x0, y0)

            # add pins
            for pin in content_list.pin_list:  # type: PinInfo
                lay_id, purp_id = self.lay_map[pin.layer]
                bbox = pin.bbox
                label = pin.label
                if pin.make_rect:
                    cur_rect = gdspy.Rectangle((bbox.left, bbox.bottom), (bbox.right, bbox.top),
                                               layer=lay_id, datatype=purp_id)
                    gds_cell.add(cur_rect)
                angle = 90 if bbox.height_unit > bbox.width_unit else 0
                cur_lbl = gdspy.Label(label, (bbox.xc, bbox.yc), rotation=angle,
                                      layer=lay_id, texttype=purp_id)
                gds_cell.add(cur_lbl)

            for path in content_list.path_list:
                # Photonic paths should be treated like polygons
                lay_id, purp_id = self.lay_map[path['layer']]
                cur_path = gdspy.Polygon(path['polygon_points'], layer=lay_id, datatype=purp_id)
                gds_cell.add(cur_path.fracture(precision=res, max_points=max_points_per_polygon))

            for blockage in content_list.blockage_list:
                pass

            for boundary in content_list.boundary_list:
                pass

            for polygon in content_list.polygon_list:
                lay_id, purp_id = self.lay_map[polygon['layer']]
                cur_poly = gdspy.Polygon(polygon['points'], layer=lay_id, datatype=purp_id)
                gds_cell.add(cur_poly.fracture(precision=res, max_points=max_points_per_polygon))

            for round_obj in content_list.round_list:
                nx, ny = round_obj.get('arr_nx', 1), round_obj.get('arr_ny', 1)
                lay_id, purp_id = self.lay_map[tuple(round_obj['layer'])]

                list_of_polygon_points, _ = PhotonicRound.polygon_pointlist_export(
                    rout=round_obj['rout'],
                    rin=round_obj['rin'],
                    theta0=round_obj['theta0'],
                    theta1=round_obj['theta1'],
                    center=round_obj['center'],
                    nx=nx,
                    ny=ny,
                    spx=round_obj.get('arr_spx', 0),
                    spy=round_obj.get('arr_spy', 0),
                    resolution=self.grid.resolution
                )
                for poly_points in list_of_polygon_points:
                    cur_poly = gdspy.Polygon(poly_points, layer=lay_id, datatype=purp_id)
                    gds_cell.add(cur_poly.fracture(precision=res, max_points=max_points_per_polygon))

        if write_gds:
            gds_lib.write_gds(out_fname)

        end = time.time()
        logging.info(f'Layout gds instantiation took {end - start:.4g}s')

        return gds_lib

    def _add_gds_via(self, gds_cell, via, lay_map, via_lay_info, x0, y0):
        blay, bpurp = lay_map[via_lay_info['bot_layer']]
        tlay, tpurp = lay_map[via_lay_info['top_layer']]
        vlay, vpurp = lay_map[via_lay_info['via_layer']]
        cw, ch = via.cut_width, via.cut_height
        if cw < 0:
            cw = via_lay_info['cut_width']
        if ch < 0:
            ch = via_lay_info['cut_height']

        num_cols, num_rows = via.num_cols, via.num_rows
        sp_cols, sp_rows = via.sp_cols, via.sp_rows
        w_arr = num_cols * cw + (num_cols - 1) * sp_cols
        h_arr = num_rows * ch + (num_rows - 1) * sp_rows

        x0 -= w_arr / 2
        y0 -= h_arr / 2
        # If the via array is odd dimension, prevent off-grid points
        if int(round(w_arr / self.grid.resolution)) % 2 == 1:
            x0 -= 0.5 * self.grid.resolution
        if int(round(h_arr / self.grid.resolution)) % 2 == 1:
            y0 -= 0.5 * self.grid.resolution

        bl, br, bt, bb = via.enc1
        tl, tr, tt, tb = via.enc2
        bot_p0, bot_p1 = (x0 - bl, y0 - bb), (x0 + w_arr + br, y0 + h_arr + bt)
        top_p0, top_p1 = (x0 - tl, y0 - tb), (x0 + w_arr + tr, y0 + h_arr + tt)

        cur_rect = gdspy.Rectangle(bot_p0, bot_p1, layer=blay, datatype=bpurp)
        gds_cell.add(cur_rect)
        cur_rect = gdspy.Rectangle(top_p0, top_p1, layer=tlay, datatype=tpurp)
        gds_cell.add(cur_rect)

        for xidx in range(num_cols):
            dx = xidx * (cw + sp_cols)
            for yidx in range(num_rows):
                dy = yidx * (ch + sp_rows)
                cur_rect = gdspy.Rectangle((x0 + dx, y0 + dy), (x0 + cw + dx, y0 + ch + dy),
                                           layer=vlay, datatype=vpurp)
                gds_cell.add(cur_rect)

    def import_content_list(self,
                            gds_filepath: str
                            ) -> ContentList:
        """
        Import a GDS and convert it to content list format.

        gdspy turns all input shapes into polygons, so we only need to care about importing into
        the polygon list. Currently we only import labels at the top level of the hierarchy

        Parameters
        ----------
        gds_filepath : str
            Path to the gds to be imported
        """

        from BPG.gds.io import GDSImport

        return GDSImport.import_content_from_gds_gdspy(gds_filepath,
                                                       reverse_lookup=GDSImport.create_reverse_lookup(self.lay_map),
                                                       lay_map=self.lay_map,
                                                       layout_cls=None,
                                                       res=self.grid.resolution)
