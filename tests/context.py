import os
import sys

# All BPG unit tests should use the built in example tech config
os.environ['BAG_CONFIG_PATH'] = './BPG/examples/tech/bag_config.yaml'

# Move the BPG package path to the front of the module search path so that
# test modules are easily found
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import BPG
