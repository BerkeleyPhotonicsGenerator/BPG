# -*- coding: utf-8 -*-

from typing import TYPE_CHECKING, Tuple, Union, List, Optional, Dict, Any, Iterator, Iterable, Generator
import numpy as np
from .photonics_port import Port
import gdspy as gdspy
import datetime
import struct
import abc

num_type = Union[int, float]
coord_type = Tuple[num_type, num_type]

"""
General GDSii stream notes:
    - all about records
    - records start with 2 bytes saying how long (in bytes) the record is (including the 2 bytes that designate size)
    - next 2 bytes are the record type and data type
    - See http://boolean.klaasholwerda.nl/interface/bnf/gdsformat.html
       http://www.cnf.cornell.edu/cnf_spie9.html
    - ex: record type for structure name is 06, data type is 06.
        - If we wanted to stream out a structure name, then we need:
          2 BYTES size of record =  2 + 2 + len(name)   where 1st 2 is size of length, 2nd 2 is size of record/data type
          ie:  we would stream out:    4 + len(name)     0606     name    encoded in hex bytes  (2 hex symbols per byte)
"""


class PhotonicCell(abc.ABC):
    """
    Needs:
        Dictionary containing parameters
            - make abstract methods so each object type are required to implement
            - similar with "draw layout" type function
        Origin & Orientation
        Hooks into GDSPY
        Ports
            - Methods for placing by ports
    is_primitive ?
    primitive_shapes
    """
    # TODO: __slots__
    def __init__(self,
                 name,  # type: str
                 type=None,  # type: str
                 origin=None,  # type: coord_type
                 ):

        self.name = name
        self.type = type
        if origin is None:
            self.origin = np.array([0.0, 0.0])
        else:
            self.origin = np.array([origin[0], origin[1]])
        self.subcells = {}   # TODO: Caching of subcells
        # Should be a list / dict of some structure that contains location, rotation, mirroring, and name of subcell
        self.primitive_shapes = []
        self.ports = []
        self.labels = []

    @abc.abstractmethod
    def draw_layout(self):
        pass

    def to_gds(self,
               multiplier,  # type: num_type
               ):
        self.draw_gds(multiplier=multiplier)

    def add(self,
            element,
            loc,  # type: coord_type
            ):
        if isinstance(element, PhotonicCell):
            # Add to objects
            #
            self.subcells[PhotonicCell.name] = dict(
                name=PhotonicCell.name,
                loc=loc,
                rotation=0,
                mirroring=False,
            )
        elif isinstance(element, Port):
            # Add to ports
            pass
        else:
            # Add to primitive shapes
            pass

    def add_polygon(self,
                    points,
                    layer,
                    ):
        # add origin to all points?
        pass

    def add_rect(self,
                 point1,
                 point2,
                 layer,
                 ):
        print("in add_rect")
        asdf = gdspy.Rectangle(point1, point2, layer)
        print(asdf)
        self.primitive_shapes.append(asdf)
        print(self.primitive_shapes)

    def add_block(self,
                  block,
                  loc,
                  ):
        if isinstance(block, PhotonicCell):
            PhotonicCell.origin = np.array([loc[0], loc[1]])
            self.objects.append(PhotonicCell)

    def draw_gds(self,
                 multiplier,  # type: num_type
                 ):

        """

        :param multiplier:
        :return:
        """

        # TODO
        """
        Right now, this just will write GDS info for the current cell.
        Need to figure out way to loop over all cells, and cache properly...
        """
        # Get time and date
        now = datetime.datetime.today()
        # Pad name to be even to ensure records are properly sized
        name = self.name
        if len(name) % 2 != 0:
            name = name + '\0'

        # Define the structure record
        output = struct.pack('>14h', 28, 0x0502,
                             now.year, now.month, now.day, now.hour, now.minute, now.second,
                             now.year, now.month, now.day, now.hour, now.minute, now.second)

        # Define the structure name
        output += struct.pack('>2h', 4 + len(name), 0x0606) + name.encode('ascii')

        # Loop over primitive shapes and add to stream
        output += b''.join(element.to_gds(multiplier) for element in self.primitive_shapes)

        # Loop over labels and add to stream
        output += b''.join(label.to_gds(multiplier) for label in self.labels) \



        """
        # 
        # http://www.cnf.cornell.edu/cnf_spie9.html
        # http://jupiter.math.nctu.edu.tw/~weng/courses/IC_2007/PROJECT_NCTU_MATH/CELL_LAYOUT/The%20GDSII%20Stream%20Format.htm
        # <SREF> ::=	SREF [EFLAGS] [PLEX] SNAME [<strans>] XY
        #  [<strans>] = FLAGS   MAG  ANGLE   Flags: 15 = x-reflection, 2 = mag, 1 = angle;
        #                                    MAG/ANGLE: both 8 byte reals, angle in degrees
        """
        # Intelligent hashing here?  maybe...
        for subcell in self.subcells:
            # Pad name to be even to ensure records are properly sized
            name = subcell.name           # reference cell name
            rotation = subcell.rotation
            magnification = subcell.magnification
            x_reflection = subcell.x_reflection

            if len(name) % 2 != 0:
                name = name + '\0'

            # Define SREF record
            data = struct.pack('>2h', 4, 0x0A00)
            # Define SNAME: name of referenced structure
            data += struct.pack('>2h', 4 + len(name), 0x1206) + name.encode('ascii')

            # Define STRANS and values
            if (rotation is not None) or (magnification is not None) or x_reflection:
                strans = 0
                strans_values = b''
                # Reflection sets bit 15 of STRANS
                if x_reflection:
                    strans += 0x8000
                # Magnification sets bit 2 of STRANS
                if not (magnification is None):
                    strans += 0x0004
                    strans_values += struct.pack('>2h', 12, 0x1B05) + gdspy._eight_byte_real(magnification)
                # Rotation sets bit 1 of STRANS
                if not (rotation is None):
                    strans += 0x0002
                    strans_values += struct.pack('>2h', 12, 0x1C05) + gdspy._eight_byte_real(rotation)
                data += struct.pack('>2hH', 6, 0x1A01, strans) + strans_values

            # Define XY
            data += struct.pack('>2h2l2h', 8, 0x1003,
                                int(round(self.origin[0] * multiplier)),
                                int(round(self.origin[1] * multiplier))
                                )

            # Define end of element
            data += struct.pack('>2h', 4, 0x1100)

            # Add subcell data to the output for the structure
            output += data

        # Define end of structure
        output += struct.pack('>2h', 4, 0x0700)

        return output

    @abc.abstractmethod
    def get_params_info(self):
        pass
