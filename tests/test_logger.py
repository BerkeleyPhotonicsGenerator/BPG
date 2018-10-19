from pathlib import Path
import BPG
import logging

str_list = ['LOG1UNIQUE', 'LOG2UNIQUE', 'LOG3UNIQUE', 'LOG4UNIQUE']

class DummyClass(BPG.PhotonicTemplateBase):
    def __init__(self, temp_db,
                 lib_name,
                 params,
                 used_names,
                 **kwargs,
                 ):
        """ Class for generating a single mode waveguide shape in Lumerical """
        BPG.PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_params_info(cls):
        return dict(
        )

    @classmethod
    def get_default_param_values(cls):
        return dict(
        )

    def draw_layout(self):
        logging.info(f'Made it to the draw_layout method')
        dataprep_logger = logging.getLogger('dataprep')
        dataprep_logger.info(str_list[0])
        logging.info(str_list[1])
        dataprep_logger.debug(str_list[2])
        logging.debug(str_list[3])


def test_logger():
    """
    Unit Test
    """
    # Load a previous BPG Project if it exists, otherwise create a new one
    local_dict = locals()
    if 'prj' not in local_dict:
        print('creating BAG project')
        bprj = BPG.PhotonicBagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    spec_file = 'BPG/tests/specs/logger_specs.yaml'
    PLM = BPG.PhotonicLayoutManager(bprj, spec_file, verbose=True)
    PLM.generate_gds()
    log_path = PLM.log_path
    log_name = PLM.log_filename
    evaulate_logs(log_path, log_name)


def test_logger_no_logfile():
    """
    Unit Test
    """
    # Load a previous BPG Project if it exists, otherwise create a new one
    local_dict = locals()
    if 'prj' not in local_dict:
        print('creating BAG project')
        bprj = BPG.PhotonicBagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    spec_file = 'BPG/tests/specs/logger_specs_no_logfile.yaml'
    PLM = BPG.PhotonicLayoutManager(bprj, spec_file, verbose=True)
    PLM.generate_gds()
    log_path = PLM.log_path
    log_name = PLM.log_filename
    evaulate_logs(log_path, log_name)


def evaulate_logs(log_path, log_name):
    root_log = log_path / log_name
    info_log = Path(str(log_path / log_name) + '_INFO')
    dataprep_log = Path(str(log_path) + '/dataprep_debug_dump.log')

    root_key = [0, 1, 0, 1]
    info_key = [0, 1, 0, 0]
    dataprep_key = [1, 0, 1, 0]

    if root_log.exists():
        root_content = open(root_log, 'r').read()
        check_content(root_content, root_key, 'root log')
    else:
        assert False, f'Root output log file does not exist.'

    if info_log.exists():
        info_content = open(info_log, 'r').read()
        check_content(info_content, info_key, 'info log')
    else:
        assert False, f'Info output log file does not exist.'

    if dataprep_log.exists():
        dataprep_content = open(dataprep_log, 'r').read()
        check_content(dataprep_content, dataprep_key, 'dataprep log')
    else:
        assert False, f'Dataprep output log file does not exist.'


def check_content(content, key_list, log_name):
    for ind, key in enumerate(key_list):
        if key:
            assert str_list[ind] in content, f'Key {str_list[ind]} should be in {log_name}, but is not.'
        else:
            assert str_list[ind] not in content, f'Key {str_list[ind]} should not be in {log_name}, but is.'


if __name__ == '__main__':
    test_logger()
    test_logger_no_logfile()
