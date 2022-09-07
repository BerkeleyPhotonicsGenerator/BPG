import os
import sys
import bag
import bag.io
import abc
import yaml
import logging
import math
import string
from .logger import setup_logger
from pathlib import Path
from itertools import chain

# BAG imports
from bag.core import BagProject, create_tech_info, _import_class_from_str
from bag.layout.util import BBox
from bag.io.file import read_yaml, read_file
from bag.layout.core import BagLayout, DummyTechInfo

# BPG imports
import BPG
from BPG.content_list import ContentList
from BPG.geometry import BBoxMut

from typing import TYPE_CHECKING, List, Callable, Union, Tuple, Dict, Optional, Any
from BPG.bpg_custom_types import layer_or_lpp_type, dim_type

# Typing imports
if TYPE_CHECKING:
    from BPG.objects import PhotonicRound, PhotonicPath
    from bag.layout.objects import InstanceInfo
    from bag.layout.core import TechInfo

try:
    import cybagoa
except ImportError:
    cybagoa = None


def _parse_yaml_file(fname):
    # type: (str) -> Dict[str, Any]
    """Parse YAML file with environment variable substitution.
    Parameters
    ----------
    fname : str
        yaml file name.
    Returns
    -------
    table : Dict[str, Any]
        the yaml file as a dictionary.
    """
    content = read_file(fname)
    # substitute environment variables
    content = string.Template(content).substitute(os.environ)
    return yaml.full_load(content)


