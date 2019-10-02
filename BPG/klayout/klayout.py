from bag.io.file import readlines_iter, open_temp, read_file
from bag.concurrent.core import SubProcessManager
import subprocess
from pathlib import Path
import os
import logging
from collections import namedtuple

from .dataprep_klayout import DataprepKlayout

from typing import TYPE_CHECKING, Dict, Optional, Tuple, Callable, List

if TYPE_CHECKING:
    pass


def dataprep_step_callback(retcode, log_file):
    if not os.path.isfile(log_file):
        return False, True, ''

    cmd_output = read_file(log_file)
    pass_str = 'klayout::DRC-H EXECUTIVE MODULE COMPLETED'
    dataprep_completed = pass_str in cmd_output

    dataprep_errors = 'ERROR' in cmd_output

    if dataprep_errors:
        logging.error(f'ERROR: klayout did not complete or had errors when running. Please consult the log: {log_file}')

    return dataprep_completed, dataprep_errors, log_file


FlowStep = namedtuple('FlowStep', 'command logfile run_dir callback_function step_name')


class KlayoutDataprep:
    """

    """

    def __init__(self,
                 run_dir: str,
                 photonic_tech_info,
                 grid,
                 **kwargs,
                 ):

        self.photonic_tech_info = photonic_tech_info
        self.grid = grid

        self._run_dir = run_dir
        os.makedirs(self._run_dir, exist_ok=True)

        max_workers = kwargs.get('max_workers', None)
        cancel_timeout = kwargs.get('cancel_timeout_ms', None)
        if cancel_timeout is not None:
            cancel_timeout /= 1e3

        self._manager = SubProcessManager(max_workers=max_workers, cancel_timeout=cancel_timeout)

        # No debug in the args to __init__.  Not intended for non-dev use.
        self.debug = False

    def run(self,
            template_runset: str,
            step_name: str,
            runset_params: Dict[str, str] = None,
            callback_function: Callable = lambda **k: None,
            **kwargs
            ) -> None:

        """
        Create a custom klayout step and run it.
        Klayout is run in the _run_dir of the current KlayoutDataprep object

        Parameters
        ----------
        template_runset: str
            A path to the template runset that should be run.
        step_name: str
            The name of the Klayout step being run

        runset_params: Dict
            A dictionary of keyword value pairs for Klayout runset variables.
            Important examples include:

            drcRulesFile : Rule file to run
            drcLayoutPaths : Path to the input layout file
            drcResultsFile : Path to the output database file (gds, db, or other).

        callback_function: Callable
            A function handle to a callback function that should be run after the flow step is run.
            Callback function must accept two arguments by name: retcode, and logfile_name
        kwargs

        Returns
        -------

        """
        flow_step = self.create_flow_step(
            template_runset=template_runset,
            step_name=step_name,
            runset_params=runset_params,
            callback_function=callback_function,
            kwargs=kwargs
        )
        self.run_flow_step(flow_step)

    def run_dataprep(self,
                     file_in: str,
                     file_out: str,
                     is_lumerical_dataprep: bool = False,
                     ):
        """
        Run the klayout dataprep flow.

        Returns
        -------

        """
        file_temp = file_in + '_temp.gds'

        dataprep_flow = self.setup_dataprep_flow(file_in,
                                                 file_out,
                                                 file_temp,
                                                 is_lumerical_dataprep=is_lumerical_dataprep
                                                 )
        self.run_flow(dataprep_flow)

        if not self.debug:
            os.remove(file_temp)

    def run_flow(self,
                 flow: List[FlowStep],
                 ) -> Tuple[List, List]:

        ret_codes, log_files = [], []

        logging.info(f'**********\n'
                     f'Running Klayout Flow\n')
        for flow_step in flow:
            code, logfile = self.run_flow_step(flow_step)
            ret_codes.append(code)
            log_files.append(logfile)

        logging.info(f'Klayout flow complete\n'
                     f'Log files can be found at: {log_files}')

        logging.info(f'**********\n')

        return ret_codes, log_files

    @staticmethod
    def run_flow_step(flow_step: FlowStep):
        cmd = flow_step.command
        run_dir = flow_step.run_dir
        logfile = flow_step.logfile
        step_name = flow_step.step_name
        callback_func = flow_step.callback_function

        logfile_path = str(Path(run_dir) / logfile)

        logging.info(
              f'Running Klayout command for flow step: {step_name}\n'
              f'Press <Ctrl> + C to exit.\n')

        with open(logfile_path, 'w') as f:
            retval = subprocess.run(cmd, stdout=f)

        callback_func(
            retcode=retval.returncode,
            log_file=logfile_path
        )
        logging.info(f'Klayout command completed.\n')

        return retval.returncode, logfile_path

    def setup_dataprep_flow(self,
                            file_in: str,
                            file_out: str,
                            file_temp: str,
                            is_lumerical_dataprep: bool = False,
                            ):
        dataprep_flow = []
        run_dir = self._run_dir

        # Step 1: Dataprep operations
        step_name = 'DataprepOps'
        dataprep_rules_content = DataprepKlayout(photonic_tech_info=self.photonic_tech_info,
                                                 grid=self.grid,
                                                 file_in=file_in,
                                                 file_out=file_temp,
                                                 dataprep_type=0,
                                                 is_lumerical_dataprep=is_lumerical_dataprep,
                                                 flat_in_calibre=True,
                                                 ).dataprep()
        rules_file = os.path.join(run_dir, step_name + '.drc')
        with open(rules_file, 'w') as f:
            f.writelines(dataprep_rules_content)

        dataprep_flow.append(
            self.create_flow_step(
                step_name=step_name,
                callback_function=dataprep_step_callback
            )
        )

        # Step 2: Scale the GDS back to correct precision
        step_name = 'Rescale'
        dataprep_rules_content = DataprepKlayout(photonic_tech_info=self.photonic_tech_info,
                                                 grid=self.grid,
                                                 file_in=file_temp,
                                                 file_out=file_out,
                                                 dataprep_type=1,
                                                 is_lumerical_dataprep=is_lumerical_dataprep,
                                                 flat_in_calibre=False
                                                 ).dataprep()
        rules_file = os.path.join(run_dir, step_name + '.drc')
        with open(rules_file, 'w') as f:
            f.writelines(dataprep_rules_content)

        dataprep_flow.append(
            self.create_flow_step(
                step_name=step_name,
                callback_function=dataprep_step_callback
            )
        )

        return dataprep_flow

    def create_flow_step(self,
                         step_name: str,
                         callback_function: Callable = lambda **k: None,
                         **kwargs,
                         ) -> FlowStep:
        """
        Create a FlowStep object describing the klayout operation to run.

        Parameters
        ----------
        step_name: str
            The name of the klayout step being run
        callback_function: Callable
            A function handle to a callback function that should be run after the flow step is run.
            Callback function must accept two arguments by name: retcode, and logfile_name
        kwargs

        Returns
        -------
        flowstep: FlowStep
            A FlowStep object describing the operation to be run in klayout.
        """
        log_name = step_name + '_Log'
        runset_name = step_name + '.drc'
        runset_filepath = str(Path(self._run_dir) / runset_name)

        with open_temp(prefix=log_name, dir=self._run_dir, delete=False) as logf:
            log_file = logf.name

        cmd = ['klayout', '-b', '-r', runset_filepath]

        return FlowStep(command=cmd,
                        logfile=log_file,
                        run_dir=self._run_dir,
                        callback_function=callback_function,
                        step_name=step_name)
