#!/usr/bin/env python3
import pytest
import os
import sys
import warnings

test_set = ['BPG/tests']

if __name__ == '__main__':
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore',
                                category=RuntimeWarning,
                                message='.*polygon with more than 199 points was created.*')

        sys.exit(pytest.main(test_set))