# From bag/core
class PhotonicBagProject(BagProject):
    """
    The main bag controller class.

    This class extracts user configuration variables and issues high level bag commands. Most config variables have
    defaults pointing to files in the BPG/examples/tech folder

    Parameters
    ----------
    bag_config_path : Optional[str]
        the bag configuration file path.  If None, will attempt to read from
        environment variable BAG_CONFIG_PATH.
    port : Optional[int]
        the BAG server process port number.  If not given, will read from port file.
    """

    def __init__(self, bag_config_path: Optional[str] = None, port: Optional[int] = None) -> None:
        BagProject.__init__(self, bag_config_path, port)

        # Init empty path variables to be set by user spec file
        self.log_path = None
        self.log_filename = 'output.log'
        self.project_dir: Optional[Path] = None
        self.scripts_dir: Optional[Path] = None
        self.data_dir: Optional[Path] = None
        self.content_dir: Optional[Path] = None
        self.lsf_path = None
        self.gds_path = None

        BPG.run_settings.load_new_configuration(config_dict={})

    def load_spec_file_paths(self,
                             spec_file: str,
                             **kwargs: Dict[str, Any],
                             ):
        """ Receives a specification file from the user and configures the project paths accordingly """
        specs = self.load_yaml(spec_file)
        specs.update(**kwargs)  # Update the read specs with any passed variables

        # If a new bag configuration is passed in the yaml, load it
        if 'bag_config_path' in specs:
            BPG.run_settings.update_configuration(self.load_yaml(specs['bag_config_path']))

        BPG.run_settings.update_configuration(specs)  # Update the base run_settings with anything from the yaml

        # Get root path for the project
        bag_work_dir = Path(os.environ['BAG_WORK_DIR'])

        # self.tech_info = create_tech_info(bag_config_path=BPG.run_settings['bag_config_path'])
        tech_params = _parse_yaml_file(BPG.run_settings['tech_config_path'])
        if 'class' in tech_params:
            tech_cls = _import_class_from_str(tech_params['class'])
            self.tech_info = tech_cls(tech_params)
        else:
            # just make a default tech_info object as place holder.
            print('*WARNING*: No TechInfo class defined.  Using a dummy version.')
            self.tech_info = DummyTechInfo(tech_params)

        # BAG might reset the photonic_tech_info config, need to reset it
        self.photonic_tech_info = create_photonic_tech_info(
            bpg_config=BPG.run_settings['bpg_config'],
            tech_info=self.tech_info,
        )
        print(f"BPG.run_settings: {BPG.run_settings['bpg_config']}")
        self.photonic_tech_info.load_tech_files()

        if 'photonic_tech_config_path' in BPG.run_settings:
            self.photonic_tech_info = create_photonic_tech_info(
                bpg_config=dict(photonic_tech_config_path=BPG.run_settings['photonic_tech_config_path']),
                tech_info=self.tech_info,
            )
            self.photonic_tech_info.load_tech_files()

        if hasattr(self.photonic_tech_info, 'finalize_template'):
            self.tech_info.finalize_template = self.photonic_tech_info.finalize_template

        # Setup relevant output files and directories
        if 'project_dir' in BPG.run_settings:
            self.project_dir = Path(BPG.run_settings['project_dir']).expanduser()
        else:
            default_path = Path(BPG.run_settings['database']['default_lib_path'])
            self.project_dir = default_path / BPG.run_settings['project_name']

        if 'gds_output_subdir' in self.photonic_tech_info.photonic_tech_params:
            self.data_dir = self.project_dir / self.photonic_tech_info.photonic_tech_params['gds_output_subdir']
        else:
            self.data_dir = self.project_dir

        self.scripts_dir = self.project_dir / 'scripts'
        self.content_dir = self.project_dir / 'content'

        # If users provide paths to add provide them here
        if 'path_setup' in BPG.run_settings:
            for path in BPG.run_settings['path_setup']:
                if path not in sys.path:
                    sys.path.insert(0, path)
                    print(f'Adding {path} to python module search path')

        # Make the project directories if they do not exists
        self.project_dir.mkdir(exist_ok=True, parents=True)
        self.scripts_dir.mkdir(exist_ok=True)
        self.data_dir.mkdir(exist_ok=True, parents=True)
        self.content_dir.mkdir(exist_ok=True)

        # Enable logging for BPG
        if 'logfile' in BPG.run_settings:
            # If logfile is specified in specs, dump all logs in that location
            log_path = bag_work_dir / BPG.run_settings['logfile']
            if log_path.is_dir():
                self.log_path = log_path
                self.log_filename = 'output.log'
            else:
                self.log_path = log_path.parent
                self.log_filename = log_path.name
        else:
            self.log_path = self.project_dir / 'logs'
            self.log_filename = 'output.log'
        self.log_path.mkdir(exist_ok=True)
        setup_logger(log_path=str(self.log_path), log_filename=str(self.log_filename))

        logging.info(f'PhotonicCoreLayout initialized from spec file: {spec_file}')

        # Overwrite tech parameters if specified in the spec file
        # Setup the abstract tech layermap
        if 'layermap' in BPG.run_settings:
            self.photonic_tech_info.layermap_path = bag_work_dir / BPG.run_settings['layermap']
        logging.info(f'loading layermap from {self.photonic_tech_info.layermap_path}')

        # Setup the dataprep procedure
        if 'dataprep' in BPG.run_settings:
            self.photonic_tech_info.dataprep_routine_filepath = bag_work_dir / BPG.run_settings['dataprep']
        logging.info(f'loading dataprep procedure from {self.photonic_tech_info.dataprep_routine_filepath}')

        if 'dataprep_params' in BPG.run_settings:
            self.photonic_tech_info.dataprep_parameters_filepath = bag_work_dir / BPG.run_settings['dataprep_params']
        logging.info(f'loading dataprep and DRC parameters from '
                     f'{self.photonic_tech_info.dataprep_parameters_filepath}')

        if 'dataprep_label_depth' in BPG.run_settings:
            self.photonic_tech_info.dataprep_label_depth = BPG.run_settings['dataprep_label_depth']
        logging.info(f'dataprep_label_depth set to '
                     f'{self.photonic_tech_info.dataprep_label_depth}')

        # Setup the lumerical export map
        if 'lsf_export_map' in BPG.run_settings:
            self.photonic_tech_info.lsf_export_path = bag_work_dir / BPG.run_settings['lsf_export_map']
        logging.info(f'loading lumerical export configuration from {self.photonic_tech_info.lsf_export_path}')

        # Now that paths are fully settled, load the tech files
        self.photonic_tech_info.load_tech_files()

        # Set the paths of the output files
        self.lsf_path = str(self.scripts_dir / BPG.run_settings['lsf_filename'])
        self.gds_path = str(self.data_dir / BPG.run_settings['gds_filename'])
        logging.info('loaded paths successfully')

    @staticmethod
    def load_yaml(filepath):
        """ Setup standardized method for yaml loading """
        return _parse_yaml_file(filepath)


