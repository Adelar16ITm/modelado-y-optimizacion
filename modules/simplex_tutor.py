import numpy as np
import pandas as pd
from fractions import Fraction


# ──────────────────────────────────────────────────────────────────────────────
# MExpr: Representación simbólica de   aM + b
# ──────────────────────────────────────────────────────────────────────────────

class MExpr:
    """
    Representa un valor de la forma  a*M + b  donde M es la constante Gran-M.

    Las comparaciones son SIMBÓLICAS:
      - primero se compara el coeficiente 'a' de M,
      - en caso de empate se compara el término independiente 'b'.

    El valor numérico (float) está disponible vía float(expr) para operaciones
    del tableau de pivoteo (que siguen siendo numéricas).
    """

    BIG_M = 1_000_000.0  # valor numérico usado solo para convertir a float

    def __init__(self, a=0.0, b=0.0):
        self.a = float(a)  # coeficiente de M
        self.b = float(b)  # término independiente

    # ── Aritmética ────────────────────────────────────────────────────────────

    def __add__(self, other):
        if isinstance(other, MExpr):
            return MExpr(self.a + other.a, self.b + other.b)
        return MExpr(self.a, self.b + float(other))

    def __radd__(self, other):
        return self.__add__(other)

    def __sub__(self, other):
        if isinstance(other, MExpr):
            return MExpr(self.a - other.a, self.b - other.b)
        return MExpr(self.a, self.b - float(other))

    def __rsub__(self, other):
        return MExpr(-self.a, float(other) - self.b)

    def __mul__(self, other):
        if isinstance(other, MExpr):
            # M*M no se soporta en simplex estándar
            if abs(self.a) > 1e-12 and abs(other.a) > 1e-12:
                raise ValueError("No se puede multiplicar M*M en simplex estándar")
            # one of them is purely real
            if abs(self.a) < 1e-12:
                return MExpr(other.a * self.b, other.b * self.b)
            return MExpr(self.a * other.b, self.b * other.b)
        f = float(other)
        return MExpr(self.a * f, self.b * f)

    def __rmul__(self, other):
        return self.__mul__(other)

    def __neg__(self):
        return MExpr(-self.a, -self.b)

    def __truediv__(self, other):
        f = float(other)
        return MExpr(self.a / f, self.b / f)

    # ── Comparación simbólica ─────────────────────────────────────────────────

    def _cmp(self, other):
        """Devuelve -1, 0, 1 según la comparación simbólica."""
        if isinstance(other, MExpr):
            da = self.a - other.a
            db = self.b - other.b
        else:
            da = self.a
            db = self.b - float(other)
        TOL = 1e-9
        if abs(da) > TOL:
            return -1 if da < 0 else 1
        if abs(db) > TOL:
            return -1 if db < 0 else 1
        return 0

    def __lt__(self, other):  return self._cmp(other) < 0
    def __le__(self, other):  return self._cmp(other) <= 0
    def __gt__(self, other):  return self._cmp(other) > 0
    def __ge__(self, other):  return self._cmp(other) >= 0
    def __eq__(self, other):  return self._cmp(other) == 0

    # ── Conversión numérica ───────────────────────────────────────────────────

    def __float__(self):
        return self.a * self.BIG_M + self.b

    def __abs__(self):
        f = float(self)
        return abs(f)

    # ── Representación textual ────────────────────────────────────────────────

    def __str__(self):
        return _fmt_mexpr(self)

    def __repr__(self):
        return f"MExpr(a={self.a}, b={self.b})"

    def is_zero(self, tol=1e-9):
        return abs(self.a) < tol and abs(self.b) < tol

    def is_positive(self, tol=1e-9):
        return self._cmp(0) > 0

    def is_negative(self, tol=1e-9):
        return self._cmp(0) < 0


def _fmt_coeff(a):
    """Formatea el coeficiente numérico 'a' como fracción reducida si es simple."""
    if abs(a - round(a)) < 1e-9:
        return str(int(round(a)))
    try:
        frac = Fraction(a).limit_denominator(64)
        if abs(float(frac) - a) < 1e-9:
            return str(frac)          # e.g. "1/2", "3/4"
    except Exception:
        pass
    return f"{a:.4g}"


def _fmt_mexpr(expr):
    """
    Formatea un MExpr como string legible:
      ( 1, 0) → 'M'
      (-1, 0) → '-M'
      (1/2, 4) → 'M/2 + 4'
      (-1/2, 4) → '-M/2 + 4'
      (2, -3) → '2M - 3'
      (0, 5)  → '5'
      (0, 0)  → '0'
    """
    a, b = expr.a, expr.b
    TOL = 1e-9

    has_M = abs(a) > TOL
    has_b = abs(b) > TOL

    if not has_M and not has_b:
        return "0"

    # ── M part ────────────────────────────────────────────────────────────────
    if has_M:
        a_abs = abs(a)
        sign_M = "-" if a < 0 else ""

        if abs(a_abs - 1.0) < TOL:
            m_str = f"{sign_M}M"
        else:
            # try to express as fraction  n/d·M  (displayed as nM/d)
            try:
                frac = Fraction(a_abs).limit_denominator(64)
                if abs(float(frac) - a_abs) < TOL:
                    n, d = frac.numerator, frac.denominator
                    if d == 1:
                        m_str = f"{sign_M}{n}M"
                    else:
                        m_str = f"{sign_M}{n}M/{d}" if n != 1 else f"{sign_M}M/{d}"
                else:
                    m_str = f"{sign_M}{a_abs:.4g}M"
            except Exception:
                m_str = f"{sign_M}{a_abs:.4g}M"
    else:
        m_str = ""

    # ── b part ────────────────────────────────────────────────────────────────
    if has_b:
        b_fmt = _fmt_coeff(abs(b))
        if has_M:
            sign_b = " + " if b > 0 else " - "
            b_str = f"{sign_b}{b_fmt}"
        else:
            b_str = f"-{b_fmt}" if b < 0 else b_fmt
    else:
        b_str = ""

    return m_str + b_str


