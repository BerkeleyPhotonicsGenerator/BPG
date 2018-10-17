import logging
from datetime import datetime


def setup_logger(logfile: str = 'bpg.log', verbose: bool = False) -> None:
    """ Configures the root logger so that all other loggers in BPG inherit from its properties """

    # Set up the initial basic config for the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers = []

    # Add a console handler
    out_handler = logging.StreamHandler()
    # If the verbose option is set to False, only display warnings and errors
    if verbose is False:
        out_handler.setLevel(logging.WARNING)
    else:
        out_handler.setLevel(logging.INFO)

    # Add an output file handler, overwrite the log file if it already exists
    file_handler = logging.FileHandler(logfile, 'w')
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('[%(filename)s:%(lineno)d] %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)

    # Add a second output file handler for info only
    file_handler_info = logging.FileHandler(logfile + '_INFO', 'w')
    file_handler_info.setLevel(logging.INFO)
    file_handler_info.setFormatter(formatter)

    # Add all handlers to root logger
    root_logger.addHandler(file_handler)
    root_logger.addHandler(file_handler_info)
    root_logger.addHandler(out_handler)

    # Print out the current date and time
    root_logger.info('##########################')
    root_logger.info('Starting BPG Build')
    time = datetime.now()
    root_logger.info(str(time))
    root_logger.info('##########################')
