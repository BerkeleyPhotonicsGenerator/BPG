import BPG
from BPG.lumericalAPI.core import LumericalAPIPlugin
import copy
from typing import TYPE_CHECKING, Optional, Dict, Any, List, Union
import numpy as np
import lumapi
import sys


if TYPE_CHECKING:
    from lumopt.utilities.simulation import Simulation
import logging

class Param:
    def __init__(self,
                 name: str,
                 initial_value: Union[int, float] = None,
                 lower_bound: Union[int, float] = None,
                 upper_bound: Union[int, float] = None,
                 ):
        self.name = name

        self.lower_bound = lower_bound
        self.upper_bound = upper_bound

        self.initial_value = initial_value

        self.value = initial_value

    def update(self,
               value):
        self.value = value


class GeometryManager(BPG.PhotonicLayoutManager):

    def __init__(self,
                 spec_file: str,
                 bag_config_path: Optional[str] = None,
                 port: Optional[int] = None,
                 **kwargs: Dict[str, Any],
                 ) -> None:

        BPG.PhotonicLayoutManager.__init__(self, spec_file, bag_config_path, port, **kwargs)

        self.base_layout_params = BPG.run_settings['layout_params']

        self.optimization_params = list()

        self.lumerical_plugin = LumericalAPIPlugin(lsf_export_config=self.photonic_tech_info.lsf_export_path)

        self.params_hist = list()

        self.dx = BPG.run_settings['opt_params']['dx']

    def update_params(self,
                      params: List,
                      ):
        for param_value, param in zip(params, self.optimization_params):
            param.update(param_value)

        self.params_hist.append(copy.deepcopy(self.optimization_params))

    def export_geometry(self,
                        sim: "Simulation",
                        params: Optional[List] = None
                        ):
        logger = logging.getLogger()
        logger.disabled = True
        self.cell_name_list = []
        self.template_list = []

        export_params = copy.deepcopy(self.base_layout_params)

        export_params.update(self.get_current_params_dict())

        if params is not None:
            temp_params = dict()
            for param_value, param in zip(params, self.optimization_params):
                temp_params[param.name] = param_value

            export_params.update(temp_params)

        self.generate_template(params=export_params)
        self.generate_content(save_content=False)

        self.lumerical_plugin.export_content_list(
            content_lists=self.content_list,
            name_list=self.cell_name_list,
            sim=sim,
        )

        logger.disabled = False
    # def set_optimization_params(self,
    #                             params: List[str],
    #                             ) -> None:
    #     self.optimization_param_names = params

    def set_optimization_params(self,
                                params: List["Param"]):

        self.optimization_params = params

        self.params_hist.append(copy.deepcopy(self.optimization_params))

    def get_current_params_dict(self) -> Dict:
        current_params = dict()
        for param in self.optimization_params:
            current_params[param.name] = param.value

        return current_params

    def get_current_params(self) -> List:
        return np.array([param.value for param in self.optimization_params])

    def get_bounds(self) -> np.ndarray:
        bounds = list()

        for param in self.optimization_params:
            bounds.append([param.lower_bound, param.upper_bound])

        return np.array(bounds)

    @staticmethod
    def get_eps_from_index_monitor(sim: "Simulation",
                                   eps_result_name: str,
                                   monitor_name: str = 'opt_fields'
                                   ):
        index_monitor_name = monitor_name + '_index'
        sim.fdtd.eval("{0}_data_set = getresult('{0}','index');".format(index_monitor_name) +
                      "{0} = matrix(length({1}_data_set.x), length({1}_data_set.y), "
                      "length({1}_data_set.z), length({1}_data_set.f), 3);".format(eps_result_name,
                                                                                   index_monitor_name) +
                      "{0}(:, :, :, :, 1) = {1}_data_set.index_x^2;".format(eps_result_name, index_monitor_name) +
                      "{0}(:, :, :, :, 2) = {1}_data_set.index_y^2;".format(eps_result_name, index_monitor_name) +
                      "{0}(:, :, :, :, 3) = {1}_data_set.index_z^2;".format(eps_result_name, index_monitor_name) +
                      "clear({0}_data_set);".format(index_monitor_name))

    def d_eps_on_cad(self,
                     sim: "Simulation",
                     ):
        self.get_eps_from_index_monitor(sim, 'original_eps_data')
        current_params = self.get_current_params()
        sim.fdtd.eval("d_epses = cell({});".format(len(current_params)))
        lumapi.putDouble(sim.fdtd.handle, "dx", self.dx)
        print('Getting d eps: dx = ' + str(self.dx))
        sim.fdtd.redrawoff()
        for i, param in enumerate(current_params):
            d_params = current_params.copy()
            d_params[i] = param + self.dx
            self.export_geometry(sim=sim, params=d_params)
            self.get_eps_from_index_monitor(sim, 'current_eps_data')
            sim.fdtd.eval("d_epses{" + str(i + 1) + "} = (current_eps_data - original_eps_data) / dx;")
            sys.stdout.write('.'), sys.stdout.flush()
        sim.fdtd.eval("clear(original_eps_data, current_eps_data, dx);")
        print('')
        sim.fdtd.redrawon()
