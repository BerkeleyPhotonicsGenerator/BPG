##
# Test hierarchy in gdspy
##

import numpy
import gdspy

# Create a new cell
A = gdspy.Cell('A')

# Add arbitrary shape to this cell
rect1 = gdspy.Rectangle((0, 0), (1, 1), layer=1)

A.add(rect1)

A.add(rect1.translate(5,5))



# Create 1 level higher of hierarchy
B = gdspy.Cell('B')

B.add(gdspy.CellReference(A, (0,0)))
B.add(gdspy.CellReference(A, (10, 2)))

C = gdspy.Cell('C')

C.add(gdspy.CellReference(B, (-50, -50)))

D = gdspy.Cell('D')

rect2 = rect1
D.add(rect2.translate(4,1))

# gdspy.current_library.add(C)

gdspy.write_gds('test.gds', unit=1.0e-6, precision=1.0e-9)
asdf