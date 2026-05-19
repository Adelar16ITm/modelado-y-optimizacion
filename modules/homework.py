"""
homework.py — Ejercicios precargados de IIO-13150 Modelado y Optimización I
============================================================================
Tareas 7 a 10 del libro Hillier & Lieberman 11ª edición.

Cada ejercicio incluye:
  - id, título, enunciado (en español)
  - tipo (transportation | assignment | shortest_path | mst | max_flow | min_cost_flow | reading)
  - datos precargados listos para el solver correspondiente
  - notas/explicación para guiar al estudiante
"""

# =============================================================================
#  TAREA 7 — TRANSPORTE
# =============================================================================
TAREA_7 = {
    "titulo": "Tarea 7 — Transporte",
    "ejercicios": [
        {
            "id": "9.1-1",
            "titulo": "Childfair Company",
            "tipo": "transportation",
            "enunciado": (
                "La Childfair Company tiene 3 plantas que producen carriolas para 4 centros de distribución.\n"
                "Las plantas 1, 2 y 3 producen 12, 17 y 11 envíos por mes, respectivamente.\n"
                "Cada CD necesita recibir 10 envíos por mes.\n\n"
                "Costo por envío = $100 + $0.50 × distancia (en millas).\n\n"
                "Distancias (millas):\n"
                "  Planta 1: CD1=800, CD2=1300, CD3=400, CD4=700\n"
                "  Planta 2: CD1=1100, CD2=1400, CD3=600, CD4=1000\n"
                "  Planta 3: CD1=600, CD2=1200, CD3=800, CD4=900\n\n"
                "Inciso (c): obtenga la solución óptima."
            ),
            "datos": {
                "costs": [[500, 750, 300, 450],
                          [650, 800, 400, 600],
                          [400, 700, 500, 550]],
                "supply": [12, 17, 11],
                "demand": [10, 10, 10, 10],
                "row_labels": ["Planta 1", "Planta 2", "Planta 3"],
                "col_labels": ["CD 1", "CD 2", "CD 3", "CD 4"],
            },
            "metodo": "min_cost",
            "nota": (
                "Costo c_ij = $100 + $0.50 · distancia_ij. Problema balanceado (oferta=demanda=40).\n"
                "El programa resuelve con Costo Mínimo + MODI."
            ),
        },
        {
            "id": "9.1-5",
            "titulo": "Onenote Co. (maximización de utilidad)",
            "tipo": "transportation",
            "enunciado": (
                "Onenote Co. produce un producto en 3 plantas para 4 clientes.\n"
                "Plantas producen 60, 80 y 40 unidades. Demanda: cliente 1=40, cliente 2=60.\n"
                "Cliente 3 quiere al menos 20. Clientes 3 y 4 quieren tantas unidades restantes como sea posible.\n\n"
                "Utilidad por unidad ($):\n"
                "  Planta 1: C1=800, C2=700, C3=500, C4=200\n"
                "  Planta 2: C1=500, C2=200, C3=100, C4=300\n"
                "  Planta 3: C1=600, C2=400, C3=300, C4=500\n\n"
                "Formule el problema MAXIMIZANDO utilidad y obtenga la solución óptima."
            ),
            "datos": {
                # Convertimos max(ganancia) → min(costo) usando costo = -ganancia.
                "costs": [[-800, -700, -500, -200],
                          [-500, -200, -100, -300],
                          [-600, -400, -300, -500]],
                "supply": [60, 80, 40],
                "demand": [40, 60, 80, 80],   # cota superior: c3 puede recibir hasta 80, c4 hasta 80
                "row_labels": ["Planta 1", "Planta 2", "Planta 3"],
                "col_labels": ["C1", "C2", "C3 (≥20)", "C4"],
            },
            "metodo": "min_cost",
            "nota": (
                "Conversión: como es maximización, usamos costo c_ij = −utilidad_ij.\n"
                "El problema es desbalanceado: oferta=180, demanda=260 → el programa agrega oferta dummy de 80.\n"
                "La utilidad máxima es −(costo óptimo)."
            ),
        },
        {
            "id": "9.2-2",
            "titulo": "P&T Co. — Verificar optimalidad",
            "tipo": "transportation_verify",
            "enunciado": (
                "Considere el problema de P&T Co. (Sec. 9.1). Verifique que la solución de la Fig. 9.4 "
                "es óptima aplicando SÓLO la prueba de optimalidad del método simplex de transporte.\n\n"
                "Costos (por carga):\n"
                "  Bellingham (75): 464, 513, 654, 867\n"
                "  Eugene (125):    352, 416, 690, 791\n"
                "  Albert Lea (100): 995, 682, 388, 685\n\n"
                "Demanda: Sacramento=80, Salt Lake=65, Rapid=70, Albuquerque=85\n\n"
                "Solución de la Fig. 9.4 a verificar:\n"
                "  x_12=20, x_14=55, x_21=80, x_22=45, x_33=70, x_34=30 (resto=0)"
            ),
            "datos": {
                "costs": [[464, 513, 654, 867],
                          [352, 416, 690, 791],
                          [995, 682, 388, 685]],
                "supply": [75, 125, 100],
                "demand": [80, 65, 70, 85],
                # BFS dada a verificar
                "allocation": [[0, 20, 0, 55],
                               [80, 45, 0, 0],
                               [0, 0, 70, 30]],
                "row_labels": ["Bellingham", "Eugene", "Albert Lea"],
                "col_labels": ["Sacramento", "Salt Lake", "Rapid City", "Albuquerque"],
            },
            "nota": (
                "El programa calcula las variables duales u_i, v_j y los costos reducidos para "
                "esta asignación SIN ejecutar la fase 1. Si todos los costos reducidos no básicos "
                "son ≥ 0, la solución es óptima."
            ),
        },
        {
            "id": "9.2-6",
            "titulo": "Reconsidere 9.1-1 con NW corner + simplex de transporte",
            "tipo": "transportation",
            "enunciado": (
                "Reconsidere el problema de Childfair (9.1-1).\n\n"
                "(a) Obtenga una solución básica inicial usando la regla de la esquina noroeste.\n"
                "(b) Comenzando con esa BFS, aplique el método simplex de transporte (MODI) "
                "hasta obtener la solución óptima."
            ),
            "datos": {
                "costs": [[500, 750, 300, 450],
                          [650, 800, 400, 600],
                          [400, 700, 500, 550]],
                "supply": [12, 17, 11],
                "demand": [10, 10, 10, 10],
                "row_labels": ["Planta 1", "Planta 2", "Planta 3"],
                "col_labels": ["CD 1", "CD 2", "CD 3", "CD 4"],
            },
            "metodo": "northwest",
            "nota": "Igual que 9.1-1, pero el programa usa Esquina Noroeste para la solución inicial.",
        },
        {
            "id": "9.2-13",
            "titulo": "Susan Meyer (gravas) — formulación + sensibilidad",
            "tipo": "transportation_full",
            "enunciado": (
                "Susan Meyer debe transportar gravas a 3 obras. Puede comprar hasta 18 ton en el norte "
                "y 14 ton en el sur. Necesita 10, 5, 10 ton en obras 1, 2, 3.\n\n"
                "Precio por ton: Norte=$300, Sur=$420\n"
                "Costo de transporte por ton (Norte→[obra1,2,3]):  100, 190, 160\n"
                "                              (Sur→[obra1,2,3]):  180, 110, 140\n\n"
                "Costo total = precio + transporte:\n"
                "  Norte: 400, 490, 460\n"
                "  Sur:   600, 530, 560\n\n"
                "(c) Verifique si la BFS {sites 1 y 2 desde Norte completos, site 3 desde Sur completo} es óptima.\n"
                "(d) Resuelva desde NW corner con simplex de transporte.\n"
                "(e) Análisis de sensibilidad sobre c_ij no básicas."
            ),
            "datos": {
                "costs": [[400, 490, 460],
                          [600, 530, 560]],
                "supply": [18, 14],
                "demand": [10, 5, 10],   # total 25, oferta 32 → desbalanceado, dummy demand 7
                # BFS sugerida en inciso (c): N→s1=10, N→s2=5, S→s3=10, dummy: N→dummy=3, S→dummy=4
                # Pero la BFS literal: "sites 1 y 2 desde Norte, site 3 desde Sur"
                "allocation": [[10, 5, 0, 3],     # Norte → s1=10, s2=5, dummy=3
                               [0, 0, 10, 4]],    # Sur → s3=10, dummy=4
                "row_labels": ["Norte", "Sur"],
                "col_labels": ["Obra 1", "Obra 2", "Obra 3"],
            },
            "metodo": "northwest",
            "nota": (
                "Desbalanceado: oferta 32, demanda 25 → dummy columna 7.\n"
                "Inciso (c): el programa verifica la BFS sugerida sin ejecutar fase 1.\n"
                "Inciso (d): solución por NW corner + MODI.\n"
                "Inciso (e): el panel de Sensibilidad muestra rangos para c_ij no básicas."
            ),
        },
        {
            "id": "9.2-14",
            "titulo": "Metro Water District — análisis de sensibilidad",
            "tipo": "transportation_full",
            "enunciado": (
                "Problema de Metro Water District (Sec. 9.1 y 9.2, tablas 9.12 y 9.21).\n\n"
                "Use el reporte de sensibilidad para responder:\n"
                "(a) ¿Sigue óptima la solución si shipping(Calorie→San Go) = $200 en vez de $230?\n"
                "(b) ¿Sigue óptima si shipping(Sacron→Los Devils) = $160 en vez de $130?\n"
                "(c) Si ambos cambios ocurren a $215 y $145 simultáneamente, ¿sigue óptima?\n"
                "(d) Si supply(Sacron) y demand(Hollyglass) bajan 0.5 mAF, ¿siguen válidos los precios sombra?"
            ),
            "datos": {
                # Metro Water District (Hillier 11e Table 9.12):
                # Sources: Colombo, Sacron, Calorie  (M = arc no permitido)
                # Destinations: Berdoo, Los Devils, San Go, Hollyglass
                # Costs (Tabla 9.12, valores típicos del texto):
                #   Colombo:   160, 130, 220, 170
                #   Sacron:    140, 130, 190, 150
                #   Calorie:   190, 200, 230,   M   (no puede a Hollyglass)
                # Para representar M, usamos un costo muy grande (99999).
                "costs": [[160, 130, 220, 170],
                          [140, 130, 190, 150],
                          [190, 200, 230, 99999]],
                "supply": [50, 60, 50],   # Colombo 50, Sacron 60, Calorie 50 (mAF)
                "demand": [30, 70, 30, 30],   # Berdoo, Los Devils, San Go, Hollyglass
                "allocation": None,   # Se calculará óptima
                "row_labels": ["Colombo", "Sacron", "Calorie"],
                "col_labels": ["Berdoo", "Los Devils", "San Go", "Hollyglass"],
            },
            "metodo": "min_cost",
            "nota": (
                "Datos aproximados del texto (Tabla 9.12). El costo M (Calorie→Hollyglass) "
                "se modela como 99999 para impedir esa asignación.\n"
                "Panel de Sensibilidad: para los cambios (a)-(d) compare con los rangos permisibles."
            ),
        },
    ],
}

