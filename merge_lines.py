import pandapower as pp
import numpy as np
from pandapower.topology import create_nxgraph
from shapely.geometry import LineString, Point, shape
import json

def merge_line_at_bus(net, bus_idx, allow_type_mismatch=False):
    """
    Collapse the two lines meeting at `bus_idx` into a single line.
    - net: a pandapower network with `geo` field on lines and buses
    - bus_idx: index of the intermediate bus (must have exactly 2 incident lines)
    - allow_type_mismatch: if False, errors on differing std_types
    """
    # find the two incident lines
    lines = net.line[(net.line.from_bus == bus_idx) | (net.line.to_bus == bus_idx)]
    if len(lines) != 2:
        raise ValueError(f"Bus {bus_idx} has {len(lines)} lines, expected 2.")
    l1_idx, l2_idx = lines.index
    l1, l2 = net.line.loc[l1_idx], net.line.loc[l2_idx]

    # check std_type consistency
    if not allow_type_mismatch and l1.std_type != l2.std_type:
        raise ValueError(f"Std_types differ: {l1.std_type} vs {l2.std_type}")
    # check parallel and dfem consistency
    if l1.parallel != l2.parallel:
        raise ValueError(f"Parallel count mismatch: {l1.parallel} vs {l2.parallel}")
    if l1.dfem != l2.dfem:
        raise ValueError(f"DFEM mismatch: {l1.dfem} vs {l2.dfem}")

    # identify end buses
    end1 = l1.from_bus if l1.to_bus == bus_idx else l1.to_bus
    end2 = l2.from_bus if l2.to_bus == bus_idx else l2.to_bus
    if end1 is None or end2 is None:
        raise ValueError(f"Cannot determine end buses for lines {l1_idx}, {l2_idx} at bus {bus_idx}")
    # ensure end buses still exist in net
    if end1 not in net.bus.index or end2 not in net.bus.index:
        raise ValueError(f"End bus index missing: {end1} or {end2} not in net.bus.index")

    # sum lengths
    new_length = float(l1.length_km) + float(l2.length_km)

    # pick parameters (safe now that parallel and dfem match)
    std_type = l1.std_type
    parallel = int(l1.parallel)
    dfem     = float(l1.dfem)

    # --- merge geodata using new 'geo' field ---
    raw_geo1 = l1['geo']; raw_geo2 = l2['geo']
    # parse JSON if stored as string
    if isinstance(raw_geo1, str): raw_geo1 = json.loads(raw_geo1)
    if isinstance(raw_geo2, str): raw_geo2 = json.loads(raw_geo2)
    geo1 = shape(raw_geo1) if isinstance(raw_geo1, (dict, list)) else raw_geo1
    geo2 = shape(raw_geo2) if isinstance(raw_geo2, (dict, list)) else raw_geo2

    # get the bus geometry, parse if needed
    raw_bus_geo = net.bus.at[bus_idx, 'geo']
    if isinstance(raw_bus_geo, str): raw_bus_geo = json.loads(raw_bus_geo)
    bus_point = shape(raw_bus_geo) if isinstance(raw_bus_geo, (dict, list)) else (
        raw_bus_geo if isinstance(raw_bus_geo, Point) else Point(raw_bus_geo)
    )
    bus_coord = tuple(bus_point.coords)[0]

    # orient segments so they meet at the bus
    if tuple(geo1.coords[0]) == bus_coord:
        geo1 = LineString(list(geo1.coords)[::-1])
    if tuple(geo2.coords[-1]) == bus_coord:
        geo2 = LineString(list(geo2.coords)[::-1])
    merged_coords = list(geo1.coords) + list(geo2.coords)[1:]

    # drop old lines and bus without reindexing to preserve indices
    net.line.drop([l1_idx, l2_idx], inplace=True)
    net.bus.drop(bus_idx, inplace=True)

    # create the merged line
    pp.create_line(
        net,
        from_bus    = end1,
        to_bus      = end2,
        length_km   = new_length,
        std_type    = std_type,
        name        = f"merged_{std_type}_{l1_idx}_{l2_idx}",
        parallel    = parallel,
        dfem        = dfem,
        geodata     = merged_coords
    )


def collapse_all_degree2_buses(net, voltage=None, allow_type_mismatch=False):
    """
    Find all buses of degree 2 (optionally filtering vn_kv) and merge their lines.
    """
    G = create_nxgraph(net)
    for b, deg in G.degree():
        if deg != 2: continue
        if voltage is not None and not np.isclose(net.bus.at[b, 'vn_kv'], voltage):
            continue
        try:
            merge_line_at_bus(net, b, allow_type_mismatch=allow_type_mismatch)
        except ValueError as e:
            print(f"Skipped bus {b}: {e}")
