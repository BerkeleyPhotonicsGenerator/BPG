# -*- coding: utf-8 -*-

"""
This module defines the content list object that is used in db.
"""
from collections import UserDict

from BPG.objects import PhotonicRect, PhotonicPolygon, PhotonicRound, PhotonicBlockage, PhotonicBoundary, \
    PhotonicPath, PhotonicPinInfo

from typing import TYPE_CHECKING, Dict, List, Tuple, Any
from BPG.bpg_custom_types import coord_type, dim_type, lpp_type

if TYPE_CHECKING:
    from BPG.objects import PhotonicViaInfo


class ContentList(UserDict):
    layout_objects_keys = (
        'rect_list', 'via_list', 'pin_list', 'path_list', 'blockage_list', 'boundary_list',
        'polygon_list', 'round_list', 'sim_list', 'source_list', 'monitor_list'
    )
    all_iterables_keys = ('inst_list',) + layout_objects_keys

    def __init__(self,
                 cell_name: str = '',
                 **kwargs: Any,
                 ) -> None:
        # Check that the kwargs are valid. If not, raise an error
        for key in kwargs:
            if key not in self.all_iterables_keys:
                raise ValueError(f'Unknown ContentList key: {key}')

        # If key is not specified, content list should have an empty list, not None
        kv_iter = ((key, kwargs.get(key, [])) for key in self.all_iterables_keys)
        UserDict.__init__(self, kv_iter)
        self.data['cell_name'] = cell_name

    def __repr__(self):
        return f'ContentList for cell_name={self.cell_name}'

    # TODO: Fill in type info? This is tough because they are all lists of content info
    @property
    def inst_list(self) -> List:
        return self['inst_list']

    @property
    def rect_list(self) -> List:
        return self['rect_list']

    @property
    def via_list(self) -> List:
        return self['via_list']

    @property
    def pin_list(self) -> List:
        return self['pin_list']

    @property
    def path_list(self) -> List:
        return self['path_list']

    @property
    def blockage_list(self) -> List:
        return self['blockage_list']

    @property
    def boundary_list(self) -> List:
        return self['boundary_list']

    @property
    def polygon_list(self) -> List:
        return self['polygon_list']

    @property
    def round_list(self) -> List:
        return self['round_list']

    @property
    def sim_list(self) -> List:
        return self['sim_list']

    @property
    def source_list(self) -> List:
        return self['source_list']

    @property
    def monitor_list(self) -> List:
        return self['monitor_list']

    @property
    def cell_name(self) -> 'str':
        return self['cell_name']

    def copy(self):
        """
        Copies the shape lists.
        Does not copy the inst_list (ie the new object will point to the original instance list)

        Returns
        -------

        """
        return ContentList(
            cell_name=self.cell_name,
            inst_list=self.inst_list,   # Do not copy inst list
            **{key: self[key].copy() for key in self.layout_objects_keys}   # Copy the layout objects
        )

    def to_bag_tuple_format(self) -> Tuple:
        """
        Returns the BAG tuple format of the ContentList

        Returns
        -------
        content_tuple : Tuple
            The content of the ContentList object in the BAG tuple format
        """
        return (self.cell_name,) + tuple(self[key] for key in self.all_iterables_keys)

    # TODO: Change this to be content based, and change dataprep as well
    # TODO: Speed this up using yields or something similar if this is found to be slow
    def sort_content_list_by_layers(self) -> Dict[lpp_type, "ContentList"]:
        """
        Sorts the given content list into a dictionary of content lists, with keys corresponding to a given lpp
        ASSUMES: the current content list is flat with no via objects

        Notes
        -----
        1) Unpack the content list
        2) Loop over objects in the content list, ignoring vias
        3) Create new layer dictionary key if object layer is new, and whose value is a content list style array
        4) Append object to proper location in the per-layer content list array

        Returns
        -------

        """
        sorted_content: Dict[lpp_type, "ContentList"] = {}

        # Loop over the layout objects in the ContentList
        for object_type in self.layout_objects_keys:
            # Ignore vias
            if object_type != 'via_list':
                # For each item, ie each rect, polygon, etc
                object_list = self[object_type]
                for content_item in object_list:
                    layer = tuple(content_item['layer'])
                    # If the layer has not yet been used
                    if layer not in sorted_content.keys():
                        # Make a new ContentList for it
                        sorted_content[layer] = ContentList()

                    # Add the object to the layer's ContentList
                    sorted_content[layer].add_item(object_type, content_item)
        return sorted_content

    def get_content_by_layer(self,
                             layer: lpp_type,
                             ) -> "ContentList":
        """
        Return all the shapes in this content list that are on the passed layer.
        Does not look at instances. Does not via objects.

        Parameters
        ----------
        layer : Tuple[str, str]
            The layer purpose pair on which the content of this ContentList will be returned.

        Returns
        -------
        layer_content : ContentList
            The content of this ContentList that is on the passed layer.
        """
        layer_content = ContentList()
        for object_type in self.layout_objects_keys:
            # Ignore vias
            if object_type != 'via_list':
                # For each item, ie each rect, polygon, etc
                object_list = self[object_type]
                for content_item in object_list:
                    if tuple(content_item['layer']) == layer:
                        layer_content.add_item(object_type, content_item)
        return layer_content

    def add_item(self,
                 key: str,
                 value: Any,
                 ):
        """
        Given a content item and which content type it is, add it to the current ContentList

        Parameters
        ----------
        key : str
            key corresponding to the content type (rect_list, via_list, etc)
            key must be in ContentList.all_iterable_keys
        value : Any
            The content item of the given key type to add to the key list in the current ContentList

        Returns
        -------

        """
        if key not in self.all_iterables_keys:
            raise ValueError(f'Unknown ContentList key: {key}')
        self[key].append(value)

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
        for key in self.layout_objects_keys:
            self[key].extend(new_content[key])

    def transform_content(self,
                          res: float,
                          loc: coord_type,
                          orient: str,
                          via_info: Dict,
                          unit_mode: bool,
                          ) -> "ContentList":
        """
        Transforms the layout content (does not transform the sub-instances) of the current ContentList by the loc and
        orient passed.

        Parameters
        ----------
        res : float
            The grid resolution.
        loc : Tuple[Union[float, int], Union[float, int]]
            The (x, y) tuple describing the translation vector for the transformation.
        orient : str
            The orientation string describing how the layout should be rotated.
        via_info : Dict
            A dictionary containing the via technology properties
        unit_mode : bool
            True if loc is provided in resolution unit coordinates. False if in layout unit coordinates.

        Returns
        -------
        new_content_list : ContentList
            The new ContentList object with the transformed shapes.
        """
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
                                  via_info: Dict,
                                  ):
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
        # Delete the current via content objects
        self['via_list'] = []

    @staticmethod
    def via_to_polygon_list(via: "PhotonicViaInfo",
                            via_lay_info: Dict,
                            x0: dim_type,
                            y0: dim_type,
                            ) -> List:
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
