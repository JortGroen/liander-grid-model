from pandapower.plotting.plotly import simple_plotly
import plotly.graph_objects as go
from plotly.offline import plot as plt
import pandapower.plotting as plot

from shapely.geometry.base import BaseGeometry

def trace_polygon(polygon):
    poly_x = [p[0] for p in polygon]
    poly_y = [p[1] for p in polygon]
    poly_x.append(poly_x[0])
    poly_y.append(poly_y[0])
    trace = go.Scatter(
        x=poly_x,
        y=poly_y,
        mode="lines",
        fill='none',
        name="Region Outline",
        meta={"show_scale_legend": False}
    )
    return trace

# def add_network_outline(fig):
#     # polygon = [(108426, 511361), (108667, 512163), (109206, 511976), (108971, 511173)]
#     polygon = [(115396.47, 508717.54), (118588.55, 516876.17), (110697, 517792.25), (108290.91, 514944.67), (106734.67,512273.68)]  # extended area
#     fig.add_trace(trace_polygon(polygon))


def add_markers(fig, points:BaseGeometry, color="red", size=10):
    x_points = [p.x for p in points]
    y_points = [p.y for p in points]

    fig.add_trace(go.Scatter(
        x=x_points, 
        y=y_points,
        mode="markers",  # Show as points (not lines)
        marker=dict(
            color=color,  # Color of the points
            size=size,      # Size of the points
        ),
        name=f"{color} markers"  # Optional: add a legend label
    ))

def draw_switches(fig, net):
    # Create switch markers

    switch_lines = []
    for idx, sw in net.switch.iterrows():
        bus1_idx = sw.bus
        bus1_coord = net.bus.loc[bus1_idx]['pos']

        # Determine the second coordinate based on switch type
        if sw.et == "b":  # Bus-bus switch
            try:
                bus2_idx = sw.element
                bus2_coord = net.bus.loc[bus2_idx]['pos']
            except KeyError:
                continue
        else:
            raise NotImplementedError(f"Plotting of switch type '{sw.et}' is not implemented.")
    
        # Draw green line
        trace = go.Scatter(
            x=[bus1_coord.x, bus2_coord.x],
            y=[bus1_coord.y, bus2_coord.y],
            mode="lines",
            line=dict(color="green", width=2, dash="dash"),
            name="Switch" if idx == 0 else None,  # Avoid duplicate legend entries
            showlegend=(idx == 0)
        )
        fig.add_trace(trace)

def plot_network(net):
    # polygon = [(108707, 511633), (108760, 511800), (108991, 511846), (108960, 511541)]  # tiny area
    # polygon = [(108426, 511361), (108667, 512163), (109206, 511976), (108971, 511173)]
    polygon = [(115396.47, 508717.54), (118588.55, 516876.17), (110697, 517792.25), (108290.91, 514944.67), (106734.67,512273.68)]  # extended area
    trace = trace_polygon(polygon)
    fig = simple_plotly(net, aspectratio=(1,1), additional_traces=[trace], auto_draw_traces=True, auto_open=False)

    fig.update_layout(
        autosize=True,
        height=1200,  # Set a fixed height
        width=1200,   # Set width equal to height for a square shape
        xaxis=dict(scaleanchor="y"),  # Lock the x and y axes ratio
        yaxis=dict(scaleanchor="x"),
        legend=dict(
            orientation="h",  # Horizontally align the legend (optional)
            x=0.5,            # Position the legend in the center horizontally
            xanchor="center", # Anchor the legend to the center
            y=-0.2,           # Place the legend below the plot (adjust as needed)
            yanchor="bottom"  # Anchor the legend to the bottom
            )
        )
    

    return fig

def show(fig):
    plt(fig)