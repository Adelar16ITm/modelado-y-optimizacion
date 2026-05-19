import streamlit as st
import pandas as pd
from modules.lp_parser import LPParser
from modules.lp_solver import LPSolver
from modules.plotting_2d import LPPlotter
from modules.duality import build_dual, complementary_slackness, solve_dual_simplex

st.set_page_config(layout="wide", page_title="OR Workbench Pro")

# --- Custom CSS for "Exam Mode" Look ---
st.markdown("""
<style>
    .block-container {padding-top: 1rem; padding-bottom: 2rem;}
    h1 {font-size: 1.8rem; margin-bottom: 0px;}
    .stButton>button {
        width: 100%;
        background-color: #0068c9;
        color: white;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

st.title("OR Workbench Pro")


# =============================================================================
#  Helper: tabla balanceada (formato inciso "a") + formulación PPL
# =============================================================================
def render_balanced_transport_and_lp(costs, supply, demand, row_lbl=None, col_lbl=None):
    """
    Dado costos (m×n), oferta, demanda y etiquetas opcionales:
      1. Balancea con dummy fila o columna (si oferta ≠ demanda)
      2. Renderiza la tabla balanceada (formato del inciso 'a' del examen)
      3. Renderiza la formulación completa del PPL (variables, objetivo,
         restricciones de oferta, demanda, no negatividad).
    """
    import numpy as np
    costs_arr = np.array(costs, dtype=float)
    m, n = costs_arr.shape

    # Labels por default
    if row_lbl is None or len(row_lbl) != m:
        row_lbl = [f"S{i+1}" for i in range(m)]
    if col_lbl is None or len(col_lbl) != n:
        col_lbl = [f"D{j+1}" for j in range(n)]

    supply = [float(s) for s in supply]
    demand = [float(d) for d in demand]
    total_s = sum(supply)
    total_d = sum(demand)

    # ── Balancear ──────────────────────────────────────────────────────────
    bal_costs = costs_arr.copy()
    bal_supply = list(supply)
    bal_demand = list(demand)
    bal_rows = list(row_lbl)
    bal_cols = list(col_lbl)
    diff = abs(total_s - total_d)

    if total_s > total_d + 1e-9:
        bal_costs = np.hstack([bal_costs, np.zeros((bal_costs.shape[0], 1))])
        bal_demand.append(diff)
        bal_cols.append("Dummy")
        dummy_msg = (f"⚠️ Desbalanceado: oferta={total_s:g}, demanda={total_d:g}. "
                     f"Agregamos **columna Dummy** (bodega/destino ficticio) con "
                     f"demanda = **{diff:g}** y costos = 0.")
    elif total_d > total_s + 1e-9:
        bal_costs = np.vstack([bal_costs, np.zeros((1, bal_costs.shape[1]))])
        bal_supply.append(diff)
        bal_rows.append("Dummy")
        dummy_msg = (f"⚠️ Desbalanceado: oferta={total_s:g}, demanda={total_d:g}. "
                     f"Agregamos **fila Dummy** (planta/origen ficticio) con "
                     f"oferta = **{diff:g}** y costos = 0.")
    else:
        dummy_msg = f"✅ Balanceado: oferta = demanda = {total_s:g}."

    m_b = len(bal_rows)
    n_b = len(bal_cols)

    def _fmt(v):
        try:
            return str(int(v)) if abs(v - int(v)) < 1e-9 else f"{v:.4g}"
        except Exception:
            return str(v)

    # ── 1) Tabla balanceada (formato inciso a) ─────────────────────────────
    st.markdown("#### 📋 Tabla de Transporte Balanceada (formato inciso *a*)")
    if diff > 1e-9:
        st.info(dummy_msg)
    else:
        st.success(dummy_msg)

    body = []
    for i in range(m_b):
        row = [float(bal_costs[i, j]) for j in range(n_b)]
        row.append(float(bal_supply[i]))
        body.append(row)
    body.append([float(d) for d in bal_demand] + [float(sum(bal_supply))])
    bal_df = pd.DataFrame(body,
                          columns=bal_cols + ["Oferta"],
                          index=bal_rows + ["Demanda"])
    # Resaltar oferta/demanda y dummy
    def _style_bal(val):
        return ""
    def _style_bal_row(row):
        styles = [""] * len(row)
        if row.name == "Demanda":
            return ["background-color:#fff3e0; font-weight:bold"] * len(row)
        if row.name == "Dummy":
            return ["background-color:#e1f5fe; color:#01579b"] * len(row)
        return styles
    def _style_bal_col(col):
        if col.name == "Oferta":
            return ["background-color:#fff3e0; font-weight:bold"] * len(col)
        if col.name == "Dummy":
            return ["background-color:#e1f5fe; color:#01579b"] * len(col)
        return [""] * len(col)
    try:
        st.dataframe(
            bal_df.style.format(_fmt).apply(_style_bal_row, axis=1).apply(_style_bal_col, axis=0),
            use_container_width=True
        )
    except Exception:
        st.dataframe(bal_df.style.format(_fmt), use_container_width=True)

    # ── 2) Formulación PPL ─────────────────────────────────────────────────
    st.markdown("#### 📝 Formulación como PPL (Programación Lineal)")

    # Nombres "naturales" tipo examen: P1B1, P1B2, etc. (concatena row+col, sin espacios)
    def _short(s):
        return str(s).replace(" ", "").replace("(", "").replace(")", "").replace("Dummy", "D")
    short_rows = [_short(r) for r in row_lbl]  # ORIGINAL (sin dummy)
    short_cols = [_short(c) for c in col_lbl]
    short_rows_b = [_short(r) for r in bal_rows]  # CON dummy
    short_cols_b = [_short(c) for c in bal_cols]

    # ── 2a) Respuestas directas para incisos (d) y (e) ────────────────────
    st.markdown("##### 📌 Respuestas directas para los incisos del examen")
    st.caption("Estas usan los **nombres originales del problema** (sin dummy), "
               "que es lo que normalmente piden los incisos (d), (e) del examen.")

    # INCISO (d) — Función objetivo con variables originales (sin dummy)
    st.markdown("**📌 Inciso (d) — Función objetivo:**")
    obj_terms_orig = []
    for i in range(m):
        for j in range(n):
            c = costs_arr[i, j]
            var = f"{short_rows[i]}{short_cols[j]}"
            obj_terms_orig.append(f"{_fmt(c)}·{var}")
    obj_line = "min Z = " + " + ".join(obj_terms_orig)
    st.code(obj_line, language="text")

    # INCISO (e) — Restricciones de DEMANDA por destino (formato examen)
    # Si oferta > demanda: la igualdad de demanda es '=' (siempre se satisface)
    # Si demanda > oferta: la demanda puede ser '<=' o '>=' según contexto
    dem_op = "=" if total_s >= total_d - 1e-9 else "<="
    st.markdown(f"**📌 Inciso (e) — Restricciones de demanda** (una por destino — copia la que te pida el examen):")
    dem_lines_e = []
    for j in range(n):
        terms = [f"{short_rows[i]}{short_cols[j]}" for i in range(m)]
        dem_lines_e.append(
            f"  ({col_lbl[j]})  " + " + ".join(terms) + f" {dem_op} {_fmt(demand[j])}"
        )
    st.code("\n".join(dem_lines_e), language="text")

    # BONUS: restricciones de oferta originales (por si el examen pide en lugar de demanda)
    sup_op = "<=" if total_s > total_d + 1e-9 else "="
    st.markdown(f"**📌 Bonus — Restricciones de oferta** (una por origen, por si el examen las pide):")
    sup_lines_e = []
    for i in range(m):
        terms = [f"{short_rows[i]}{short_cols[j]}" for j in range(n)]
        sup_lines_e.append(
            f"  ({row_lbl[i]})  " + " + ".join(terms) + f" {sup_op} {_fmt(supply[i])}"
        )
    st.code("\n".join(sup_lines_e), language="text")

    # No-negatividad versión examen
    st.markdown("**📌 No negatividad:**")
    nonneg = ",  ".join([f"{short_rows[i]}{short_cols[j]}"
                          for i in range(m) for j in range(n)])
    st.code(f"  {nonneg}  >=  0", language="text")

    st.markdown("---")
    st.markdown("##### 📚 Formulación completa balanceada (con notación x(i,j) y dummy)")
    st.caption("Esta es la versión 'completa' incluyendo dummy y notación matricial.")

    # Variables (notación matricial completa)
    st.markdown(f"**Variables de decisión** ({m_b} × {n_b} = **{m_b*n_b} variables**):")
    var_def = (
        "  x(i,j) = unidades enviadas del origen i al destino j\n"
        f"  i  ∈  {{ {', '.join(bal_rows)} }}\n"
        f"  j  ∈  {{ {', '.join(bal_cols)} }}"
    )
    st.code(var_def, language="text")

    # Función objetivo
    st.markdown("**Función objetivo** (minimizar costo total de transporte):")
    obj_terms = []
    for i in range(m_b):
        for j in range(n_b):
            c = bal_costs[i, j]
            obj_terms.append(f"{_fmt(c)}·x({bal_rows[i]},{bal_cols[j]})")
    obj_lines = []
    per_line = 4
    for k in range(0, len(obj_terms), per_line):
        chunk = " + ".join(obj_terms[k:k+per_line])
        if k == 0:
            obj_lines.append("min Z = " + chunk)
        else:
            obj_lines.append("        + " + chunk)
    st.code("\n".join(obj_lines), language="text")

    # Restricciones de oferta
    st.markdown(f"**Restricciones de oferta** (una por origen — {m_b} en total):")
    lines = []
    for i in range(m_b):
        terms = [f"x({bal_rows[i]},{bal_cols[j]})" for j in range(n_b)]
        lines.append(f"  ({bal_rows[i]})  " + " + ".join(terms) + f"  =  {_fmt(bal_supply[i])}")
    st.code("\n".join(lines), language="text")

    # Restricciones de demanda
    st.markdown(f"**Restricciones de demanda** (una por destino — {n_b} en total):")
    lines = []
    for j in range(n_b):
        terms = [f"x({bal_rows[i]},{bal_cols[j]})" for i in range(m_b)]
        lines.append(f"  ({bal_cols[j]})  " + " + ".join(terms) + f"  =  {_fmt(bal_demand[j])}")
    st.code("\n".join(lines), language="text")

    # No negatividad
    st.markdown("**No negatividad:**")
    st.code("  x(i,j) >= 0   para todo i, j", language="text")

    return bal_costs, bal_supply, bal_demand, bal_rows, bal_cols


# =============================================================================
#  Helper: formato C / C' (cortes) para MST estilo examen
# =============================================================================
def render_mst_cuts_format(edges, all_nodes, start_node=None):
    """
    Ejecuta Prim para extraer la evolución de los cortes (C, C') paso a paso,
    como pide el formato del examen 2010 (Problema 4 inciso d).

    Renderiza una tabla y un bloque de texto estilo examen:
      C = {nodos en árbol}     C' = {nodos faltantes}     ← arista agregada
    """
    from modules.networks import NetworkSolver
    all_nodes_set = set(str(n) for n in all_nodes)
    if not all_nodes_set:
        return
    if start_node is None:
        start_node = sorted(all_nodes_set)[0]
    start_node = str(start_node)

    ns = NetworkSolver(list(all_nodes_set), edges)
    res = ns.solve_mst_prim(start=start_node)
    steps = res.get("steps", [])

    if not steps:
        st.info("No se pudieron computar los pasos de Prim.")
        return

    # Construir las filas C / C' paso a paso
    rows = []
    current_C = {start_node}
    # Estado INICIAL (antes del primer paso): C = {start}, próxima arista = step[0]
    if steps:
        first_edge = steps[0]["Arista elegida"]
        first_w = steps[0]["Peso"]
        rows.append({
            "Estado": "Inicial",
            "C": current_C.copy(),
            "Cprime": all_nodes_set - current_C,
            "Arista a agregar": first_edge,
            "Peso": first_w,
        })

    for i, s in enumerate(steps):
        edge_str = s["Arista elegida"]
        try:
            u_str, v_str = edge_str.split(" — ")
        except Exception:
            try:
                u_str, v_str = edge_str.split("—")
            except Exception:
                continue
        u_str, v_str = u_str.strip(), v_str.strip()
        # Identificar el nodo nuevo (el que no estaba en C)
        new_node = v_str if u_str in current_C else u_str
        current_C.add(new_node)

        # Próxima arista (la del siguiente paso)
        if i + 1 < len(steps):
            next_edge = steps[i+1]["Arista elegida"]
            next_w = steps[i+1]["Peso"]
        else:
            next_edge = "✓ MST completo"
            next_w = ""

        rows.append({
            "Estado": f"Tras paso {i+1}",
            "C": current_C.copy(),
            "Cprime": all_nodes_set - current_C,
            "Arista a agregar": next_edge,
            "Peso": next_w,
        })

    # ── Render ──────────────────────────────────────────────────────────
    st.markdown("### 📝 Formato C / C' (estilo examen 2010 Problema 4-d)")
    st.caption(f"Calculado con Prim empezando desde **{start_node}**. "
               f"Cada renglón es uno de los slots del formato del examen.")

    def _set_str(s):
        if not s:
            return "{ }"
        return "{ " + ", ".join(sorted(s)) + " }"

    # Versión tabla
    tbl_rows = []
    for r in rows:
        tbl_rows.append({
            "Estado": r["Estado"],
            "C  (en árbol)": _set_str(r["C"]),
            "C'  (faltan)": _set_str(r["Cprime"]),
            "Arista a agregar": r["Arista a agregar"],
            "Peso": r["Peso"],
        })
    st.dataframe(pd.DataFrame(tbl_rows), hide_index=True, use_container_width=True)

    # Versión texto plano estilo examen (cópialo directo a la hoja)
    st.markdown("**Copia esto en el formato del examen:**")
    text_lines = []
    for r in rows:
        c_str = _set_str(r["C"])
        cp_str = _set_str(r["Cprime"])
        if r["Arista a agregar"] == "✓ MST completo":
            tail = "  ← MST completo ✓"
        else:
            tail = f"  ← agregar: {r['Arista a agregar']} (peso {r['Peso']})"
        text_lines.append(f"C = {c_str:35s}  C' = {cp_str:30s}{tail}")
    # Rellenar hasta 7 filas como el formato del examen
    while len(text_lines) < 7:
        text_lines.append("C = ________________________________   C' = _____________________________")
    st.code("\n".join(text_lines), language="text")

    return res


# =============================================================================
#  Helper: layout en capas (BFS) + gráfica residual estilo examen
# =============================================================================
def auto_layered_layout(edges, source, sink):
    """
    Layout izquierda→derecha basado en BFS desde source.
    Coloca source a la izquierda, sink a la derecha, otros nodos por capas.
    Para redes conocidas (Problema 3 estilo Hillier con A..G) usa layout manual.
    """
    nodes = set(str(n) for u, v, _ in edges for n in (u, v))
    source, sink = str(source), str(sink)

    # ── Layout manual para la red estándar A-B-C-D-E-F-G ──────────────
    # (estilo examen Problema 3 — B arriba, D abajo, C centro, E top-right, F bot-right)
    standard_7 = {"A", "B", "C", "D", "E", "F", "G"}
    if nodes == standard_7 and source == "A" and sink == "G":
        return {
            "A": (-1.0,  0.0),
            "B": (-0.45, 0.75),
            "D": (-0.45,-0.75),
            "C": ( 0.05, 0.0),
            "E": ( 0.55, 0.75),
            "F": ( 0.55,-0.45),
            "G": ( 1.05, 0.0),
        }

    nodes = list(nodes)

    # BFS desde source para asignar nivel/columna
    levels = {source: 0}
    queue = [source]
    while queue:
        node = queue.pop(0)
        for tup in edges:
            u, v = str(tup[0]), str(tup[1])
            if u == node and v not in levels:
                levels[v] = levels[node] + 1
                queue.append(v)

    # Sink debe estar a la derecha
    max_lvl = max(levels.values()) if levels else 0
    if sink in levels and levels[sink] < max_lvl:
        levels[sink] = max_lvl
    # Nodos no alcanzables: ponlos en el medio
    for n in nodes:
        if n not in levels:
            levels[n] = max(max_lvl // 2, 1)
    max_lvl = max(levels.values()) if levels else 1

    # Agrupar por nivel
    by_level = {}
    for n, lvl in levels.items():
        by_level.setdefault(lvl, []).append(n)

    # Posiciones: x = nivel normalizado, y = distribuido vertical
    positions = {}
    for lvl, nodes_at_level in by_level.items():
        x = -1 + 2 * lvl / max(max_lvl, 1)   # rango [-1, 1]
        n_at = len(nodes_at_level)
        for i, n in enumerate(sorted(nodes_at_level)):
            if n_at == 1:
                y = 0.0
            else:
                y = -1.0 + 2.0 * i / (n_at - 1)
            positions[n] = (x, y)
    return positions


def draw_max_flow_residual_graph(original_edges, residual_summary, source, sink,
                                  title="Red Residual"):
    """
    Dibuja la red residual estilo examen:
      - Layout en capas (source a la izquierda, sink a la derecha)
      - Para cada arco original u→v: una flecha con etiqueta 'fwd | flow'
        (forward residual = capacidad disponible, flow = enviado/cancelable)
      - Arcos saturados (fwd=0) en color naranja/dorado
    """
    import plotly.graph_objects as go
    import math

    pos = auto_layered_layout(original_edges, source, sink)
    nodes = list(pos.keys())

    fig = go.Figure()

    # Index residual_summary por arco para acceso rápido
    res_by_arc = {}
    for r in residual_summary:
        arc_str = r["Arco original"]  # "u → v"
        u_str, v_str = arc_str.split(" → ")
        res_by_arc[(u_str, v_str)] = r

    # Dibujar arcos
    for tup in original_edges:
        u, v = str(tup[0]), str(tup[1])
        if u not in pos or v not in pos:
            continue
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        r = res_by_arc.get((u, v))
        if r is None:
            continue
        fwd = r["Cap. residual (→)"]
        bwd = r["Cap. residual (←)"]

        saturated = fwd <= 1e-6
        arrow_color = "#E67E22" if saturated else "#7F8C8D"   # naranja saturado, gris normal
        width = 3.5 if saturated else 2

        # Flecha forward
        fig.add_annotation(
            x=x1, y=y1, ax=x0, ay=y0,
            xref="x", yref="y", axref="x", ayref="y",
            showarrow=True, arrowhead=3, arrowsize=1.4,
            arrowwidth=width, arrowcolor=arrow_color,
            standoff=18, startstandoff=18
        )

        # Etiquetas estilo examen: forward cerca del ORIGEN (u),
        # backward cerca del DESTINO (v), como en el libro Hillier.
        def _f(x):
            return str(int(x)) if abs(x - int(x)) < 1e-9 else f"{x:.4g}"

        dx, dy = x1 - x0, y1 - y0
        length = max(math.sqrt(dx*dx + dy*dy), 1e-6)
        # Posición del label forward: a 25% del arco desde u
        fx, fy = x0 + 0.25 * dx, y0 + 0.25 * dy
        # Posición del label backward: a 75% del arco desde u
        bx, by = x0 + 0.75 * dx, y0 + 0.75 * dy
        # Offset perpendicular para que las etiquetas no choquen con la flecha
        ox, oy = -dy / length * 0.06, dx / length * 0.06

        # Forward (capacidad disponible) — color naranja si saturado, oscuro si no
        fig.add_annotation(
            x=fx + ox, y=fy + oy,
            text=f"<b>{_f(fwd)}</b>", showarrow=False,
            font=dict(size=13,
                      color="#A04000" if saturated else "#1A1A1A"),
            bgcolor="rgba(255,255,255,0.95)",
            bordercolor=arrow_color, borderwidth=1, borderpad=2
        )
        # Backward (flujo enviado / cancelable)
        fig.add_annotation(
            x=bx + ox, y=by + oy,
            text=f"{_f(bwd)}", showarrow=False,
            font=dict(size=11, color="#566573"),
            bgcolor="rgba(245,245,245,0.85)",
            bordercolor="#BDC3C7", borderwidth=1, borderpad=2
        )

    # Dibujar nodos
    for n in nodes:
        x, y = pos[n]
        is_st = (n == str(source)) or (n == str(sink))
        color = "#27AE60" if n == str(source) else ("#C0392B" if n == str(sink) else "#0068c9")
        fig.add_trace(go.Scatter(
            x=[x], y=[y], mode="markers+text",
            marker=dict(size=42, color=color, line=dict(color="white", width=3)),
            text=[n], textposition="middle center",
            textfont=dict(color="white", size=14, family="Arial Black"),
            showlegend=False, hoverinfo="skip"
        ))

    fig.update_layout(
        height=460, title=title,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(visible=False, range=[-1.3, 1.3]),
        yaxis=dict(visible=False, range=[-1.3, 1.3], scaleanchor="x", scaleratio=1),
        plot_bgcolor="#FAFAFA", paper_bgcolor="white",
    )
    return fig


# =============================================================================
#  Helper: formulación PPL/PE de un problema de asignación
# =============================================================================
def render_assignment_formulation(costs, row_lbl=None, col_lbl=None):
    """
    Renderiza la formulación algebraica de un problema de asignación:
      - Variables binarias x_ij ∈ {0,1}
      - Restricciones: cada recurso a una sola tarea (= 1)
                       cada tarea a lo más a un recurso (≤ 1)
      - Función objetivo: min Z = Σ c_ij x_ij
    """
    import numpy as np
    costs_arr = np.array(costs, dtype=float)
    m, n = costs_arr.shape

    if row_lbl is None or len(row_lbl) != m:
        row_lbl = [f"S{i+1}" for i in range(m)]
    if col_lbl is None or len(col_lbl) != n:
        col_lbl = [f"D{j+1}" for j in range(n)]

    def _short(s):
        return str(s).replace(" ", "")
    short_rows = [_short(r) for r in row_lbl]
    short_cols = [_short(c) for c in col_lbl]

    def _fmt(v):
        try:
            return str(int(v)) if abs(v - int(v)) < 1e-9 else f"{v:.4g}"
        except Exception:
            return str(v)

    st.markdown("#### 📝 Formulación PPL / PE (Asignación)")
    st.caption(f"Variables BINARIAS. {m} recursos × {n} tareas = **{m*n} variables**.")

    # ── Respuestas directas para incisos del examen ─────────────────────────
    st.markdown("##### 📌 Respuestas directas para los incisos del examen")

    # INCISO (a) — Restricciones de asignación (una por recurso/producto)
    st.markdown(f"**📌 Inciso (a) — Restricciones «cada recurso a UNA tarea»** "
                f"(una por recurso — {m} en total):")
    lines_a = []
    for i in range(m):
        terms = [f"{short_rows[i]}{short_cols[j]}" for j in range(n)]
        lines_a.append(f"  ({row_lbl[i]})  " + " + ".join(terms) + " = 1")
    st.code("\n".join(lines_a), language="text")
    st.caption(f"Copia la del recurso que pida el examen (ej. {row_lbl[0]} si pide ese).")

    # INCISO (b) — Restricciones de capacidad (una por tarea/máquina)
    st.markdown(f"**📌 Inciso (b) — Restricciones «cada tarea a LO MÁS un recurso»** "
                f"(una por tarea — {n} en total):")
    lines_b = []
    for j in range(n):
        terms = [f"{short_rows[i]}{short_cols[j]}" for i in range(m)]
        lines_b.append(f"  ({col_lbl[j]})  " + " + ".join(terms) + " <= 1")
    st.code("\n".join(lines_b), language="text")
    st.caption(f"Copia la de la tarea que pida el examen (ej. {col_lbl[0]} si pide ese).")

    # Función objetivo
    st.markdown("**📌 Función objetivo:**")
    obj_terms = []
    for i in range(m):
        for j in range(n):
            c = costs_arr[i, j]
            obj_terms.append(f"{_fmt(c)}·{short_rows[i]}{short_cols[j]}")
    obj_lines = []
    per_line = 4
    for k in range(0, len(obj_terms), per_line):
        chunk = " + ".join(obj_terms[k:k+per_line])
        if k == 0:
            obj_lines.append("min Z = " + chunk)
        else:
            obj_lines.append("        + " + chunk)
    st.code("\n".join(obj_lines), language="text")

    # Variables binarias
    st.markdown("**📌 Variables binarias:**")
    all_vars = ",  ".join([f"{short_rows[i]}{short_cols[j]}"
                            for i in range(m) for j in range(n)])
    st.code(f"  {all_vars}  ∈  {{0, 1}}", language="text")

    st.markdown("---")
    st.markdown("##### 📚 Notación matricial (versión formal)")
    st.code(
        "  x(i,j) = 1  si el recurso i se asigna a la tarea j, 0 si no\n"
        f"  i ∈ {{ {', '.join(row_lbl)} }}\n"
        f"  j ∈ {{ {', '.join(col_lbl)} }}\n\n"
        "  min Z = Σ Σ c(i,j) · x(i,j)\n"
        "  s.a.  Σ_j x(i,j) = 1     ∀ i  (cada recurso a una tarea)\n"
        "        Σ_i x(i,j) ≤ 1    ∀ j  (cada tarea a lo más un recurso)\n"
        "        x(i,j) ∈ {0, 1}    ∀ i, j",
        language="text"
    )


# --- Navigation ---
module = st.radio("Module", ["📚 Tareas", "Linear Programming", "Simplex Tutor", "Transportation", "Networks", "Shortest Path", "Integer Programming", "Dynamic Programming"], horizontal=True, label_visibility="collapsed")


if module == "Linear Programming":
    # --- Auto-save persistence (invisible to user) ---
    from modules.persistence import save_last_session, load_last_session
    
    def auto_save():
        """Save current state automatically when inputs change."""
        st.session_state.lp_solved = False
        shared_data = {
            "obj_type": st.session_state.get("obj_type_radio", "Maximize"),
            "obj_formula": st.session_state.get("obj_formula_input", ""),
            "constraints": st.session_state.get("const_input", "")
        }
        save_last_session("Linear Programming", shared_data)
        # Also save to shared cross-panel key
        save_last_session("LP_Problem", shared_data)
    
    # --- Sidebar for Templates ---
    from modules.templates import TemplateManager
    templates = TemplateManager.get_templates()
    selected_template = st.sidebar.selectbox("Load Template", list(templates.keys()))

    # ── Historial de Problemas ────────────────────────────────────────────────
    if 'lp_history' not in st.session_state:
        st.session_state.lp_history = []

    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 📂 Historial de Problemas")

    _hist = st.session_state.lp_history
    if not _hist:
        st.sidebar.caption("Aún no has resuelto ningún problema. Presiona SOLVE para guardar.")
    else:
        # Clear-all button
        if st.sidebar.button("🗑️ Limpiar historial", key="clear_history", use_container_width=True):
            st.session_state.lp_history = []
            st.rerun()

        for _hi, _entry in enumerate(reversed(_hist)):
            _label = f"[{len(_hist)-_hi}] {_entry['opt_type']} {_entry['obj'][:28]}{'…' if len(_entry['obj'])>28 else ''}"
            _ts    = _entry.get('ts', '')
            with st.sidebar.expander(f"{_label}", expanded=False):
                st.caption(f"🕐 {_ts}")
                st.code(f"{_entry['opt_type']} {_entry['obj']}\n\n{_entry['constraints']}", language="")
                if st.button("▶ Cargar", key=f"hist_load_{_hi}", use_container_width=True):
                    st.session_state.obj_type_radio       = _entry['opt_type']
                    st.session_state.obj_formula_input    = _entry['obj']
                    st.session_state.const_input          = _entry['constraints']
                    st.session_state.last_template        = None  # reset template selector
                    st.rerun()
    
    # Defaults
    default_obj = "Minimize 3x + 5y"
    default_constraints = "x + y >= 10\n2x - y >= 5"
    
    # --- State Management & Initialization ---
    
    # Try to restore from shared session first, then own session, then defaults
    if 'initialized' not in st.session_state:
        # Prefer shared cross-panel key so Simplex changes are picked up too
        shared = load_last_session("LP_Problem")
        last_session = shared if (shared and shared.get("data")) else load_last_session("Linear Programming")
        if last_session and last_session.get("data"):
            st.session_state.obj_type_radio = last_session["data"].get("obj_type", "Maximize")
            st.session_state.obj_formula_input = last_session["data"].get("obj_formula", "3x + 5y")
            st.session_state.const_input = last_session["data"].get("constraints", default_constraints)
        else:
            st.session_state.obj_type_radio = "Maximize"
            st.session_state.obj_formula_input = "3x + 5y"
            st.session_state.const_input = default_constraints
        st.session_state.initialized = True
    
    # Initialize Session Keys if not present (fallback)
    if 'obj_type_radio' not in st.session_state:
        st.session_state.obj_type_radio = "Maximize" # Default
    if 'obj_formula_input' not in st.session_state:
        st.session_state.obj_formula_input = "3x + 5y"
    if 'const_input' not in st.session_state:
        st.session_state.const_input = default_constraints

    # --- Template Loader ---
    if selected_template != "Select Template...":
        t_data = templates[selected_template]
        
        # Only update if the template selection has CHANGED
        if 'last_template' not in st.session_state or st.session_state.last_template != selected_template:
            import re
            raw_obj = t_data['objective']
            
            # Parse Direction
            new_type = "Maximize"
            if "min" in raw_obj.lower() and "max" not in raw_obj.lower():
                new_type = "Minimize"
            
            # Parse Formula
            new_formula = re.sub(r'^(maximize|minimize|max|min)[:\s]*', '', raw_obj, flags=re.IGNORECASE).strip()
            
            # Update Session State (this will update widgets)
            st.session_state.obj_type_radio = new_type
            st.session_state.obj_formula_input = new_formula
            st.session_state.const_input = t_data['constraints']
            
            st.session_state.last_template = selected_template
            auto_save()  # Save template change

    col1, col2, col3 = st.columns([1, 1, 1.3]) # Model, Solution, Graph

    with col1:
        st.subheader("1. Model Input")
        
        # Split Controls: Radio Buttons + Text Input (Bound to Keys) - with auto-save callbacks
        opt_type = st.radio("Optimization Goal", ["Maximize", "Minimize"], horizontal=True, key="obj_type_radio", on_change=auto_save)
        obj_func_only = st.text_input("Objective Function (Z =)", key="obj_formula_input", help="e.g. '3x + 5y'", on_change=auto_save)
        
        st.caption("Constraints (one per line):")
        constraints_txt = st.text_area("Constraints", height=250, key="const_input", on_change=auto_save)
        
        # Non-Negativity Toggle
        non_negativity = st.checkbox("Assume Variables Non-Negative (x, y >= 0)", value=True)
        
        solve_btn = st.button("SOLVE & GRAPH", type="primary", use_container_width=True)

    if solve_btn:
        st.session_state.lp_solved = True
        # ── Save to history ──────────────────────────────────────────────────
        from datetime import datetime as _dt
        _now = _dt.now().strftime("%d/%m %H:%M")
        _new_entry = {
            'opt_type':    opt_type,
            'obj':         obj_func_only.strip(),
            'constraints': constraints_txt.strip(),
            'ts':          _now,
        }
        # Avoid duplicate consecutive entries
        _hist_cur = st.session_state.get('lp_history', [])
        if not _hist_cur or _hist_cur[-1]['obj'] != _new_entry['obj'] or _hist_cur[-1]['constraints'] != _new_entry['constraints']:
            _hist_cur.append(_new_entry)
            # Keep max 30 entries
            st.session_state.lp_history = _hist_cur[-30:]
        
    if st.session_state.get('lp_solved'):
        try:
            # Parse
            # Combine Direction + Function Key
            constraints_list = constraints_txt.split('\n')
            full_obj_input = f"{opt_type} {obj_func_only}"
            parser = LPParser(full_obj_input, constraints_list)
            parsed_data = parser.parse()
            
            # Solve
            solver = LPSolver(parsed_data)
            result = solver.solve(assume_non_negative=non_negativity)
            
            with col2:
                st.subheader("2. Solution")
                if result['success']:
                    # 1. Status Check
                    st.success(f"**Status:** {result['status']}")
                    st.metric(label=f"Objective ({parsed_data['optimization_type'].title()})", value=f"{result['z_value']:.4f}")
                    
                    # 2. Variables Table
                    st.subheader("Variables")
                    var_df = pd.DataFrame(list(result['variables'].items()), columns=['Variable', 'Value'])
                    st.dataframe(var_df, hide_index=True, use_container_width=True)
                    
                    # Prepare DataFrames for Full-Width Report SECTION
                    const_df = pd.DataFrame(result['constraints'])
                    
                    vert_csv = ""
                    vert_df = None
                    if "vertices" in result and result["vertices"] is not None and len(result["vertices"]) > 0:
                        vert_df = pd.DataFrame(result["vertices"])
                        vert_csv = "\n\nVertices:\n" + vert_df.to_csv(index=False)
                    
                    # Export String Construction
                    csv_buffer = ""
                    csv_buffer += "Summary\n"
                    csv_buffer += f"Status,{result['status']}\n"
                    csv_buffer += f"Objective,{result['z_value']}\n\n"
                    
                    csv_buffer += "Variables:\n" + var_df.to_csv(index=False) + "\n"
                    csv_buffer += "Constraints:\n" + const_df.to_csv(index=False)
                    csv_buffer += vert_csv
                    
                    st.download_button("Download Full Report (CSV)", csv_buffer, "lp_solution_report.csv", "text/csv")
                    
                elif result['status'] == 'Unbounded':
                    st.warning(f"**Status:** {result['status']}")
                    st.info("The problem is **Unbounded**.")
                    st.markdown("""
                    This means the constraints do not enclose the feasible region in the direction of optimization. 
                    - For **Maximization**: The objective value can increase to infinity.
                    - For **Minimization**: The objective value can decrease to negative infinity.
                    
                    **Check:**
                    - Did you forget a constraint (e.g. `x <= 100`)?
                    - Is the optimization direction correct?
                    """)
                    
                elif result['status'] == 'Infeasible':
                    st.error(f"**Status:** {result['status']}")
                    st.markdown("""
                    The problem is **Infeasible**. 
                    There is no solution that satisfies **all** constraints simultaneously.
                    
                    **Check:**
                    - Are there conflicting constraints? (e.g., `x >= 10` and `x <= 5`)
                    - Did you set the wrong bounds?
                    """)
                    
                else:
                    st.error(f"Solver Failed: {result['message']}")
                    st.warning(f"Status: {result['status']}")

            selected_x, selected_y = None, None
            with col3:
                st.subheader("3. Graph")
                if len(parsed_data['variables']) > 2:
                    st.info(f"Graph disabled — {len(parsed_data['variables'])} variables detected.")
                elif len(parsed_data['variables']) < 2:
                    st.warning("Graph unavailable.")
                else:
                    st.caption("👇 Ver gráfica a ancho completo abajo")

            # ── Gráfica ancho completo ──────────────────────────────────────
            if len(parsed_data['variables']) == 2:
                st.divider()
                st.subheader("3. 📊 Gráfica")
                try:
                    from modules.plotting_2d import LPPlotter
                    plotter = LPPlotter(parsed_data, result)
                    fig = plotter.plot()
                    event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", selection_mode="points")

                    if getattr(event, "selection", None) and event.selection.get("points"):
                        selected_x = event.selection["points"][0].get("x")
                        selected_y = event.selection["points"][0].get("y")
                    elif isinstance(event, dict) and event.get("selection", {}).get("points"):
                        selected_x = event["selection"]["points"][0].get("x")
                        selected_y = event["selection"]["points"][0].get("y")
                except Exception as e:
                    st.error(f"Graph Error: {e}")


            # --- Full Width Report Section ---
            if result['success']:
                st.divider()
                st.subheader("Detailed Analysis")
                
                # Constraints Analysis - Full Width
                st.markdown("### Constraints Analysis")
                st.dataframe(const_df, hide_index=True, use_container_width=True)

                # ── Forma Ordenada–Origen (solo para 2 variables) ────────────
                if len(parsed_data['variables']) == 2:
                    v1n, v2n = parsed_data['variables'][0], parsed_data['variables'][1]
                    c1_obj = parsed_data['original_c'][0] if len(parsed_data['original_c']) > 0 else 0
                    c2_obj = parsed_data['original_c'][1] if len(parsed_data['original_c']) > 1 else 0

                    def _frac(num, den, var):
                        """Return a clean 'slope·var' string."""
                        if abs(den) < 1e-9:
                            return None          # can't solve for x2
                        m = -num / den
                        if abs(m) < 1e-9:
                            return "0"
                        if abs(m - round(m)) < 1e-9:
                            m_str = str(int(round(m)))
                        else:
                            # try to show as fraction
                            from fractions import Fraction
                            fr = Fraction(m).limit_denominator(100)
                            m_str = str(fr) if fr.denominator != 1 else str(fr.numerator)
                        return f"{m_str}{var}"

                    lines = []
                    for i, _ci in enumerate(parsed_data.get('constraints_info', [])):
                        _orig = _ci['original']
                        a1 = _orig['lhs'].get(v1n, 0.0)
                        a2 = _orig['lhs'].get(v2n, 0.0)
                        b  = _orig['rhs']
                        ct = _orig['op']

                        if abs(a2) < 1e-9:
                            # No x2 term — constraint is purely on x1
                            if abs(a1) < 1e-9:
                                expr = f"0 {ct} {b:.4g}"
                            else:
                                lim = b / a1
                                sym = "≤" if (ct == "<=" and a1 > 0) or (ct == ">=" and a1 < 0) else "≥"
                                expr = f"{v1n} {sym} {lim:.4g}".replace(".0 ", " ")
                            lines.append(f"**R{i+1}:** {expr}  *(no tiene {v2n})*")
                        else:
                            b_val = b / a2
                            slope_str = _frac(a1, a2, v1n)
                            b_str = str(int(b_val)) if b_val == int(b_val) else f"{b_val:.4g}"

                            # inequality direction when dividing by a2 (sign may flip)
                            if ct == "<=":
                                op_str = "≤" if a2 > 0 else "≥"
                            elif ct == ">=":
                                op_str = "≥" if a2 > 0 else "≤"
                            else:
                                op_str = "="

                            if slope_str and slope_str != "0":
                                _abs_b = abs(b_val)
                                _abs_b_str = str(int(_abs_b)) if _abs_b == int(_abs_b) else f"{_abs_b:.4g}"
                                rhs = f"{slope_str} + {b_str}" if b_val >= 0 else f"{slope_str} - {_abs_b_str}"
                            else:
                                rhs = b_str

                            lines.append(f"**R{i+1}:** {v2n} {op_str} {rhs}")

                    # Objective iso-profit line
                    Z_opt = result.get('objective', 0)
                    if abs(c2_obj) > 1e-9:
                        slope_obj = _frac(c1_obj, c2_obj, v1n)
                        b_obj = Z_opt / c2_obj
                        b_obj_str = str(int(b_obj)) if b_obj == int(b_obj) else f"{b_obj:.4g}"
                        if slope_obj and slope_obj != "0":
                            _abs_bo = abs(b_obj)
                            _abs_bo_str = str(int(_abs_bo)) if _abs_bo == int(_abs_bo) else f"{_abs_bo:.4g}"
                            obj_rhs = f"{slope_obj} + {b_obj_str}" if b_obj >= 0 else f"{slope_obj} - {_abs_bo_str}"
                        else:
                            obj_rhs = b_obj_str
                        z_str = f"{Z_opt:g}"
                        lines.append(f"**FO (Z={z_str}):** {v2n} = {obj_rhs}  *(pendiente = -{c1_obj/c2_obj:.4g})*")

                    # Optimality range from vertices table
                    opt_range_lines = []
                    if vert_df is not None and '_c1_min' in vert_df.columns:
                        opt_rows = vert_df[vert_df.get('Optimal', False) == True] if 'Optimal' in vert_df.columns else vert_df.iloc[[]]
                        if not opt_rows.empty:
                            r = opt_rows.iloc[0]
                            def _bnd(v):
                                if v == float('inf'):   return "∞"
                                if v == float('-inf'):  return "-∞"
                                return f"{float(v):.4g}"
                            opt_range_lines.append(
                                f"**Rango de optimalidad** (en el vértice óptimo):\n"
                                f"- c₁ ({v1n}) ∈ [{_bnd(r.get('_c1_min', '-∞'))}, {_bnd(r.get('_c1_max', '∞'))}]\n"
                                f"- c₂ ({v2n}) ∈ [{_bnd(r.get('_c2_min', '-∞'))}, {_bnd(r.get('_c2_max', '∞'))}]"
                            )

                    with st.expander("📐 Forma Ordenada–Origen  (despejando " + v2n + ")", expanded=False):
                        for ln in lines:
                            st.markdown(ln)
                        if opt_range_lines:
                            st.markdown("---")
                            for ln in opt_range_lines:
                                st.markdown(ln)
                        st.caption(
                            "Cada restricción se expresó despejando " + v2n +
                            ". La línea de la FO muestra la pendiente de las curvas de nivel. "
                            "El rango de optimalidad indica cuánto pueden variar c₁ y c₂ sin cambiar la base óptima."
                        )

                # --- Simplex Iteration Sequence Table ---
                st.markdown("### Secuencia del Método Simplex")
                try:
                    from modules.simplex_tutor import SimplexTutor as _ST
                    _c      = list(parsed_data['original_c'])
                    _A_rows = []
                    _b_vals = []
                    _ctypes = []
                    for _ci in parsed_data.get('constraints_info', []):
                        _orig = _ci['original']
                        _row  = [_orig['lhs'].get(v, 0.0) for v in parsed_data['variables']]
                        _A_rows.append(_row)
                        _b_vals.append(_orig['rhs'])
                        _ctypes.append(_orig['op'])

                    _tutor = _ST(
                        c=_c,
                        A=_A_rows,
                        b=_b_vals,
                        constraint_types=_ctypes,
                        optimization_type=parsed_data['optimization_type'],
                        var_names=parsed_data['variables'],
                    )
                    _seq = _tutor.run_to_completion()

                    if _seq:
                        import pandas as _pd_seq
                        seq_df = _pd_seq.DataFrame(_seq)

                        # Pretty-format numbers
                        def _fmt_seq(v):
                            if not isinstance(v, (int, float)): return v
                            if v == int(v): return str(int(v))
                            return f"{v:.4f}".rstrip('0').rstrip('.')
                        num_seq_cols = [c for c in seq_df.columns if seq_df[c].dtype in ['float64', 'int64']]

                        # Highlight the final (optimal) row in the same gold colour as the plot
                        def _style_seq(row):
                            if row.get('Estado', '') == 'Optimal' or (
                                row.name == len(_seq) - 1 and row.get('Entra', '—') == '—'
                                and row.get('Iteración', 0) > 0
                            ):
                                return ['background-color: #FFD700; font-weight: bold; color: #5a4000'] * len(row)
                            elif row.get('Iteración', -1) == 0:
                                return ['background-color: #f0f0f0; color: #555'] * len(row)
                            return [''] * len(row)

                        styled_seq = (seq_df.style
                                      .apply(_style_seq, axis=1)
                                      .format({c: _fmt_seq for c in num_seq_cols}))
                        st.dataframe(styled_seq, hide_index=True, use_container_width=True)
                        st.caption("🔹 Fila inicial (Iteración 0) = solución básica inicial. "
                                   "🟡 Última fila resaltada = solución óptima.")
                    else:
                        st.info("No se generaron iteraciones.")
                except Exception as _seq_err:
                    st.warning(f"No se pudo generar la secuencia simplex: {_seq_err}")

                # --- Análisis de Sensibilidad (Rangos) ---
                st.markdown("### Análisis de Sensibilidad (Rangos)")
                try:
                    if '_tutor' in locals():
                        _sa = _tutor.get_sensitivity_analysis()
                        if _sa is not None:
                            import pandas as _pd_sa
                            
                            st.markdown("**Rangos para Coeficientes de la Función Objetivo ($c_j$)**")
                            _o_df_sa = _pd_sa.DataFrame(_sa['objective_ranges'])
                            
                            def _fmt_inf(v):
                                if v == float('inf'): return '∞'
                                if v == float('-inf'): return '-∞'
                                if isinstance(v, (int, float)):
                                    return str(int(v)) if v == int(v) else f"{v:.4g}"
                                return v
                                
                            _o_cols = [c for c in _o_df_sa.columns if _o_df_sa[c].dtype in ['float64', 'int64']]
                            st.dataframe(
                                _o_df_sa.style.format({c: _fmt_inf for c in _o_cols}),
                                hide_index=True, use_container_width=True
                            )
                            st.caption("Muestra cuánto puede cambiar un coeficiente en la función objetivo antes de que cambie la solución óptima (base actual óptima).")

                            st.markdown("**Rangos para Valores del Lado Derecho de las Restricciones (RHS - $b_i$)**")
                            _rhs_df_sa = _pd_sa.DataFrame(_sa['rhs_ranges'])
                            _r_cols = [c for c in _rhs_df_sa.columns if _rhs_df_sa[c].dtype in ['float64', 'int64']]
                            st.dataframe(
                                _rhs_df_sa.style.format({c: _fmt_inf for c in _r_cols}),
                                hide_index=True, use_container_width=True
                            )
                            st.caption("Muestra el límite de aumento/disminución del lado derecho para que los precios sombra (variables básicas) sigan siendo válidos (factibilidad base).")
                        else:
                            st.info("La solución no alcanzó un estado óptimo, por lo que no hay análisis de sensibilidad disponible.")
                except Exception as _sa_err:
                    st.warning(f"No se pudo calcular el análisis de sensibilidad: {_sa_err}")


                # Vertices - Full Width
                if vert_df is not None:
                    if len(parsed_data['variables']) == 2:
                        st.markdown("### Vértices de Intersección (2D)")
                    else:
                        st.markdown(f"### Vértices de Intersección ({len(parsed_data['variables'])}D)")

                    # Build optimal-vertex color map (matches plot colors)
                    PLOT_COLORS = ['gold', 'red', 'lightgreen', 'cyan', 'orange']
                    # CSS-friendly versions and contrasting text colors
                    OPT_BG = [
                        ('#FFD700', '#5a4000'),   # gold
                        ('#FF4444', '#5a0000'),   # red
                        ('#90EE90', '#1a4d1a'),   # lightgreen
                        ('#00CED1', '#004d50'),   # cyan
                        ('#FFA500', '#5a3000'),   # orange
                    ]

                    # Assign a color index to each optimal vertex in order of appearance
                    opt_color_map = {}  # (v1_val, v2_val) -> color_idx
                    opt_idx = 0
                    if len(parsed_data['variables']) == 2:
                        v1k, v2k = parsed_data['variables'][0], parsed_data['variables'][1]
                        for _vrow in (result.get('vertices') or []):
                            if _vrow.get('Optimal') and _vrow.get('Factible') == 'Sí':
                                key = (round(float(_vrow.get(v1k, 0)), 4),
                                       round(float(_vrow.get(v2k, 0)), 4))
                                if key not in opt_color_map:
                                    opt_color_map[key] = opt_idx % len(OPT_BG)
                                    opt_idx += 1

                    # Add ⭐ marker column and highlight optimal rows
                    display_vert = vert_df.copy()
                    # Label each optimal vertex with its number
                    def _opt_label(row):
                        if not row.get('Optimal'):
                            return ''
                        if len(parsed_data['variables']) == 2:
                            key = (round(float(row.get(v1k, 0)), 4), round(float(row.get(v2k, 0)), 4))
                            cidx = opt_color_map.get(key, 0)
                            if opt_idx > 1:
                                return f'⭐ Óptimo {cidx + 1}'
                        return '⭐ Óptimo'
                    display_vert.insert(0, '  ', display_vert.apply(_opt_label, axis=1))

                    # Drop the raw boolean column from view
                    cols_to_show = [c for c in display_vert.columns if c != 'Optimal']
                    display_vert = display_vert[cols_to_show]

                    def _highlight_optimal(row):
                        styles = [''] * len(row)
                        lbl = row.get('  ', '')
                        if lbl.startswith('⭐ Óptimo'):
                            if len(parsed_data['variables']) == 2:
                                key = (round(float(row.get(v1k, 0)), 4),
                                       round(float(row.get(v2k, 0)), 4))
                                cidx = opt_color_map.get(key, 0)
                            else:
                                cidx = 0
                            bg, fg = OPT_BG[cidx % len(OPT_BG)]
                            styles = [f'background-color: {bg}; font-weight: bold; color: {fg}'] * len(row)
                        elif selected_x is not None and selected_y is not None and len(parsed_data['variables']) == 2:
                            try:
                                vx = float(row.get(parsed_data['variables'][0], 0))
                                vy = float(row.get(parsed_data['variables'][1], 0))
                                if abs(vx - selected_x) < 1e-4 and abs(vy - selected_y) < 1e-4:
                                    styles = ['background-color: #fff3cd; font-weight: bold; color: #856404'] * len(row)
                            except: pass
                        return styles

                    def _fmt_num(v):
                        """Clean number display: 12000.0→12000, 0.666667→0.6667, strings unchanged."""
                        if not isinstance(v, (int, float)):
                            return v
                        if v == int(v):
                            return str(int(v))
                        return f"{v:.4f}".rstrip('0').rstrip('.')
                    # Create clean display vertices dataframe
                    display_vert_df = display_vert.copy()

                    # Apply format only to numeric columns
                    num_cols = [c for c in display_vert_df.columns if display_vert_df[c].dtype in ['float64', 'int64']]
                    fmt_dict = {c: _fmt_num for c in num_cols}
                    
                    # Get variable names for range_cols
                    v1 = parsed_data['variables'][0] if len(parsed_data['variables']) >= 1 else 'X1'
                    v2 = parsed_data['variables'][1] if len(parsed_data['variables']) >= 2 else 'X2'

                    # Create a separate ranges dataframe
                    range_cols = [v1, v2, 'Factible', '_c1c2_min', '_c1c2_max', '_c1_min', '_c1_max', '_c2_min', '_c2_max']
                    
                    # Ensure columns exist before filtering
                    existing_range_cols = [c for c in range_cols if c in vert_df.columns]
                    ranges_df = vert_df[existing_range_cols].copy()
                    
                    # Drop the hidden columns from the main display dataframe
                    hidden_cols = ['_c1c2_min', '_c1c2_max', '_c1_min', '_c1_max', '_c2_min', '_c2_max']
                    for col in hidden_cols:
                        if col in display_vert_df.columns:
                            display_vert_df = display_vert_df.drop(columns=[col])

                    styled_df = (display_vert_df.style
                                 .apply(_highlight_optimal, axis=1)
                                 .format(fmt_dict))
                    st.dataframe(styled_df, hide_index=True, use_container_width=True)
                    
                    # Render the separate Ranges table
                    if False and len(parsed_data['variables']) == 2 and any(col in vert_df.columns for col in hidden_cols):
                        st.markdown("### Rangos de Optimidad por Vértice ($c_1, c_2$)")
                        
                        # Filter to only feasible rows for ranges
                        ranges_df = ranges_df[ranges_df['Factible'] == 'Sí'].copy()
                        ranges_df = ranges_df.drop(columns=['Factible'])
                        
                        # Add optimal marker to ranges df using the same numbered labels
                        feasible_vert = vert_df[vert_df['Factible'] == 'Sí'].copy()
                        def _opt_label_ranges(row):
                            if not row.get('Optimal'):
                                return ''
                            key = (round(float(row.get(v1k, 0)), 4), round(float(row.get(v2k, 0)), 4))
                            cidx = opt_color_map.get(key, 0)
                            if opt_idx > 1:
                                return f'⭐ Óptimo {cidx + 1}'
                            return '⭐ Óptimo'
                        ranges_df.insert(0, '  ', feasible_vert.apply(_opt_label_ranges, axis=1).values)
                        
                        # Format the infinity bounds
                        def fmt_bound(val):
                            if val == "" or pd.isna(val): return ""
                            if val == float('inf'): return "∞"
                            if val == -float('inf'): return "-∞"
                            return f"{float(val):.4f}"
                            
                        # Keep coordinates for highlighting logic
                        ranges_df['Rango c1/c2'] = ranges_df.apply(lambda r: f"[{fmt_bound(r['_c1c2_min'])}, {fmt_bound(r['_c1c2_max'])}]", axis=1)
                        ranges_df['Rango c1'] = ranges_df.apply(lambda r: f"[{fmt_bound(r['_c1_min'])}, {fmt_bound(r['_c1_max'])}]", axis=1)
                        ranges_df['Rango c2'] = ranges_df.apply(lambda r: f"[{fmt_bound(r['_c2_min'])}, {fmt_bound(r['_c2_max'])}]", axis=1)

                        # ── Vértice + Z* columns ──────────────────────────────
                        _oc  = parsed_data.get('original_c', [])
                        _c1v = float(_oc[0]) if len(_oc) > 0 else 0.0
                        _c2v = float(_oc[1]) if len(_oc) > 1 else 0.0

                        def _fmtc(val):
                            fv = float(val)
                            return str(int(fv)) if fv == int(fv) else f"{fv:.4g}"

                        ranges_df['Vértice'] = ranges_df.apply(
                            lambda r: f"({v1}={_fmtc(r[v1])}, {v2}={_fmtc(r[v2])})", axis=1
                        )
                        ranges_df['Z* (óptimo)'] = ranges_df.apply(
                            lambda r: (
                                lambda z: f"Z = {int(z)}" if z == int(z) else f"Z = {z:.4g}"
                            )(_c1v * float(r[v1]) + _c2v * float(r[v2])),
                            axis=1
                        )
                        # ──────────────────────────────────────────────────────

                        # Drop the raw hidden columns
                        ranges_df = ranges_df.drop(columns=[c for c in hidden_cols if c in ranges_df.columns])
                        
                        styled_ranges = (ranges_df.style
                                         .apply(_highlight_optimal, axis=1)
                                         .format(fmt_dict))
                        
                        # Drop the Optimal column and coords from actual view, just keep them for styling
                        # Actually Streamlit style.format requires columns to be present. Instead we hide them.
                        st.dataframe(styled_ranges, hide_index=True, use_container_width=True, 
                                     column_config={"  ": None, v1: None, v2: None})
                        
                        st.info("💡 **Tip:** Dale clic a cualquier vértice factible en la gráfica para resaltarlo y ver sus rangos válidos para los coeficientes de la función objetivo.")

                        # ── Línea de rangos de optimalidad (c1) ──────────────
                        try:
                            import plotly.graph_objects as _go

                            # Collect segment data from feasible_vert + ranges already computed
                            _segs = []
                            for _, _fr in feasible_vert.iterrows():
                                _x1v  = float(_fr.get(v1, 0))
                                _x2v  = float(_fr.get(v2, 0))
                                _lo   = float(_fr.get('_c1_min', -float('inf')))
                                _hi   = float(_fr.get('_c1_max',  float('inf')))
                                _z    = _c1v * _x1v + _c2v * _x2v
                                _is_opt = bool(_fr.get('Optimal', False))
                                _segs.append({
                                    'lo': _lo, 'hi': _hi,
                                    'label': f"({v1}={_fmtc(_x1v)}, {v2}={_fmtc(_x2v)})\nZ={int(_z) if _z==int(_z) else f'{_z:.4g}'}",
                                    'is_opt': _is_opt,
                                    'z': _z,
                                })

                            if _segs:
                                # --- determine display axis limits ---
                                _finite_lo = [s['lo'] for s in _segs if s['lo'] > -1e9]
                                _finite_hi = [s['hi'] for s in _segs if s['hi'] <  1e9]
                                _all_finite = _finite_lo + _finite_hi
                                if _all_finite:
                                    _ax_min = min(_all_finite)
                                    _ax_max = max(_all_finite)
                                    _margin = (_ax_max - _ax_min) * 0.18 or 5
                                else:
                                    _ax_min, _ax_max, _margin = 0, 100, 10
                                _disp_lo = _ax_min - _margin
                                _disp_hi = _ax_max + _margin

                                # Clip infinities to display range
                                PALETTE = ['#2196F3','#FF9800','#4CAF50','#E91E63','#9C27B0','#00BCD4']
                                OPT_CLR = '#FFD700'  # gold for optimal

                                _fig_line = _go.Figure()
                                for _si, _s in enumerate(_segs):
                                    _lo_d = max(_s['lo'], _disp_lo) if _s['lo'] > -1e9 else _disp_lo
                                    _hi_d = min(_s['hi'], _disp_hi) if _s['hi'] <  1e9 else _disp_hi
                                    _clr = OPT_CLR if _s['is_opt'] else PALETTE[_si % len(PALETTE)]
                                    _y   = 0  # all on same axis

                                    # Filled segment bar (thin horizontal bar via scatter fill)
                                    _fig_line.add_trace(_go.Scatter(
                                        x=[_lo_d, _lo_d, _hi_d, _hi_d, _lo_d],
                                        y=[-0.35, 0.35, 0.35, -0.35, -0.35],
                                        fill='toself',
                                        fillcolor=_clr,
                                        line=dict(color='white', width=1.5),
                                        opacity=0.85,
                                        mode='lines',
                                        showlegend=False,
                                        hoverinfo='skip',
                                    ))

                                    # Label inside segment
                                    _mid = (_lo_d + _hi_d) / 2
                                    _fig_line.add_trace(_go.Scatter(
                                        x=[_mid], y=[0],
                                        mode='text',
                                        text=[_s['label']],
                                        textfont=dict(
                                            size=10,
                                            color='#1a1a1a' if _s['is_opt'] else 'white',
                                        ),
                                        showlegend=False,
                                        hovertemplate=f"<b>{_s['label'].replace(chr(10),'  ')}</b><extra></extra>",
                                    ))

                                    # Boundary tick marks
                                    for _bnd, _bnd_val in [('lo', _s['lo']), ('hi', _s['hi'])]:
                                        _bnd_disp = _lo_d if _bnd == 'lo' else _hi_d
                                        _bnd_lbl  = ('−∞' if _s['lo'] <= -1e9 else f"{_s['lo']:.4g}") if _bnd == 'lo' \
                                                    else ('∞'  if _s['hi'] >=  1e9 else f"{_s['hi']:.4g}")
                                        _fig_line.add_annotation(
                                            x=_bnd_disp, y=-0.55,
                                            text=_bnd_lbl,
                                            showarrow=False,
                                            font=dict(size=9, color='#555'),
                                            yanchor='top',
                                        )
                                        _fig_line.add_shape(
                                            type='line',
                                            x0=_bnd_disp, x1=_bnd_disp, y0=-0.35, y1=0.35,
                                            line=dict(color='white', width=2),
                                        )

                                # Current c1 value marker
                                if _disp_lo <= _c1v <= _disp_hi:
                                    _fig_line.add_shape(
                                        type='line',
                                        x0=_c1v, x1=_c1v, y0=-0.42, y1=0.42,
                                        line=dict(color='black', width=2, dash='dot'),
                                    )
                                    _fig_line.add_annotation(
                                        x=_c1v, y=0.50,
                                        text=f"c₁ actual = {_fmtc(_c1v)}",
                                        showarrow=False,
                                        font=dict(size=9, color='black', family='monospace'),
                                        yanchor='bottom',
                                    )

                                _fig_line.update_layout(
                                    title=dict(
                                        text=f"Rango de optimalidad — eje c₁ ({v1})",
                                        font=dict(size=13),
                                        x=0.0,
                                    ),
                                    xaxis=dict(
                                        title=f"c₁ (coeficiente de {v1})",
                                        range=[_disp_lo, _disp_hi],
                                        showgrid=True,
                                        gridcolor='#eee',
                                        zeroline=False,
                                    ),
                                    yaxis=dict(visible=False, range=[-0.85, 0.85]),
                                    height=160,
                                    margin=dict(l=10, r=10, t=40, b=40),
                                    plot_bgcolor='#f8f9fa',
                                    paper_bgcolor='white',
                                )
                                st.plotly_chart(_fig_line, use_container_width=True)

                        except Exception as _lnErr:
                            st.caption(f"No se pudo construir la línea de rangos: {_lnErr}")
                        # ──────────────────────────────────────────────────────


                # ── DUALIDAD (siempre visible, incluso si infactible) ─────────

                with st.expander("🔄 Dualidad – Problema Dual", expanded=False):
                    try:
                        # Gather primal data
                        _dc_raw = list(parsed_data['original_c'])
                        _dA, _db, _dct = [], [], []
                        for _ci in parsed_data.get('constraints_info', []):
                            _orig = _ci['original']
                            _dA.append([_orig['lhs'].get(v, 0.0) for v in parsed_data['variables']])
                            _db.append(_orig['rhs'])
                            _dct.append(_orig['op'])

                        dual_info = build_dual(
                            c=_dc_raw,
                            A=_dA,
                            b=_db,
                            constraint_types=_dct,
                            optimization_type=parsed_data['optimization_type'],
                            var_names=parsed_data['variables'],
                        )

                        # ─ Section 1: Formulation side-by-side ─────────────
                        dc1, dc2 = st.columns(2)

                        with dc1:
                            st.markdown("**📌 Primal**")
                            opt_str = "Max" if parsed_data['optimization_type'] == 'max' else "Min"
                            c_terms = " + ".join(
                                f"{int(v) if v==int(v) else v}{n}"
                                for v, n in zip(_dc_raw, parsed_data['variables'])
                            )
                            st.code(f"{opt_str} Z = {c_terms}\n\nSujeto a:", language="")
                            for i, (row, rhs, ct) in enumerate(zip(_dA, _db, _dct)):
                                lhs_str = " + ".join(
                                    f"{int(row[j]) if row[j]==int(row[j]) else row[j]}{parsed_data['variables'][j]}"
                                    for j in range(len(row)) if abs(row[j]) > 1e-9
                                )
                                rhs_str = str(int(rhs)) if rhs == int(rhs) else str(rhs)
                                st.markdown(f"&nbsp;&nbsp;`R{i+1}: {lhs_str} {ct} {rhs_str}`", unsafe_allow_html=True)
                            st.markdown(", ".join(f"{v} ≥ 0" for v in parsed_data['variables']))

                        with dc2:
                            st.markdown("**📌 Dual**")
                            st.code(f"{dual_info['dual_obj_str']}\n\nSujeto a:", language="")
                            for i, cs in enumerate(dual_info['dual_constraints_str']):
                                st.markdown(f"&nbsp;&nbsp;`{cs}`", unsafe_allow_html=True)
                            st.markdown(", ".join(dual_info['dual_var_restr_str']))

                        # ─ Section 2: SOB Conversion Table ──────────────────
                        st.markdown("##### 📋 Tabla de Conversión (Tabla Mágica S.O.B.)")
                        import pandas as _pd_dual
                        sob_df = _pd_dual.DataFrame(dual_info['sob_rows'])
                        st.dataframe(sob_df, hide_index=True, use_container_width=True)

                        # ─ Section 3: Dual Simplex Iterations ───────────────
                        st.markdown("##### 🔢 Secuencia Simplex del Problema Dual")
                        _ds_result = solve_dual_simplex(dual_info)
                        if _ds_result['error']:
                            st.warning(f"No se pudo ejecutar el Simplex en el dual: {_ds_result['error']}")
                        elif _ds_result['iterations']:
                            _ds_df = _pd_dual.DataFrame(_ds_result['iterations'])

                            def _fmt_ds(v):
                                if not isinstance(v, (int, float)): return v
                                if v == int(v): return str(int(v))
                                return f"{v:.4f}".rstrip('0').rstrip('.')

                            def _style_ds(row):
                                if row.get('Estado', '') == 'Optimal' or (
                                    row.name == len(_ds_result['iterations']) - 1
                                    and row.get('Entra', '—') == '—'
                                    and row.get('Iteración', 0) > 0
                                ):
                                    return ['background-color: #FFD700; font-weight: bold; color: #5a4000'] * len(row)
                                elif row.get('Iteración', -1) == 0:
                                    return ['background-color: #f0f0f0; color: #555'] * len(row)
                                return [''] * len(row)

                            _num_ds_cols = [c for c in _ds_df.columns if _ds_df[c].dtype in ['float64','int64']]
                            _styled_ds = (_ds_df.style
                                          .apply(_style_ds, axis=1)
                                          .format({c: _fmt_ds for c in _num_ds_cols}))
                            st.dataframe(_styled_ds, hide_index=True, use_container_width=True)
                            st.caption(
                                "🔹 Fila Iteración 0 = solución básica inicial del dual.  "
                                "🟡 Fila resaltada = solución óptima del dual (W*).  "
                                "Las variables de decisión del dual son los precios sombra (yi)."
                            )
                        else:
                            st.info("No se generaron iteraciones para el dual.")
                        st.markdown("##### ✅ Solución del Dual")
                        dsol = dual_info['dual_solution']
                        if dsol['success']:
                            dy_vals = dsol['y']
                            W_val   = dsol['W']
                            Z_val   = result.get('objective', None)

                            # Shadow prices table
                            sp_rows = []
                            for i, (yn, yv) in enumerate(zip(dual_info['dual_var_names'], dy_vals)):
                                ct_label = _dct[i]
                                sp_rows.append({
                                    'Variable Dual': yn,
                                    'Restricción Primal': f"R{i+1}  ({ct_label})",
                                    'Precio Sombra (y*)':  round(yv, 6),
                                    'Interpretación': (
                                        f"Cada unidad extra en R{i+1} cambia Z en {round(yv,4)}"
                                        if abs(yv) > 1e-9
                                        else f"R{i+1} no activa — no afecta Z"
                                    ),
                                })
                            sp_df = _pd_dual.DataFrame(sp_rows)

                            def _hi_shadow(row):
                                if abs(row.get('Precio Sombra (y*)', 0)) > 1e-9:
                                    return ['background-color: #d4edda; color: #155724'] * len(row)
                                return ['background-color: #f8f9fa; color: #6c757d'] * len(row)

                            st.dataframe(
                                sp_df.style.apply(_hi_shadow, axis=1),
                                hide_index=True, use_container_width=True
                            )

                            # Duality theorem verification
                            st.markdown("##### 🔗 Teorema de Dualidad Fuerte")
                            if Z_val is not None:
                                diff = abs(Z_val - W_val)
                                check = "✅ Z\\* = W\\*" if diff < 1e-4 else f"⚠️ diferencia = {diff:.6f}"
                                cols_d = st.columns(3)
                                cols_d[0].metric("Z\\* (Primal)", f"{Z_val:,.4f}")
                                cols_d[1].metric("W\\* (Dual)",   f"{W_val:,.4f}")
                                cols_d[2].metric("Verificación", check)

                            # Complementary slackness
                            st.markdown("##### ↔️ Holgura Complementaria")
                            cs_rows = complementary_slackness(
                                primal_x=[result['variables'].get(v, 0) for v in parsed_data['variables']],
                                primal_A=_dA,
                                primal_b=_db,
                                primal_ct=_dct,
                                dual_y=dy_vals,
                                dual_A=dual_info['dual_A'],
                                dual_b=dual_info['dual_b'],
                                dual_ct=dual_info['dual_constraint_types'],
                            )
                            cs_df = _pd_dual.DataFrame(cs_rows)

                            def _hi_cs(row):
                                if row.get('yi·slack = 0 ?', '') == '✅':
                                    return ['background-color: #d4edda'] * len(row)
                                return ['background-color: #f8d7da'] * len(row)

                            st.dataframe(
                                cs_df.style.apply(_hi_cs, axis=1),
                                hide_index=True, use_container_width=True
                            )
                            st.caption("🟢 Verde = condición de holgura complementaria satisfecha (yi⋅slack = 0).")

                            # ── Gráfica de la Solución Dual ──────────────────
                            st.markdown("##### 📊 Gráfica de la Solución Dual")
                            try:
                                import plotly.graph_objects as _go_d
                                import numpy as _np_d

                                _m_dual = len(dy_vals)         # número de vars dual = # restricciones primal
                                _n_dual = len(dual_info['dual_b'])  # número restricciones dual = # vars primal

                                # ── 1. Siempre: gráfica de barras de precios sombra ──────
                                _bar_colors = ['#FFD700' if abs(v) > 1e-9 else '#BDBDBD' for v in dy_vals]
                                _fig_bar = _go_d.Figure(_go_d.Bar(
                                    x=dual_info['dual_var_names'],
                                    y=[round(v, 6) for v in dy_vals],
                                    marker_color=_bar_colors,
                                    text=[f"{v:.4g}" for v in dy_vals],
                                    textposition='outside',
                                    hovertemplate="<b>%{x}</b><br>Precio sombra: %{y:.4f}<extra></extra>",
                                ))
                                _fig_bar.update_layout(
                                    title=dict(text="Precios Sombra (y* — Solución Dual Óptima)", font=dict(size=13)),
                                    xaxis_title="Variable Dual (yi)",
                                    yaxis_title="Precio Sombra",
                                    height=300,
                                    margin=dict(l=10, r=10, t=50, b=40),
                                    plot_bgcolor='#f8f9fa',
                                    paper_bgcolor='white',
                                    yaxis=dict(zeroline=True, zerolinecolor='#aaa'),
                                )
                                st.plotly_chart(_fig_bar, use_container_width=True)

                                # ── 2. Región factible 2D (solo cuando dual tiene 2 vars) ──
                                if _m_dual == 2:
                                    st.markdown("**Región Factible del Problema Dual (2D)**")
                                    _dA_np = _np_d.array(dual_info['dual_A'], dtype=float)  # (n, 2)
                                    _db_np = _np_d.array(dual_info['dual_b'], dtype=float)   # (n,)
                                    _y1_opt, _y2_opt = float(dy_vals[0]), float(dy_vals[1])

                                    # Axis limits: extend 25% beyond the optimal point
                                    _margin_f = max(abs(_y1_opt), abs(_y2_opt), 1) * 0.30
                                    _y1_max = max(_y1_opt * 1.5, _y2_opt * 0.5, 5) + _margin_f
                                    _y2_max = max(_y2_opt * 1.5, _y1_opt * 0.5, 5) + _margin_f
                                    _y1_arr = _np_d.linspace(0, _y1_max, 400)
                                    _y2_arr = _np_d.linspace(0, _y2_max, 400)

                                    _fig2d = _go_d.Figure()
                                    _dc_types = dual_info['dual_constraint_types']
                                    _dy_n     = dual_info['dual_var_names']
                                    _CLRS = ['#1976D2','#388E3C','#F57C00','#7B1FA2','#00838F','#C62828']

                                    # Draw constraint lines
                                    for _ji in range(_n_dual):
                                        _a1 = _dA_np[_ji, 0]
                                        _a2 = _dA_np[_ji, 1]
                                        _rhs = _db_np[_ji]
                                        _clr = _CLRS[_ji % len(_CLRS)]

                                        if abs(_a2) > 1e-9:
                                            _line_y2 = (_rhs - _a1 * _y1_arr) / _a2
                                            _mask = (_line_y2 >= -0.05 * _y2_max) & (_line_y2 <= _y2_max * 1.1)
                                            if _mask.any():
                                                _fig2d.add_trace(_go_d.Scatter(
                                                    x=_y1_arr[_mask], y=_line_y2[_mask],
                                                    mode='lines',
                                                    name=f"DC{_ji+1}: {_dc_types[_ji]} {_rhs:.4g}",
                                                    line=dict(color=_clr, width=2, dash='solid'),
                                                ))
                                        elif abs(_a1) > 1e-9:
                                            _xv = _rhs / _a1
                                            _fig2d.add_vline(x=_xv, line_color=_clr, line_width=2,
                                                             annotation_text=f"DC{_ji+1}")

                                    # Shade feasible region (sampled grid)
                                    _G1, _G2 = _np_d.meshgrid(
                                        _np_d.linspace(0, _y1_max, 120),
                                        _np_d.linspace(0, _y2_max, 120),
                                    )
                                    _feas = _np_d.ones(_G1.shape, dtype=bool)
                                    for _ji in range(_n_dual):
                                        _a1 = _dA_np[_ji, 0]; _a2 = _dA_np[_ji, 1]; _rhs = _db_np[_ji]
                                        _lhs_g = _a1 * _G1 + _a2 * _G2
                                        if _dc_types[_ji] == '>=':
                                            _feas &= (_lhs_g >= _rhs - 1e-6)
                                        elif _dc_types[_ji] == '<=':
                                            _feas &= (_lhs_g <= _rhs + 1e-6)
                                        else:
                                            _feas &= (_np_d.abs(_lhs_g - _rhs) <= 1e-4)
                                    # non-negativity
                                    _feas &= (_G1 >= -1e-6) & (_G2 >= -1e-6)

                                    _Z_feas = _np_d.where(_feas, 0.3, _np_d.nan)
                                    _fig2d.add_trace(_go_d.Heatmap(
                                        x=_np_d.linspace(0, _y1_max, 120),
                                        y=_np_d.linspace(0, _y2_max, 120),
                                        z=_Z_feas,
                                        colorscale=[[0,'rgba(144,238,144,0.25)'],[1,'rgba(144,238,144,0.25)']],
                                        showscale=False, hoverinfo='skip',
                                    ))

                                    # Objective function isoline through W*
                                    _dc_obj = dual_info['dual_c']  # [b1, b2] = RHS primal
                                    if abs(_dc_obj[1]) > 1e-9:
                                        _iso_y1 = _y1_arr
                                        _iso_y2 = (W_val - _dc_obj[0] * _iso_y1) / _dc_obj[1]
                                        _iso_mask = (_iso_y2 >= -0.05*_y2_max) & (_iso_y2 <= _y2_max * 1.1)
                                        if _iso_mask.any():
                                            _fig2d.add_trace(_go_d.Scatter(
                                                x=_iso_y1[_iso_mask], y=_iso_y2[_iso_mask],
                                                mode='lines',
                                                name=f"W = {W_val:.4g} (óptimo)",
                                                line=dict(color='#FFD700', width=2.5, dash='dash'),
                                            ))

                                    # Mark optimal point
                                    _fig2d.add_trace(_go_d.Scatter(
                                        x=[_y1_opt], y=[_y2_opt],
                                        mode='markers+text',
                                        name=f"y* = ({_y1_opt:.4g}, {_y2_opt:.4g})",
                                        marker=dict(size=14, color='#FFD700', symbol='star',
                                                    line=dict(color='black', width=1.5)),
                                        text=[f"W* = {W_val:.4g}"],
                                        textposition='top right',
                                        textfont=dict(size=11, color='black'),
                                    ))

                                    # Non-negativity axes
                                    _fig2d.add_vline(x=0, line_color='#555', line_width=1)
                                    _fig2d.add_hline(y=0, line_color='#555', line_width=1)

                                    _fig2d.update_layout(
                                        xaxis_title=f"{_dy_n[0]} (y₁)",
                                        yaxis_title=f"{_dy_n[1]} (y₂)",
                                        height=420,
                                        margin=dict(l=10, r=10, t=20, b=40),
                                        plot_bgcolor='#f8f9fa',
                                        paper_bgcolor='white',
                                        legend=dict(x=0.01, y=0.99, bgcolor='rgba(255,255,255,0.8)'),
                                        xaxis=dict(range=[0, _y1_max], zeroline=False),
                                        yaxis=dict(range=[0, _y2_max], zeroline=False),
                                    )
                                    st.plotly_chart(_fig2d, use_container_width=True)
                                    st.caption(
                                        "🟢 Región sombreada = región factible del dual. "
                                        "⭐ Estrella dorada = solución óptima dual (y*). "
                                        "🟡 Línea discontinua = isocurva W = valor óptimo."
                                    )
                                else:
                                    st.caption(
                                        f"ℹ️ El dual tiene {_m_dual} variables — la región factible 2D "
                                        "se muestra solo cuando el dual tiene exactamente 2 variables "
                                        "(primal con 2 restricciones)."
                                    )

                            except Exception as _dg_err:
                                st.caption(f"No se pudo generar la gráfica del dual: {_dg_err}")
                            # ──────────────────────────────────────────────────

                        else:
                            st.warning(f"No se pudo resolver el dual: {dsol.get('message', 'Error desconocido')}")

                    except Exception as _dual_err:
                        st.warning(f"No se pudo construir el dual: {_dual_err}")

            # ── DUALIDAD siempre visible ─────────────────────────────────────────
            try:
                _primal_infeasible = not result.get('success', False)
                st.divider()
                with st.expander("🔄 Dualidad – Formulación del Problema Dual", expanded=False):
                    if _primal_infeasible:
                        st.info(
                            "⚠️ El primal no tiene solución factible. "
                            "Se muestra la formulación del dual, pero las iteraciones "
                            "simplex y la solución óptima dual no están disponibles."
                        )
                    # Always build and show formulation + SOB table
                    _dc_raw2 = list(parsed_data['original_c'])
                    _dA2, _db2, _dct2 = [], [], []
                    for _ci2 in parsed_data.get('constraints_info', []):
                        _orig2 = _ci2['original']
                        _dA2.append([_orig2['lhs'].get(v, 0.0) for v in parsed_data['variables']])
                        _db2.append(_orig2['rhs'])
                        _dct2.append(_orig2['op'])
                    dual_info2 = build_dual(
                        c=_dc_raw2, A=_dA2, b=_db2,
                        constraint_types=_dct2,
                        optimization_type=parsed_data['optimization_type'],
                        var_names=parsed_data['variables'],
                    )
                    _fc1, _fc2 = st.columns(2)
                    with _fc1:
                        st.markdown("**📌 Primal**")
                        opt_s2 = "Max" if parsed_data['optimization_type'] == 'max' else "Min"
                        c_terms2 = " + ".join(
                            f"{int(v) if v == int(v) else v}{n}"
                            for v, n in zip(_dc_raw2, parsed_data['variables'])
                        )
                        st.code(f"{opt_s2} Z = {c_terms2}\n\nSujeto a:", language="")
                        for i2, (row2, rhs2, ct2) in enumerate(zip(_dA2, _db2, _dct2)):
                            lhs_s2 = " + ".join(
                                f"{int(row2[j]) if row2[j] == int(row2[j]) else row2[j]}{parsed_data['variables'][j]}"
                                for j in range(len(row2)) if abs(row2[j]) > 1e-9
                            )
                            rhs_s2 = str(int(rhs2)) if rhs2 == int(rhs2) else str(rhs2)
                            st.markdown(f"&nbsp;&nbsp;`R{i2+1}: {lhs_s2} {ct2} {rhs_s2}`", unsafe_allow_html=True)
                        st.markdown(", ".join(f"{v} ≥ 0" for v in parsed_data['variables']))
                    with _fc2:
                        st.markdown("**📌 Dual**")
                        st.code(f"{dual_info2['dual_obj_str']}\n\nSujeto a:", language="")
                        for cs2 in dual_info2['dual_constraints_str']:
                            st.markdown(f"&nbsp;&nbsp;`{cs2}`", unsafe_allow_html=True)
                        st.markdown(", ".join(dual_info2['dual_var_restr_str']))
                    import pandas as _pd_d2
                    st.markdown("##### 📋 Tabla de Conversión (S.O.B.)")
                    st.dataframe(_pd_d2.DataFrame(dual_info2['sob_rows']), hide_index=True, use_container_width=True)
                    if _primal_infeasible:
                        st.caption(
                            "ℹ️ Dado que el primal es infactible, la solución óptima dual no se calcula aquí. "
                            "Puedes analizar el dual de forma independiente ingresándolo directamente."
                        )
            except Exception:
                pass  # silently skip if parsed_data/result not yet available

        except Exception as e:
            col1.error(f"Input Error: {str(e)}")


elif module == "Simplex Tutor":
    import numpy as np

    import streamlit.components.v1 as components

    # Shared CSS (embedded into each component HTML)
    _SIMPLEX_CSS = """
    <style>
    body { margin: 0; padding: 4px; background: #fff; font-family: Arial, sans-serif; color: #111; }
    table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
    th, td { border: 2px solid #999; padding: 6px 10px; text-align: center; color: #111; }
    thead th { background: #2c3e7a; color: #fff; font-weight: bold; }
    td.cb     { background: #d6e4f7; color: #111; font-weight: bold; }
    td.basis  { background: #2c3e7a; color: #fff; font-weight: bold; }
    td.rhs    { background: #d6e4f7; color: #111; font-weight: bold; }
    tr.zj  td { background: #f0f0f0; color: #333; font-style: italic; }
    tr.cjzj td{ background: #e8f5e9; color: #111; }
    td.entering { background: #c0392b; color: #fff; font-weight: bold; }
    td.positive { color: #1a7a32; font-weight: bold; }
    td.negative { color: #c0392b; font-weight: bold; }
    td.zero     { color: #777; }
    tr.pivot-row td { background: #fff3cd; color: #111; }
    p { color: #333; }
    </style>
    """


    st.subheader("Método Simplex – Paso a Paso")

    from modules.persistence import save_last_session, load_last_session

    # ── Restore last session on first load ───────────────────────────────────
    if 'simp_initialized' not in st.session_state:
        # Try shared cross-panel key first so LP panel changes are picked up
        shared = load_last_session("LP_Problem")
        own    = load_last_session("Simplex Tutor")
        last   = shared if (shared and shared.get("data")) else own
        if last and last.get("data"):
            d = last["data"]
            # Shared key uses LP-style keys; own key uses simp-style keys
            if "obj_formula" in d:
                # Coming from LP panel: convert direction label and use formula
                lp_type = d.get("obj_type", "Maximize")
                st.session_state["simp_opt_type"] = "Maximizar" if lp_type == "Maximize" else "Minimizar"
                st.session_state["simp_obj"]      = d.get("obj_formula", "50x1 + 40x2")
                st.session_state["simp_cons"]     = d.get("constraints", "3x1 + 5x2 <= 150\nx2 <= 20\n8x1 + 5x2 <= 300")
            else:
                st.session_state["simp_opt_type"]  = d.get("opt_type",  "Maximizar")
                st.session_state["simp_obj"]        = d.get("obj",       "50x1 + 40x2")
                st.session_state["simp_cons"]       = d.get("cons",      "3x1 + 5x2 <= 150\nx2 <= 20\n8x1 + 5x2 <= 300")
            st.session_state["simp_nonneg"] = d.get("nonneg", True)
        st.session_state['simp_initialized'] = True

    def _simp_autosave():
        simp_type = st.session_state.get("simp_opt_type", "Maximizar")
        simp_obj  = st.session_state.get("simp_obj",      "50x1 + 40x2")
        simp_cons = st.session_state.get("simp_cons",     "")
        save_last_session("Simplex Tutor", {
            "opt_type": simp_type,
            "obj":      simp_obj,
            "cons":     simp_cons,
            "nonneg":   st.session_state.get("simp_nonneg",   True),
        })
        # Also update shared cross-panel key so LP panel sees the new values
        save_last_session("LP_Problem", {
            "obj_type":   "Maximize" if simp_type == "Maximizar" else "Minimize",
            "obj_formula": simp_obj,
            "constraints": simp_cons,
        })

    col_in, col_tbl = st.columns([1, 2.2])

    with col_in:
        st.markdown("#### Configuración del Problema")
        opt_type_s = st.radio("Tipo", ["Maximizar", "Minimizar"], horizontal=True,
                              key="simp_opt_type", on_change=_simp_autosave)
        obj_str  = st.text_input("Función objetivo (Z =)", "50x1 + 40x2",
                                 key="simp_obj", on_change=_simp_autosave)
        cons_str = st.text_area("Restricciones (una por línea)",
                                "3x1 + 5x2 <= 150\nx2 <= 20\n8x1 + 5x2 <= 300",
                                height=160, key="simp_cons", on_change=_simp_autosave)
        non_neg  = st.checkbox("Variables no-negativas (xi ≥ 0)", value=True,
                               key="simp_nonneg", on_change=_simp_autosave)

        # ── Method selector ──────────────────────────────────────────────
        st.markdown("---")
        st.markdown("**Método de solución:**")
        simp_method = st.radio(
            "Selecciona el método",
            options=["Gran M", "Dos Fases"],
            index=0,
            horizontal=True,
            key="simp_method",
            help=(
                "**Gran M**: Penaliza las variables artificiales con un coeficiente M "
                "muy grande directamente en la función objetivo.\n\n"
                "**Dos Fases**: Fase 1 minimiza la suma de artificiales (sin M); "
                "Fase 2 optimiza el objetivo original con la base factible encontrada."
            ),
        )
        st.markdown("---")

        init_btn = st.button("▶ Inicializar", use_container_width=True, key="simp_init")
        step_btn = st.button("⏩ Siguiente Iteración", use_container_width=True,
                             key="simp_step",
                             disabled=('simp_tutor' not in st.session_state))
        reset_btn = st.button("🔄 Reiniciar", use_container_width=True, key="simp_reset")

        if reset_btn:
            for k in ['simp_tutor', 'simp_log', 'simp_last_pivot']:
                st.session_state.pop(k, None)
            st.rerun()

    # ── Helper: build and display textbook tableau ───────────────────────────
    from modules.simplex_tutor import (MExpr as _MExpr, _fmt_mexpr as _fmt_mexpr_fn,
                                       TwoPhaseSimplexTutor as _TwoPhaseTutor)

    def _fmt(v, decimals=4):
        """Format numbers cleanly (no M awareness — used for constraint cells)."""
        if isinstance(v, _MExpr):
            return str(v)
        if abs(v) < 1e-9:
            return "0"
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{v:.{decimals}g}"

    def _fmt_M(v, decimals=4):
        """Format with symbolic M for Big-M values (used in cj / CB / zj / cj-zj)."""
        if isinstance(v, _MExpr):
            return str(v)
        # Fallback for plain floats
        if abs(v) < 1e-9:
            return "0"
        if abs(v - round(v)) < 1e-9:
            return str(int(round(v)))
        return f"{v:.{decimals}g}"

    def _cell_cls(j, v, entering_col, row_type='data'):
        """Determine CSS class for a cj-zj cell."""
        if row_type == 'cjzj':
            if j == entering_col:
                return "entering"
            # Compare symbolically if MExpr, numerically otherwise
            if isinstance(v, _MExpr):
                if v.is_positive():
                    return "positive"
                if v.is_negative():
                    return "negative"
                return "zero"
            if v > 1e-8:
                return "positive"
            if v < -1e-8:
                return "negative"
            return "zero"
        return ""

    def _build_tableau_html(tutor_dict, pivot_row=None):
        """Build the full self-contained HTML document for the tableau.

        Artificial variable columns (a1, a2, …) are shown only while they
        are IN the current basis.  Once an artificial leaves the basis it is
        no longer relevant and is hidden to keep the display clean.
        """
        col_names  = tutor_dict['col_names']
        rows       = tutor_dict['rows']
        entering   = tutor_dict['entering_col']
        iteration  = tutor_dict.get('iteration', 0)

        # Prefer symbolic MExpr lists; fall back to numeric lists if absent
        cj_vals    = tutor_dict.get('cj_sym',    tutor_dict['cj'])
        zj_vals    = tutor_dict.get('zj_sym',    tutor_dict['zj'])
        cjzj_vals  = tutor_dict.get('cj_zj_sym', tutor_dict['cj_zj'])
        z_val      = tutor_dict.get('z_value_sym', tutor_dict['z_value'])

        # ── Which columns to display? ────────────────────────────────────────
        # Artificial columns that left the basis are hidden after iter 0.
        basis_set = {row['basis'] for row in rows}
        visible   = []        # list of original column indices to show
        remap     = {}        # original_j → display_j
        phase = tutor_dict.get('phase', None)
        for j, name in enumerate(col_names):
            is_artificial = name.startswith('a') and name[1:].isdigit()
            
            # Hide artificial variables that left the basis, unless we are in Phase 1 of Two-Phase method
            hide_col = False
            if is_artificial and name not in basis_set and iteration > 0:
                if phase == 1:
                    hide_col = False
                else:
                    hide_col = True
                    
            if hide_col:
                continue  # hide: artificial already left the basis (Big-M or Phase 2)
                
            remap[j] = len(visible)
            visible.append(j)

        # Re-map entering column to display index (None if hidden)
        display_entering = remap.get(entering, None)

        def ecls(j_display):  # entering-column class helper
            return ' class="entering"' if j_display == display_entering else ''

        n_vis = len(visible)

        # cj header sub-row
        hdr_cj    = ''.join(f'<th{ecls(remap[j])}>{_fmt_M(cj_vals[j])}</th>'
                            for j in visible)
        # variable name header row
        hdr_names = ''.join(f'<th{ecls(remap[j])}>{col_names[j]}</th>'
                            for j in visible)

        # constraint rows
        tbody = ''
        for idx, row in enumerate(rows):
            is_pivot = (idx == pivot_row)
            tr_open  = '<tr class="pivot-row">' if is_pivot else '<tr>'
            marker   = ' &larr; pivote' if is_pivot else ''
            cells    = ''.join(
                f'<td{ecls(remap[j])}>{_fmt(row["coefficients"][j])}</td>'
                for j in visible
            )
            tbody += (f'{tr_open}'
                      f'<td class="cb">{_fmt_M(row["CB"])}</td>'
                      f'<td class="basis">{row["basis"]}{marker}</td>'
                      f'{cells}'
                      f'<td class="rhs">{_fmt(row["rhs"])}</td>'
                      f'</tr>')

        # zj row
        zj_cells = ''.join(f'<td>{_fmt_M(zj_vals[j])}</td>' for j in visible)
        tbody += (f'<tr class="zj">'
                  f'<td></td><td><b>z<sub>j</sub></b></td>'
                  f'{zj_cells}'
                  f'<td class="rhs"><b>Z = {_fmt_M(z_val)}</b></td>'
                  f'</tr>')

        # cj-zj row
        cjzj_cells = ''.join(
            f'<td class="{_cell_cls(remap[j], cjzj_vals[j], display_entering, "cjzj")}">'
            f'{_fmt_M(cjzj_vals[j])}</td>'
            for j in visible
        )
        tbody += (f'<tr class="cjzj">'
                  f'<td></td><td><b>c<sub>j</sub>-z<sub>j</sub></b></td>'
                  f'{cjzj_cells}<td></td></tr>')

        return f"""<!DOCTYPE html><html><head>{_SIMPLEX_CSS}</head><body>
        <table>
          <thead>
            <tr><th>C<sub>B</sub></th><th>Base</th>{hdr_names}<th>RHS</th></tr>
            <tr style="font-size:0.8em;color:#aaa;"><th></th><th>c<sub>j</sub></th>{hdr_cj}<th></th></tr>
          </thead>
          <tbody>{tbody}</tbody>
        </table>
        </body></html>"""

    def render_tableau(tutor_dict, pivot_row=None):
        html_doc = _build_tableau_html(tutor_dict, pivot_row)
        n_rows   = len(tutor_dict['rows']) + 3  # +cj header +zj +cjzj
        height   = max(180, n_rows * 38 + 20)
        components.html(html_doc, height=height, scrolling=False)

    def _build_ratio_html(pivot_info):
        """Build self-contained HTML for the ratio-test table."""
        ratios  = pivot_info['ratios']
        ec_name = pivot_info['entering_name']
        rows_html = ''
        for r in ratios:
            if r['ratio'] is None:
                ratio_str = '&mdash; (no positivo)'
                bg = ''
            else:
                ratio_str = _fmt(r['ratio'])
                bg = ' style="background:#fffde7; color:#111; font-weight:bold;"' if r['is_min'] else ''
            cell4 = f'<b>{ratio_str} &#10003; (m&iacute;n)</b>' if r['is_min'] else ratio_str
            pv    = _fmt(r['pivot_col_val']) if r['pivot_col_val'] > 1e-8 else '&le; 0'
            rows_html += (f'<tr{bg}><td>{r["basis"]}</td>'
                          f'<td>{_fmt(r["rhs"])}</td>'
                          f'<td>{pv}</td>'
                          f'<td>{cell4}</td></tr>')
        return f"""<!DOCTYPE html><html><head>{_SIMPLEX_CSS}</head><body>
        <p style="margin:4px 0 6px;font-size:.85rem;color:#ccc;"
           >Prueba de raz&oacute;n &mdash; columna entrante: <b>{ec_name}</b></p>
        <table style="width:auto;">
          <thead><tr>
            <th>Base</th>
            <th>RHS (b<sub>i</sub>)</th>
            <th>Coef. {ec_name}</th>
            <th>b<sub>i</sub> / a<sub>ij</sub></th>
          </tr></thead>
          <tbody>{rows_html}</tbody>
        </table>
        </body></html>"""

    def render_ratio_table(pivot_info):
        html_doc = _build_ratio_html(pivot_info)
        n_rows   = len(pivot_info['ratios']) + 2
        height   = max(120, n_rows * 38 + 40)
        components.html(html_doc, height=height, scrolling=False)

    # ── Initialize ───────────────────────────────────────────────────────────
    if init_btn:
        try:
            from modules.lp_parser import LPParser
            opt_word   = "Maximize" if opt_type_s == "Maximizar" else "Minimize"
            full_obj   = f"{opt_word} {obj_str}"
            cons_lines = [c.strip() for c in cons_str.strip().split('\n') if c.strip()]
            parser     = LPParser(full_obj, cons_lines)
            parsed     = parser.parse()

            # Extract matrices
            c      = list(parsed['original_c'])
            A_rows, b_vals, ctypes = [], [], []
            for ci in parsed.get('constraints_info', []):
                orig = ci['original']
                A_rows.append([orig['lhs'].get(v, 0.0) for v in parsed['variables']])
                b_vals.append(orig['rhs'])
                ctypes.append(orig['op'])

            opt_dir = 'max' if opt_type_s == "Maximizar" else 'min'

            # Create the appropriate tutor based on the selected method
            chosen_method = st.session_state.get("simp_method", "Gran M")
            if chosen_method == "Dos Fases":
                tutor = _TwoPhaseTutor(
                    c=c, A=A_rows, b=b_vals,
                    constraint_types=ctypes,
                    optimization_type=opt_dir,
                    var_names=parsed['variables'],
                )
            else:  # Gran M (default)
                from modules.simplex_tutor import SimplexTutor
                tutor = SimplexTutor(
                    c=c, A=A_rows, b=b_vals,
                    constraint_types=ctypes,
                    optimization_type=opt_dir,
                    var_names=parsed['variables'],
                )

            st.session_state.simp_tutor      = tutor
            st.session_state.simp_log        = []
            st.session_state.simp_last_pivot = None
            st.rerun()
        except Exception as e:
            st.error(f"Error al parsear: {e}")

    # ── Step ─────────────────────────────────────────────────────────────────
    if step_btn and 'simp_tutor' in st.session_state:
        tutor = st.session_state.simp_tutor
        ok, msg, pinfo = tutor.next_step()
        st.session_state.simp_log.append((ok, msg))
        st.session_state.simp_last_pivot = pinfo if ok else None
        st.rerun()

    # ── Display ──────────────────────────────────────────────────────────────
    with col_tbl:
        if 'simp_tutor' not in st.session_state:
            st.info("Configure el problema a la izquierda y presiona ▶ Inicializar.")
        else:
            tutor  = st.session_state.simp_tutor
            tdict  = tutor.get_tableau_dict()
            pinfo  = st.session_state.get('simp_last_pivot')
            log    = st.session_state.get('simp_log', [])

            # Status badge (handles both Big-M and Two-Phase statuses)
            status = tdict['status']
            phase  = tdict.get('phase', None)   # 1 or 2 for Two-Phase, None for Big-M

            if status == "Optimal":
                st.success(f"✅ **Óptimo alcanzado** — Iteración {tdict['iteration']}")
            elif "Infeasible" in status:
                st.error("❌ **Problema infactible** (w∗ ≠ 0 en Fase 1)")
            elif "Unbounded" in status:
                st.error("⚠️ **Solución no acotada**")
            elif "Fase 1" in status and "Inicializada" in status:
                st.info("🔵 **Fase 1** — Tabla inicial. Presiona ⏩ para iterar.")
            elif "Fase 2" in status and "Inicializada" in status:
                st.success("💚 **Fase 1 completa** → iniciando **Fase 2**. Presiona ⏩ para continuar.")
            elif "Fase 1" in status:
                st.info(f"🔵 **{status}** — minimizando suma de artificiales (w = Σaᵢ)")
            elif "Fase 2" in status:
                st.warning(f"💚 **{status}** — optimizando objetivo original")
            elif status == "Initialized":
                st.info("Tabla inicial. Presiona ⏩ para iterar.")
            else:
                st.warning(f"🔄 **{status}**")

            # Direction reminder (Phase 1 always minimises w)
            if phase == 1:
                opt_lbl    = "Fase 1 – Minimizar w = Σaᵢ"
                enter_rule = "Entra: menor **cj-zj < 0** (reduce w)"
            else:
                opt_lbl    = "Maximización" if tdict['optimization_type'] == 'max' else "Minimización"
                enter_rule = ("Entra: mayor **cj-zj > 0**" if tdict['optimization_type'] == 'max'
                              else "Entra: menor **cj-zj < 0**")
            st.caption(f"{opt_lbl} | {enter_rule} | Sale: razón mínima positiva | Empates: variable más a la izquierda")

            # Main tableau
            pivot_row_idx = pinfo['leaving_row'] if pinfo else None
            render_tableau(tdict, pivot_row=pivot_row_idx)

            # Ratio test (only when a pivot just happened)
            if pinfo:
                st.markdown("---")
                render_ratio_table(pinfo)

            # Solution when optimal
            if status == "Optimal":
                st.markdown("---")
                st.markdown("#### 🎯 Solución Óptima")
                sol, z = tutor.get_solution()
                # Only show decision variables
                dec_vars = tutor.var_names
                sol_rows = [{"Variable": v, "Valor": _fmt(sol.get(v, 0))} for v in dec_vars]
                sol_df = pd.DataFrame(sol_rows)
                st.dataframe(sol_df, hide_index=True, use_container_width=False)
                z_display = z if tdict['optimization_type'] == 'min' else z
                st.metric("Z óptimo", _fmt(z_display))

                # ── Excel Solver-style Answer Report ─────────────────────────
                st.markdown("---")
                with st.expander("📊 Reporte de Respuesta – Estilo Excel Solver", expanded=True):
                    opt_word_es = "Maximizar" if tdict['optimization_type'] == 'max' else "Minimizar"

                    # --- 1. Celda Objetivo ---
                    st.markdown("**Celda Objetivo**")
                    obj_df = pd.DataFrame([{
                        "Nombre":         f"Z ({opt_word_es})",
                        "Valor Original": 0,
                        "Valor Final":    round(z_display, 6),
                    }])
                    st.dataframe(obj_df, hide_index=True, use_container_width=True)

                    # --- 2. Celdas de Variables ---
                    st.markdown("**Celdas de Variables**")
                    var_rows = [{
                        "Variable":       v,
                        "Valor Original": 0,
                        "Valor Final":    round(sol.get(v, 0.0), 6),
                    } for v in dec_vars]
                    st.dataframe(pd.DataFrame(var_rows), hide_index=True, use_container_width=True)

                    # --- 3. Restricciones ---
                    st.markdown("**Restricciones**")
                    tol_bind = 1e-5
                    constr_rows = []
                    x_vec = np.array([sol.get(v, 0.0) for v in tutor.var_names])
                    for i in range(tutor.num_constraints):
                        coefs  = tutor.A_orig[i]
                        rhs    = tutor.b_orig[i]
                        ctype  = tutor.constraint_types[i]
                        lhs_v  = float(coefs @ x_vec)

                        if ctype == '<=':
                            slack  = rhs - lhs_v
                            status_str = "Activa (Binding)"   if abs(slack) < tol_bind else "No Activa"
                            sign   = "<="
                        elif ctype == '>=':
                            slack  = lhs_v - rhs
                            status_str = "Activa (Binding)"   if abs(slack) < tol_bind else "No Activa"
                            sign   = ">="
                        else:  # '='
                            slack  = abs(lhs_v - rhs)
                            status_str = "Activa (Binding)"   if slack < tol_bind else "No Activa"
                            sign   = "="

                        # Build constraint label
                        lhs_str = " + ".join(f"{_fmt(c)}{v}" for c, v in zip(coefs, tutor.var_names) if abs(c) > 1e-9)
                        constr_rows.append({
                            "Restricción":       f"R{i+1}",
                            "Fórmula":           f"{lhs_str} {sign} {_fmt(rhs)}",
                            "Valor LHS":         round(lhs_v, 6),
                            "RHS":               round(rhs, 6),
                            "Holgura / Exceso":  round(slack, 6),
                            "Estado":            status_str,
                        })

                    def _style_constr(row):
                        if "Activa" in row.get("Estado", "") and "No" not in row.get("Estado", ""):
                            return ["background-color: #d4edda; color: #155724; font-weight: bold"] * len(row)
                        return [""] * len(row)

                    constr_df = pd.DataFrame(constr_rows)
                    st.dataframe(
                        constr_df.style.apply(_style_constr, axis=1),
                        hide_index=True,
                        use_container_width=True,
                    )
                    st.caption("🟢 Filas verdes = restricciones activas (binding), es decir holgura/exceso = 0.")


            # ── Dual simplex expander ────────────────────────────────────────
            st.markdown("---")
            with st.expander("🔄 Aplicar Simplex al Problema Dual", expanded=False):
                try:
                    from modules.duality import build_dual, solve_dual_simplex

                    # Reconstruct primal data from the active tutor
                    _tc       = list(tutor.c_orig)
                    _tA       = [list(r) for r in tutor.A_orig]
                    _tb       = list(tutor.b_orig)
                    _tct      = list(tutor.constraint_types)
                    _topt     = tutor.optimization_type
                    _tvars    = list(tutor.var_names)

                    _dinfo = build_dual(
                        c=_tc, A=_tA, b=_tb,
                        constraint_types=_tct,
                        optimization_type=_topt,
                        var_names=_tvars,
                    )

                    # ── Dual formulation ─────────────────────────────────────
                    st.markdown("##### 📌 Formulación del Problema Dual")
                    _dd1, _dd2 = st.columns(2)
                    with _dd1:
                        st.markdown("**Primal**")
                        _p_opt = "Max" if _topt == "max" else "Min"
                        _p_obj = " + ".join(
                            f"{int(v) if v==int(v) else v}{n}"
                            for v, n in zip(_tc, _tvars)
                        )
                        st.code(f"{_p_opt} Z = {_p_obj}\n\nSujeto a:", language="")
                        for _i, (_row, _rhs, _ct) in enumerate(zip(_tA, _tb, _tct)):
                            _ls = " + ".join(
                                f"{int(_row[_j]) if _row[_j]==int(_row[_j]) else _row[_j]}{_tvars[_j]}"
                                for _j in range(len(_row)) if abs(_row[_j]) > 1e-9
                            )
                            _rs = str(int(_rhs)) if _rhs == int(_rhs) else str(_rhs)
                            st.markdown(f"&nbsp;&nbsp;`R{_i+1}: {_ls} {_ct} {_rs}`", unsafe_allow_html=True)
                        st.markdown(", ".join(f"{v} ≥ 0" for v in _tvars))
                    with _dd2:
                        st.markdown("**Dual**")
                        st.code(f"{_dinfo['dual_obj_str']}\n\nSujeto a:", language="")
                        for _cs in _dinfo['dual_constraints_str']:
                            st.markdown(f"&nbsp;&nbsp;`{_cs}`", unsafe_allow_html=True)
                        st.markdown(", ".join(_dinfo['dual_var_restr_str']))

                    # ── Dual simplex iterations ──────────────────────────────
                    st.markdown("##### 🔢 Iteraciones Simplex del Dual")
                    _ds = solve_dual_simplex(_dinfo)
                    if _ds['error']:
                        st.warning(f"No se pudo resolver el dual: {_ds['error']}")
                    elif not _ds['iterations']:
                        st.info("No se generaron iteraciones para el dual.")
                    else:
                        # Build one HTML tableau per iteration using the same renderer
                        from modules.simplex_tutor import SimplexTutor as _ST
                        _dy_names = _dinfo['dual_var_names']
                        _dc       = _dinfo['dual_c']
                        _dA       = _dinfo['dual_A']
                        _db       = _dinfo['dual_b']
                        _dct      = _dinfo['dual_constraint_types']
                        _d_opt    = _dinfo['dual_type']
                        _dvar_res = _dinfo['dual_var_restr']

                        # Recreate tutor to step through tableaux
                        _d_tutor = _ST(
                            c=_dc, A=_dA, b=_db,
                            constraint_types=_dct,
                            optimization_type=_d_opt,
                            var_names=_dy_names,
                        )
                        # Show initial tableau
                        _d_it = 0
                        _d_td = _d_tutor.get_tableau_dict()
                        st.markdown(f"**Iteración {_d_it} – Tabla inicial**")
                        render_tableau(_d_td)

                        # Step until done
                        _max_iter = 30
                        while _d_tutor.get_tableau_dict()['status'] not in ('Optimal', 'Unbounded', 'Infeasible') and _d_it < _max_iter:
                            _ok, _msg, _piv = _d_tutor.next_step()
                            _d_it += 1
                            _d_td = _d_tutor.get_tableau_dict()
                            _st = _d_td['status']
                            _label = f"**Iteración {_d_it}**" + (" — ✅ Óptimo" if _st == 'Optimal' else "")
                            st.markdown(_label)
                            render_tableau(_d_td)
                            if _piv:
                                render_ratio_table(_piv)

                        # Dual optimal solution summary
                        _d_td_final = _d_tutor.get_tableau_dict()
                        if _d_td_final['status'] == 'Optimal':
                            _d_sol, _W = _d_tutor.get_solution()
                            st.markdown("---")
                            st.success(f"✅ Solución óptima dual: **W* = {_fmt(_W)}**")
                            _d_sol_rows = [{"Variable Dual": v, "Valor (Precio Sombra)": _fmt(_d_sol.get(v, 0))}
                                           for v in _dy_names]
                            st.dataframe(pd.DataFrame(_d_sol_rows), hide_index=True, use_container_width=False)
                            st.caption("Los valores de y* son los precios sombra del primal. Por el Teorema de Dualidad Fuerte: Z* = W*.")

                except Exception as _de:
                    st.warning(f"No se pudo construir la sección dual: {_de}")

            # Iteration log
            if log:
                st.markdown("---")
                st.markdown("#### 📋 Historial de Iteraciones")
                for ok_flag, msg_text in log:
                    st.info(msg_text)


elif module == "Transportation":
    st.subheader("Transportation Problem")
    import numpy as np
    from modules.transport import TransportSolver

    # ── Grid dimensions ─────────────────────────────────────────────────
    col1, col2 = st.columns([1, 1])
    with col1:
        rows      = int(st.number_input("Sources / Trabajadores", 2, 8, 3, key="tp_rows"))
        cols_dest = int(st.number_input("Destinations / Tareas",  2, 8, 3, key="tp_cols"))
        method    = st.selectbox(
            "Método de Solución",
            ["Northwest Corner", "Min Cost", "Hungarian Method"],
            key="tp_method"
        )

    is_hungarian = method == "Hungarian Method"

    if is_hungarian:
        st.info("ℹ️ **Método Húngaro (Asignación):** Cada trabajador se asigna exactamente "
                "a una tarea. Oferta y demanda no aplican.")

    # ── Persist cost matrix: only reset when shape changes ──────────────
    _shape_key = "tp_cost_shape"
    _data_key  = "tp_cost_data"

    if st.session_state.get(_shape_key) != (rows, cols_dest):
        # Shape changed → fresh matrix + clear stale widget diffs
        st.session_state[_data_key]  = np.ones((rows, cols_dest), dtype=float).tolist()
        st.session_state[_shape_key] = (rows, cols_dest)
        for _wkey in ("cost_grid", "supply_grid", "demand_grid"):
            st.session_state.pop(_wkey, None)

    _cost_init = pd.DataFrame(
        st.session_state[_data_key],
        columns=[f"D{j+1}" for j in range(cols_dest)],
        index=[f"S{i+1}" for i in range(rows)]
    )

    st.write("**Matriz de Costos C_ij:**")
    # key lets Streamlit track diffs internally — NO write-back needed
    cost_df = st.data_editor(_cost_init, key="cost_grid", use_container_width=True)

    # ── Supply / Demand ──────────────────────────────────────────────────
    if not is_hungarian:
        if st.session_state.get("tp_sup_shape") != rows:
            st.session_state["tp_supply_init"] = [100] * rows
            st.session_state["tp_sup_shape"]   = rows
            st.session_state.pop("supply_grid", None)

        if st.session_state.get("tp_dem_shape") != cols_dest:
            st.session_state["tp_demand_init"] = [100] * cols_dest
            st.session_state["tp_dem_shape"]   = cols_dest
            st.session_state.pop("demand_grid", None)

        col_s, col_d = st.columns(2)
        with col_s:
            st.write("Supply:")
            supply_df = st.data_editor(
                pd.DataFrame(st.session_state["tp_supply_init"], columns=["Supply"]),
                key="supply_grid"
            )
        with col_d:
            st.write("Demand:")
            demand_df = st.data_editor(
                pd.DataFrame(st.session_state["tp_demand_init"], columns=["Demand"]),
                key="demand_grid"
            )

    # ─── Vista previa: tabla balanceada + Formulación PPL ───
    if not is_hungarian:
        try:
            _prev_costs  = cost_df.values.astype(float)
            _prev_supply = supply_df.values.flatten().astype(float)
            _prev_demand = demand_df.values.flatten().astype(float)
            with st.expander("📋 Tabla balanceada + Formulación PPL  (para incisos como 'a', 'd', 'e')",
                             expanded=True):
                render_balanced_transport_and_lp(_prev_costs, _prev_supply, _prev_demand)
        except Exception as _prev_err:
            st.caption(f"(No se pudo generar vista previa: {_prev_err})")
    else:
        # Vista previa para Asignación (Húngaro)
        try:
            _prev_costs = cost_df.values.astype(float)
            with st.expander("📝 Formulación PPL/PE de Asignación  (incisos 'a', 'b')",
                             expanded=True):
                render_assignment_formulation(_prev_costs)
        except Exception as _prev_err:
            st.caption(f"(No se pudo generar vista previa: {_prev_err})")

    if st.button("▶ Resolver", type="primary", use_container_width=True):
        try:
            costs = cost_df.values.astype(float)

            if is_hungarian:
                supply = np.ones(int(rows))
                demand = np.ones(int(cols_dest))
            else:
                supply = supply_df.values.flatten().astype(float)
                demand = demand_df.values.flatten().astype(float)

            method_map = {
                "Northwest Corner": "northwest",
                "Min Cost":         "min_cost",
                "Hungarian Method": "hungarian",
            }
            method_key = method_map.get(method, "min_cost")

            solver = TransportSolver(costs, supply, demand)
            res = solver.solve_initial(method=method_key)

            st.subheader("Resultado")

            if not res.get("is_assignment") and "initial_cost" in res:
                _c1, _c2, _c3 = st.columns(3)
                _c1.metric("Solución Inicial", f"${res['initial_cost']:,.2f}")
                _c2.metric("Costo Óptimo", f"${res['total_cost']:,.2f}",
                           delta=f"{res['total_cost'] - res['initial_cost']:,.2f}")
                iters = res.get("iterations", [])
                _c3.metric("Iteraciones MODI", len(iters) - 1 if iters else 0)
            else:
                st.metric("Costo Total Óptimo", f"${res['total_cost']:,.2f}")

        except Exception as _tp_err:
            st.error(f"❌ Error al resolver: {_tp_err}")
            st.caption("Verifica que la matriz de costos y los valores de oferta/demanda sean válidos.")

        else:
            st.caption(f"Estado: {res['status']}")
            _col_labels = list(cost_df.columns)
            _row_labels = [f"S{i+1}" for i in range(int(rows))]

            if res.get("is_assignment"):
                # ── HUNGARIAN ────────────────────────────────────────────────
                st.markdown("### 🏆 Asignaciones Óptimas")
                pairs = res.get("assignment_pairs", [])
                if pairs:
                    pairs_df = pd.DataFrame(pairs)
                    def _highlight_pairs(row):
                        return ["background-color:#FFD700; font-weight:bold; color:#5a4000"] * len(row)
                    st.dataframe(pairs_df.style.apply(_highlight_pairs, axis=1),
                                 hide_index=True, use_container_width=True)

                st.markdown("### Matriz de Asignación (1 = asignado)")
                alloc_disp = pd.DataFrame(
                    res["allocation"].astype(int), columns=_col_labels, index=_row_labels
                )
                def _hl_1(val):
                    return "background-color:#FFD700; font-weight:bold; color:#5a4000" if val == 1 else ""
                st.dataframe(alloc_disp.style.map(_hl_1), use_container_width=True)

                if res.get("steps"):
                    with st.expander("📋 Pasos del Método Húngaro", expanded=True):
                        for _step_info in res["steps"]:
                            st.markdown(f"#### {_step_info['label']}")
                            st.caption(_step_info.get("desc", ""))
                            _mat = _step_info["matrix"]
                            _nr, _nc = _mat.shape
                            _snap_df = pd.DataFrame(
                                _mat,
                                columns=[f"D{_jj+1}" for _jj in range(_nc)],
                                index=[f"S{_ii+1}" for _ii in range(_nr)]
                            )
                            def _hl_zero(val):
                                return "background-color:#d4edda; color:#155724; font-weight:bold" if abs(val) < 1e-6 else ""
                            st.dataframe(_snap_df.style.map(_hl_zero).format("{:.4g}"),
                                         use_container_width=True)
                            _asgn = _step_info.get("assignment", [])
                            if _asgn:
                                _asgn_lbl = ", ".join(
                                    f"S{r+1}→D{c+1}" for r, c in sorted(_asgn)
                                    if r < int(rows) and c < len(_col_labels)
                                )
                                st.success(f"✅ Asignación óptima: {_asgn_lbl}")
                            st.markdown("---")

            else:
                # ── NW CORNER / MIN COST ─────────────────────────────────────
                st.markdown("### Matriz de Asignación Óptima")
                _alloc_df = pd.DataFrame(
                    res["allocation"], columns=_col_labels, index=_row_labels
                )
                def _fmt_alloc(v):
                    if v < 1e-9: return "—"
                    return str(int(v)) if v == int(v) else f"{v:.2f}"
                def _hl_alloc(v):
                    return "background-color:#e8f5e9; font-weight:bold; color:#1b5e20" if v > 1e-9 else ""
                st.dataframe(_alloc_df.style.map(_hl_alloc).format(_fmt_alloc),
                             use_container_width=True)

                # ── Phase 1 steps ─────────────────────────────────────────────
                _p1 = res.get("phase1_steps", [])
                if _p1:
                    _p1_name = "Esquina Noroeste" if method == "Northwest Corner" else "Costo Mínimo"
                    with st.expander(f"📐 Fase 1 – Solución Inicial ({_p1_name})", expanded=True):
                        _p1_summary = [{
                            "Paso":        s["Paso"],
                            "Celda":       s["Celda"],
                            "Cantidad":    s["Cantidad"],
                            "Costo c_ij":  s["Costo c_ij"],
                            "Costo acum.": s["Costo acum."],
                        } for s in _p1]
                        def _style_p1_last(row):
                            if row.name == len(_p1_summary) - 1:
                                return ["background-color:#fff9c4; font-weight:bold"] * len(row)
                            return [""] * len(row)
                        st.dataframe(
                            pd.DataFrame(_p1_summary).style.apply(_style_p1_last, axis=1),
                            hide_index=True, use_container_width=True
                        )
                        st.caption(f"Solución inicial: **${_p1[-1]['Costo acum.']:,.2f}** en {len(_p1)} asignaciones.")
                        st.markdown("---")
                        st.markdown("**Matrices paso a paso:**")
                        for _s in _p1:
                            st.markdown(f"**Paso {_s['Paso']}** — Asignar `{_s['Cantidad']}` unidades a `{_s['Celda']}` (c = {_s['Costo c_ij']})")
                            _snap = _s["snapshot"]
                            _nr, _nc = _snap.shape
                            _sdf = pd.DataFrame(
                                _snap,
                                columns=[f"D{_jj+1}" for _jj in range(_nc)],
                                index=[f"S{_ii+1}" for _ii in range(_nr)]
                            )
                            def _fmt_sn(v):
                                if v < 1e-9: return "—"
                                return str(int(v)) if v == int(v) else f"{v:.2f}"
                            def _hl_sn(v):
                                return "background-color:#e3f2fd; font-weight:bold; color:#0d47a1" if v > 1e-9 else ""
                            st.dataframe(_sdf.style.map(_hl_sn).format(_fmt_sn),
                                         use_container_width=True)

                # ── MODI iterations ───────────────────────────────────────────
                _iters = res.get("iterations", [])
                if _iters:
                    with st.expander("🔄 Fase 2 – Iteraciones MODI (Simplex de Transporte)", expanded=True):
                        # Summary table
                        _sum_rows = [{
                            "Iter":        it["Iter"],
                            "Costo":       it["Costo"],
                            "Min RC":      it["Min RC"],
                            "Estado":      it["Estado"],
                            "Celda entra": it.get("entering") or "—",
                            "θ (theta)":   it.get("theta") if it.get("theta") is not None else "—",
                        } for it in _iters]
                        def _style_sum(row):
                            if row.get("Estado") == "Óptimo":
                                return ["background-color:#FFD700; font-weight:bold; color:#5a4000"] * len(row)
                            return [""] * len(row)
                        st.dataframe(
                            pd.DataFrame(_sum_rows).style.apply(_style_sum, axis=1),
                            hide_index=True, use_container_width=True
                        )
                        st.caption("🟡 Fila dorada = solución óptima (min RC ≥ 0).")
                        st.markdown("---")
                        st.markdown("**Detalle por iteración:**")
                        for _it in _iters:
                            _is_opt = _it["Estado"] == "Óptimo"
                            _badge  = "✅ Óptimo" if _is_opt else "🔄 Mejorando"
                            with st.expander(
                                f"Iteración {_it['Iter']} — ${_it['Costo']:,.4f}  |  Min RC: {_it['Min RC']}  {_badge}",
                                expanded=False
                            ):
                                _ia, _ib = st.columns([2, 1])
                                with _ia:
                                    st.markdown("**Asignación actual:**")
                                    _snp = _it.get("snapshot")
                                    if _snp is not None:
                                        _nr, _nc = _snp.shape
                                        _snp_df = pd.DataFrame(
                                            _snp,
                                            columns=[f"D{_jj+1}" for _jj in range(_nc)],
                                            index=[f"S{_ii+1}" for _ii in range(_nr)]
                                        )
                                        def _fmt_it(v):
                                            if v < 1e-9: return "—"
                                            return str(int(v)) if v == int(v) else f"{v:.4f}"
                                        def _hl_it(v):
                                            return "background-color:#e8f5e9; font-weight:bold; color:#1b5e20" if v > 1e-9 else ""
                                        st.dataframe(
                                            _snp_df.style.map(_hl_it).format(_fmt_it),
                                            use_container_width=True
                                        )
                                with _ib:
                                    _uu = _it.get("u", [])
                                    _vv = _it.get("v", [])
                                    if _uu:
                                        st.markdown("**Variables duales:**")
                                        _dual_rows = ([{"Var": f"u{_ii+1}", "Valor": _uu[_ii]} for _ii in range(len(_uu))]
                                                      + [{"Var": f"v{_jj+1}", "Valor": _vv[_jj]} for _jj in range(len(_vv))])
                                        st.dataframe(pd.DataFrame(_dual_rows), hide_index=True, use_container_width=True)
                                _rc = _it.get("rc", {})
                                if _rc:
                                    st.markdown("**Costos reducidos (no básicas):**")
                                    _rc_rows = [{"Celda": _k, "c_ij − u_i − v_j": _rv}
                                                for _k, _rv in sorted(_rc.items(), key=lambda x: x[1])]
                                    def _style_rc(row):
                                        _rv = row.get("c_ij − u_i − v_j", 0)
                                        if _rv < -1e-6:
                                            return ["background-color:#ffebee; color:#b71c1c; font-weight:bold"] * len(row)
                                        return [""] * len(row)
                                    st.dataframe(
                                        pd.DataFrame(_rc_rows).style.apply(_style_rc, axis=1),
                                        hide_index=True, use_container_width=True
                                    )
                                    st.caption("🔴 Rojo = RC negativo → entra a la base.")
                                if _it.get("entering"):
                                    st.info(f"📥 **Celda entrante:** `{_it['entering']}` (RC = {_it['Min RC']})"
                                            + (f"  |  **Loop:** `{'→'.join(_it['loop'])}→{_it['loop'][0]}`" if _it.get("loop") else "")
                                            + (f"  |  **θ = {_it['theta']}**" if _it.get("theta") is not None else ""))


elif module == "Networks":
    st.subheader("🕸️ Modelos de Redes")
    from modules.networks import NetworkSolver
    import plotly.graph_objects as go
    import math as _math

    net_type = st.radio(
        "Técnica",
        ["MST – Árbol de Expansión Mínima", "Flujo Máximo", "Flujo de Costo Mínimo"],
        horizontal=True, key="net_type"
    )
    is_mst    = net_type.startswith("MST")
    is_maxflow = net_type == "Flujo Máximo"
    is_mcf    = net_type.startswith("Flujo de Costo")

    _col_cfg, _col_tbl = st.columns([1, 2])
    with _col_cfg:
        if is_mst:
            st.info("**MST:** Conectar todos los nodos al mínimo costo total.\n\n"
                    "Aristas **no dirigidas** — ingresa el peso.")
            _mst_algo = st.radio("Algoritmo", ["Kruskal", "Prim"], horizontal=True, key="mst_algo")
        elif is_maxflow:
            st.info("**Flujo Máximo:** Cuánto puede fluir de fuente a sumidero.\n\n"
                    "Aristas **dirigidas** — ingresa la **capacidad**.")
        else:
            st.info("**Flujo de Costo Mínimo:** Enviar X unidades al menor costo posible.\n\n"
                    "Cada arista tiene **capacidad** y **costo por unidad**.")
    with _col_tbl:
        if is_mcf:
            st.write("**Aristas** (u, v, Capacidad, Costo/unidad):")
            _mcf_default = pd.DataFrame(
                [
                    # Super-fuente → Fábricas (cap = producción, costo = $0)
                    ["S",  "F1",  50,   0],
                    ["S",  "F2",  40,   0],
                    # Fábricas → destinos
                    ["F1", "W1", 999, 900],
                    ["F1", "F2",  10, 200],
                    ["F1", "DC", 999, 400],
                    ["F2", "DC", 999, 300],
                    # DC → Bodegas
                    ["DC", "W1", 999, 200],
                    ["DC", "W2",  80, 100],
                    # Entre Bodegas (bidireccional)
                    ["W1", "W2", 999, 300],
                    ["W2", "W1", 999, 300],
                    # Bodegas → Super-sumidero (cap = demanda, costo = $0)
                    ["W1", "T",   30,   0],
                    ["W2", "T",   60,   0],
                ],
                columns=["u","v","Capacidad","Costo/unidad"]
            )
            _net_edges_df = st.data_editor(_mcf_default, num_rows="dynamic",
                                            key="net_edges_mcf", use_container_width=True)
            _col_w_name = "Capacidad"
        else:
            _col_w_name = "Peso" if is_mst else "Capacidad"
            st.write(f"**Aristas** (nodo u, nodo v, {_col_w_name}):")
            _net_default = pd.DataFrame(
                [["O","A",2],["O","B",5],["O","C",4],
                 ["B","C",1],["B","A",2],["B","D",4],["B","E",3],
                 ["A","D",7],["C","E",4],["E","D",1],["D","T",5],["E","T",7]],
                columns=["u", "v", _col_w_name]
            )
            _net_edges_df = st.data_editor(_net_default, num_rows="dynamic",
                                            key="net_edges", use_container_width=True)

    if is_maxflow or is_mcf:
        _net_nodes_raw = sorted(set(
            str(r["u"]) for _, r in _net_edges_df.iterrows() if str(r["u"]).strip()
        ) | set(
            str(r["v"]) for _, r in _net_edges_df.iterrows() if str(r["v"]).strip()
        ))
        _cf1, _cf2, _cf3 = st.columns([1,1,1])
        with _cf1:
            _mf_source = st.selectbox("Nodo fuente (s)", _net_nodes_raw, index=0, key="mf_source")
        with _cf2:
            _mf_sink = st.selectbox("Nodo sumidero (t)", _net_nodes_raw,
                                     index=len(_net_nodes_raw)-1, key="mf_sink")
        if is_mcf:
            with _cf3:
                _mcf_req = st.number_input("Flujo requerido", min_value=0.0, value=10.0,
                                            step=1.0, key="mcf_req")

    if st.button("▶ Resolver Red", type="primary", use_container_width=True):
        try:
            _net_edges = [
                (str(r["u"]), str(r["v"]), float(r[_col_w_name]))
                for _, r in _net_edges_df.iterrows()
                if str(r["u"]).strip() and str(r["v"]).strip()
            ]
            _net_nodes = list(set(n for u, v, _ in _net_edges for n in (u, v)))
            _net_solver = NetworkSolver(_net_nodes, _net_edges)

            def _draw_network(all_edges, highlight_edges=None, directed=False, title=""):
                _nodes_set = sorted(set(n for u, v, _ in all_edges for n in (u, v)))
                _N = len(_nodes_set)
                _pos = {nd: (_math.cos(2*_math.pi*i/_N), _math.sin(2*_math.pi*i/_N))
                        for i, nd in enumerate(_nodes_set)}
                _hl = set((str(u), str(v)) for u, v, _ in (highlight_edges or []))
                _hl |= set((str(v), str(u)) for u, v, _ in (highlight_edges or []))
                _fig = go.Figure()
                _drawn = set()
                for u, v, w in all_edges:
                    _key = tuple(sorted([u, v]))
                    if not directed and _key in _drawn: continue
                    _drawn.add(_key)
                    x0,y0 = _pos[u]; x1,y1 = _pos[v]
                    _in_hl = (u,v) in _hl
                    _clr = "#FFD700" if _in_hl else "#ccc"
                    _wid = 5 if _in_hl else 1.5
                    mx,my = (x0+x1)/2,(y0+y1)/2
                    if directed:
                        _fig.add_annotation(x=x1,y=y1,ax=x0,ay=y0,
                                            xref="x",yref="y",axref="x",ayref="y",
                                            showarrow=True,arrowhead=3,arrowsize=1.5,
                                            arrowwidth=_wid,arrowcolor=_clr)
                    else:
                        _fig.add_trace(go.Scatter(x=[x0,x1,None],y=[y0,y1,None],mode="lines",
                                                   line=dict(color=_clr,width=_wid),
                                                   showlegend=False,hoverinfo="skip"))
                    _fig.add_annotation(x=mx,y=my,text=f"<b>{w:g}</b>",showarrow=False,
                                        font=dict(size=10,color="#333"),
                                        bgcolor="rgba(255,255,255,0.85)",borderpad=2)
                for nd in _nodes_set:
                    x,y = _pos[nd]
                    _fig.add_trace(go.Scatter(x=[x],y=[y],mode="markers+text",
                                              marker=dict(size=28,color="#0068c9",
                                                          line=dict(color="white",width=2)),
                                              text=[nd],textposition="middle center",
                                              textfont=dict(color="white",size=11),
                                              showlegend=False,hoverinfo="skip"))
                _fig.update_layout(height=380,title=title,
                                   margin=dict(l=10,r=10,t=30,b=10),
                                   xaxis=dict(visible=False),yaxis=dict(visible=False),
                                   plot_bgcolor="#f8f9fa",paper_bgcolor="white")
                return _fig

            if is_mst:
                _res = (_net_solver.solve_mst_kruskal() if _mst_algo == "Kruskal"
                        else _net_solver.solve_mst_prim())

                st.success(f"✅ **Costo total del MST: {_res['total_cost']:g}**  "
                           f"({len(_res['mst_edges'])} aristas, algoritmo: {_res['algorithm']})")

                st.markdown("### 🌲 Árbol de Expansión Mínima (resultado final)")
                st.plotly_chart(
                    _draw_network(_net_edges, highlight_edges=_res["mst_edges"],
                                  directed=False, title="MST (dorado = incluida)"),
                    use_container_width=True
                )
                st.caption("🟡 Aristas doradas = MST  |  Grises = rechazadas")

                st.markdown("### Aristas del MST")
                _mst_tbl = [{ "Arista": f"{u}—{v}", "Peso": w }
                            for u, v, w in _res["mst_edges"]]
                _mst_df2 = pd.DataFrame(_mst_tbl)
                def _hl_mst(row):
                    return ["background-color:#e8f5e9; color:#1b5e20; font-weight:bold"] * len(row)
                st.dataframe(_mst_df2.style.apply(_hl_mst, axis=1),
                             hide_index=True, use_container_width=True)
                st.metric("Costo Total", f"{_res['total_cost']:g}")

                with st.expander(f"📋 Pasos del Algoritmo {_res['algorithm']}", expanded=True):
                    _disp = []
                    for _s in _res["steps"]:
                        if _res["algorithm"] == "Kruskal":
                            _disp.append({"Paso": _s["Paso"], "Arista": _s["Arista"],
                                          "Peso": _s["Peso"], "¿Crea ciclo?": _s["¿Crea ciclo?"],
                                          "Acción": _s["Acción"], "Costo acum.": _s["Costo acum."]})
                        else:
                            _disp.append({"Paso": _s["Paso"], "Arista elegida": _s["Arista elegida"],
                                          "Peso": _s["Peso"], "Nodos en árbol": _s["Nodos en árbol"],
                                          "Costo acum.": _s["Costo acum."]})
                    def _style_disp(row):
                        _a = str(row.get("Acción", ""))
                        if "Incluida" in _a or "elegida" in _a:
                            return ["background-color:#e8f5e9; color:#1b5e20; font-weight:bold"] * len(row)
                        if "Rechazada" in _a:
                            return ["background-color:#ffebee; color:#b71c1c"] * len(row)
                        return ["background-color:#e8f5e9"] * len(row)
                    st.dataframe(pd.DataFrame(_disp).style.apply(_style_disp, axis=1),
                                 hide_index=True, use_container_width=True)
                    if _res["algorithm"] == "Kruskal":
                        st.caption("🟢 Verde = incluida en MST  |  🔴 Rojo = rechazada (crea ciclo)")
                    st.markdown("---")
                    st.markdown("**Construcción paso a paso:**")
                    for _s in _res["steps"]:
                        _lbl = _s.get("Arista", _s.get("Arista elegida", ""))
                        st.markdown(f"**Paso {_s['Paso']}** — `{_lbl}` (peso={_s['Peso']}) → Acumulado: **{_s['Costo acum.']:g}**")
                        st.plotly_chart(
                            _draw_network(_net_edges, highlight_edges=_s["mst_so_far"], directed=False),
                            use_container_width=True, key=f"mst_s_{_s['Paso']}"
                        )

                # ─── Formato C / C' estilo examen ───
                _all_mst_nodes = set(str(n) for u, v, _ in _net_edges for n in (u, v))
                render_mst_cuts_format(_net_edges, _all_mst_nodes,
                                        start_node=sorted(_all_mst_nodes)[0])

            elif is_maxflow:  # Max Flow
                _res = _net_solver.solve_max_flow(_mf_source, _mf_sink)
                st.success(f"✅ **Flujo Máximo: {_res['max_flow']:g}**  "
                           f"de `{_mf_source}` → `{_mf_sink}`  "
                           f"({len(_res['iterations'])} caminos aumentantes)")

                _sat = [(r["Arista"].split(" → ")[0], r["Arista"].split(" → ")[1], r["Capacidad"])
                        for r in _res["edge_flows"] if "Sí" in r["Saturada"]]
                st.markdown("### 🌊 Red de Flujo")
                st.plotly_chart(
                    _draw_network(_net_edges, highlight_edges=_sat, directed=True,
                                  title="Red de flujo (dorado = saturada)"),
                    use_container_width=True
                )
                st.caption("🟡 Aristas doradas = saturadas  |  Grises = con holgura")

                st.markdown("### Flujo por Arista")
                _ef_df = pd.DataFrame(_res["edge_flows"])
                def _style_ef(row):
                    if "Sí" in str(row.get("Saturada", "")):
                        return ["background-color:#FFD700; font-weight:bold; color:#5a4000"] * len(row)
                    return [""] * len(row)
                st.dataframe(_ef_df.style.apply(_style_ef, axis=1),
                             hide_index=True, use_container_width=True)

                with st.expander("📋 Caminos Aumentantes (iteraciones)", expanded=True):
                    _it_df2 = pd.DataFrame(_res["iterations"])
                    def _style_it2(row):
                        if row.name == len(_res["iterations"]) - 1:
                            return ["background-color:#FFD700; font-weight:bold; color:#5a4000"] * len(row)
                        return [""] * len(row)
                    st.dataframe(_it_df2.style.apply(_style_it2, axis=1),
                                 hide_index=True, use_container_width=True)
                    st.caption("🟡 Última fila = flujo máximo total.")

                # ─── Capacidades RESIDUALES (segunda gráfica del examen) ───
                st.markdown("### 🔄 Capacidades Residuales (al terminar el algoritmo)")
                st.caption("Esta es la **segunda gráfica** que aparece en exámenes tipo 2010. "
                           "Para cada arco original `u → v`: el número hacia adelante (→) es lo que "
                           "TODAVÍA podrías mandar; el número hacia atrás (←) es el flujo que YA enviaste "
                           "(y que podrías cancelar).")

                _res_df = pd.DataFrame(_res["residual_summary"])
                def _style_res(row):
                    if row.get("Cap. residual (→)", 1) <= 1e-6:
                        return ["background-color:#fff3cd; font-weight:bold; color:#856404"] * len(row)
                    return [""] * len(row)
                st.dataframe(_res_df.style.apply(_style_res, axis=1),
                             hide_index=True, use_container_width=True)
                st.caption("🟡 Filas amarillas = arcos saturados (residual forward = 0).")

                # ─── Gráfica residual estilo examen ───
                st.markdown("**📊 Gráfica residual estilo examen** "
                            "(layout en capas, cada arco etiquetado **`forward | backward`**):")
                st.caption("**Forward** = capacidad disponible (lo que aún puedes mandar). "
                           "**Backward** = flujo enviado (lo que podrías cancelar). "
                           "Arcos en **naranja** = saturados (forward = 0).")
                st.plotly_chart(
                    draw_max_flow_residual_graph(
                        _net_edges, _res["residual_summary"],
                        _mf_source, _mf_sink,
                        title=f"Red residual — flujo máximo = {_res['max_flow']:g}"
                    ),
                    use_container_width=True, key="mf_residual_graph"
                )

            else:  # Minimum Cost Flow
                _mcf_cost_edges = [
                    (str(r["u"]), str(r["v"]), float(r["Capacidad"]), float(r["Costo/unidad"]))
                    for _, r in _net_edges_df.iterrows()
                    if str(r["u"]).strip() and str(r["v"]).strip()
                ]
                _res = _net_solver.solve_min_cost_flow(
                    _mf_source, _mf_sink, _mcf_req, cost_edges=_mcf_cost_edges
                )
                if _res["feasible"]:
                    st.success(f"✅ **Costo Mínimo: {_res['total_cost']:g}**  "
                               f"para enviar **{_res['total_flow']:g} / {_res['required_flow']:g}** unidades  "
                               f"de `{_mf_source}` → `{_mf_sink}`")
                else:
                    st.warning(f"⚠️ Solo se enviaron **{_res['total_flow']:g}** de "
                               f"**{_res['required_flow']:g}** unidades. Red sin capacidad suficiente.")

                _km1, _km2, _km3 = st.columns(3)
                _km1.metric("Flujo enviado", f"{_res['total_flow']:g} u")
                _km2.metric("Costo total", f"{_res['total_cost']:g}")
                _km3.metric("Costo prom./unidad",
                            f"{_res['total_cost']/_res['total_flow']:.2f}" if _res['total_flow'] > 0 else "—")

                _mcf_draw_edges = [(u, v, cap) for u, v, cap, _ in _mcf_cost_edges]
                _mcf_flow_edges = [
                    (r["Arista"].split(" → ")[0], r["Arista"].split(" → ")[1], r["Capacidad"])
                    for r in _res["edge_flows"] if r["Flujo"] > 1e-6
                ]
                st.markdown("### 💸 Red de Flujo de Costo Mínimo")
                st.plotly_chart(
                    _draw_network(_mcf_draw_edges, highlight_edges=_mcf_flow_edges,
                                  directed=True, title="Flujo de Costo Mínimo (dorado = con flujo)"),
                    use_container_width=True
                )
                st.caption("🟡 Dorado = aristas con flujo  |  Gris = sin flujo")

                st.markdown("### Flujo y Costo por Arista")
                _mcf_ef_df = pd.DataFrame(_res["edge_flows"])
                def _style_mcf_ef(row):
                    if row.get("Flujo", 0) > 1e-6:
                        return ["background-color:#e8f5e9; color:#1b5e20; font-weight:bold"] * len(row)
                    return [""] * len(row)
                st.dataframe(_mcf_ef_df.style.apply(_style_mcf_ef, axis=1),
                             hide_index=True, use_container_width=True)

                with st.expander("📋 Caminos Aumentantes – Successive Shortest Paths", expanded=True):
                    _mcf_it_df = pd.DataFrame(_res["iterations"])
                    def _style_mcf_it(row):
                        if row.name == len(_res["iterations"]) - 1:
                            return ["background-color:#FFD700; font-weight:bold; color:#5a4000"] * len(row)
                        return [""] * len(row)
                    st.dataframe(_mcf_it_df.style.apply(_style_mcf_it, axis=1),
                                 hide_index=True, use_container_width=True)
                    st.caption("Cada iteración: camino de menor costo en el grafo residual → máximo flujo posible.")

        except Exception as _net_err:
            import traceback
            st.error(f"❌ Error: {_net_err}")
            st.code(traceback.format_exc())

elif module == "Shortest Path":
    st.subheader("🗺️ Shortest Path")
    from modules.shortest_path import ShortestPathSolver
    import plotly.graph_objects as go
    import math

    st.markdown("Ingresa las aristas del grafo y elige el nodo origen y destino.")

    col_cfg, col_tbl = st.columns([1, 2])

    with col_cfg:
        sp_directed = st.checkbox("Grafo dirigido (→)", value=False)
        sp_algo = st.selectbox("Algoritmo", ["Dijkstra", "Bellman-Ford"])
        st.caption("Bellman-Ford soporta pesos negativos.")

    with col_tbl:
        st.write("**Aristas** (nodo origen, nodo destino, peso):")
        _sp_default = pd.DataFrame(
            [["A","B",4],["A","C",2],["B","C",1],["B","D",5],["C","D",8],["C","E",10],["D","E",2]],
            columns=["Desde","Hasta","Peso"]
        )
        sp_edges_df = st.data_editor(_sp_default, num_rows="dynamic", key="sp_edges",
                                     use_container_width=True)

    # Build node list from current edges
    _sp_nodes_set = set()
    for _, r in sp_edges_df.iterrows():
        _sp_nodes_set.add(str(r["Desde"]))
        _sp_nodes_set.add(str(r["Hasta"]))
    _sp_nodes_list = sorted(_sp_nodes_set)

    if _sp_nodes_list:
        col_src, col_tgt = st.columns(2)
        with col_src:
            sp_source = st.selectbox("Nodo Origen", _sp_nodes_list, index=0, key="sp_source")
        with col_tgt:
            sp_target = st.selectbox("Nodo Destino", _sp_nodes_list,
                                     index=len(_sp_nodes_list)-1, key="sp_target")

        if st.button("🔍 Resolver Shortest Path", type="primary", use_container_width=True):
            try:
                _sp_edges = [(str(r["Desde"]), str(r["Hasta"]), float(r["Peso"]))
                             for _, r in sp_edges_df.iterrows()
                             if str(r["Desde"]).strip() and str(r["Hasta"]).strip()]

                sp_solver = ShortestPathSolver(_sp_edges, directed=sp_directed)

                if sp_algo == "Dijkstra":
                    sp_res = sp_solver.dijkstra(sp_source, sp_target)
                else:
                    sp_res = sp_solver.bellman_ford(sp_source, sp_target)

                # ── Result header ─────────────────────────────────────
                if sp_res["status"] == "Optimal":
                    path_str = " → ".join(sp_res["path"])
                    st.success(f"✅ **Camino óptimo:** `{path_str}`")
                    st.metric("Costo Total del Camino", f"{sp_res['path_cost']:g}")
                elif sp_res["status"] == "No Path":
                    st.error(f"❌ No existe camino entre **{sp_source}** y **{sp_target}**.")
                elif "ciclo negativo" in sp_res["status"].lower():
                    st.error("⚠️ Ciclo negativo detectado — el camino mínimo no está definido.")
                else:
                    st.info(f"Estado: {sp_res['status']}")

                # ── Distances from source ─────────────────────────────
                st.markdown("### Distancias desde el nodo origen")
                _dist_data = [
                    {"Nodo": n,
                     "Distancia desde " + sp_source: ("∞" if d == math.inf else round(d, 4)),
                     "En camino óptimo": "⭐" if (sp_res["path"] and n in sp_res["path"]) else ""}
                    for n, d in sorted(sp_res["distances"].items())
                ]
                _dist_df = pd.DataFrame(_dist_data)

                def _style_sp_dist(row):
                    if row.get("En camino óptimo") == "⭐":
                        return ["background-color:#FFD700; font-weight:bold; color:#5a4000"] * len(row)
                    return [""] * len(row)

                st.dataframe(_dist_df.style.apply(_style_sp_dist, axis=1),
                             hide_index=True, use_container_width=True)

                # ── Iteration table ───────────────────────────────────
                if sp_res.get("iterations"):
                    with st.expander("📋 Tabla de iteraciones paso a paso", expanded=True):
                        _it_df = pd.DataFrame(sp_res["iterations"])
                        st.dataframe(_it_df, hide_index=True, use_container_width=True)

                # ── Graph visualization ───────────────────────────────
                st.markdown("### 🕸️ Visualización del Grafo")
                try:
                    # Simple circular layout
                    import math as _m
                    _n = len(_sp_nodes_list)
                    _pos = {
                        nd: (_m.cos(2 * _m.pi * i / _n), _m.sin(2 * _m.pi * i / _n))
                        for i, nd in enumerate(_sp_nodes_list)
                    }

                    _path_edges = set()
                    if sp_res.get("path") and len(sp_res["path"]) > 1:
                        for _pi in range(len(sp_res["path"]) - 1):
                            _path_edges.add((sp_res["path"][_pi], sp_res["path"][_pi+1]))

                    _fig_sp = go.Figure()

                    # For undirected graphs, deduplicate edges so A-B and B-A are drawn only once
                    _drawn_edges = set()
                    _edges_to_draw = []
                    for _u, _v, _w in _sp_edges:
                        if sp_directed:
                            _edges_to_draw.append((_u, _v, _w))
                        else:
                            _key = tuple(sorted([_u, _v]))
                            if _key not in _drawn_edges:
                                _drawn_edges.add(_key)
                                _edges_to_draw.append((_u, _v, _w))

                    # Draw edges
                    for _u, _v, _w in _edges_to_draw:
                        _x0, _y0 = _pos[_u]
                        _x1, _y1 = _pos[_v]
                        # Optimal if this edge OR its reverse is in the shortest path
                        _is_opt = (
                            (_u, _v) in _path_edges or
                            (_v, _u) in _path_edges
                        )
                        _clr = "#FFD700" if _is_opt else "#aaa"
                        _wid = 4 if _is_opt else 1.5

                        _mx, _my = (_x0 + _x1) / 2, (_y0 + _y1) / 2

                        if sp_directed:
                            # Draw directed arrow using annotation
                            _fig_sp.add_annotation(
                                x=_x1, y=_y1,
                                ax=_x0, ay=_y0,
                                xref="x", yref="y", axref="x", ayref="y",
                                showarrow=True,
                                arrowhead=3, arrowsize=1.5, arrowwidth=_wid,
                                arrowcolor=_clr,
                            )
                        else:
                            # Undirected: plain line (reciprocal, no arrow needed)
                            _fig_sp.add_trace(go.Scatter(
                                x=[_x0, _x1, None], y=[_y0, _y1, None],
                                mode="lines",
                                line=dict(color=_clr, width=_wid),
                                showlegend=False, hoverinfo="skip"
                            ))

                        # Weight label at midpoint
                        _fig_sp.add_annotation(
                            x=_mx, y=_my, text=f"<b>{_w}</b>",
                            showarrow=False,
                            font=dict(size=10, color="#222"),
                            bgcolor="rgba(255,255,255,0.85)",
                            borderpad=2,
                        )

                    # Draw nodes
                    for nd in _sp_nodes_list:
                        _x, _y = _pos[nd]
                        _is_src = nd == sp_source
                        _is_tgt = nd == sp_target
                        _in_path = sp_res.get("path") and nd in sp_res["path"]
                        _color = "#FFD700" if _in_path else ("#0068c9" if _is_src else ("#e33" if _is_tgt else "#555"))
                        _fig_sp.add_trace(go.Scatter(
                            x=[_x], y=[_y],
                            mode="markers+text",
                            marker=dict(size=30, color=_color, line=dict(color="white", width=2)),
                            text=[nd], textposition="middle center",
                            textfont=dict(color="white", size=12, family="monospace"),
                            showlegend=False,
                            hovertemplate=f"<b>{nd}</b><br>Dist: {sp_res['distances'].get(nd, '∞')}<extra></extra>"
                        ))

                    _fig_sp.update_layout(
                        height=420,
                        margin=dict(l=10, r=10, t=30, b=10),
                        xaxis=dict(visible=False), yaxis=dict(visible=False),
                        plot_bgcolor="#f8f9fa", paper_bgcolor="white",
                        showlegend=False,
                    )
                    st.plotly_chart(_fig_sp, use_container_width=True)
                    st.caption("🟡 Nodos/aristas en dorado = camino óptimo  |  🔵 Origen  |  🔴 Destino")
                except Exception as _viz_err:
                    st.warning(f"No se pudo renderizar el grafo: {_viz_err}")

            except Exception as _sp_err:
                st.error(f"Error al resolver: {_sp_err}")
    else:
        st.info("Agrega al menos una arista en la tabla para comenzar.")

elif module == "Integer Programming":
    st.subheader("Integer / Mixed-Integer Programming")
    # Lazy import to avoid import errors if module not yet perfect or deps missing
    from modules.integer_programming import IPSolver
    
    col1, col2 = st.columns([1, 1])
    with col1:
        obj_type = st.selectbox("Objective", ["Maximize", "Minimize"])
        obj_func = st.text_input("Z =", "3x + 4y")
        constraints = st.text_area("Constraints", "2x + y <= 10\nx + 3y <= 12")
        
        st.write("Variable Types:")
        # Simple string-based selector for now
        int_vars = st.text_input("Integer Variables (comma sep)", "x, y")
        bin_vars = st.text_input("Binary Variables (comma sep)", "")
        
        if st.button("Solve IP"):
            maximize = (obj_type == "Maximize")
            constraints_list = constraints.split('\n')
            integers = [v.strip() for v in int_vars.split(',')] if int_vars else []
            binaries = [v.strip() for v in bin_vars.split(',')] if bin_vars else []
            
            solver = IPSolver(obj_func, constraints_list, maximize, integers, binaries)
            res = solver.solve()
            
            with col2:
                if res['status'] == 'Optimal':
                    st.success("Optimal Solution Found")
                    st.metric(label="Objective", value=str(res['objective']))
                    st.write("Variables:", res['variables'])
                else:
                    st.error(f"Status: {res['status']}")
                    if 'message' in res:
                        st.write(res['message'])

elif module == "Dynamic Programming":
    st.subheader("Dynamic Programming")
    st.info("Generic DP Module: Demonstrating structure for Resource Allocation")
    from modules.dynamic_programming import DPSolver
    
    # Placeholder UI for generic DP
    st.write("**Problem Configuration (Example)**")
    st.text_input("Stages (e.g. Years)", "3")
    st.text_input("Total State Resource", "10")
    
    if st.button("Solve DP Example"):
        solver = DPSolver([], [], [], None, None)
        res = solver.solve()
        st.write("Optimal Value:", res['optimal_value'])
        st.dataframe(res['policy_table'])

# =============================================================================
#  📚 TAREAS — Ejercicios precargados (Tareas 7 a 10 — Hillier 11e)
# =============================================================================
elif module == "📚 Tareas":
    st.subheader("📚 Tareas IIO-13150 — Ejercicios precargados")
    from modules.homework import TAREAS
    from modules.transport import TransportSolver
    from modules.networks import NetworkSolver
    from modules.shortest_path import ShortestPathSolver
    import numpy as np

    st.caption("Selecciona una tarea y un ejercicio. El programa carga los datos del libro Hillier 11e "
               "y resuelve automáticamente.")

    # ── Selector ────────────────────────────────────────────────────────────
    _csel1, _csel2 = st.columns([1, 2])
    with _csel1:
        _tarea_key = st.selectbox("Tarea", list(TAREAS.keys()), key="hw_tarea")
    _ejercicios = TAREAS[_tarea_key]["ejercicios"]
    _opts = [f"{e['id']} — {e['titulo']}" for e in _ejercicios]
    with _csel2:
        _idx = st.selectbox("Ejercicio", range(len(_opts)),
                            format_func=lambda i: _opts[i], key="hw_idx")

    _ej = _ejercicios[_idx]

    st.markdown(f"### 📝 {_ej['id']} — {_ej['titulo']}")
    with st.expander("📖 Enunciado completo", expanded=True):
        st.text(_ej.get("enunciado", "(Sin enunciado)"))

    if _ej.get("nota"):
        st.info(f"ℹ️ **Nota técnica:** {_ej['nota']}")

    _tipo = _ej["tipo"]
    _datos = _ej.get("datos", {})

    # ── Helpers para tablas ─────────────────────────────────────────────────
    def _hw_fmt(v):
        if abs(v) < 1e-9: return "—"
        return str(int(v)) if v == int(v) else f"{v:.4g}"

    def _hw_hl_alloc(v):
        return ("background-color:#e8f5e9; font-weight:bold; color:#1b5e20"
                if v > 1e-9 else "")

    # ────────────────────────────────────────────────────────────────────────
    #  TIPO: reading
    # ────────────────────────────────────────────────────────────────────────
    if _tipo == "reading":
        st.warning("📚 Este es un ejercicio de **lectura/discusión** — no es computacional.")
        st.markdown(
            "**Cómo resolverlo:** lee el artículo referenciado en la Sec. 10.3 del Hillier 11e "
            "sobre el estudio en la industria forestal sueca. Redacta una respuesta de 1-2 párrafos "
            "que cubra: (1) cómo se aplicaron modelos de optimización en redes y (2) los beneficios "
            "financieros y no financieros obtenidos."
        )

    # ────────────────────────────────────────────────────────────────────────
    #  TIPO: transportation / transportation_full
    # ────────────────────────────────────────────────────────────────────────
    elif _tipo in ("transportation", "transportation_full"):
        _row_lbl = _datos["row_labels"]
        _col_lbl = _datos["col_labels"]

        st.markdown("#### 📋 Datos del problema")
        _cost_df = pd.DataFrame(_datos["costs"], columns=_col_lbl, index=_row_lbl)
        st.markdown("**Matriz de costos c_ij:**")
        st.dataframe(_cost_df.style.format("{:.4g}"), use_container_width=True)

        _cs, _cd = st.columns(2)
        with _cs:
            st.markdown("**Oferta:**")
            st.dataframe(pd.DataFrame({"Oferta": _datos["supply"]}, index=_row_lbl),
                         use_container_width=True)
        with _cd:
            st.markdown("**Demanda:**")
            st.dataframe(pd.DataFrame({"Demanda": _datos["demand"]}, index=_col_lbl),
                         use_container_width=True)

        _ts = float(sum(_datos["supply"]))
        _td = float(sum(_datos["demand"]))
        if abs(_ts - _td) < 1e-9:
            st.success(f"✅ Balanceado: oferta = demanda = {_ts:g}")
        else:
            st.warning(f"⚠️ Desbalanceado: oferta={_ts:g}, demanda={_td:g}. "
                       f"Se agregará fila/columna dummy automáticamente.")

        _met = _ej.get("metodo", "min_cost")
        _met_disp = {"min_cost": "Costo Mínimo", "northwest": "Esquina Noroeste"}.get(_met, _met)
        st.caption(f"Método sugerido: **{_met_disp}** + Optimización MODI")

        # ─── Tabla balanceada + Formulación PPL (incisos a, d, e) ───
        with st.expander("📋 Tabla balanceada + Formulación PPL  (incisos 'a', 'd', 'e')",
                         expanded=True):
            render_balanced_transport_and_lp(
                _datos["costs"], _datos["supply"], _datos["demand"],
                row_lbl=_row_lbl, col_lbl=_col_lbl
            )

        if st.button(f"▶ Resolver {_ej['id']}", type="primary",
                     use_container_width=True, key=f"hw_solve_{_ej['id']}"):
            try:
                _solver = TransportSolver(
                    np.array(_datos["costs"], dtype=float),
                    list(_datos["supply"]), list(_datos["demand"])
                )
                _res = _solver.solve_initial(method=_met)

                # ─── Métrica principal ───
                _opt_cost = _res["total_cost"]
                # Si es maximización (todos los costos ≤ 0 → 9.1-5), mostrar utilidad
                if all(c <= 0 for row in _datos["costs"] for c in row):
                    st.success(f"✅ **Utilidad máxima: ${-_opt_cost:,.4f}**  "
                               f"(costo equivalente: ${_opt_cost:,.4f})")
                else:
                    st.success(f"✅ **Costo óptimo: ${_opt_cost:,.4f}**")
                    if "initial_cost" in _res:
                        st.caption(f"Costo inicial (antes de MODI): ${_res['initial_cost']:,.4f}")

                # ─── Asignación óptima ───
                _alloc = _res["allocation"]
                _alloc_df = pd.DataFrame(_alloc, columns=_col_lbl, index=_row_lbl)
                st.markdown("**📦 Asignación óptima x_ij:**")
                st.dataframe(_alloc_df.style.map(_hw_hl_alloc).format(_hw_fmt),
                             use_container_width=True)

                # ─── Solución INICIAL (Fase 1) + eij sobre la BFS inicial ───
                _p1 = _res.get("phase1_steps", [])
                if _p1:
                    _final_p1 = _p1[-1].get("snapshot")
                    if _final_p1 is not None:
                        st.markdown("**🟦 Solución inicial (Fase 1 – Costo Mínimo / NW Corner):**")
                        _init_df = pd.DataFrame(_final_p1, columns=_col_lbl + [
                            f"Dummy{k+1}" for k in range(_final_p1.shape[1] - len(_col_lbl))
                        ], index=_row_lbl + [
                            f"Dummy{k+1}" for k in range(_final_p1.shape[0] - len(_row_lbl))
                        ])
                        st.dataframe(_init_df.style.map(_hw_hl_alloc).format(_hw_fmt),
                                     use_container_width=True)
                        st.caption(f"Costo de la solución inicial: ${_res['initial_cost']:,.4f}")

                # ─── Iteraciones MODI ───
                _iters = _res.get("iterations", [])
                if _iters:
                    # eij sobre la BFS inicial (iteración 0 del MODI)
                    _it0 = _iters[0]
                    if _it0.get("rc"):
                        st.markdown("**🔍 Costos reducidos eij sobre la BFS inicial (celdas cerradas):**")
                        _rc0_rows = []
                        for cell, rc_val in sorted(_it0["rc"].items(), key=lambda x: x[1]):
                            _rc0_rows.append({
                                "Celda (Sx→Dy)": cell,
                                "eij": round(rc_val, 4),
                                "Estatus": "⬅ entra a la base" if rc_val < -1e-6 else "OK (≥ 0)"
                            })
                        def _style_rc0(row):
                            if "entra" in str(row.get("Estatus", "")):
                                return ["background-color:#ffebee; color:#b71c1c; font-weight:bold"] * len(row)
                            return [""] * len(row)
                        st.dataframe(pd.DataFrame(_rc0_rows).style.apply(_style_rc0, axis=1),
                                     hide_index=True, use_container_width=True)
                        if _it0.get("entering"):
                            st.info(f"📥 **Ruta por abrir:** {_it0['entering']}  "
                                    f"|  **Flujo por enviar θ = {_it0.get('theta')}**  "
                                    f"|  eij = {_it0['Min RC']}")

                    with st.expander(f"📋 Iteraciones MODI ({len(_iters)} total)",
                                     expanded=False):
                        _summary = [{
                            "Iter": it["Iter"],
                            "Costo": it["Costo"],
                            "Min RC": it["Min RC"],
                            "Estado": it["Estado"],
                            "Celda entra": it.get("entering") or "—",
                            "θ": it.get("theta") if it.get("theta") is not None else "—",
                        } for it in _iters]
                        st.dataframe(pd.DataFrame(_summary),
                                     hide_index=True, use_container_width=True)

                # ─── Panel de Sensibilidad (sólo transportation_full) ───
                if _tipo == "transportation_full":
                    st.markdown("---")
                    st.markdown("### 📊 Análisis de Sensibilidad")
                    _sens = _solver.sensitivity_report(_alloc)
                    if "error" in _sens:
                        st.error(_sens["error"])
                    else:
                        _cu, _cv = st.columns(2)
                        with _cu:
                            st.markdown("**Precios sombra u_i (oferta):**")
                            _u_rows = [{"Origen": _row_lbl[i] if i < len(_row_lbl) else f"Dummy{i}",
                                        "u_i": _sens["u"][i]}
                                       for i in range(_sens["n_supply"]) if _sens["u"][i] is not None]
                            st.dataframe(pd.DataFrame(_u_rows), hide_index=True,
                                         use_container_width=True)
                        with _cv:
                            st.markdown("**Precios sombra v_j (demanda):**")
                            _v_rows = [{"Destino": _col_lbl[j] if j < len(_col_lbl) else f"Dummy{j}",
                                        "v_j": _sens["v"][j]}
                                       for j in range(_sens["n_demand"]) if _sens["v"][j] is not None]
                            st.dataframe(pd.DataFrame(_v_rows), hide_index=True,
                                         use_container_width=True)

                        st.markdown("**Rangos permisibles para c_ij no básicas:**")
                        if _sens["nonbasic_ranges"]:
                            st.dataframe(pd.DataFrame(_sens["nonbasic_ranges"]),
                                         hide_index=True, use_container_width=True)
                            st.caption(
                                "Cada celda no básica permanece NO básica mientras c_ij ≥ cota inferior. "
                                "Si c_ij baja por debajo, esa celda entra a la base y la solución cambia."
                            )
                        else:
                            st.info("No hay celdas no básicas en este problema.")

            except Exception as _hw_err:
                st.error(f"❌ Error al resolver: {_hw_err}")
                import traceback
                with st.expander("Trace"):
                    st.code(traceback.format_exc())

    # ────────────────────────────────────────────────────────────────────────
    #  TIPO: transportation_verify (sólo prueba de optimalidad)
    # ────────────────────────────────────────────────────────────────────────
    elif _tipo == "transportation_verify":
        _row_lbl = _datos["row_labels"]
        _col_lbl = _datos["col_labels"]

        st.markdown("#### 📋 Datos del problema")
        st.markdown("**Matriz de costos c_ij:**")
        st.dataframe(pd.DataFrame(_datos["costs"], columns=_col_lbl, index=_row_lbl).style.format("{:.4g}"),
                     use_container_width=True)

        _cs, _cd = st.columns(2)
        with _cs:
            st.markdown("**Oferta:**")
            st.dataframe(pd.DataFrame({"Oferta": _datos["supply"]}, index=_row_lbl),
                         use_container_width=True)
        with _cd:
            st.markdown("**Demanda:**")
            st.dataframe(pd.DataFrame({"Demanda": _datos["demand"]}, index=_col_lbl),
                         use_container_width=True)

        st.markdown("**BFS dada x_ij (a verificar):**")
        _bfs_df = pd.DataFrame(_datos["allocation"], columns=_col_lbl, index=_row_lbl)
        st.dataframe(_bfs_df.style.map(_hw_hl_alloc).format(_hw_fmt),
                     use_container_width=True)

        if st.button(f"▶ Verificar Optimalidad de la BFS",
                     type="primary", use_container_width=True, key=f"hw_verify_{_ej['id']}"):
            _solver = TransportSolver(
                np.array(_datos["costs"], dtype=float),
                list(_datos["supply"]), list(_datos["demand"])
            )
            _res = _solver.verify_optimality(_datos["allocation"])

            if _res["is_optimal"]:
                st.success(f"✅ **La BFS dada ES ÓPTIMA**  "
                           f"(min costo reducido = {_res['min_reduced_cost']:.4g} ≥ 0)")
            else:
                st.error(f"❌ **La BFS dada NO es óptima**  "
                         f"(min costo reducido = {_res['min_reduced_cost']:.4g} < 0)")
            st.metric("Costo total Z", f"${_res['total_cost']:,.4f}")

            _cu, _cv = st.columns(2)
            with _cu:
                st.markdown("**Variables duales u_i:**")
                st.dataframe(pd.DataFrame([
                    {"Origen": _row_lbl[i] if i < len(_row_lbl) else f"Dummy{i}",
                     "u_i": _res["u"][i]}
                    for i in range(_res["n_supply"]) if _res["u"][i] is not None
                ]), hide_index=True, use_container_width=True)
            with _cv:
                st.markdown("**Variables duales v_j:**")
                st.dataframe(pd.DataFrame([
                    {"Destino": _col_lbl[j] if j < len(_col_lbl) else f"Dummy{j}",
                     "v_j": _res["v"][j]}
                    for j in range(_res["n_demand"]) if _res["v"][j] is not None
                ]), hide_index=True, use_container_width=True)

            st.markdown("**Costos reducidos (celdas no básicas):**")
            _rc_rows = []
            for (i, j), rc_val in sorted(_res["reduced_costs"].items(), key=lambda x: x[1]):
                _r = _row_lbl[i] if i < len(_row_lbl) else f"Dummy{i}"
                _c = _col_lbl[j] if j < len(_col_lbl) else f"Dummy{j}"
                _rc_rows.append({
                    "Celda": f"{_r} → {_c}",
                    "c_ij − u_i − v_j": round(rc_val, 4),
                    "Estatus": "Entra (< 0)" if rc_val < -1e-6 else "OK (≥ 0)"
                })
            _df_rc = pd.DataFrame(_rc_rows)
            def _style_rc_hw(row):
                rv = row.get("c_ij − u_i − v_j", 0)
                if rv < -1e-6:
                    return ["background-color:#ffebee; color:#b71c1c; font-weight:bold"] * len(row)
                return [""] * len(row)
            st.dataframe(_df_rc.style.apply(_style_rc_hw, axis=1),
                         hide_index=True, use_container_width=True)
            st.caption("Si TODOS los costos reducidos son ≥ 0 → la BFS es óptima. "
                       "Si alguno es < 0 (rojo) → no es óptima y esa celda debe entrar a la base.")

    # ────────────────────────────────────────────────────────────────────────
    #  TIPO: assignment (Húngaro)
    # ────────────────────────────────────────────────────────────────────────
    elif _tipo == "assignment":
        _row_lbl = _datos["row_labels"]
        _col_lbl = _datos["col_labels"]

        st.markdown("#### 📋 Matriz de costos")
        st.dataframe(pd.DataFrame(_datos["costs"], columns=_col_lbl, index=_row_lbl).style.format("{:.4g}"),
                     use_container_width=True)

        # ─── Formulación PPL para incisos (a) y (b) ───
        with st.expander("📝 Formulación PPL/PE  (incisos 'a', 'b')", expanded=True):
            render_assignment_formulation(_datos["costs"], _row_lbl, _col_lbl)

        if st.button(f"▶ Resolver con Algoritmo Húngaro", type="primary",
                     use_container_width=True, key=f"hw_hung_{_ej['id']}"):
            _nr = len(_row_lbl); _nc = len(_col_lbl)
            _solver = TransportSolver(
                np.array(_datos["costs"], dtype=float), [1]*_nr, [1]*_nc
            )
            _res = _solver.solve_initial(method="hungarian")

            st.success(f"✅ **Costo óptimo: {_res['total_cost']:.4g}**")

            _pairs = _res.get("assignment_pairs", [])
            if _pairs:
                _labeled = []
                for p in _pairs:
                    _ri = int(p["Fuente"].lstrip("S")) - 1
                    _ci = int(p["Tarea"].lstrip("D")) - 1
                    if _ri < _nr and _ci < _nc:
                        _labeled.append({
                            "Recurso": _row_lbl[_ri],
                            "Asignado a": _col_lbl[_ci],
                            "Costo": p["Costo"],
                        })
                st.markdown("**🏆 Asignaciones óptimas:**")
                st.dataframe(pd.DataFrame(_labeled), hide_index=True, use_container_width=True)

            with st.expander("📋 Pasos del Método Húngaro", expanded=False):
                for _s in _res.get("steps", []):
                    st.markdown(f"**{_s['label']}**")
                    st.caption(_s.get("desc", ""))
                    _mat = _s["matrix"]
                    st.dataframe(pd.DataFrame(_mat).style.format("{:.2f}"),
                                 use_container_width=True)
                    if _s.get("assignment"):
                        _asg = ", ".join(
                            f"{_row_lbl[r] if r < _nr else f'Dummy{r}'}→{_col_lbl[c] if c < _nc else f'Dummy{c}'}"
                            for r, c in sorted(_s["assignment"])
                            if r < _nr  # ignore padded rows
                        )
                        st.info(f"✅ Asignación: {_asg}")
                    st.markdown("---")

    # ────────────────────────────────────────────────────────────────────────
    #  TIPO: shortest_path
    # ────────────────────────────────────────────────────────────────────────
    elif _tipo == "shortest_path":
        # Soporta múltiples sub-redes (red_a, red_b)
        for _lbl, _red in _datos.items():
            st.markdown(f"#### 🗺️ Red ({_lbl.upper()})")
            _edges = _red["edges"]
            st.dataframe(pd.DataFrame(_edges, columns=["u", "v", "peso"]),
                         hide_index=True, use_container_width=True)
            _c1, _c2 = st.columns(2)
            _c1.metric("Origen", _red["source"])
            _c2.metric("Destino", _red["target"])

            if st.button(f"▶ Resolver {_lbl.upper()} (Dijkstra)",
                         type="primary", use_container_width=True,
                         key=f"hw_sp_{_ej['id']}_{_lbl}"):
                _sp = ShortestPathSolver(_edges, directed=False)
                _r = _sp.dijkstra(_red["source"], _red["target"])

                if _r["path"]:
                    st.success(f"✅ **Ruta más corta: {' → '.join(_r['path'])}**  "
                               f"(distancia total = {_r['path_cost']:g})")
                else:
                    st.error("❌ No se encontró ruta.")

                _dist_rows = [{"Nodo": n, "Distancia": ("∞" if d == float("inf") else d)}
                              for n, d in sorted(_r["distances"].items())]
                st.markdown("**Distancias desde origen:**")
                st.dataframe(pd.DataFrame(_dist_rows), hide_index=True,
                             use_container_width=True)

                with st.expander(f"📋 Iteraciones Dijkstra ({_lbl})", expanded=False):
                    _it_df = pd.DataFrame(_r["iterations"])
                    _show_cols = ["Iteración", "Nodo visitado", "Distancia acumulada",
                                  "Nodos actualizados"]
                    _show_cols = [c for c in _show_cols if c in _it_df.columns]
                    st.dataframe(_it_df[_show_cols] if _show_cols else _it_df,
                                 hide_index=True, use_container_width=True)
            st.markdown("---")

    # ────────────────────────────────────────────────────────────────────────
    #  TIPO: mst
    # ────────────────────────────────────────────────────────────────────────
    elif _tipo == "mst":
        if "edges" in _datos:
            _redes = {"": {"edges": _datos["edges"]}}
        else:
            _redes = {k: v for k, v in _datos.items() if isinstance(v, dict)}

        for _lbl, _red in _redes.items():
            _sufix = f" ({_lbl.upper()})" if _lbl else ""
            st.markdown(f"#### 🌳 Aristas{_sufix}")
            _edges = _red["edges"]
            _ed_df = pd.DataFrame(_edges, columns=["u", "v", "peso"])
            if len(_ed_df) > 30:
                with st.expander(f"Ver {len(_ed_df)} aristas", expanded=False):
                    st.dataframe(_ed_df, hide_index=True, use_container_width=True)
            else:
                st.dataframe(_ed_df, hide_index=True, use_container_width=True)

            if st.button(f"▶ Resolver MST{_sufix} (Kruskal)",
                         type="primary", use_container_width=True,
                         key=f"hw_mst_{_ej['id']}_{_lbl}"):
                _nodes = list(set(str(n) for u, v, _ in _edges for n in (u, v)))
                _ns = NetworkSolver(_nodes, _edges)
                _r = _ns.solve_mst_kruskal()
                st.success(f"✅ **MST costo total = {_r['total_cost']:g}**  "
                           f"({len(_r['mst_edges'])} aristas)")

                _mst_df = pd.DataFrame([{"u": u, "v": v, "peso": w}
                                        for u, v, w in _r["mst_edges"]])
                st.markdown(f"**Aristas del MST{_sufix}:**")
                st.dataframe(_mst_df, hide_index=True, use_container_width=True)

                # ─── Formato C / C' estilo examen (Prim) ───
                _hw_nodes_set = set(str(n) for u, v, _ in _edges for n in (u, v))
                render_mst_cuts_format(_edges, _hw_nodes_set,
                                        start_node=sorted(_hw_nodes_set)[0])

                with st.expander(f"📋 Pasos Kruskal{_sufix}", expanded=False):
                    _ps = [{"Paso": s["Paso"], "Arista": s["Arista"], "Peso": s["Peso"],
                            "¿Ciclo?": s["¿Crea ciclo?"], "Acción": s["Acción"],
                            "Costo acum.": s["Costo acum."]}
                           for s in _r["steps"]]
                    st.dataframe(pd.DataFrame(_ps), hide_index=True,
                                 use_container_width=True)
            st.markdown("---")

    # ────────────────────────────────────────────────────────────────────────
    #  TIPO: max_flow
    # ────────────────────────────────────────────────────────────────────────
    elif _tipo == "max_flow":
        st.markdown("#### 🌊 Aristas dirigidas (capacidad)")
        _edges = _datos["edges"]
        st.dataframe(pd.DataFrame(_edges, columns=["u", "v", "capacidad"]),
                     hide_index=True, use_container_width=True)
        _c1, _c2 = st.columns(2)
        _c1.metric("Fuente", _datos["source"])
        _c2.metric("Sumidero", _datos["target"])

        if st.button(f"▶ Resolver Flujo Máximo", type="primary",
                     use_container_width=True, key=f"hw_mf_{_ej['id']}"):
            _nodes = list(set(str(n) for u, v, _ in _edges for n in (u, v)))
            _ns = NetworkSolver(_nodes, _edges)
            _r = _ns.solve_max_flow(_datos["source"], _datos["target"])

            st.success(f"✅ **Flujo Máximo = {_r['max_flow']:g}**  "
                       f"({_datos['source']} → {_datos['target']}, "
                       f"{len(_r['iterations'])} caminos aumentantes)")

            st.markdown("**Flujo por arista:**")
            _ef = pd.DataFrame(_r["edge_flows"])
            def _style_ef_hw(row):
                if "Sí" in str(row.get("Saturada", "")):
                    return ["background-color:#FFD700; font-weight:bold; color:#5a4000"] * len(row)
                return [""] * len(row)
            st.dataframe(_ef.style.apply(_style_ef_hw, axis=1),
                         hide_index=True, use_container_width=True)
            st.caption("🟡 Dorado = arista saturada.")

            with st.expander("📋 Caminos aumentantes", expanded=False):
                st.dataframe(pd.DataFrame(_r["iterations"]),
                             hide_index=True, use_container_width=True)

            # ─── Capacidades RESIDUALES (segunda gráfica del examen) ───
            st.markdown("### 🔄 Capacidades Residuales (segunda gráfica)")
            st.caption("Para cada arco `u → v`: el número **forward** es lo que aún puedes mandar; "
                       "**backward** es el flujo enviado, que podrías cancelar.")

            # Tabla
            _res_df = pd.DataFrame(_r["residual_summary"])
            def _style_res_hw(row):
                if row.get("Cap. residual (→)", 1) <= 1e-6:
                    return ["background-color:#fff3cd; font-weight:bold; color:#856404"] * len(row)
                return [""] * len(row)
            st.dataframe(_res_df.style.apply(_style_res_hw, axis=1),
                         hide_index=True, use_container_width=True)
            st.caption("🟡 Filas amarillas = arcos saturados (residual hacia adelante = 0).")

            # Gráfica estilo examen (layout en capas + etiquetas duales)
            st.markdown("**📊 Gráfica residual estilo examen:**")
            st.plotly_chart(
                draw_max_flow_residual_graph(
                    _edges, _r["residual_summary"],
                    _datos["source"], _datos["target"],
                    title=f"Red residual — flujo máximo = {_r['max_flow']:g}"
                ),
                use_container_width=True, key=f"hw_mf_residual_{_ej['id']}"
            )

    # ────────────────────────────────────────────────────────────────────────
    #  TIPO: min_cost_flow
    # ────────────────────────────────────────────────────────────────────────
    elif _tipo == "min_cost_flow":
        st.markdown("#### 💸 Aristas (capacidad y costo/unidad)")
        _cost_edges = _datos["edges_with_cost"]
        st.dataframe(pd.DataFrame(_cost_edges,
                                  columns=["u", "v", "capacidad", "costo/unidad"]),
                     hide_index=True, use_container_width=True)
        _c1, _c2, _c3 = st.columns(3)
        _c1.metric("Fuente", _datos["source"])
        _c2.metric("Sumidero", _datos["target"])
        _c3.metric("Flujo requerido", _datos["required_flow"])

        if st.button(f"▶ Resolver Flujo de Costo Mínimo", type="primary",
                     use_container_width=True, key=f"hw_mcf_{_ej['id']}"):
            _es = [(u, v, cap) for u, v, cap, _ in _cost_edges]
            _nodes = list(set(str(n) for u, v, _ in _es for n in (u, v)))
            _ns = NetworkSolver(_nodes, _es)
            _r = _ns.solve_min_cost_flow(
                _datos["source"], _datos["target"], _datos["required_flow"],
                cost_edges=_cost_edges
            )
            if _r["feasible"]:
                st.success(f"✅ **Costo Mínimo = ${_r['total_cost']:,.2f}**  "
                           f"(flujo enviado: {_r['total_flow']:g} / {_datos['required_flow']:g})")
            else:
                st.warning(f"⚠️ Sólo se pudo enviar {_r['total_flow']:g} de "
                           f"{_datos['required_flow']:g}.")

            _m1, _m2, _m3 = st.columns(3)
            _m1.metric("Flujo enviado", f"{_r['total_flow']:g}")
            _m2.metric("Costo total", f"${_r['total_cost']:,.2f}")
            if _r['total_flow'] > 0:
                _m3.metric("Costo prom./unidad", f"${_r['total_cost']/_r['total_flow']:.2f}")

            st.markdown("**Flujo por arista:**")
            _ef = pd.DataFrame(_r["edge_flows"])
            def _style_mcf_hw(row):
                if row.get("Flujo", 0) > 1e-6:
                    return ["background-color:#e8f5e9; color:#1b5e20; font-weight:bold"] * len(row)
                return [""] * len(row)
            st.dataframe(_ef.style.apply(_style_mcf_hw, axis=1),
                         hide_index=True, use_container_width=True)

            with st.expander("📋 Iteraciones (Successive Shortest Paths)", expanded=False):
                st.dataframe(pd.DataFrame(_r["iterations"]),
                             hide_index=True, use_container_width=True)

    # ────────────────────────────────────────────────────────────────────────
    #  TIPO: project_selection (Programación entera 0-1)
    # ────────────────────────────────────────────────────────────────────────
    elif _tipo == "project_selection":
        _proj_lbl = _datos["project_labels"]
        _year_lbl = _datos["year_labels"]
        _vpn = _datos["vpn"]
        _reqs = _datos["requirements"]
        _budgets = _datos["budgets"]
        _fixed = _datos["fixed_costs"]
        _given = _datos["given_solution"]
        _n = len(_proj_lbl)

        st.markdown("#### 📋 Datos del problema")
        _tbl = pd.DataFrame(_reqs, columns=_year_lbl, index=_proj_lbl)
        _tbl.insert(0, "VPN", _vpn)
        _tbl["Costo fijo F"] = _fixed
        st.dataframe(_tbl.style.format("{:.0f}"), use_container_width=True)

        st.markdown("**Presupuesto disponible por año:**")
        st.dataframe(pd.DataFrame([_budgets], columns=_year_lbl, index=["Presupuesto"]),
                     use_container_width=True)

        # Inciso (d): Z* con la solución dada
        st.markdown("---")
        st.markdown("### Inciso (d): Z\\* para la solución dada")
        _z_d = sum((_vpn[i] - _fixed[i]) * _given[i] for i in range(_n))
        _terms = []
        for i in range(_n):
            if _given[i] == 1:
                _terms.append(f"({_vpn[i]}−{_fixed[i]})·1 = {_vpn[i]-_fixed[i]}")
        _formula = "  +  ".join(_terms) if _terms else "0"
        st.success(f"✅ **Z\\* = {_formula} = ${_z_d} (mil pesos)**")
        st.caption(f"Solución dada: " +
                   ", ".join(f"{_proj_lbl[i]}*={_given[i]}" for i in range(_n)))

        # Verificar presupuestos
        _viola = []
        for y in range(len(_budgets)):
            _used = sum(_reqs[i][y] * _given[i] for i in range(_n))
            _viola.append({"Año": _year_lbl[y], "Capital usado": _used,
                            "Presupuesto": _budgets[y],
                            "OK": "✅" if _used <= _budgets[y] else "❌"})
        st.markdown("**Verificación de presupuestos:**")
        st.dataframe(pd.DataFrame(_viola), hide_index=True, use_container_width=True)

        # Resolver IP completa con PuLP
        st.markdown("---")
        st.markdown("### Solución óptima de la IP (con PuLP)")
        if st.button("▶ Resolver IP completa (con costos fijos)",
                     type="primary", use_container_width=True,
                     key=f"hw_ip_{_ej['id']}"):
            try:
                import pulp
                _model = pulp.LpProblem("Seleccion_Proyectos", pulp.LpMaximize)
                _x = [pulp.LpVariable(f"x_{_proj_lbl[i]}", cat="Binary") for i in range(_n)]
                # Función objetivo con costos fijos
                _model += pulp.lpSum((_vpn[i] - _fixed[i]) * _x[i] for i in range(_n)), "Z"
                # Restricciones de presupuesto por año
                for y in range(len(_budgets)):
                    _model += (pulp.lpSum(_reqs[i][y] * _x[i] for i in range(_n))
                                <= _budgets[y]), f"Budget_{_year_lbl[y]}"
                # Contingencia: P1 ≤ P2
                _model += _x[0] <= _x[1], "Contingencia_P1_P2"
                _model.solve(pulp.PULP_CBC_CMD(msg=False))

                if pulp.LpStatus[_model.status] == "Optimal":
                    _sol = [int(round(_x[i].value())) for i in range(_n)]
                    _z_opt = int(round(_model.objective.value()))
                    st.success(f"✅ **Solución óptima IP: Z\\* = ${_z_opt} (mil pesos)**")
                    _sol_df = pd.DataFrame([{
                        "Proyecto": _proj_lbl[i],
                        "Seleccionado": "✓" if _sol[i] == 1 else "—",
                        "VPN": _vpn[i],
                        "Costo fijo": _fixed[i],
                        "Aporte neto": (_vpn[i] - _fixed[i]) * _sol[i],
                    } for i in range(_n)])
                    st.dataframe(_sol_df, hide_index=True, use_container_width=True)
                else:
                    st.error(f"Status: {pulp.LpStatus[_model.status]}")
            except Exception as _err:
                st.error(f"Error: {_err}")

    else:
        st.error(f"Tipo de ejercicio no soportado: {_tipo}")

    
