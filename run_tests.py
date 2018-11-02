import pytest
import os

# Use the built in example bag_config for tests
os.environ['BAG_CONFIG_PATH'] = "./BPG/examples/tech/bag_config.yaml"

test_set = ['BPG/tests',
            'BPG/examples/Waveguide.py',
            ] 

pytest.main(test_set)
