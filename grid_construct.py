import numpy as np
import pandapower as pp
from pandapower.topology import create_nxgraph
import pandas as pd
import geopandas as gpd
import json
from shapely.geometry import shape, Point, Polygon
from shapely.geometry.base import BaseGeometry
from gridIO import load_gpkg
from assets import define_cables, define_transformers, get_bus_params
import network_plotter as plot
from cluster import cluster_buses, get_centroid
from merge_lines import collapse_all_degree2_buses
import matplotlib.colors as mcolors
all_colors = [color for color in mcolors.CSS4_COLORS if 'blue' not in color.lower() and 'orange' not in color.lower()]

# polygon = Polygon([(108707, 511633), (108760, 511800), (108991, 511846), (108960, 511541)])  # tiny area
# polygon = Polygon([(108426, 511361), (108667, 512163), (109206, 511976), (108971, 511173)])  # small area
polygon = Polygon([(115396.47, 508717.54), (118588.55, 516876.17), (110697, 517792.25), (108290.91, 514944.67), (106734.67,512273.68)])  # extended area

def get_geometry(df):
    geo = df['geo'].map(json.loads).map(shape)
    gdf = gpd.GeoDataFrame(geo, geometry='geo')
    return gdf

def get_or_create_bus(net, voltage_level, coords):
    """
    Get or create a bus in the pandapower network based on the voltage level and coordinates.
    """

    #any(shape(json.loads(geojson)).contains(pt) for geojson in net.bus['geo'])

    #geodict = net.bus['geo'].apply(json.loads)
    #geom = geodict.apply(shape)
    point = Point(coords)
    #assert point not in net.bus['geo'].values, 'it exists!'

    # Check if a bus with the same voltage level and coordinates already exists
    busses_voltage = net.bus[net.bus['vn_kv'] == voltage_level]
    mask = busses_voltage['pos'] == point

    if mask.any():
        return busses_voltage[mask].index[0]

    idx = pp.create_bus(net, name=f"linebus_{voltage_level}", vn_kv=voltage_level, geodata=coords, pos=Point(coords))
    return idx


def place_lines(gdf, net, std_type='AL_3x150_10kV'):
    std = net.std_types['line'][std_type]
    voltage_level = std['vn_kv_line']

    for index, row in gdf.iterrows():
        geometry = row.geometry
        # Extract coordinates from the geometry
        coords = geometry.coords        
        coords_a, coords_b = coords[0], coords[-1]

        # Get or create buses for the line endpoints
        bus_a = get_or_create_bus(net, voltage_level=voltage_level, coords=coords_a)
        bus_b = get_or_create_bus(net, voltage_level=voltage_level, coords=coords_b)
        
        length = row.geometry.length/1000  # RD is in meters, convert to kilometers
        
        # Create a line in the pandapower network
        # pp.create_line(net,from_bus=bus_a, to_bus=bus_b, length_km=length, std_type='AL_3x150_10kV', name=f"test", parallel= 1, dfem= 1.0)
        line_idx = pp.create_line(
                net,
                from_bus     = bus_a,
                to_bus       = bus_b,
                length_km    = length,
                std_type     = std_type,
                name         = f"line_{voltage_level}_{index}",
                parallel     = 1,             # >1 if you have multiple cables in parallel
                dfem         = 1.0,            # derating factor (≤1.0) if needed
                geodata      = list(geometry.coords)
        )
    
    return

def place_buses(gdf, net, bus_params):
    """
    Place buses on the grid based on the geometry of the GeoDataFrame.
    """
    for index, row in gdf.iterrows():
        # Extract coordinates from the geometry
        coords = row.geometry.coords[0]

        # Create a bus in the pandapower network
        name = f"bus_connection_{bus_params['vn_kv']}kv_{index}"
        bus_idx = pp.create_bus(net, vn_kv=bus_params['vn_kv'], name=name, geodata=(coords[0], coords[1]))

    return net

def get_terminal_buses(net, voltage=None):
    G = create_nxgraph(net)
    terminal_bus_indices = np.array([node for node, degree in G.degree() if degree == 1])
    terminal_buses = net.bus.loc[terminal_bus_indices]  # the indices are linked to the bus indices from net!

    if voltage is not None:
        terminal_buses = terminal_buses[terminal_buses['vn_kv'] == voltage]

    return terminal_buses


def get_buses_within_range(buses, target: BaseGeometry, range: float=30):
    gdf = gpd.GeoDataFrame(buses, geometry="pos")
    search_area = target.buffer(range)

    within_mask = gdf.geometry.within(search_area)

    return buses[within_mask]

def get_buses_outside_polygon(buses, polygon: BaseGeometry):
    gdf = gpd.GeoDataFrame(buses, geometry="pos")
    outside_mask = ~gdf.geometry.within(polygon)
    return buses[outside_mask]

