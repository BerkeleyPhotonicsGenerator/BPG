import h5py
import pandas
import scipy.io as sp
import matplotlib.pyplot as plt
import numpy as np


class WaveguideAnalysis:
    """
    Class that imports generated FDE data from Lumerical on a single mode waveguide and plots the neff
    """
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.data = {}

    def plot_neff(self):
        #plt.plot(self.data['neff'], 'k.-')
        plt.grid(True)
        plt.title('Effective index vs Waveguide width')
        plt.xlabel('Sweep num')
        plt.ylabel('neff')
        plt.show()

    def read_data(self):
        # data = pandas.read_hdf(data_dir)
        self.data = sp.loadmat(self.data_dir)
        #print(self.data)
        print(self.data.keys())
        # with h5py.File(data_dir) as f:
        #     for key in f.keys():
        #         self.data[key] = f[key].value

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
    sim_data = WaveguideAnalysis(data_dir)
    sim_data.read_data()
    # sim_data.plot_power()
    sim_data.plot_data()
