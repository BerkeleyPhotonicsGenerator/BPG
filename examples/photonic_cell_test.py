# -*- coding: utf-8 -*-
import sys
sys.path.append('/Users/Sidney/Documents/Research/BPG')

import gdspy
import datetime
import struct
from BPG.PhotonicCell import PhotonicCell


#lib = gdspy.current_library


class TestRectCell(PhotonicCell):
    def draw_layout(self):
        print("in draw_layout")
        self.add_rect((0, 10), (20, 40), 1)
        print("end of draw layout")

    def get_params_info(self):
        pass


def write_gds(filename):
    precision = 1.0e-9
    unit = 1.0e-6
    if isinstance(filename, str):
        outfile = open(filename + '.gds', 'wb')
        close = True
    else:
        close = False
    now = datetime.datetime.today()
    name = filename if len(filename) % 2 == 0 else (filename + '\0')
    outfile.write(
        struct.pack('>19h', 6, 0x0002, 0x0258, 28, 0x0102, now.year,
                    now.month, now.day, now.hour, now.minute, now.second,
                    now.year, now.month, now.day, now.hour, now.minute,
                    now.second, 4 + len(name), 0x0206) +
        name.encode('ascii') + struct.pack('>2h', 20, 0x0305) +
        gdspy._eight_byte_real(precision / unit) + gdspy._eight_byte_real(precision))
    for cell in cell_list:
        print("here")
        outfile.write(cell.draw_gds(multiplier= unit / precision))

    outfile.write(struct.pack('>2h', 4, 0x0400))
    if close:
        outfile.close()

testcell = TestRectCell(name='test')
cell_list = [testcell]

testcell.draw_layout()

write_gds('test_1')
