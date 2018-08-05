import h5py
import pandas
import matplotlib.pyplot as plt


class WaveguideAnalysis:
    """
    Class that imports generated FDE data from Lumerical on a single mode waveguide and plots the neff
    """
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.data = {}

    def plot_data(self):
        plt.plot(self.data['neff'], 'k.-')
        plt.grid(True)
        plt.title('Effective index vs Waveguide width')
        plt.xlabel('Sweep num')
        plt.ylabel('neff')
        plt.show()

    def read_data(self, to_read=None):
        # data = pandas.read_hdf(data_dir)
        with h5py.File(data_dir) as f:
            for key in f.keys():
                self.data[key] = f[key].value


if __name__ == '__main__':
    data_dir = 'gen_libs/Generated_Waveguide/data/SingleModeWaveguide0.mat'
    sim_data = WaveguideAnalysis(data_dir)
    sim_data.read_data(to_read=None)
    # sim_data.plot_data()
