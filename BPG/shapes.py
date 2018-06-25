"""
shapes.py
Created by Pavan Bhargava 05/07/2018
Contains classes that describe the dimensions of drawn lumerical objects
"""

import numbers


class Coordinate:
    def __init__(self, axis, loc, res=.001, unit='e-6'):
        """
        This class represents a single coordinate location along one of the cartesian axes
        """
        self._res = res
        self._axis = None
        self._loc = None
        self._unit = unit

        self.axis = axis
        self.loc = loc

    """ Magic Methods """

    def __repr__(self):
        return 'Coordinate(axis={}, loc={})'.format(self.axis, self.loc)

    def __str__(self):
        return str(self.loc) + self._unit

    """ Getters and Setters """

    @property
    def axis(self):
        return self._axis

    @axis.setter
    def axis(self, axis):
        if all([axis != 'x',
                axis != 'y',
                axis != 'z']):
            # if the provided input does not correspond to a standard axis
            raise ValueError('{} does not correspond to a valid axis'.format(axis))
        else:
            self._axis = axis

    @property
    def loc(self):
        return round(self._loc * self._res, 3)

    @loc.setter
    def loc(self, val):
        if isinstance(val, numbers.Real):
            self._loc = int(round(val / self._res))
        else:
            raise ValueError('Input does not represent a valid coordinate description')


class Rectangle_Base:
    def __init__(self):
        """
        This class creates a lumerical script file which generates rectangle shapes
        """
        # Each coordinate axis has a max and min value
        self.x_min = Coordinate('x', 0)
        self.x_max = Coordinate('x', 0)
        self.y_min = Coordinate('y', 0)
        self.y_max = Coordinate('y', 0)
        self.z_min = Coordinate('z', 0)
        self.z_max = Coordinate('z', 0)

    def set_center_span(self, dim, center, span):
        """
        Adjusts the size of the rectangle by setting the center and span of the shape along the given dimension

        Parameters:
        ----------
        dim : str
            'x', 'y', or 'z' for which direction to apply the size adjustment
        center : float
            coordinate value of the center of the shape along the provided dimension
        span : float
            length value of the shape along the provided dimension
        """
        min = center - span/2
        max = center + span/2
        self.set_min_max(dim, min, max)

    def set_min_max(self, dim, min, max):
        """
        Adjusts the size of the rectangle by setting the center and span of the shape along the given dimension

        Parameters:
        ----------
        dim : str
            'x', 'y', or 'z' for which direction to apply the size adjustment
        min : float
            coordinate value of the minimum of the shape along the provided dimension
        max : float
            coordinate value of the maximum of the shape along the provided dimension
        """
        if dim == 'x':
            self.x_min.loc = min
            self.x_max.loc = max
        elif dim == 'y':
            self.y_min.loc = min
            self.y_max.loc = max
        elif dim == 'z':
            self.z_min.loc = min
            self.z_max.loc = max
        else:
            raise ValueError('provided dimension is invalid')


    def export(self):
        """
        Prints the lumerical commands required to generate the specified rectangle shape
        """
        prop_file = []
        prop_file.append('set("x min", {});\n'.format(self.x_min))
        prop_file.append('set("x max", {});\n'.format(self.x_max))
        prop_file.append('set("y min", {});\n'.format(self.y_min))
        prop_file.append('set("y max", {});\n'.format(self.y_max))
        prop_file.append('set("z min", {});\n'.format(self.z_min))
        prop_file.append('set("z max", {});\n'.format(self.z_max))
        return prop_file


class Rectangle(Rectangle_Base):
    def __init__(self, name, material_info):
        """
        Class for creating rectangular objects in lumerical simulation
        """
        Rectangle_Base.__init__(self)
        # Initialize empty variables
        self.name = name
        self.mesh_order = None

        # Initialize the rectangle with technology specific information
        self.material_info = material_info
        self.set_min_max('z', self.material_info['z_min'], self.material_info['z_max'])
        self.alpha = self.material_info['alpha']

    def export(self):
        prop_file = []
        prop_file.append('addrect;\n')
        prop_file.append('set("name", "{}");\n'.format(self.name))
        prop_file.append('set("material", "{}");\n'.format(self.material_info['material']))
        prop_file.append('set("alpha", {});\n'.format(self.alpha))
        if self.mesh_order is not None:
            prop_file.append('set("override mesh order from material database", 1);\n')
            prop_file.append('set("mesh order", {});\n'.format(self.mesh_order))
        prop_file += Rectangle_Base.export(self)
        return prop_file


if __name__ == '__main__':
    test = Rectangle('test_rect', 'rx')
    test.set_center_span('x', 0, .5)
    test.set_center_span('y', 0, 4)
    print(''.join(test.export()))
