import subprocess
from pathlib import Path
import logging
from typing import TYPE_CHECKING, Callable, List

if TYPE_CHECKING:
    pass


def default_callback(**kwargs):
    """
    Expected parameters:

    Parameters
    ----------
    kwargs:
        retcode : int
            return code of the LVS process.
        log_file : str
            log file name.


    Returns
    -------

    """
    retcode = kwargs.get('retcode', True)
    logfile = kwargs.get('logfile', None)
    if retcode:
        return True, logfile
    else:
        return False, logfile


class Task:

    def __init__(self,
                 name: str,
                 command: list,
                 logfile: str,
                 run_dir: str,
                 callback_function: Callable = default_callback,
                 ):
        self.name = name
        self.command = command
        self.logfile = logfile
        self.run_dir = run_dir
        if callback_function is None:
            self.callback_function = default_callback
        else:
            self.callback_function = callback_function

    def __repr__(self):
        return (f'[Task Object: Name: {self.name}, '
                f'Command: {self.command}, '
                f'run_dir: {self.run_dir},  '
                f'callback: {self.callback_function}]'
                )

    def run(self):
        logging.info(
            f'Task started: {self.name}\n'
            f'running command: {self.command}\n'
            f'Press <Ctrl> + C to exit.\n'
        )

        logfile_path = str(Path(self.run_dir) / self.logfile)

        with open(logfile_path, 'w') as f:
            retval = subprocess.run(self.command, stdout=f)

        callback_return = self.callback_function(
            retcode=retval.returncode,
            log_file=logfile_path
        )

        if isinstance(callback_return, tuple):
            success = callback_return[0]
        else:
            success = callback_return

        if not success:
            logging.info(f'Task callback indicates task FAILED. See {logfile_path}')
        else:
            logging.info(f'Task callback indicates task passed.')

        logging.info(f'Task completed: {self.name}\n\n')

        return success, logfile_path


class Flow:
    def __init__(self):
        self._flow_list: List[Task] = []

    def append(self,
               task: Task,
               ):
        self._flow_list.append(task)

    def run(self):
        logging.info(f'Starting flow.')
        ret_codes, log_files = [], []
        for task in self._flow_list:
            code, logfile = task.run()
            ret_codes.append(code)
            log_files.append(logfile)

        logging.info(f'Flow complete.\n'
                     f'Log files can be found at: {log_files}\n\n')

        if all(return_code for return_code in ret_codes):
            logging.info(f'All tasks run succesfully\n\n')
        else:
            for ind, (code, task) in enumerate(zip(ret_codes, self._flow_list)):
                if not code:
                    logging.info(f'Task # {ind} FAILED:   {task}')
            logging.info(f'\n\n')

        return ret_codes, log_files
