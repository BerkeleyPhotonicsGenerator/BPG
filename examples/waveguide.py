# -*- coding: utf-8 -*-

from typing import Dict, Set, Any

from BPG.photonics_template import PhotonicTemplateBase
from bag.layout.core import BBox
from bag.layout.template import TemplateDB


class Waveguide(PhotonicTemplateBase):

    def __init__(self,
                 temp_db,  # type: TemplateDB
                 lib_name,  # type: str
                 params,  # type: Dict[str, Any]
                 used_names,  # type: Set[str]
                 **kwargs,
                 ):
        PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_default_param_values(cls):
        return dict(
            width=0.4,
            length=1,
        )

    @classmethod
    def get_params_info(cls):

        return dict(
            width='Waveguide width [layout units]',
            length='Waveguide length [layout units]',
        )

    def draw_layout(self):
        length = self.params['length']
        width = self.params['width']

        self.add_rect('Si',
                      bbox=BBox(left=0, bottom=-width/2, right=length, top=width/2,
                           resolution=self.grid.resolution, unit_mode=False
                           ),
                      unit_mode=False
                      )

        self.add_photonic_port(
            name='PORT0',
            center=(0, 0),
            inside_point=(length/2, 0),
            width=width,
            layer=('RX', 'port'),
            resolution=self.grid.resolution,
            unit_mode=False
        )

        self.add_photonic_port(
            name='PORT1',
            center=(length, 0),
            inside_point=(length/2, 0),
            width=width,
            layer=('RX', 'port'),
            resolution=self.grid.resolution,
            unit_mode=False
        )


class WaveguideVert(PhotonicTemplateBase):

    def __init__(self,
                 temp_db,  # type: TemplateDB
                 lib_name,  # type: str
                 params,  # type: Dict[str, Any]
                 used_names,  # type: Set[str]
                 **kwargs,
                 ):
        PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_default_param_values(cls):
        return dict(
            width=0.4,
            length=1,
        )

    @classmethod
    def get_params_info(cls):

        return dict(
            width='Waveguide width [layout units]',
            length='Waveguide length [layout units]',
        )

    def draw_layout(self):
        length = self.params['length']
        width = self.params['width']

        self.add_rect('Poly',
                      bbox=BBox(left=-width/2, bottom=0, right=width/2, top=length,
                           resolution=self.grid.resolution, unit_mode=False
                           ),
                      unit_mode=False
                      )

        self.add_photonic_port(
            name='PORT0',
            center=(0, 0),
            inside_point=(0, length/2),
            width=width,
            layer=('RX', 'port'),
            resolution=self.grid.resolution,
            unit_mode=False
        )

        self.add_photonic_port(
            name='PORT1',
            center=(0, length),
            inside_point=(0, length/2),
            width=width,
            layer=('RX', 'port'),
            resolution=self.grid.resolution,
            unit_mode=False
        )


