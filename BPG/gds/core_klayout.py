import time
import logging
import yaml
import pya
import numpy as np

from bag.layout.util import BBox
from BPG.content_list import ContentList
from BPG.abstract_plugin import AbstractPlugin

from typing import TYPE_CHECKING, List, Tuple, Optional
if TYPE_CHECKING:
    from bag.layout.objects import ViaInfo, PinInfo, InstanceInfo


TRANSFORM_TABLE = {'R0': pya.Trans.R0,
                   'R90': pya.Trans.R90,
                   'R180': pya.Trans.R180,
                   'R270': pya.Trans.R270,
                   'MX': pya.Trans.M0,
                   'MY': pya.Trans.M90,
                   'MXR90': pya.Trans.M45,
                   'MYR90': pya.Trans.M135,
                   }


class KLayoutGDSPlugin(AbstractPlugin):
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
        logging.info(f'In PhotonicTemplateDB._create_gds')

        tech_info = self.grid.tech_info
        lay_unit = tech_info.layout_unit
        res = tech_info.resolution
        unit = 1 / res

        if not max_points_per_polygon:
            max_points_per_polygon = self.max_points_per_polygon

        with open(self.gds_layermap, 'r') as f:
            lay_info = yaml.load(f)
            lay_map = lay_info['layer_map']
            via_info = lay_info['via_info']

        out_fname = self.gds_filepath + f'{name_append}.gds'
        gds_lib = pya.Layout()
        cell_dict = dict()
        logging.info(f'Instantiating gds layout')

        start = time.time()
        for content_list in content_lists:
            # Create the cell in the gds library and in the cell dict
            gds_cell = gds_lib.create_cell(content_list.cell_name)
            cell_dict[content_list.cell_name] = gds_cell.cell_index()

            # add instances
            for inst_info in content_list.inst_list:  # type: InstanceInfo
                if inst_info.params is not None:
                    raise ValueError('Cannot instantiate PCells in GDS.')
                num_rows = inst_info.num_rows
                num_cols = inst_info.num_cols
                angle, reflect = inst_info.angle_reflect
                if num_rows > 1 or num_cols > 1:
                    gds_cell.insert(
                        pya.CellInstArray(cell_dict[inst_info.cell],
                                          pya.Trans(TRANSFORM_TABLE[inst_info.orient],
                                                    inst_info.loc[0] * unit,
                                                    inst_info.loc[1] * unit),
                                          pya.Vector(unit, 0),
                                          pya.Vector(0, unit),
                                          inst_info.sp_cols,
                                          inst_info.sp_rows,
                                          )
                    )
                else:
                    gds_cell.insert(
                        pya.CellInstArray(cell_dict[inst_info.cell],
                                          pya.Trans(TRANSFORM_TABLE[inst_info.orient],
                                                    inst_info.loc[0] * unit,
                                                    inst_info.loc[1] * unit),
                                          )
                    )

            # add rectangles
            for rect in content_list.rect_list:
                nx, ny = rect.get('arr_nx', 1), rect.get('arr_ny', 1)
                (x0, y0), (x1, y1) = rect['bbox']
                lay_id, purp_id = lay_map[tuple(rect['layer'])]

                if nx > 1 or ny > 1:
                    spx, spy = rect['arr_spx'], rect['arr_spy']
                    for xidx in range(nx):
                        dx = xidx * spx
                        for yidx in range(ny):
                            dy = yidx * spy

                            gds_cell.shapes(gds_lib.layer(lay_id, purp_id)).insert(
                                pya.Box((x0 + dx) * unit, (y0 + dy) * unit,
                                        (x1 + dx) * unit, (y1 + dy) * unit)
                            )
                else:
                    gds_cell.shapes(gds_lib.layer(lay_id, purp_id)).insert(
                        pya.Box(x0 * unit, y0 * unit,
                                x1 * unit, y1 * unit)
                    )

            # add vias
            for via in content_list.via_list:  # type: ViaInfo
                via_lay_info = via_info[via.id]

                nx, ny = via.arr_nx, via.arr_ny
                x0, y0 = via.loc
                if nx > 1 or ny > 1:
                    spx, spy = via.arr_spx, via.arr_spy
                    for xidx in range(nx):
                        xc = x0 + xidx * spx
                        for yidx in range(ny):
                            yc = y0 + yidx * spy
                            self._add_gds_via(gds_lib, gds_cell, via, lay_map, via_lay_info, xc, yc)
                else:
                    self._add_gds_via(gds_lib, gds_cell, via, lay_map, via_lay_info, x0, y0)

            # add pins
            for pin in content_list.pin_list:  # type: PinInfo
                lay_id, purp_id = lay_map[pin.layer]
                bbox = pin.bbox
                label = pin.label
                if pin.make_rect:
                    gds_cell.shapes(gds_lib.layer(lay_id, purp_id)).insert(
                        pya.Box(bbox.left_unit, bbox.bottom_unit,
                                bbox.right_unit, bbox.top_unit)
                    )
                angle = pya.Trans.R90 if bbox.height_unit > bbox.width_unit else pya.Trans.R0
                gds_cell.shapes(gds_lib.layer(lay_id, purp_id)).insert(
                    pya.Text(label, pya.Trans(angle, bbox.xc_unit, bbox.yc_unit))
                )

            for path in content_list.path_list:
                # Photonic paths should be treated like polygons
                lay_id, purp_id = lay_map[path['layer']]
                gds_cell.shapes(gds_lib.layer(lay_id, purp_id)).insert(
                    pya.Polygon([pya.Point(pt[0] * unit, pt[1] * unit) for pt in path['polygon_points']])
                )

            for blockage in content_list.blockage_list:
                pass

            for boundary in content_list.boundary_list:
                pass

            for polygon in content_list.polygon_list:
                lay_id, purp_id = lay_map[polygon['layer']]
                gds_cell.shapes(gds_lib.layer(lay_id, purp_id)).insert(
                    pya.Polygon([pya.Point(pt[0] * unit, pt[1] * unit) for pt in polygon['points']])
                )

            for round_obj in content_list.round_list:
                nx, ny = round_obj.get('arr_nx', 1), round_obj.get('arr_ny', 1)
                lay_id, purp_id = lay_map[tuple(round_obj['layer'])]
                x0, y0 = round_obj['center']

                if nx > 1 or ny > 1:
                    spx, spy = round_obj['arr_spx'], round_obj['arr_spy']
                    for xidx in range(nx):
                        dx = xidx * spx
                        for yidx in range(ny):
                            dy = yidx * spy

                            gds_cell.shapes(gds_lib.layer(lay_id, purp_id)).insert(
                                pya.Polygon([pya.Point(pt[0], pt[1])
                                             for pt in self._round_to_polygon_unit(x0+dx, y0+dy,
                                                                                   round_obj['rout'],
                                                                                   round_obj['rin'],
                                                                                   round_obj['theta0'],
                                                                                   round_obj['theta1'],
                                                                                   self.grid.resolution,
                                                                                   )])
                            )
                else:
                    gds_cell.shapes(gds_lib.layer(lay_id, purp_id)).insert(
                        pya.Polygon([pya.Point(pt[0], pt[1])
                                     for pt in self._round_to_polygon_unit(x0, y0,
                                                                           round_obj['rout'],
                                                                           round_obj['rin'],
                                                                           round_obj['theta0'],
                                                                           round_obj['theta1'],
                                                                           self.grid.resolution,
                                                                           )])
                    )

        if write_gds:
            gds_lib.write(out_fname)

        end = time.time()
        logging.info(f'Layout gds instantiation took {end - start:.4g}s')

        return gds_lib

    def _round_to_polygon_unit(self, x0, y0, radius, inner_radius, initial_angle, final_angle, tolerance):
        angles_same = np.isclose(np.mod(initial_angle, 360.0), np.mod(final_angle, 360.0))

        ang_rad = 2 * np.pi if angles_same else abs(np.deg2rad(final_angle - initial_angle))
        num_pts = max(3, 1 + int(0.5 * ang_rad / np.arccos(1 - tolerance / radius) + 0.5))

        if inner_radius <= 0:
            if angles_same:
                t = np.linspace(np.deg2rad(initial_angle), np.deg2rad(final_angle), num_pts, endpoint=False)
            else:
                t = np.linspace(np.deg2rad(initial_angle), np.deg2rad(final_angle), num_pts, endpoint=True)
            ptsx = np.cos(t) * radius + x0
            ptsy = np.sin(t) * radius + y0
        else:
            if angles_same:
                t = np.linspace(np.deg2rad(initial_angle), np.deg2rad(final_angle), num_pts, endpoint=False)
            else:
                t = np.linspace(np.deg2rad(initial_angle), np.deg2rad(final_angle), num_pts, endpoint=True)
            ptsx = np.cos(t) * radius + x0
            ptsy = np.sin(t) * radius + y0

            if angles_same:
                t = np.linspace(np.deg2rad(final_angle), np.deg2rad(initial_angle), num_pts, endpoint=False)
            else:
                t = np.linspace(np.deg2rad(final_angle), np.deg2rad(initial_angle), num_pts, endpoint=True)

            ptsx = np.concatenate(ptsx, np.cos(t) * inner_radius + x0)
            ptsy = np.concatenate(ptsy, np.sin(t) * inner_radius + x0)

        return [(int(round(px / self.grid.resolution)), int(round(py / self.grid.resolution)))
                for px, py in zip(ptsx, ptsy)]

    def _add_gds_via(self, gds_lib, gds_cell, via, lay_map, via_lay_info, x0, y0):
        unit = int(round(self.grid.resolution))
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
        # bot_p0, bot_p1 = (x0 - bl, y0 - bb), (x0 + w_arr + br, y0 + h_arr + bt)
        # top_p0, top_p1 = (x0 - tl, y0 - tb), (x0 + w_arr + tr, y0 + h_arr + tt)

        gds_cell.shapes(gds_lib.layer(blay, bpurp)).insert(
            pya.Box((x0 - bl) * unit, (y0 - bb) * unit,
                    (x0 + w_arr + br) * unit, (y0 + h_arr + bt) * unit)
        )
        gds_cell.shapes(gds_lib.layer(tlay, tpurp)).insert(
            pya.Box((x0 - tl) * unit, (y0 - tb) * unit,
                    (x0 + w_arr + tr) * unit, (y0 + h_arr + tt) * unit)
        )

        for xidx in range(num_cols):
            dx = xidx * (cw + sp_cols)
            for yidx in range(num_rows):
                dy = yidx * (ch + sp_rows)
                gds_cell.shapes(gds_lib.layer(vlay, vpurp)).insert(
                    pya.Box((x0 + dx) * unit, (y0 + dy) * unit,
                            (x0 + cw + dx) * unit, (y0 + ch + dy) * unit)
                )

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
        # Import information from the layermap
        with open(self.gds_layermap, 'r') as f:
            lay_info = yaml.load(f)
            lay_map = lay_info['layer_map']

        # Import the GDS from the file
        gds_lib = gdspy.GdsLibrary()
        gds_lib.read_gds(infile=gds_filepath)

        # Get the top cell in the GDS and flatten its contents
        # TODO: Currently we do not support importing GDS with multiple top cells
        top_cell = gds_lib.top_level()
        if len(top_cell) != 1:
            raise ValueError("Cannot import a GDS with multiple top level cells")
        top_cell = top_cell[0]
        top_cell.flatten()

        # Lists of components we will import from the GDS
        polygon_list = []
        pin_list = []

        for polyset in top_cell.polygons:
            for count in range(len(polyset.polygons)):
                points = polyset.polygons[count]
                layer = polyset.layers[count]
                datatype = polyset.datatypes[count]

                # Reverse lookup layername from gds LPP
                lpp = self.lpp_reverse_lookup(lay_map, gds_layerid=[layer, datatype])

                # Create the polygon from the provided data if the layer exists in the layermap
                if lpp:
                    content = dict(layer=lpp,
                                   points=points)
                    polygon_list.append(content)
        for label in top_cell.get_labels(depth=0):
            text = label.text
            layer = label.layer
            texttype = label.texttype
            position = label.position
            bbox = BBox(left=position[0] - self.grid.resolution,
                        bottom=position[1] - self.grid.resolution,
                        right=position[0] + self.grid.resolution,
                        top=position[1] + self.grid.resolution,
                        resolution=self.grid.resolution)

            # Reverse lookup layername from gds LPP
            lpp = self.lpp_reverse_lookup(lay_map, gds_layerid=[layer, texttype])

            # Create the label from the provided data if the layer exists in the layermap
            # TODO: Find the best way to generate a label in the content list
            if lpp:
                pass
                # self.add_label(label=text,
                #                layer=lpp,
                #                bbox=bbox)

        # After all of the components have been converted, dump into content list
        return ContentList(cell_name=top_cell.name,
                           polygon_list=polygon_list)

    @staticmethod
    def lpp_reverse_lookup(layermap: dict,
                           gds_layerid: List[int]
                           ) -> str:
        """
        Given a layermap dictionary, find the layername that matches the provided gds layer id

        Parameters
        ----------
        layermap : dict
            mapping from layer name to gds layer id
        gds_layerid : Tuple[int, int]
            gds layer id to find the layer name for

        Returns
        -------
        layername : str
            first layername that matches the provided gds layer id
        """
        for layer_name, layer_id in layermap.items():
            if layer_id == gds_layerid:
                return layer_name
        else:
            print(f"{gds_layerid} was not found in the layermap!")