# =============================================================================
#  TAREA 8 — ASIGNACIÓN
# =============================================================================
TAREA_8 = {
    "titulo": "Tarea 8 — Asignación",
    "ejercicios": [
        {
            "id": "9.3-2",
            "titulo": "4 barcos → 4 puertos (asignación vía transporte)",
            "tipo": "transportation",
            "enunciado": (
                "4 barcos deben enviarse a 4 puertos. Cada barco se asigna a un puerto.\n"
                "Costo (carga, transporte, descarga):\n"
                "  Barco 1: P1=500, P2=400, P3=600, P4=700\n"
                "  Barco 2: P1=600, P2=600, P3=700, P4=500\n"
                "  Barco 3: P1=700, P2=500, P3=700, P4=600\n"
                "  Barco 4: P1=500, P2=400, P3=600, P4=600\n\n"
                "(b) Solución óptima.  (c) Reformule como transporte.  (d) NW corner.  "
                "(e) Simplex de transporte.  (f) ¿Hay óptimos alternativos?"
            ),
            "datos": {
                "costs": [[500, 400, 600, 700],
                          [600, 600, 700, 500],
                          [700, 500, 700, 600],
                          [500, 400, 600, 600]],
                "supply": [1, 1, 1, 1],
                "demand": [1, 1, 1, 1],
                "row_labels": ["Barco 1", "Barco 2", "Barco 3", "Barco 4"],
                "col_labels": ["Puerto 1", "Puerto 2", "Puerto 3", "Puerto 4"],
            },
            "metodo": "northwest",
            "nota": (
                "Asignación como transporte: oferta=demanda=1 en cada fila/columna.\n"
                "Tendrá degeneración (sólo 4 variables básicas en lugar de 4+4−1=7).\n"
                "El programa la maneja automáticamente.\n"
                "Si al final hay costos reducidos = 0 en celdas no básicas, hay óptimos alternativos."
            ),
        },
        {
            "id": "9.3-4",
            "titulo": "Nadadores → estilos (5 nadadores, 4 estilos)",
            "tipo": "transportation",
            "enunciado": (
                "El entrenador debe asignar 4 de 5 nadadores a 4 estilos. Tiempos (seg) en 50 yardas:\n\n"
                "                Carl   Chris  David  Tony   Ken\n"
                "  Espalda       37.7   32.9   33.8   37.0   35.4\n"
                "  Pecho         43.4   33.1   42.2   34.7   41.8\n"
                "  Mariposa      33.3   28.5   38.9   30.4   33.6\n"
                "  Libre         29.2   26.4   29.6   28.5   31.1\n\n"
                "Minimizar la suma de los 4 tiempos."
            ),
            "datos": {
                # 4 estilos (filas) × 5 nadadores (columnas).
                # Desbalanceado: 4 estilos vs 5 nadadores → un nadador queda sin asignar.
                # Se modela agregando un estilo dummy de costo 0.
                "costs": [[37.7, 32.9, 33.8, 37.0, 35.4],
                          [43.4, 33.1, 42.2, 34.7, 41.8],
                          [33.3, 28.5, 38.9, 30.4, 33.6],
                          [29.2, 26.4, 29.6, 28.5, 31.1]],
                "supply": [1, 1, 1, 1],         # cada estilo demanda 1 nadador
                "demand": [1, 1, 1, 1, 1],      # cada nadador puede asignarse a 1 estilo
                "row_labels": ["Espalda", "Pecho", "Mariposa", "Libre"],
                "col_labels": ["Carl", "Chris", "David", "Tony", "Ken"],
            },
            "metodo": "min_cost",
            "nota": (
                "5 nadadores × 4 estilos: desbalanceado. El programa agrega estilo dummy con costo 0.\n"
                "El nadador asignado al dummy es el que NO compite."
            ),
        },
        {
            "id": "9.4-1",
            "titulo": "9.3-2 resuelto con algoritmo Húngaro",
            "tipo": "assignment",
            "enunciado": (
                "Mismo problema que 9.3-2 (barcos → puertos), pero ahora resuelto con el algoritmo "
                "Húngaro paso a paso."
            ),
            "datos": {
                "costs": [[500, 400, 600, 700],
                          [600, 600, 700, 500],
                          [700, 500, 700, 600],
                          [500, 400, 600, 600]],
                "row_labels": ["Barco 1", "Barco 2", "Barco 3", "Barco 4"],
                "col_labels": ["Puerto 1", "Puerto 2", "Puerto 3", "Puerto 4"],
            },
            "metodo": "hungarian",
            "nota": (
                "Húngaro: (1) restar mínimo por fila, (2) restar mínimo por columna, "
                "(3) cubrir ceros con líneas mínimas, (4) iterar hasta n líneas."
            ),
        },
        {
            "id": "9.4-2",
            "titulo": "9.3-4 resuelto con algoritmo Húngaro",
            "tipo": "assignment",
            "enunciado": (
                "Mismo problema que 9.3-4 (nadadores → estilos), pero ahora con el algoritmo Húngaro."
            ),
            "datos": {
                # Hungarian acepta matriz no cuadrada (el solver hace padding interno).
                "costs": [[37.7, 32.9, 33.8, 37.0, 35.4],
                          [43.4, 33.1, 42.2, 34.7, 41.8],
                          [33.3, 28.5, 38.9, 30.4, 33.6],
                          [29.2, 26.4, 29.6, 28.5, 31.1]],
                "row_labels": ["Espalda", "Pecho", "Mariposa", "Libre"],
                "col_labels": ["Carl", "Chris", "David", "Tony", "Ken"],
            },
            "metodo": "hungarian",
            "nota": "Matriz 4×5: el solver Húngaro la rellena a 5×5 con costo 0 (estilo dummy).",
        },
    ],
}

