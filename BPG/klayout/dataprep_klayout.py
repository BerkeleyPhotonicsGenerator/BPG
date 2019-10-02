import logging
import re
from collections import UserList
import warnings

from typing import TYPE_CHECKING, Tuple, List, Union, Dict, Pattern, Any

if TYPE_CHECKING:
    from BPG.photonic_core import PhotonicTechInfo
    from bag.layout.routing import RoutingGrid
    from BPG.bpg_custom_types import lpp_type

################################################################################
# define parameters for testing
################################################################################
# Create a separate logger for large dataprep debug information
dataprep_logger = logging.getLogger('dataprep')


class LayerInfo(dict):
    items = ['cad_layer', 'cad_purpose', 'gds_layer', 'gds_purpose', 'min_width', 'min_space', 'base_name', 'index',
             'ignore', 'bypass']

    def __init__(self,
                 **kwargs: Any,
                 ) -> None:
        # Check that the kwargs are valid. If not, raise an error
        for key in kwargs:
            if key not in self.items:
                raise ValueError(f'Unknown key: {key}')

        # If key is not specified, content list should have an empty list, not None
        kv_iter = ((key, kwargs.get(key, None)) for key in self.items)
        dict.__init__(self, kv_iter)
        self['index'] = 0
        self['ignore'] = False
        self['bypass'] = False

    @property
    def cad_layer(self) -> str:
        return self['cad_layer']

    @property
    def cad_purpose(self) -> str:
        return self['cad_purpose']

    @property
    def cad_lpp(self) -> "lpp_type":
        return self['cad_layer'], self['cad_purpose']

    @property
    def gds_layer(self) -> str:
        return self['gds_layer']

    @property
    def gds_purpose(self) -> str:
        return self['gds_purpose']

    @property
    def gds_lpp(self) -> "lpp_type":
        return self['gds_layer'], self['gds_purpose']

    @property
    def min_width(self) -> float:
        return self['min_width']

    @property
    def min_space(self) -> float:
        return self['min_space']

    @property
    def base_name(self) -> str:
        return self['base_name']

    @property
    def index(self) -> int:
        return self['index']

    @property
    def current_name(self) -> str:
        return f'{self["base_name"]}__{self["index"]}'

    def next_name(self) -> str:
        self['index'] += 1
        return f'{self["base_name"]}__{self["index"]}'

    @property
    def bypass(self) -> bool:
        return self['bypass']

    @bypass.setter
    def bypass(self,
               val: bool,
               ):
        if self['ignore']:
            raise ValueError(f'Layers cannot be both bypassed and ignored. Layer {self["cad_lpp"]} violates this.')
        self['bypass'] = val

    @property
    def ignore(self) -> bool:
        return self['ignore']

    @ignore.setter
    def ignore(self,
               val: bool,
               ):
        if self['bypass']:
            raise ValueError(f'Layers cannot be both bypassed and ignored. Layer {self["cad_lpp"]} violates this.')
        self['ignore'] = val


