import re
import numpy as np

def parse_fraction(s):
    """Parses a string like '1/2', '0.5', '-3/4' into a float."""
    s = s.strip()
    if '/' in s:
        try:
            num, den = s.split('/')
            return float(num) / float(den)
        except ValueError:
            return 1.0 # Fallback
    return float(s)

def parse_term(term):
    """
    Parses a single term like "-3x", "x", "2.5y", "x[1,2]", "x_ij".
    Returns (coefficient, variable_name).
    """
    term = term.strip()
    if not term:
        return 0.0, None
    
    # Handle signs explicitly if attached
    sign = 1.0
    if term.startswith('-'):
        sign = -1.0
        term = term[1:]
    elif term.startswith('+'):
        term = term[1:]
        
    term = term.strip()
    
    # Regex to separate coeff from var
    # Supports: x, x1, x_1, x[1,2], x_ij
    # Structure: [number*] [variable]
    
    # Check if pure number
    try:
        return sign * parse_fraction(term), None # Constant
    except:
        pass

    # Split coeff and var
    # Look for the first letter or strictly var start
    match = re.search(r'[a-zA-Z]', term)
    if not match:
        # Maybe just number? handled above theoretically
        return sign * float(term), None
        
    idx = match.start()
    coeff_part = term[:idx].strip()
    var_part = term[idx:].strip()
    
    # Parse coefficient
    coeff = 1.0
    if coeff_part == '':
        coeff = 1.0
    elif coeff_part == '*': # explicit multiplication 2*x
        coeff = 1.0 # unlikely to be just *
    else:
        # Handle "2*" case
        if coeff_part.endswith('*'):
            coeff_part = coeff_part[:-1]
        coeff = parse_fraction(coeff_part)
        
    return sign * coeff, var_part

def parse_full_input(objective_str, constraints_str, bounds_default=True):
    """
    Parses the entire problem input.
    Returns standard matrices for SciPy.
    """
    # 1. Parse Objective
    # Normalize
    obj_clean = objective_str.replace(" ", "")
    # Add spaces around operators for easier splitting (simple heuristic)
    # Better: usage of regex split or Term matching
    
    # Strategy: Split by + or - but keep delimiters.
    # Hacky split: replace - with +-, then split by +.
    
    def split_terms(expr):
        expr = expr.replace(" ", "")
        expr = expr.replace("-", "+-")
        if expr.startswith("+-"): 
            expr = expr[1:] # -x -> +-x -> (split) -> -x
            # Wait, if start is negative: "-3x" -> "+-3x". Split -> ["", "-3x"]
        
        terms = expr.split('+')
        return [t for t in terms if t.strip()]

    # Collect all unique variables first to build index
    all_vars = set()
    
    obj_terms_raw = split_terms(objective_str)
    
    # Parse constraints lines
    cons_lines = [line.strip() for line in constraints_str.split('\n') if line.strip()]
    parsed_constraints = []
    
    for line in cons_lines:
        line = line.split('#')[0].strip()
        if not line: continue
        
        # Normalize <=, >=, =
        line = line.replace("<=", "≤").replace(">=", "≥").replace("=<", "≤").replace("=>", "≥")
        
        if "≤" in line:
            parts = line.split("≤")
            op = "<="
        elif "≥" in line:
            parts = line.split("≥")
            op = ">="
        elif "=" in line:
            parts = line.split("=")
            op = "="
        else:
            # Maybe strict < or >? Treat as weak for LP
            if "<" in line: parts, op = line.split("<"), "<="
            elif ">" in line: parts, op = line.split(">"), ">="
            else: return {'errors': [f"Invalid operator in line: {line}"]}
            
        lhs_str, rhs_str = parts[0], parts[1]
        
        # Parse RHS (Constant)
        try:
            limit = parse_fraction(rhs_str)
        except:
            return {'errors': [f"Invalid RHS in line: {line}"]}
            
        # Parse LHS Terms
        term_list = split_terms(lhs_str)
        parsed_c = {'terms': [], 'limit': limit, 'op': op, 'original': line}
        
        for t in term_list:
            c, v = parse_term(t)
            if v:
                all_vars.add(v)
                parsed_c['terms'].append((c, v))
            else:
                # Constant on LHS -> move to RHS
                parsed_c['limit'] -= c
                
        parsed_constraints.append(parsed_c)

    # Parse Objective Vars
    parsed_obj = []
    obj_const = 0.0
    for t in obj_terms_raw:
        c, v = parse_term(t)
        if v:
            all_vars.add(v)
            parsed_obj.append((c, v))
        else:
            obj_const += c
            
    # Sort vars for consistency (x, y, z... or x1, x2...)
    # Custom sort: Length then alpha? or just alpha?
    # x1 before x10
    sorted_vars = sorted(list(all_vars), key=lambda s: (len(s), s))
    var_map = {v: i for i, v in enumerate(sorted_vars)}
    n_vars = len(sorted_vars)
    
    # Build Matrices
    # SciPy minimize: c @ x
    # A_ub @ x <= b_ub
    # A_eq @ x == b_eq
    
    c = np.zeros(n_vars)
    for coeff, v in parsed_obj:
        c[var_map[v]] += coeff
        
    A_ub = []
    b_ub = []
    A_eq = []
    b_eq = []
    
    constraints_meta = [] # To map result back to constraints
    
    for pc in parsed_constraints:
        row = np.zeros(n_vars)
        for coeff, v in pc['terms']:
            row[var_map[v]] += coeff
            
        if pc['op'] == '<=':
            A_ub.append(row)
            b_ub.append(pc['limit'])
            constraints_meta.append({'type': '<=', 'original': pc['original'], 'coeffs': row.tolist(), 'limit': pc['limit']})
        elif pc['op'] == '>=':
            # Convert to <=: -row <= -limit
            A_ub.append(-row)
            b_ub.append(-pc['limit'])
            constraints_meta.append({'type': '>=', 'original': pc['original'], 'coeffs': row.tolist(), 'limit': pc['limit']})
        elif pc['op'] == '=':
            A_eq.append(row)
            b_eq.append(pc['limit'])
            constraints_meta.append({'type': '=', 'original': pc['original'], 'coeffs': row.tolist(), 'limit': pc['limit']})
            
    # Bounds calculation
    # If bounds_default is True -> (0, None)
    # If False -> (None, None) (Free variables)
    bounds = [(0, None) if bounds_default else (None, None) for _ in range(n_vars)]
            
    return {
        'c': c.tolist(),
        'obj_const': obj_const,
        'A_ub': [row.tolist() for row in A_ub] if A_ub else [],
        'b_ub': b_ub,
        'A_eq': [row.tolist() for row in A_eq] if A_eq else [],
        'b_eq': b_eq,
        'bounds': bounds,
        'variables': sorted_vars,
        'constraints_meta': constraints_meta,
        'errors': []
    }
