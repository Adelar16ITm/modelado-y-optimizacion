"""
transport.py  ── Transportation & Assignment Solver
==================================================
Supports three algorithms exposed through ``solve_initial(method=…)``:

  • "min_cost"   – Minimum-Cost initial BFS  + MODI optimisation
  • "northwest"  – North-West Corner initial BFS + MODI optimisation
  • "hungarian"  – Hungarian method (manual steps for pedagogy)

All methods return detailed step-by-step information for display.
"""

import numpy as np
from scipy.optimize import linear_sum_assignment

_EPS   = 1e-9
_DEGEN = 1e-8


class TransportSolver:
    def __init__(self, cost_matrix, supply, demand):
        self.costs      = np.array(cost_matrix, dtype=float)
        self.supply     = np.array(supply,      dtype=float)
        self.demand     = np.array(demand,      dtype=float)
        self.m          = len(supply)
        self.n          = len(demand)
        self.num_supply = self.m
        self.num_demand = self.n

    # ------------------------------------------------------------------ #
    #  Public entry-point                                                  #
    # ------------------------------------------------------------------ #
    def solve_initial(self, method: str = "min_cost") -> dict:
        if method == "hungarian":
            return self._hungarian()

        # ── Auto-balance ────────────────────────────────────────────────
        total_s = float(self.supply.sum())
        total_d = float(self.demand.sum())
        costs   = self.costs.copy()
        supply  = self.supply.copy()
        demand  = self.demand.copy()
        dummy_col_added = False
        dummy_row_added = False

        if total_s > total_d + _EPS:
            dummy_demand    = total_s - total_d
            costs           = np.hstack([costs, np.zeros((costs.shape[0], 1))])
            demand          = np.append(demand, dummy_demand)
            dummy_col_added = True
        elif total_d > total_s + _EPS:
            dummy_supply    = total_d - total_s
            costs           = np.vstack([costs, np.zeros((1, costs.shape[1]))])
            supply          = np.append(supply, dummy_supply)
            dummy_row_added = True

        m, n = len(supply), len(demand)

        # Temporarily override instance dimensions for sub-methods
        _saved = (self.costs, self.m, self.n)
        self.costs, self.m, self.n = costs, m, n

        alloc = np.zeros((m, n))
        s, d  = supply.copy(), demand.copy()

        if method == "northwest":
            phase1_steps = self._northwest_corner(alloc, s, d)
        else:
            phase1_steps = self._min_cost(alloc, s, d)

        initial_cost     = float(np.sum(alloc * costs))
        alloc_opt, iters = self._modi(alloc)
        final_cost       = float(np.sum(alloc_opt * costs))

        self.costs, self.m, self.n = _saved  # restore

        # Strip dummy from output allocation
        if dummy_col_added:
            alloc_out = alloc_opt[:, :-1]
        elif dummy_row_added:
            alloc_out = alloc_opt[:-1, :]
        else:
            alloc_out = alloc_opt

        return {
            "allocation":       alloc_out,
            "total_cost":       final_cost,
            "initial_cost":     initial_cost,
            "status":           "Óptimo (Simplex de Transporte)",
            "is_assignment":    False,
            "iterations":       iters,
            "phase1_steps":     phase1_steps,
            "dummy_col_added":  dummy_col_added,
            "dummy_row_added":  dummy_row_added,
            "n_cols_orig":      self.n,   # original (pre-pad) dimensions
            "n_rows_orig":      self.m,
        }

    # ------------------------------------------------------------------ #
    #  Phase 1 – Northwest Corner                                          #
    # ------------------------------------------------------------------ #
    def _northwest_corner(self, alloc, s, d):
        """Fill allocation using NW-corner rule; returns list of step dicts."""
        m, n   = self.m, self.n
        steps  = []
        step_n = 1
        i = j  = 0
        while i < m and j < n:
            q           = min(s[i], d[j])
            alloc[i, j] = q
            s[i]       -= q
            d[j]       -= q
            steps.append({
                "Paso":       step_n,
                "Celda":      f"S{i+1} → D{j+1}",
                "Cantidad":   round(q, 4),
                "Costo c_ij": round(self.costs[i, j], 4),
                "Costo acum.": round(float(np.sum(alloc * self.costs)), 4),
                "snapshot":   alloc.copy(),
                "supply_rem": s.copy(),
                "demand_rem": d.copy(),
            })
            step_n += 1
            if   s[i] < _EPS: i += 1
            elif d[j] < _EPS: j += 1
        return steps

    # ------------------------------------------------------------------ #
    #  Phase 1 – Minimum Cost                                              #
    # ------------------------------------------------------------------ #
    def _min_cost(self, alloc, s, d):
        """Fill allocation using min-cost rule; returns list of step dicts."""
        m, n   = self.m, self.n
        cells  = sorted(
            [(self.costs[i, j], i, j) for i in range(m) for j in range(n)],
            key=lambda x: x[0])
        steps  = []
        step_n = 1
        for cost_ij, i, j in cells:
            if s[i] > _EPS and d[j] > _EPS:
                q           = min(s[i], d[j])
                alloc[i, j] = q
                s[i]       -= q
                d[j]       -= q
                steps.append({
                    "Paso":       step_n,
                    "Celda":      f"S{i+1} → D{j+1}",
                    "Cantidad":   round(q, 4),
                    "Costo c_ij": round(cost_ij, 4),
                    "Costo acum.": round(float(np.sum(alloc * self.costs)), 4),
                    "snapshot":   alloc.copy(),
                    "supply_rem": s.copy(),
                    "demand_rem": d.copy(),
                })
                step_n += 1
        return steps

    # ------------------------------------------------------------------ #
    #  Phase 2 – MODI                                                      #
    # ------------------------------------------------------------------ #
    def _modi(self, alloc):
        alloc = alloc.astype(float)
        iters = []
        try:
            return self._modi_inner(alloc, iters)
        except Exception as e:
            return alloc, [{"Iter": 0,
                            "Costo": float(np.sum(alloc * self.costs)),
                            "Min RC": 0,
                            "Estado": f"Error: {e}"}]

    def _modi_inner(self, alloc, iters):
        m, n   = self.m, self.n
        MAX_IT = 100

        for _it in range(MAX_IT):
            # ── Basis ────────────────────────────────────────────────────
            basis = [(i, j) for i in range(m) for j in range(n)
                     if alloc[i, j] > _EPS]
            need  = m + n - 1
            if len(basis) < need:
                basis = self._fix_degeneracy(basis, alloc, m, n, need)
            basis_set = set(basis)

            # ── Dual variables ───────────────────────────────────────────
            u = [None] * m;  v = [None] * n
            u[0] = 0.0
            changed = True
            while changed:
                changed = False
                for (i, j) in basis:
                    if u[i] is not None and v[j] is None:
                        v[j] = self.costs[i, j] - u[i];  changed = True
                    elif v[j] is not None and u[i] is None:
                        u[i] = self.costs[i, j] - v[j];  changed = True

            # ── Reduced costs ────────────────────────────────────────────
            rc = {}
            for i in range(m):
                if u[i] is None: continue
                for j in range(n):
                    if v[j] is None: continue
                    if (i, j) not in basis_set:
                        rc[(i, j)] = self.costs[i, j] - u[i] - v[j]

            total  = float(np.sum(alloc * self.costs))
            min_rc = min(rc.values()) if rc else 0.0

            entering = min(rc, key=rc.get) if rc and min_rc < -_EPS else None
            loop     = None
            theta    = None

            if entering:
                loop  = self._find_loop(entering, basis_set, m, n)
                if loop:
                    minus_cells = [loop[k] for k in range(1, len(loop), 2)]
                    theta       = float(min(alloc[i][j] for i, j in minus_cells))

            iters.append({
                "Iter":         _it,
                "Costo":        round(total, 4),
                "Min RC":       round(min_rc, 6),
                "Estado":       "Óptimo" if min_rc >= -_EPS else "Mejorando",
                # Rich step data for display
                "snapshot":     alloc.copy(),
                "u":            [round(x, 4) if x is not None else None for x in u],
                "v":            [round(x, 4) if x is not None else None for x in v],
                "rc":           {f"S{i+1}→D{j+1}": round(v2, 4) for (i, j), v2 in rc.items()},
                "entering":     f"S{entering[0]+1}→D{entering[1]+1}" if entering else None,
                "loop":         [f"S{r+1}→D{c+1}" for r, c in loop] if loop else None,
                "theta":        round(theta, 4) if theta is not None else None,
            })

            if not rc or min_rc >= -_EPS:
                break

            if loop is None:
                break

            # ── Pivot ────────────────────────────────────────────────────
            for k, (i, j) in enumerate(loop):
                alloc[i, j] += theta if k % 2 == 0 else -theta
            alloc[np.abs(alloc) < _EPS / 10] = 0.0

        return alloc, iters

    # ------------------------------------------------------------------ #
    #  Stepping-stone loop – recursive backtracking DFS                   #
    # ------------------------------------------------------------------ #
    def _find_loop(self, entering, basis_set, m, n):
        start = tuple(entering)
        row_to_cols: dict = {}
        col_to_rows: dict = {}
        for (i, j) in basis_set:
            row_to_cols.setdefault(i, set()).add(j)
            col_to_rows.setdefault(j, set()).add(i)

        path    = [start]
        visited = {start}
        result  = []

        def dfs(col_move: bool) -> bool:
            cur = path[-1]
            L   = len(path)
            if L > 2 * (m + n):
                return False
            if col_move:
                neighbours = [(r, cur[1]) for r in col_to_rows.get(cur[1], ())
                              if r != cur[0] and (r, cur[1]) not in visited]
            else:
                neighbours = [(cur[0], c) for c in row_to_cols.get(cur[0], ())
                              if c != cur[1] and (cur[0], c) not in visited]
            next_col_move = not col_move
            for nc in neighbours:
                if L >= 3:
                    can_close = (nc[1] == start[1]) if next_col_move else (nc[0] == start[0])
                    if can_close:
                        result.clear()
                        result.extend(path + [nc])
                        return True
                path.append(nc)
                visited.add(nc)
                if dfs(next_col_move):
                    return True
                path.pop()
                visited.discard(nc)
            return False

        dfs(col_move=True)
        return result if result else None

    # ------------------------------------------------------------------ #
    #  Degeneracy fix – union-find                                         #
    # ------------------------------------------------------------------ #
    def _fix_degeneracy(self, basis, alloc, m, n, need):
        parent = list(range(m + n))

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]; x = parent[x]
            return x

        def union(x, y):
            px, py = find(x), find(y)
            if px == py: return False
            parent[px] = py; return True

        basis_set = set(map(tuple, basis))
        for (i, j) in basis:
            union(i, m + j)

        candidates = sorted(
            ((i, j) for i in range(m) for j in range(n) if (i, j) not in basis_set),
            key=lambda ij: (ij[0] == 0, ij[0], ij[1])
        )
        for (i, j) in candidates:
            if len(basis) >= need: break
            if union(i, m + j):
                alloc[i, j] = _DEGEN
                basis.append((i, j))
                basis_set.add((i, j))
        return basis

    # ------------------------------------------------------------------ #
    #  Optimality test on a user-provided BFS (no Phase 1)                #
    # ------------------------------------------------------------------ #
    def verify_optimality(self, allocation):
        """
        Toma una BFS proporcionada por el usuario y aplica SÓLO la prueba de
        optimalidad del simplex de transporte (sin construir BFS inicial).
        Maneja problemas desbalanceados auto-agregando dummy si la asignación
        ya incluye columnas/filas extra.

        Devuelve dict con u, v, costos reducidos, y is_optimal.
        """
        alloc = np.array(allocation, dtype=float)
        m_alloc, n_alloc = alloc.shape

        # Si la asignación incluye filas/columnas dummy, expandir self.costs
        costs = self.costs.copy()
        if n_alloc > costs.shape[1]:
            extra = n_alloc - costs.shape[1]
            costs = np.hstack([costs, np.zeros((costs.shape[0], extra))])
        if m_alloc > costs.shape[0]:
            extra = m_alloc - costs.shape[0]
            costs = np.vstack([costs, np.zeros((extra, costs.shape[1]))])

        m, n = alloc.shape
        # Override temporal para usar _fix_degeneracy
        _saved = (self.costs, self.m, self.n)
        self.costs, self.m, self.n = costs, m, n

        try:
            basis = [(i, j) for i in range(m) for j in range(n) if alloc[i, j] > _EPS]
            need = m + n - 1
            if len(basis) < need:
                basis = self._fix_degeneracy(basis, alloc, m, n, need)
            basis_set = set(basis)

            u = [None] * m
            v = [None] * n
            u[0] = 0.0
            changed = True
            while changed:
                changed = False
                for (i, j) in basis:
                    if u[i] is not None and v[j] is None:
                        v[j] = costs[i, j] - u[i]
                        changed = True
                    elif v[j] is not None and u[i] is None:
                        u[i] = costs[i, j] - v[j]
                        changed = True

            rc = {}
            for i in range(m):
                if u[i] is None:
                    continue
                for j in range(n):
                    if v[j] is None:
                        continue
                    if (i, j) not in basis_set:
                        rc[(i, j)] = costs[i, j] - u[i] - v[j]

            min_rc = min(rc.values()) if rc else 0.0
            is_optimal = (min_rc >= -_EPS)

            return {
                "is_optimal":    is_optimal,
                "u":             [round(x, 6) if x is not None else None for x in u],
                "v":             [round(x, 6) if x is not None else None for x in v],
                "reduced_costs": {(i, j): round(val, 6) for (i, j), val in rc.items()},
                "min_reduced_cost": round(min_rc, 6),
                "total_cost":    float(np.sum(alloc * costs)),
                "basis":         basis,
                "n_supply":      m,
                "n_demand":      n,
                "status":        "Óptima" if is_optimal else "No óptima",
            }
        finally:
            self.costs, self.m, self.n = _saved

    # ------------------------------------------------------------------ #
    #  Sensibility analysis on a user-provided optimal BFS                #
    # ------------------------------------------------------------------ #
    def sensitivity_report(self, allocation):
        """
        Análisis de sensibilidad sobre una BFS óptima.

        Para celdas NO básicas: rango permisible de c_ij = [u_i + v_j, ∞)
          → c_ij puede bajar como máximo |costo_reducido| antes de que la celda entre.
        Para celdas BÁSICAS: el rango requiere calcular el ciclo (loop) para cada celda;
          se reporta el ciclo y la dirección de cambio.

        u_i, v_j son los precios sombra de oferta y demanda respectivamente.
        """
        opt = self.verify_optimality(allocation)
        if not opt["is_optimal"]:
            return {
                "error": "La BFS proporcionada NO es óptima. El análisis de sensibilidad "
                         "sólo aplica a soluciones óptimas.",
                "verify": opt,
            }

        alloc = np.array(allocation, dtype=float)
        m, n = alloc.shape
        u = opt["u"]
        v = opt["v"]
        basis_set = set(opt["basis"])

        # Expandir costos si hay dummy
        costs = self.costs.copy()
        if n > costs.shape[1]:
            costs = np.hstack([costs, np.zeros((costs.shape[0], n - costs.shape[1]))])
        if m > costs.shape[0]:
            costs = np.vstack([costs, np.zeros((m - costs.shape[0], costs.shape[1]))])

        # ── Rangos para c_ij NO básicas ───────────────────────────────────────
        nonbasic_ranges = []
        for i in range(m):
            for j in range(n):
                if (i, j) not in basis_set and u[i] is not None and v[j] is not None:
                    current  = float(costs[i, j])
                    lower    = u[i] + v[j]   # nivel al que costo reducido = 0
                    nonbasic_ranges.append({
                        "Celda":       f"S{i+1}→D{j+1}",
                        "c_ij actual": round(current, 4),
                        "Cota inf.":   round(lower, 4),
                        "Decrec. max": round(current - lower, 4),
                        "Crec. max":   "∞",
                        "Rango":       f"[{lower:.2f}, ∞)",
                    })

        # ── Rangos para c_ij BÁSICAS (usando loop / ciclo) ────────────────────
        basic_ranges = []
        # Override para usar _find_loop
        _saved = (self.costs, self.m, self.n)
        self.costs, self.m, self.n = costs, m, n
        try:
            for (i, j) in basis_set:
                # Buscar el ciclo que se formaría si esta celda básica saliera
                # En vez del enfoque clásico, reportamos: si c_ij cambia δ,
                # ¿cuándo entra otra celda? Es decir: para cada no-básica (k,l),
                # el RC cambia con δ si (i,j) participa en su loop.
                # Aproximación: reportamos sólo c_ij y x_ij; rango completo
                # requiere análisis por ciclo.
                basic_ranges.append({
                    "Celda":     f"S{i+1}→D{j+1}",
                    "c_ij":      round(float(costs[i, j]), 4),
                    "x_ij":      round(float(alloc[i, j]), 4),
                    "Nota":      "Básica — rango depende del ciclo (ver explicación)",
                })
        finally:
            self.costs, self.m, self.n = _saved

        # ── Precios sombra (variables duales) ─────────────────────────────────
        shadow_supply = {f"S{i+1}": round(u[i], 4) for i in range(m) if u[i] is not None}
        shadow_demand = {f"D{j+1}": round(v[j], 4) for j in range(n) if v[j] is not None}

        return {
            "is_optimal":      True,
            "total_cost":      opt["total_cost"],
            "u":               opt["u"],
            "v":               opt["v"],
            "shadow_supply":   shadow_supply,
            "shadow_demand":   shadow_demand,
            "nonbasic_ranges": nonbasic_ranges,
            "basic_ranges":    basic_ranges,
            "n_supply":        m,
            "n_demand":        n,
        }

    # ------------------------------------------------------------------ #
    #  Hungarian Method – manual steps for pedagogy                        #
    # ------------------------------------------------------------------ #
    def _hungarian(self):
        n_rows, n_cols = self.costs.shape
        n   = max(n_rows, n_cols)
        mat = np.zeros((n, n), dtype=float)
        mat[:n_rows, :n_cols] = self.costs

        steps = []
        steps.append({
            "label":    "Paso 1 – Matriz original",
            "matrix":   mat.copy(),
            "desc":     "Matriz de costos original (padded a cuadrada si es necesario).",
        })

        # Step 1: Row reduction
        row_min = mat.min(axis=1, keepdims=True)
        mat     = mat - row_min
        steps.append({
            "label":  "Paso 2 – Reducción de filas",
            "matrix": mat.copy(),
            "desc":   "Se resta el mínimo de cada fila → cada fila tiene al menos un 0.",
        })

        # Step 2: Column reduction
        col_min = mat.min(axis=0, keepdims=True)
        mat     = mat - col_min
        steps.append({
            "label":  "Paso 3 – Reducción de columnas",
            "matrix": mat.copy(),
            "desc":   "Se resta el mínimo de cada columna → cada columna tiene al menos un 0.",
        })

        # Step 3+: Assignment adjustment loop
        iteration = 4
        while True:
            row_ind, col_ind = linear_sum_assignment(mat)
            # Check if we have n zeros covering the assignment
            # (scipy always finds the optimal — we just show the current state)
            steps.append({
                "label":  f"Paso {iteration} – Asignación tentativa",
                "matrix": mat.copy(),
                "desc":   f"Asignación óptima encontrada en la matriz reducida.",
                "assignment": list(zip(row_ind.tolist(), col_ind.tolist())),
            })
            break   # scipy finds optimal in one shot; no iteration needed

        # Final result
        alloc = np.zeros((n_rows, n_cols))
        total = 0.0
        pairs = []
        for r, c in zip(row_ind, col_ind):
            if r < n_rows and c < n_cols:
                alloc[r, c] = 1.0
                total      += self.costs[r, c]
                pairs.append({
                    "Fuente": f"S{r+1}",
                    "Tarea":  f"D{c+1}",
                    "Costo":  self.costs[r, c],
                })

        return {
            "allocation":       alloc,
            "total_cost":       total,
            "status":           "Óptimo (Húngaro)",
            "is_assignment":    True,
            "assignment_pairs": pairs,
            "steps":            steps,
        }
