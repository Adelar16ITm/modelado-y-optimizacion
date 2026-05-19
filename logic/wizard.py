def wizard_to_text(state):
    """
    Converts the Wizard State (dict) into string format for the editor.
    State structure:
    {
        'variables': [{'name': 'x', 'lb': 0, 'ub': None, 'type': 'Continuous'}],
        'goal': 'Maximize',
        'objective_coeffs': {'x': 10, 'y': 5},
        'constraints': [
             {'lhs': {'x': 1, 'y': 1}, 'sign': '<=', 'rhs': 100, 'name': 'Limit'}
        ]
    }
    """
    
    # 1. Objective
    # format: 10x + 5y
    terms = []
    for var, coef in state['objective_coeffs'].items():
        if coef == 0: continue
        sign = "+" if coef >= 0 else "-"
        val = abs(coef)
        # Simplify 1x -> x
        val_str = f"{val}" if val != 1 else ""
        if not terms and coef > 0: # First term positive
             terms.append(f"{val_str}{var}")
        else:
             terms.append(f"{sign} {val_str}{var}")
             
    obj_str = " ".join(terms).strip()
    if obj_str.startswith("+ "): obj_str = obj_str[2:]
    
    # 2. Constraints
    const_lines = []
    for c in state['constraints']:
        # LHS
        lhs_terms = []
        for var, coef in c['lhs'].items():
            if coef == 0: continue
            sign = "+" if coef >= 0 else "-"
            val = abs(coef)
            val_str = f"{val}" if val != 1 else ""
            
            if not lhs_terms and coef > 0:
                 lhs_terms.append(f"{val_str}{var}")
            else:
                 lhs_terms.append(f"{sign} {val_str}{var}")
        
        lhs_str = " ".join(lhs_terms).strip()
        if lhs_str.startswith("+ "): lhs_str = lhs_str[2:]
        if not lhs_str: lhs_str = "0"
        
        # Line: x + y <= 100 # Name
        line = f"{lhs_str} {c['sign']} {c['rhs']}"
        if c.get('name'):
            line += f"  # {c['name']}"
        const_lines.append(line)
        
    return obj_str, "\n".join(const_lines)
