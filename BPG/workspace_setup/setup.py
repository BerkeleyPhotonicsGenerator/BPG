import os
import shutil
from pathlib import Path
from shutil import copyfile, copytree, rmtree


def copy_setup_files():
    # The root directory is where the workspace will be created, setup files are stored locally
    root = os.getcwd()
    install_dir = os.path.dirname(os.path.realpath(__file__))

    # Create temp directory
    tmp_dir = Path(root) / 'tmp'
    tmp_dir.mkdir(exist_ok=True)

    # Copy over basic files
    copyfile(install_dir + '/.gitignore', root + '/.gitignore')
    copyfile(install_dir + '/sourceme.sh', root + '/sourceme.sh')
    copyfile(install_dir + '/sourceme.csh', root + '/sourceme.csh')
    copytree(install_dir + '/../examples' + '/tech/', root + '/example_tech',
             dirs_exist_ok=True)
    copytree(install_dir + '/../examples', root + '/examples',
             dirs_exist_ok=True,
             ignore=shutil.ignore_patterns('tech/'))
    copyfile(install_dir + '/../examples/run_bpg.py',
             root + '/run_bpg.py')


def copy_test_files():
    # The root directory is where the workspace will be created, setup files are stored locally
    root = os.getcwd()
    install_dir = os.path.dirname(os.path.realpath(__file__))

    # Copy over basic files
    rmtree(root + '/bpg_test_suite', ignore_errors=True)
    copytree(install_dir + '/../../tests', root + '/bpg_test_suite')


if __name__ == '__main__':
    copy_setup_files()
