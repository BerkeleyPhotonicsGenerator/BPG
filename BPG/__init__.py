import os
import sys
from .template import PhotonicTemplateBase  # Expose PhotonicTemplateBase so that all generators can subclass it
from .layout_manager import PhotonicLayoutManager  # Expose PLM to simplify BPG usage


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
