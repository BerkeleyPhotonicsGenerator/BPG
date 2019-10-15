import emopt



class EmoptGeometryExporter_2D:
    """Provides systems for BPG testbenches utilizing emopt to move content lists """

    def __init__(self, domain, sim):
        self.domain = domain
        self.sim = sim

        self.exported_content = []

    def add_rect