class LayerInfoList(UserList):
    def __init__(self,
                 info_list: List["LayerInfo"] = None,
                 ):
        if info_list is None:
            info_list = []
        UserList.__init__(self, info_list)

    def has_cad_lpp(self,
                    cad_lpp: "lpp_type",
                    ) -> Union["LayerInfo", bool]:
        for info in self:
            if info.cad_lpp == cad_lpp:
                return info
        return False

    def has_gds_lpp(self,
                    gds_lpp: "lpp_type",
                    ) -> Union["LayerInfo", bool]:
        for info in self:
            if info.gds_lpp == gds_lpp:
                return info
        return False

    def get_next_name_from_lpp(self,
                               lpp: "lpp_type",
                               ) -> Union[str, bool]:
        for info in self:
            if info.cad_lpp == lpp:
                return info.next_name()
        return False

    def get_current_name_from_lpp(self,
                                  lpp: "lpp_type",
                                  ) -> Union[str, bool]:
        for info in self:
            if info.cad_lpp == lpp:
                return info.current_name
        return False

    def append_unique_layerinfo(self,
                                new_info: "LayerInfo",
                                ) -> None:
        if not isinstance(new_info, LayerInfo):
            raise ValueError(f'LayerInfoList.append_unique_layerinfo takes 1 LayerInfo object as an argument.')

        if self.has_cad_lpp(new_info.cad_lpp):
            logging.warning(f'cad lpp {new_info.cad_lpp} with already exists in LayerInfoList. \n'
                            f'Not adding this lpp to the list of valid layers.\n\n')
            return
        if self.has_gds_lpp(new_info.gds_lpp):
            logging.warning(f'gds lpp {new_info.gds_lpp} (with cad lpp {new_info.cad_lpp}) already used in '
                            f'LayerInfoList.\n'
                            f'Not adding this lpp to the list of valid layers.\n\n')
            return
        self.append(new_info)

    def merge_info_lists(self,
                         new_info_list: "LayerInfoList",
                         ) -> None:
        if not isinstance(new_info_list, LayerInfoList):
            raise ValueError(f'LayerInfoList.append_unique takes 1 LayerInfoList object as an argument.')

        for info in new_info_list:
            self.append_unique_layerinfo(info)


