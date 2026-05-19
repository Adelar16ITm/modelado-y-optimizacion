"""
duality.py  –  Primal → Dual LP conversion and solver.

Rules implemented (S.O.B. "Tabla Mágica" from Duality PDF):

  PRIMAL MAX  →  DUAL MIN
  ────────────────────────────────────────────────────────
  Primal constraint i  <=   =>  dual variable yi  >= 0
  Primal constraint i  =    =>  dual variable yi  free (nrs)
  Primal constraint i  >=   =>  dual variable yi  <= 0

  Primal variable xj   >= 0 =>  dual constraint j  >=
  Primal variable xj   free =>  dual constraint j  =
  Primal variable xj   <= 0 =>  dual constraint j  <=

  For PRIMAL MIN: all signs flip (dual is MAX).
"""

import numpy as np
from scipy.optimize import linprog


def _fmt(v):
    """Clean numeric formatter."""
    if abs(v) < 1e-9:
        return "0"
    if abs(v - round(v)) < 1e-9:
        return str(int(round(v)))
    return f"{v:.4g}"


def build_dual(c, A, b, constraint_types, optimization_type, var_names):
    """
    Build the dual of an LP problem and solve it.

    Parameters
    ----------
    c : list[float]        primal objective coefficients (original sign for max)
    A : list[list[float]]  primal constraint matrix  (m x n)
    b : list[float]        primal RHS values
    constraint_types : list[str]   '<=' | '>=' | '=' per constraint
    optimization_type : str        'max' | 'min'
    var_names : list[str]          ['x1', 'x2', ...]

    Returns
    -------
    dict with all information needed to display and solve the dual.
    """
    c_vec = np.array(c, dtype=float)
    A_mat = np.array(A, dtype=float)
    b_vec = np.array(b, dtype=float)
    m, n  = A_mat.shape

    is_max    = (optimization_type == 'max')
    dual_type = 'min' if is_max else 'max'

    # ── Dual variable names & sign restrictions ──────────────────────────────
    dual_var_names = [f'y{i+1}' for i in range(m)]
    dual_var_restr = []   # '>=0' | '<=0' | 'nrs'
    for ct in constraint_types:
        if is_max:
            if ct == '<=':   dual_var_restr.append('>=0')
            elif ct == '=':  dual_var_restr.append('nrs')
            else:            dual_var_restr.append('<=0')
        else:
            if ct == '>=':   dual_var_restr.append('>=0')
            elif ct == '=':  dual_var_restr.append('nrs')
            else:            dual_var_restr.append('<=0')

    # ── Dual constraint types (one per primal variable – assume xj >= 0) ────
    dual_ct = ['>=' if is_max else '<=' for _ in range(n)]

    # ── Dual matrices ────────────────────────────────────────────────────────
    # Dual objective:     W  = b^T y      (coefficients = primal b)
    # Dual constraints:   A^T y  <op>  c  (matrix = A^T, rhs = primal c)
    dual_c = b_vec.tolist()       # objective coefficients
    dual_A = A_mat.T              # shape (n, m)
    dual_b = c_vec.tolist()       # RHS

    # ── Human-readable strings ───────────────────────────────────────────────
    obj_terms = ' + '.join(
        f"{_fmt(coef)}{yn}" for coef, yn in zip(dual_c, dual_var_names)
    )
    dual_obj_str = f"{dual_type.capitalize()} W = {obj_terms}"

    dual_constraints_str = []
    for j in range(n):
        parts = [
            f"{_fmt(dual_A[j, i])}{dual_var_names[i]}"
            for i in range(m) if abs(dual_A[j, i]) > 1e-9
        ]
        lhs = ' + '.join(parts) if parts else '0'
        dual_constraints_str.append(
            f"{lhs}  {dual_ct[j]}  {_fmt(dual_b[j])}   [{var_names[j]}]"
        )

    dual_var_restr_str = []
    for yn, r in zip(dual_var_names, dual_var_restr):
        label = {'>=0': '≥ 0', '<=0': '≤ 0', 'nrs': 'irrestricta (nrs)'}[r]
        dual_var_restr_str.append(f"{yn} {label}")

    # ── SOB conversion table rows ────────────────────────────────────────────
    sob_rows = []
    for i in range(m):
        ct = constraint_types[i]
        r  = dual_var_restr[i]
        label = {'>=0': '≥ 0', '<=0': '≤ 0', 'nrs': 'irrestricta'}[r]
        sob_rows.append({
            'Primal': f"Restricción R{i+1}  ({ct})",
            'Dual':   f"{dual_var_names[i]}  {label}",
        })
    for j in range(n):
        sob_rows.append({
            'Primal': f"Variable {var_names[j]}  (≥ 0)",
            'Dual':   f"Restricción DC{j+1}  ({dual_ct[j]})",
        })

    # ── Solve the dual ───────────────────────────────────────────────────────
    dual_solution = _solve_dual(
        dual_c, dual_A.tolist(), dual_b, dual_ct, dual_var_restr, dual_type
    )

    return {
        'primal_type':           optimization_type,
        'dual_type':             dual_type,
        'dual_obj_str':          dual_obj_str,
        'dual_c':                dual_c,
        'dual_A':                dual_A.tolist(),
        'dual_b':                dual_b,
        'dual_constraint_types': dual_ct,
        'dual_var_names':        dual_var_names,
        'dual_var_restr':        dual_var_restr,
        'dual_var_restr_str':    dual_var_restr_str,
        'dual_constraints_str':  dual_constraints_str,
        'sob_rows':              sob_rows,
        'dual_solution':         dual_solution,
    }


