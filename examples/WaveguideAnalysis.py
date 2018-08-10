import pandas as pd
import scipy.io as sp
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr


class FDEAnalysis:
    """
    Class that imports generated FDE data from Lumerical and prepares the data for analysis. Currently only supports
    handling for a single input mode
    """

    def __init__(self, data_path):
        """
        Initializes a new FDEAnalysis class by loading and cleaning data from the file data_dir

        Parameters
        ----------
        data_path : str
            path to the data file
        """
        # Store the raw info so that it can always be manipulated by subclasses
        self.data_path = data_path
        self.raw_data = None

        # Attributes holding all of the formatted data
        self.x = None
        self.y = None
        self.z = None
        self.f = None
        self.surface_normal = None
        self.loss = None
        self.neff = None
        self.Ex = None

        # Upon init of class, read and perform data cleaning
        self.read_data()
        self.extract_data()

    def read_data(self):
        """
        Grabs data from file stored in self.data_dir attr

        Assumes that data is provided in the matlab v5.0 .mat format. SciPy's loadmat function does not handle
        MATLAB v7.3 .mat file format
        """
        self.raw_data = sp.loadmat(self.data_path)

    def extract_data(self):
        """ Cleans raw data up and creates xarray instances to handle them """
        self.x = np.squeeze(self.raw_data['x'])
        self.y = np.squeeze(self.raw_data['y'])
        self.z = np.squeeze(self.raw_data['z'])
        # TODO: self.f
        # TODO: self.loss
        # TODO: Make Ex not hardcoded in the 'y' direction
        self.Ex = xr.DataArray(np.abs(self.raw_data['Ex']), dims=['x', 'y', 'z'], coords={'x': self.x,
                                                                                          'y': np.array([0]),
                                                                                          'z': self.z})
        self.neff = self.raw_data['neff']

    def plot_power(self):
        plt.plot(self.raw_data['power'])
        plt.grid(True)
        plt.title('Effective index vs Waveguide width')
        plt.xlabel('Sweep num')
        plt.ylabel('neff')
        plt.show()

    def plot_data(self):
        plt.ticklabel_format(axis='both', style='sci', scilimits=(-2, 2))
        x_raw, z_raw = np.squeeze(self.raw_data['x']), np.squeeze(self.raw_data['z'])
        X, Z = np.meshgrid(x_raw, z_raw, indexing='ij')
        plt.contour(X, Z, np.abs(self.raw_data['Ex']))
        plt.grid(True)
        plt.title('Ex')
        plt.xlabel('X')
        plt.ylabel('Z')
        plt.show()


class WaveguideAnalysis(FDEAnalysis):
    """
    Class that imports generated FDE data from Lumerical on a single mode waveguide and plots the neff
    """

    def __init__(self, data_path):
        FDEAnalysis.__init__(self, data_path)

    def plot_neff(self):
        # plt.plot(self.data['neff'], 'k.-')
        plt.grid(True)
        plt.title('Effective index vs Waveguide width')
        plt.xlabel('Sweep num')
        plt.ylabel('neff')
        plt.show()

    def plot_power(self):
        plt.plot(self.data['power'])
        plt.grid(True)
        plt.title('Effective index vs Waveguide width')
        plt.xlabel('Sweep num')
        plt.ylabel('neff')
        plt.show()

    def plot_data(self):
        plt.ticklabel_format(axis='both', style='sci', scilimits=(-2, 2))
        x_raw, z_raw = np.squeeze(self.data['x']), np.squeeze(self.data['z'])
        X, Z = np.meshgrid(x_raw, z_raw, indexing='ij')
        plt.contour(X, Z, np.abs(self.data['Ex']))
        plt.grid(True)
        plt.title('Ex')
        plt.xlabel('X')
        plt.ylabel('Z')
        plt.show()


if __name__ == '__main__':
    data_dir = 'gen_libs/Generated_Waveguide/data/data3.mat'
    # sim_data = WaveguideAnalysis(data_dir)
    sim_data = FDEAnalysis(data_dir)
    print(sim_data.neff)
