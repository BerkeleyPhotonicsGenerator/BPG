######################################################################
#                                                                    #
#  Copyright 2009-2018 Lucas Heitzmann Gabrielli.                    #
#  This file is part of gdspy, distributed under the terms of the    #
#  Boost Software License - Version 1.0.  See the accompanying       #
#  LICENSE file or <http://www.boost.org/LICENSE_1_0.txt>            #
#                                                                    #
######################################################################

import gdspy


def test_writer_gds(tmpdir):
    lib = gdspy.GdsLibrary()
    c1 = gdspy.Cell('gw_rw_gds_1', True)
    c1.add(gdspy.Rectangle((0, -1), (1, 2), 2, 4))
    c1.add(gdspy.Label('label', (1, -1), 'w', 45, 1.5, True, 5, 6))
    c2 = gdspy.Cell('gw_rw_gds_2', True)
    c2.add(gdspy.Round((0, 0), 1, number_of_points=32, max_points=20))
    c3 = gdspy.Cell('gw_rw_gds_3', True)
    c3.add(gdspy.CellReference(c1, (0, 1), -90, 2, True))
    c4 = gdspy.Cell('gw_rw_gds_4', True)
    c4.add(gdspy.CellArray(c2, 2, 3, (1, 4), (-1, -2), 180, 0.5, True))
    lib.add((c1, c2, c3, c4))

    fname1 = str(tmpdir.join('test1.gds'))
    writer1 = gdspy.GdsWriter(fname1, name='lib', unit=2e-3, precision=1e-5)
    for c in lib.cell_dict.values():
        writer1.write_cell(c)
    writer1.close()
    lib1 = gdspy.GdsLibrary()
    lib1.read_gds(fname1, 1e-3, {'gw_rw_gds_1': '1'}, {2: 4}, {4: 2}, {6: 7})
    assert lib1.name == 'lib'
    assert len(lib1.cell_dict) == 4
    assert set(lib1.cell_dict.keys()) == {
        '1', 'gw_rw_gds_2', 'gw_rw_gds_3', 'gw_rw_gds_4'
    }
    c = lib1.cell_dict['1']
    assert len(c.elements) == len(c.labels) == 1
    assert c.elements[0].area() == 12.0
    assert c.elements[0].layer == 4
    assert c.elements[0].datatype == 2
    assert c.labels[0].text == 'label'
    assert c.labels[0].position[0] == 2 and c.labels[0].position[1] == -2
    assert c.labels[0].anchor == 4
    assert c.labels[0].rotation == 45
    assert c.labels[0].magnification == 1.5
    assert c.labels[0].x_reflection == True
    assert c.labels[0].layer == 5
    assert c.labels[0].texttype == 7

    c = lib1.cell_dict['gw_rw_gds_2']
    assert len(c.elements) == 2
    assert isinstance(c.elements[0], gdspy.Polygon) \
           and isinstance(c.elements[1], gdspy.Polygon)

    c = lib1.cell_dict['gw_rw_gds_3']
    assert len(c.elements) == 1
    assert isinstance(c.elements[0], gdspy.CellReference)
    assert c.elements[0].ref_cell == lib1.cell_dict['1']
    assert c.elements[0].origin[0] == 0 and c.elements[0].origin[1] == 2
    assert c.elements[0].rotation == -90
    assert c.elements[0].magnification == 2
    assert c.elements[0].x_reflection == True

    c = lib1.cell_dict['gw_rw_gds_4']
    assert len(c.elements) == 1
    assert isinstance(c.elements[0], gdspy.CellArray)
    assert c.elements[0].ref_cell == lib1.cell_dict['gw_rw_gds_2']
    assert c.elements[0].origin[0] == -2 and c.elements[0].origin[1] == -4
    assert c.elements[0].rotation == 180
    assert c.elements[0].magnification == 0.5
    assert c.elements[0].x_reflection == True
    assert c.elements[0].spacing[0] == 2 and c.elements[0].spacing[1] == 8
    assert c.elements[0].columns == 2
    assert c.elements[0].rows == 3

    fname2 = str(tmpdir.join('test2.gds'))
    with open(fname2, 'wb') as fout:
        writer2 = gdspy.GdsWriter(fout, name='lib2', unit=2e-3, precision=1e-5)
        for c in lib.cell_dict.values():
            writer2.write_cell(c)
        writer2.close()
    with open(fname2, 'rb') as fin:
        lib2 = gdspy.GdsLibrary()
        lib2.read_gds(fin)
    assert lib2.name == 'lib2'
    assert len(lib2.cell_dict) == 4
