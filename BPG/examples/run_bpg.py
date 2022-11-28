import os
import argparse
import BPG
import pya


if __name__ == '__main__':

    # Sample snippet of code using argparse
    parser = argparse.ArgumentParser(description='Run a BPG generator build with spec-file input')
    parser.add_argument('spec_file', type=str, nargs=1, default=None,
                        help='spec file to run')
    parser.add_argument('-d', default=False, const=True, action='store_const',
                        help='option to run dataprep')
    parser.add_argument('-f', default=False, const=True, action='store_const',
                        help='option to flatten dataprep output')
    parser.add_argument('-l', default=False, const=True, action='store_const',
                        help='option to generate lsf')

    args = parser.parse_args()

    spec_file = args.spec_file[0]
    do_dataprep = args.d
    do_lsf = args.l

    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content(save_content=False)

    plm.generate_gds()

    if do_dataprep:
        plm.dataprep()
        plm.generate_dataprep_gds()

        if args.f:
            file_out = plm.gds_path
            file_flat = file_out + '_flattened.gds'
            flatten_layout = pya.Layout()
            flatten_layout.read(file_out)
            flatten_layout.top_cell().flatten(True)
            flatten_layout.write(file_flat)

    if do_lsf:
        plm.generate_lsf()