class DataprepKlayout:
    IMPLEMENTED_DATAPREP_OPERATIONS = ['rad', 'add', 'manh', 'ouo', 'sub', 'ext', 'and', 'xor', 'snap']

    def __init__(self,
                 photonic_tech_info: "PhotonicTechInfo",
                 grid: "RoutingGrid",
                 file_in: str = '',
                 file_out: str = '',
                 dataprep_type: int = 0,
                 is_lumerical_dataprep: bool = False,
                 **kwargs,
                 ):
        """

        Parameters
        ----------
        photonic_tech_info : PhotonicTechInfo
        grid : RoutingGrid
            The bag routingGrid object for this layout.
        file_in : str
        file_out : str
        dataprep_type : Union[str, int]
            The type of dataprep being run.
            0
                The dataprep operations, which are performed on a scaled up resolution
            1
                The rescaling operation which reduces precision back to original
        is_lumerical_dataprep
            True if running the LSF dataprep

        """
        self.photonic_tech_info: PhotonicTechInfo = photonic_tech_info
        self.grid = grid

        self.file_in = file_in
        self.file_out = file_out
        self.dataprep_type = dataprep_type

        self.is_lumerical_dataprep = is_lumerical_dataprep

        if 'flat_in_calibre' in kwargs:
            self.flat_in_calibre = kwargs['flat_in_calibre']
        else:
            self.flat_in_calibre = True

        self.all_lpps_list: "LayerInfoList" = self.parse_layermap(layermap_dict=self.photonic_tech_info.layer_map)
        self.include_all_layers = (dataprep_type == 1)

        # The lines to stream out
        self.outlines = []

        self.global_grid_size = self.photonic_tech_info.global_grid_size
        self.global_rough_grid_size = self.photonic_tech_info.global_rough_grid_size

        # TODO: Figure out proper operation precision as a tech param
        self.global_operation_precision = self.global_grid_size / 10

        # Should shapes be Manhattanized during rad.
        self.GLOBAL_DO_MANH_DURING_OP = True

        # Dataprep custom configuration
        # bypass and ignore lists are lists of LPP pairs in tuple state.
        self.dataprep_ignore_list: List[Tuple[str, str]] = []
        self.dataprep_bypass_list: List[Tuple[str, str]] = []

        self._init_bypass_and_ignore_lists()

        # Load the dataprep operations list and OUUO list
        self.ouuo_regex_list: List[Tuple[Pattern, Pattern]] = []
        self.dataprep_groups: List[Dict] = []

        if not self.is_lumerical_dataprep:
            dataprep_groups_temp = self.photonic_tech_info.dataprep_routine_data.get('dataprep_groups', [])
            ouuo_list_temp = self.photonic_tech_info.dataprep_routine_data.get('over_under_under_over', [])
        else:
            dataprep_groups_temp = self.photonic_tech_info.lsf_export_parameters.get('dataprep_groups', [])
            ouuo_list_temp = self.photonic_tech_info.lsf_export_parameters.get('over_under_under_over', [])

        if dataprep_groups_temp is None:
            self.dataprep_groups = []
        else:
            for dataprep_group in dataprep_groups_temp:
                self.dataprep_groups.append(self._check_dataprep_ops(dataprep_group))

        if ouuo_list_temp is None:
            self.ouuo_regex_list = []
        else:
            # lpp entries can be regex. Keep as regex, as the final list of used layers is not known at this time
            for lpp_entry in ouuo_list_temp:
                self.ouuo_regex_list.append(self._check_input_lpp_entry_and_convert_to_regex(lpp_entry))

    @staticmethod
    def _check_input_lpp_entry_and_convert_to_regex(lpp_entry,
                                                    ) -> Tuple[Pattern, Pattern]:
        """
        Checks whether the lpp entry is a dictionary with an 'lpp' key, whose value is a list composed of 2 strings
        Raises an error if the lpp entry is not valid.

        Parameters
        ----------
        lpp_entry :
            The lpp entry from the yaml file to check

        Returns
        -------
        lpp_key : Tuple[Pattern, Pattern]
            The valid lpp as a tuple of two regex patterns.
        """
        if not isinstance(lpp_entry, dict):
            raise ValueError(f'lpp list entries must be dictionaries.\n'
                             f'Entry {lpp_entry} violates this.')
        lpp_layer = lpp_entry.get('lpp', None)
        if lpp_layer is None:
            raise ValueError(f'List entries must be dictionaries with an lpp key:'
                             f'  - {{lpp: [layer, purpose]}}\n'
                             f'Entry {lpp_entry} violates this.')

        if len(lpp_layer) != 2:
            raise ValueError(f'lpp entry must specify a layer and a purpose, in that order.\n'
                             f'Specified lpp {lpp_layer} does not meet this criteria.')
        if not (isinstance(lpp_layer[0], str) and isinstance(lpp_layer[1], str)):
            raise ValueError(f'Lpp layers and purposes must be specified as a list of two strings.\n'
                             f'Entry {lpp_layer} does not meet this criteria.')

        # Try to compile the lpp entries to ensure they are valid regexes
        layer_regex = re.compile(lpp_layer[0])
        purpose_regex = re.compile(lpp_layer[1])

        return layer_regex, purpose_regex

    def _check_dataprep_ops(self,
                            dataprep_group,
                            ) -> Dict[str, List]:
        """
        Checks whether the passed dataprep group is valid.
        Raises an error if the dataprep group is not valid.

        Parameters
        ----------
        dataprep_group :
            The dataprep_group entry from the yaml file to check.

        Returns
        -------
        dataprep_group_clean : Dict[str, List]
            The clean
        """
        # Check that lpp_in and lpp_ops are specified, and that they are both lists
        if 'lpp_in' not in dataprep_group:
            raise ValueError(f'Dataprep group entry must be a dictionary containing a key named \'lpp_in\'.\n'
                             f'Dataprep group {dataprep_group} does not meet this criteria.')
        if 'lpp_ops' not in dataprep_group:
            raise ValueError(f'Dataprep group entry must be a dictionary containing a key named \'lpp_ops\'.\n'
                             f'Dataprep group {dataprep_group} does not meet this criteria.')
        if not (isinstance(dataprep_group['lpp_in'], list)):
            raise ValueError(f'lpp_in must be a list of dictionaries.\n'
                             f'Dataprep group {dataprep_group} does not meet this criteria.')
        if not (isinstance(dataprep_group['lpp_ops'], list)):
            raise ValueError(f'lpp_ops must be a list of dictionaries.\n'
                             f'Dataprep group {dataprep_group} does not meet this criteria.')

        # Check the lpp_in entries
        lpp_in_clean = []
        for lpp_in_entry in dataprep_group['lpp_in']:
            lpp_in_clean.append(self._check_input_lpp_entry_and_convert_to_regex(lpp_in_entry))

        # Check the lpp_ops entries
        lpp_op_clean = []
        for lpp_op_entry in dataprep_group['lpp_ops']:
            # Check entry is a dict
            if not isinstance(lpp_op_entry, dict):
                raise ValueError(f'lpp_ops entries must be dictionaries.\n'
                                 f'Dataprep group {dataprep_group} does not meet this criteria.')
            # Check that 'operation' is specified and valid
            if 'operation' not in lpp_op_entry:
                raise ValueError(f'lpp_ops entry must specify a value for the key \'operation\'\n'
                                 f'Dataprep group {dataprep_group} does not meet this criteria.')
            if lpp_op_entry['operation'] not in self.IMPLEMENTED_DATAPREP_OPERATIONS:
                raise ValueError(f'The following dataprep operations are implemented at this '
                                 f'time: {self.IMPLEMENTED_DATAPREP_OPERATIONS}\n'
                                 f'Dataprep group {dataprep_group} uses an unsupported dataprep '
                                 f'operation {lpp_op_entry["operation"]}.')

            operation = lpp_op_entry['operation']

            # Check amount is specified and valid, if necessary
            amount = lpp_op_entry.get('amount', None)
            if (amount is None) and not (operation in ['manh', 'ouo']):
                raise ValueError(f'Amount must be specified for operation \'{operation}\' '
                                 f'in dataprep group {dataprep_group}')
            if (amount is not None) and not (isinstance(amount, int) or isinstance(amount, float)):
                raise ValueError(f'amount must be a float or int.\n'
                                 f'Operation \'{operation}\' in dataprep group {dataprep_group} '
                                 f'does not meet this criteria.')

            out_layer = lpp_op_entry.get('lpp', None)
            if (out_layer is None) and (operation not in ['manh', 'snap', 'ouo']):
                raise ValueError(f'output lpp must be specified for operation \'{operation}\' '
                                 f'in dataprep group {dataprep_group}')
            if out_layer is not None:
                if len(out_layer) != 2:
                    raise ValueError(f'lpp entry must specify a layer and a purpose, in that order.\n'
                                     f'Specified entry {out_layer} does not meet this criteria.')
                if not (isinstance(out_layer[0], str) and isinstance(out_layer[1], str)):
                    raise ValueError(f'Lpp layers and purposes must be specified as a list of two strings.\n'
                                     f'{out_layer} in dataprep group {dataprep_group} does not meet this criteria.')
                out_layer = (out_layer[0], out_layer[1])

            lpp_op_clean.append(
                dict(
                    operation=operation,
                    amount=amount,
                    lpp=out_layer,
                )
            )

        return dict(
            lpp_in=lpp_in_clean,
            lpp_ops=lpp_op_clean,
        )

    def _init_bypass_and_ignore_lists(self):
        """
        Parse the dataprep_ignore_list and dataprep_bypass_list from the dataprep_routine.yaml
        Mark matching layers in the all_lpps_list as ignored or bypassed as necessary.

        Returns
        -------

        """
        dataprep_ignore_list_temp = self.photonic_tech_info.dataprep_routine_data.get(
            'dataprep_ignore_list', [])
        dataprep_bypass_list_temp = self.photonic_tech_info.dataprep_routine_data.get(
            'dataprep_bypass_list', [])

        # If ignore/bypass were not specified in the yaml, handle appropriately. If they were specified
        # reformat ignore and bypass lists, as they are specified as dictionaries in the yaml
        if dataprep_ignore_list_temp is None:
            self.dataprep_ignore_list = []
        else:
            # lpp entries can be regex. Find all layers to ignore now
            for lpp_entry in dataprep_ignore_list_temp:
                self.dataprep_ignore_list.extend(
                    self.regex_search_lpps(
                        regex=self._check_input_lpp_entry_and_convert_to_regex(lpp_entry),
                    )
                )

        if dataprep_bypass_list_temp is None:
            self.dataprep_bypass_list = []
        else:
            # lpp entries can be regex. Find all layers to bypass now
            for lpp_entry in dataprep_bypass_list_temp:
                self.dataprep_bypass_list.extend(
                    self.regex_search_lpps(
                        regex=self._check_input_lpp_entry_and_convert_to_regex(lpp_entry),
                    )
                )

        for layer in self.all_lpps_list:
            if layer.cad_lpp in self.dataprep_bypass_list:
                layer.bypass = True
            if layer.cad_lpp in self.dataprep_ignore_list:
                layer.ignore = True

    def get_manhattanization_size_on_layer(self,
                                           layer: Union[str, Tuple[str, str]]
                                           ) -> float:
        """
        Finds the layer-specific Manhattanization size.

        Parameters
        ----------
        layer : Union[str, Tuple[str, str]]
            The layer or LPP being Manhattanized.

        Returns
        -------
        manh_size : float
            The Manhattanization size for the layer.
        """
        if isinstance(layer, tuple):
            layer = layer[0]

        per_layer_manh = self.photonic_tech_info.dataprep_routine_data['manh_size_per_layer']
        if per_layer_manh is None:
            logging.warning(f'\'manh_size_per_layer\' dictionary is not specified in the dataprep_routine.yaml file.'
                            f'Defaulting to empty dictionary.')
            per_layer_manh = {}

        if layer not in per_layer_manh:
            logging.info(f'Layer {layer} is not in the manh_size_per_layer dictionary in dataprep_routine file.\n'
                         f'Defaulting to global_grid_size')
            manh_size = self.global_grid_size
        else:
            manh_size = per_layer_manh[layer]

        return manh_size

    def regex_search_lpps(self,
                          regex: Tuple[Pattern, Pattern],
                          allow_bypass: bool = False,
                          allow_ignore: bool = False,
                          ) -> List[Tuple[str, str]]:
        """
        Returns a list of all keys in the dictionary that match the passed lpp regex.
        Searches for a match in both the layer and purpose regex.

        Parameters
        ----------
        regex : Tuple[Pattern, Pattern]
            The lpp regex patterns to match
        allow_bypass : bool
            True to allow regex matches for bypassed layers.
        allow_ignore : bool
            True to allow regex matches for ignored layers.

        Returns
        -------
        matches : List[Tuple[str, str]]
            The list of dictionary keys that match the provided regex
        """
        matches = []
        # Loop over each lpp
        for layer_info in self.all_lpps_list:
            # If allowing bypass and allowing ignore (aka, allow everything),
            # or if allowing bypass or layer should not be bypassed
            # or if allowing ignored or layer should not be ignored
            # Note a layer cannot every be both (should ignore) and (should bypass)
            # if (allow_ignore and allow_bypass) or \
            #         (allow_bypass or not layer_info.bypass) or \
            #         ((allow_ignore or not layer_info.ignore) and (layer_info.bypass and not allow_bypass)):
            # if (allow_bypass or not layer_info.bypass) and (allow_ignore or not layer_info.ignore):

                # Actually, for now allow all matches, and do regex checks per layer
                if regex[0].fullmatch(layer_info.cad_layer) and regex[1].fullmatch(layer_info.cad_purpose):
                    matches.append((layer_info.cad_layer, layer_info.cad_purpose))
        return matches

    def regex_search_lpp_list(self,
                              lpp_regex_list,
                              lpp,
                              ):
        """Checks if any of the regex lpps in the lpp_regex_list match the passed lpp"""
        match = False
        lpp_info = self.all_lpps_list.has_cad_lpp(lpp)
        # If LPP is not in list of current LPPs, dont check anything for now
        if not lpp_info:
            return False
        for lpp_regex_str in lpp_regex_list:
            layer_regex = re.compile(lpp_regex_str[0])
            purpose_regex = re.compile(lpp_regex_str[1])
            if layer_regex.fullmatch(lpp_info.cad_layer) and purpose_regex.fullmatch(lpp_info.cad_purpose):
                match = lpp_regex_str
                break

        return match

    def lpp_in_bypass_list(self,
                           lpp,
                           ):
        return self.regex_search_lpp_list(self.dataprep_bypass_list, lpp)

    def lpp_in_ignore_list(self,
                           lpp,
                           ):
        return self.regex_search_lpp_list(self.dataprep_ignore_list, lpp)

    @staticmethod
    def parse_layermap(layermap_dict: dict) -> "LayerInfoList":
        """
        Parses layermap file into a list of dictionaries for each layer.

        Parameters
        ----------
        layermap_dict

        Returns
        -------

        """
        layer_info_list = LayerInfoList()

        for lpp_name, lpp_num_gds in layermap_dict.items():
            layer_info = LayerInfo(
                cad_layer=lpp_name[0],
                cad_purpose=lpp_name[1],
                gds_layer=lpp_num_gds[0],
                gds_purpose=lpp_num_gds[1],
                base_name=f'{lpp_name[0]}_{lpp_name[1]}'
            )
            layer_info_list.append_unique_layerinfo(layer_info)

        return layer_info_list

    def init_klayout_outlines(self):
        # Write the header

        # TODO: dbu, tiles, threads,
        self.outlines.append(f'source("{self.file_in}")\n')
        self.outlines.append(f'target("{self.file_out}")\n')
        # # Dataprep operations need to run on magnified precision inputs
        # if self.dataprep_type == 0:
        #     set to 10x
        # # Rescale the results down to original precision
        # elif self.dataprep_type == 1:
        #     set to 1/10x
        # else:
        #     raise ValueError(f'Bad dataprep_type')
        #
        #
        # if self.flat_in_calibre:
        #     # TODO: find out to flatten
        # self.outlines.append(f'\n\n\n')

        # Begin the layer stream in section
        self.outlines.append(f'\n\n\n# Initialize layers\n')

        # Write the layer mapping for each non-ignored, non-bypassed layer
        for layer_info in self.all_lpps_list:
            if self.include_all_layers or (not layer_info.ignore and not layer_info.bypass):
                layer_name, layer_purpose, gds_name, gds_purpose = \
                    layer_info.cad_layer, layer_info.cad_purpose, layer_info.gds_layer, layer_info.gds_purpose
                current_name = layer_info.current_name

                self.outlines.append(f'# Layer {layer_name}, {layer_purpose}\n')
                self.outlines.append(f'{layer_name}_{layer_purpose} = input({gds_name}, {gds_purpose})\n')

                # Copy layers
                self.outlines.append(f'{current_name} = {layer_name}_{layer_purpose}.dup\n')
                self.outlines.append(f'\n\n')

        self.outlines.append(f'\n\n\n')
        self.outlines.append(f'# DATAPREP OPERATIONS:\n')

    def final_klayout_outlines(self):
        """
        Copy out the layers that went through dataprep. Add back in all bypassed layers
        Returns
        -------

        """
        self.outlines.append(f'\n\n\n#Final streamout:\n\n')
        # Stream out all non-ignored, non-bypassed layers
        for layer_info in self.all_lpps_list:
            if self.include_all_layers or (not layer_info.ignore and not layer_info.bypass):
                current_name = layer_info.current_name
                gds_name, gds_purpose = layer_info.gds_layer, layer_info.gds_purpose
                self.outlines.append(f'{current_name}.output({gds_name}, {gds_purpose})\n')

        self.outlines.append(f'\n\n\n')
        self.outlines.append(f'# Add bypassed layers back into the GDS\n\n')

        if not self.include_all_layers:
            # Add back bypassed layers
            for layer_info in self.all_lpps_list:
                layer_name, layer_purpose, gds_name, gds_purpose = \
                    layer_info.cad_layer, layer_info.cad_purpose, layer_info.gds_layer, layer_info.gds_purpose
                if layer_info.bypass:
                    current_name = layer_info.current_name

                    self.outlines.append(f'# Bypassed layer {layer_name}, {layer_purpose}\n')
                    self.outlines.append(f'input({gds_name}, {gds_purpose}).output({gds_name}, {gds_purpose})\n')
                    self.outlines.append(f'\n\n')

    def write_poly_operation(self,
                             lpp_in,
                             lpp_out,
                             operation,
                             size_amount,
                             do_manh_in_rad,
                             ):
        in_lpp_name = self.all_lpps_list.get_current_name_from_lpp(lpp_in)
        out_lpp_name_current = self.all_lpps_list.get_current_name_from_lpp(lpp_out)
        out_lpp_name_new = self.all_lpps_list.get_next_name_from_lpp(lpp_out)

        if not in_lpp_name:
            raise ValueError(f'lpp_in: {lpp_in} was is not a valid layer in the layermap.'
                             f'Either lpp_in must be a valid gds layer, or must be a temporary dataprep output layer.')
        if not out_lpp_name_current or not out_lpp_name_new:
            print(f'ERROR\n {lpp_out}\n')
            raise ValueError(f'Currently require all layers (even temporary layers) to be defined in a layermap. '
                             f'This may change so that temporary layers do not need to be defined in a layermap.'
                             f'Failing layer is:   {lpp_out}')

        if operation == 'manh':
            raise ValueError(f'manh not yet supported in klayout')

        elif operation == 'rad':
            # TODO: Not equivalent to calibre
            # TODO: Implement using manh
            self.outlines.append(f'{out_lpp_name_new} = {out_lpp_name_current}.or({in_lpp_name}.sized({size_amount}))\n')

        elif operation == 'add':
            self.outlines.append(f'{out_lpp_name_new} = '
                                 f'{out_lpp_name_current}.or({in_lpp_name}.sized({size_amount:0.3f}))\n')

        elif operation == 'sub':
            self.outlines.append(f'{out_lpp_name_new} = '
                                 f'{out_lpp_name_current}.not({in_lpp_name}.sized({size_amount:0.3f}))\n')

        elif operation == 'and':
            self.outlines.append(f'{out_lpp_name_new} = '
                                 f'{out_lpp_name_current}.and({in_lpp_name}.sized({size_amount:0.3f}))\n')

        elif operation == 'xor':
            self.outlines.append(f'{out_lpp_name_new} = '
                                 f'{out_lpp_name_current}.xor({in_lpp_name}.sized({size_amount:0.3f}))\n')

        elif operation == 'ext':
            raise ValueError(f'ext not yet implemented')

        elif operation == 'ouo':

            raise ValueError(f'not yet implemented OUO')
            # # TODO: Check that min width doesnt disappear
            # min_space_unit = self.photonic_tech_info.min_space_unit(lpp_out)
            # min_width_unit = self.photonic_tech_info.min_width_unit(lpp_out)
            # # Subtract half a grid size to prevent min width shapes from disappearing and min space gaps from
            # # getting merged
            # underofover_size = f'{self.global_grid_size * (0.5 * min_space_unit) - (0.5 * self.global_grid_size):.4f}'
            # overofunder_size = f'{self.global_grid_size * (0.5 * min_width_unit) - (0.5 * self.global_grid_size):.4f}'
            #
            # self.outlines.append(f'// OUO on layer {lpp_out} performed with underofover_size = {underofover_size} and'
            #                      f'overofunder_size = {overofunder_size}\n')

        elif operation == 'del':
            raise ValueError(f'del not yet implemented')

        elif operation == 'snap':
            self.outlines.append(f'{out_lpp_name_new} = snapped({in_lpp_name}.sized({size_amount:0.3f}))\n')

        else:
            raise ValueError(f'Operation {operation} specified in dataprep algorithm, but is not implemented.')

        self.outlines.append(f'\n\n')

    def parse_dataprep_groups(self,
                              ):
        for dataprep_group in self.dataprep_groups:
            for lpp_in_regex in dataprep_group['lpp_in']:
                # Get all LPP ins that match lpp_in regex
                lpp_in_list = self.regex_search_lpps(lpp_in_regex, allow_bypass=True, allow_ignore=False)
                for lpp_in in lpp_in_list:
                    if self.lpp_in_bypass_list(lpp_in) or self.lpp_in_ignore_list(lpp_in):
                        warnings.warn(f'input lpp {lpp_in} is in bypass list or ignore list. this is not allowed.\n'
                                      f'failing operation is {dataprep_group}')
                    else:
                        for lpp_op in dataprep_group['lpp_ops']:
                            operation = lpp_op['operation']
                            amount = lpp_op['amount']
                            if (amount is None) and (operation == 'manh'):
                                amount = self.get_manhattanization_size_on_layer(lpp_in)

                            out_layer = lpp_op['lpp']
                            if self.lpp_in_bypass_list(out_layer) or self.lpp_in_ignore_list(out_layer):
                                warnings.warn(
                                    f'output lpp {out_layer} is in bypass list or ignore list. this is not allowed.\n'
                                    f'failing operation is {dataprep_group}')
                            else:
                                if (out_layer is None) and (operation == 'manh'):
                                    out_layer = lpp_in
                                    self.outlines.append(f'# Manh output layer not specified in operation. '
                                                         f'Setting to {out_layer}\n')
                                elif (out_layer is None) and (operation == 'snap'):
                                    out_layer = lpp_in
                                    self.outlines.append(f'# snap output layer not specified in operation. '
                                                         f'Setting to {out_layer}\n')
                                elif (out_layer is None) and (operation == 'ouo'):
                                    out_layer = lpp_in
                                    self.outlines.append(f'# ouo output layer not specified in operation. '
                                                         f'Setting to {out_layer}\n')

                                self.outlines.append(f'# Dataprep operation: {operation}  '
                                                     f'on layer: {lpp_in} to layer: {out_layer}  with size {amount}\n')

                                self.write_poly_operation(
                                    lpp_in=lpp_in,
                                    lpp_out=out_layer,
                                    operation=operation,
                                    size_amount=amount,
                                    do_manh_in_rad=self.GLOBAL_DO_MANH_DURING_OP,
                                )

        # # OUUO is a special operation
        # for lpp_regex in self.ouuo_regex_list:
        #     # Get all LPP ins that match lpp_in regex
        #     lpp_in_list = self.regex_search_lpps(lpp_regex, allow_bypass=False, allow_ignore=False)
        #
        #     for lpp in lpp_in_list:
        #         if self.lpp_in_bypass_list(lpp) or self.lpp_in_ignore_list(lpp):
        #             raise ValueError(f'ouuo lpp {lpp} is in bypass list or ignore list. this is not allowed.')
        #         self.write_poly_operation(
        #             lpp_in=lpp,
        #             lpp_out=lpp,
        #             operation='ouo',
        #             size_amount=0,
        #             do_manh_in_rad=False
        #         )

    def dataprep(self):
        """
        Parse the dataprep instructions and create the klayout runset file.
        Returns
        -------

        """
        # Write out the initial header information, and the
        self.init_klayout_outlines()
        if self.dataprep_type == 0:
            self.parse_dataprep_groups()
        elif self.dataprep_type == 1:
            pass
        else:
            raise ValueError(f'invalid dataprep_type')
        self.final_klayout_outlines()

        return self.outlines
