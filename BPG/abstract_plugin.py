"""
This module contains abstract classes that should be subclassed to create a new plugin to BPG.

Each plugin should have a main interface class that takes a configuration dictionary as input to the __init__(). Then
it should expose several methods to perform basic functions needed by the plugin. Examples include exporting a content
list to another representation, setting up simulations and testbench scripts, etc.
"""

import abc

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from BPG.content_list import ContentList


class AbstractPlugin(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def export_content_list(self,
                            content_list: "ContentList",
                            ):
        """
        This method will take a content list and generate a script that specifies the structure in the desired software
        package. Ex: for lumerical, export_content_list will generate an lsf file that tells lumerical how to
        generate the exact same layout

        Parameters
        ----------
        content_list
        """
        pass
