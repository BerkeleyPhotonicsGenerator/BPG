import BPG
from BPG.lumerical_tb import LumericalTB


class WaveguideFDE(LumericalTB):
    """ Runs an FDE sim on the Waveguide example to get the modes """

    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        LumericalTB.__init__(self, temp_db, lib_name, params, used_names, **kwargs)

    def construct_tb(self):
        """
        Places the FDE solver at the port built into the waveguide class
        Note: LumericalTB automatically creates the Waveguide class and places it at the origin as stated in spec file
        """
        fde = self.add_FDE_solver()  # Create blank fde solver

        # Set the size of the simulation region
        fde.set_span('x', 4.0e-6)
        fde.set_span('z', 4.0e-6)

        # Move and orient the solver to match the port
        fde.align_to_port(self.dut_inst['FDEPort'])

        # Change the simulation settings
        fde.num_modes = 2
        fde.wavelength = 1.55e-6


if __name__ == '__main__':
    # Load a previous BPG Project if it exists, otherwise create a new one
    local_dict = locals()
    if 'prj' not in local_dict:
        print('creating BAG project')
        bprj = BPG.PhotonicBagProject()

    else:
        print('loading BAG project')
        bprj = local_dict['bprj']

    spec_file = 'BPG/examples/specs/WaveguideTB.yaml'
    PLM = BPG.PhotonicLayoutManager(bprj, spec_file)
    PLM.generate_flat_gds()
    # PLM.generate_gds()
    PLM.generate_tb()

