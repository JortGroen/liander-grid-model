import geopandas as gpd
import fiona
from shapely.geometry import Polygon
import os

def get_layer_names(gpkg_path: str) -> list:
    """
    Return a list of layer names in the given GeoPackage.
    """
    return fiona.listlayers(gpkg_path)

def load_gpkg(file_path: str) -> gpd.GeoDataFrame:
    layers = get_layer_names(file_path)
    print(f"Layers found in {file_path}: {layers}")
    data = {}
    for layer in layers:
        data[layer] = gpd.read_file(file_path, layer=layer)
        print(f"Loaded layer: {layer}, Number of features: {len(data[layer])}")
    return data

def load_and_filter(file_in: str, file_out: str, polygon: Polygon):
    """
    Load a GeoPackage file and return a dictionary of GeoDataFrames for each layer.
    """

    # List all layers in the GeoPackage
    layers = get_layer_names(file_in)
    print(f"Layers found in {file_in}: {layers}")

    # Initialize an empty dictionary to store filtered data from each layer
    filtered_layers = {}

    # Filter each layer
    for layer in layers:
        gpkg_data = gpd.read_file(file_in, layer=layer)
        filtered_data = gpkg_data[gpkg_data.geometry.apply(lambda x: x.within(polygon) or x.intersects(polygon))]
        filtered_layers[layer] = filtered_data

    # Save filtered layers to a new GeoPackage file
    for i, (layer, data) in enumerate(filtered_layers.items()):
        print(f"{i}, Layer: {layer}, Number of features: {len(data)}")
        data.to_file(file_out, layer=layer, driver="GPKG")

    print(f"Filtered data from all layers saved successfully to {file_out}")

def __main__():
    # Define your polygon (replace with your actual coordinates) crs="EPSG:28992"
    #polygon_coords = [(109196, 512914), (109555, 513688), (110335, 513353), (110374, 513050), (110101,512500)]
    # polygon_coords = [(108707, 511633), (108760, 511800), (108991, 511846), (108960, 511541)]  # tiny area
    # polygon_coords = [(108426, 511361), (108667, 512163), (109206, 511976), (108971, 511173)]  # small
    polygon_coords = [(115396.47, 508717.54), (118588.55, 516876.17), (110697, 517792.25), (108290.91, 514944.67), (106734.67,512273.68)]  # extended area
    polygon = Polygon(polygon_coords)
    
    load_and_filter(file_in="liander_elektriciteitsnetten.gpkg" , file_out="filtered_power_grid_big.gpkg", polygon=polygon)

    data = load_gpkg(file_path="filtered_power_grid.gpkg")
    pass


if __name__ == "__main__":
    __main__()