def create_photonic_tech_info(bpg_config: Dict,
                              tech_info: "TechInfo",
                              ) -> "PhotonicTechInfo":
    """Create PhotonicTechInfo object."""

    if 'photonic_tech_config_path' not in bpg_config:
        raise ValueError('photonic_tech_config_path not defined in bag_config.yaml.')

    photonic_tech_params = _parse_yaml_file(bpg_config['photonic_tech_config_path'])
    if 'photonic_tech_class' in photonic_tech_params:
        photonic_tech_cls = _import_class_from_str(photonic_tech_params['photonic_tech_class'])
        photonic_tech_info = photonic_tech_cls(photonic_tech_params,
                                               tech_info.resolution,
                                               tech_info.layout_unit,
                                               )
    else:
        # Make a default photonic_tech_info as a place holder.
        print('*WARNING*: No PhotonicTechInfo class defined.  Using a dummy version.')
        photonic_tech_info = DummyPhotonicTechInfo(photonic_tech_params,
                                                   tech_info.resolution,
                                                   tech_info.layout_unit
                                                   )

    return photonic_tech_info


class PhotonicBagLayout(BagLayout):
    """
    This class contains layout information of a cell.

    Parameters
    ----------
    grid : :class:`bag.layout.routing.RoutingGrid`
        the routing grid instance.
    use_cybagoa : bool
        True to use cybagoa package to accelerate layout.
    """

    def __init__(self, grid, use_cybagoa=False):
        BagLayout.__init__(self, grid, use_cybagoa)

        # Add new features to be supported in content list
        self._round_list: List["PhotonicRound"] = []
        self._sim_list = []
        self._source_list = []
        self._monitor_list = []

        # The angle to rotate this master by upon finalization
        self._mod_angle = 0

        # TODO: fix bound box during rotation
        # Initialize the boundary of this cell with zero area at the origin
        self._bound_box = BBoxMut(0, 0, 0, 0, resolution=self._res, unit_mode=True)

    @property
    def mod_angle(self):
        """ Angle that this master must be rotated by during finalization """
        return self._mod_angle

    @mod_angle.setter
    def mod_angle(self, val):
        """ Ensure that the provided angle is between 0 and pi/2 """
        if val < 0 or val > math.pi / 2:
            raise ValueError(f"Angle {val} is not in modulo format")
        self._mod_angle = val

    @property
    def bound_box(self) -> BBoxMut:
        return self._bound_box

    def finalize(self):
        # type: () -> None
        """ Prevents any further changes to this layout. """
        # TODO: change this to be a 'close to 0' check
        if self.mod_angle != 0:
            self.rotate_all_by(self.mod_angle)

        self._finalized = True

        # get rectangles
        rect_list = []
        for obj in self._rect_list:
            if obj.valid:
                if not obj.bbox.is_physical():
                    print('WARNING: rectangle with non-physical bounding box found.', obj.layer)
                else:
                    obj_content = obj.content
                    rect_list.append(obj_content)

        # filter out invalid geometries
        path_list = []
        polygon_list = []
        blockage_list = []
        boundary_list = []
        via_list = []
        round_list = []
        sim_list = []
        for targ_list, obj_list in ((path_list, self._path_list),
                                    (polygon_list, self._polygon_list),
                                    (blockage_list, self._blockage_list),
                                    (boundary_list, self._boundary_list),
                                    (via_list, self._via_list),
                                    (round_list, self._round_list),
                                    (sim_list, self._sim_list)
                                    ):
            for obj in obj_list:
                if obj.valid:
                    targ_list.append(obj.content)

        # get via primitives
        via_list.extend(self._via_primitives)

        # get instances
        inst_list = []  # type: List[InstanceInfo]
        for obj in self._inst_list:
            if obj.valid:
                obj_content = self._format_inst(obj)
                inst_list.append(obj_content)

        # Assemble raw content list from all
        self._raw_content = [inst_list,
                             self._inst_primitives,
                             rect_list,
                             via_list,
                             self._pin_list,
                             path_list,
                             blockage_list,
                             boundary_list,
                             polygon_list,
                             round_list,
                             sim_list,
                             self._source_list,
                             self._monitor_list
                             ]

        if (not inst_list and not self._inst_primitives and not rect_list and not blockage_list and
                not boundary_list and not via_list and not self._pin_list and not path_list and
                not polygon_list and not round_list and not self._sim_list and not self._source_list
                and not self._monitor_list):
            self._is_empty = True
        else:
            self._is_empty = False

        # Calculate the bounding box for the overall layout
        for inst in self._inst_list:
            self._bound_box.merge(inst.bound_box)
        for rect in self._rect_list:
            self._bound_box.merge(rect.bound_box)
        if self._via_list != []:
            logging.warning("vias are currently not considered in master bounding box calculations")
        # if self._pin_list != []:
        #     logging.warning("pins are currently not considered in master bounding box calculations")
        for path in self._path_list:
            self._bound_box.merge(path.bound_box)
        if self._blockage_list != []:
            logging.warning("blockages are currently not considered in master bounding box calculations")
        if self._boundary_list != []:
            logging.warning("boundaries are currently not considered in master bounding box calculations")
        for poly in self._polygon_list:
            self._bound_box.merge(poly.bound_box)
        if self._round_list != []:
            for round in self._round_list:
                self._bound_box.merge(round.bound_box)

    def get_content(self,
                    lib_name: str,
                    cell_name: str,
                    rename_fun: Callable[[str], str],
                    ) -> Union[ContentList, Tuple[str, 'cybagoa.PyOALayout']]:
        """
        Returns a list describing geometries in this layout.

        Parameters
        ----------
        lib_name : str
            the layout library name.
        cell_name : str
            the layout top level cell name.
        rename_fun : Callable[[str], str]
            the layout cell renaming function.

        Returns
        -------
        content : Union[ContentList, Tuple[str, 'cybagoa.PyOALayout']]
            a ContentList describing this layout, or PyOALayout if cybagoa package is enabled.
        """

        if not self._finalized:
            raise Exception('Layout is not finalized.')

        cell_name = rename_fun(cell_name)
        (inst_list, inst_prim_list, rect_list, via_list, pin_list,
         path_list, blockage_list, boundary_list, polygon_list, round_list,
         sim_list, source_list, monitor_list) = self._raw_content

        # update library name and apply layout cell renaming on instances
        inst_tot_list = []
        for inst in inst_list:
            inst_temp = inst.copy()
            inst_temp['lib'] = lib_name
            inst_temp['cell'] = rename_fun(inst_temp['cell'])
            inst_tot_list.append(inst_temp)
        inst_tot_list.extend(inst_prim_list)

        if self._use_cybagoa and cybagoa is not None:
            encoding = bag.io.get_encoding()
            oa_layout = cybagoa.PyLayout(encoding)

            for obj in inst_tot_list:
                oa_layout.add_inst(**obj)
            for obj in rect_list:
                oa_layout.add_rect(**obj)
            for obj in via_list:
                oa_layout.add_via(**obj)
            for obj in pin_list:
                oa_layout.add_pin(**obj)
            for obj in path_list:
                oa_layout.add_path(**obj)
            for obj in blockage_list:
                oa_layout.add_blockage(**obj)
            for obj in boundary_list:
                oa_layout.add_boundary(**obj)
            for obj in polygon_list:
                oa_layout.add_polygon(**obj)
            for obj in round_list:
                oa_layout.add_round(**obj)

            return cell_name, oa_layout
        else:
            return ContentList(
                cell_name=cell_name,
                inst_list=inst_tot_list,
                rect_list=rect_list,
                via_list=via_list,
                pin_list=pin_list,
                path_list=path_list,
                blockage_list=blockage_list,
                boundary_list=boundary_list,
                polygon_list=polygon_list,
                round_list=round_list,
                sim_list=sim_list,
                source_list=source_list,
                monitor_list=monitor_list,
            )

    def rotate_all_by(self,
                      mod_angle: float = 0.0,
                      ) -> None:
        """
        Rotates all shapes generated on this level of the hierarchy and rotates them by the given angle about the
        origin. All shapes are converted to polygons to perform this rotation. It is assumed that the angles of
        the instances have already been rotated as needed.

        Parameters
        ----------
        mod_angle : float
            An angle between 0 and pi/2 representing the amount that all shapes should be rotated by
        """
        if self._finalized:
            raise Exception('Layout is already finalized.')

        # Rotate all polygons first! Otherwise the other shapes get rotated twice
        temp_poly_list = []
        for _ in range(len(self._polygon_list)):
            temp_poly = self._polygon_list.pop(0)  # Pull the current polygon off the list
            # Rotate the polygons and add them to the list
            temp_poly.rotate(angle=mod_angle)
            temp_poly_list.append(temp_poly)

        # Only add polygons to the content list after popping all of them off once. Otherwise there is an infinite loop
        for poly in temp_poly_list:
            self.add_polygon(poly)

        # Rotate all rects
        for _ in range(len(self._rect_list)):
            rect = self._rect_list.pop(0)  # Pull the current arrayed rectangle off the list
            poly_list = rect.export_to_polygon()  # Convert the arrayed rectangle to a list of polygons
            for poly in poly_list:
                # Rotate the polygons and add them to the list
                poly.rotate(angle=mod_angle)
                self.add_polygon(poly)

        # Rotate all round shapes
        for _ in range(len(self._round_list)):
            circ = self._round_list.pop(0)  # Pull the current arrayed round off the list
            poly_list = circ.export_to_polygon()
            for poly in poly_list:
                # Rotate the polygons and add them to the list
                poly.rotate(angle=mod_angle)
                self.add_polygon(poly)

        # Rotate all path shapes
        for _ in range(len(self._path_list)):
            path = self._path_list.pop(0)  # Pull the current arrayed path off the list
            poly = path.export_to_polygon()
            poly.rotate(angle=mod_angle)
            self.add_polygon(poly)

        # Remove all pin shaptes from pin list
        temp_pin_list = []
        for _ in range(len(self._pin_list)):
            pin = self._pin_list.pop(0)  # Pull the current pin off the list
            temp_pin_list.append(pin)

        # Rotate and add them back in
        for pin in temp_pin_list:
            new_bbox = self.bbox_rotate(bbox=pin.bbox, angle=mod_angle)
            self.add_label(
                label=pin.label,
                layer=pin.layer,
                bbox=new_bbox
            )

        for inst in self._inst_list:  # type: "PhotonicInstance"
            inst.rotate(
                loc=(0, 0),
                angle=mod_angle,
                mirror=False,
                unit_mode=False,
            )

        # TODO: Rotate all vias

        # TODO: Rotate all blockages

        # TODO: Rotate all boundaries

    def bbox_rotate(self, bbox: BBox, angle: float) -> BBox:
        """
        Given a bbox, finds coordinates for new rotated bbox
        Parameters
        ----------
        bbox : BBox
            input bbox
        angle : float
            angle in radians to rotate the bbox
        Returns
        -------
        bbox : BBox
            output bbox
        """
        ll = [bbox.left, bbox.bottom]
        new_x = math.cos(angle) * ll[0] - math.sin(angle) * ll[1]
        new_y = math.sin(angle) * ll[0] + math.cos(angle) * ll[1]
        return BBox(left=new_x,
                    bottom=new_y,
                    right=new_x + self._res,
                    top=new_y + self._res,
                    unit_mode=False,
                    resolution=self._res
                    )

    def move_all_by(self,
                    dx: "dim_type" = 0.0,
                    dy: "dim_type" = 0.0,
                    unit_mode: bool = False,
                    ) -> None:
        """Move all layout objects in this layout by the given amount.

        Parameters
        ----------
        dx : Union[float, int]
            the X shift.
        dy : Union[float, int]
            the Y shift.
        unit_mode : bool
            True if shift values are given in resolution units.
        """
        if self._finalized:
            raise Exception('Layout is already finalized.')

        for obj in chain(self._inst_list, self._inst_primitives, self._rect_list,
                         self._via_primitives, self._via_list, self._pin_list,
                         self._path_list, self._blockage_list, self._boundary_list,
                         self._polygon_list, self._round_list,
                         self._sim_list, self._source_list, self._monitor_list):
            obj.move_by(dx=dx, dy=dy, unit_mode=unit_mode)

    def add_round(self,
                  round_obj: "PhotonicRound",
                  ):
        """Add a new (arrayed) round shape.

        Parameters
        ----------
        round_obj : BPG.objects.PhotonicRound
            the round object to add.
        """
        if self._finalized:
            raise Exception('Layout is already finalized.')

        self._round_list.append(round_obj)

    def add_path(self,
                 path: "PhotonicPath",
                 ):
        BagLayout.add_path(self, path)

    def add_sim_obj(self,
                    sim_obj,
                    ):
        """ Add a new Lumerical simulation object to the db """
        if self._finalized:
            raise Exception('Layout is already finalized.')

        self._sim_list.append(sim_obj)

    def add_source_obj(self,
                       source_obj,
                       ):
        """ Add a new Lumerical source object to the db """
        if self._finalized:
            raise Exception('Layout is already finalized.')

        self._source_list.append(source_obj)

    def add_monitor_obj(self,
                        monitor_obj,
                        ):
        """ Add a new Lumerical monitor object to the db """
        if self._finalized:
            raise Exception('Layout is already finalized.')

        self._monitor_list.append(monitor_obj)


