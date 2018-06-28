from bag.core import BagProject
class PhotonicBagProject(BagProject):
    """The main bag controller class.

    This class mainly stores all the user configurations, and issue
    high level bag commands.

    Parameters
    ----------
    bag_config_path : Optional[str]
        the bag configuration file path.  If None, will attempt to read from
        environment variable BAG_CONFIG_PATH.
    port : Optional[int]
        the BAG server process port number.  If not given, will read from port file.

    Attributes
    ----------
    bag_config : Dict[str, Any]
        the BAG configuration parameters dictionary.
    tech_info : bag.layout.core.TechInfo
        the BAG process technology class.
    """

    def __init__(self, bag_config_path=None, port=None):
        '''
        # create design module database.
        try:
            lib_defs_file = _get_config_file_abspath(self.bag_config['lib_defs'])
        except ValueError:
            lib_defs_file = ''
        sch_exc_libs = self.bag_config['database']['schematic']['exclude_libraries']
        self.dsn_db = ModuleDB(lib_defs_file, self.tech_info, sch_exc_libs, prj=self)

        if port is not None:
            # make DbAccess instance.
            dealer = ZMQDealer(port, **dealer_kwargs)
            db_cls = _import_class_from_str(self.bag_config['database']['class'])
            self.impl_db = db_cls(dealer, bag_tmp_dir, self.bag_config['database'])
            self._default_lib_path = self.impl_db.default_lib_path
        else:
            self.impl_db = None  # type: Optional[DbAccess]
            self._default_lib_path = DbAccess.get_default_lib_path(self.bag_config['database'])

        # make SimAccess instance.
        sim_cls = _import_class_from_str(self.bag_config['simulation']['class'])
        self.sim = sim_cls(bag_tmp_dir, self.bag_config['simulation'])  # type: SimAccess
        '''
        self.tech_info = PTech()


class PTech():
    def __init__(self):
        self.resolution = 0.001
        self.layout_unit = 0.000001
        self.via_tech_name = ''
        self.pin_purpose = None

    def get_layer_id(self, layer):
        pass


    def finalize_template(self, a):
        pass

    def use_flip_parity(self):
        pass