# =============================================================================
#  TAREA 9 — REDES DE FLUJO (1)
# =============================================================================
TAREA_9 = {
    "titulo": "Tarea 9 — Redes de flujo (1)",
    "ejercicios": [
        {
            "id": "10.3-1",
            "titulo": "Lectura — Industria forestal sueca",
            "tipo": "reading",
            "enunciado": (
                "Lea el artículo referenciado sobre el estudio de OR realizado en la industria forestal "
                "sueca (resumen en Sec. 10.3). Describa brevemente cómo se aplicaron modelos de "
                "optimización en redes y enumere los beneficios obtenidos."
            ),
            "nota": (
                "Este ejercicio es de lectura/discusión — no es computacional. No hay un solver que "
                "lo resuelva. El estudiante debe leer el artículo y redactar la respuesta."
            ),
        },
        {
            "id": "10.3-4",
            "titulo": "Ruta más corta — Redes (a) y (b)",
            "tipo": "shortest_path",
            "enunciado": (
                "Encuentre la ruta más corta en las dos redes del Prob. 10.3-4.\n\n"
                "Red (a): nodos O, A, B, C, D, E, T  (Origen=O, Destino=T)\n"
                "Aristas (peso):  O-A=4, O-B=6, O-C=5, A-B=1, A-D=6, B-C=2, B-D=5, "
                "B-E=4, C-E=7, D-E=2, D-T=5, E-T=8\n\n"
                "Red (b): nodos O, A, B, C, D, E, F, G, H, I, T (Origen=O, Destino=T)\n"
                "Aristas: O-A=4, O-B=3, O-C=2, A-D=4, A-B=2, B-D=5, B-E=2, C-E=3, "
                "C-F=6, D-G=2, D-E=1, E-G=3, E-H=4, F-H=5, F-I=2, G-T=7, G-H=2, "
                "H-T=5, H-I=3, I-T=6"
            ),
            "datos": {
                "red_a": {
                    "edges": [("O","A",4),("O","B",6),("O","C",5),("A","B",1),
                              ("A","D",6),("B","C",2),("B","D",5),("B","E",4),
                              ("C","E",7),("D","E",2),("D","T",5),("E","T",8)],
                    "source": "O", "target": "T",
                },
                "red_b": {
                    "edges": [("O","A",4),("O","B",3),("O","C",2),("A","D",4),
                              ("A","B",2),("B","D",5),("B","E",2),("C","E",3),
                              ("C","F",6),("D","G",2),("D","E",1),("E","G",3),
                              ("E","H",4),("F","H",5),("F","I",2),("G","T",7),
                              ("G","H",2),("H","T",5),("H","I",3),("I","T",6)],
                    "source": "O", "target": "T",
                },
            },
            "metodo": "dijkstra",
            "nota": "Redes no dirigidas con pesos positivos → Dijkstra. El programa muestra distancias y ruta óptima.",
        },
        {
            "id": "10.4-1",
            "titulo": "MST sobre las redes de 10.3-4",
            "tipo": "mst",
            "enunciado": (
                "Use Kruskal/Prim para encontrar el árbol de expansión mínima en las mismas redes "
                "del Prob. 10.3-4 (a) y (b)."
            ),
            "datos": {
                "red_a": {
                    "edges": [("O","A",4),("O","B",6),("O","C",5),("A","B",1),
                              ("A","D",6),("B","C",2),("B","D",5),("B","E",4),
                              ("C","E",7),("D","E",2),("D","T",5),("E","T",8)],
                },
                "red_b": {
                    "edges": [("O","A",4),("O","B",3),("O","C",2),("A","D",4),
                              ("A","B",2),("B","D",5),("B","E",2),("C","E",3),
                              ("C","F",6),("D","G",2),("D","E",1),("E","G",3),
                              ("E","H",4),("F","H",5),("F","I",2),("G","T",7),
                              ("G","H",2),("H","T",5),("H","I",3),("I","T",6)],
                },
            },
            "metodo": "kruskal",
            "nota": "Las mismas redes que 10.3-4 pero buscando MST (conexión total al mínimo costo).",
        },
        {
            "id": "10.4-2",
            "titulo": "Wirehouse Lumber — MST entre 8 arboledas",
            "tipo": "mst",
            "enunciado": (
                "Wirehouse Lumber debe construir caminos entre 8 arboledas. Determine qué pares "
                "conectar para minimizar la longitud total de caminos.\n\n"
                "Distancias entre arboledas (millas):\n"
                "(matriz simétrica — sólo se listan aristas únicas)"
            ),
            "datos": {
                # Matriz simétrica → aristas únicas (i<j)
                "edges": [
                    (1,2,1.3),(1,3,2.1),(1,4,0.9),(1,5,0.7),(1,6,1.8),(1,7,2.0),(1,8,1.5),
                    (2,3,0.9),(2,4,1.8),(2,5,1.2),(2,6,2.6),(2,7,2.3),(2,8,1.1),
                    (3,4,2.6),(3,5,1.7),(3,6,2.5),(3,7,1.9),(3,8,1.0),
                    (4,5,0.7),(4,6,1.6),(4,7,1.5),(4,8,0.9),
                    (5,6,0.9),(5,7,1.1),(5,8,0.8),
                    (6,7,0.6),(6,8,1.0),
                    (7,8,0.5),
                ],
            },
            "metodo": "kruskal",
            "nota": "Grafo completo K8 con pesos. Kruskal selecciona las 7 aristas más cortas sin ciclos.",
        },
    ],
}

