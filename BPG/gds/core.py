import time
import logging
import yaml
import gdspy
from math import pi

from BPG.abstract_plugin import AbstractPlugin
from BPG.objects import *


class GDSPlugin(AbstractPlugin):
    def __init__(self, config):
        AbstractPlugin.__init__(self, config)
        self.config = config
        self.grid = self.config['grid']
        self.gds_layermap = self.config['gds_layermap']
        self.gds_filepath = self.config['gds_filepath']
        self.lib_name = config['lib_name']

    def export_content_list(self, content_list, **kwargs):
        """
        Exports the physical design into the lumerical LSF format

        Parameters
        ----------
        content_list
            A flattened content list that has already been run through lumerical dataprep
        """
        logging.info(f'In PhotonicTemplateDB._create_gds')

        tech_info = self.grid.tech_info
        lay_unit = tech_info.layout_unit
        res = tech_info.resolution

        with open(self.gds_layermap, 'r') as f:
            lay_info = yaml.load(f)
            lay_map = lay_info['layer_map']
            via_info = lay_info['via_info']

        out_fname = self.gds_filepath + '%s.gds' % self.lib_name
        gds_lib = gdspy.GdsLibrary(name=self.lib_name)
        cell_dict = gds_lib.cell_dict
        logging.info(f'Instantiating gds layout')

        start = time.time()
        for content in content_list:
            (cell_name, inst_tot_list, rect_list, via_list, pin_list,
             path_list, blockage_list, boundary_list, polygon_list, round_list,
             sim_list, source_list, monitor_list) = content
            gds_cell = gdspy.Cell(cell_name, exclude_from_current=True)
            gds_lib.add(gds_cell)

            # add instances
            for inst_info in inst_tot_list:  # type: InstanceInfo
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
            for rect in rect_list:
                nx, ny = rect.get('arr_nx', 1), rect.get('arr_ny', 1)
                (x0, y0), (x1, y1) = rect['bbox']
                lay_id, purp_id = lay_map[tuple(rect['layer'])]

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
            for via in via_list:  # type: ViaInfo
                via_lay_info = via_info[via.id]

                nx, ny = via.arr_nx, via.arr_ny
                x0, y0 = via.loc
                if nx > 1 or ny > 1:
                    spx, spy = via.arr_spx, via.arr_spy
                    for xidx in range(nx):
                        xc = x0 + xidx * spx
                        for yidx in range(ny):
                            yc = y0 + yidx * spy
                            self._add_gds_via(gds_cell, via, lay_map, via_lay_info, xc, yc)
                else:
                    self._add_gds_via(gds_cell, via, lay_map, via_lay_info, x0, y0)

            # add pins
            for pin in pin_list:  # type: PinInfo
                lay_id, purp_id = lay_map[pin.layer]
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

            for path in path_list:
                # Photonic paths should be treated like polygons
                lay_id, purp_id = lay_map[path['layer']]
                cur_path = gdspy.Polygon(path['polygon_points'], layer=lay_id, datatype=purp_id,
                                         verbose=False)
                gds_cell.add(cur_path.fracture(precision=res))

            for blockage in blockage_list:
                pass

            for boundary in boundary_list:
                pass

            for polygon in polygon_list:
                lay_id, purp_id = lay_map[polygon['layer']]
                cur_poly = gdspy.Polygon(polygon['points'], layer=lay_id, datatype=purp_id,
                                         verbose=False)
                gds_cell.add(cur_poly.fracture(precision=res))

            for round_obj in round_list:
                nx, ny = round_obj.get('arr_nx', 1), round_obj.get('arr_ny', 1)
                lay_id, purp_id = lay_map[tuple(round_obj['layer'])]
                x0, y0 = round_obj['center']

                if nx > 1 or ny > 1:
                    spx, spy = round_obj['arr_spx'], round_obj['arr_spy']
                    for xidx in range(nx):
                        dx = xidx * spx
                        for yidx in range(ny):
                            dy = yidx * spy
                            cur_round = gdspy.Round((x0 + dx, y0 + dy), radius=round_obj['rout'],
                                                    inner_radius=round_obj['rin'],
                                                    initial_angle=round_obj['theta0'] * pi / 180,
                                                    final_angle=round_obj['theta1'] * pi / 180,
                                                    number_of_points=self.grid.resolution,
                                                    layer=lay_id, datatype=purp_id)
                            gds_cell.add(cur_round)
                else:
                    cur_round = gdspy.Round((x0, y0), radius=round_obj['rout'],
                                            inner_radius=round_obj['rin'],
                                            initial_angle=round_obj['theta0'] * pi / 180,
                                            final_angle=round_obj['theta1'] * pi / 180,
                                            number_of_points=self.grid.resolution,
                                            layer=lay_id, datatype=purp_id)
                    gds_cell.add(cur_round)

        gds_lib.write_gds(out_fname, unit=lay_unit, precision=res * lay_unit)

        end = time.time()
        logging.info(f'Layout gds instantiation took {end - start:.4g}s')

    @staticmethod
    def _add_gds_via(gds_cell, via, lay_map, via_lay_info, x0, y0):
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