def _to_mexpr(v):
    """Convierte un float o MExpr a MExpr."""
    if isinstance(v, MExpr):
        return v
    return MExpr(0.0, float(v))


# ──────────────────────────────────────────────────────────────────────────────
# SimplexTutor
# ──────────────────────────────────────────────────────────────────────────────

class SimplexTutor:
    """
    Step-by-step Simplex Method tutor following the textbook format:
    - Tableau with columns: CB | Basic Var | x1...xn | s1...sm | RHS
    - Bottom rows: zj and cj - zj (net evaluation row / reduced costs)
    - Max: enter variable with highest positive (cj - zj); tie → leftmost
    - Min: enter variable with most negative (cj - zj); tie → leftmost
    - Leaving variable determined by minimum positive ratio test (RHS / pivot col)

    Big-M variables are tracked symbolically as MExpr(a, b) = aM + b.
    The tableau matrix T stays as numpy float for numerical stability.
    """

    def __init__(self, c, A, b, constraint_types=None, optimization_type='max',
                 var_names=None, slack_names=None):
        """
        Parameters
        ----------
        c                : list of objective coefficients for decision variables
        A                : 2D list of constraint LHS coefficients
        b                : list of RHS values (must be >= 0)
        constraint_types : list of '<=', '>=', '=' per constraint (default all '<=')
        optimization_type: 'max' or 'min'
        var_names        : names for decision variables (default x1, x2, ...)
        slack_names      : override slack/surplus/artificial names (optional)
        """
        self.c_orig = np.array(c, dtype=float)
        self.A_orig = np.array(A, dtype=float)
        self.b_orig = np.array(b, dtype=float)
        self.optimization_type = optimization_type.lower()
        self.num_vars = len(c)
        self.num_constraints = len(b)

        if constraint_types is None:
            constraint_types = ['<='] * self.num_constraints
        self.constraint_types = constraint_types

        # --- Variable names ---
        if var_names is None:
            var_names = [f"x{i+1}" for i in range(self.num_vars)]
        self.var_names = var_names

        # --- Build augmented tableau with slacks / surplus / artificials ---
        # <=  → add slack  s_i  (coefficient +1)
        # >=  → add surplus s_i (coefficient -1) + artificial a_i (coefficient +1)
        # =   → add artificial a_i (coefficient +1)
        #
        # Column order (textbook convention):
        #   [decision vars | slacks/surpluses | artificials]
        # Two passes ensure artificials are never interleaved with slacks.

        # M cost for artificials: -M for max, +M for min
        def _M_cost():
            if self.optimization_type == 'max':
                return MExpr(-1, 0)   # -M
            else:
                return MExpr(+1, 0)   # +M

        # ── Pass 0: count slacks and artificials to determine column offsets ──
        num_slacks = sum(
            1 if ct == '<=' else (2 if ct == '>=' else 0)
            for ct in constraint_types
        )
        # Only surpluses count as slacks; '=' has no slack
        # Re-count correctly: '<=' → 1 slack, '>=' → 1 surplus, '=' → 0 slacks
        num_slacks = sum(1 for ct in constraint_types if ct in ('<=', '>='))
        num_artificials = sum(1 for ct in constraint_types if ct in ('>=', '='))

        slack_col_start       = self.num_vars
        artificial_col_start  = self.num_vars + num_slacks
        total_extra           = num_slacks + num_artificials

        # ── Pass 1: collect per-constraint slack/surplus info ─────────────────
        # slack_meta[i] entries for constraint i: (col, name, coeff)
        # artificial_meta[i] entries for constraint i: (col, name, coeff) or []
        slack_meta = []
        artificial_meta = []

        s_count = 0
        a_count = 0
        initial_basis = []
        extra_names_slacks = []
        extra_names_artificials = []
        cj_slacks = []
        cj_artificials = []
        slack_info = []  # per-constraint list of (col, name, coeff) — used to build T

        for i, ctype in enumerate(constraint_types):
            s_entries = []
            a_entries = []

            if ctype == '<=':
                s_count += 1
                col  = slack_col_start + (s_count - 1)
                name = f"s{s_count}"
                s_entries.append((col, name, +1))
                extra_names_slacks.append(name)
                cj_slacks.append(MExpr(0, 0))
                initial_basis.append((i, col, name))

            elif ctype == '>=':
                # surplus
                s_count += 1
                s_col  = slack_col_start + (s_count - 1)
                s_name = f"s{s_count}"
                s_entries.append((s_col, s_name, -1))
                extra_names_slacks.append(s_name)
                cj_slacks.append(MExpr(0, 0))
                # artificial
                a_count += 1
                a_col  = artificial_col_start + (a_count - 1)
                a_name = f"a{a_count}"
                a_entries.append((a_col, a_name, +1))
                extra_names_artificials.append(a_name)
                cj_artificials.append(_M_cost())
                initial_basis.append((i, a_col, a_name))

            elif ctype == '=':
                # artificial only (no slack)
                a_count += 1
                a_col  = artificial_col_start + (a_count - 1)
                a_name = f"a{a_count}"
                a_entries.append((a_col, a_name, +1))
                extra_names_artificials.append(a_name)
                cj_artificials.append(_M_cost())
                initial_basis.append((i, a_col, a_name))

            slack_info.append(s_entries + a_entries)

        # ── Assemble extra_names and cj_sym in the correct column order ───────
        # Order: slacks first, then artificials
        extra_names  = extra_names_slacks + extra_names_artificials
        extra_c_sym  = cj_slacks         + cj_artificials

        self.total_vars = self.num_vars + total_extra
        self.extra_names = extra_names
        self.all_var_names = self.var_names + extra_names

        # Symbolic objective coefficients (MExpr for all variables)
        self.cj_sym = [MExpr(0, float(v)) for v in self.c_orig] + extra_c_sym

        # Numeric cj (for backward compatibility / numerical operations)
        self.cj = np.array([float(v) for v in self.cj_sym], dtype=float)

        # Build full tableau matrix: num_constraints × total_vars+1 (last col = RHS)
        T = np.zeros((self.num_constraints, self.total_vars + 1))
        T[:, :self.num_vars] = self.A_orig
        for i, info_list in enumerate(slack_info):
            for (col, name, coeff) in info_list:
                T[i, col] = coeff
        T[:, -1] = self.b_orig
        self.T = T

        # Basis tracking
        self.initial_basis_cols = [col for (_, col, _) in initial_basis]
        self.basis_cols = list(self.initial_basis_cols)
        self.basis_names = [name for (_, _, name) in initial_basis]

        # Step log
        self.step_log = []
        self.iteration = 0
        self.status = "Initialized"
        self.last_pivot_info = None

    # ------------------------------------------------------------------
    # Core computations
    # ------------------------------------------------------------------

    def _compute_zj(self):
        """zj[j] = sum over basic rows of (CB_i * T[i, j])  — NUMERIC"""
        CB = np.array([self.cj[col] for col in self.basis_cols])
        zj = np.zeros(self.total_vars + 1)
        for j in range(self.total_vars + 1):
            zj[j] = float(CB @ self.T[:, j])
        return zj

    def _compute_cj_zj(self, zj):
        """cj - zj — NUMERIC (kept for backward compat / numerical pivot)"""
        cj_zj = np.zeros(self.total_vars)
        for j in range(self.total_vars):
            cj_zj[j] = self.cj[j] - zj[j]
        return cj_zj

    # ── Symbolic versions ─────────────────────────────────────────────────────

    def _compute_zj_sym(self):
        """
        zj_sym[j] = Σ_i CB_sym[i] * T[i, j]  — returns list of MExpr.
        The RHS (last column) is also included as index total_vars.
        """
        CB_sym = [self.cj_sym[col] for col in self.basis_cols]
        zj_sym = []
        for j in range(self.total_vars + 1):
            acc = MExpr(0, 0)
            for i in range(self.num_constraints):
                t_ij = float(self.T[i, j])
                if abs(t_ij) < 1e-12:
                    continue
                acc = acc + CB_sym[i] * t_ij
            zj_sym.append(acc)
        return zj_sym

    def _compute_cj_zj_sym(self, zj_sym):
        """cj_sym - zj_sym for every variable column — returns list of MExpr."""
        return [self.cj_sym[j] - zj_sym[j] for j in range(self.total_vars)]

    # ── Entering variable (symbolic comparison) ───────────────────────────────

    def _select_entering_sym(self, cj_zj_sym):
        """
        Select entering variable using symbolic comparison of MExpr values.
          Max: most positive cj-zj  (compare MExpr; tie → leftmost)
          Min: most negative cj-zj  (compare MExpr; tie → leftmost)
        Returns column index or None if optimal.
        """
        if self.optimization_type == 'max':
            best = MExpr(0, 1e-8)   # threshold > 0 symbolically
            entering_col = None
            for j in range(self.total_vars):
                v = cj_zj_sym[j]
                if v > best:
                    best = v
                    entering_col = j
                elif v == best and entering_col is not None:
                    # Tie: leftmost
                    pass
            return entering_col
        else:  # min
            worst = MExpr(0, -1e-8)   # threshold < 0 symbolically
            entering_col = None
            for j in range(self.total_vars):
                v = cj_zj_sym[j]
                if v < worst:
                    worst = v
                    entering_col = j
                elif v == worst and entering_col is not None:
                    pass
            return entering_col

    def _select_entering(self, cj_zj):
        """
        Numeric fallback (used in run_to_completion which is purely numeric).
        """
        if self.optimization_type == 'max':
            best_val = np.max(cj_zj)
            if best_val <= 1e-8:
                return None
            candidates = [j for j in range(self.total_vars) if abs(cj_zj[j] - best_val) < 1e-8]
        else:
            best_val = np.min(cj_zj)
            if best_val >= -1e-8:
                return None
            candidates = [j for j in range(self.total_vars) if abs(cj_zj[j] - best_val) < 1e-8]
        return min(candidates)

    def _ratio_test(self, entering_col):
        """
        Minimum ratio test:
          ratio_i = RHS_i / T[i, entering_col]  for T[i, entering_col] > 0
        Returns (row_index, ratio) or None if unbounded.
        """
        rhs = self.T[:, -1]
        col_vals = self.T[:, entering_col]

        min_ratio = float('inf')
        min_row = -1

        for i in range(self.num_constraints):
            if col_vals[i] > 1e-8:
                ratio = rhs[i] / col_vals[i]
                if ratio < min_ratio - 1e-8:
                    min_ratio = ratio
                    min_row = i
                elif abs(ratio - min_ratio) < 1e-8:
                    if self.basis_cols[i] < self.basis_cols[min_row]:
                        min_row = i

        if min_row == -1:
            return None, float('inf')
        return min_row, min_ratio

    # ------------------------------------------------------------------
    # Step
    # ------------------------------------------------------------------

    def next_step(self):
        """
        Perform one iteration of the Simplex method.
        Returns (continue: bool, message: str, details: dict)
        """
        # Use symbolic computation for display and entering selection
        zj_sym = self._compute_zj_sym()
        cj_zj_sym = self._compute_cj_zj_sym(zj_sym)

        entering_col = self._select_entering_sym(cj_zj_sym)
        if entering_col is None:
            self.status = "Optimal"
            self.last_pivot_info = None
            return False, "✅ Solución óptima encontrada. Todos los cj-zj cumplen el criterio de optimalidad.", {}

        entering_name = self.all_var_names[entering_col]

        # Ratio test
        leaving_row, ratio = self._ratio_test(entering_col)
        if leaving_row is None:
            self.status = "Unbounded"
            self.last_pivot_info = None
            return False, "⚠️ El problema es NO ACOTADO. No hay elementos positivos en la columna pivote.", {}

        leaving_name = self.basis_names[leaving_row]
        pivot_val = self.T[leaving_row, entering_col]

        # Build ratio details for display
        ratios = []
        for i in range(self.num_constraints):
            pv = self.T[i, entering_col]
            rhs_i = self.T[i, -1]
            if pv > 1e-8:
                ratios.append({
                    'row': i,
                    'basis': self.basis_names[i],
                    'rhs': rhs_i,
                    'pivot_col_val': pv,
                    'ratio': rhs_i / pv,
                    'is_min': (i == leaving_row)
                })
            else:
                ratios.append({
                    'row': i,
                    'basis': self.basis_names[i],
                    'rhs': rhs_i,
                    'pivot_col_val': pv,
                    'ratio': None,
                    'is_min': False
                })

        # Save pivot info BEFORE pivoting (for display)
        pivot_info = {
            'iteration': self.iteration + 1,
            'entering_col': entering_col,
            'entering_name': entering_name,
            'entering_cj': str(self.cj_sym[entering_col]),
            'leaving_row': leaving_row,
            'leaving_name': leaving_name,
            'pivot_val': pivot_val,
            'ratios': ratios,
            'opt_direction': self.optimization_type,
        }

        # --- Pivot Operation ---
        self.T[leaving_row, :] /= pivot_val

        for r in range(self.num_constraints):
            if r != leaving_row:
                factor = self.T[r, entering_col]
                if abs(factor) > 1e-12:
                    self.T[r, :] -= factor * self.T[leaving_row, :]

        # Update basis
        self.basis_cols[leaving_row] = entering_col
        self.basis_names[leaving_row] = entering_name

        self.iteration += 1
        self.status = f"Iteración {self.iteration}"
        self.last_pivot_info = pivot_info

        # Format message using symbolic representation
        cj_zj_str = str(cj_zj_sym[entering_col])
        msg = (f"**Itera {self.iteration}:** Entra **{entering_name}** "
               f"(cj-zj = {cj_zj_str}), "
               f"Sale **{leaving_name}** (razón mínima = {ratio:.4g}). "
               f"Elemento pivote = {pivot_val:.4g}.")

        self.step_log.append(msg)
        return True, msg, pivot_info

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def get_tableau_dict(self):
        """
        Returns a dict ready to build the textbook-style display.
        Includes both numeric and symbolic (MExpr) versions of zj and cj-zj.
        """
        zj_num = self._compute_zj()
        cj_zj_num = self._compute_cj_zj(zj_num)

        zj_sym = self._compute_zj_sym()
        cj_zj_sym = self._compute_cj_zj_sym(zj_sym)

        # Use symbolic entering selection for correct pivot highlighting
        entering_col = self._select_entering_sym(cj_zj_sym)

        rows = []
        for i in range(self.num_constraints):
            bc = self.basis_cols[i]
            rows.append({
                'CB': self.cj_sym[bc],          # MExpr
                'basis': self.basis_names[i],
                'coefficients': [float(self.T[i, j]) for j in range(self.total_vars)],
                'rhs': float(self.T[i, -1])
            })

        return {
            # Numeric (for backward compat)
            'cj': [float(self.cj_sym[j]) for j in range(self.total_vars)],
            'zj': [float(zj_num[j]) for j in range(self.total_vars)],
            'cj_zj': [float(cj_zj_num[j]) for j in range(self.total_vars)],
            'z_value': float(zj_num[-1]),
            # Symbolic (for display)
            'cj_sym': list(self.cj_sym[:self.total_vars]),       # list of MExpr
            'zj_sym': zj_sym[:self.total_vars],                  # list of MExpr
            'cj_zj_sym': cj_zj_sym,                             # list of MExpr
            'z_value_sym': zj_sym[self.total_vars],             # MExpr
            # Common
            'col_names': list(self.all_var_names),
            'rows': rows,
            'entering_col': entering_col,
            'status': self.status,
            'iteration': self.iteration,
            'optimization_type': self.optimization_type,
        }

    def get_solution(self):
        """Returns the current basic feasible solution (variable values)."""
        sol = {name: 0.0 for name in self.all_var_names}
        for i, name in enumerate(self.basis_names):
            sol[name] = float(self.T[i, -1])
        zj = self._compute_zj()
        z = float(zj[-1])
        return sol, z

    def run_to_completion(self, max_iter=100):
        """
        Run the simplex method to completion and return the sequence of
        basic feasible solutions visited.
        """
        sequence = []

        def _snapshot(iteration, entering=None, leaving=None):
            sol, z = self.get_solution()
            dec_vars = {v: sol.get(v, 0.0) for v in self.var_names}
            return {
                'Iteración': iteration,
                'Base': ', '.join(self.basis_names),
                **dec_vars,
                'Z': z,
                'Entra': entering or '—',
                'Sale': leaving or '—',
                'Estado': self.status,
            }

        sequence.append(_snapshot(0))

        for _ in range(max_iter):
            zj_sym = self._compute_zj_sym()
            cj_zj_sym = self._compute_cj_zj_sym(zj_sym)
            entering_col = self._select_entering_sym(cj_zj_sym)

            if entering_col is None:
                self.status = 'Optimal'
                break

            entering_name = self.all_var_names[entering_col]
            leaving_row, _ = self._ratio_test(entering_col)

            if leaving_row is None:
                self.status = 'Unbounded'
                break

            leaving_name = self.basis_names[leaving_row]

            # Pivot
            pivot_val = self.T[leaving_row, entering_col]
            self.T[leaving_row, :] /= pivot_val
            for r in range(self.num_constraints):
                if r != leaving_row:
                    factor = self.T[r, entering_col]
                    if abs(factor) > 1e-12:
                        self.T[r, :] -= factor * self.T[leaving_row, :]

            self.basis_cols[leaving_row] = entering_col
            self.basis_names[leaving_row] = entering_name
            self.iteration += 1
            self.status = f'Iteración {self.iteration}'

            sequence.append(_snapshot(self.iteration, entering_name, leaving_name))

        return sequence

    def get_sensitivity_analysis(self):
        """
        Calculates allowable increase and allowable decrease for:
        1. Objective function coefficients (decision variables)
        2. Right-Hand Side (RHS) values for constraints.
        Returns a dict: {'objective_ranges': list, 'rhs_ranges': list}
        Returns None if not Optimal.
        """
        if self.status != 'Optimal':
            return None

        zj = self._compute_zj()
        cj_zj = self._compute_cj_zj(zj)

        obj_ranges = []
        for j in range(self.num_vars):
            var_name = self.var_names[j]
            orig_c = float(self.cj[j])

            allowable_increase = float('inf')
            allowable_decrease = float('inf')

            if j not in self.basis_cols:
                if self.optimization_type == 'max':
                    allowable_increase = float(zj[j] - self.cj[j])
                else:
                    allowable_decrease = float(self.cj[j] - zj[j])
            else:
                r = self.basis_cols.index(j)
                if self.optimization_type == 'max':
                    inc_limits = []
                    dec_limits = []
                    for k in range(self.total_vars):
                        alpha = self.T[r, k]
                        red_cost = cj_zj[k]
                        if k not in self.basis_cols:
                            if alpha < -1e-8:
                                inc_limits.append(red_cost / alpha)
                            elif alpha > 1e-8:
                                dec_limits.append(-(red_cost / alpha))
                    allowable_increase = min(inc_limits) if inc_limits else float('inf')
                    allowable_decrease = min(dec_limits) if dec_limits else float('inf')
                else:
                    inc_limits = []
                    dec_limits = []
                    for k in range(self.total_vars):
                        alpha = self.T[r, k]
                        red_cost = cj_zj[k]
                        if k not in self.basis_cols:
                            if alpha > 1e-8:
                                inc_limits.append(red_cost / alpha)
                            elif alpha < -1e-8:
                                dec_limits.append(-(red_cost / alpha))
                    allowable_increase = min(inc_limits) if inc_limits else float('inf')
                    allowable_decrease = min(dec_limits) if dec_limits else float('inf')

            obj_ranges.append({
                'Variable': var_name,
                'Valor Final': float(self.T[self.basis_cols.index(j), -1]) if j in self.basis_cols else 0.0,
                'Coeficiente Objetivo': orig_c,
                'Aumento Permisible': allowable_increase if allowable_increase < 1e10 else float('inf'),
                'Disminución Permisible': allowable_decrease if allowable_decrease < 1e10 else float('inf')
            })

        rhs_ranges = []
        for i in range(self.num_constraints):
            alpha_col = self.initial_basis_cols[i]
            alpha = self.T[:, alpha_col]
            b_bar = self.T[:, -1]

            inc_limits = []
            dec_limits = []

            for r in range(self.num_constraints):
                al = alpha[r]
                br = b_bar[r]
                if al > 1e-8:
                    dec_limits.append(br / al)
                elif al < -1e-8:
                    inc_limits.append(-(br / al))

            allowable_increase = min(inc_limits) if inc_limits else float('inf')
            allowable_decrease = min(dec_limits) if dec_limits else float('inf')

            constraint_name = f"R{i+1}"

            rhs_ranges.append({
                'Restricción': constraint_name,
                'Lado Derecho (RHS)': float(self.b_orig[i]),
                'Precio Sombra': float(zj[alpha_col]),
                'Aumento Permisible': allowable_increase if allowable_increase < 1e10 else float('inf'),
                'Disminución Permisible': allowable_decrease if allowable_decrease < 1e10 else float('inf')
            })

        return {
            'objective_ranges': obj_ranges,
            'rhs_ranges': rhs_ranges
        }


