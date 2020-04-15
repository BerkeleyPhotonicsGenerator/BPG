import time
import logging
import yaml
import numpy as np

from BPG.abstract_plugin import AbstractPlugin
# from .code_generator import LumericalDesignGenerator
from BPG.lumerical.objects import PhotonicRect, PhotonicPolygon, PhotonicRound

try:
    import lumapi
except ImportError:
    lumapi = None

from BPG.geometry import CoordBase


from typing import TYPE_CHECKING, List

if TYPE_CHECKING:
    from BPG.content_list import ContentList
    from lumopt.utilities.simulation import Simulation


class LumericalAPIPlugin:
    def __init__(self,
                 lsf_export_config,
                 ):
        self.lsf_export_config = lsf_export_config

    def export_content_list(self,
                            content_lists: List["ContentList"],
                            name_list: List[str] = None,
                            sim: "Simulation" = None,
                            ):
        """
        Exports the physical design into the lumerical LSF format

        Parameters
        ----------
        content_lists : List[ContentList]
            A list of flattened content lists that have already been run through lumerical dataprep
        name_list : List[str]
            A list of names to give to each generated lsf
        sim : Simulation

        """

        sim.fdtd.switchtolayout()
        sim.fdtd.redrawoff()

        start = time.time()
        # 1) Import tech information for the layermap and lumerical properties
        with open(self.lsf_export_config, 'r') as f:
            lay_info = yaml.load(f)
            prop_map = lay_info['lumerical_prop_map']

        # 2) For each element in the content list, convert it into lsf code and append to running file
        for name, content_list in zip(name_list, content_lists):
            sim.fdtd.select(name)
            sim.fdtd.delete()
            struct_group = sim.fdtd.addstructuregroup()
            struct_group['name'] = name

            for rect in content_list.rect_list:
                if tuple(rect['layer']) in prop_map:
                    layer_prop = prop_map[tuple(rect['layer'])]

                    x_min = CoordBase(rect['bbox'][0][0]).meters
                    x_max = CoordBase(rect['bbox'][1][0]).meters
                    y_min = CoordBase(rect['bbox'][0][1]).meters
                    y_max = CoordBase(rect['bbox'][1][1]).meters

                    if not isinstance(layer_prop['z_min'], list):
                        z_min_list = [layer_prop['z_min']]
                    else:
                        z_min_list = layer_prop['z_min']
                    if not isinstance(layer_prop['z_max'], list):
                        z_max_list = [layer_prop['z_max']]
                    else:
                        z_max_list = layer_prop['z_max']

                    for z_min_val, z_max_val in zip(z_min_list, z_max_list):
                        z_min = CoordBase(z_min_val).meters
                        z_max = CoordBase(z_max_val).meters

                        nx, ny = rect.get('arr_nx', 1), rect.get('arr_ny', 1)
                        spx, spy = CoordBase(rect.get('arr_spx', 0)).meters, CoordBase(rect.get('arr_spy', 0)).meters

                        for x_count in range(nx):
                            for y_count in range(ny):
                                lum_rectangle = sim.fdtd.addrect()


                                lum_rectangle['material'] = layer_prop['material']
                                if 'alpha' in layer_prop:
                                    lum_rectangle['alpha'] = layer_prop['alpha']

                                if 'mesh_order' in layer_prop:
                                    lum_rectangle['override mesh order from material database'] = 1
                                    lum_rectangle['mesh order'] = layer_prop['mesh_order']

                                lum_rectangle['x min'] = x_min + x_count * spx
                                lum_rectangle['x max'] = x_max + x_count * spx
                                lum_rectangle['y min'] = y_min + y_count * spy
                                lum_rectangle['y max'] = y_max + y_count * spy
                                lum_rectangle['z min'] = z_min
                                lum_rectangle['z max'] = z_max

                                sim.fdtd.addtogroup(name)

            # for via in via_list:
            #     pass

            # for pin in pin_list:
            #     pass

            for path in content_list.path_list:
                pass
                # TODO
                # # Treat like polygons
                # if tuple(path['layer']) in prop_map:
                #     layer_prop = prop_map[tuple(path['layer'])]
                #     lsf_repr = PhotonicPolygon.lsf_export(path['polygon_points'], layer_prop)
                #     lsfwriter.add_formatted_code_block(lsf_repr)

            for polygon in content_list.polygon_list:
                if tuple(polygon['layer']) in prop_map:
                    layer_prop = prop_map[tuple(polygon['layer'])]

                    if not isinstance(layer_prop['z_min'], list):
                        z_min_list = [layer_prop['z_min']]
                    else:
                        z_min_list = layer_prop['z_min']
                    if not isinstance(layer_prop['z_max'], list):
                        z_max_list = [layer_prop['z_max']]
                    else:
                        z_max_list = layer_prop['z_max']

                    for z_min_val, z_max_val in zip(z_min_list, z_max_list):
                        z_min = CoordBase(z_min_val).meters
                        z_max = CoordBase(z_max_val).meters

                        # TODO: figure out better way to convert units
                        points = np.array(polygon['points']) * 1e-6

                        lum_polygon = sim.fdtd.addpoly()

                        lum_polygon['material'] = layer_prop['material']

                        if 'alpha' in layer_prop:
                            lum_polygon['alpha'] = layer_prop['alpha']

                        if 'mesh_order' in layer_prop:
                            lum_polygon['override mesh order from material database'] = 1
                            lum_polygon['mesh order'] = layer_prop['mesh_order']

                        lum_polygon['x'] = 0
                        lum_polygon['y'] = 0
                        lum_polygon['z min'] = z_min
                        lum_polygon['z max'] = z_max

                        lum_polygon['vertices'] = points

                        sim.fdtd.addtogroup(name)

            for round_obj in content_list.round_list:
                pass
                # TODO
                # if tuple(round_obj['layer']) in prop_map:
                #     nx, ny = round_obj.get('arr_nx', 1), round_obj.get('arr_ny', 1)
                #     layer_prop = prop_map[tuple(round_obj['layer'])]
                #
                #     if nx > 1 or ny > 1:
                #         lsf_repr = PhotonicRound.lsf_export(
                #             rout=round_obj['rout'],
                #             rin=round_obj['rin'],
                #             theta0=round_obj['theta0'],
                #             theta1=round_obj['theta1'],
                #             layer_prop=layer_prop,
                #             center=round_obj['center'],
                #             nx=nx,
                #             ny=ny,
                #             spx=round_obj['arr_spx'],
                #             spy=round_obj['arr_spy'],
                #         )
                #     else:
                #         lsf_repr = PhotonicRound.lsf_export(
                #             rout=round_obj['rout'],
                #             rin=round_obj['rin'],
                #             theta0=round_obj['theta0'],
                #             theta1=round_obj['theta1'],
                #             layer_prop=layer_prop,
                #             center=round_obj['center'],
                #         )
                #     lsfwriter.add_formatted_code_block(lsf_repr)

            # TODO
            # if len(content_list.sim_list) != 0:
            #     lsfwriter.add_formatted_line(' ')
            #     lsfwriter.add_formatted_line('#-------------------------- ')
            #     lsfwriter.add_formatted_line('# Adding Simulation Objects ')
            #     lsfwriter.add_formatted_line('#-------------------------- ')
            # for sim in content_list.sim_list:
            #     # lsf_repr = sim.lsf_export()
            #     lsf_repr = sim['code']
            #     lsfwriter.add_formatted_code_block(lsf_repr)
            #
            # if len(content_list.source_list) != 0:
            #     lsfwriter.add_formatted_line(' ')
            #     lsfwriter.add_formatted_line('#---------------------- ')
            #     lsfwriter.add_formatted_line('# Adding Source Objects ')
            #     lsfwriter.add_formatted_line('#---------------------- ')
            # for source in content_list.source_list:
            #     # lsf_repr = source.lsf_export()
            #     lsf_repr = source.content['code']
            #     lsfwriter.add_formatted_code_block(lsf_repr)
            #
            # if len(content_list.monitor_list) != 0:
            #     lsfwriter.add_formatted_line(' ')
            #     lsfwriter.add_formatted_line('#----------------------- ')
            #     lsfwriter.add_formatted_line('# Adding Monitor Objects ')
            #     lsfwriter.add_formatted_line('#----------------------- ')
            # for monitor in content_list.monitor_list:
            #     # lsf_repr = monitor.lsf_export()
            #     lsf_repr = monitor.content['code']
            #     lsfwriter.add_formatted_code_block(lsf_repr)
            #
            # lsfwriter.export_to_lsf()

        end = time.time()
        logging.info(f'LSF Generation took {end-start:.4g} seconds')
        sim.fdtd.redrawon()

