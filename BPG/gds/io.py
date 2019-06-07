import yaml
import gdspy
from BPG import PhotonicTemplateBase
from bag.layout.util import BBox
from typing import List, Tuple


class GDSImport(PhotonicTemplateBase):
    """
    This class takes a path to a GDS (relative to BAG_WORK_DIR) and imports it as a master to be
    used in BPG.

    Notes
    -----
    * We currently do not check for differences in unit size between the input GDS and the current
    templateDB unit size
    * This assumes that there is a single top cell for each GDS. If there are multiple top cells,
    this master will error out
    """
    def __init__(self, temp_db, lib_name, params, used_names, **kwargs):
        PhotonicTemplateBase.__init__(self, temp_db, lib_name, params, used_names, **kwargs)
        self.gds_layermap = self.template_db.photonic_tech_info.layermap_path

    @classmethod
    def get_params_info(cls):
        return dict(
            gds_path='Filepath to gds file to import',
        )

    def draw_layout(self):
        self.import_content_from_gds(self.params['gds_path'])

    def import_content_from_gds(self,
                                gds_filepath: str
                                ):
        """
        Read a GDS and copy all of the polygons into this master

        gdspy turns all input shapes into polygons, so we only need to care about importing into
        the polygon list. Currently we only import labels at the top level of the hierarchy

        Parameters
        ----------
        gds_filepath : str
            Path to the gds to be imported
        """
        # Import information from the layermap
        with open(self.gds_layermap, 'r') as f:
            lay_info = yaml.load(f)
            lay_map = lay_info['layer_map']

        # Import the GDS from the file
        gds_lib = gdspy.GdsLibrary()
        gds_lib.read_gds(infile=gds_filepath, units='convert')

        # Get the top cell in the GDS and flatten its contents
        top_cell = gds_lib.top_level()
        if len(top_cell) != 1:
            raise ValueError("Cannot import a GDS with multiple top level cells")
        top_cell = top_cell[0]  # top_cell returns a list, so just grab the only element
        top_cell.flatten()

        # TODO: This currently accesses an internal attr polygons, instead of the get_polygons() method, may be unstable
        for polyset in top_cell.polygons:
            for count in range(len(polyset.polygons)):
                points = polyset.polygons[count]
                layer = polyset.layers[count]
                datatype = polyset.datatypes[count]

                # Reverse lookup layername from gds LPP
                lpp = self.lpp_reverse_lookup(lay_map, gds_layerid=[layer, datatype])

                # Create the polygon from the provided data if the layer exists in the layermap
                if lpp:
                    self.add_polygon(layer=lpp,
                                     points=points,
                                     unit_mode=False)
        for label in top_cell.get_labels(depth=0):
            text = label.text
            layer = label.layer
            texttype = label.texttype
            position = label.position
            bbox = BBox(left=position[0] - self.grid.resolution,
                        bottom=position[1] - self.grid.resolution,
                        right=position[0] + self.grid.resolution,
                        top=position[1] + self.grid.resolution,
                        resolution=self.grid.resolution)

            # Reverse lookup layername from gds LPP
            lpp = self.lpp_reverse_lookup(lay_map, gds_layerid=[layer, texttype])

            # Create the label from the provided data if the layer exists in the layermap
            if lpp:
                self.add_label(label=text,
                               layer=lpp,
                               bbox=bbox)

    @staticmethod
    def lpp_reverse_lookup(layermap: dict, gds_layerid: List[int]):
        """
        Given a layermap dictionary, find the layername that matches the provided gds layer id

        Parameters
        ----------
        layermap : dict
            mapping from layer name to gds layer id
        gds_layerid : Tuple[int, int]
            gds layer id to find the layer name for

        Returns
        -------
        layername : str
            first layername that matches the provided gds layer id
        """
        for layer_name, layer_id in layermap.items():
            if layer_id == gds_layerid:
                return layer_name
        else:
            print(f"{gds_layerid} was not found in the layermap!")
