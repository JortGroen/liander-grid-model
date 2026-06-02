# interactive_grid.py

import os
import json
import pandas as pd
import webbrowser

from bokeh.plotting import figure, output_file, save
from bokeh.models import (
    ColumnDataSource,
    HoverTool,
    CustomJS,
    BoxZoomTool
)

# ——————————————————————————————————————————————
# 1) LOAD & PARSE YOUR CSVs
# ——————————————————————————————————————————————

# Lines
DF_LINES = pd.read_csv("lines.csv")
LINE_COLOR_MAP = {
    "CABLE_1x400_50kV": "lightblue",
    "CABLE_3x150_10kV": "purple"
}
DF_LINES["color"] = DF_LINES["std_type"].map(LINE_COLOR_MAP)

def extract_line_coords(geo_json):
    g = json.loads(geo_json)
    return [pt[0] for pt in g["coordinates"]], [pt[1] for pt in g["coordinates"]]

line_xs, line_ys = zip(*DF_LINES["geo"].apply(extract_line_coords))

# Buses
DF_BUSES = pd.read_csv("buses.csv")
# identify bus ID column
df_id_col = DF_BUSES.columns[0]
BUS_COLOR_MAP = {50.0: "lightblue", 10.0: "purple"}

def extract_bus_coords(geo_json):
    g = json.loads(geo_json)
    return g["coordinates"][0], g["coordinates"][1]

# Loads
DF_LOADS = pd.read_csv("loads.csv")  # expects 'bus' plus one load column
load_cols = [c for c in DF_LOADS.columns if c != "bus"]
if not load_cols:
    raise ValueError("loads.csv must have a 'bus' and at least one load column")
val_col = load_cols[0]
DF_LOADS = DF_LOADS.rename(columns={val_col: "load_index"})

# Merge loads, keep DF_BUSES columns unchanged, suffix duplicates from DF_LOADS
DF_BUSES = DF_BUSES.merge(
    DF_LOADS,
    how="left",
    left_on=df_id_col,
    right_on="bus",
    suffixes=("", "_load")
)
DF_BUSES = DF_BUSES.rename(columns={'p_mw': "load_mw"})
DF_BUSES["load_mw"] = DF_BUSES["load_mw"].fillna(0)

# Compute default colors by voltage
DF_BUSES["color"] = DF_BUSES["vn_kv"].map(BUS_COLOR_MAP)
# Override color for buses with load
DF_BUSES.loc[DF_BUSES["load_mw"] > 0, "color"] = "orange"

# Coordinates for all buses
bus_xs, bus_ys = zip(*DF_BUSES["geo"].apply(extract_bus_coords))

# Split into load‐buses (by prefix) vs. others
is_load_bus = DF_BUSES[df_id_col].astype(str).str.startswith("bus_load_")
DF_LOAD = DF_BUSES[is_load_bus]
DF_OTHER = DF_BUSES[~is_load_bus]

if not DF_LOAD.empty:
    load_xs, load_ys = zip(*DF_LOAD["geo"].apply(extract_bus_coords))
else:
    load_xs, load_ys = [], []
if not DF_OTHER.empty:
    other_xs, other_ys = zip(*DF_OTHER["geo"].apply(extract_bus_coords))
else:
    other_xs, other_ys = [], []

# Build lookup: bus_id → (x, y, vn)
BUS_LOOKUP = {
    bid: (x, y, vn)
    for bid, x, y, vn in zip(
        DF_BUSES[df_id_col], bus_xs, bus_ys, DF_BUSES["vn_kv"]
    )
}

# Transformers
DF_TRAFOS = pd.read_csv("trafos.csv")
trafo_pairs = DF_TRAFOS.apply(
    lambda row: (
        [BUS_LOOKUP[row["hv_bus"]][0], BUS_LOOKUP[row["lv_bus"]][0]],
        [BUS_LOOKUP[row["hv_bus"]][1], BUS_LOOKUP[row["lv_bus"]][1]]
    ), axis=1
)
trafo_xs, trafo_ys = zip(*trafo_pairs)
trafo_names = DF_TRAFOS.get("name", [f"T{idx}" for idx in DF_TRAFOS.index])

# Switches
DF_SW = pd.read_csv("switches.csv")
switch_xs, switch_ys, switch_colors, switch_labels = [], [], [], []
for idx, row in DF_SW.iterrows():
    b, elem, et = row["bus"], row["element"], row["et"]
    if et != "b":
        raise ValueError(f"Switch row {idx}: unsupported et='{et}'")
    if b not in BUS_LOOKUP or elem not in BUS_LOOKUP:
        raise KeyError(f"Switch row {idx}: '{b}' or '{elem}' not found")
    x0, y0, vn = BUS_LOOKUP[b]
    x1, y1, _ = BUS_LOOKUP[elem]
    switch_xs.append([x0, x1])
    switch_ys.append([y0, y1])
    switch_colors.append(BUS_COLOR_MAP[vn])
    switch_labels.append(f"{b}⇄{elem}")