class PhotonicTechInfo(object, metaclass=abc.ABCMeta):
    def __init__(self, photonic_tech_params, resolution, layout_unit):
        self._resolution = resolution
        self._layout_unit = layout_unit
        self.photonic_tech_params = photonic_tech_params

        # Get the main working directory to be used for all relative paths
        root_path = os.environ['BAG_WORK_DIR']

        # Layermap
        self.layermap_path = self.photonic_tech_params.get(
            'layermap',
            root_path + '/BPG/examples/tech/BPG_tech_files/gds_map.yaml'
        )
        if not Path(self.layermap_path).is_file():
            raise ValueError(f'layermap file {self.layermap_path} does not exist!')
        print(f'Loading layermap from {self.layermap_path}')

        # LSF Export Map
        # TODO: allow this to fail?
        self.lsf_export_path = self.photonic_tech_params.get(
            'lsf_dataprep_filepath',
            root_path + '/BPG/examples/tech/BPG_tech_files/lumerical_map.yaml'
        )
        if not Path(self.lsf_export_path).is_file():
            raise ValueError(f'layermap file {self.lsf_export_path} does not exist!')
        print(f'Loading lumerical export config from {self.lsf_export_path}')

        # Dataprep routine
        # TODO: allow this to fail?
        self.dataprep_routine_filepath = self.photonic_tech_params.get(
            'dataprep_routine_filepath',
            root_path + '/BPG/examples/tech/BPG_tech_files/dataprep.yaml'
        )
        if not Path(self.dataprep_routine_filepath).is_file():
            raise ValueError(f'dataprep file {self.dataprep_routine_filepath} does not exist!')
        print(f'Loading dataprep procedure from {self.dataprep_routine_filepath}')

        # TODO: Create a dummy dataprep params file so that we can do a file exists check
        self.dataprep_parameters_filepath = self.photonic_tech_params.get(
            'dataprep_parameters_filepath',
            None
        )
        print(f'Loading dataprep parameters from {self.dataprep_parameters_filepath}')

        self.dataprep_skill_path = self.photonic_tech_params.get(
            'dataprep_skill_path',
            root_path + 'BPG/BPG/dataprep_skill.il'
        )

        self.calibre_dataprep_runset_template = self.photonic_tech_params.get(
            'dataprep_calibre_runset_template',
            None
        )

        self.plvs_runset_template = self.photonic_tech_params.get(
            'plvs_runset_template',
            None
        )

        # Dataprep defaults to keeping labels at all depths of hierarchy present in post-dataprep output
        # Can be overwritten in user yaml
        self.dataprep_label_depth = self.photonic_tech_params.get(
            'dataprep_label_depth',
            -1
        )



        self.layer_map = None
        self.via_info = None
        self.lsf_export_parameters = None
        self.dataprep_parameters = None
        self.global_dataprep_size_amount = None
        self.global_grid_size = None
        self.global_rough_grid_size = None
        self.dataprep_routine_data = None

        self.load_tech_files()

    def load_tech_files(self):
        with open(self.layermap_path, 'r') as f:
            layer_info = yaml.full_load(f)
            self.layer_map = layer_info['layer_map']
            self.via_info = layer_info['via_info']

        with open(self.lsf_export_path, 'r') as f:
            self.lsf_export_parameters = yaml.full_load(f)

        if self.dataprep_parameters_filepath:
            with open(self.dataprep_parameters_filepath, 'r') as f:
                self.dataprep_parameters = yaml.full_load(f)
        else:
            self.dataprep_parameters = None
            logging.warning('Warning: dataprep_parameters_filepath not specified in tech config. '
                            'Dataprep and DRC lookup functions may not work.')

        if self.dataprep_routine_filepath:
            with open(self.dataprep_routine_filepath, 'r') as f:
                self.dataprep_routine_data = yaml.full_load(f)
            self.global_dataprep_size_amount = self.dataprep_routine_data['GlobalDataprepSizeAmount']
            self.global_grid_size = self.dataprep_routine_data['GlobalGridSize']
            self.global_rough_grid_size = self.dataprep_routine_data['GlobalRoughGridSize']
        else:
            self.dataprep_routine_data = None
            logging.warning('Warning: dataprep_routine_filepath not specified in tech config. '
                            'Dataprep and DRC lookup functions may not work.')

    ''' 
    Default Layer Properties 
    
    These properties make it easy for generator developers to reference tech-specific layers and properties in
    a generic way.
    '''

    @property
    def waveguide_layer(self) -> "layer_or_lpp_type":
        raise NotImplementedError("Please specify the default waveguide layer in your tech file to support this "
                                  "property")

    @property
    def waveguide_width(self) -> float:
        raise NotImplementedError("Please specify the default waveguide width in your tech class to support this "
                                  "property")

    @abc.abstractmethod
    def min_width_unit(self,
                       layer: "layer_or_lpp_type",
                       ) -> int:
        """
        Returns the minimum width (in resolution units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_width_unit : float
            The minimum width in resolution units for shapes on the layer
        """

    @abc.abstractmethod
    def min_width(self,
                  layer: "layer_or_lpp_type",
                  ) -> float:
        """
        Returns the minimum width (in layout units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_width : float
            The minimum width for shapes on the layer
        """

    @abc.abstractmethod
    def min_space_unit(self,
                       layer: "layer_or_lpp_type",
                       ) -> int:
        """
        Returns the minimum space (in resolution units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_space_unit : float
            The minimum space in resolution units for shapes on the layer
        """

    @abc.abstractmethod
    def min_space(self,
                  layer: "layer_or_lpp_type",
                  ) -> float:
        """
        Returns the minimum space (in layout units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_space : float
            The minimum space for shapes on the layer
        """

    @abc.abstractmethod
    def max_width_unit(self,
                       layer: "layer_or_lpp_type",
                       ) -> int:
        """
        Returns the maximum width (in resolution units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        max_width_unit : float
            The maximum width in resolution units for shapes on the layer
        """

    @abc.abstractmethod
    def max_width(self,
                  layer: "layer_or_lpp_type",
                  ) -> float:
        """
        Returns the maximum width (in layout units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        max_width : float
            The maximum width for shapes on the layer
        """

    @abc.abstractmethod
    def min_area_unit(self,
                      layer: "layer_or_lpp_type",
                      ) -> int:
        """
        Returns the minimum area (in resolution units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_area_unit : float
            The minimum area in resolution units for shapes on the layer
        """

    @abc.abstractmethod
    def min_area(self,
                 layer: "layer_or_lpp_type",
                 ) -> float:
        """
        Returns the minimum area (in layout units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_area : float
            The minimum area for shapes on the layer
        """

    @abc.abstractmethod
    def min_edge_length_unit(self,
                             layer: "layer_or_lpp_type",
                             ) -> int:
        """
        Returns the minimum edge length (in resolution units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_edge_length : float
            The minimum edge length in resolution units for shapes on the layer
        """

    @abc.abstractmethod
    def min_edge_length(self,
                        layer: "layer_or_lpp_type",
                        ) -> float:
        """
        Returns the minimum edge length (in layout units) for a given layer.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        min_edge_length : float
            The minimum edge length for shapes on the layer
        """

    @abc.abstractmethod
    def height_unit(self,
                    layer: "layer_or_lpp_type",
                    ) -> int:
        """
        Returns the height from the top of the silicon region (defined as 0) to the bottom surface of the given
        layer, in resolution units.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        height_unit : float
            The height of the bottom surface in resolution units for shapes on the layer
        """

    @abc.abstractmethod
    def height(self,
               layer: "layer_or_lpp_type",
               ) -> float:
        """
        Returns the height from the top of the silicon region (defined as 0) to the bottom surface of the given
        layer, in layout units.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        height : float
            The height of the bottom surface for shapes on the layer
        """

    @abc.abstractmethod
    def thickness_unit(self,
                       layer: "layer_or_lpp_type",
                       ) -> int:
        """
        Returns the thickness of the layer, in resolution units

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        thickness_unit : float
            The thickness in resolution units for shapes on the layer
        """

    @abc.abstractmethod
    def thickness(self,
                  layer: "layer_or_lpp_type",
                  ) -> float:
        """
        Returns the thickness of the layer, in layout units.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        thickness : float
            The thickness of shapes on the layer
        """

    @abc.abstractmethod
    def sheet_resistance(self,
                         layer: layer_or_lpp_type,
                         ) -> float:
        """
        Returns the sheet resistance of the layer, in Ohm/sq.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer name or LPP of the layer.

        Returns
        -------
        rs : float
            The sheet resistance of the layer in Ohm/sq
        """


