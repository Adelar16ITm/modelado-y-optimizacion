import numpy as np
from scipy.optimize import linprog

def solve_linear_program(parsed_data, goal='Maximize', custom_bounds=None, integer_vars=None):
    """
    Solves the LP/MIP using scipy.optimize.linprog (Highs).
    
    Args:
        parsed_data: Dict from parser.
        goal: 'Maximize' or 'Minimize'
        custom_bounds: Dict {var_name: (min, max)}. Default (0, None).
        integer_vars: List of variable names that must be integer.
    """
    
    # 1. Prepare Objective
    c = np.array(parsed_data['c'], dtype=float).flatten()
    
    if c.size == 0:
        return {
            'status': "Error: No variables found in objective.",
            'success': False,
            'z_optimal': 0.0,
            'point': [],
            'shadow_prices': {},
            'constraints_analysis': []
        }

    if goal == 'Maximize':
        c = -c
        
    # 2. Extract Matrices
    A_ub = parsed_data['A_ub']
    b_ub = parsed_data['b_ub']
    A_eq = parsed_data['A_eq']
    b_eq = parsed_data['b_eq']
    
    # Handle empty constraints
    if A_ub is not None and len(A_ub) == 0: A_ub, b_ub = None, None
    if A_eq is not None and len(A_eq) == 0: A_eq, b_eq = None, None
    
    # 3. Prepare Bounds & Integrality
    variables = parsed_data['variables']
    bounds = []
    integrality = [] # 0=continuous, 1=integer
    
    for i, var in enumerate(variables):
        # Bounds
        if custom_bounds and var in custom_bounds:
            bounds.append(custom_bounds[var])
        else:
             # Use bounds from parser (which respects the Global Non-Neg checkbox)
             # parsed_data['bounds'] is a list aligned with 'variables'
             if 'bounds' in parsed_data and i < len(parsed_data['bounds']):
                 bounds.append(parsed_data['bounds'][i])
             else:
                 bounds.append((0, None)) # Fallback safety
             
        # Integrality
        if integer_vars and var in integer_vars:
            integrality.append(1)
        else:
            integrality.append(0)
    
    # Debugging Output
    # print(f"DEBUG SOLVER: c shape: {c.shape}, integrality: {integrality}")
    
    # 4. Solve
    try:
        # Check if integrality is needed (all 0 -> None)
        int_arg = None
        if any(x == 1 for x in integrality):
            int_arg = np.array(integrality)
            
        res = linprog(
            c, 
            A_ub=A_ub, b_ub=b_ub, 
            A_eq=A_eq, b_eq=b_eq, 
            bounds=bounds, 
            method='highs',
            integrality=int_arg
        )
    except Exception as e:
        print(f"CRITICAL SOLVER ERROR: {e}")
        return {
            'status': f"Solver Crash: {e}",
            'success': False,
            'z_optimal': 0.0,
            'point': [0.0]*len(c),
            'shadow_prices': {},
            'constraints_analysis': []
        }
    
    # 4. Interpret Results
    result_data = {
        'status': res.message,
        'success': res.success,
        'z_optimal': 0.0,
        'point': [],
        'shadow_prices': {}, # Constraint Text -> Price
        'constraints_analysis': [] # Detailed analysis with slacks
    }
    
    if res.success:
        # Recover correct Z sign
        val = res.fun
        if goal == 'Maximize':
            val = -val
        result_data['z_optimal'] = val
        result_data['point'] = res.x.tolist()
        
        # --- SENSITIVITY & SLACKS ---
        
        idx_ub = 0
        idx_eq = 0
        
        # Check if arrays are None or empty logic before using them
        duals_ub = res.ineqlin.marginals if hasattr(res, 'ineqlin') and res.ineqlin is not None else []
        duals_eq = res.eqlin.marginals if hasattr(res, 'eqlin') and res.eqlin is not None else []
        
        # Reduced Costs
        reduced_costs = np.zeros_like(res.x)
        if hasattr(res, 'lower') and hasattr(res.lower, 'marginals'):
             reduced_costs += res.lower.marginals
        if hasattr(res, 'upper') and hasattr(res.upper, 'marginals'):
             reduced_costs -= res.upper.marginals
        
        if goal == 'Maximize':
            reduced_costs = -reduced_costs
            
        result_data['reduced_costs'] = reduced_costs.tolist()

        scale_factor = -1.0 if goal == 'Maximize' else 1.0
        
        # Safely iterate
        cons_meta = parsed_data.get('constraints_meta', [])
        
        for i, meta in enumerate(cons_meta):
            # Calculate Slack / Activity
            lhs_val = np.dot(meta['coeffs'], res.x)
            rhs_val = meta['limit']
            ctype = meta['type']
            
            slack_val = 0.0
            type_label = "Slack"
            is_active = False
            
            if ctype == '<=':
                slack_val = rhs_val - lhs_val
                type_label = "Slack (≤)"
            elif ctype == '>=':
                slack_val = lhs_val - rhs_val 
                type_label = "Surplus (≥)"
            elif ctype == '=':
                slack_val = abs(lhs_val - rhs_val)
                type_label = "Gap (=)"
                
            if abs(slack_val) < 1e-5:
                is_active = True
                
            # Retrieve Shadow Price
            price = 0.0
            if (ctype == '<=' or ctype == '>='):
                # Ensure duals_ub has enough elements
                if idx_ub < len(duals_ub):
                    price = duals_ub[idx_ub] * scale_factor
                    idx_ub += 1
            elif ctype == '=':
                if idx_eq < len(duals_eq):
                    price = duals_eq[idx_eq] * scale_factor
                    idx_eq += 1
            
            result_data['constraints_analysis'].append({
                'Constraint': meta['original'],
                'Type': ctype,
                'LHS': lhs_val,
                'RHS': rhs_val,
                'Limit': rhs_val,
                'Slack Value': slack_val,
                'Slack Type': type_label,
                'Is Active': is_active,
                'Shadow Price': price,
                'id': i # consistent index for Plotting highlighting
            })
            
    return result_data
