import BPG
from BPG.objects import PhotonicRound
from bag.layout.objects import BBox
import numpy as np

from typing import Tuple, Union


class DataprepShapes(BPG.PhotonicTemplateBase):
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
            layerA='',
            layerB='',
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
        )

    def draw_layout(self):
        self.add_round(
            PhotonicRound(
                layer=self.params['layerA'],
                resolution=self.grid.resolution,
                rout=1,
                center=(0, 0),
                rin=0,
                unit_mode=False,
            )
        )

        self.add_rect(
            layer=self.params['layerB'],
            coord1=(0.5, 0.25),
            coord2=(2, 3),
            unit_mode=False,
        )


class ParallelRects(BPG.PhotonicTemplateBase):
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
        # Add the DataprepShapes in multiple places, and add labels

        spx = 10
        label_list = ['add', 'sub', 'xor', 'and', 'rad', ]

        for i, el in enumerate(label_list):
            shapes_master = self.new_template(temp_cls=DataprepShapes,
                                              params=dict(
                                                  layerA=(f'layerA_{el}', 'drawing'),
                                                  layerB=(f'layerB_{el}', 'drawing'))
                                              )

            self.add_instance(
                master=shapes_master,
                loc=(spx * i, 0),
                orient='R0',
                unit_mode=False,
            )

            self.add_label(
                label=el,
                layer=('text', 'drawing'),
                bbox=BBox(
                    left=spx * i,
                    bottom=5,
                    right=spx * i + 0.001,
                    top=5.001,
                    resolution=self.grid.resolution,
                    unit_mode=False,
                )
            )

        self.add_label(
            label='Circle is on layerA_op. Rectangle is on layerB_op.  Dataprep does B (+/-/xor/and) A',
            layer=('text', 'drawing'),
            bbox=BBox(
                left=0,
                bottom=-5,
                right=0.001,
                top=-4.999,
                resolution=self.grid.resolution,
                unit_mode=False,
            )
        )


class MinWidthSpace(BPG.PhotonicTemplateBase):
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
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
        )

    def make_label(self,
                   loc: Tuple[Union[float, int], Union[float, int]],
                   string: str,
                   unit_mode: bool = False,
                   ) -> None:
        self.add_label(
            label=string,
            layer=('text', 'drawing'),
            bbox=BBox(
                left=loc[0],
                bottom=loc[1],
                right=loc[0] + 0.001,
                top=loc[1] + 0.001,
                resolution=self.grid.resolution,
                unit_mode=unit_mode,
            )
        )

    def draw_layout(self):
        """
        Min space OUO check:

        Add non-min-width rectangles separated by different gaps,
            - below min space
            - min space
            - above min space
        Visually confirm that below min space have merged, but at and above min space have not



        Min width OUO check:

        Add a rectangle with different widths
            - below min width
            - min width
            - above min width
        Visually confirm that below min width has disappeared, but at and above have not

        """
        min_width = self.photonic_tech_info.min_width(layer='M1')
        min_space = self.photonic_tech_info.min_space(layer='M1')
        res = self.grid.resolution
        min_width_unit = int(round(min_width / res))
        min_space_unit = int(round(min_space / res))

        min_width_label_loc = 0

        self.make_label(loc=(min_width_label_loc, 100),
                        string=f'Min width tests. min_width = {min_width}',
                        )

        min_width_unit_list = range(min_width_unit - 2, min_width_unit + 3)

        y_start = 90
        delta_y = -10

        for ind, width in enumerate(min_width_unit_list):
            y = (y_start + ind * delta_y) / res
            self.add_rect(
                layer=('M1', 'drawing'),
                x_span=1000,
                y_span=width,
                center=(min_width_label_loc / res, y),
                unit_mode=True
            )
            self.make_label(
                loc=(min_width_label_loc / res, y + 300),
                string=f'width = {width}. rectangle {"SHOULD" if width >= min_width_unit else "SHOULD NOT"} be here',
                unit_mode=True
            )

        min_space_label_loc = 30
        self.make_label(loc=(min_space_label_loc, 100),
                        string=f'Min space tests. min_space = {min_space}',
                        )

        min_space_unit_list = range(min_space_unit - 2, min_space_unit + 3)

        for ind, space in enumerate(min_space_unit_list):
            y = (y_start + ind * delta_y) / res
            self.add_rect(
                layer=('M1', 'drawing'),
                coord1=(min_space_label_loc / res, y),
                coord2=((min_space_label_loc + 1) / res, y + min_width_unit + 10),
                unit_mode=True
            )
            self.add_rect(
                layer=('M1', 'drawing'),
                coord1=(min_space_label_loc / res, y - space),
                coord2=((min_space_label_loc + 1) / res, y - space - (min_width_unit + 10)),
                unit_mode=True
            )

            self.make_label(
                loc=(min_space_label_loc / res, y + 300),
                string=f'space = {space}. rectangle {"SHOULD" if space < min_space_unit else "SHOULD NOT"} be merged',
                unit_mode=True
            )


def test_dataprep():
    spec_file = 'BPG/tests/specs/dataprep_specs_width_space.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)

    plm.generate_content()
    plm.generate_gds()
    plm.generate_flat_content()
    plm.generate_flat_gds()

    plm.dataprep()
    plm.generate_dataprep_gds()


if __name__ == '__main__':
    test_dataprep()




