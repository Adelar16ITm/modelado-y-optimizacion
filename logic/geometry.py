import numpy as np
import scipy.spatial

def get_intersections_and_path(parsed_data):
    """
    Finds vertices for 2D plotting.
    1. Collects all lines (user constraints + bounds).
    2. Computes all intersections.
    3. Filters feasible points.
    4. Computes convex hull / ordered polygon.
    """
    
    # Needs to rebuild the lines effectively
    # Form: a*x + b*y = limit (conceptually)
    
    lines = []
    
    # 1. User Constraints
    for meta in parsed_data['constraints_meta']:
        # meta['coeffs'] is [a, b] or [a]
        coeffs = meta['coeffs']
        a = coeffs[0] if len(coeffs) > 0 else 0
        b = coeffs[1] if len(coeffs) > 1 else 0
        
        lines.append({
            'a': a, 
            'b': b, 
            'c': meta['limit'], 
            'type': meta['type'],
            'label': meta['original']
        })
            
    # 2. Bounds
    # parsed_data['bounds'] is list of (min, max) for x and y
    # x bounds
    xb = parsed_data['bounds'][0]
    if xb[0] is not None:
        lines.append({'a': 1, 'b': 0, 'c': xb[0], 'type': '>=', 'label': 'x >= lower'})
    if xb[1] is not None:
        lines.append({'a': 1, 'b': 0, 'c': xb[1], 'type': '<=', 'label': 'x <= upper'})
        
    # y bounds
    yb = parsed_data['bounds'][1]
    if yb[0] is not None:
        lines.append({'a': 0, 'b': 1, 'c': yb[0], 'type': '>=', 'label': 'y >= lower'})
    if yb[1] is not None:
        lines.append({'a': 0, 'b': 1, 'c': yb[1], 'type': '<=', 'label': 'y <= upper'})
    
    points = []
    
    # Intersect all pairs
    for i in range(len(lines)):
        for j in range(i+1, len(lines)):
            l1, l2 = lines[i], lines[j]
            
            # Cramer's rule / Det
            det = l1['a']*l2['b'] - l2['a']*l1['b']
            if abs(det) < 1e-9:
                continue # Parallel
                
            x = (l1['c']*l2['b'] - l2['c']*l1['b']) / det
            y = (l1['a']*l2['c'] - l2['a']*l1['c']) / det
            
            points.append((x, y, [l1['label'], l2['label']]))
            
    # Filter Feasible
    feasible_verts = []
    tolerance = 1e-6
    
    active_lines_map = {} # (x,y) -> list of lines
    
    for px, py, parent_lines in points:
        is_feas = True
        
        # Check against user constraints
        for meta in parsed_data['constraints_meta']:
            val = meta['coeffs'][0]*px + meta['coeffs'][1]*py
            lim = meta['limit']
            op = meta['type']
            
            if op == '<=':
                if val > lim + tolerance: is_feas = False
            elif op == '>=':
                if val < lim - tolerance: is_feas = False
            elif op == '=':
                if abs(val - lim) > tolerance: is_feas = False
                
            if not is_feas: break
            
        # Check bounds
        if is_feas:
            bx, by = parsed_data['bounds']
            # x
            if bx[0] is not None and px < bx[0] - tolerance: is_feas = False
            if bx[1] is not None and px > bx[1] + tolerance: is_feas = False
            # y
            if by[0] is not None and py < by[0] - tolerance: is_feas = False
            if by[1] is not None and py > by[1] + tolerance: is_feas = False
            
        if is_feas:
            # Check dupes
            found_dupe = False
            for exist in feasible_verts:
                ex, ey = exist['x'], exist['y']
                if abs(px-ex) < 1e-7 and abs(py-ey) < 1e-7:
                    exist['lines'] = list(set(exist['lines'] + parent_lines))
                    found_dupe = True
                    break
            
            if not found_dupe:
                feasible_verts.append({'x': px, 'y': py, 'lines': parent_lines})

    # Order vertices (Convex Hull)
    # Simple angular sort around centroid
    if len(feasible_verts) > 2:
        cx = sum(v['x'] for v in feasible_verts)/len(feasible_verts)
        cy = sum(v['y'] for v in feasible_verts)/len(feasible_verts)
        feasible_verts.sort(key=lambda v: np.arctan2(v['y'] - cy, v['x'] - cx))
        
    return feasible_verts