# =============================================================================
#  TAREA 10 — REDES DE FLUJO (2)
# =============================================================================
TAREA_10 = {
    "titulo": "Tarea 10 — Redes de flujo (2)",
    "ejercicios": [
        {
            "id": "10.5-1",
            "titulo": "Flujo máximo — red estándar del texto",
            "tipo": "max_flow",
            "enunciado": (
                "Use el algoritmo de caminos aumentantes para encontrar el flujo máximo de la fuente "
                "(O) al sumidero (T) en la red mostrada.\n\n"
                "Aristas dirigidas (capacidad):\n"
                "  O→A=5, O→B=7, O→C=4\n"
                "  A→B=1, A→D=3\n"
                "  B→C=2, B→D=4, B→E=5\n"
                "  C→E=4\n"
                "  D→T=9, D→E=1\n"
                "  E→D=0, E→T=6"
            ),
            "datos": {
                "edges": [("O","A",5),("O","B",7),("O","C",4),
                          ("A","B",1),("A","D",3),
                          ("B","C",2),("B","D",4),("B","E",5),
                          ("C","E",4),
                          ("D","T",9),("D","E",1),
                          ("E","T",6)],
                "source": "O", "target": "T",
            },
            "metodo": "edmonds_karp",
            "nota": "Red dirigida estándar. Edmonds-Karp encuentra el flujo máximo iterando con BFS.",
        },
        {
            "id": "10.5-3",
            "titulo": "Sistema de acueductos (3 ríos → ciudad)",
            "tipo": "max_flow",
            "enunciado": (
                "Acueductos desde 3 ríos (R1, R2, R3) hasta la ciudad T, vía nodos intermedios A-F.\n\n"
                "Capacidades (miles de acre-pies/día):\n"
                "  R1→A=75, R1→B=65\n"
                "  R2→A=40, R2→B=50, R2→C=60\n"
                "  R3→B=80, R3→C=70\n"
                "  A→D=60, A→E=45\n"
                "  B→D=70, B→E=55, B→F=45\n"
                "  C→E=70, C→F=90\n"
                "  D→T=120, E→T=190, F→T=130"
            ),
            "datos": {
                "edges": [("R1","A",75),("R1","B",65),
                          ("R2","A",40),("R2","B",50),("R2","C",60),
                          ("R3","B",80),("R3","C",70),
                          ("A","D",60),("A","E",45),
                          ("B","D",70),("B","E",55),("B","F",45),
                          ("C","E",70),("C","F",90),
                          ("D","T",120),("E","T",190),("F","T",130),
                          # Super fuente S → R1, R2, R3 (capacidad = oferta de cada río)
                          ("S","R1",140),("S","R2",150),("S","R3",150)],
                "source": "S", "target": "T",
            },
            "metodo": "edmonds_karp",
            "nota": (
                "Multi-fuente: agregamos super-fuente S con capacidad ilimitada hacia R1, R2, R3.\n"
                "El flujo máximo S→T es el flujo total que llega a la ciudad."
            ),
        },
        {
            "id": "10.5-6",
            "titulo": "Flujo máximo A→F en red 6-nodos",
            "tipo": "max_flow",
            "enunciado": (
                "Red con fuente A, sumidero F.\n\n"
                "Capacidades dirigidas:\n"
                "  A→B=6, A→D=4\n"
                "  B→C=3, B→E=9, B→D=2\n"
                "  C→F=7, C→E=6\n"
                "  D→E=7\n"
                "  E→F=9"
            ),
            "datos": {
                "edges": [("A","B",6),("A","D",4),
                          ("B","C",3),("B","E",9),("B","D",2),
                          ("C","F",7),("C","E",6),
                          ("D","E",7),
                          ("E","F",9)],
                "source": "A", "target": "F",
            },
            "metodo": "edmonds_karp",
            "nota": "Red dirigida 6-nodos. El programa muestra iteraciones y aristas saturadas.",
        },
        {
            "id": "10.6-5",
            "titulo": "Makonsel — flujo de costo mínimo (2 plantas, 2 almacenes, 3 tiendas)",
            "tipo": "min_cost_flow",
            "enunciado": (
                "Makonsel produce en 2 plantas, almacena en 2 bodegas, vende en 3 tiendas (RO1, RO2, RO3).\n\n"
                "Planta → Bodega (costo/carga, capacidad):\n"
                "  P1→W1: $425, cap 125  |  P1→W2: $560, cap 150  (P1 produce 200)\n"
                "  P2→W1: $510, cap 175  |  P2→W2: $600, cap 200  (P2 produce 300)\n\n"
                "Bodega → Tienda (costo/carga, capacidad):\n"
                "  W1→RO1: $470, cap 100  |  W1→RO2: $505, cap 150  |  W1→RO3: $490, cap 100\n"
                "  W2→RO1: $390, cap 125  |  W2→RO2: $410, cap 150  |  W2→RO3: $440, cap 75\n\n"
                "Demanda mensual: RO1=150, RO2=200, RO3=150 (total 500)\n"
                "Producción mensual: P1=200, P2=300 (total 500)"
            ),
            "datos": {
                # Estructura: S → P1, P2 con cap=producción y costo 0
                # P → W con cap y costo dados
                # W → RO con cap y costo dados
                # RO → T con cap=demanda y costo 0
                "edges_with_cost": [
                    # Super-fuente
                    ("S","P1",200,0),("S","P2",300,0),
                    # Plantas → bodegas
                    ("P1","W1",125,425),("P1","W2",150,560),
                    ("P2","W1",175,510),("P2","W2",200,600),
                    # Bodegas → tiendas
                    ("W1","RO1",100,470),("W1","RO2",150,505),("W1","RO3",100,490),
                    ("W2","RO1",125,390),("W2","RO2",150,410),("W2","RO3", 75,440),
                    # Tiendas → super-sumidero
                    ("RO1","T",150,0),("RO2","T",200,0),("RO3","T",150,0),
                ],
                "source": "S", "target": "T",
                "required_flow": 500,
            },
            "metodo": "successive_shortest_paths",
            "nota": (
                "Modelo con super-fuente S y super-sumidero T. Bodegas son nodos de transbordo.\n"
                "Se requiere flujo = 500 (= producción total = demanda total)."
            ),
        },
    ],
}