# ──────────────────────────────────────────────────────────────────────────────
# TwoPhaseSimplexTutor
# ──────────────────────────────────────────────────────────────────────────────

class TwoPhaseSimplexTutor:
    """
    Implementa el Método de las Dos Fases:

    Fase 1 – Minimizar  w = a1 + a2 + …  (sin M)
             Los cj de las artificiales son 1; todos los demás 0.
             Si w* = 0 → problema factible → continuar en Fase 2.
             Si w* > 0 → problema infactible.

    Fase 2 – Eliminar columnas de artificiales que salieron de la base,
             restaurar la función objetivo original, y continuar el Simplex.

    La estructura del tableau es idéntica a SimplexTutor para que
    _build_tableau_html y render_tableau de app.py funcionen sin cambios.
    No se usa MExpr; todos los valores son floats (el renderizador los acepta).
    """

    def __init__(self, c, A, b, constraint_types=None, optimization_type='max',
                 var_names=None):
        self.c_orig        = np.array(c, dtype=float)
        self.A_orig        = np.array(A, dtype=float)
        self.b_orig        = np.array(b, dtype=float)
        self.optimization_type = optimization_type.lower()
        self.num_vars      = len(c)
        self.num_constraints = len(b)

        if constraint_types is None:
            constraint_types = ['<='] * self.num_constraints
        self.constraint_types = constraint_types

        if var_names is None:
            var_names = [f"x{i+1}" for i in range(self.num_vars)]
        self.var_names = var_names

        # ── Column offsets ─────────────────────────────────────────────────
        num_slacks      = sum(1 for ct in constraint_types if ct in ('<=', '>='))
        num_artificials = sum(1 for ct in constraint_types if ct in ('>=', '='))
        slack_col_start       = self.num_vars
        artificial_col_start  = self.num_vars + num_slacks
        self.total_vars = self.num_vars + num_slacks + num_artificials

        # ── Column names: decisions | slacks | artificials ────────────────
        # Two-pass to maintain order (identical approach to SimplexTutor)
        extra_slack_names = []
        extra_art_names   = []
        slack_info        = []   # per-row: list of (col, coeff)
        art_info          = []   # per-row: (col, coeff) or None
        initial_basis     = []   # (row, col, name)

        s_count = 0
        a_count = 0
        for i, ct in enumerate(constraint_types):
            row_slack = []
            row_art   = None
            if ct == '<=':
                col  = slack_col_start + s_count
                name = f"s{s_count + 1}"
                s_count += 1
                row_slack.append((col, +1))
                extra_slack_names.append(name)
                initial_basis.append((i, col, name))
            elif ct == '>=':
                # surplus
                sc  = slack_col_start + s_count
                sn  = f"s{s_count + 1}"
                s_count += 1
                row_slack.append((sc, -1))
                extra_slack_names.append(sn)
                # artificial
                ac  = artificial_col_start + a_count
                an  = f"a{a_count + 1}"
                a_count += 1
                row_art = (ac, +1)
                extra_art_names.append(an)
                initial_basis.append((i, ac, an))
            elif ct == '=':
                ac  = artificial_col_start + a_count
                an  = f"a{a_count + 1}"
                a_count += 1
                row_art = (ac, +1)
                extra_art_names.append(an)
                initial_basis.append((i, ac, an))
            slack_info.append(row_slack)
            art_info.append(row_art)

        extra_names     = extra_slack_names + extra_art_names
        self.all_var_names = list(self.var_names) + extra_names

        # ── Artificial column indices (original indexing) ────────────────
        self.artificial_cols_orig = [artificial_col_start + k
                                     for k in range(num_artificials)]

        # ── Build tableau T ───────────────────────────────────────────────
        T = np.zeros((self.num_constraints, self.total_vars + 1))
        T[:, :self.num_vars] = self.A_orig
        T[:, -1]             = self.b_orig
        for i, entries in enumerate(slack_info):
            for (col, coeff) in entries:
                T[i, col] = coeff
        for i, entry in enumerate(art_info):
            if entry:
                col, coeff = entry
                T[i, col] = coeff
        self.T = T

        # ── Basis ─────────────────────────────────────────────────────────
        self.initial_basis_cols = [col for (_, col, _) in initial_basis]
        self.basis_cols  = list(self.initial_basis_cols)
        self.basis_names = [name for (_, _, name) in initial_basis]

        # ── Phase-1 objective: minimize w = Σ ai ─────────────────────────
        # cj[ai] = 1, cj[everything else] = 0
        self._ph1_cj = np.zeros(self.total_vars)
        for ac in self.artificial_cols_orig:
            self._ph1_cj[ac] = 1.0

        # ── Phase-2 objective: original c ────────────────────────────────
        self._ph2_cj = np.zeros(self.total_vars)
        for j in range(self.num_vars):
            self._ph2_cj[j] = float(self.c_orig[j])

        # Active cj (starts as Phase 1)
        self.cj = self._ph1_cj.copy()

        # ── State ─────────────────────────────────────────────────────────
        self.phase     = 1
        self.iteration = 0
        self.status    = "Fase 1 – Inicializada"
        self.last_pivot_info = None

        # If no artificials → skip to Phase 2 immediately
        if num_artificials == 0:
            self._start_phase2()

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    def _compute_zj(self):
        """zj[j] = Σ_i cB_i * T[i,j].  Returns array of length total_vars+1."""
        CB = np.array([self.cj[col] for col in self.basis_cols])
        zj = np.zeros(self.total_vars + 1)
        for j in range(self.total_vars + 1):
            zj[j] = CB @ self.T[:, j]
        return zj

    def _cj_zj(self, zj):
        return np.array([self.cj[j] - zj[j] for j in range(self.total_vars)])

    def _entering_ph1(self, cj_zj):
        """Minimise w: most negative cj-zj."""
        best, col = -1e-9, None
        for j in range(self.total_vars):
            if cj_zj[j] < best:
                best, col = cj_zj[j], j
        return col

    def _entering_ph2(self, cj_zj):
        """Phase 2 following original optimization direction."""
        if self.optimization_type == 'max':
            best, col = 1e-8, None
            for j in range(self.total_vars):
                if cj_zj[j] > best:
                    best, col = cj_zj[j], j
        else:
            best, col = -1e-8, None
            for j in range(self.total_vars):
                if cj_zj[j] < best:
                    best, col = cj_zj[j], j
        return col

    def _ratio_test(self, entering_col):
        rhs      = self.T[:, -1]
        col_vals = self.T[:, entering_col]
        min_ratio, min_row = float('inf'), -1
        for i in range(self.num_constraints):
            if col_vals[i] > 1e-8:
                r = rhs[i] / col_vals[i]
                if r < min_ratio - 1e-9:
                    min_ratio, min_row = r, i
                elif abs(r - min_ratio) < 1e-9:
                    if self.basis_cols[i] < self.basis_cols[min_row]:
                        min_row = i
        return (min_row if min_row != -1 else None), min_ratio

    def _pivot(self, entering_col, leaving_row):
        pivot_val = self.T[leaving_row, entering_col]
        self.T[leaving_row, :] /= pivot_val
        for r in range(self.num_constraints):
            if r != leaving_row:
                f = self.T[r, entering_col]
                if abs(f) > 1e-12:
                    self.T[r, :] -= f * self.T[leaving_row, :]
        self.basis_cols[leaving_row]  = entering_col
        self.basis_names[leaving_row] = self.all_var_names[entering_col]

    def _build_ratios(self, entering_col, leaving_row):
        ratios = []
        for i in range(self.num_constraints):
            pv = float(self.T[i, entering_col])
            if pv > 1e-8:
                ratios.append({'basis': self.basis_names[i],
                               'rhs': float(self.T[i, -1]),
                               'pivot_col_val': pv,
                               'ratio': float(self.T[i, -1]) / pv,
                               'is_min': (i == leaving_row)})
            else:
                ratios.append({'basis': self.basis_names[i],
                               'rhs': float(self.T[i, -1]),
                               'pivot_col_val': pv,
                               'ratio': None,
                               'is_min': False})
        return ratios

    def _start_phase2(self):
        """Transition to Phase 2: drop out-of-basis artificials, restore cj."""
        self.phase = 2

        art_set   = set(self.artificial_cols_orig)
        basis_set = set(self.basis_cols)

        # Columns to keep: everything that is NOT an artificial outside the basis
        keep_cols = [j for j in range(self.total_vars)
                     if not (j in art_set and j not in basis_set)]

        new_n = len(keep_cols)
        new_T = np.zeros((self.num_constraints, new_n + 1))
        for new_j, old_j in enumerate(keep_cols):
            new_T[:, new_j] = self.T[:, old_j]
        new_T[:, -1] = self.T[:, -1]

        # Remap basis columns
        old2new = {old: new for new, old in enumerate(keep_cols)}
        self.basis_cols = [old2new[bc] for bc in self.basis_cols]

        # New variable names and cj
        new_names = [self.all_var_names[j] for j in keep_cols]
        new_cj    = np.zeros(new_n)
        for new_j, old_j in enumerate(keep_cols):
            if old_j not in art_set:
                new_cj[new_j] = self._ph2_cj[old_j]
            # artificials still in basis (degenerate) → cj = 0 (already 0)

        self.T             = new_T
        self.cj            = new_cj
        self.all_var_names = new_names
        self.total_vars    = new_n
        self.status        = "Fase 2 – Inicializada"

    # ──────────────────────────────────────────────────────────────────────
    # Public API  (mirrors SimplexTutor)
    # ──────────────────────────────────────────────────────────────────────

    def next_step(self):
        """One iteration.  Returns (continue: bool, message: str, pivot_info or None)."""
        zj     = self._compute_zj()
        cj_zj  = self._cj_zj(zj)

        if self.phase == 1:
            entering_col = self._entering_ph1(cj_zj)

            # Phase 1 optimal?
            if entering_col is None:
                w_star = float(zj[self.total_vars])
                if abs(w_star) > 1e-6:
                    self.status = "Infeasible"
                    return False, "❌ El problema es **infactible** (w* ≠ 0 en Fase 1).", None
                # Transition
                self._start_phase2()
                return True, (
                    "✅ **Fase 1 completa** — w* = 0 → el problema es factible.  "
                    "Ahora se elimina las columnas artificiales y se restaura el "
                    "objetivo original.  Presiona ⏩ para continuar en **Fase 2**."
                ), None

            leaving_row, ratio = self._ratio_test(entering_col)
            if leaving_row is None:
                self.status = "Unbounded"
                return False, "⚠️ Solución no acotada en Fase 1.", None

            pinfo = {
                'entering_col':  entering_col,
                'entering_name': self.all_var_names[entering_col],
                'leaving_row':   leaving_row,
                'leaving_name':  self.basis_names[leaving_row],
                'pivot_val':     float(self.T[leaving_row, entering_col]),
                'ratios':        self._build_ratios(entering_col, leaving_row),
                'opt_direction': 'min',   # Phase 1 always minimises
            }
            self._pivot(entering_col, leaving_row)
            self.iteration += 1
            self.status = f"Fase 1 – Iteración {self.iteration}"

            msg = (f"**Fase 1 – Iter {self.iteration}:** "
                   f"Entra **{pinfo['entering_name']}** "
                   f"(cj-zj = {cj_zj[entering_col]:.4g}), "
                   f"Sale **{pinfo['leaving_name']}** (razón = {ratio:.4g}).")
            return True, msg, pinfo

        else:  # Phase 2
            entering_col = self._entering_ph2(cj_zj)

            if entering_col is None:
                self.status = "Optimal"
                return False, (
                    "✅ **Solución óptima encontrada.** "
                    "Todos los cj-zj cumplen el criterio de optimalidad."
                ), None

            leaving_row, ratio = self._ratio_test(entering_col)
            if leaving_row is None:
                self.status = "Unbounded"
                return False, "⚠️ El problema es NO ACOTADO.", None

            pinfo = {
                'entering_col':  entering_col,
                'entering_name': self.all_var_names[entering_col],
                'leaving_row':   leaving_row,
                'leaving_name':  self.basis_names[leaving_row],
                'pivot_val':     float(self.T[leaving_row, entering_col]),
                'ratios':        self._build_ratios(entering_col, leaving_row),
                'opt_direction': self.optimization_type,
            }
            self._pivot(entering_col, leaving_row)
            self.iteration += 1
            self.status = f"Fase 2 – Iteración {self.iteration}"

            msg = (f"**Fase 2 – Iter {self.iteration}:** "
                   f"Entra **{pinfo['entering_name']}** "
                   f"(cj-zj = {cj_zj[entering_col]:.4g}), "
                   f"Sale **{pinfo['leaving_name']}** (razón = {ratio:.4g}).")
            return True, msg, pinfo

    def get_tableau_dict(self):
        """Returns dict compatible with _build_tableau_html in app.py."""
        zj    = self._compute_zj()
        cjzj  = self._cj_zj(zj)

        if self.phase == 1:
            entering_col = self._entering_ph1(cjzj)
        else:
            entering_col = self._entering_ph2(cjzj)

        rows = []
        for i in range(self.num_constraints):
            bc = self.basis_cols[i]
            rows.append({
                'CB':           float(self.cj[bc]),
                'basis':        self.basis_names[i],
                'coefficients': [float(self.T[i, j]) for j in range(self.total_vars)],
                'rhs':          float(self.T[i, -1]),
            })

        n = self.total_vars
        return {
            # Numeric lists (used by _build_tableau_html via _fmt_M fallback)
            'cj':          [float(self.cj[j]) for j in range(n)],
            'zj':          [float(zj[j])      for j in range(n)],
            'cj_zj':       [float(cjzj[j])   for j in range(n)],
            'z_value':     float(zj[n]),
            # _build_tableau_html prefers *_sym but falls back to numeric if absent
            'cj_sym':      [float(self.cj[j]) for j in range(n)],
            'zj_sym':      [float(zj[j])      for j in range(n)],
            'cj_zj_sym':   [float(cjzj[j])   for j in range(n)],
            'z_value_sym': float(zj[n]),
            # Common
            'col_names':   list(self.all_var_names),
            'rows':        rows,
            'entering_col': entering_col,
            'status':      self.status,
            'iteration':   self.iteration,
            'optimization_type': self.optimization_type,
            'phase':       self.phase,   # 1 or 2  (used by UI for badge)
        }

    def get_solution(self):
        """Returns (solution_dict, z_value) — mirrors SimplexTutor."""
        sol = {name: 0.0 for name in self.all_var_names}
        for i, name in enumerate(self.basis_names):
            sol[name] = float(self.T[i, -1])
        zj = self._compute_zj()
        return sol, float(zj[-1])
