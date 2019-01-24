#!/usr/bin/env python3
import pytest
import os
import warnings

# Use the built in example bag_config for tests
os.environ['BAG_CONFIG_PATH'] = "./BPG/examples/tech/bag_config.yaml"

test_set = ['BPG/tests',
            'BPG/examples/Waveguide.py',
            ]

if __name__ == '__main__':
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',
                                category=RuntimeWarning,
                                message='.*polygon with more than 199 points was created.*')

        pytest.main(test_set)
