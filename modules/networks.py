"""
networks.py  ── Network Models Solver
======================================
Algorithms:
  • MST  – Minimum Spanning Tree via Kruskal (step-by-step) and Prim
  • Max Flow – Ford-Fulkerson / Edmonds-Karp with flow per edge
"""

import numpy as np


class NetworkSolver:
    def __init__(self, nodes, edges):
        """
        nodes : list of node labels (strings or ints)
        edges : list of (u, v, weight)  — undirected for MST, directed for Max Flow
        """
        self.nodes = list(nodes)
        self.edges = [(str(u), str(v), float(w)) for u, v, w in edges]

    # ------------------------------------------------------------------ #
    #  MST – Kruskal (with step-by-step)                                  #
    # ------------------------------------------------------------------ #
    def solve_mst_kruskal(self):
        """
        Kruskal's algorithm: sort edges by weight, add edge if it doesn't
        create a cycle (union-find).  Returns steps for pedagogy.
        """
        nodes = list(set(n for u, v, _ in self.edges for n in (u, v)))

        # Sort edges by weight
        sorted_edges = sorted(self.edges, key=lambda x: x[2])

        # Union-Find
        parent = {n: n for n in nodes}
        rank   = {n: 0  for n in nodes}

        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(x, y):
            px, py = find(x), find(y)
            if px == py:
                return False
            if rank[px] < rank[py]:
                px, py = py, px
            parent[py] = px
            if rank[px] == rank[py]:
                rank[px] += 1
            return True

        mst_edges  = []
        steps      = []
        total_cost = 0.0

        for u, v, w in sorted_edges:
            creates_cycle = (find(u) == find(v))
            accepted      = not creates_cycle and union(u, v)

            if accepted:
                mst_edges.append((u, v, w))
                total_cost += w

            steps.append({
                "Paso":          len(steps) + 1,
                "Arista":        f"{u} — {v}",
                "Peso":          w,
                "¿Crea ciclo?":  "Sí ❌" if creates_cycle else "No ✅",
                "Acción":        "Rechazada" if creates_cycle else "Incluida en MST",
                "Costo acum.":   round(total_cost, 4),
                "mst_so_far":    list(mst_edges),
            })

        return {
            "algorithm":  "Kruskal",
            "mst_edges":  mst_edges,
            "total_cost": total_cost,
            "steps":      steps,
            "status":     "Óptimo",
            "nodes":      nodes,
            "all_edges":  self.edges,
        }

    # ------------------------------------------------------------------ #
    #  MST – Prim (with step-by-step)                                     #
    # ------------------------------------------------------------------ #
    def solve_mst_prim(self, start=None):
        """
        Prim's algorithm: grow tree one node at a time by always picking
        the cheapest edge that connects a new node.
        """
        nodes = list(set(n for u, v, _ in self.edges for n in (u, v)))
        if not nodes:
            return {"status": "Sin nodos", "mst_edges": [], "total_cost": 0, "steps": []}

        # Build adjacency (undirected)
        adj = {n: [] for n in nodes}
        for u, v, w in self.edges:
            adj[u].append((v, w))
            adj[v].append((u, w))

        start = start or nodes[0]
        in_tree   = {start}
        mst_edges = []
        steps     = []
        total     = 0.0

        while len(in_tree) < len(nodes):
            # Find cheapest edge crossing the cut
            candidates = []
            for u in in_tree:
                for v, w in adj[u]:
                    if v not in in_tree:
                        candidates.append((w, u, v))

            if not candidates:
                break   # disconnected graph

            candidates.sort()
            w_min, u_min, v_min = candidates[0]
            in_tree.add(v_min)
            mst_edges.append((u_min, v_min, w_min))
            total += w_min

            steps.append({
                "Paso":         len(steps) + 1,
                "Nodos en árbol": ", ".join(sorted(in_tree)),
                "Arista elegida": f"{u_min} — {v_min}",
                "Peso":          w_min,
                "Costo acum.":   round(total, 4),
                "Candidatas":    [(f"{uu}—{vv}", ww) for ww, uu, vv in candidates],
                "mst_so_far":   list(mst_edges),
            })

        return {
            "algorithm":  "Prim",
            "mst_edges":  mst_edges,
            "total_cost": total,
            "steps":      steps,
            "status":     "Óptimo",
            "nodes":      nodes,
            "all_edges":  self.edges,
            "start":      start,
        }

    # ------------------------------------------------------------------ #
    #  Max Flow – Edmonds-Karp (BFS augmenting paths)                      #
    # ------------------------------------------------------------------ #
    def solve_max_flow(self, source, target):
        """
        Edmonds-Karp: BFS to find augmenting paths until no more exist.
        Returns max flow value and flow on each edge, plus iteration steps.
        """
        source, target = str(source), str(target)
        nodes = list(set(n for u, v, _ in self.edges for n in (u, v)))

        # Capacity matrix as dict of dicts
        cap  = {u: {v: 0.0 for v in nodes} for u in nodes}
        flow = {u: {v: 0.0 for v in nodes} for u in nodes}

        for u, v, w in self.edges:
            cap[u][v] += w   # allow parallel edges

        def bfs_path(src, snk):
            visited = {src}
            queue   = [(src, [src])]
            while queue:
                node, path = queue.pop(0)
                for nb in nodes:
                    if nb not in visited and cap[node][nb] - flow[node][nb] > 1e-9:
                        visited.add(nb)
                        if nb == snk:
                            return path + [nb]
                        queue.append((nb, path + [nb]))
            return None

        total_flow = 0.0
        iterations = []

        while True:
            path = bfs_path(source, target)
            if not path:
                break

            # Bottleneck
            bottleneck = min(
                cap[path[k]][path[k+1]] - flow[path[k]][path[k+1]]
                for k in range(len(path) - 1)
            )

            # Update flows
            for k in range(len(path) - 1):
                u, v = path[k], path[k+1]
                flow[u][v] += bottleneck
                flow[v][u] -= bottleneck

            total_flow += bottleneck
            iterations.append({
                "Iter":           len(iterations) + 1,
                "Camino":         " → ".join(path),
                "Cuello de botella": bottleneck,
                "Flujo total":    round(total_flow, 4),
            })

        # Build per-edge flow summary (only original edges, only if flow > 0)
        edge_flows = []
        for u, v, cap_uv in self.edges:
            f = flow[u][v]
            edge_flows.append({
                "Arista":     f"{u} → {v}",
                "Capacidad":  cap_uv,
                "Flujo":      round(max(f, 0), 4),
                "Holgura":    round(cap_uv - max(f, 0), 4),
                "Saturada":   "🔴 Sí" if abs(cap_uv - max(f, 0)) < 1e-6 else "🟢 No",
            })

        return {
            "max_flow":   total_flow,
            "edge_flows": edge_flows,
            "iterations": iterations,
            "source":     source,
            "target":     target,
            "nodes":      nodes,
            "all_edges":  self.edges,
            "status":     "Óptimo",
        }

    # ------------------------------------------------------------------ #
    #  Minimum Cost Flow – Successive Shortest Paths (Bellman-Ford)        #
    # ------------------------------------------------------------------ #
    def solve_min_cost_flow(self, source, target, required_flow, cost_edges=None):
        """
        Successive Shortest Paths algorithm:
          1. Find cheapest path from source→target in the residual graph
             (Bellman-Ford handles negative residual costs on back-edges).
          2. Push as much flow as possible along that path.
          3. Repeat until `required_flow` units are sent or no path exists.

        Parameters
        ----------
        source, target  : node labels
        required_flow   : units to send  (float)
        cost_edges      : list of (u, v, capacity, cost_per_unit)
                          If None, self.edges (u,v,w) is used with w = capacity = cost.
        """
        source, target = str(source), str(target)

        if cost_edges is not None:
            raw = [(str(u), str(v), float(cap), float(cst))
                   for u, v, cap, cst in cost_edges]
        else:
            raw = [(str(u), str(v), float(w), float(w)) for u, v, w in self.edges]

        nodes = list(set(n for u, v, _, _ in raw for n in (u, v)))
        INF   = float("inf")

        cap_res  = {u: {v: 0.0 for v in nodes} for u in nodes}
        cost_res = {u: {v: 0.0 for v in nodes} for u in nodes}
        for u, v, cap, cst in raw:
            cap_res[u][v]  += cap
            cost_res[u][v]  = cst
            cost_res[v][u]  = -cst

        flow_on    = {u: {v: 0.0 for v in nodes} for u in nodes}
        total_flow = 0.0
        total_cost = 0.0
        remaining  = float(required_flow)
        iterations = []

        def bellman_ford(src, snk):
            dist = {n: INF for n in nodes};  dist[src] = 0.0
            prev = {n: None for n in nodes}
            for _ in range(len(nodes) - 1):
                updated = False
                for u in nodes:
                    for v in nodes:
                        if cap_res[u][v] > 1e-9 and dist[u] + cost_res[u][v] < dist[v] - 1e-9:
                            dist[v] = dist[u] + cost_res[u][v]
                            prev[v] = u
                            updated = True
                if not updated:
                    break
            return dist, prev

        def trace(prev, src, snk):
            if prev[snk] is None and snk != src: return None
            path, cur = [], snk
            while cur != src:
                path.append(cur); cur = prev[cur]
                if cur is None: return None
            path.append(src); path.reverse()
            return path

        it = 1
        while remaining > 1e-9:
            dist, prev = bellman_ford(source, target)
            if dist[target] == INF: break
            path = trace(prev, source, target)
            if path is None: break

            bottleneck = min(cap_res[path[k]][path[k+1]] for k in range(len(path)-1))
            bottleneck = min(bottleneck, remaining)
            path_cost  = dist[target]

            for k in range(len(path) - 1):
                u, v = path[k], path[k+1]
                cap_res[u][v] -= bottleneck;  cap_res[v][u] += bottleneck
                flow_on[u][v] += bottleneck;  flow_on[v][u] -= bottleneck

            total_flow += bottleneck
            total_cost += bottleneck * path_cost
            remaining  -= bottleneck

            iterations.append({
                "Iter":            it,
                "Camino":          " → ".join(path),
                "Costo/unidad":    round(path_cost, 4),
                "Flujo enviado":   round(bottleneck, 4),
                "Flujo acum.":     round(total_flow, 4),
                "Costo acum.":     round(total_cost, 4),
                "Flujo restante":  round(remaining, 4),
            })
            it += 1

        edge_flows = []
        for u, v, cap, cst in raw:
            f = max(flow_on[u][v], 0.0)
            edge_flows.append({
                "Arista":        f"{u} → {v}",
                "Capacidad":     cap,
                "Costo/unidad":  cst,
                "Flujo":         round(f, 4),
                "Costo total":   round(f * cst, 4),
                "Holgura":       round(cap - f, 4),
                "Saturada":      "🔴 Sí" if cap - f < 1e-6 else "🟢 No",
            })

        feasible = remaining < 1e-9
        return {
            "total_flow":    round(total_flow, 4),
            "total_cost":    round(total_cost, 4),
            "required_flow": required_flow,
            "feasible":      feasible,
            "iterations":    iterations,
            "edge_flows":    edge_flows,
            "source":        source,
            "target":        target,
            "nodes":         nodes,
            "all_edges":     raw,
            "status":        "Óptimo" if feasible else "Flujo insuficiente",
        }

    # ------------------------------------------------------------------ #
    #  Convenience wrappers (keep old interface working)                   #
    # ------------------------------------------------------------------ #
    def solve_mst(self):
        return self.solve_mst_kruskal()

    def solve_shortest_path(self, source, target):
        """Kept for backward compatibility."""
        return {"status": "Use el módulo Shortest Path para rutas punto a punto."}
