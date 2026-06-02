import pandapower as pp
import pandas as pd
import network_plotter as plot

def find_mistake(network_data):
    # Combined diagnostic script for identifying convergence issues due to disconnected buses

    # Load key components
    bus_df = network_data.get("bus", pd.DataFrame())
    line_df = network_data.get("line", pd.DataFrame())
    switch_df = network_data.get("switch", pd.DataFrame())

    # Step 1: Extract connected buses from lines
    from_buses = line_df["from_bus"].dropna().astype(int)
    to_buses = line_df["to_bus"].dropna().astype(int)
    line_connected_buses = set(from_buses).union(set(to_buses))

    # Step 2: Extract buses referenced in switches (both `bus` and the line’s `from_bus`/`to_bus`)
    switch_buses = switch_df["bus"].dropna().astype(int)

    # Identify valid lines referenced by switches
    valid_line_indices = set(line_df.index)
    active_line_indices = set(line_df[line_df.get("in_service", True)].index)

    # Filter switches that reference valid and active lines
    switch_lines = switch_df[
        (switch_df["et"] == "l") &
        (switch_df["element"].isin(active_line_indices))
    ]

    # Now extract the buses these lines connect to
    switched_line_buses = set()
    for _, row in switch_lines.iterrows():
        line_idx = row["element"]
        if line_idx in line_df.index:
            line = line_df.loc[line_idx]
            if line.get("from_bus") is not None:
                switched_line_buses.add(int(line["from_bus"]))
            if line.get("to_bus") is not None:
                switched_line_buses.add(int(line["to_bus"]))

    # Step 3: Combine all connected buses
    electrically_connected_buses = line_connected_buses.union(switch_buses).union(switched_line_buses)

    # Step 4: Identify unconnected buses
    all_buses = set(bus_df.index)
    unconnected_buses_final = all_buses - electrically_connected_buses

    # Extract info on unconnected buses
    final_unconnected_buses_df = bus_df.loc[bus_df.index.isin(unconnected_buses_final)]

pass


net = pp.from_excel("extended_network.xlsx")




pp.runpp(net)


pp.plotting.plotly.pf_res_plotly(net)
