# general imports
import abc
import numpy as np
import logging
import math
import copy
import warnings
import importlib
import yaml

# bag imports
import bag.io
from bag.layout.template import TemplateBase
from bag.layout.util import transform_point, BBox, BBoxArray, transform_loc_orient
from BPG.photonic_core import PhotonicBagLayout

# Photonic object imports
from BPG.port import PhotonicPort
from BPG.objects import PhotonicRect, PhotonicPolygon, PhotonicAdvancedPolygon, PhotonicInstance, PhotonicRound, \
    PhotonicPath

# Typing imports
from typing import TYPE_CHECKING, Dict, Any, List, Set, Optional, Tuple, Iterable
from BPG.bpg_custom_types import *

if TYPE_CHECKING:
    from BPG.bpg_custom_types import layer_or_lpp_type, lpp_type, coord_type, dim_type
    from bag.layout.objects import Instance
    from BPG.photonic_core import PhotonicTechInfo
    from BPG.db import PhotonicTemplateDB


class PhotonicTemplateBase(TemplateBase, metaclass=abc.ABCMeta):
    def __init__(self,
                 temp_db: "PhotonicTemplateDB",
                 lib_name: str,
                 params: Dict[str, Any],
                 used_names: Set[str],
                 **kwargs,
                 ) -> None:
        use_cybagoa: bool = kwargs.get('use_cybagoa', False)
        assert isinstance(use_cybagoa, bool)

        TemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        logging.debug(f'Initializing master {self.__class__.__name__}')
        self._photonic_ports: Dict[str, PhotonicPort] = {}
        self._layout = PhotonicBagLayout(self._grid, use_cybagoa=use_cybagoa)
        if temp_db.photonic_tech_info is None:
            raise ValueError("temp_db.photonic_tech_info was None")
        self.photonic_tech_info: 'PhotonicTechInfo' = temp_db.photonic_tech_info

        # Feature flag that when False, prevents users from creating rotated masters that contain other
        # rotated masters
        self.allow_rotation_hierarchy = False

        # This stores the angular offset from the cardinal axes that this master is drawn at
        self._angle = self.params.get('_angle', 0.0)
        self._layout.mod_angle = self.angle

    @property
    def angle(self) -> float:
        return self._angle

    @abc.abstractmethod
    def draw_layout(self) -> None:
        pass

    def photonic_ports_names_iter(self) -> Iterable[str]:
        return self._photonic_ports.keys()

    def add_obj(self, obj) -> None:
        """
        Takes a provided layout object and adds it to the db. Automatically detects what type of object is
        being added, and sends it to the appropriate category in the layoutDB.
        Also accepts a list of layout objects.

        TODO: Provide support for directly adding photonic ports and simulation objects
        """
        if isinstance(obj, PhotonicRect):
            self._layout.add_rect(obj)
        elif isinstance(obj, PhotonicPolygon):
            self._layout.add_polygon(obj)
        elif isinstance(obj, PhotonicRound):
            self._layout.add_round(obj)
        elif isinstance(obj, PhotonicPath):
            self._layout.add_path(obj)
        elif isinstance(obj, PhotonicAdvancedPolygon):
            self._layout.add_polygon(obj)
        elif isinstance(obj, PhotonicInstance):
            self._layout.add_instance(obj)
        elif isinstance(obj, list):
            for layout_obj in obj:
                self.add_obj(layout_obj)
        else:
            raise ValueError("{} is not a valid layout object type, and cannot be added to the db".format(type(obj)))

    def add_rect(self,
                 layer: layer_or_lpp_type,
                 coord1: coord_type = None,
                 coord2: coord_type = None,
                 bbox: Union[BBox, BBoxArray] = None,
                 nx: int = 1,
                 ny: int = 1,
                 spx: dim_type = 0,
                 spy: dim_type = 0,
                 unit_mode: bool = False,
                 ) -> PhotonicRect:
        """
        Creates a new rectangle based on the user provided arguments and adds it to the db. User can either provide a
        pair of coordinates representing opposite corners of the rectangle, or a BBox/BBoxArray. This rectangle can
        also be arrayed with the number and spacing parameters.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            the layer name, or the (layer, purpose) pair.
        coord1 : Tuple[Union[int, float], Union[int, float]]
            point defining one corner of rectangle boundary.
        coord2 : Tuple[Union[int, float], Union[int, float]]
            opposite corner from coord1 defining rectangle boundary.
        bbox : bag.layout.util.BBox or bag.layout.util.BBoxArray
            the base bounding box.  If this is a BBoxArray, the BBoxArray's
            arraying parameters are used.
        nx : int
            number of columns.
        ny : int
            number of rows.
        spx : float
            column pitch.
        spy : float
            row pitch.
        unit_mode : bool
            True if layout dimensions are specified in resolution units.

        Returns
        -------
        rect : PhotonicRect
            the added rectangle.

        """
        # If coordinates are provided, use them to define a BBox for the rectangle
        if coord1 is not None or coord2 is not None:
            # Ensure both points are defined
            if coord1 is None or coord2 is None:
                raise ValueError("If defining by two points, both must be specified.")

            # Define the BBox
            bbox = BBox(
                left=min(coord1[0], coord2[0]),
                right=max(coord1[0], coord2[0]),
                bottom=min(coord1[1], coord2[1]),
                top=max(coord1[1], coord2[1]),
                resolution=self.grid.resolution,
                unit_mode=unit_mode
            )

        rect = PhotonicRect(layer, bbox, nx=nx, ny=ny, spx=spx, spy=spy, unit_mode=unit_mode)
        self._layout.add_rect(rect)
        self._used_tracks.record_rect(self.grid, layer, rect.bbox_array)
        return rect

    def add_polygon(self,
                    layer: layer_or_lpp_type = None,
                    points: List[coord_type] = None,
                    resolution: Optional[float] = None,
                    unit_mode: bool = False,
                    ) -> PhotonicPolygon:
        """
        Creates a new polygon from the user provided points and adds it to the db

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            the layer of the polygon
        resolution : float
            the layout grid resolution
        points : List[coord_type]
            the points defining the polygon
        unit_mode : bool
            True if the points are given in resolution units

        Returns
        -------
        polygon : PhotonicPolygon
            the added polygon object
        """
        # Ensure proper arguments are passed
        if layer is None or points is None:
            raise ValueError("If adding polygon by layer and points, both layer and points list must be defined.")

        if resolution is None:
            resolution = self.grid.resolution
            assert isinstance(resolution, float)

        polygon = PhotonicPolygon(
            resolution=resolution,
            layer=layer,
            points=points,
            unit_mode=unit_mode,
        )

        self._layout.add_polygon(polygon)
        return polygon

    def add_round(self,
                  layer: layer_or_lpp_type,
                  resolution: float,
                  rout: dim_type,
                  center: coord_type = (0, 0),
                  rin: dim_type = 0,
                  theta0: dim_type = 0,
                  theta1: dim_type = 360,
                  nx: int = 1,
                  ny: int = 1,
                  spx: dim_type = 0,
                  spy: dim_type = 0,
                  unit_mode: bool = False
                  ):
        """ Creates a PhotonicRound object based on the provided arguments and adds it to the db """
        new_round = PhotonicRound(layer=layer,
                                  resolution=resolution,
                                  rout=rout,
                                  center=center,
                                  rin=rin,
                                  theta0=theta0,
                                  theta1=theta1,
                                  nx=nx,
                                  ny=ny,
                                  spx=spx,
                                  spy=spy,
                                  unit_mode=unit_mode)
        self._layout.add_round(new_round)
        return new_round

    def add_path(self,
                 layer: layer_or_lpp_type,
                 width: dim_type,
                 points: List[coord_type],
                 resolution: float,
                 unit_mode: bool = False,
                 ) -> PhotonicPath:
        """
        Create a PhotonicPath object based on the provided arguments
        and add it to the db.
        """
        new_path = PhotonicPath(layer=layer,
                                width=width,
                                points=points,
                                resolution=resolution,
                                unit_mode=unit_mode)
        self._layout.add_path(new_path)
        return new_path

    def finalize(self):
        """ Call the old finalize method, but then also grab the bounding box from the layout content """
        TemplateBase.finalize(self)
        if self._layout._inst_list != [] and self.angle != 0:
            logging.warning(f"{self.__class__.__name__} requires hierarchical non-cardinal rotation. This feature is "
                            f"currently experimental. Please raise an issue if incorrect results occur")
        self.prim_bound_box = self._layout.bound_box

    def add_photonic_port(self,
                          name: Optional[str] = None,
                          center: Optional[coord_type] = None,
                          orient: Optional[str] = None,
                          angle: Optional[float] = 0.0,
                          width: Optional[dim_type] = None,
                          layer: Optional[layer_or_lpp_type] = None,
                          overwrite_purpose: bool = False,
                          resolution: Optional[float] = None,
                          unit_mode: bool = False,
                          port: Optional[PhotonicPort] = None,
                          overwrite: bool = False,
                          show: bool = True
                          ) -> PhotonicPort:
        """
        Add a photonic port to the current hierarchy. A PhotonicPort
        object can be passed, or will be constructed if the proper
        arguments are passed to this function.

        Parameters
        ----------
        name :
            name to give the new port
        center :
            (x, y) location of the port
        orient :
            orientation pointing INTO the port
        angle :
            angle of a unit vector pointing into the port. This is used in combination with orient to place the port
        width :
            the port width
        layer :
            the layer on which the port should be added. If only a string, the purpose is defaulted to 'port'
        overwrite_purpose :
            True to overwrite the 'port' purpose if an LPP is passed. If False (default), the purpose of a passed LPP
            is stripped away and the 'port' purpose is used.
        resolution :
            the grid resolution
        unit_mode :
            True if layout dimensions are specified in resolution units
        port :
            the PhotonicPort object to add. This argument can be provided in lieu of all the others.
        overwrite :
            True to add the port with the specified name even if another port with that name already exists in this
            level of the design hierarchy.
        show :
            True to draw the port indicator shape

        Returns
        -------
        port : PhotonicPort
            the added photonic port object
        """
        # TODO: Add support for renaming?
        # TODO: Remove force append?
        # Create a temporary port object unless one is passed as an argument
        if port is None:
            if layer is None:
                raise TypeError("layer is required when creating a port")
            if name is None:
                raise TypeError("name is required when creating a port")
            if center is None:
                raise TypeError("center is required when creating a port")
            if orient is None:
                raise TypeError("orient is required when creating a port")
            if width is None:
                raise TypeError("width is required when creating a port")
            if angle is None:
                raise TypeError("angle is required when creating a port")

            if resolution is None:
                resolution = self.grid.resolution
                assert isinstance(resolution, float)

            if overwrite_purpose:
                if isinstance(layer, str):
                    raise ValueError(f'Calling add_photonic_port with overwrite_purpose=True requires a LPP to be '
                                     f'pased in the \'layer\' argument.')
                else:
                    layer = (layer[0], layer[1])
            else:
                if isinstance(layer, str):
                    layer = (layer, 'port')
                else:
                    layer = (layer[0], 'port')

            # Check arguments for validity
            if all([name, center, orient, width, layer]) is False:
                raise ValueError('User must define name, center, orient, width, and layer')

            port = PhotonicPort(name=name,
                                center=center,
                                orient=orient,
                                angle=angle,
                                width=width,
                                layer=layer,
                                resolution=resolution,
                                unit_mode=unit_mode)

        # Add port to port list. If name already is taken, remap port if overwrite is true
        if port.name not in self._photonic_ports.keys() or overwrite:
            self._photonic_ports[port.name] = port
        else:
            raise ValueError('Port "{}" already exists in cell.'.format(port.name))

        if port.name is not None:
            self.add_label(
                label=port.name,
                layer=port.layer,
                bbox=BBox(
                    bottom=port.center_unit[1],
                    left=port.center_unit[0],
                    top=port.center_unit[1] + self.grid.resolution,
                    right=port.center_unit[0] + self.grid.resolution,
                    resolution=port.resolution,
                    unit_mode=True
                ),
            )

        if show is True:
            # Draw port shape
            center_vec = port.center_unit
            orient_vec = np.array(port.width_vec_unit)
            perp_vec = np.array([-1 * orient_vec[1], orient_vec[0]])

            self.add_polygon(
                layer=port.layer,
                points=[center_vec,
                        center_vec + orient_vec / 2 + perp_vec / 2,
                        center_vec + 2 * orient_vec,
                        center_vec + orient_vec / 2 - perp_vec / 2,
                        center_vec],
                resolution=port.resolution,
                unit_mode=True,
            )

        return port

    def has_photonic_port(self,
                          port_name: str,
                          ) -> bool:
        """Checks if the given port name exists in the current hierarchy level.

        Parameters
        ----------
        port_name : str
            the name of the port

        Returns
        -------
            : boolean
            true if port exists in current hierarchy level
        """
        return port_name in self._photonic_ports

    def get_photonic_port(self,
                          port_name: Optional[str] = '',
                          ) -> PhotonicPort:
        """ Return the photonic port object with the given name.

        Parameters
        ----------
        port_name : Optional[str]
            the photonic port terminal name. If None or empty, check if this photonic template has only one port,
            and return it

        Returns
        -------
        port : PhotonicPort
            The photonic port object
        """
        if not port_name:
            if len(self._photonic_ports) == 1:
                port_name = list(self._photonic_ports.keys())[0]
            else:
                raise ValueError(
                    'Template "{}" has {} ports != 1. Must get port by name.'.format(self.__class__.__name__,
                                                                                     len(self._photonic_ports)
                                                                                     )
                )
        else:
            if not self.has_photonic_port(port_name):
                raise ValueError('Port "{}" does not exist in {}'.format(port_name, self.__class__.__name__))
        return self._photonic_ports[port_name]

    def add_instance(self: "PhotonicTemplateBase",
                     master: "PhotonicTemplateBase",
                     inst_name: Optional[str] = None,
                     loc: coord_type = (0, 0),
                     orient: str = "R0",
                     angle: float = 0.0,
                     reflect: bool = False,
                     nx: int = 1,
                     ny: int = 1,
                     spx: dim_type = 0,
                     spy: dim_type = 0,
                     unit_mode: bool = False,
                     ) -> PhotonicInstance:
        """Adds a new (arrayed) instance to layout.

        Parameters
        ----------
        master :
            the master template object.
        inst_name :
            instance name.  If None or an instance with this name already exists,
            a generated unique name is used.
        loc :
            instance location.
        orient :
            instance orientation.  Defaults to "R0"
        angle :
            angle in radians to rotate this instance
        reflect :
            True to mirror reflect the instance
        nx :
            number of columns.  Must be positive integer.
        ny :
            number of rows.  Must be positive integer.
        spx :
            column pitch.  Used for arraying given instance.
        spy :
            row pitch.  Used for arraying given instance.
        unit_mode :
            True if dimensions are given in resolution units.

        Returns
        -------
        inst : PhotonicInstance
            the added instance.
        """
        res = self.grid.resolution
        if not unit_mode:
            loc = int(round(loc[0] / res)), int(round(loc[1] / res))
            spx = int(round(spx / res))
            spy = int(round(spy / res))

        inst = PhotonicInstance(self.grid, self._lib_name, master, loc=loc, orient=orient, angle=angle,
                                mirrored=reflect, name=inst_name, nx=nx, ny=ny, spx=spx, spy=spy, unit_mode=True)

        self._layout.add_instance(inst)
        return inst

    def add_sim_obj(self, sim_obj):
        """ Add a new Lumerical simulation object to the db """
        self._layout.add_sim_obj(sim_obj)

    def add_source_obj(self, source_obj):
        """ Add a new Lumerical source object to the db """
        self._layout.add_source_obj(source_obj)

    def add_monitor_obj(self, monitor_obj):
        """ Add a new Lumerical monitor object to the db """
        self._layout.add_monitor_obj(monitor_obj)

    def add_instances_port_to_port(self,
                                   inst_master: "PhotonicTemplateBase",
                                   instance_port_name: str,
                                   self_port: Optional[PhotonicPort] = None,
                                   self_port_name: Optional[str] = None,
                                   instance_name: Optional[str] = None,
                                   reflect: bool = False,
                                   ) -> PhotonicInstance:
        warnings.warn(f'PhotonicTemplateBase.add_instances_port_to_port was renamed to '
                      f'add_instance_port_to_port (no "s"). '
                      f'The old method name will be removed in V1.0',
                      DeprecationWarning)

        return self.add_instance_port_to_port(
            inst_master=inst_master,
            instance_port_name=instance_port_name,
            self_port=self_port,
            self_port_name=self_port_name,
            instance_name=instance_name,
            reflect=reflect
        )

    def add_instance_port_to_port(self,
                                  inst_master: "PhotonicTemplateBase",
                                  instance_port_name: str,
                                  self_port: Optional[PhotonicPort] = None,
                                  self_port_name: Optional[str] = None,
                                  instance_name: Optional[str] = None,
                                  reflect: bool = False,
                                  ) -> PhotonicInstance:
        """
        Instantiates a new instance of the inst_master template.
        The new instance is placed such that its port named 'instance_port_name' is aligned-with and touching the
        'self_port' or 'self_port_name' port of the current hierarchy level.

        The new instance is rotated about the new instance's master's origin until desired port is aligned.
        Optional reflection is performed after rotation, about the port axis.

        The self port being connected to can be specified either by passing a self_port PhotonicPort object,
        or by passing the self_port_name, which refers to a port that must exist in the current hierarchy level.

        Parameters
        ----------
        inst_master : PhotonicTemplateBase
            the template master to be added
        instance_port_name : str
            the name of the port in the added instance to connect to
        self_port : Optional[PhotonicPort]
            the photonic port object in the current hierarchy to connect to. Has priority over self_port_name
        self_port_name : Optional[str]
            the name of the port in the current hierarchy to connect to
        instance_name : Optional[str]
            the name to give the new instance
        reflect : bool
            True to flip the added instance after rotation

        Returns
        -------
        new_inst : PhotonicInstance
            the newly added instance
        """
        # Get the reference port that we will be aligning the new instance to
        # TODO: If ports dont have same width/layer, do we return error?
        if self_port is None and self_port_name is None:
            raise ValueError('Either self_port or self_port_name must be specified')
        if self_port_name and not self.has_photonic_port(self_port_name):
            raise ValueError('Photonic port ' + self_port_name + ' does not exist in '
                             + self.__class__.__name__)
        if not inst_master.has_photonic_port(instance_port_name):
            raise ValueError('Photonic port ' + instance_port_name + ' does not exist in '
                             + inst_master.__class__.__name__)
        # self_port has priority over self_port_name if both are specified
        if self_port:
            my_port = self_port
        else:
            my_port = self.get_photonic_port(self_port_name)
        new_port = inst_master.get_photonic_port(instance_port_name)

        # Compute the angle that the instance must be rotated by in order to have its port align to my_port
        # Assuming self.angle = 0 We want the port to point to my_port.angle + math.pi
        # Without reflection, inst_master.angle + new_port.angle + diff_angle gives the mod_angle of the
        # newly instances port. If no reflection:
        #   inst_master.angle + new_port.angle + diff_angle = my_port.angle + math.pi
        # if the instance is reflected... -(inst_master.angle + new_port.angle) + diff_angle = my_port.angle + math.pi
        if reflect:
            diff_angle = inst_master.angle + new_port.angle + my_port.angle + math.pi
        else:
            diff_angle = -1 * (inst_master.angle + new_port.angle) + my_port.angle + math.pi

        # Place a rotated PhotonicInstance that is rotated but not in the correct location
        new_inst: "PhotonicInstance" = self.add_instance(
            master=inst_master,
            inst_name=instance_name,
            loc=(0, 0),
            orient='R0',
            angle=diff_angle,
            reflect=reflect,
            unit_mode=True,
        )

        # Translate the new instance
        translation_vec = my_port.center_unit - new_inst.get_photonic_port(instance_port_name).center_unit
        new_inst.move_by(dx=translation_vec[0], dy=translation_vec[1], unit_mode=True)
        return new_inst

    def delete_port(self,
                    port_names: Union[str, List[str]],
                    ) -> None:
        """
        Removes the given ports from this instances list of ports. Raises error if given port does not exist.

        Parameters
        ----------
        port_names : Union[str, List[str]]
        """
        if isinstance(port_names, str):
            port_names = [port_names]

        for port_name in port_names:
            if self.has_photonic_port(port_name):
                del self._photonic_ports[port_name]
            else:
                raise ValueError('Photonic port ' + port_name + ' does not exist in '
                                 + self.__class__.__name__)

    def update_port(self):
        # TODO: Implement me.  Deal with matching here?
        pass

    def _get_unused_port_name(self,
                              port_name: Optional[str],
                              ) -> str:
        """Returns a new unique name for a port in the current hierarchy level

        Parameters
        ----------
        port_name : Optional[str]
            base port name. If no value is supplied, 'PORT' is used as the base name

        Returns
        -------
        new_name : str
            new unique port name
        """

        if port_name is None:
            port_name = 'PORT'
        new_name = port_name
        if port_name in self._photonic_ports:
            cnt = 0
            new_name = port_name + '_' + str(cnt)
            while new_name in self._photonic_ports:
                cnt += 1
                new_name = port_name + '_' + str(cnt)

        return new_name

    def extract_photonic_ports(self,
                               inst: Union[PhotonicInstance, "Instance"],
                               port_names: Optional[Union[str, List[str]]] = None,
                               port_renaming: Optional[Union[str, List[str], Dict[str, str]]] = None,
                               show: bool = True,
                               ) -> List["PhotonicPort"]:
        """
        Brings ports from lower level of hierarchy to the current hierarchy level

        Parameters
        ----------
        inst : PhotonicInstance
            the instance that contains the ports to be extracted
        port_names : Optional[Union[str, List[str]]
            the port name or list of port names re-export. If not supplied, all ports of the inst will be extracted
        port_renaming : Optional[Dict[str, str]]
            a dictionary containing key-value pairs mapping inst's port names (key)
            to the new desired port names (value).
            If not supplied, extracted ports will be given their original names
        show : bool
        """
        if port_names is None:
            port_names = list(inst.master.photonic_ports_names_iter())

        if isinstance(port_names, str):
            port_names = [port_names]

        if port_renaming is None:
            port_renaming = {}

        if isinstance(port_renaming, str):
            port_renaming = [port_renaming]

        if isinstance(port_renaming, list):
            if len(port_renaming) != len(port_names):
                raise ValueError(f'If port_renaming is a list, must be same length as port_names')

        ports_out = []

        for ind, port_name in enumerate(port_names):
            old_port = inst[port_name]
            translation = inst.location_unit
            orientation = inst.orientation

            # Get new desired name
            if isinstance(port_renaming, dict):
                if port_name in port_renaming.keys():
                    new_name = port_renaming[port_name]
                else:
                    new_name = port_name
            else:
                new_name = port_renaming[ind]

            # If name is already used
            if new_name in self._photonic_ports:
                # Append unique number
                new_name = self._get_unused_port_name(new_name)
            ports_out.append(
                self.add_photonic_port(
                    name=new_name,
                    center=old_port.center_unit.tolist(),
                    orient='R0',
                    angle=old_port.angle,
                    width=old_port.width_unit,
                    layer=old_port.layer,
                    unit_mode=True,
                    show=show
                )
            )

        return ports_out

    def _find_metal_pairs(self,
                          bot_layer,
                          top_layer,
                          metal_info,
                          ):
        """
        Creates an ordered list of metal pairs required to generate a via stack between rect1 and rect2

        Metal ordering algorithm
        ------------------------
        1) Map each rectangle's layer to index in the metal stack
        2) Determine which rect is lower/higher in the stack based on the index
        3) Add each metal pair in the stack between rect1 and rect2 to the metal_pair list, starting with the lower
        rectangle and traversing up the metal stack
        """
        metal_pairs = []

        # 1) Map each rectangle layer to index in the metal stack
        index_bottom = metal_info[bot_layer]['index']
        index_top = metal_info[top_layer]['index']

        # Check if layer order needs to be swapped
        if index_bottom > index_top:
            top_layer, bot_layer = bot_layer, top_layer

        top_layer_fixed = metal_info[top_layer].get('base_name', top_layer)

        # 2) Add each layer pair (layer names) between bot_metal and top_metal to a metal_pair list
        cur_bot = metal_info[bot_layer].get('base_name', bot_layer)
        while True:
            # Try to find the metal layer that the current bot layer connects to
            try:
                cur_top = metal_info[cur_bot]['connect_to']
            except KeyError:
                raise ValueError(f'Could not complete via stack from {bot_layer} to {top_layer}')
            metal_pairs.append((cur_bot, cur_top))
            if cur_top == top_layer_fixed:
                # If we have made it from the bottom to the top of the via stack, break out of the loop
                break
            else:
                # Otherwise continue traversing the via stack
                cur_bot = cur_top
        return metal_pairs

    def add_via_stack(self,
                      bot_layer: layer_or_lpp_type,
                      top_layer: layer_or_lpp_type,
                      loc: coord_type,
                      min_area_on_bot_top_layer: bool = False,
                      unit_mode: bool = False,
                      ):
        """
        Adds a via stack with one via in each layer at the provided location.
        All intermediate layers will be enclosed with an enclosure that satisfies both via rules and min area rules

        Parameters
        ----------
        bot_layer : Union[str, Tuple[str, str]]
            Layer name or layer LPP of the bottom layer in the via stack
        top_layer : Union[str, Tuple[str, str]]
            Layer name or layer LPP of the top layer in the via stack
        loc : coord_type
            Coordinate of the center of the via stack
        min_area_on_bot_top_layer : bool
            True to have enclosures on top and bottom layer satisfy minimum area constraints
        unit_mode : bool
            True if input arguments are specified in layout resolution units

        Returns
        -------

        """
        # If the bottom layer and top layer are the same, do not draw any vias
        if bot_layer == top_layer:
            return

        if not unit_mode:
            loc = (int(round(loc[0] / self.grid.resolution)), int(round(loc[1] / self.grid.resolution)))

        if isinstance(bot_layer, tuple):
            bot_layer = bot_layer[0]
        if isinstance(top_layer, tuple):
            top_layer = top_layer[0]

        bot_layer = bag.io.fix_string(bot_layer)
        top_layer = bag.io.fix_string(top_layer)

        metal_info = self.photonic_tech_info.dataprep_parameters['MetalStack']

        metal_pairs = self._find_metal_pairs(bot_layer=bot_layer,
                                             top_layer=top_layer,
                                             metal_info=metal_info,
                                             )

        bot_layer_id_global = self.grid.tech_info.get_layer_id(metal_pairs[0][0])
        top_layer_id_global = self.grid.tech_info.get_layer_id((metal_pairs[-1][1]))

        for bot_lay_name, top_lay_name in metal_pairs:
            bot_lay_type = self.grid.tech_info.get_layer_type(bot_lay_name)
            top_lay_type = self.grid.tech_info.get_layer_type(top_lay_name)
            bot_lay_id = self.grid.tech_info.get_layer_id(bot_lay_name)

            via_name = self.grid.tech_info.get_via_name(bot_lay_id)
            via_type_list = self.grid.tech_info.get_via_types(bmtype=bot_lay_type,
                                                              tmtype=top_lay_type)

            for via_type, weight in via_type_list:
                try:
                    (sp, sp2_list, sp3, sp6, dim, enc_b_list, arr_enc_b, arr_test_b) = self.grid.tech_info.get_via_drc_info(
                        vname=via_name,
                        vtype=via_type,
                        mtype=bot_lay_type,
                        mw_unit=0,
                        is_bot=True,
                    )

                    (_, _, _, _, _, enc_t_list, arr_enc_t, arr_test_t) = self.grid.tech_info.get_via_drc_info(
                        vname=via_name,
                        vtype=via_type,
                        mtype=top_lay_type,
                        mw_unit=0,
                        is_bot=True,
                    )
                # Didnt get valid via info
                except ValueError:
                    continue

                # Want to use the via with symmetric enclosure, if available.
                enc_b = enc_b_list[0]
                enc_t = enc_t_list[0]
                for enc in enc_b_list:
                    if enc[0] == enc[1]:
                        enc_b = enc
                        break
                for enc in enc_t_list:
                    if enc[0] == enc[1]:
                        enc_t = enc

                # Fix minimum area violations:
                if bot_lay_id > bot_layer_id_global or min_area_on_bot_top_layer:
                    min_area_unit = self.grid.tech_info.get_min_area_unit(bot_lay_type)
                    if (2 * enc_b[0] + dim[0]) * (2 * enc_b[1] + dim[1]) < min_area_unit:
                        min_side_len_unit = int(np.ceil(np.sqrt(min_area_unit)))
                        enc_b = [np.ceil((min_side_len_unit - dim[0]) / 2), np.ceil((min_side_len_unit - dim[1]) / 2)]

                if bot_lay_id + 1 < top_layer_id_global or min_area_on_bot_top_layer:
                    min_area_unit = self.grid.tech_info.get_min_area_unit(top_lay_type)
                    if (2 * enc_t[0] + dim[0]) * (2 * enc_t[1] + dim[1]) < min_area_unit:
                        min_side_len_unit = int(np.ceil(np.sqrt(min_area_unit)))
                        enc_t = [np.ceil((min_side_len_unit - dim[0]) / 2), np.ceil((min_side_len_unit - dim[1]) / 2)]

                self.add_via_primitive(
                    via_type=self.grid.tech_info.get_via_id(bot_layer=bot_lay_name, top_layer=top_lay_name),
                    loc=loc,
                    num_rows=1,
                    num_cols=1,
                    sp_rows=0,
                    sp_cols=0,
                    enc1=[enc_b[0], enc_b[0], enc_b[1], enc_b[1]],
                    enc2=[enc_t[0], enc_t[0], enc_t[1], enc_t[1]],
                    orient='R0',
                    cut_width=dim[0],
                    cut_height=dim[1],
                    nx=1,
                    ny=1,
                    spx=0,
                    spy=0,
                    unit_mode=True,
                )

    def add_via_stack_by_ind(self,
                             bot_layer_ind: int,
                             top_layer_ind: int,
                             loc: coord_type,
                             min_area_on_bot_top_layer: bool = False,
                             unit_mode: bool = False,
                             ):
        """
        Adds a stack of vias from the metal at the bot_layer_ind index to the metal at the top_layer_ind index.

        Parameters
        ----------
        bot_layer_ind : int
            Index of the bottom layer of the via stack
        top_layer_ind : int
            Index of the top layer of the via stack
        loc : coord_type
            Coordinate of the center of the via stack
        min_area_on_bot_top_layer : bool
            True to have enclosures on top and bottom layer satisfy minimum area constraints
        unit_mode : bool
            True if input arguments are specified in layout resolution units

        Returns
        -------

        """
        return self.add_via_stack(
            bot_layer=self.grid.tech_info.get_layer_name(bot_layer_ind),
            top_layer=self.grid.tech_info.get_layer_name(top_layer_ind),
            loc=loc,
            min_area_on_bot_top_layer=min_area_on_bot_top_layer,
            unit_mode=unit_mode
        )

    def new_template_with(self, angle=0.0, **kwargs):
        """
        Create a new template with the given parameters

        This method will update the parameter values with the given kwargs, then create a new template with those
        parameters and return it. This procedure also takes on the angle provided by the caller. Unlike
        self.new_template the masters initial angle is completely ignored. This method should only be called by
        PhotonicInstance

        Parameters
        ----------
        angle : float
            angle in radians fo the rotation to be performed
        kwargs : dict
            a dictionary of new parameter values

        Returns
        -------
        master : PhotonicTemplateBase
            Newly created master from the given parameters
        """
        # Create a new parameter dictionary based on the provided changes
        new_params = copy.deepcopy(self.params)
        for key, val in kwargs.items():
            if key in new_params:
                new_params[key] = val

        # Move to populate_params? This deletes the old angle and sets it to the provided value via hidden params
        new_params.pop('_angle', None)
        return TemplateBase.new_template(self,
                                         params=new_params,
                                         temp_cls=self.__class__,
                                         hidden_params={'_angle': angle},
                                         **kwargs
                                         )



    def new_template_with_spec_file(self, 
                                    path_to_yaml,
                                    **kwargs):
        """
        """
        #
        # Should I care about unsafe load?
        with open( path_to_yaml ) as yaml_file:
            yaml_file_load = yaml.load(yaml_file)

        photonic_module = importlib.import_module(yaml_file_load['layout_package'])
        photonic_class = yaml_file_load['layout_class']
        temp_cls = getattr(photonic_module, photonic_class)

        #params = copy.deepcopy(yaml_file_load['layout_params'])
        params = yaml_file_load['layout_params']

        #import pdb
        #pdb.set_trace()

        return TemplateBase.new_template(self,
                                         params=params,
                                         temp_cls=temp_cls,
                                         **kwargs
                                         )
