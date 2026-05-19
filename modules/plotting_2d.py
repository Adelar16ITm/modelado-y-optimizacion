import plotly.graph_objects as go
import numpy as np
import itertools

class LPPlotter:
    def __init__(self, parser_result, solver_result):
        self.data = parser_result
        self.sol = solver_result
        self.vars = self.data['variables']
    
    def _get_line_intersection(self, line1, line2):
        # Line form: a1*x + b1*y = c1
        # Det = a1*b2 - a2*b1
        # x = (c1*b2 - c2*b1) / Det
        # y = (a1*c2 - a2*c1) / Det
        
        det = line1[0] * line2[1] - line2[0] * line1[1]
        if abs(det) < 1e-9: # Parallel
            return None
        
        x = (line1[2] * line2[1] - line2[2] * line1[1]) / det
        y = (line1[0] * line2[2] - line2[0] * line1[2]) / det
        return (x, y)

    def _is_feasible(self, point):
        x, y = point
        # Check non-negativity (hardcoded for now as per reqs usually)
        if x < -1e-7 or y < -1e-7:
            return False
            
        # Check all constraints
        # A_ub * [x, y] <= b_ub
        if self.data['A_ub'] is not None:
             vals = self.data['A_ub'] @ np.array([x, y])
             # Allow small tolerance
             if np.any(vals > self.data['b_ub'] + 1e-7):
                 return False
                 
        if self.data['A_eq'] is not None:
            vals = self.data['A_eq'] @ np.array([x, y])
            if np.any(np.abs(vals - self.data['b_eq']) > 1e-7):
                return False
                
        return True

    def plot(self):
        if len(self.vars) != 2:
            return None
            
        fig = go.Figure()
        
        # 1. Gather all "lines"
        # Constraints from A_ub, A_eq
        lines = [] # (a, b, c) for ax + by = c
        
        if self.data['A_ub'] is not None:
            for i, row in enumerate(self.data['A_ub']):
                lines.append((row[0], row[1], self.data['b_ub'][i]))
                
        if self.data['A_eq'] is not None:
            for i, row in enumerate(self.data['A_eq']):
                lines.append((row[0], row[1], self.data['b_eq'][i]))
                
        # Add bounds as lines: x = 0, y = 0
        lines.append((1, 0, 0)) # x=0
        lines.append((0, 1, 0)) # y=0
        
        # 2. Find Intersections (Vertices)
        feasible_vertices = []
        all_vertices = []
        for l1, l2 in itertools.combinations(lines, 2):
            pt = self._get_line_intersection(l1, l2)
            if pt:
                all_vertices.append(pt)
                if self._is_feasible(pt):
                    feasible_vertices.append(pt)
                
        # Add unique vertices
        unique_feasible = []
        for v in feasible_vertices:
            if not any(np.allclose(v, uv) for uv in unique_feasible):
                unique_feasible.append(v)
                
        unique_all = []
        for v in all_vertices:
            if not any(np.allclose(v, uv) for uv in unique_all):
                unique_all.append(v)
                
        # 3. Sort vertices to form a polygon (Convex Hull usually for LP region)
        if len(unique_feasible) > 2:
            # Sort by angle from centroid
            center = np.mean(unique_feasible, axis=0)
            def angle_from_center(p):
                return np.arctan2(p[1] - center[1], p[0] - center[0])
            unique_feasible.sort(key=angle_from_center)
            
            # Close the loop
            x_poly = [v[0] for v in unique_feasible] + [unique_feasible[0][0]]
            y_poly = [v[1] for v in unique_feasible] + [unique_feasible[0][1]]
            
            # Plot Feasible Region
            fig.add_trace(go.Scatter(
                x=x_poly, y=y_poly,
                fill='toself',
                fillcolor='rgba(0, 100, 255, 0.2)',
                line=dict(color='rgba(0, 100, 255, 0.5)'),
                name='Feasible Region',
                hoverinfo='skip'
            ))
            
            # Plot Vertices
            fig.add_trace(go.Scatter(
                x=[v[0] for v in unique_all],
                y=[v[1] for v in unique_all],
                mode='markers',
                marker=dict(color='blue', size=8),
                name='Vertices',
                text=[f"({v[0]:.2f}, {v[1]:.2f})" for v in unique_all],
                hoverinfo='text'
            ))

        # 4. Determine Plot Limits
        all_x = [v[0] for v in unique_all]
        all_y = [v[1] for v in unique_all]
        is_infeasible = (self.sol.get('status') in ('Infeasible', 'infeasible') or
                         (not self.sol.get('success') and self.sol.get('status') not in ('Unbounded', 'unbounded')))
        if self.sol['success']:
            all_x.append(self.sol['variables'][self.vars[0]])
            all_y.append(self.sol['variables'][self.vars[1]])
            
        if not all_x: all_x = [0, 10]
        if not all_y: all_y = [0, 10]
        
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        pad_x = max(1, (x_max - x_min) * 0.2)
        pad_y = max(1, (y_max - y_min) * 0.2)
        
        x_range = [max(0, x_min - pad_x), x_max + pad_x]
        y_range = [max(0, y_min - pad_y), y_max + pad_y]
        
        # 5. Plot Constraint Lines (clipped to view)
        # For ax + by = c
        # If b != 0: y = (c - ax) / b
        # If b == 0: x = c / a (vertical)
        
        line_x = np.linspace(x_range[0], x_range[1], 300)

        # Vivid, distinct colors per constraint
        _LINE_COLORS = ['#E53935', '#1E88E5', '#43A047', '#FB8C00', '#8E24AA',
                        '#00ACC1', '#F4511E', '#039BE5', '#00897B', '#FFB300']

        # Build constraint list with real labels from constraints_info
        constraints_source = []
        _cinfo = self.data.get('constraints_info', [])
        v1n, v2n = self.vars[0], self.vars[1]

        def _fmt_con_label(ci_idx, letter):
            """Return 'R1: 2x + 3y <= 10' style label."""
            try:
                orig = _cinfo[ci_idx]['original']
                lhs  = orig.get('lhs', {})
                op   = orig.get('op', '?')
                rhs  = orig.get('rhs', 0)
                parts = []
                for vn in [v1n, v2n]:
                    coef = float(lhs.get(vn, 0))
                    if abs(coef) < 1e-9:
                        continue
                    coef_s = '' if abs(coef - 1) < 1e-9 else (str(int(coef)) if coef == int(coef) else f"{coef:.3g}")
                    sign   = '-' if coef < 0 else ('+' if parts else '')
                    parts.append(f"{sign}{coef_s}{vn}".lstrip('+'))
                lhs_str = ' + '.join(parts).replace('+ -', '- ') if parts else '0'
                rhs_str = str(int(rhs)) if rhs == int(rhs) else f"{rhs:.4g}"
                return f"{letter}: {lhs_str} {op} {rhs_str}"
            except Exception:
                return letter

        if self.data['A_ub'] is not None:
            for i, row in enumerate(self.data['A_ub']):
                constraints_source.append({
                    'a': row[0], 'b': row[1], 'c': self.data['b_ub'][i],
                    'label': _fmt_con_label(i, f"R{i+1}")
                })
        if self.data['A_eq'] is not None:
            base = len(constraints_source)
            for i, row in enumerate(self.data['A_eq']):
                constraints_source.append({
                    'a': row[0], 'b': row[1], 'c': self.data['b_eq'][i],
                    'label': _fmt_con_label(base + i, f"Ig{i+1}")
                })

        for ci, con in enumerate(constraints_source):
            a, b, c = float(con['a']), float(con['b']), float(con['c'])
            color   = _LINE_COLORS[ci % len(_LINE_COLORS)]
            lname   = con['label']
            if abs(b) > 1e-5:
                line_y = (c - a * line_x) / b
                mask   = (line_y >= y_range[0] - 1) & (line_y <= y_range[1] + 1)
                fig.add_trace(go.Scatter(
                    x=line_x[mask], y=line_y[mask],
                    mode='lines',
                    line=dict(width=2.5, color=color),
                    name=lname,
                    opacity=1.0,
                    hovertemplate=f"<b>{lname}</b><br>(%{{x:.3g}}, %{{y:.3g}})<extra></extra>",
                ))
            elif abs(a) > 1e-5:
                val = c / a
                fig.add_trace(go.Scatter(
                    x=[val, val], y=y_range,
                    mode='lines',
                    line=dict(width=2.5, color=color),
                    name=lname,
                    opacity=1.0,
                    hovertemplate=f"<b>{lname}</b><br>x={val:.3g}<extra></extra>",
                ))

        # 6. Plot Optimal Solution
        if self.sol['success']:
            v1, v2 = self.vars[0], self.vars[1]
            optimal_pts = []
            
            # Buscamos todos los vértices óptimos
            for v_data in self.sol.get('vertices', []):
                if v_data.get('Optimal') and v_data.get('Factible') == 'Sí':
                    pt = (v_data.get(v1, 0.0), v_data.get(v2, 0.0))
                    # Evitar duplicados por exactitud numérica
                    if not any(np.allclose(pt, p) for p in optimal_pts):
                        optimal_pts.append(pt)
                        
            if not optimal_pts:
                # Fallback estándar si falla la lista de vértices
                opt_x = self.sol['variables'][self.vars[0]]
                opt_y = self.sol['variables'][self.vars[1]]
                optimal_pts.append((opt_x, opt_y))
                
            # Si hay múltiples soluciones óptimas, dibuja la línea/arista que las conecta
            if len(optimal_pts) > 1:
                # Ordenar para conectar correctamente los puntos 
                optimal_pts.sort(key=lambda p: (p[0], p[1]))
                col_x = [p[0] for p in optimal_pts]
                col_y = [p[1] for p in optimal_pts]
                fig.add_trace(go.Scatter(
                    x=col_x, y=col_y,
                    mode='lines',
                    line=dict(color='fuchsia', width=4, dash='solid'),
                    name='Arista Óptima',
                    opacity=0.8
                ))
            
            # Graficar los vértices óptimos
            colors = ['gold', 'red', 'lightgreen', 'cyan', 'orange']
            for i, (ox, oy) in enumerate(optimal_pts):
                color = colors[i % len(colors)]
                label = f'Óptimo {i+1}' if len(optimal_pts) > 1 else 'Óptimo'
                fig.add_trace(go.Scatter(
                    x=[ox], y=[oy],
                    mode='markers+text',
                    marker=dict(symbol='star', size=15, color=color, line=dict(color='black', width=1)),
                    name=label,
                    text=[label],
                    textposition='top center'
                ))

        # 6b. Infeasible: show intersection points only (no annotation overlay)
        elif is_infeasible:
            if unique_all:
                fig.add_trace(go.Scatter(
                    x=[v[0] for v in unique_all],
                    y=[v[1] for v in unique_all],
                    mode='markers',
                    marker=dict(color='gray', size=7, opacity=0.5, symbol='x'),
                    name='Intersecciones (sin región factible)',
                    hovertext=[f"({v[0]:.2g}, {v[1]:.2g})" for v in unique_all],
                    hoverinfo='text'
                ))

        _title = "Region Factible y Solucion" if self.sol.get('success') else \
                 ("Problema Infactible — las restricciones no tienen region comun" if is_infeasible
                  else "Sin Solucion — Restricciones")
        fig.update_layout(
            title=dict(text=_title, font=dict(size=13)),
            xaxis_title=self.vars[0],
            yaxis_title=self.vars[1],
            xaxis=dict(range=x_range),
            yaxis=dict(range=y_range),
            height=620,
            showlegend=True,
            legend=dict(orientation="v", x=1.01, y=1, xanchor='left',
                        bgcolor='rgba(255,255,255,0.85)', bordercolor='#ccc', borderwidth=1),
        )
        return fig
