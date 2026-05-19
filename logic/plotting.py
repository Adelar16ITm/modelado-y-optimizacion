import plotly.graph_objects as go
import numpy as np

def generate_lp_plot(parsed_data, vertices, solution_point=None, z_val=None, show_vertex_labels=True):
    """
    Generates a Plotly figure for the LP region.
    """
    fig = go.Figure()
    
    # 1. Setup Ranges
    # 1. Setup Ranges
    if not vertices:
        # Smart Auto-Range for Infeasible/Unbounded cases
        # Calculate intercepts of all constraints to find 'action area'
        x_vals = [0]
        y_vals = [0]
        
        for meta in parsed_data.get('constraints_meta', []):
            try:
                a, b = meta['coeffs']
                c = meta['limit']
                if abs(a) > 1e-6: x_vals.append(c/a)
                if abs(b) > 1e-6: y_vals.append(c/b)
            except: pass
            
        # Filter extreme values (e.g. parallel lines near infinity)
        x_vals = [x for x in x_vals if -1e6 < x < 1e6]
        y_vals = [y for y in y_vals if -1e6 < y < 1e6]
        
        if not x_vals: x_vals = [10]
        if not y_vals: y_vals = [10]
        
        pad_x = (max(x_vals) - min(x_vals)) * 0.1 + 1
        pad_y = (max(y_vals) - min(y_vals)) * 0.1 + 1
        
        x_min, x_max = min(x_vals) - pad_x, max(x_vals) + pad_x
        y_min, y_max = min(y_vals) - pad_y, max(y_vals) + pad_y
        
        # Enforce non-negative view preference slightly
        if x_min > -10: x_min = -1
        if y_min > -10: y_min = -1
    else:
        xs = [v['x'] for v in vertices]
        ys = [v['y'] for v in vertices]
        pad_x = (max(xs) - min(xs))*0.2 if max(xs)!=min(xs) else 2
        pad_y = (max(ys) - min(ys))*0.2 if max(ys)!=min(ys) else 2
        x_min, x_max = min(xs)-pad_x, max(xs)+pad_x
        y_min, y_max = min(ys)-pad_y, max(ys)+pad_y
        
        # Ensure 0 is visible if near
        x_min = min(x_min, -0.5)
        y_min = min(y_min, -0.5)

    # 2. Feasible Region
    if len(vertices) >= 3:
        px = [v['x'] for v in vertices] + [vertices[0]['x']]
        py = [v['y'] for v in vertices] + [vertices[0]['y']]
        
        fig.add_trace(go.Scatter(
            x=px, y=py,
            fill='toself',
            mode='lines',
            line=dict(color='rgba(0,100,200,0.5)', width=0), 
            fillcolor='rgba(0,120,255,0.2)', # Modern Blue
            name='Feasible Region',
            hoverinfo='skip',
            showlegend=True
        ))

    # 3. Plot Constraints Lines
    # Academic Palette: Blue, Orange, Green, Red, Purple, Brown, Pink, Gray, Olive, Cyan
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf']
    
    # Active constraints logic
    active_indices = set()
    if solution_point is not None:
         sx, sy = solution_point[0], solution_point[1]
         for i, meta in enumerate(parsed_data.get('constraints_meta', [])):
             # Re-evaluate LHS to check slack
             coeffs = meta['coeffs']
             val = coeffs[0]*sx + coeffs[1]*sy if len(coeffs) >= 2 else coeffs[0]*sx
             if abs(val - meta['limit']) < 1e-4:
                 active_indices.add(i)

    def get_line_segment(a, b, c, type_, xr, yr):
        # ax + by = c
        def y_at_x(x): return (c - a*x)/b
        def x_at_y(y): return (c - b*y)/a
        
        pts = []
        
        if abs(b) < 1e-9:
             # Vertical Line: ax = c -> x = c/a
             if abs(a) > 1e-9:
                 x = c/a
                 if xr[0] <= x <= xr[1]:
                     pts.append((x, yr[0]))
                     pts.append((x, yr[1]))
                     
        elif abs(a) < 1e-9:
            # Horizontal Line: by = c -> y = c/b
            if abs(b) > 1e-9:
                y = c/b
                if yr[0] <= y <= yr[1]:
                    pts.append((xr[0], y))
                    pts.append((xr[1], y))
        else:
            # General Case
            # Check intersection with borders (x_min, x_max, y_min, y_max)
            # x_min
            y = y_at_x(xr[0])
            if yr[0] <= y <= yr[1]: pts.append((xr[0], y))
            # x_max
            y = y_at_x(xr[1])
            if yr[0] <= y <= yr[1]: pts.append((xr[1], y))
            # y_min
            x = x_at_y(yr[0])
            if xr[0] <= x <= xr[1]: pts.append((x, yr[0]))
            # y_max
            x = x_at_y(yr[1])
            if xr[0] <= x <= xr[1]: pts.append((x, yr[1]))
            
        return sorted(list(set(pts)))

    for i, meta in enumerate(parsed_data.get('constraints_meta', [])):
        coeffs = meta['coeffs']
        a = coeffs[0]
        b = coeffs[1] if len(coeffs) > 1 else 0
        c = meta['limit']
        
        is_active = i in active_indices
        
        pts = get_line_segment(a, b, c, meta['type'], (x_min, x_max), (y_min, y_max))
        if len(pts) >= 2:
            width = 3 if is_active else 2
            opacity = 1.0 if is_active else 0.7
            dash = 'solid' if is_active else 'dashdot'
            
            # Shorten name for legend
            lbl = meta['original']
            legend_lbl = lbl[:20] + "..." if len(lbl) > 20 else lbl
            
            fig.add_trace(go.Scatter(
                x=[p[0] for p in pts],
                y=[p[1] for p in pts],
                mode='lines',
                name=legend_lbl,
                line=dict(width=width, dash=dash, color=colors[i % len(colors)]),
                opacity=opacity,
                hovertext=f"{meta['original']} {'[BINDING]' if is_active else ''}",
            ))

    # 4. Vertices Points (Annotations for "Rounded Text Boxes")
    if vertices:
        vx = [v['x'] for v in vertices]
        vy = [v['y'] for v in vertices]
        
        # Markers
        fig.add_trace(go.Scatter(
            x=vx, y=vy,
            mode='markers',
            marker=dict(size=8, color='black'),
            name='Vertices',
            hoverinfo='text',
            hovertext=[f"Vertex: ({v['x']:.2f}, {v['y']:.2f})" for v in vertices],
            showlegend=True
        ))
        
        # Annotations (better control than text trace)
        if show_vertex_labels:
            for v in vertices:
                # Offset logic to avoid overlap
                # Simple heuristic: push away from center of mass? or just top-right default
                fig.add_annotation(
                    x=v['x'],
                    y=v['y'],
                    text=f"({v['x']:.2f}, {v['y']:.2f})",
                    showarrow=True,
                    arrowhead=0,
                    arrowsize=1,
                    arrowwidth=1,
                    arrowcolor="#666",
                    ax=20, # offset x
                    ay=-20, # offset y
                    bgcolor="rgba(255,255,255,0.8)",
                    bordercolor="black",
                    borderwidth=1,
                    borderpad=4,
                    font=dict(size=10, color="black"),
                    captureevents=True
                )
        
    # 5. Optimal Point (Red Star)
    if solution_point:
        fig.add_trace(go.Scatter(
            x=[solution_point[0]], 
            y=[solution_point[1]],
            mode='markers',
            marker=dict(size=20, color='red', symbol='star'), 
            name='Optimal Point',
            hoverinfo='skip'
        ))
        
        # Optimal Annotation
        fig.add_annotation(
            x=solution_point[0],
            y=solution_point[1],
            text=f"<b>Optimal Point<br>({solution_point[0]:.2f}, {solution_point[1]:.2f})</b>",
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor="red",
            ax=0,
            ay=-40, # Above the star
            bgcolor="rgba(255,255,255,0.9)",
            bordercolor="red",
            borderwidth=2,
            borderpad=4,
            font=dict(size=12, color="red")
        )
        
    # Layout with External Legend
    fig.update_layout(
        title=dict(
            text="Feasible Region and Optimal Solution", 
            x=0.5, 
            y=0.95,
            xanchor='center',
            yanchor='top',
            font=dict(size=22, color="black", family="Arial")
        ),
        margin=dict(l=60, r=40, t=80, b=80), 
        height=700,
        dragmode='pan',
        template='plotly_white',
        plot_bgcolor='white',
        xaxis=dict(
            title=dict(text=f"<b>{parsed_data['variables'][0]}</b>", font=dict(size=14)),
            range=[x_min, x_max], 
            showgrid=True, gridcolor='#e5e5e5', gridwidth=1,
            zeroline=True, zerolinewidth=2, zerolinecolor='#333',
            mirror=True, ticks='outside', showline=True, linecolor='#333'
        ),
        yaxis=dict(
             title=dict(text=f"<b>{parsed_data['variables'][1]}</b>", font=dict(size=14)),
            range=[y_min, y_max], 
            showgrid=True, gridcolor='#e5e5e5', gridwidth=1,
            zeroline=True, zerolinewidth=2, zerolinecolor='#333',
             mirror=True, ticks='outside', showline=True, linecolor='#333'
        ),
        legend=dict(
            orientation="h", 
            yanchor="top", 
            y=-0.1, 
            xanchor="center", 
            x=0.5,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="#ccc",
            borderwidth=1,
            font=dict(size=12)
        ),
        hovermode="closest"
    )
    
    # Configure modebar
    config = {
        'toImageButtonOptions': {
            'format': 'png',
            'filename': 'lp_graph_export',
            'height': 800,
            'width': 1200,
            'scale': 2
        },
        'displayModeBar': False, # Clean Look requested
    }
    
    return fig, config
