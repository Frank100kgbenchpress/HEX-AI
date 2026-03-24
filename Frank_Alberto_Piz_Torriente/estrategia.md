# Informe de Estrategia: Agente de Inteligencia Artificial para Hex

Este documento detalla la arquitectura algorítmica y las decisiones de diseño empleadas en el desarrollo del agente para el juego de Hex. El agente implementa un algoritmo de **Monte Carlo Tree Search (MCTS)** profundamente optimizado con heurísticas específicas del dominio, meta-estrategias de simulación y un estricto control de tiempo para maximizar la efectividad en un factor de ramificación masivo.

---

## 1. Arquitectura Base: MCTS Orientado al Rendimiento

El núcleo del agente se basa en MCTS, estructurado en las cuatro fases clásicas (Selección, Expansión, Simulación y Retropropagación). Sin embargo, dada la magnitud del espacio de estados en Hex (particularmente en tableros de 19x19), el algoritmo estándar se ha expandido masivamente:

* **Control de Presupuesto de Tiempo de Alta Precisión:** El algoritmo principal de iteración evalúa constantemente su tiempo de ejecución, cerrando la búsqueda y seleccionando la mejor rama cuando el reloj interno del sistema alcanza los 4.8 segundos (`time_budget_seconds`).
* **Freno de Emergencia Intra-Simulación:** A diferencia de las implementaciones clásicas, el control temporal también se inyecta *dentro* de las capas de la fase de Rollout. Si una simulación se enreda en un tablero masivo, el hilo finaliza prematuramente, evitando un veredicto de "Tiempo Agotado" por parte del sistema central o del juez (previniendo caídas totales del ciclo lógico).

---

## 2. Tecnologías de Aceleración Estructural y Topológica

Para realizar verificaciones de estado y victoria sin sufrir los retrasos sistémicos de estructuras iterativas pesadas (como DFS/BFS), se implementan atajos de cómputo:

* **Disjoint Set Union (DSU / Union-Find):** La validación de conectividad de los nodos a los bordes del tablero no se calcula por búsqueda de grafos recursiva, sino usando un DSU. Cada jugador tiene un bosque de conectividades donde los extremos virtuales (arriba-abajo o izquierda-derecha) actúan como centinelas. Si una jugada unifica las raíces de los bordes, equivale a victoria segura verificable en **O(α(N))** (prácticamente tiempo constante).
* **Amenazas Dobles / Tenedores ("Forks") en Raíz:** Cuando quedan escasas opciones, el agente explora iteraciones de 2 profundidades en atajo para buscar movimientos que revelen dos o más frentes ganadores simultáneos de mate-en-1, haciendo ineludible la victoria matemática y obviando el coste del árbol MCTS.

---

## 3. Funciones Heurísticas Avanzadas (MCTS-Mejorado)

Con el fin de sesgar positivamente la fase de Selección y Expansión, reduciendo exploraciones caóticas y priorizando calidad, el motor implementa las siguientes mejoras estructurales:

### A. RAVE (Rapid Action Value Estimation) y Simetría Hexagonal
Utiliza el principio de *All-Moves-As-First (AMAF)*. Durante un rollout, un buen movimiento tardío se valora como un candidato que habría sido bueno haber jugado desde la raíz. El agente combina **UCT** (Upper Confidence Bound) con los valores RAVE. Adicionalmente, aprovecha las propiedades geométricas del tablero Hex inyectando aprendizajes subyacentes en su cuadrante simétricamente opuesto (rotación topológica 180º).

### B. Memoria Táctica Transitoria: Killer Moves y LGR
* **Last Good Reply (LGR):** Si en un rollout un contraataque logró el porcentaje de victoria más alto después del movimiento X por el oponente, ese combo (Ataque-Respuesta) se guarda en una tabla y se premia de nuevo probabilísticamente ante dicha situación, propiciando bloqueos de respuesta comprobada por el sistema.
* **Killer Moves (Prioridad 2):** Movimientos que han ganado simulaciones recientes son encolados globalmente como prioridades sobre las visitas iniciales de los nodos hijos en el árbol formal de expansión.

### C. Sesgos Iniciales de Dominio (Domain Knowledge - Prioridad 1)
En el nodo recién expandido, los candidatos más cercanos al círculo central reciben un bono estadístico temporal que decae fuertemente con cada visita. Se garantiza el peso gravitacional inicial de la captura del centro sobre exploraciones inútiles en rincones aislados. Además, se emplea un **Libro de Aperturas Cacheado** de centro y puentes básicos en el inicio absoluto para evitar pensar "en blanco".

---

## 4. Rollouts Híbridos y Probabilidades Condicionadas (Dynamic Playouts)

Dado que las iteraciones Monte-Carlo en tableros grandes (como 19x19) resultaban prohibitivas por cálculo, consumiendo hasta 7 segundos por iteración si contenían evaluaciones anidadas predictivas, se introdujo un algoritmo de simulación heurístico variable:

#### Modo Ligero (Early-game masivo - Ej. Tableros $\ge 13x13$):
Cuando el tablero es muy extenso (Turnos tempranos masivos), el agente aborta temporalmente la exhaustividad matemática. Las fichas simulan movimientos dictados puramente por un bono geométrico y penalizando drásticamente la distancia euclidiana (*$10.0 - \sqrt{dist^2}$*). El MCTS simula a máxima velocidad engordando el valor estadístico del nodo raíz.

#### Modo Pesado Táctico (Late-game / Tableros compactos - Ej. $11x11$):
Una vez el volumen del tablero disminiye (o desde el inicio de un tablero pequeño), los rollouts mutan hacia un árbol de selección ponderada (`weighted random choices`) de naturaleza táctico-predictiva:
* **Vector de Peligro Activo (`has_threat`):** El bot reacciona defensivamente priorizando bloqueos de alto calibre (multiplicados astronómicamente ej: `+ 200 * threat`) si un puente de victoria es encendido por el adversario.
* **Agresividad Condicionada:** Si la evaluación de amenaza muestra inactividad, los pesos se concentran asimétricamente en su estrategia de formación propia (`_bridge_forming_count`), construyendo ramales hacia los extremos de manera violenta (`+ 80 de peso relativo`).
* **Poda "Must-Play":** A lo largo del árbol principal (fuera del rollout) los nodos sin trascendencia directa son descartados o mitigados si uno o dos movimientos se determinan como requerimientos obligatorios de supervivencia.

---

## 5. Criterios de Remate Eficiente (Length Penalties)

Cada ruta simulada retropropaga un mitigador final que disminuye la recompensa matemática de partida `(recompensa = 1.0 - penalidad)` escalando progresivamente según el conteo y volumen métrico de la distancia. En resumen, esto instruye orgánicamente al algoritmo a consumar la victoria de la forma más rápida, mortal y directa concebida, en lugar de dilatar simulaciones con movimientos irrelevantes o aleatorios en un tablero ya mecánicamente subyugado.
