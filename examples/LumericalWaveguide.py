import BPG


class SingleModeWaveguide(BPG.LumericalGenerator):
    def __init__(self, specfile):
        """ Class for generating a single mode waveguide shape in Lumerical """
        BPG.LumericalGenerator.__init__(self, specfile)

    def draw_layout(self):
        """ Specifies the creation of the lumerical shapes """
        # Add cladding
        clad = self.add_rect(name='clad', layer='cladding')
        clad.set_center_span('x', center=0, span=4)
        clad.set_center_span('y', center=0, span=4)

        # Add buried oxide layer
        box = self.add_rect(name='box', layer='box')
        box.set_center_span('x', center=0, span=4)
        box.set_center_span('y', center=0, span=4)

        # Add 1st waveguide
        wg0 = self.add_rect(name='wg0', layer='rx')
        wg0.set_center_span('x', center=0, span=4)
        wg0.set_center_span('y', center=1, span=.5)

        # Add 2nd waveguide
        wg0 = self.add_rect(name='wg1', layer='rx')
        wg0.set_center_span('x', center=0, span=4)
        wg0.set_center_span('y', center=-1, span=.5)


if __name__ == '__main__':
    specfile = './example_spec_file.yaml'
    wg = SingleModeWaveguide(specfile=specfile)
    wg.draw_layout()
    wg.export_to_lsf()
