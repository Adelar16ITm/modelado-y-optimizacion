import numpy as np
import pandas as pd
from itertools import combinations
import math

TOLERANCE = 1e-9

def solve_intersection(c1, c2):
    """
    Find intersection (x, y) of two lines:
    a1*x + b1*y = L1
    a2*x + b2*y = L2
    Returns None if parallel.
    """
    a1, b1, L1 = c1['a'], c1['b'], c1['limit']
    a2, b2, L2 = c2['a'], c2['b'], c2['limit']

    det = a1 * b2 - a2 * b1
    if abs(det) < TOLERANCE:
        return None # Parallel lines

    x = (L1 * b2 - L2 * b1) / det
    y = (a1 * L2 - a2 * L1) / det
    return (x, y)

def is_feasible(point, constraints):
    x, y = point
    for c in constraints:
        val = c['a'] * x + c['b'] * y
        lim = c['limit']
        op = c['op']
        
        # Allow small float error
        if op == 'lte':
            if val > lim + TOLERANCE: return False
        elif op == 'gte':
            if val < lim - TOLERANCE: return False
        elif op == 'eq':
            if abs(val - lim) > TOLERANCE: return False
    return True

def get_vertices_and_region(constraints, bounds_enabled=True):
    """
    1. Collects all constraints.
    2. Adds X>=0, Y>=0 if bounds_enabled.
    3. Finds all intersections.
    4. Filters feasible ones.
    5. Returns feasible_points (list of dicts) and status.
    """
    
    # Add implicit bounds if requested
    active_constraints = list(constraints) # Copy
    if bounds_enabled:
        # x >= 0  => 1*x + 0*y >= 0
        active_constraints.append({'a': 1.0, 'b': 0.0, 'limit': 0.0, 'op': 'gte', 'line_label': 'x ≥ 0'})
        # y >= 0  => 0*x + 1*y >= 0
        active_constraints.append({'a': 0.0, 'b': 1.0, 'limit': 0.0, 'op': 'gte', 'line_label': 'y ≥ 0'})

    unique_lines = active_constraints
    
    intersections = []
    
    # If 0 or 1 constraints, no finite region usually (unless equality/point). 
    # But usually need at least 2 lines to make a point.
    if len(unique_lines) < 2:
        return [], "Unbounded or Not Enough Constraints"

    # Find intersections of every pair
    for i in range(len(unique_lines)):
        for j in range(i + 1, len(unique_lines)):
            pt = solve_intersection(unique_lines[i], unique_lines[j])
            if pt:
                intersections.append({
                    'x': pt[0],
                    'y': pt[1],
                    'lines': [unique_lines[i]['line_label'], unique_lines[j]['line_label']]
                })

    # Filter feasible
    feasible_verts = []
    for pt in intersections:
        if is_feasible((pt['x'], pt['y']), active_constraints):
            # Check if duplicate (close to existing)
            is_dup = False
            for exist in feasible_verts:
                if math.isclose(exist['x'], pt['x'], abs_tol=1e-7) and math.isclose(exist['y'], pt['y'], abs_tol=1e-7):
                    # Merge line labels info
                    exist['lines'] = list(set(exist['lines'] + pt['lines']))
                    is_dup = True
                    break
            if not is_dup:
                feasible_verts.append(pt)

    return feasible_verts, "Feasible"

def order_vertices_polygon(vertices):
    """Sorts vertices to form a convex polygon (or ordered path) for plotting."""
    if not vertices:
        return []
    
    # Calculate centroid
    cx = sum(v['x'] for v in vertices) / len(vertices)
    cy = sum(v['y'] for v in vertices) / len(vertices)
    
    def angle_from_centroid(v):
        return math.atan2(v['y'] - cy, v['x'] - cx)
    
    sorted_verts = sorted(vertices, key=angle_from_centroid)
    return sorted_verts

def evaluate_objective(vertices, objective_expr, mode='Maximize'):
    """
    Evaluates Z = ax + by for each vertex.
    Returns list with 'value' added, and identifies optimal.
    """
    a, b, c = objective_expr # c is usually 0 for linear prog, but we handle it
    
    if not vertices:
        return []

    results = []
    for v in vertices:
        val = a * v['x'] + b * v['y'] + c
        # Clean small epsilons
        if abs(val) < 1e-9: val = 0.0
        
        v_copy = v.copy()
        v_copy['value'] = val
        results.append(v_copy)
    
    # Determine optimal
    vals = [r['value'] for r in results]
    if not vals:
        return results

    if mode == 'Maximize':
        best_val = max(vals)
    else:
        best_val = min(vals)
    
    # Mark optimal
    for r in results:
        r['is_optimal'] = math.isclose(r['value'], best_val, abs_tol=1e-7)

    return results