# =============================================================================
#  EXAMEN — Tercer Parcial, Mayo 2010
# =============================================================================
EXAMEN_2010 = {
    "titulo": "Examen Mayo 2010 — Tercer Parcial",
    "ejercicios": [
        # ─────────────────────────────────────────────────────────────────────
        {
            "id": "1abc",
            "titulo": "Problema 1 (P&G) — Transporte: costo mínimo + reducidos eij",
            "tipo": "transportation_full",
            "enunciado": (
                "Fer (P&G) determina la política óptima de transporte desde 2 plantas a 3 bodegas.\n"
                "  · P1 oferta=40, P2 oferta=20  (total 60)\n"
                "  · B1 demanda=25, B2 demanda=15, B3 demanda=10  (total 50)\n\n"
                "Costos unitarios:\n"
                "  P1→B1=14, P1→B2=7, P1→B3=9\n"
                "  P2→B1=8,  P2→B2=10, P2→B3=5\n\n"
                "(a) Tabla de transporte balanceada.\n"
                "(b) Política factible usando COSTO MÍNIMO.\n"
                "(c) eij (efecto neto/costos reducidos) para celdas cerradas + celda entrante + θ.\n"
                "(d) Función objetivo (escribe algebraicamente).\n"
                "(e) Restricción de demanda de B2 (escribe algebraicamente)."
            ),
            "datos": {
                "costs": [[14, 7, 9],
                          [8, 10, 5]],
                "supply": [40, 20],
                "demand": [25, 15, 10],
                "row_labels": ["P1", "P2"],
                "col_labels": ["B1", "B2", "B3"],
            },
            "metodo": "min_cost",
            "nota": (
                "Desbalanceado: oferta(60) > demanda(50). El programa agrega columna dummy (j=4) con demanda 10 y costo 0.\n"
                "Tie-breaking del solver: 'fila más arriba, columna más a la izquierda' — coincide con la regla del examen.\n\n"
                "📝 Respuestas algebraicas (para los incisos d, e):\n"
                "  (d) min Z = 14·P1B1 + 7·P1B2 + 9·P1B3 + 8·P2B1 + 10·P2B2 + 5·P2B3\n"
                "  (e) P1B2 + P2B2 = 15   (demanda B2)"
            ),
        },
        # ─────────────────────────────────────────────────────────────────────
        {
            "id": "2",
            "titulo": "Problema 2 (Rex) — Asignación 2 productos × 3 máquinas",
            "tipo": "assignment",
            "enunciado": (
                "Rex asigna 2 productos a 3 máquinas. Un producto → una máquina, una máquina → un producto.\n\n"
                "Costos unitarios:\n"
                "          M1    M2    M3\n"
                "  P1:      2     4     2\n"
                "  P2:      5     4     3\n\n"
                "(a) Restricción algebraica: P1 asignado a alguna máquina.\n"
                "(b) Restricción algebraica: no exceder capacidad de M1.\n"
                "(c) Z* costo total óptimo."
            ),
            "datos": {
                "costs": [[2, 4, 2], [5, 4, 3]],
                "row_labels": ["P1", "P2"],
                "col_labels": ["M1", "M2", "M3"],
            },
            "metodo": "hungarian",
            "nota": (
                "📝 Respuestas algebraicas:\n"
                "  (a) x_P1,M1 + x_P1,M2 + x_P1,M3 = 1   (P1 asignado a exactamente una máquina)\n"
                "  (b) x_P1,M1 + x_P2,M1 ≤ 1            (capacidad M1 a lo más 1 producto)\n"
                "  (c) Solución óptima: P1→M1 (costo 2) y P2→M3 (costo 3) → Z* = 5\n"
                "      (M2 queda sin asignar)\n"
                "El solver Húngaro la encuentra directamente."
            ),
        },
        # ─────────────────────────────────────────────────────────────────────
        {
            "id": "3a",
            "titulo": "Problema 3a — Capacidad de la ruta A-B-E-G",
            "tipo": "reading",
            "enunciado": (
                "De la red de fibra óptica, determinar el número MÁXIMO de llamadas/hora que pueden\n"
                "circular ÚNICAMENTE por la ruta A → B → E → G.\n\n"
                "Capacidades de los arcos de esa ruta:\n"
                "  · A→B = 6\n"
                "  · B→E = 3\n"
                "  · E→G = 5"
            ),
            "nota": (
                "📝 Respuesta:\n"
                "La capacidad de una ruta = cuello de botella = mínimo de las capacidades de sus arcos.\n"
                "  min(6, 3, 5) = **3 mil llamadas/hora**"
            ),
        },
        # ─────────────────────────────────────────────────────────────────────
        {
            "id": "3b",
            "titulo": "Problema 3b — Flujo máximo total A → G",
            "tipo": "max_flow",
            "enunciado": (
                "Red de fibra óptica completa. Calcular el flujo máximo total de A a G.\n\n"
                "Aristas dirigidas con capacidades (mil llamadas/hora):\n"
                "  A→B=6, A→D=6\n"
                "  B→C=2, B→E=3\n"
                "  C→D=3, C→E=2, C→F=2\n"
                "  D→C=3, D→F=1, D→G=2\n"
                "  E→F=2, E→G=5\n"
                "  F→G=5"
            ),
            "datos": {
                "edges": [("A","B",6),("A","D",6),
                          ("B","C",2),("B","E",3),
                          ("C","D",3),("C","E",2),("C","F",2),
                          ("D","C",3),("D","F",1),("D","G",2),
                          ("E","F",2),("E","G",5),
                          ("F","G",5)],
                "source": "A", "target": "G",
            },
            "metodo": "edmonds_karp",
            "nota": (
                "Capacidades extraídas del diagrama del examen.\n"
                "El algoritmo de trayectoria aumentante (Edmonds-Karp) encuentra el flujo máximo."
            ),
        },
        # ─────────────────────────────────────────────────────────────────────
        {
            "id": "4a",
            "titulo": "Problema 4a — Ruta más corta A → F",
            "tipo": "shortest_path",
            "enunciado": (
                "Alonso busca la ruta más corta de A a F en la red de carreteras.\n\n"
                "Distancias entre ciudades (km):\n"
                "  A-B=210, A-C=210\n"
                "  B-D=192, B-E=315\n"
                "  C-D=210, C-E=180\n"
                "  D-F=192, E-F=180"
            ),
            "datos": {
                "red": {
                    "edges": [("A","B",210),("A","C",210),
                              ("B","D",192),("B","E",315),
                              ("C","D",210),("C","E",180),
                              ("D","F",192),("E","F",180)],
                    "source": "A", "target": "F",
                },
            },
            "metodo": "dijkstra",
            "nota": "📝 Respuesta esperada: A → C → E → F  con distancia = 210+180+180 = **570 km**",
        },
        # ─────────────────────────────────────────────────────────────────────
        {
            "id": "4b",
            "titulo": "Problema 4b — Ruta A → F con C-E cerrada (guerrilla)",
            "tipo": "shortest_path",
            "enunciado": (
                "El camino C-E está cerrado. Encontrar la nueva ruta más corta A → F.\n\n"
                "Aristas restantes:\n"
                "  A-B=210, A-C=210, B-D=192, B-E=315, C-D=210, D-F=192, E-F=180"
            ),
            "datos": {
                "red": {
                    "edges": [("A","B",210),("A","C",210),
                              ("B","D",192),("B","E",315),
                              ("C","D",210),
                              ("D","F",192),("E","F",180)],
                    "source": "A", "target": "F",
                },
            },
            "metodo": "dijkstra",
            "nota": "📝 Respuesta esperada: A → B → D → F  con distancia = 210+192+192 = **594 km**",
        },
        # ─────────────────────────────────────────────────────────────────────
        {
            "id": "4c",
            "titulo": "Problema 4c — Ruta más corta A → D",
            "tipo": "shortest_path",
            "enunciado": (
                "La cita cambia a la ciudad D. Encontrar la ruta más corta A → D."
            ),
            "datos": {
                "red": {
                    "edges": [("A","B",210),("A","C",210),
                              ("B","D",192),("B","E",315),
                              ("C","D",210),("C","E",180),
                              ("D","F",192),("E","F",180)],
                    "source": "A", "target": "D",
                },
            },
            "metodo": "dijkstra",
            "nota": "📝 Respuesta esperada: A → B → D  con distancia = 210+192 = **402 km**",
        },
        # ─────────────────────────────────────────────────────────────────────
        {
            "id": "4d",
            "titulo": "Problema 4d — MST: tender líneas telefónicas",
            "tipo": "mst",
            "enunciado": (
                "Alonso obtiene el contrato. Las líneas siguen las carreteras existentes.\n"
                "Determinar el árbol de expansión mínima (MST) que conecta TODAS las ciudades."
            ),
            "datos": {
                "edges": [("A","B",210),("A","C",210),
                          ("B","D",192),("B","E",315),
                          ("C","D",210),("C","E",180),
                          ("D","F",192),("E","F",180)],
            },
            "metodo": "kruskal",
            "nota": (
                "📝 Respuesta esperada (Kruskal):\n"
                "  Aristas: C-E (180), E-F (180), B-D (192), D-F (192), A-B (210)\n"
                "  Longitud total = 180+180+192+192+210 = **954 km**\n"
                "El formato C / C' del examen pide cortes — el programa muestra directamente las 5 aristas del MST."
            ),
        },
        # ─────────────────────────────────────────────────────────────────────
        {
            "id": "5",
            "titulo": "Problema 5 (Pepe) — Selección de proyectos (IP)",
            "tipo": "project_selection",
            "enunciado": (
                "Pepe decide entre 4 proyectos (P1, P2, P3, P4). Cifras en miles de pesos.\n\n"
                "  Proyecto │ VPN │ Año1 │ Año2 │ Año3 │ Año4\n"
                "  ─────────┼─────┼──────┼──────┼──────┼─────\n"
                "    P1     │ 50  │  10  │  15  │  20  │  10\n"
                "    P2     │ 70  │  15  │  20  │  10  │  10\n"
                "    P3     │ 30  │  20  │  10  │  10  │  15\n"
                "    P4     │ 40  │  10  │  10  │  15  │  20\n"
                "  ─────────┼─────┼──────┼──────┼──────┼─────\n"
                "  Presupuesto │   50 │  45 │  50 │  45\n\n"
                "Restricciones extra:\n"
                "  · P2 contingente respecto a P1: si P1=1 entonces P2=1  →  P1 ≤ P2\n"
                "  · Costos fijos al ejecutar: F1=30, F2=40, F3=50, F4=70\n\n"
                "(a) Función objetivo  (d) Z* para P1=1, P2=1, P3=0, P4=0"
            ),
            "datos": {
                "vpn":          [50, 70, 30, 40],
                "requirements": [[10, 15, 20, 10],
                                 [15, 20, 10, 10],
                                 [20, 10, 10, 15],
                                 [10, 10, 15, 20]],
                "budgets":      [50, 45, 50, 45],
                "fixed_costs":  [30, 40, 50, 70],
                "given_solution": [1, 1, 0, 0],
                "project_labels": ["P1", "P2", "P3", "P4"],
                "year_labels": ["Año 1", "Año 2", "Año 3", "Año 4"],
            },
            "nota": (
                "📝 Respuestas algebraicas:\n"
                "  (a) max Z = 50·P1 + 70·P2 + 30·P3 + 40·P4   (sin costos fijos)\n"
                "  (b) 20·P1 + 10·P2 + 10·P3 + 15·P4 ≤ 50      (presupuesto año 3)\n"
                "  (c) P1 ≤ P2                                  (contingencia)\n"
                "  (d) Con costos fijos:\n"
                "      Z* = (50−30)·1 + (70−40)·1 − 20·0 − 30·0 = 20 + 30 = **50 mil pesos**\n"
                "El programa también resuelve la IP completa con PuLP para verificar."
            ),
        },
    ],
}


# =============================================================================
#  Diccionario maestro
# =============================================================================
TAREAS = {
    "Tarea 7 — Transporte": TAREA_7,
    "Tarea 8 — Asignación": TAREA_8,
    "Tarea 9 — Redes de flujo (1)": TAREA_9,
    "Tarea 10 — Redes de flujo (2)": TAREA_10,
    "📝 Examen Mayo 2010": EXAMEN_2010,
}


def get_ejercicio(tarea_key: str, ejercicio_id: str):
    """Devuelve el dict del ejercicio dado tarea + id."""
    t = TAREAS.get(tarea_key)
    if not t:
        return None
    for e in t["ejercicios"]:
        if e["id"] == ejercicio_id:
            return e
    return None


def list_ejercicios(tarea_key: str):
    """Devuelve [(id, titulo), ...] para una tarea."""
    t = TAREAS.get(tarea_key)
    if not t:
        return []
    return [(e["id"], e["titulo"]) for e in t["ejercicios"]]