def get_buses_inside_polygon(buses, polygon: BaseGeometry):
    gdf = gpd.GeoDataFrame(buses, geometry="pos")
    outside_mask = gdf.geometry.within(polygon)
    return buses[outside_mask]

def place_and_connect_buses(gdf, net, bus_params, range=30, line_std='CABLE_3x150_10kV'):
    """
    Place buses on the grid based on the geometry of the GeoDataFrame.
    """
    for index, row in gdf.iterrows():
        # Extract coordinates from the geometry
        coords = row.geometry.coords[0]
      
        name = f"bus_load_{bus_params['vn_kv']}kv_{index}"
        bus1_idx = pp.create_bus(net, vn_kv=bus_params['vn_kv'], name=name, geodata=(coords[0], coords[1]), pos=Point(coords))

        # the bus is potentially at a transformer site
        trafos_bus_idxs = net.trafo['lv_bus'][net.trafo['vn_lv_kv'] == 10]  # get the lv side of trafos that have 10kv as their lv side (HV-LV transformer)
        distances = Point(coords).distance(net.bus.loc[trafos_bus_idxs]['pos'])  # get the distance of our bus compared to the lv sides of the transformers
        if np.sum(distances < 50) == 1:  #  it's within the transformer, connect to LV side
            bus2_idx = distances[distances < 500].index[0]
            pp.create_switch(net, bus=bus1_idx, element=bus2_idx, et='b', closed=True, type="CB", name=name)
            continue
        elif np.sum(distances < 50) > 1:
            raise ValueError(f"Multiple buses found within 50 units: {np.sum(distances < 50)}. Expected only one.")

        ## if the bus is not at a transformer site, connect to the closest terminal mv lines
        # find terminal buses that are within the range of our bus
        terminal_buses = get_terminal_buses(net, voltage=bus_params['vn_kv'])
        terminal_buses_within_range = get_buses_within_range(terminal_buses, Point(coords), range=5) # find the ones that is within 5m

        # connect to the closest terminal mv lines
        for bus2_idx in terminal_buses_within_range.index:
            name = f"switch_connection_bus{bus1_idx}_bus{bus2_idx}_{bus_params['vn_kv']}kV"
            pp.create_switch(net, bus=bus1_idx, element=bus2_idx, et='b', closed=True, type="CB", name=name)
            # pp.create_transformer(net, bus1_idx, bus2_idx, std_type="Trafo_40MVA_50_10", name="trafo_test")


    return net

def place_external_grid_connections(net, polygon):
    external_buses = get_buses_outside_polygon(net.bus, polygon)
    for index, bus in external_buses.iterrows():
        pp.create_ext_grid(net, index)


def place_hv_transformer(net):

    # get HV terminal buses in the area
    terminal_50kv = get_terminal_buses(net, voltage=50)
    terminal_50kv = get_buses_inside_polygon(terminal_50kv, polygon)

    # get unlinked MV terminal buses in the area
    terminal_10kv = get_terminal_buses(net, voltage=10)
    terminal_10kv = get_buses_inside_polygon(terminal_10kv, polygon)

    # they often come in clusters at HV-MV transformers, e.g., 2 HV lines go to 10 MV lines
    terminal_10kv_clusters = cluster_buses(terminal_10kv, r=50)  # find MV clusters
    terminal_50kv_clusters = cluster_buses(terminal_50kv, r=50)  # find HV clusters

    fig = plot.plot_network(net)
   
    # we will add a aggregation bus that represents the transformer. Get the parameters of those buses
    bus_params_MV=get_bus_params(10)
    bus_params_HV=get_bus_params(50)

    # determine MV cluster centroids (position for the aggregation MV bus)
    centroidsMV = []
    for cluster, color in zip(terminal_10kv_clusters, all_colors):
        buses = net.bus.loc[cluster]
        centroid = get_centroid(buses)
        centroidsMV.append(centroid)
        # plot.add_markers(fig, buses['pos'], color='orange')
        # plot.add_markers(fig, [centroid], color='orange')
    
    # create transformer from HV cluster centroids to MV cluster centroids and connect cluster buses to them
    centroidsHV = []
    for HV_idx, (cluster, color) in enumerate(zip(terminal_50kv_clusters, all_colors)):
        buses = net.bus.loc[cluster]
        centroidHV = get_centroid(buses)

        distances = centroidHV.distance(centroidsMV)
        if np.all(distances > 100):  # this is not a transformer, continue
            continue

        centroidsHV.append(centroidHV)
        plot.add_markers(fig, buses['pos'], color=color)
        plot.add_markers(fig, [centroidHV], color='gray')

        MV_idx = np.argmin(distances)  # find the closest centroid
        MV_loc = centroidsMV[MV_idx]  # get the coordinates of the closest centroid
        # plot.add_markers(fig, [MV_loc], color='green')
        busMV_idx = pp.create_bus(net, vn_kv=bus_params_MV['vn_kv'], name='HV_MV_transformer_MV_bus', geodata=MV_loc.coords[0], pos=MV_loc)  # create MV side bus
        busHV_idx = pp.create_bus(net, vn_kv=bus_params_HV['vn_kv'], name='HV_MV_transformer_HV_bus', geodata=centroidHV.coords[0], pos=centroidHV)  # create HV side bus
        pp.create_transformer(net, busHV_idx, busMV_idx, std_type="Trafo_40MVA_50_10", name="trafo_HV_MV")

        # connect HV cluster buses to the HV centroid bus
        for bus_idx, bus in net.bus.loc[cluster].iterrows():
            pp.create_switch(net, bus=bus_idx, element=busHV_idx, et='b', closed=True, type="CB", name='HV_MV_transformer_HV_cluster_switch')

        # connect MV cluster buses to the MV centroid bus
        if len(cluster) > 10:  # if it is a substation (larger area)
            MV_cluster = get_buses_within_range(terminal_10kv, target=MV_loc, range=150)  # expand the cluster from the centroid
        else:
            MV_cluster = net.bus.loc[terminal_10kv_clusters[MV_idx]]
        for bus_idx, bus in MV_cluster.iterrows():
            pp.create_switch(net, bus=bus_idx, element=busMV_idx, et='b', closed=True, type="CB", name='HV_MV_transformer_MV_cluster_switch')

    return


