import time
import logging
import yaml

from BPG.abstract_plugin import AbstractPlugin
from .code_generator import LumericalDesignGenerator
from BPG.lumerical.objects import PhotonicRect, PhotonicPolygon, PhotonicRound

from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from BPG.content_list import ContentList
    from pathlib import Path


class LumericalPlugin(AbstractPlugin):
    def __init__(self,
                 lsf_export_config,
                 ):
        self.lsf_export_config = lsf_export_config
        self.export_dir = None

    def export_content_list(self,
                            content_lists: List["ContentList"],
                            name_list: List[str] = None,
                            export_dir: "Path" = None,
                            ):
        """
        Exports the physical design into the lumerical LSF format

        Parameters
        ----------
        content_lists : List[ContentList]
            A list of flattened content lists that have already been run through lumerical dataprep
        name_list : List[str]
            A list of names to give to each generated lsf
        export_dir : Path
            The path in which the LSF files will be generated
        """

        if export_dir is None:
            raise ValueError(f'export_dir must be specified')
        self.export_dir = export_dir

        start = time.time()
        # 1) Import tech information for the layermap and lumerical properties
        with open(self.lsf_export_config, 'r') as f:
            lay_info = yaml.load(f)
            prop_map = lay_info['lumerical_prop_map']

        # 2) For each element in the content list, convert it into lsf code and append to running file
        for name, content_list in zip(name_list, content_lists):
            lsfwriter = LumericalDesignGenerator(str(self.export_dir / name))

            if len(content_list.rect_list) != 0:
                lsfwriter.add_formatted_line(' ')
                lsfwriter.add_formatted_line('#------------------ ')
                lsfwriter.add_formatted_line('# Adding Rectangles ')
                lsfwriter.add_formatted_line('#------------------ ')
            for rect in content_list.rect_list:
                nx, ny = rect.get('arr_nx', 1), rect.get('arr_ny', 1)
                if tuple(rect['layer']) in prop_map:
                    layer_prop = prop_map[tuple(rect['layer'])]
                    if nx > 1 or ny > 1:
                        lsf_repr = PhotonicRect.lsf_export(rect['bbox'], layer_prop, nx, ny,
                                                           spx=rect['arr_spx'], spy=rect['arr_spy'])
                    else:
                        lsf_repr = PhotonicRect.lsf_export(rect['bbox'], layer_prop)
                    lsfwriter.add_formatted_code_block(lsf_repr)

            # for via in via_list:
            #     pass

            # for pin in pin_list:
            #     pass

            for path in content_list.path_list:
                # Treat like polygons
                if tuple(path['layer']) in prop_map:
                    layer_prop = prop_map[tuple(path['layer'])]
                    lsf_repr = PhotonicPolygon.lsf_export(path['polygon_points'], layer_prop)
                    lsfwriter.add_formatted_code_block(lsf_repr)

            if len(content_list.polygon_list) != 0:
                lsfwriter.add_formatted_line(' ')
                lsfwriter.add_formatted_line('#---------------- ')
                lsfwriter.add_formatted_line('# Adding Polygons ')
                lsfwriter.add_formatted_line('#---------------- ')
            for polygon in content_list.polygon_list:
                if tuple(polygon['layer']) in prop_map:
                    layer_prop = prop_map[tuple(polygon['layer'])]
                    lsf_repr = PhotonicPolygon.lsf_export(polygon['points'], layer_prop)
                    lsfwriter.add_formatted_code_block(lsf_repr)

            if len(content_list.round_list) != 0:
                lsfwriter.add_formatted_line(' ')
                lsfwriter.add_formatted_line('#-------------- ')
                lsfwriter.add_formatted_line('# Adding Rounds ')
                lsfwriter.add_formatted_line('#-------------- ')
            for round_obj in content_list.round_list:
                if tuple(round_obj['layer']) in prop_map:
                    nx, ny = round_obj.get('arr_nx', 1), round_obj.get('arr_ny', 1)
                    layer_prop = prop_map[tuple(round_obj['layer'])]

                    if nx > 1 or ny > 1:
                        lsf_repr = PhotonicRound.lsf_export(
                            rout=round_obj['rout'],
                            rin=round_obj['rin'],
                            theta0=round_obj['theta0'],
                            theta1=round_obj['theta1'],
                            layer_prop=layer_prop,
                            center=round_obj['center'],
                            nx=nx,
                            ny=ny,
                            spx=round_obj['arr_spx'],
                            spy=round_obj['arr_spy'],
                        )
                    else:
                        lsf_repr = PhotonicRound.lsf_export(
                            rout=round_obj['rout'],
                            rin=round_obj['rin'],
                            theta0=round_obj['theta0'],
                            theta1=round_obj['theta1'],
                            layer_prop=layer_prop,
                            center=round_obj['center'],
                        )
                    lsfwriter.add_formatted_code_block(lsf_repr)

            if len(content_list.sim_list) != 0:
                lsfwriter.add_formatted_line(' ')
                lsfwriter.add_formatted_line('#-------------------------- ')
                lsfwriter.add_formatted_line('# Adding Simulation Objects ')
                lsfwriter.add_formatted_line('#-------------------------- ')
            for sim in content_list.sim_list:
                # lsf_repr = sim.lsf_export()
                lsf_repr = sim['code']
                lsfwriter.add_formatted_code_block(lsf_repr)

            if len(content_list.source_list) != 0:
                lsfwriter.add_formatted_line(' ')
                lsfwriter.add_formatted_line('#---------------------- ')
                lsfwriter.add_formatted_line('# Adding Source Objects ')
                lsfwriter.add_formatted_line('#---------------------- ')
            for source in content_list.source_list:
                # lsf_repr = source.lsf_export()
                lsf_repr = source.content['code']
                lsfwriter.add_formatted_code_block(lsf_repr)

            if len(content_list.monitor_list) != 0:
                lsfwriter.add_formatted_line(' ')
                lsfwriter.add_formatted_line('#----------------------- ')
                lsfwriter.add_formatted_line('# Adding Monitor Objects ')
                lsfwriter.add_formatted_line('#----------------------- ')
            for monitor in content_list.monitor_list:
                # lsf_repr = monitor.lsf_export()
                lsf_repr = monitor.content['code']
                lsfwriter.add_formatted_code_block(lsf_repr)

            lsfwriter.export_to_lsf()

        end = time.time()
        logging.info(f'LSF Generation took {end-start:.4g} seconds')
