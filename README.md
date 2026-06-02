# liander-grid-model

Constructs a [pandapower](https://www.pandapower.org/) medium-voltage (10 kV) distribution network from Liander's open GIS data and runs power flow simulations on it.

## Overview

The pipeline reads cable and installation data from a Liander GeoPackage, builds a topologically correct pandapower network, infers HV/MV transformer locations by clustering terminal buses, attaches loads, and exports results for analysis and visualisation.

Voltage levels modelled: **10 kV** (MV). The 50 kV HV backbone is used only to locate transformer sites; it is removed from the final network.

## Installation

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

## Data

The pipeline expects a Liander GeoPackage with the following layers:

| Layer | Description |
|---|---|
| `hoogspanningskabels` | 50 kV HV cables |
| `middenspanningskabels` | 10 kV MV cables |
| `middenspanningsinstallaties` | MV installation points (MV/LV transformer sites) |

Liander publishes this data as open data at [liander.nl/over-liander/open-data](https://www.liander.nl/over-liander/open-data).

The raw file is not included in this repository. Update the path and polygon in `gridIO.py` / `grid_construct.py` to match your area of interest. Coordinates use the Dutch RD New projection (EPSG:28992).

## Usage

**Build the network:**

```bash
python grid_construct.py
```

This writes `extended_network.xlsx` (and CSV snapshots) to the working directory and opens an interactive plotly visualisation.

**Run power flow on an existing network:**

```bash
python power_flow.py
```

Loads `extended_network.xlsx` and calls `pp.runpp()`, then opens a plotly power-flow results plot.

## Project structure

```
├── assets.py            # Cable and transformer standard types (Liander specs)
├── gridIO.py            # GeoPackage I/O and spatial filtering
├── grid_construct.py    # Main pipeline: GIS → pandapower network
├── cluster.py           # Radius-based bus clustering (for transformer detection)
├── merge_lines.py       # Collapse degree-2 intermediate nodes
├── network_plotter.py   # Plotly visualisation helpers
├── power_flow.py        # Load network from Excel and run power flow
├── interactive_vis.py   # Bokeh-based interactive visualisation
└── requirements.txt
```

## License

MIT