class DummyPhotonicTechInfo(PhotonicTechInfo):
    """
    A dummy PhotonicTechInfo class

    Parameters
    ----------

    """
    def __init__(self, photonic_tech_params, resolution, layout_unit):
        PhotonicTechInfo.__init__(self, {}, resolution, layout_unit)

    def min_area(self,
                 layer: "layer_or_lpp_type",
                 ):
        return 0

    def min_area_unit(self,
                      layer: "layer_or_lpp_type",
                      ):
        return 0

    def min_edge_length(self,
                        layer: "layer_or_lpp_type",
                        ):
        return 0

    def min_edge_length_unit(self,
                             layer: "layer_or_lpp_type",
                             ):
        return 0

    def min_space(self,
                  layer: "layer_or_lpp_type",
                  ):
        return 0

    def min_space_unit(self,
                       layer: "layer_or_lpp_type",
                       ):
        return 0

    def min_width(self,
                  layer: "layer_or_lpp_type",
                  ):
        return 0

    def min_width_unit(self,
                       layer: "layer_or_lpp_type",
                       ):
        return 0

    def max_width(self,
                  layer: "layer_or_lpp_type",
                  ):
        return 0

    def max_width_unit(self,
                       layer: "layer_or_lpp_type",
                       ):
        return 0

    def height(self,
               layer: "layer_or_lpp_type",
               ):
        return 0

    def height_unit(self,
                    layer: "layer_or_lpp_type",
                    ):
        return 0

    def thickness(self,
                  layer: "layer_or_lpp_type",
                  ):
        return 0

    def thickness_unit(self,
                       layer: "layer_or_lpp_type",
                       ):
        return 0

    def sheet_resistance(self,
                         layer: "layer_or_lpp_type",
                         ) -> float:
        return 0