def add_load(net):
    from math import tan, acos
    load_bus_idxs = net.bus[net.bus['name'].str.startswith('bus_load')].index  # get all load buses

    # for all MV-LV transformers
    for idx in load_bus_idxs:
        name = net.bus.loc[idx]['name']
        pp.create_load(net,
            bus=idx,
            p_mw=0.00018,             # 180 kW
            q_mvar=0.00006,           #  60 kVAr
            name=name + "_load"
            )
    
    # direct MV loads
    terminal_buses_10kV = get_terminal_buses(net, voltage=10)
    #terminal_buses_10kV = get_buses_inside_polygon(terminal_buses_10kV, polygon)
    for idx, bus in terminal_buses_10kV.iterrows():
        pp.create_load(net,
            bus=idx,
            p_mw=0.00045,          # 450 kW
            q_mvar=0.00045 * tan(acos(0.95)),  # ≈0.15 MVAr
            name=name + "_direct_MV_load"
            )
    
    return

def construct_grid():
    # TODO, THERE ARE SOME LINES THAT ARE INCOMPLETE BECAUSE THEY ARE IN THE EXTERNAL AREA
    # extend right top coordinate a bit more north

    # gdf = load_gpkg(file_path="filtered_power_grid.gpkg")
    gdf = load_gpkg(file_path="filtered_power_grid_big.gpkg")

    # Initialize an empty pandapower network
    net = pp.create_empty_network()
    net.bus['pos'] = pd.Series(dtype="object")  # initialize position row for the busses

    # Define cables
    define_cables(net)
    define_transformers(net)

    # add middle voltage lines
    place_lines(gdf['hoogspanningskabels'], net, std_type='CABLE_1x400_50kV')
    place_lines(gdf['middenspanningskabels'], net, std_type='CABLE_3x150_10kV')
    collapse_all_degree2_buses(net)  # remove all connection buses

    # fig = plot.plot_network(net)
    # plot.show(fig)
    # return

    external_bus_check(net, polygon)
    # place_external_grid_connections(net, polygon)


    place_hv_transformer(net)

    #place_lines(gdf['laagspanningskabels'], net, std_type='CABLE_3x50_Cu_0.4kV')

    place_and_connect_buses(gdf['middenspanningsinstallaties'], net, bus_params=get_bus_params(10), range=30, line_std='CABLE_3x150_10kV')  # place busses, connect to lines within a range (if low voltage lines are placed, these are transformers)

    slack_bus_mask = net.bus['name'] == 'HV_MV_transformer_MV_bus'
    for idx in net.bus[slack_bus_mask].index:
        pp.create_ext_grid(net, idx)
    
    net.trafo.drop(net.trafo.loc[net.trafo['name'] == 'trafo_HV_MV'].index, inplace=True)  # remove the HV-MV transformer, we will not use it
    net.switch.drop(net.switch[net.switch['name'] == 'HV_MV_transformer_HV_cluster_switch'].index, inplace=True)  # remove the HV-MV transformer switches, we will not use them
    net.line.drop(net.line[net.line['std_type'] == 'CABLE_1x400_50kV'].index, inplace=True)  # remove the HV lines, we will not use them
    net.bus.drop(net.bus[net.bus['vn_kv'] == 50].index, inplace=True)  # remove the HV buses, we will not use them

    add_load(net)  # add loads to the network (MV-LV transformers and direct MV loads)

    # # Remove the HV-MV transformer islend line
    # net.bus.drop(19, inplace=True)  # remove the bus that is not connected to anything, it is a remnant of the HV-MV transformer
    # net.bus.drop(20, inplace=True)  # remove the bus that is not connected to anything, it is a remnant of the HV-MV transformer
    # net.switch.drop(net.switch[net.switch['bus'] == 19].index, inplace=True)  # remove the switch that is not connected to anything, it is a remnant of the HV-MV transformer
    # net.switch.drop(net.switch[net.switch['bus'] == 20].index, inplace=True)  # remove the switch that is not connected to anything, it is a remnant of the HV-MV transformer
    # net.line.drop(10, inplace=True)  # remove the line that is not connected to anything, it is a remnant of the HV-MV transformer

    # # remove the HV-MV transformer sole bus
    # net.bus.drop(59, inplace=True)  # remove the bus that is not connected to anything, it is a remnant of the HV-MV transformer
    # net.switch.drop(net.switch[net.switch['bus'] == 59].index, inplace=True)  # remove the switch that is not connected to anything, it is a remnant of the HV-MV transformer
    # net.load.drop(net.load[net.load['bus'] == 59].index, inplace=True)  # remove the load that is not connected to anything, it is a remnant of the HV-MV transformer

    # bus_switches_to_delete = [40, 6, 37, 43, 56, 35, 8, 32, 30, 10, 12, 14, 16, 18]
    # for idx in bus_switches_to_delete:
    #     net.switch.drop(net.switch[net.switch['bus'] == idx].index, inplace=True)
    #     pp.create_ext_grid(net, idx)
    
    # net.ext_grid.drop(net.ext_grid[net.ext_grid['bus'] == 57].index, inplace=True)  # remove the ext grid that is not connected to anything, it is a remnant of the HV-MV transformer
    # net.bus.drop(57, inplace=True)  # remove the bus that is not connected to anything, it is a remnant of the HV-MV transformer

    # bus_lines_to_delete = [6, 37, 43, 56, 35, 8, 32, 30, 10, 12, 14, 16, 18]
    # for idx in bus_lines_to_delete:
    #     line = net.line[net.line['from_bus'] == idx]
    #     net.line.drop(line.index, inplace=True)  # remove the line that is not connected to anything, it is a remnant of the HV-MV transformer
    #     line = net.line[net.line['to_bus'] == idx]
    #     net.line.drop(line.index, inplace=True)  # remove the line that is not connected to anything, it is a remnant of the HV-MV transformer

    #     net.ext_grid.drop(net.ext_grid[net.ext_grid['bus'] == idx].index, inplace=True)  # remove the ext grid that is not connected to anything, it is a remnant of the HV-MV transformer
    #     net.bus.drop(idx, inplace=True)  # remove the bus that is not connected to anything, it is a remnant of the HV-MV transformer


    # lines_to_delete = [55]
    # for idx in lines_to_delete:
    #     net.line.drop(idx, inplace=True)

    # connected_buses = pd.concat([net.line['from_bus'], net.line['to_bus']]).unique()  # get all buses that are connected to a line
    # unconnected_buses = net.bus.index.difference(connected_buses)  # get all buses that are not connected to a line
    # for idx in unconnected_buses:
    #     net.bus.drop(idx, inplace=True)
    #     net.load.drop(net.load[net.load['bus'] == idx].index, inplace=True)  # remove the load that is not connected to anything
    


    net.bus.to_csv('buses.csv', index=True)
    net.line.to_csv('lines.csv', index=True)
    net.trafo.to_csv('trafos.csv', index=True)
    net.switch.to_csv('switches.csv', index=True)
    net.ext_grid.to_csv('ext_grid.csv', index=True)
    net.load.to_csv('loads.csv', index=True)
    pp.to_excel(net, 'extended_network.xlsx', include_empty_tables=False, include_results=True)

    del gdf  # release GDAL/fiona resources before plotting

    fig = plot.plot_network(net)
    plot.draw_switches(fig, net)
    # plot.add_markers(fig, buses['pos'], color='orange')
    plot.show(fig)

    import os; os._exit(0)  # skip GDAL/fiona destructor crash on Windows


def external_bus_check(net, polygon):
    external_buses = get_buses_outside_polygon(net.bus, polygon)
    terminal_buses = get_terminal_buses(net)
    for index, bus in external_buses.iterrows():
        if index not in terminal_buses.index: # if there is a bus in the external network that is not a terminal bus
            raise ValueError(f"Bus {index} is outside the polygon but not a terminal bus.")
    return


def __main__():

    construct_grid()

if __name__ == "__main__":
    __main__()