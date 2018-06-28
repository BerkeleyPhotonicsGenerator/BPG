
from bag.layout.template import TemplateBase
from bag.layout.util import BBox
import yaml
import os
import sys

from bag.core import BagProject
from bag.layout import RoutingGrid, TemplateDB
from BPG.photonics_template import PhotonicsTemplateBase, PhotonicsPort, PhotonicsTemplateDB
from BPG.photonic_core import PhotonicBagProject


class Test(PhotonicsTemplateBase):
    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (PhotonicsTemplateDB, str, Dict[str, Any], Set[str], **Any) -> None
        super(Test, self).__init__(temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        """Returns a dictionary containing default parameter values.

        Override this method to define default parameter values.  As good practice,
        you should avoid defining default values for technology-dependent parameters
        (such as channel length, transistor width, etc.), but only define default
        values for technology-independent parameters (such as number of tracks).

        Returns
        -------
        default_params : dict[str, any]
            dictionary of default parameter values.
        """
        return dict(
        )

    @classmethod
    def get_params_info(cls):
        """Returns a dictionary containing parameter descriptions.

        Override this method to return a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : dict[str, str]
            dictionary from parameter name to description.
        """
        return dict(
        )

    def draw_layout(self):
        """
        """

        self.add_rect(
            layer='RX',
            bbox=BBox(
                left=0,
                right=1000,
                bottom=0,
                top=10000,
                resolution=self.grid.resolution,
                unit_mode=True,
            ),
            unit_mode=True,
        )


class Test2(PhotonicsTemplateBase):
    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # type: (PhotonicsTemplateDB, str, Dict[str, Any], Set[str], **Any) -> None
        super(Test2, self).__init__(temp_db, lib_name, params, used_names, **kwargs)
        self._sch_params = None

    @property
    def sch_params(self):
        # type: () -> Dict[str, Any]
        return self._sch_params

    @classmethod
    def get_default_param_values(cls):
        # type: () -> Dict[str, Any]
        """Returns a dictionary containing default parameter values.

        Override this method to define default parameter values.  As good practice,
        you should avoid defining default values for technology-dependent parameters
        (such as channel length, transistor width, etc.), but only define default
        values for technology-independent parameters (such as number of tracks).

        Returns
        -------
        default_params : dict[str, any]
            dictionary of default parameter values.
        """
        return dict(
        )

    @classmethod
    def get_params_info(cls):
        """Returns a dictionary containing parameter descriptions.

        Override this method to return a dictionary from parameter names to descriptions.

        Returns
        -------
        param_info : dict[str, str]
            dictionary from parameter name to description.
        """
        return dict(
        )

    def draw_layout(self):
        """
        """

        rect1 = self.add_rect(
            layer='RX',
            bbox=BBox(
                left=5,
                right=10,
                bottom=1,
                top=5,
                resolution=self.grid.resolution,
                unit_mode=False,
            ),
        )
        rect2 = self.add_rect(
            layer=('M1', 'phot'),
            bbox=BBox(
                left=10,
                right=20,
                bottom=1,
                top=5,
                resolution=self.grid.resolution,
                unit_mode=False,
            ),
        )

        rect3 = self.add_rect(
            layer='PC',
            bbox=BBox(
                left=-10,
                right=0,
                bottom=-10,
                top=-5,
                resolution=self.grid.resolution,
                unit_mode=False,
            ),
        )

        test_master = self.new_template(params={}, temp_cls=Test)

        test_1 = self.add_instance(
            test_master,
            'test_inst_1',
            loc=(-5, -5),
            unit_mode=False
        )

        test_2 = self.add_instance(
            test_master,
            'test_inst_2',
            loc=(5, 20),
            unit_mode=False
        )


def make_tdb(prj, target_lib, specs):
    grid_specs = specs['routing_grid']
    layers = grid_specs['layers']
    spaces = grid_specs['spaces']
    widths = grid_specs['widths']
    bot_dir = grid_specs['bot_dir']

    routing_grid = RoutingGrid(prj.tech_info, layers, spaces, widths, bot_dir)
    tdb = TemplateDB('template_libs.def', routing_grid, target_lib, use_cybagoa=True,
                     gds_lay_file='gds_map.yaml')
    return tdb


def generate(prj, specs, gen_layout=True):
    # Get information from YAML
    lib_name = specs['lib_name']
    cell_name = specs['cell_name']
    params = specs['params']

    temp_db = make_tdb(prj, impl_lib, specs)
    temp = temp_db.new_template(params=params, temp_cls=Test2, debug=False)

    if gen_layout:
        print('creating layout')
        temp_db.batch_layout(prj, [temp], [cell_name])
        print('done')


if __name__ == '__main__':

    os.environ['BAG_CONFIG_PATH'] = 'bag_config.yaml'
    os.environ['BAG_WORK_DIR'] = '.'
    os.environ['BAG_TECH_CONFIG_DIR'] = '.'
    os.environ['BAG_TEMP_DIR'] = '.'
    os.environ['PROJECT'] = '.'


    impl_lib = 'PhotTest'

    block_specs = dict(
        lib_name='PhotTest_libname',
        cell_name='Test_cellname',
        params=dict(
        ),
        routing_grid=dict(
            layers={},
            spaces={},
            widths={},
            bot_dir='x'
        )
    )

    local_dict = locals()
    if 'prj' not in local_dict:
        print('creating BAG project')
        bprj = PhotonicBagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    generate(bprj, block_specs, gen_layout=True)