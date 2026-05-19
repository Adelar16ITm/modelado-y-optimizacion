import heapq
import math


class ShortestPathSolver:
    """
    Solves shortest-path problems on a weighted directed/undirected graph.
    Supports Dijkstra (no negative weights) and Bellman-Ford (negative weights OK).
    """

    def __init__(self, edges: list, directed: bool = False):
        """
        edges : list of (u, v, weight)  – strings/ints as node names
        directed : if False, adds reverse edge automatically
        """
        self.directed = directed
        self.nodes = set()
        self.adj = {}  # node -> [(neighbor, weight)]

        for u, v, w in edges:
            w = float(w)
            self.nodes.add(str(u))
            self.nodes.add(str(v))
            u, v = str(u), str(v)
            self.adj.setdefault(u, []).append((v, w))
            if not directed:
                self.adj.setdefault(v, []).append((u, w))

        self.nodes = sorted(self.nodes)
        # ensure every node has an entry
        for n in self.nodes:
            self.adj.setdefault(n, [])

    # ------------------------------------------------------------------ #
    #  Dijkstra                                                            #
    # ------------------------------------------------------------------ #
    def dijkstra(self, source: str, target: str = None):
        """
        Returns dict with:
          distances   – {node: dist}
          predecessors– {node: prev_node}
          iterations  – list of step dicts for table display
          path        – list of nodes source→target (if target given)
          path_cost   – total cost of path
        """
        dist = {n: math.inf for n in self.nodes}
        pred = {n: None for n in self.nodes}
        dist[source] = 0
        visited = set()
        heap = [(0, source)]
        iterations = []
        step = 0

        while heap:
            d, u = heapq.heappop(heap)
            if u in visited:
                continue
            visited.add(u)

            updated = []
            for v, w in self.adj.get(u, []):
                if v not in visited:
                    new_d = dist[u] + w
                    if new_d < dist[v]:
                        dist[v] = new_d
                        pred[v] = u
                        heapq.heappush(heap, (new_d, v))
                        updated.append(v)

            iterations.append({
                "Iteración": step,
                "Nodo visitado": u,
                "Distancia acumulada": dist[u],
                "Nodos actualizados": ", ".join(updated) if updated else "—",
                **{n: ("∞" if dist[n] == math.inf else round(dist[n], 4))
                   for n in self.nodes},
            })
            step += 1

            if target and u == target:
                break

        path, path_cost = self._reconstruct(pred, dist, source, target)
        return {
            "algorithm": "Dijkstra",
            "distances": dist,
            "predecessors": pred,
            "iterations": iterations,
            "path": path,
            "path_cost": path_cost,
            "status": "Optimal" if path else ("No Path" if target else "Completed"),
        }

    # ------------------------------------------------------------------ #
    #  Bellman-Ford                                                        #
    # ------------------------------------------------------------------ #
    def bellman_ford(self, source: str, target: str = None):
        dist = {n: math.inf for n in self.nodes}
        pred = {n: None for n in self.nodes}
        dist[source] = 0
        all_edges = []
        for u, neighbors in self.adj.items():
            for v, w in neighbors:
                all_edges.append((u, v, w))

        iterations = []
        n = len(self.nodes)
        for step in range(n - 1):
            updated = []
            for u, v, w in all_edges:
                if dist[u] != math.inf and dist[u] + w < dist[v]:
                    dist[v] = dist[u] + w
                    pred[v] = u
                    updated.append(v)
            iterations.append({
                "Iteración": step + 1,
                "Aristas relajadas": len(updated),
                "Nodos actualizados": ", ".join(updated) if updated else "—",
                **{n_: ("∞" if dist[n_] == math.inf else round(dist[n_], 4))
                   for n_ in self.nodes},
            })
            if not updated:
                break  # converged early

        # Negative cycle check
        negative_cycle = False
        for u, v, w in all_edges:
            if dist[u] != math.inf and dist[u] + w < dist[v]:
                negative_cycle = True
                break

        path, path_cost = self._reconstruct(pred, dist, source, target)
        status = "Ciclo negativo detectado" if negative_cycle else (
            "Optimal" if path else ("No Path" if target else "Completed")
        )
        return {
            "algorithm": "Bellman-Ford",
            "distances": dist,
            "predecessors": pred,
            "iterations": iterations,
            "path": path,
            "path_cost": path_cost,
            "negative_cycle": negative_cycle,
            "status": status,
        }

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #
    def _reconstruct(self, pred, dist, source, target):
        if target is None or dist.get(target, math.inf) == math.inf:
            return [], None
        path = []
        cur = target
        while cur is not None:
            path.append(cur)
            cur = pred[cur]
        path.reverse()
        if path[0] != source:
            return [], None
        return path, dist[target]
