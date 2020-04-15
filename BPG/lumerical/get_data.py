import h5py
# from lumopt.utilities.fields import Fields
import numpy as np
import scipy as sp
import scipy.constants
import scipy.io

USE_H5PY = False


def get_fields(data_file: 'str',
               field_obj_name: 'str',
               ):
    if USE_H5PY:
        f = h5py.File(data_file)

        field_obj = f[field_obj_name]

        x = np.array(field_obj['E']['x'])
        y = np.array(field_obj['E']['y'])
        z = np.array(field_obj['E']['z'])
        wl = np.array(field_obj['E']['lambda'])

        E = np.array(field_obj['E']['E'])

        index_x = np.array(field_obj['index']['index_x'])
        index_y = np.array(field_obj['index']['index_y'])
        index_z = np.array(field_obj['index']['index_z'])

        field_eps = np.stack((np.power(np.abs(index_x), 2),
                              np.power(index_y, 2),
                              np.power(index_z, 2)),
                             axis=-1
                             )
        D = E * field_eps * sp.constants.epsilon_0

        H = np.array(field_obj['H']['H'])

    else:
        f = scipy.io.loadmat(data_file, struct_as_record=False, squeeze_me=True)
        field_obj = f[field_obj_name]

        x = np.array(field_obj.E.x)
        y = np.array(field_obj.E.y)
        z = np.array(field_obj.E.z)
        wl = np.array(field_obj.E.__dict__['lambda'])

        E = np.array(field_obj.E.E)

        index_x = np.array(field_obj.index.index_x)
        index_y = np.array(field_obj.index.index_y)
        index_z = np.array(field_obj.index.index_z)

        field_eps = np.stack((np.power(np.abs(index_x), 2),
                              np.power(index_y, 2),
                              np.power(index_z, 2)),
                             axis=-1
                             )
        D = None  # E * field_eps * sp.constants.epsilon_0

        H = np.array(field_obj.H.H)


    return Field(x=x,
                 y=y,
                 z=z,
                 wl=wl,
                 E=E,
                 D=D,
                 H=H,
                 eps=field_eps,
                 )


def get_mode_monitor(data_file: str,
                     mode_monitor_name: str,
                     ):
    f = scipy.io.loadmat(data_file, struct_as_record=False, squeeze_me=True)
    monitor = f[mode_monitor_name]

    return monitor.__dict__


class Field:
    def __init__(self,
                 x,
                 y,
                 z,
                 wl,
                 E,
                 D,
                 H,
                 eps,
                 ):
        self.x = x
        self.y = y
        self.z = z
        self.wl = wl

        self.E = E
        self.D = D
        self.H = H
        self.eps = eps

