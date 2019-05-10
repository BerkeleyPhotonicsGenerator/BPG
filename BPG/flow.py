
import subprocess
from pathlib import Path
import logging
from typing import TYPE_CHECKING, Callable, List

if TYPE_CHECKING:
    pass


class Task:

    def __init__(self,
                 name: str,
                 command: list,
                 logfile: str,
                 run_dir: str,
                 callback_function: Callable = lambda **k: None,
                 ):
        self.name = name
        self.command = command
        self.logfile = logfile
        self.run_dir = run_dir
        self.callback_function = callback_function

    def run(self):
        logging.info(
            f'Task started: {self.name}\n'
            f'Press <Ctrl> + C to exit.\n'
        )

        logfile_path = str(Path(self.run_dir) / self.logfile)

        print(f'running command: {self.command}')

        with open(logfile_path, 'w') as f:
            retval = subprocess.run(self.command, stdout=f)

        returncode = retval
        self.callback_function(
            retcode=retval.returncode,
            log_file=logfile_path
        )
        logging.info(f'Task completed: {self.name}\n')

        return retval.returncode, logfile_path


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
                     f'Log files can be found at: {log_files}')