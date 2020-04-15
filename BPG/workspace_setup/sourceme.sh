#!/bin/sh

set -ex

echo "--- Loading environment variables for BPG ---"
export BAG_WORK_DIR=`pwd`  # set current directory as the main workspace
export BAG_CONFIG_PATH=${BAG_WORK_DIR}/example_tech/bag_config.yaml
export BAG_FRAMEWORK=${BAG_WORK_DIR}/BAG_Framework
export BAG_TECH_CONFIG_DIR=${BAG_WORK_DIR}/example_tech/BAG_tech_files
export BAG_TEMP_DIR=${BAG_WORK_DIR}/tmp
