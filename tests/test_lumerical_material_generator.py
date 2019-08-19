import BPG
import yaml
from BPG.lumerical.code_generator import LumericalMaterialGenerator
from pathlib import Path


def test_example_lumerical_map():
    """
    Runs the provided example lumerical materials specification through the LumericalMaterialGenerator class and
    checks that they are properly created
    """

    # 1) load the lumerical map file from the examples dir into the
    filepath = 'BPG/examples/tech/BPG_tech_files/lumerical_map.yaml'
    # If the path where we place the output does not exist, create it
    outpath = Path('gen_libs/bpg_test_suite/lsf_writer_tests')
    outpath.mkdir(exist_ok=True, parents=True)
    outpath = str(outpath / 'materials.lsf')

    with open(filepath, 'r') as f:
        lumerical_map = yaml.load(f)

    # 2) Extract the custom materials under the materials key
    mat_map = lumerical_map['materials']

    # 3) Create the LumericalMaterialGenerator class and load the data in
    lmg = LumericalMaterialGenerator(outpath)
    lmg.import_material_file(mat_map)
    lmg.export_to_lsf()


if __name__ == '__main__':
    test_example_lumerical_map()
