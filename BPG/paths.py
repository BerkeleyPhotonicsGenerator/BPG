import os
from pathlib import Path


class LumericalPath:
    """
    Class containing all important paths to be accessed by the Lumerical Generation scripts
    """
    def __init__(self):
        cwd = Path(os.path.abspath(__file__))
        self.root = cwd/'..'/'..'
        self.root = self.root.resolve()
        self.scripts = self.root/'scripts'
        if not self.scripts.exists():
            print('scripts directory does not exist, please create ./scripts. All generation scripts will be '
                  'placed here')
        self.data = self.root/'data'
        if not self.data.exists():
            print('data directory does not exist, please create ./data. All raw data will be placed here')
        self.techfile = os.environ['LUMERICAL_TECH']
        if not Path(self.techfile).exists():
            print('please create an environment variable LUMERICAL_TECH pointing to a layerstack.yaml file\n')
            print('A sample tech file is being loaded')
            self.techfile = cwd/'example_layerstack.yaml'
