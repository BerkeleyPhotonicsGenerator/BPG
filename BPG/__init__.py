import os
import sys
from collections import UserDict, Mapping
from .template import PhotonicTemplateBase  # Expose PhotonicTemplateBase so that all generators can subclass it
from .layout_manager import PhotonicLayoutManager  # Expose PLM to simplify BPG usage
from typing import Union


class ConfigDict(UserDict):
    """
    This dictionary class is intended to store global configuration settings loaded on startup from the default
    config in BPG and the user provided bpg_config.yaml files. These dictionary values are used as defaults for any
    given individual generator run, and can be overriden by settings in the yaml file
    """

    def __init__(self, default_dict=None):
        """
        Do not initialize the dictionary with any data, instead use the load_configuration method to be explicit
        about mutating global state

        Parameters
        ----------
        default_dict : Union[dict, ConfigDict]
            A dictionary to be reloaded prior to every call to load_configuration
        """
        UserDict.__init__(self)
        self.default_dict = default_dict
        self.load_configuration(config_dict={})

    def __setitem__(self, key, value):
        """ This class prevents unintentional mutation of global settings """
        raise ValueError(f"Dynamically modifying global settings is not allowed!"
                         f"Please set {key} to {value} in either your global config file or spec file")

    def load_configuration(self, config_dict: Union[dict, "ConfigDict"]):
        """ Use this method to explicitly modify the internal settings of the dictionary """
        if self.default_dict:
            self.data.update(self.default_dict)
        self._update(config_dict)

    def _update(self, mapping) -> None:
        """
        Private update method to allow nested dictionaries to have their some internal values updated without
        overwriting the whole thing. Since this method is specific to ConfigDict, this does not allow updating
        beyond 2 levels of hierarchy.
        """
        for key, value in mapping.items():
            dict_value = self.data.get(key, {})
            if not isinstance(dict_value, Mapping):
                self.data[key] = value
            elif isinstance(value, Mapping):
                dict_value.update(value)
            else:
                self.data[key] = value


def setup_environment():
    """ Sets up python module search path from config file """
    config = PhotonicLayoutManager.load_yaml(os.environ['BAG_CONFIG_PATH'])
    # Add paths specified in config file
    if 'path_setup' in config:
        for path in config['path_setup']:
            if path not in sys.path:
                sys.path.append(path)
                print(f'Adding {path} to python module search path')


def check_environment():
    """ Checks that all required environment variables have been set """
    env_list = [('BAG_WORK_DIR', 'Root directory where all generator folders are located'),
                ('BAG_CONFIG_PATH', 'Path to yaml file containing configuration for BAG and BPG'),
                ('BAG_FRAMEWORK', 'Path to BAG installation'),
                ('BAG_TEMP_DIR', 'Path to where temporary files will be placed'),
                ('BAG_TECH_CONFIG_DIR', 'Path to directory containing tech-specific configuration'),
                ]

    for var, description in env_list:
        if var not in os.environ:
            print(f'Environment variable {var} not set.\nDescription:{description}')


__version__ = '0.8.5'
print(f'Loaded BPG v{__version__}')
check_environment()
setup_environment()

# Use the core setting built into BPG as a base for all configuration
bpg_default_config = PhotonicLayoutManager.load_yaml(
    os.path.dirname(os.path.realpath(__file__)) + "/default_config.yaml"
)

# Import settings from the global config file
global_settings = ConfigDict(default_dict=bpg_default_config)
_bpg_global_config_file = PhotonicLayoutManager.load_yaml(os.environ['BAG_CONFIG_PATH'])
global_settings.load_configuration(_bpg_global_config_file)

# Initialize these run settings to share the global settings, this will typically be modified for each spec file
# By PhotonicLayoutManager
run_settings = ConfigDict(default_dict=global_settings)
