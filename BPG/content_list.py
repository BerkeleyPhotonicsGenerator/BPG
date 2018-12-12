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

from .objects import PhotonicRect, PhotonicPolygon, PhotonicRound, PhotonicVia, PhotonicBlockage, PhotonicBoundary, \
    PhotonicPath, PhotonicPinInfo

from typing import TYPE_CHECKING, Union, Dict, Any, List, Set, \
    Optional, Tuple, Iterable, Sequence

if TYPE_CHECKING:
    pass


class ContentList():
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
        '''
        Copies the shape lists. Does not copy the inst_list (ie the new object will point to the original instance list)

        Returns
        -------

        '''
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

    def layout_objects(self):
        pass

    def to_json(self):
        pass

    def fill_content(self,
                     cell_name=None,
                     ):
        # Do I overwrite
        pass

    def transform_content(self,
                          res,
                          loc,
                          orient,
                          via_info,
                          unit_mode,
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
