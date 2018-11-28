import time
import logging
import yaml

from BPG.abstract_plugin import AbstractPlugin
from .code_generator import LumericalDesignGenerator
from .objects import *


class LumericalPlugin(AbstractPlugin):
    def __init__(self, lsf_export_config, lsf_filepath):
        self.lsf_export_config = lsf_export_config
        self.lsf_filepath = lsf_filepath

    def export_content_list(self, content_list):
        """
        Exports the physical design into the lumerical LSF format

        Parameters
        ----------
        content_list
            A flattened content list that has already been run through lumerical dataprep
        """
        start = time.time()
        # 1) Import tech information for the layermap and lumerical properties
        with open(self.lsf_export_config, 'r') as f:
            lay_info = yaml.load(f)
            prop_map = lay_info['lumerical_prop_map']

        # 2) For each element in the content list, convert it into lsf code and append to running file
        for count, content in enumerate(content_list):
            lsfwriter = LumericalDesignGenerator(self.lsf_filepath + '_' + str(count))

            # Unpack content list for easy access by type
            (cell_name, inst_tot_list, rect_list, via_list, pin_list,
             path_list, blockage_list, boundary_list, polygon_list, round_list,
             sim_list, source_list, monitor_list) = content

            if len(rect_list) != 0:
                lsfwriter.add_formatted_line(' ')
                lsfwriter.add_formatted_line('#------------------ ')
                lsfwriter.add_formatted_line('# Adding Rectangles ')
                lsfwriter.add_formatted_line('#------------------ ')
            for rect in rect_list:
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

            for path in path_list:
                # Treat like polygons
                if tuple(path['layer']) in prop_map:
                    layer_prop = prop_map[tuple(path['layer'])]
                    lsf_repr = PhotonicPolygon.lsf_export(path['polygon_points'], layer_prop)
                    lsfwriter.add_formatted_code_block(lsf_repr)

            if len(polygon_list) != 0:
                lsfwriter.add_formatted_line(' ')
                lsfwriter.add_formatted_line('#---------------- ')
                lsfwriter.add_formatted_line('# Adding Polygons ')
                lsfwriter.add_formatted_line('#---------------- ')
            for polygon in polygon_list:
                if tuple(polygon['layer']) in prop_map:
                    layer_prop = prop_map[tuple(polygon['layer'])]
                    lsf_repr = PhotonicPolygon.lsf_export(polygon['points'], layer_prop)
                    lsfwriter.add_formatted_code_block(lsf_repr)

            if len(round_list) != 0:
                lsfwriter.add_formatted_line(' ')
                lsfwriter.add_formatted_line('#-------------- ')
                lsfwriter.add_formatted_line('# Adding Rounds ')
                lsfwriter.add_formatted_line('#-------------- ')
            for round_obj in round_list:
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

            if len(sim_list) != 0:
                lsfwriter.add_formatted_line(' ')
                lsfwriter.add_formatted_line('#-------------------------- ')
                lsfwriter.add_formatted_line('# Adding Simulation Objects ')
                lsfwriter.add_formatted_line('#-------------------------- ')
            for sim in sim_list:
                lsf_repr = sim.lsf_export()
                lsfwriter.add_formatted_code_block(lsf_repr)

            if len(source_list) != 0:
                lsfwriter.add_formatted_line(' ')
                lsfwriter.add_formatted_line('#---------------------- ')
                lsfwriter.add_formatted_line('# Adding Source Objects ')
                lsfwriter.add_formatted_line('#---------------------- ')
            for source in source_list:
                lsf_repr = source.lsf_export()
                lsfwriter.add_formatted_code_block(lsf_repr)

            if len(monitor_list) != 0:
                lsfwriter.add_formatted_line(' ')
                lsfwriter.add_formatted_line('#----------------------- ')
                lsfwriter.add_formatted_line('# Adding Monitor Objects ')
                lsfwriter.add_formatted_line('#----------------------- ')
            for monitor in monitor_list:
                lsf_repr = monitor.lsf_export()
                lsfwriter.add_formatted_code_block(lsf_repr)

            lsfwriter.export_to_lsf()

        end = time.time()
        logging.info(f'LSF Generation took {end-start:.4g} seconds')
