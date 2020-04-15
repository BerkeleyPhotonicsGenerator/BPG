import BPG
from BPG.gds.io import GDSImport


class TestGDSImport(BPG.PhotonicTemplateBase):
    @classmethod
    def get_params_info(cls):
        return dict(
            gds_path='Path to gds to import'
        )

    def draw_layout(self):
        master = self.new_template(params=self.params, temp_cls=GDSImport)
        self.add_instance(master)


def test_gds_import():
    spec_file = 'bpg_test_suite/specs/gds_import.yaml'
    plm = BPG.PhotonicLayoutManager(spec_file)
    plm.generate_content()
    plm.generate_gds()


if __name__ == '__main__':
    test_gds_import()