def _solve_dual(dual_c, dual_A, dual_b, dual_ct, dual_var_restr, dual_obj_type):
    """Solve the dual LP with scipy linprog (always minimises internally)."""
    c_arr  = np.array(dual_c, dtype=float)
    A_arr  = np.array(dual_A, dtype=float)
    b_arr  = np.array(dual_b, dtype=float)

    obj = -c_arr if dual_obj_type == 'max' else c_arr

    A_ub, b_ub, A_eq, b_eq = [], [], [], []
    for j, ct in enumerate(dual_ct):
        row = A_arr[j]
        rhs = b_arr[j]
        if ct == '<=':
            A_ub.append(row);   b_ub.append(rhs)
        elif ct == '>=':
            A_ub.append(-row);  b_ub.append(-rhs)
        else:
            A_eq.append(row);   b_eq.append(rhs)

    bounds = []
    for r in dual_var_restr:
        if r == '>=0':   bounds.append((0, None))
        elif r == '<=0': bounds.append((None, 0))
        else:            bounds.append((None, None))

    try:
        res = linprog(
            obj,
            A_ub=np.array(A_ub) if A_ub else None,
            b_ub=np.array(b_ub) if b_ub else None,
            A_eq=np.array(A_eq) if A_eq else None,
            b_eq=np.array(b_eq) if b_eq else None,
            bounds=bounds,
            method='highs',
        )
        if res.success:
            W = (-res.fun) if dual_obj_type == 'max' else res.fun
            return {'success': True, 'W': float(W), 'y': res.x.tolist()}
        return {'success': False, 'message': res.message}
    except Exception as exc:
        return {'success': False, 'message': str(exc)}


def solve_dual_simplex(dual_info):
    """
    Run the Simplex Tutor on the dual problem.

    Parameters
    ----------
    dual_info : dict   returned by build_dual()

    Returns
    -------
    dict with keys:
        'iterations' : list[dict]  – simplex sequence rows (same format as SimplexTutor)
        'error'      : str | None  – error message if failed
    """
    try:
        import sys, os
        # Make sure the modules folder is importable
        _here = os.path.dirname(os.path.abspath(__file__))
        if _here not in sys.path:
            sys.path.insert(0, _here)
        from simplex_tutor import SimplexTutor

        dual_c   = dual_info['dual_c']
        dual_A   = dual_info['dual_A']
        dual_b   = dual_info['dual_b']
        dual_ct  = dual_info['dual_constraint_types']
        dual_opt = dual_info['dual_type']      # 'min' or 'max'
        y_names  = dual_info['dual_var_names'] # ['y1', 'y2', ...]

        tutor = SimplexTutor(
            c=dual_c,
            A=dual_A,
            b=dual_b,
            constraint_types=dual_ct,
            optimization_type=dual_opt,
            var_names=y_names,
        )
        iterations = tutor.run_to_completion()
        return {'iterations': iterations, 'error': None}

    except Exception as exc:
        return {'iterations': [], 'error': str(exc)}



def complementary_slackness(primal_x, primal_A, primal_b, primal_ct,
                             dual_y, dual_A, dual_b, dual_ct):
    """
    Compute complementary slackness for display.
    Returns list of row-dicts with binding status.
    """
    m = len(primal_b)
    n = len(primal_x)
    rows = []

    # Primal slacks
    for i in range(m):
        lhs  = sum(primal_A[i][j] * primal_x[j] for j in range(n))
        ct   = primal_ct[i]
        slack = (primal_b[i] - lhs) if ct == '<=' else (lhs - primal_b[i]) if ct == '>=' else 0.0
        yi   = dual_y[i] if i < len(dual_y) else 0.0
        prod = abs(yi * slack)
        rows.append({
            'Tipo':               'Primal',
            'Restricción':        f'R{i+1}  ({ct})',
            'Holgura / Exceso':   round(slack, 6),
            'Var. Dual':          f'y{i+1} = {_fmt(yi)}',
            'yi·slack = 0 ?':     '✅' if prod < 1e-5 else f'❌ ({prod:.4f})',
        })

    # Dual slacks
    for j in range(n):
        lhs  = sum(dual_A[j][i] * dual_y[i] for i in range(m))
        ct   = dual_ct[j]
        slack = (dual_b[j] - lhs) if ct == '<=' else (lhs - dual_b[j]) if ct == '>=' else 0.0
        xj   = primal_x[j]
        prod = abs(xj * slack)
        rows.append({
            'Tipo':               'Dual',
            'Restricción':        f'DC{j+1}  ({ct})',
            'Holgura / Exceso':   round(slack, 6),
            'Var. Dual':          f'x{j+1} = {_fmt(xj)}',
            'yi·slack = 0 ?':     '✅' if prod < 1e-5 else f'❌ ({prod:.4f})',
        })

    return rows
