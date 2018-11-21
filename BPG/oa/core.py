import os
import time
import logging

from bag.io import get_encoding
from BPG.abstract_plugin import AbstractPlugin

try:
    import cybagoa
except ImportError:
    cybagoa = None


class OAPlugin(AbstractPlugin):
    def __init__(self, config):
        AbstractPlugin.__init__(self, config)
        self.config = config
        self._prj = self.config['bagProject']
        self._use_cybagoa = False
        self._pure_oa = False
        self._lib_name = self.config['lib_name']
        self._grid = self.config['grid']

    def export_content_list(self, content_list, **kwargs):
        """
        Exports the physical design into the open access format

        Parameters
        ----------
        content_list

        Returns
        -------
        """
        if self._prj is None:
            raise ValueError('BagProject is not defined.')
        elif self._use_cybagoa:
            # remove write locks from old layouts
            cell_view_list = [(item[0], 'layout') for item in content_list]
            if self._pure_oa:
                pass
            else:
                # create library if it does not exist
                self._prj.create_library(self._lib_name)
                self._prj.release_write_locks(self._lib_name, cell_view_list)

            logging.info(f'Instantiating layout')

            # create OALayouts
            start = time.time()
            if 'CDSLIBPATH' in os.environ:
                cds_lib_path = os.path.abspath(os.path.join(os.environ['CDSLIBPATH'], 'cds.lib'))
            else:
                cds_lib_path = os.path.abspath('./cds.lib')
            with cybagoa.PyOALayoutLibrary(cds_lib_path, self._lib_name, self._prj.default_lib_path,
                                           self._prj.tech_info.via_tech_name,
                                           get_encoding()) as lib:
                lib.add_layer('prBoundary', 235)
                lib.add_purpose('label', 237)
                lib.add_purpose('drawing1', 241)
                lib.add_purpose('drawing2', 242)
                lib.add_purpose('drawing3', 243)
                lib.add_purpose('drawing4', 244)
                lib.add_purpose('drawing5', 245)
                lib.add_purpose('drawing6', 246)
                lib.add_purpose('drawing7', 247)
                lib.add_purpose('drawing8', 248)
                lib.add_purpose('drawing9', 249)
                lib.add_purpose('boundary', 250)
                lib.add_purpose('pin', 251)

                for cell_name, oa_layout in content_list:
                    lib.create_layout(cell_name, 'layout', oa_layout)
            end = time.time()
            logging.info(f'Layout instantiation took {end-start:.4g}s')
        else:
            # create library if it does not exist
            self._prj.create_library(self._lib_name)

            logging.info(f'Instantiating layout')

            via_tech_name = self._grid.tech_info.via_tech_name
            start = time.time()
            self._prj.instantiate_layout(self._lib_name, 'layout', via_tech_name, content_list)
            end = time.time()
            logging.info(f'Layout instantiation took {end-start:.4g}s')