class WaveguideConnectTest(PhotonicTemplateBase):

    def __init__(self,
                 temp_db,  # type: TemplateDB
                 lib_name,  # type: str
                 params,  # type: Dict[str, Any]
                 used_names,  # type: Set[str]
                 **kwargs,
                 ):
        PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_default_param_values(cls):
        return dict(
            width1=0.4,
            length1=1,
            width2=0.4,
            length2=1,
        )

    @classmethod
    def get_params_info(cls):

        return dict(
            width1='Waveguide width [layout units]',
            length1='Waveguide length [layout units]',
            width2='',
            length2='',
            wg1='',
            wg2='',
        )

    def draw_layout(self):
        wg1_params = self.params['wg1']
        wg2_params = self.params['wg2']

        wg_h_master = self.new_template(params=wg1_params, temp_cls=Waveguide)
        wg_v_master = self.new_template(params=wg2_params, temp_cls=WaveguideVert)

        self.add_instance(
            wg_h_master,
            'absolute_pos_H',
            (-10, -10),
            'R0',
            unit_mode=False,
        )

        self.add_instance(
            wg_v_master,
            'absolute_pos_V',
            (-15, -10),
            'R0',
            unit_mode=False,
        )

        # Add array of ports
        self.add_photonic_port(
            name='VertPort_InDown_AlignedNoReflect',
            center=(0, 0),
            inside_point=(0, -1),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        self.add_photonic_port(
            name='VertPort_InDown_AlignedReflect',
            center=(20, 0),
            inside_point=(20, -1),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        self.add_photonic_port(
            name='VertPort_InDown_180NoReflect',
            center=(40, 0),
            inside_point=(40, -1),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        self.add_photonic_port(
            name='VertPort_InDown_180Reflect',
            center=(60, 0),
            inside_point=(60, -1),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        # Connect to the ports
        self.add_instances_port_to_port(
            inst_master=wg_v_master,
            instance_port_name='PORT0',
            self_port_name='VertPort_InDown_AlignedNoReflect',
            instance_name='test',
        )

        self.add_instances_port_to_port(
            inst_master=wg_v_master,
            instance_port_name='PORT0',
            self_port_name='VertPort_InDown_AlignedReflect',
            instance_name='test',
            reflect=True
        )

        self.add_instances_port_to_port(
            inst_master=wg_v_master,
            instance_port_name='PORT1',
            self_port_name='VertPort_InDown_180NoReflect',
            instance_name='test',
        )

        self.add_instances_port_to_port(
            inst_master=wg_v_master,
            instance_port_name='PORT1',
            self_port_name='VertPort_InDown_180Reflect',
            instance_name='test',
            reflect=True
        )

        # 90/270 test
        # add array of ports
        self.add_photonic_port(
            name='VertPort_InDown_90NoReflect',
            center=(0, 30),
            inside_point=(0, -1),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        self.add_photonic_port(
            name='VertPort_InDown_90Reflect',
            center=(20, 30),
            inside_point=(20, -1),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        self.add_photonic_port(
            name='VertPort_InDown_270NoReflect',
            center=(40, 30),
            inside_point=(40, -1),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        self.add_photonic_port(
            name='VertPort_InDown_270Reflect',
            center=(60, 30),
            inside_point=(60, -1),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        # Connect to the ports
        self.add_instances_port_to_port(
            inst_master=wg_h_master,
            instance_port_name='PORT0',
            self_port_name='VertPort_InDown_90NoReflect',
            instance_name='test',
        )

        self.add_instances_port_to_port(
            inst_master=wg_h_master,
            instance_port_name='PORT0',
            self_port_name='VertPort_InDown_90Reflect',
            instance_name='test',
            reflect=True
        )

        self.add_instances_port_to_port(
            inst_master=wg_h_master,
            instance_port_name='PORT1',
            self_port_name='VertPort_InDown_270NoReflect',
            instance_name='test',
        )

        self.add_instances_port_to_port(
            inst_master=wg_h_master,
            instance_port_name='PORT1',
            self_port_name='VertPort_InDown_270Reflect',
            instance_name='test',
            reflect=True
        )

        # 0/180 tests when reference port is horizontal
        # Add array of ports
        self.add_photonic_port(
            name='HorzPort_InRight_AlignedNoReflect',
            center=(0, 100),
            inside_point=(1, 100),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        self.add_photonic_port(
            name='HorzPort_InRight_AlignedReflect',
            center=(40, 100),
            inside_point=(41, 100),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        self.add_photonic_port(
            name='HorzPort_InRight_180NoReflect',
            center=(80, 100),
            inside_point=(81, 100),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        self.add_photonic_port(
            name='HorzPort_InRight_180Reflect',
            center=(120, 100),
            inside_point=(121, 100),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        # Connect to the ports
        self.add_instances_port_to_port(
            inst_master=wg_h_master,
            instance_port_name='PORT1',
            self_port_name='HorzPort_InRight_AlignedNoReflect',
            instance_name='test',
        )

        self.add_instances_port_to_port(
            inst_master=wg_h_master,
            instance_port_name='PORT1',
            self_port_name='HorzPort_InRight_AlignedReflect',
            instance_name='test',
            reflect=True
        )

        self.add_instances_port_to_port(
            inst_master=wg_h_master,
            instance_port_name='PORT0',
            self_port_name='HorzPort_InRight_180NoReflect',
            instance_name='test',
        )

        self.add_instances_port_to_port(
            inst_master=wg_h_master,
            instance_port_name='PORT0',
            self_port_name='HorzPort_InRight_180Reflect',
            instance_name='test',
            reflect=True
        )

        # 90/270 test
        # add array of ports
        self.add_photonic_port(
            name='HorzPort_InRight_90NoReflect',
            center=(0, 200),
            inside_point=(1, 200),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        self.add_photonic_port(
            name='HorzPort_InRight_90Reflect',
            center=(40, 200),
            inside_point=(41, 200),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        self.add_photonic_port(
            name='HorzPort_InRight_270NoReflect',
            center=(80, 200),
            inside_point=(81, 200),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        self.add_photonic_port(
            name='HorzPort_InRight_270Reflect',
            center=(120, 200),
            inside_point=(121, 200),
            width=1,
            layer='Si',
            unit_mode=False,
        )

        # Connect to the ports
        self.add_instances_port_to_port(
            inst_master=wg_v_master,
            instance_port_name='PORT0',
            self_port_name='HorzPort_InRight_90NoReflect',
            instance_name='test',
        )

        self.add_instances_port_to_port(
            inst_master=wg_v_master,
            instance_port_name='PORT0',
            self_port_name='HorzPort_InRight_90Reflect',
            instance_name='test',
            reflect=True
        )

        self.add_instances_port_to_port(
            inst_master=wg_v_master,
            instance_port_name='PORT1',
            self_port_name='HorzPort_InRight_270NoReflect',
            instance_name='test',
        )

        self.add_instances_port_to_port(
            inst_master=wg_v_master,
            instance_port_name='PORT1',
            self_port_name='HorzPort_InRight_270Reflect',
            instance_name='test',
            reflect=True
        )