# External grid points
DF_EXT = pd.read_csv("ext_grid.csv")
ext_xs, ext_ys = [], []
for idx, row in DF_EXT.iterrows():
    bid = row["bus"]
    if bid not in BUS_LOOKUP:
        raise KeyError(f"External row {idx}: bus '{bid}' not found")
    x, y, _ = BUS_LOOKUP[bid]
    ext_xs.append(x)
    ext_ys.append(y)

# ——————————————————————————————————————————————
# 2) CREATE COLUMN DATA SOURCES
# ——————————————————————————————————————————————
line_source = ColumnDataSource({
    "xs": list(line_xs), "ys": list(line_ys),
    "name": DF_LINES["name"], "color": DF_LINES["color"]
})
other_bus_source = ColumnDataSource({
    "x": list(other_xs), "y": list(other_ys),
    "id": DF_OTHER[df_id_col], "vn_kv": DF_OTHER["vn_kv"],
    "type": DF_OTHER["type"], "in_service": DF_OTHER["in_service"],
    "color": DF_OTHER["color"], "load_mw": DF_OTHER["load_mw"]
})
load_bus_source = ColumnDataSource({
    "x": list(load_xs), "y": list(load_ys),
    "id": DF_LOAD[df_id_col], "vn_kv": DF_LOAD["vn_kv"],
    "type": DF_LOAD["type"], "in_service": DF_LOAD["in_service"],
    "color": DF_LOAD["color"], "load_mw": DF_LOAD["load_mw"]
})
trafo_source = ColumnDataSource({"xs": list(trafo_xs), "ys": list(trafo_ys), "name": trafo_names})
switch_source = ColumnDataSource({
    "xs": switch_xs, "ys": switch_ys,
    "color": switch_colors, "label": switch_labels
})
ext_source = ColumnDataSource({"x": ext_xs, "y": ext_ys})

# ——————————————————————————————————————————————
# 3) SET UP PLOT
# ——————————————————————————————————————————————
p = figure(
    width=800, height=800,
    title="Grid: Lines, Buses, Transformers, Switches & External Grid",
    tools="pan,wheel_zoom,box_zoom,reset,tap",
    active_drag="pan",
    active_scroll="wheel_zoom",
    match_aspect=True
)
box_zoom = BoxZoomTool(match_aspect=True)
p.add_tools(box_zoom)

# ——————————————————————————————————————————————
# 4) DRAW LINES
# ——————————————————————————————————————————————
lines = p.multi_line(
    xs="xs", ys="ys", source=line_source,
    line_width=2, line_color="color",
    selection_line_color="red", nonselection_line_alpha=0.1
)
p.add_tools(HoverTool(tooltips=[("Line", "@name")], renderers=[lines]))
p.js_on_event("tap", CustomJS(args=dict(source=line_source), code="""
    if (!source.selected.indices.length) { source.selected.indices=[]; source.change.emit(); }
"""))

# ——————————————————————————————————————————————
# 5) DRAW BUSES
# ——————————————————————————————————————————————
# normal buses: circles
p.circle(
    x="x", y="y", source=other_bus_source,
    size=8, fill_color="color", line_color="white", alpha=0.8,
    legend_label="Bus"
)
# load buses: squares
p.square(
    x="x", y="y", source=load_bus_source,
    size=10, fill_color="color", line_color="white", alpha=0.8,
    legend_label="Load Bus"
)
# hover tool for buses including load info
hover_bus = HoverTool(tooltips=[
    ("Bus ID", "@id"),
    ("Voltage", "@vn_kv kV"),
    ("Load", "@load_mw MW"),
    ("Type", "@type"),
    ("In service?", "@in_service")
])
p.add_tools(hover_bus)

# ——————————————————————————————————————————————
# 6) DRAW TRANSFORMERS
# ——————————————————————————————————————————————
p.multi_line(
    xs="xs", ys="ys", source=trafo_source,
    line_width=3, line_color="green", legend_label="Transformer"
)

# ——————————————————————————————————————————————
# 7) DRAW SWITCHES
# ——————————————————————————————————————————————
p.multi_line(
    xs="xs", ys="ys", source=switch_source,
    line_width=2, line_color="color", line_dash="dashed", legend_label="Switch"
)

# ——————————————————————————————————————————————
# 8) DRAW EXTERNAL GRID
# ——————————————————————————————————————————————
p.square(
    x="x", y="y", source=ext_source,
    size=12, fill_color="yellow", line_color="black", alpha=0.9,
    legend_label="External Grid"
)

# ——————————————————————————————————————————————
# 9) OUTPUT & AUTO-OPEN
# ——————————————————————————————————————————————
html_file = "grid_visualization.html"
output_file(html_file, title="Grid Interactive")
save(p)
webbrowser.open(f"file://{os.path.abspath(html_file)}", new=2)
print(f"✔️ Created and opened '{html_file}' in your browser.")
