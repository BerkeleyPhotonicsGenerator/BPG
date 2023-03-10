
echo "--- Loading environment variables for BPG ---"
setenv BAG_WORK_DIR `pwd`  # set current directory as the main workspace
setenv BAG_CONFIG_PATH ${BAG_WORK_DIR}/example_tech/bag_config.yaml
setenv BAG_FRAMEWORK ${BAG_WORK_DIR}/BAG_Framework
setenv BAG_TECH_CONFIG_DIR ${BAG_WORK_DIR}/example_tech/BAG_tech_files
setenv BAG_TEMP_DIR ${BAG_WORK_DIR}/tmp

if (! $?PYTHONPATH) then
  setenv PYTHONPATH ${BAG_WORK_DIR}:${BAG_WORK_DIR}/BAG_Framework:${BAG_WORK_DIR}/BPG
else
  setenv PYTHONPATH ${BAG_WORK_DIR}:${BAG_WORK_DIR}/BAG_Framework:${BAG_WORK_DIR}/BPG:$PYTHONPATH
endif

