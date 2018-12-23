import logging
from datetime import datetime


def setup_logger(log_path: str,
                 log_filename: str = 'bpg.log',
                 ) -> None:
    """
    Configures the root logger so that all other loggers in BPG inherit from its properties.

    Parameters
    ----------
    log_path : str
        The path to save the log files.
    log_filename : str
        The name of the primary output log file.

    Returns
    -------

    """
    # Set up the initial basic config for the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = []

    # Add a console handler
    out_handler = logging.StreamHandler()
    # If the verbose option is set to False, only display warnings and errors
    out_handler.setLevel(logging.INFO)

    # Add an output file to the root logger, overwrite the log file if it already exists
    file_handler = logging.FileHandler(log_path + '/' + log_filename, 'w')
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(filename)s:%(lineno)d] %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # Add an output file to the root logger for INFO level logs and higher (debug can get messy)
    file_handler_info = logging.FileHandler(log_path + '/' + log_filename + '_INFO', 'w')
    file_handler_info.setLevel(logging.INFO)
    file_handler_info.setFormatter(formatter)

    root_logger.addHandler(file_handler)
    root_logger.addHandler(file_handler_info)
    root_logger.addHandler(out_handler)
    root_logger.addHandler(file_handler_info)
    # Add filter to prevent dataprep debug logs from hitting the main logger

    # Print out the current date and time
    root_logger.info('##########################')
    root_logger.info('Starting BPG Build')
    time = datetime.now()
    root_logger.info(str(time))
    root_logger.info('##########################')

    ################################################################################
    # Dataprep logger
    ################################################################################
    # Set up a dataprep logger for dumping dataprep debug data
    dataprep_logger = logging.getLogger('dataprep')
    dataprep_logger.setLevel(logging.DEBUG)
    dataprep_logger.propagate = False

    # Add a file stream for the dataprep logger
    dataprep_file_handler = logging.FileHandler(log_path + '/' 'dataprep_debug_dump.log', 'w')
    dataprep_file_handler.setLevel(logging.DEBUG)
    dataprep_file_handler.setFormatter(formatter)

    dataprep_logger.handlers = []
    dataprep_logger.addHandler(dataprep_file_handler)

    # Print out the current date and time
    dataprep_logger.info('##########################')
    dataprep_logger.info('Starting BPG Build')
    dataprep_logger.info('Initializing dataprep_debug_dump.log')
    time = datetime.now()
    dataprep_logger.info(str(time))
    dataprep_logger.info('##########################')

    ################################################################################
    # Timing logger
    ################################################################################
    # Set up a time information logger for dumping timing data when generating
    timing_logger = logging.getLogger('timing')
    timing_logger.setLevel(logging.DEBUG)
    timing_logger.propagate = False

    # Add a file stream for the dataprep logger
    timing_file_handler = logging.FileHandler(log_path + '/' 'timing.log', 'w')
    timing_file_handler.setLevel(logging.DEBUG)
    timing_formatter = logging.Formatter('%(message)-15s')
    timing_file_handler.setFormatter(timing_formatter)

    timing_logger.handlers = []
    timing_logger.addHandler(timing_file_handler)

    # Print out the current date and time
    timing_logger.info('################################################################################')
    timing_logger.info(f'{"Time (s)":>15} | Operation')
    timing_logger.info('################################################################################')

    timing_logger.propagate = True
