import os
from pathlib import Path
from shutil import copyfile, copytree


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
    copytree(install_dir + '/../examples' + '/tech', root + '/example_tech')
