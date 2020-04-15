import BPG


class SingleModeWaveguide(BPG.PhotonicTemplateBase):
    """ 
    This is an example that demonstrates the basic pattern for layout generators. Every generator is a class which
    inherits from BPG.PhotonicTemplateBase. This parent class supplies all of the basic methods for adding primitive
    objects like polygons, ports, vias, etc. As a user, you can call these methods to describe an algorithm for creating
    any photonic device. BPG will internally instantiate this generator class and call the draw_layout() method to
    actually draw the layout.

    In a later example we will demonstrate how to call other generators from your generator class to construct more
    complex hierarchical layouts.

    Parameters
    ----------
    width : float
        Width of the waveguide to be drawn
    length : float
        Length of the waveguide to be drawn
    """
    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        # Just like any other Python class, it is critical that you call the __init__ of the parent class. You
        # don't need to understand or modify any of these arguments.
        BPG.PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    @classmethod
    def get_params_info(cls):
        """ 
        This method is required! It returns a dictionary with every user configurable parameter. If one of these
        parameters is not provided, BPG will return an error with the missing parameter and description. Note that these
        parameters are also used for caching. If you run the same generator class with the same set of parameters, BPG
        will automatically re-use the first version rather than regenerating things from scratch.

        When this generator class is run, BPG automatically extracts these parameters from the user parameter dictionary 
        and stores them in a variable called self.params for your use.
        """
        return dict(
            width='Waveguide width in microns',
            length='Waveguide length in microns'
        )

    @classmethod
    def get_default_param_values(cls):
        """
        If you don't want to force the user for provide all parameters, you can return sensible defaults here.
        """
        return dict(
            width=.6,
            length=10
        )

    def draw_layout(self):
        """
        This is the core method that describes the algorithm for drawing your layout. If this method is not provided,
        you will get an error saying the abstract methods are not implemented!
        """

        # Here we access user provided parameters width and length that were specified in self.get_params_info()
        width = self.params['width']
        length = self.params['length']

        # PhotonicTemplateBase contains a number of methods to add primitive shapes to the layout. In this case, we
        # create a rectangle on the ('SI', 'drawing') layer with the user specified width and height centered at (0, 0).
        # To see all of the other methods to create primitive shapes, check out PhotonicTemplateBase in BPG/template.py
        self.add_rect(layer=('SI', 'drawing'),
                      coord1=(-.5 * width, -.5 * length),
                      coord2=(.5 * width, .5 * length)
                      )

        # ports are useful markers for rotation and alignment. This concept will be explored in later examples. This port
        # in particular will be used in WaveguideTB.py to align a finite difference eigenmode solver for lumerical simulation
        self.add_photonic_port(name='FDEPort',
                               center=(0, 0),
                               orient='R90',
                               width=width,
                               layer='SI')


if __name__ == '__main__':
    """ 
    This is a quick unit test to run the waveguide class and generate a GDS and LSF file
    """

    # This yaml file provides all of the details for which class to generate, which parameters to use when generating, what
    # to name the generated gds, what technology information to use, and much more
    spec_file = 'BPG/examples/specs/WaveguideTB.yaml'

    # BPG's PhotonicLayoutManager handles the details of initializing a generator class and running common tasks like generating
    # GDS or LSF files. It takes a spec file as input to do all initial configuration
    plm = BPG.PhotonicLayoutManager(spec_file)

    # generate_content() is the first step of the process, which actually initializes and runs the generator class to form a 
    # database of layout shapes. This database is a convenient intermediate representation that can be used as a source for
    # GDS generation, LSF generation, or anything else
    plm.generate_content()

    # generate_gds() automatically reads to current content database and creates a gds from it. The name of the gds is specified in
    # the spec file
    plm.generate_gds()

    # By default generate_content() stores a hierarchical representation of layout content. However, some software requires a
    # flat representation of the layout. This method generates a flattened version of the content database
    plm.generate_flat_content()

    # This will create a lumerical script file that describes the current layout
    plm.generate_lsf()
