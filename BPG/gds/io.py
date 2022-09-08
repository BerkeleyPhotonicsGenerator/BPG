import warnings


from BPG import PhotonicTemplateBase
from bag.layout.util import BBox
from BPG.content_list import ContentList

from BPG import run_settings as bpg_run_settings
if bpg_run_settings['bpg_config']['bpg_gds_backend'] == 'gdspy':
    import gdspy
if bpg_run_settings['bpg_config']['bpg_gds_backend'] == 'klayout':
    import pya


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
        self.lay_map = self.template_db.photonic_tech_info.layer_map

        self.reverse_lookup = self.create_reverse_lookup(self.lay_map)

    @classmethod
    def get_params_info(cls):
        return dict(
            gds_path='Filepath to gds file to import',
        )

    @staticmethod
    def create_reverse_lookup(lay_map):
        reverse_lookup = {}
        for layer_name, layer_id in lay_map.items():
            if tuple(layer_id) not in reverse_lookup:
                reverse_lookup[tuple(layer_id)] = layer_name
            else:
                warnings.warn(f'GDS layer {tuple(layer_id)} has multiple LPPs mapped to it. ')
        return reverse_lookup

    def draw_layout(self):
        if bpg_run_settings['bpg_config']['bpg_gds_backend'] == 'gdspy':
            self.import_content_from_gds_gdspy(self.params['gds_path'],
                                               reverse_lookup=self.reverse_lookup,
                                               lay_map=self.lay_map,
                                               layout_cls=self,
                                               res=self.grid.resolution)
        elif bpg_run_settings['bpg_config']['bpg_gds_backend'] == 'klayout':
            self.import_content_from_gds_klayout(self.params['gds_path'],
                                                 reverse_lookup=self.reverse_lookup,
                                                 lay_map=self.lay_map,
                                                 layout_cls=self,
                                                 res=self.grid.resolution)
        else:
            raise ValueError(f'Invalid bpg_gds_backend setting: {bpg_run_settings["bpg_config"]["bpg_gds_backend"]}')

    @staticmethod
    def import_content_from_gds_klayout(gds_filepath: str,
                                        reverse_lookup,
                                        lay_map=None,
                                        layout_cls=None,
                                        res=0.001,
                                        ):
        """
        Read a GDS and copy all of the polygons and labels into this master

        Parameters
        ----------
        gds_filepath : str
            Path to the gds to be imported
        reverse_lookup : dict
            Dictionary mapping LPP GDS numbers to layer/purpose name
        lay_map : dict
            Dictionary mapping LPP layer/purpose name to GDS numbers
        layout_cls : PhotonicTemplateBase or None
            Layout class into which gds should be imported
        res : float
            Layout resolution
        """

        create_layout = layout_cls is not None
        polygon_list = []
        pin_list = []

        # Prepare KLayout layermap
        pya_layermap = pya.LayerMap()
        for ind, (lay_key_tuple, gds_lpp) in enumerate(lay_map.items()):
            pya_layermap.map(pya.LayerInfo(int(gds_lpp[0]), int(gds_lpp[1])), ind)

        # Import the GDS from the file
        layout = pya.Layout()
        options = pya.LoadLayoutOptions()
        options.layer_map = pya_layermap
        options.create_other_layers = False

        layout.read(gds_filepath, options)
        top_cell: "pya.Cell" = layout.top_cell()
        top_cell.flatten(True)

        layer_infos = layout.layer_infos()

        shape_iter = pya.RecursiveShapeIterator(layout,
                                                top_cell,
                                                layout.layer_indexes())
        shape_iter.shape_flags = pya.Shapes.SPolygons + pya.Shapes.SBoxes + pya.Shapes.SPaths
        shape_iter.max_depth = 1
        while not shape_iter.at_end():
            shape: "pya.Shape" = shape_iter.shape()
            # polygon: "pya.Polygon" = shape.polygon
            polygon: "pya.DSimplePolygon" = shape.dsimple_polygon
            if polygon:
                polygon_points = [(point.x, point.y) for point in polygon.each_point()]

                # Reverse lookup layername from gds LPP
                pya_layerinfo: "pya.LayerInfo" = layer_infos[shape.layer]
                lpp = reverse_lookup[(pya_layerinfo.layer, pya_layerinfo.datatype)]

                # Create the polygon from the provided data if the layer exists in the layermap
                if lpp:
                    if create_layout:
                        layout_cls.add_polygon(layer=lpp,
                                               points=polygon_points,
                                               unit_mode=False)
                    else:
                        polygon_list.append({
                            'layer': lpp,
                            'points': polygon_points
                        })
            shape_iter.next()

        shape_iter.shape_flags = pya.Shapes.STexts
        shape_iter.max_depth = 1
        while not shape_iter.at_end():
            shape: "pya.Shape" = shape_iter.shape()

            # Reverse lookup layername from gds LPP
            pya_layerinfo: "pya.LayerInfo" = layer_infos[shape.layer]
            lpp = reverse_lookup[(pya_layerinfo.layer, pya_layerinfo.datatype)]

            # Create the polygon from the provided data if the layer exists in the layermap
            if lpp:
                if create_layout:
                    layout_cls.add_label(shape.text_string,
                                         layer=lpp,
                                         bbox=BBox(shape.dtext.x - layout_cls.grid.resolution,
                                                   shape.dtext.y - layout_cls.grid.resolution,
                                                   shape.dtext.x + layout_cls.grid.resolution,
                                                   shape.dtext.y + layout_cls.grid.resolution,
                                                   layout_cls.grid.resolution))
                else:
                    pin_list.append({
                        'net_name': shape.text_string,
                        'pin_name': shape.text_string,
                        'label': shape.text_string,
                        'layer': lpp,
                        'bbox': BBox(shape.dtext.x - res,
                                     shape.dtext.y - res,
                                     shape.dtext.x + res,
                                     shape.dtext.y + res,
                                     res),
                        'make_rect': False
                    })
            shape_iter.next()

        if not create_layout:
            return ContentList(cell_name=top_cell.name,
                               polygon_list=polygon_list,
                               pin_list=pin_list)

    @staticmethod
    def import_content_from_gds_gdspy(gds_filepath: str,
                                      reverse_lookup,
                                      lay_map=None,
                                      layout_cls=None,
                                      res=0.001,
                                      ):
        """
        Read a GDS and copy all of the polygons and labels into this master

        gdspy turns all input shapes into polygons, so we only need to care about importing into
        the polygon list. Currently we only import labels at the top level of the hierarchy

        Parameters
        ----------
        gds_filepath : str
            Path to the gds to be imported
        reverse_lookup : dict
            Dictionary mapping LPP GDS numbers to layer/purpose name
        lay_map : dict
            Dictionary mapping LPP layer/purpose name to GDS numbers
        layout_cls : PhotonicTemplateBase or None
            Layout class into which gds should be imported
        res : float
            Layout resolution
        """

        create_layout = layout_cls is not None
        polygon_list = []
        pin_list = []

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
                lpp = reverse_lookup[(layer, datatype)]

                # Create the polygon from the provided data if the layer exists in the layermap
                if lpp:
                    if create_layout:
                        layout_cls.add_polygon(layer=lpp,
                                               points=points,
                                               unit_mode=False)
                    else:
                        polygon_list.append({
                            'layer': lpp,
                            'points': points
                        })
                    
        for path in top_cell.paths:
            polyset = path.to_polygonset()
            for count in range(len(polyset.polygons)):
                points = polyset.polygons[count]
                layer = polyset.layers[count]
                datatype = polyset.datatypes[count]

                # Reverse lookup layername from gds LPP
                lpp = reverse_lookup[(layer, datatype)]

                # Create the polygon from the provided data if the layer exists in the layermap
                if lpp:
                    if create_layout:
                        layout_cls.add_polygon(layer=lpp,
                                               points=points,
                                               unit_mode=False)
                    else:
                        polygon_list.append({
                            'layer': lpp,
                            'points': points
                        })

        for label in top_cell.get_labels(depth=0):
            text = label.text
            layer = label.layer
            texttype = label.texttype
            position = label.position

            # Reverse lookup layername from gds LPP
            lpp = reverse_lookup[(layer, texttype)]

            # Create the label from the provided data if the layer exists in the layermap
            if lpp:
                if create_layout:
                    bbox = BBox(left=position[0] - layout_cls.grid.resolution,
                                bottom=position[1] - layout_cls.grid.resolution,
                                right=position[0] + layout_cls.grid.resolution,
                                top=position[1] + layout_cls.grid.resolution,
                                resolution=layout_cls.grid.resolution)
                    layout_cls.add_label(label=text,
                                         layer=lpp,
                                         bbox=bbox)
                else:
                    pin_list.append({
                        'net_name': text,
                        'pin_name': text,
                        'label': text,
                        'layer': lpp,
                        'bbox': BBox(position[0] - res,
                                     position[1] - res,
                                     position[0] + res,
                                     position[1] + res,
                                     res),
                        'make_rect': False
                    })

        if not create_layout:
            return ContentList(cell_name=top_cell.name,
                               polygon_list=polygon_list,
                               pin_list=pin_list)
