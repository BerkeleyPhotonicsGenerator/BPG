# -*- coding: utf-8 -*-

"""
This module defines the content list object that is used in db.
"""

import os
import abc
import numpy as np
import yaml
import time
import logging

from BPG.objects import PhotonicRect, PhotonicPolygon, PhotonicRound, PhotonicVia, PhotonicBlockage, PhotonicBoundary, \
    PhotonicPath, PhotonicPinInfo

from typing import TYPE_CHECKING, Dict, List, Tuple
from BPG.bpg_custom_types import coord_type, dim_type, layer_type

if TYPE_CHECKING:
    pass


class ContentList(dict):
    layout_objects_list = [
        'rect_list', 'via_list', 'pin_list', 'path_list', 'blockage_list', 'boundary_list',
        'polygon_list', 'round_list', 'sim_list', 'source_list', 'monitor_list'
    ]
    all_iterables_list = ['inst_list'] + layout_objects_list
    def __init__(self,
                 cell_name: str = '',
                 inst_list: List = None,
                 rect_list: List = None,
                 via_list: List = None,
                 pin_list: List = None,
                 path_list: List = None,
                 blockage_list: List = None,
                 boundary_list: List = None,
                 polygon_list: List = None,
                 round_list: List = None,
                 sim_list: List = None,
                 source_list: List = None,
                 monitor_list: List = None,
                 ) -> None:
        self.cell_name = cell_name
        self.inst_list = [] if inst_list is None else inst_list
        self.rect_list = [] if rect_list is None else rect_list
        self.via_list = [] if via_list is None else via_list
        self.pin_list = [] if pin_list is None else pin_list
        self.path_list = [] if path_list is None else path_list
        self.blockage_list = [] if blockage_list is None else blockage_list
        self.boundary_list = [] if boundary_list is None else boundary_list
        self.polygon_list = [] if polygon_list is None else polygon_list
        self.round_list = [] if round_list is None else round_list
        self.sim_list = [] if sim_list is None else sim_list
        self.source_list = [] if source_list is None else source_list
        self.monitor_list = [] if monitor_list is None else monitor_list

    def copy(self):
        """
        Copies the shape lists.
        Does not copy the inst_list (ie the new object will point to the original instance list)

        Returns
        -------

        """
        return ContentList(
            cell_name=self.cell_name,
            inst_list=self.inst_list,
            rect_list=self.rect_list.copy(),
            via_list=self.via_list.copy(),
            pin_list=self.pin_list.copy(),
            path_list=self.path_list.copy(),
            blockage_list=self.blockage_list.copy(),
            boundary_list=self.boundary_list.copy(),
            polygon_list=self.polygon_list.copy(),
            round_list=self.round_list.copy(),
            sim_list=self.sim_list.copy(),
            source_list=self.source_list.copy(),
            monitor_list=self.monitor_list.copy()
        )

    def copy_layout_shapes(self):
        """
        Copies only the shapes, not the instances, of the passed content list.

        Returns
        -------

        """
        new_copy = self.copy()
        new_copy.inst_list = []
        return new_copy

    def to_bag_tuple_format(self) -> Tuple:
        """
        Returns the BAG tuple format of the ContentList

        Returns
        -------
        content_tuple : Tuple
            The content of the ContentList object in the BAG tuple format
        """
        return (
            self.cell_name, self.inst_list, self.rect_list, self.via_list, self.pin_list, self.path_list,
            self.blockage_list, self.boundary_list, self.polygon_list, self.round_list,
            self.sim_list, self.source_list, self.monitor_list
        )

    # TODO: Change this to be content based, and change dataprep as well
    def sort_content_list_by_layers(self) -> Dict[layer_type, "ContentList"]:
        """
        Sorts the given content list into a dictionary of content lists, with keys corresponding to a given lpp

        Notes
        -----
        1) Unpack the content list
        2) Loop over objects in the content list, ignoring vias
        3) Create new layer dictionary key if object layer is new, and whose value is a content list style array
        4) Append object to proper location in the per-layer content list array

        Returns
        -------

        """
        sorted_content = {}
        for

    def extend_content_list(self,
                            new_content: "ContentList",
                            ) -> None:
        """
        Extends the current ContentList object's layout shapes with those of the passed new_content ContentList.
        Does not extend the instances.

        Parameters
        ----------
        new_content

        Returns
        -------

        """
        self.rect_list.extend(new_content.rect_list)
        self.via_list.extend(new_content.via_list)
        self.pin_list.extend(new_content.pin_list)
        self.path_list.extend(new_content.path_list)
        self.blockage_list.extend(new_content.blockage_list)
        self.boundary_list.extend(new_content.boundary_list)
        self.polygon_list.extend(new_content.polygon_list)
        self.round_list.extend(new_content.round_list)
        self.sim_list.extend(new_content.sim_list)
        self.source_list.extend(new_content.source_list)
        self.monitor_list.extend(new_content.monitor_list)

    def transform_content(self,
                          res: float,
                          loc: coord_type,
                          orient: str,
                          via_info: Dict,
                          unit_mode: bool,
                          ):
        new_rect_list = []
        new_via_list = []  # via list which can not be handled by DataPrep
        new_pin_list = []
        new_path_list = []
        new_blockage_list = []
        new_boundary_list = []
        new_polygon_list = []
        new_round_list = []
        new_sim_list = []
        new_source_list = []
        new_monitor_list = []

        # add rectangles
        for rect in self.rect_list:
            new_rect_list.append(
                PhotonicRect.from_content(
                    content=rect,
                    resolution=res
                ).transform(
                    loc=loc,
                    orient=orient,
                    unit_mode=unit_mode,
                    copy=False
                ).content
            )

        # add vias
        for via in self.via_list:
            # Keep new via list empty
            # Add its component rectangles to the polygon list.
            via_lay_info = via_info[via.id]

            nx, ny = via.arr_nx, via.arr_ny
            x0, y0 = via.loc
            if nx > 1 or ny > 1:
                spx, spy = via.arr_spx, via.arr_spy
                for xidx in range(nx):
                    xc = x0 + xidx * spx
                    for yidx in range(ny):
                        yc = y0 + yidx * spy
                        self.polygon_list.extend(self.via_to_polygon_list(via, via_lay_info, xc, yc))
            else:
                self.polygon_list.extend(self.via_to_polygon_list(via, via_lay_info, x0, y0))

        # add pins
        for pin in self.pin_list:
            new_pin_list.append(
                PhotonicPinInfo.from_content(
                    content=pin,
                    resolution=res
                ).transform(
                    loc=loc,
                    orient=orient,
                    unit_mode=unit_mode,
                    copy=False
                )
            )

        for path in self.path_list:
            new_path_list.append(
                PhotonicPath.from_content(
                    content=path,
                    resolution=res
                ).transform(
                    loc=loc,
                    orient=orient,
                    unit_mode=unit_mode,
                    copy=False
                ).content
            )

        for blockage in self.blockage_list:
            new_blockage_list.append(
                PhotonicBlockage.from_content(
                    content=blockage,
                    resolution=res
                ).transform(
                    loc=loc,
                    orient=orient,
                    unit_mode=unit_mode,
                    copy=False
                ).content
            )

        for boundary in self.boundary_list:
            new_boundary_list.append(
                PhotonicBoundary.from_content(
                    content=boundary,
                    resolution=res
                ).transform(
                    loc=loc,
                    orient=orient,
                    unit_mode=unit_mode,
                    copy=False
                ).content
            )

        for polygon in self.polygon_list:
            new_polygon_list.append(
                PhotonicPolygon.from_content(
                    content=polygon,
                    resolution=res
                ).transform(
                    loc=loc,
                    orient=orient,
                    unit_mode=unit_mode,
                    copy=False
                ).content
            )

        for round_obj in self.round_list:
            new_round_list.append(
                PhotonicRound.from_content(
                    content=round_obj,
                    resolution=res
                ).transform(
                    loc=loc,
                    orient=orient,
                    unit_mode=unit_mode,
                    copy=False
                ).content
            )

        for sim in self.sim_list:
            new_sim_list.append(sim)

        for source in self.source_list:
            new_source_list.append(source)

        for monitor in self.monitor_list:
            new_monitor_list.append(monitor)

        return ContentList(
            cell_name='',
            inst_list=[],
            rect_list=new_rect_list,
            via_list=new_via_list,
            pin_list=new_pin_list,
            path_list=new_path_list,
            blockage_list=new_blockage_list,
            boundary_list=new_boundary_list,
            polygon_list=new_polygon_list,
            round_list=new_round_list,
            sim_list=new_sim_list,
            source_list=new_source_list,
            monitor_list=new_monitor_list,
        )

    def via_to_polygon_and_delete(self,
                                  via_info):
        for via in self.via_list:
            # Keep new via list empty, as we are adding its component rectangles to the polygon list.
            # new_via_list.append(
            #     PhotonicVia.from_content(
            #         content=via,
            #     ).transform(
            #         loc=loc,
            #         orient=orient,
            #         unit_mode=unit_mode,
            #         copy=False
            #     ).content
            # )

            via_lay_info = via_info[via.id]

            nx, ny = via.arr_nx, via.arr_ny
            x0, y0 = via.loc
            if nx > 1 or ny > 1:
                spx, spy = via.arr_spx, via.arr_spy
                for xidx in range(nx):
                    xc = x0 + xidx * spx
                    for yidx in range(ny):
                        yc = y0 + yidx * spy
                        self.polygon_list.extend(self.via_to_polygon_list(via, via_lay_info, xc, yc))
            else:
                self.polygon_list.extend(self.via_to_polygon_list(via, via_lay_info, x0, y0))

        self.via_list = []


    @staticmethod
    def via_to_polygon_list(via, via_lay_info, x0, y0):
        blay = via_lay_info['bot_layer']
        tlay = via_lay_info['top_layer']
        vlay = via_lay_info['via_layer']
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

        bot_left, bot_bot, bot_right, bot_top = x0 - bl, y0 - bb, x0 + w_arr + br, y0 + h_arr + bt
        top_left, top_bot, top_right, top_top = x0 - tl, y0 - tb, x0 + w_arr + tr, y0 + h_arr + tt

        bot_polygon = {
            'layer': blay,
            'points': [(bot_left, bot_bot), (bot_left, bot_top), (bot_right, bot_top), (bot_right, bot_bot)]
        }
        top_polygon = {
            'layer': tlay,
            'points': [(top_left, top_bot), (top_left, top_top), (top_right, top_top), (top_right, top_bot)]
        }

        polygon_list = [bot_polygon, top_polygon]

        for xidx in range(num_cols):
            dx = xidx * (cw + sp_cols)
            via_left, via_right = x0 + dx, x0 + cw + dx
            for yidx in range(num_rows):
                dy = yidx * (ch + sp_rows)
                via_bot, via_top = y0 + dy, y0 + ch + dy
                via_polygon = {
                    'layer': vlay,
                    'points': [(via_left, via_bot), (via_left, via_top), (via_right, via_top), (via_right, via_bot)]
                }
                polygon_list.append(via_polygon)

        return polygon_list
