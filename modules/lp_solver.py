import numpy as np
from scipy.optimize import linprog
import pandas as pd

class LPSolver:
    def __init__(self, parser_result):
        self.data = parser_result
        self.solution = None
        
    def solve(self, assume_non_negative=True):
        self.assume_non_negative = assume_non_negative
        # Prepare bounds
        default_bound = (0, None) if assume_non_negative else (None, None)
        bounds_list = [default_bound] * len(self.data['variables'])
        
        try:
            res = linprog(
                c=self.data['c'],
                A_ub=self.data['A_ub'],
                b_ub=self.data['b_ub'],
                A_eq=self.data['A_eq'],
                b_eq=self.data['b_eq'],
                bounds=bounds_list,
                method='highs'
            )
            
            self.solution = res
            return self._format_result(res)
            
        except Exception as e:
            return {"status": "Error", "message": str(e)}

    def _format_result(self, res):
        status_map = {
            0: "Optimal",
            1: "Iteration limit reached",
            2: "Infeasible",
            3: "Unbounded",
            4: "Numerical difficulties"
        }
        
        status_text = status_map.get(res.status, "Unknown")
        
        if self.data['optimization_type'] == 'max':
            z_value = -res.fun if res.success else None
        else:
            z_value = res.fun if res.success else None

        result = {
            "status": status_text,
            "success": res.success,
            "message": res.message,
            "z_value": z_value,
            "variables": {},
            "constraints": [],
            "vertices": []
        }
        
        if res.success:
            # Map variables
            for i, var in enumerate(self.data['variables']):
                result["variables"][var] = res.x[i]
            
            # Detailed Constraint Analysis
            result["constraints"] = self.analyze_constraints(res)
            
            # Vertex Calculation (2D or ND)
            if len(self.data['variables']) == 2:
                result["vertices"] = self.calculate_2d_vertices(res)
                result["c1_c2_range"] = self.calculate_c1_c2_range(res)
            elif len(self.data['variables']) > 2:
                result["vertices"] = self.calculate_nd_vertices(res)
                
        return result

    def calculate_c1_c2_range(self, res):
        if not res.success or len(self.data['variables']) != 2:
            return None
            
        opt_x = res.x[0]
        opt_y = res.x[1]
        v1 = self.data['variables'][0]
        v2 = self.data['variables'][1]
        
        active_ratios = []
        tol = 1e-4
        
        for c_info in self.data.get('constraints_info', []):
            orig = c_info['original']
            a = orig['lhs'].get(v1, 0)
            b = orig['lhs'].get(v2, 0)
            val = a * opt_x + b * opt_y
            rhs = orig['rhs']
            
            # Check if active
            if abs(val - rhs) < tol:
                if abs(b) > 1e-9:
                    active_ratios.append(a / b)
                else:
                    active_ratios.append(float('inf'))
                    
        if self.assume_non_negative:
            if abs(opt_x) < tol:
                active_ratios.append(float('inf'))
            if abs(opt_y) < tol:
                active_ratios.append(0.0)
                
        if len(active_ratios) < 2:
            return None
            
        c1 = self.data['original_c'][0]
        c2 = self.data['original_c'][1]
        
        current_r = c1 / c2 if abs(c2) > 1e-9 else float('inf')
        
        # For a standard 2D problem, the valid c1/c2 range for maintaining this optimal vertex
        # is bounded by the minimum and maximum slopes of the active constraints.
        min_r = min(active_ratios)
        max_r = max(active_ratios)
        
        return {
            'min': min_r,
            'max': max_r,
            'current': current_r
        }

    def analyze_constraints(self, res):
        analysis = []
        tol = 1e-5
        
        rhs_ranges = self.calculate_2d_rhs_ranges(res) if len(self.data['variables']) == 2 else {}
        
        # Accessing duals (shadow prices)
        # res.ineqlin.marginals, res.eqlin.marginals
        # Note: Scipy's Highs wrapper structure:
        # res.ineqlin is for A_ub x <= b_ub
        # res.eqlin is for A_eq x = b_eq
        
        ineq_duals = res.ineqlin.marginals if hasattr(res, 'ineqlin') and res.ineqlin is not None else []
        eq_duals = res.eqlin.marginals if hasattr(res, 'eqlin') and res.eqlin is not None else []
        
        for c_info in self.data.get('constraints_info', []):
            original = c_info['original'] # {lhs, op, rhs, original_text}
            
            # Calculate actual LHS using x values
            lhs_val = 0
            for var, coeff in original['lhs'].items():
                if var in self.data['variables']:
                    idx = self.data['variables'].index(var)
                    lhs_val += coeff * res.x[idx]
            
            rhs_val = original['rhs']
            op = original['op']
            
            slack = 0
            surplus = 0
            gap = 0
            is_active = False
            note = ""
            
            if op == '<=':
                slack = rhs_val - lhs_val
                if abs(slack) < tol:
                    is_active = True
                note = f"Slack: {slack:.4f}"
            elif op == '>=':
                surplus = lhs_val - rhs_val
                if abs(surplus) < tol:
                    is_active = True
                note = f"Surplus: {surplus:.4f}"
            elif op == '=':
                gap = abs(lhs_val - rhs_val)
                if gap < tol:
                    is_active = True
                note = f"Diff: {gap:.4f}"
            
            # Shadow Price
            dual_val = 0.0
            if c_info['solver_type'] == 'ub' and c_info['solver_index'] is not None:
                if c_info['solver_index'] < len(ineq_duals):
                   dual_val = ineq_duals[c_info['solver_index']]
            elif c_info['solver_type'] == 'eq' and c_info['solver_index'] is not None:
                if c_info['solver_index'] < len(eq_duals):
                   dual_val = eq_duals[c_info['solver_index']]
            
            # Adjust Shadow Price sign based on Optimization Direction
            # Scipy minimizes. Shadow price is change in Minimize obj per unit LHS.
            # If we are maximizing, Z_max = -Z_min.
            # So dual_max = -dual_min? Usually needs careful interpretation.
            # For now, we report the raw dual. Interpretation depends on text.
            
            analysis.append({
                "Constraint": original['original_text'],
                "Type": op,
                "LHS": lhs_val,
                "RHS": rhs_val,
                "Slack/Surplus": slack if op=='<=' else (surplus if op=='>=' else gap),
                "Active": is_active,
                "Shadow Price": dual_val,
                "Aumento Permisible": rhs_ranges.get(original['original_text'], {}).get('Increase', 'N/A'),
                "Disminución Permisible": rhs_ranges.get(original['original_text'], {}).get('Decrease', 'N/A')
            })
            
        return analysis

    def calculate_2d_rhs_ranges(self, res):
        if not res.success or len(self.data['variables']) != 2:
            return {}

        original_opt_z = res.fun
        tol = 1e-4

        ranges = {}
        for idx, c_info in enumerate(self.data.get('constraints_info', [])):
            orig = c_info['original']
            c_name = orig['original_text']
            
            # For each constraint, we find the allowable increase and decrease
            # by solving the LP repeatedly or using the shadow price and basis validity range.
            # A more robust approach for just 2D is to just check boundaries empirically.
            
            # Fallback strategy: empirical search since solving a 2D LP is very fast.
            # We want to find the max delta_b such that the CURRENT basis remains optimal.
            # Actually, Scipy doesn't easily expose the optimal basis matrix to do the textbook
            # B^-1 b >= 0 check robustly without re-implementing simplex.
            
            # Let's use the simplest reliable method for the textbook problem:
            # Reconstruct the textbook formula based on the intersection points.
            
            # The active constraints at the optimal solution:
            opt_x, opt_y = res.x[0], res.x[1]
            v1, v2 = self.data['variables'][0], self.data['variables'][1]
            val = orig['lhs'].get(v1, 0)*opt_x + orig['lhs'].get(v2, 0)*opt_y
            
            # If constraint is non-binding (slack > 0)
            if orig['op'] == '<=' and orig['rhs'] - val > tol:
                ranges[c_name] = {'Increase': float('inf'), 'Decrease': round(orig['rhs'] - val, 4)}
                continue
            elif orig['op'] == '>=' and val - orig['rhs'] > tol:
                ranges[c_name] = {'Increase': round(val - orig['rhs'], 4), 'Decrease': float('inf')}
                continue
                
            # If constraint is binding, we need to find the limits of its movement.
            # We move the constraint b by delta. The intersection moves.
            # As it moves, it will eventually violate another constraint.
            
            A1, B1 = orig['lhs'].get(v1, 0), orig['lhs'].get(v2, 0)
            
            # Find the *other* binding constraint that forms the optimal vertex
            other_binding = None
            for j, other_c in enumerate(self.data.get('constraints_info', [])):
                if j == idx: continue
                o_orig = other_c['original']
                o_val = o_orig['lhs'].get(v1, 0)*opt_x + o_orig['lhs'].get(v2, 0)*opt_y
                if abs(o_val - o_orig['rhs']) < tol:
                    A2, B2 = o_orig['lhs'].get(v1, 0), o_orig['lhs'].get(v2, 0)
                    # Check if not parallel
                    if abs(A1*B2 - A2*B1) > 1e-5:
                        other_binding = o_orig
                        break
            
            # Also check axis bounds as potential other binding constraint
            if not other_binding and self.assume_non_negative:
                if abs(opt_x) < tol:
                    other_binding = {'lhs': {v1: 1, v2: 0}, 'rhs': 0, 'op': '>='}
                elif abs(opt_y) < tol:
                    other_binding = {'lhs': {v1: 0, v2: 1}, 'rhs': 0, 'op': '>='}
                    
            if not other_binding:
                ranges[c_name] = {'Increase': 0.0, 'Decrease': 0.0}
                continue
                
            A2, B2 = other_binding['lhs'].get(v1, 0), other_binding['lhs'].get(v2, 0)
            Det = A1*B2 - A2*B1
            
            # Movement vector for a 1-unit increase in b1
            # A1(x+dx) + B1(y+dy) = b1 + 1  => A1dx + B1dy = 1
            # A2(x+dx) + B2(y+dy) = b2      => A2dx + B2dy = 0
            dx = B2 / Det
            dy = -A2 / Det
            
            max_inc = float('inf')
            max_dec = float('inf')
            
            # Check all OTHER boundaries including non-negativity
            all_limits = []
            for k, test_c in enumerate(self.data.get('constraints_info', [])):
                if k == idx: continue
                t_orig = test_c['original']
                if t_orig == other_binding: continue
                
                Ak, Bk = t_orig['lhs'].get(v1, 0), t_orig['lhs'].get(v2, 0)
                bk = t_orig['rhs']
                op_k = t_orig['op']
                
                # Current value
                val_k = Ak*opt_x + Bk*opt_y
                
                # Rate of change
                rate = Ak*dx + Bk*dy
                
                if op_k == '<=':
                    slack = bk - val_k
                    # We need val_k + delta * rate <= bk  =>  delta * rate <= slack
                    if rate > 1e-6:
                        max_inc = min(max_inc, slack / rate)
                    elif rate < -1e-6:
                        max_dec = min(max_dec, slack / -rate)
                elif op_k == '>=':
                    surplus = val_k - bk
                    # We need val_k + delta * rate >= bk  =>  delta * rate >= -surplus => delta * -rate <= surplus
                    if -rate > 1e-6:
                        max_inc = min(max_inc, surplus / -rate)
                    elif -rate < -1e-6:
                        max_dec = min(max_dec, surplus / rate)
                        
            if self.assume_non_negative:
                # x >= 0  => opt_x + delta*dx >= 0 => delta*dx >= -opt_x
                if -dx > 1e-6:
                    max_inc = min(max_inc, opt_x / -dx)
                elif dx < -1e-6:
                    max_dec = min(max_dec, opt_x / dx)
                    
                # y >= 0
                if -dy > 1e-6:
                    max_inc = min(max_inc, opt_y / -dy)
                elif dy < -1e-6:
                    max_dec = min(max_dec, opt_y / dy)

            # Special adjustment based on constraint type for display consistency
            if orig['op'] == '<=':
                ranges[c_name] = {
                    'Increase': round(max_inc, 4) if max_inc != float('inf') else float('inf'),
                    'Decrease': round(max_dec, 4) if max_dec != float('inf') else float('inf')
                }
            elif orig['op'] == '>=':
                # For >=, increasing the RHS restricts the region MORE.
                # The math above assumes delta is added to the equation value.
                ranges[c_name] = {
                    'Increase': round(max_dec, 4) if max_dec != float('inf') else float('inf'),
                    'Decrease': round(max_inc, 4) if max_inc != float('inf') else float('inf')
                }
            else:
                 ranges[c_name] = {'Increase': 0.0, 'Decrease': 0.0}
                 
        return ranges

    def calculate_2d_vertices(self, res):
        import itertools

        # Variable names (defined once, used throughout)
        v1 = self.data['variables'][0]
        v2 = self.data['variables'][1]

        # Gather all lines: ax + by = c
        lines = []

        # 1. Structural Constraints
        for c_info in self.data.get('constraints_info', []):
            orig = c_info['original']
            a = orig['lhs'].get(v1, 0)
            b = orig['lhs'].get(v2, 0)
            c = orig['rhs']
            lines.append({'a': a, 'b': b, 'c': c, 'name': orig['original_text'], 'type': orig['op']})

        # 2. Non-negativity bounds (if enabled) — use real variable names
        if self.assume_non_negative:
            lines.append({'a': 1, 'b': 0, 'c': 0, 'name': f'{v1} >= 0', 'type': '>='})
            lines.append({'a': 0, 'b': 1, 'c': 0, 'name': f'{v2} >= 0', 'type': '>='})

            
        vertices = []
        seen = set()
        
        for l1, l2 in itertools.combinations(lines, 2):
            # Intersection of
            # a1x + b1y = c1
            # a2x + b2y = c2
            
            det = l1['a']*l2['b'] - l2['a']*l1['b']
            if abs(det) < 1e-9:
                continue # Parallel
                
            x = (l1['c']*l2['b'] - l2['c']*l1['b']) / det
            y = (l1['a']*l2['c'] - l2['a']*l1['c']) / det
            
            pt = (round(x, 6), round(y, 6))
            if pt in seen:
                continue
            seen.add(pt)
            
            # Check Feasibility
            is_feasible = self.check_feasibility(pt[0], pt[1])
            
            c1 = self.data['original_c'][0]
            c2 = self.data['original_c'][1]
            z = c1 * pt[0] + c2 * pt[1]

            is_optimal = False
            # Optimality check with relative tolerance
            if self.data['optimization_type'] == 'max':
                opt_z = -res.fun
            else:
                opt_z = res.fun
            tol_z = max(1.0, abs(opt_z) * 1e-4)  # absolute floor + relative
            
            if is_feasible and abs(z - opt_z) < tol_z:
                is_optimal = True

            # Clean up -0.0 display issues
            px = pt[0] if abs(pt[0]) > 1e-9 else 0.0
            py = pt[1] if abs(pt[1]) > 1e-9 else 0.0

            c1 = self.data['original_c'][0]
            c2 = self.data['original_c'][1]

            # Optimality range for this specific vertex (valid if it's feasible)
            c1c2_min = ""
            c1c2_max = ""
            c1_min = ""
            c1_max = ""
            c2_min = ""
            c2_max = ""

            if is_feasible:
                # Find slopes of the two lines intersecting here (l1 and l2)
                # Equation is ax + by = c  =>  y = (-a/b)x + (c/b)  => slope magnitude for ratio is a/b
                ratios = []
                for L in [l1, l2]:
                    if abs(L['b']) > 1e-9:
                        ratios.append(L['a'] / L['b'])
                    else:
                        ratios.append(float('inf'))
                min_ratio = min(ratios)
                max_ratio = max(ratios)
                
                c1c2_min = min_ratio
                c1c2_max = max_ratio

                # c1 range (holding c2 constant)
                # ratio = c1 / c2 => min_ratio <= c1 / c2 <= max_ratio
                # If c2 > 0: c2 * min_ratio <= c1 <= c2 * max_ratio
                if c2 > 0:
                    c1_min = c2 * min_ratio if min_ratio != float('inf') else float('inf')
                    c1_max = c2 * max_ratio if max_ratio != float('inf') else float('inf')
                elif c2 < 0:
                    c1_min = c2 * max_ratio if max_ratio != float('inf') else -float('inf')
                    c1_max = c2 * min_ratio if min_ratio != float('inf') else -float('inf')
                else: # c2 == 0
                    c1_min = 0.0
                    c1_max = float('inf')

                # c2 range (holding c1 constant)
                # min_ratio <= c1 / c2 <= max_ratio => 1/max_ratio <= c2/c1 <= 1/min_ratio
                if c1 > 0:
                    c2_min = c1 / max_ratio if max_ratio != float('inf') and max_ratio != 0 else 0.0
                    c2_max = c1 / min_ratio if min_ratio != 0 else float('inf')
                elif c1 < 0:
                    c2_min = c1 / min_ratio if min_ratio != 0 else -float('inf')
                    c2_max = c1 / max_ratio if max_ratio != float('inf') and max_ratio != 0 else 0.0
                else:
                    c2_min = 0.0
                    c2_max = float('inf')

            # Build row with slack/surplus for each structural constraint
            row = {
                v1: px,
                v2: py,
                "Z": round(z, 4),
                "Factible": "Sí" if is_feasible else "No",
                "Optimal": is_optimal,
                "_c1c2_min": c1c2_min, # Hidden from main table, extracted later
                "_c1c2_max": c1c2_max,
                "_c1_min": c1_min,
                "_c1_max": c1_max,
                "_c2_min": c2_min,
                "_c2_max": c2_max,
            }

            for idx, c_info in enumerate(self.data.get('constraints_info', []), start=1):
                orig = c_info['original']
                a = orig['lhs'].get(v1, 0)
                b = orig['lhs'].get(v2, 0)
                lhs_val = a * pt[0] + b * pt[1]
                rhs_val = orig['rhs']
                op = orig['op']
                if op == '<=':
                    slack_val = round(rhs_val - lhs_val, 6)
                    col = f"s{idx}"
                elif op == '>=':
                    slack_val = round(lhs_val - rhs_val, 6)
                    col = f"e{idx}"
                else:
                    slack_val = round(abs(lhs_val - rhs_val), 6)
                    col = f"gap{idx}"
                row[col] = slack_val

            row["Restricciones Activas"] = f"{l1['name']}, {l2['name']}"

            # Basic / Non-basic classification
            # A variable is basic if its value > 0, non-basic if = 0
            basic = []
            nonbasic = []
            # Decision variables
            for dv, dval in [(v1, px), (v2, py)]:
                if abs(dval) > 1e-6:
                    basic.append(dv)
                else:
                    nonbasic.append(dv)
            # Slack/surplus variables
            for key, val in row.items():
                if key.startswith('s') or key.startswith('e') or key.startswith('gap'):
                    if abs(val) > 1e-6:
                        basic.append(key)
                    else:
                        nonbasic.append(key)

            row["Básicas"] = ", ".join(basic) if basic else "—"
            row["No Básicas"] = ", ".join(nonbasic) if nonbasic else "—"
            vertices.append(row)

        # Sort by first two variable values
        vertices.sort(key=lambda v: (v.get(v1, 0), v.get(v2, 0)))
        return vertices

    def check_feasibility(self, x, y):
        tol = 1e-5
        # Check explicit constraints
        for c_info in self.data.get('constraints_info', []):
            orig = c_info['original']
            v1 = self.data['variables'][0]
            v2 = self.data['variables'][1]
            val = orig['lhs'].get(v1, 0)*x + orig['lhs'].get(v2, 0)*y
            rhs = orig['rhs']
            op = orig['op']
            
            if op == '<=':
                if val > rhs + tol: return False
            elif op == '>=':
                if val < rhs - tol: return False
            elif op == '=':
                if abs(val - rhs) > tol: return False
                
        # Check non-negativity
        if self.assume_non_negative:
            if x < -tol or y < -tol: return False
            
        return True

    def calculate_nd_vertices(self, res):
        import itertools
        import numpy as np

        num_vars = len(self.data['variables'])
        
        # Gather all hyperplane equations: Ax = b
        equations = []
        
        # 1. Structural Constraints
        for c_info in self.data.get('constraints_info', []):
            orig = c_info['original']
            row_coeffs = [orig['lhs'].get(v, 0) for v in self.data['variables']]
            equations.append({
                'coeffs': row_coeffs, 
                'rhs': orig['rhs'],
                'name': orig['original_text'],
                'op': orig['op']
            })

        # 2. Non-negativity bounds (if enabled)
        if self.assume_non_negative:
            for i, v in enumerate(self.data['variables']):
                row_coeffs = [1 if j == i else 0 for j in range(num_vars)]
                equations.append({
                    'coeffs': row_coeffs, 
                    'rhs': 0,
                    'name': f'{v} >= 0',
                    'op': '>='
                })

        vertices = []
        seen = set()
        
        # We need exactly `num_vars` hyperplanes to intersect to form a vertex
        for combo in itertools.combinations(equations, num_vars):
            A = np.array([eq['coeffs'] for eq in combo])
            b = np.array([eq['rhs'] for eq in combo])
            
            try:
                # Solve Ax = b
                pt = np.linalg.solve(A, b)
                # Round to avoid floating point issues
                pt_tuple = tuple(round(float(x), 6) for x in pt)
                
                if pt_tuple in seen:
                    continue
                seen.add(pt_tuple)
                
                # Check Feasibility
                is_feasible = True
                
                # Check against structural
                tol = 1e-4
                for eq in equations:
                    val = sum(c * x for c, x in zip(eq['coeffs'], pt_tuple))
                    if eq['op'] == '<=' and val > eq['rhs'] + tol:
                        is_feasible = False; break
                    elif eq['op'] == '>=' and val < eq['rhs'] - tol:
                        is_feasible = False; break
                    elif eq['op'] == '=' and abs(val - eq['rhs']) > tol:
                        is_feasible = False; break
                
                z = sum(c * x for c, x in zip(self.data['original_c'], pt_tuple))

                is_optimal = False
                if self.data['optimization_type'] == 'max':
                    opt_z = -res.fun
                else:
                    opt_z = res.fun
                tol_z = max(1.0, abs(opt_z) * 1e-4)

                if is_feasible and abs(z - opt_z) < tol_z:
                    is_optimal = True

                row = {
                    "Z": round(z, 4),
                    "Factible": "Sí" if is_feasible else "No",
                    "Optimal": is_optimal,
                }
                
                # Add variable values
                for i, v in enumerate(self.data['variables']):
                    clean_val = pt_tuple[i] if abs(pt_tuple[i]) > 1e-9 else 0.0
                    row[v] = clean_val
                    
                # Add slack/surplus values for structural constraints
                for idx, c_info in enumerate(self.data.get('constraints_info', []), start=1):
                    orig = c_info['original']
                    val = sum(orig['lhs'].get(v, 0) * pt_tuple[i] for i, v in enumerate(self.data['variables']))
                    if orig['op'] == '<=':
                        row[f"s{idx}"] = round(orig['rhs'] - val, 6)
                    elif orig['op'] == '>=':
                        row[f"e{idx}"] = round(val - orig['rhs'], 6)
                    elif orig['op'] == '=':
                        row[f"a{idx}"] = round(abs(val - orig['rhs']), 6)

                vertices.append(row)
                
            except np.linalg.LinAlgError:
                # Singular matrix = lines don't intersect at exactly one point (parallel or dependent)
                continue

        # Reorder columns slightly so variables are first, then Z, etc.
        df = pd.DataFrame(vertices)
        if not df.empty:
            cols = self.data['variables'] + ["Z", "Factible", "Optimal"] + [c for c in df.columns if c not in self.data['variables'] + ["Z", "Factible", "Optimal"]]
            df = df[cols]
            
        return df
