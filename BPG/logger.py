import logging
from datetime import datetime


def setup_logger(log_path: str,
                 log_filename: str = 'bpg.log',
                 verbose: bool = False,
                 ) -> None:
    """

    Parameters
    ----------
    log_path : str
        The path to save the log files.
    log_filename : str
        The name of the primary output log file.
    verbose : bool
        True to output debug level messages to stdout. False to output info level messages to stdout.

    Returns
    -------

    """
    """ Configures the root logger so that all other loggers in BPG inherit from its properties """

    # Set up the initial basic config for the root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    logger.handlers = []

    # Add a console handler
    out_handler = logging.StreamHandler()
    # If the verbose option is set to False, only display warnings and errors
    if verbose is False:
        out_handler.setLevel(logging.INFO)
    else:
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

    logger.addHandler(file_handler)
    logger.addHandler(file_handler_info)
    logger.addHandler(out_handler)
    logger.addHandler(file_handler_info)
    # Add filter to prevent dataprep debug logs from hitting the main logger
    logger.addFilter(DataprepFilter())

    # Print out the current date and time
    logger.info('##########################')
    logger.info('Starting BPG Build')
    time = datetime.now()
    logger.info(str(time))
    logger.info('##########################')

    # Set up a dataprep logger for dumping dataprep debug data
    dataprep_logger = logging.getLogger('.dataprep')
    dataprep_logger.setLevel(logging.DEBUG)
    dataprep_logger.handlers = []

    # Add a file stream for the dataprep logger
    dataprep_file_handler = logging.FileHandler(log_path + '/' 'dataprep_debug_dump.log', 'w')
    dataprep_file_handler.setLevel(logging.DEBUG)
    dataprep_file_handler.setFormatter(formatter)

    dataprep_logger.addHandler(dataprep_file_handler)

    # Print out the current date and time
    dataprep_logger.info('##########################')
    dataprep_logger.info('Starting BPG Build')
    dataprep_logger.info('Initializing dataprep_debug_dump.log')
    time = datetime.now()
    dataprep_logger.info(str(time))
    dataprep_logger.info('##########################')


class DataprepFilter(logging.Filter):
    def filter(self, record: logging.LogRecord):
        return not (record.levelno == logging.DEBUG and record.name == 'dataprep')
