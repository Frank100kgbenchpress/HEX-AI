# Estrategia del Agente Hex

Este agente usa **MCTS (Monte Carlo Tree Search)** con mejoras heurísticas avanzadas para jugar rápido y de forma táctico-estratégica en tableros de Hex.

## Resumen de la estrategia

1. **MCTS con Asignación de Tiempo Estricta y Dinámica**
   - Ejecuta iteraciones de selección, expansión, rollout y retropropagación respetando implacablemente el cronómetro (4.8s/5.0s) desde el milisegundo en que inicia su turno preventivo.
   - Alcanza su clímax de presupuesto de tiempo durante el medio-juego del tablero donde la disputa requerirá ramificarse más, mientras que las aperturas se aligeran.

2. **Libro de Aperturas y Atajos Tácticos DSU (Mate en 1 y Mate en 2)**
   - Durante las primeras jugadas del tablero extrae posiciones del centro y puentes inmediatos de un libro cacheado para no perder tiempo en el árbol de búsqueda en un tablero casi vacío.
   - En el juego se buscan jugadas ganadoras inmediatas y bloqueos de rivales al instante operando de modo ultra-rápido empleando *Disjoint Set Union (DSU)* directamente desde la raíz antes de iterar MCTS, evitando que victorias garantizadas consuman tiempo ciego del árbol.
   - Si restan pocas opciones, detecta *amenazas dobles o tenedores* ("forks") calculados a gran velocidad con copias ligeras del estado y validados con DSU, asegurando victorias imparables en turnos dobles.

3. **RAVE (AMAF) Simétrico en Selección**
   - La selección de hijos mezcla el valor UCT clásico con estadísticas RAVE, habiendo elevado el parámetro de RAVE para afianzar la exploración inicial.
   - Se aprovecha la simetría de rotación cruzada (180º) del modelo topológico de Hex para registrar un "shadow learning", reduciendo iteraciones.

4. **Rollout Probabilístico Dinámico y Adaptativo**
   En lugar de la caída rígida en cascada, ahora se aplican selecciones aleatorias guiadas por distribuciones de pesos ("weights") que se adaptan al estado de amenaza de la mesa (`has_threat`):
   - **Evaluación de Amenaza Inminente:** Mide en tiempo real de rollout si el oponente va a ganar conectando un puente. Si el sistema arroja peligro (`has_threat = True`), los pesos se vuelcan masivamente a jugadas defensivas y bloqueos (`+200.0`). Si se asume seguro frente a su oponente, se vuelve puramente agresivo ponderando conectar diamantes con sus celdas vecinas (`+80.0`), sin parar a bloquear sin un fin.
   - **Victorias / Bloqueos directos:** Continúa teniendo la máxima jerarquía.
   - **LGR (Last Good Reply):** Si un movimiento reciente fue una respuesta exitosa ante una casilla tirada por el oponente, tratará de contestar de nuevo agresivamente con ese mismo contraataque.

5. **Optimización con Algoritmos de Búsqueda y Poda de Nodos Relevantes**
   - En *Expansión* se eliminan "Cells Muertas" (posiciones aisladas inofensivas) priorizando la contigüidad.
   - Filtros de respuesta obligatoria: Si hay ataques fuertes al interior de un sub-estado ramificado, los atajos de *Must-play* dirigen a MCTS en el objetivo.

6. **Killer Moves & Conocimiento del Dominio**
   - Al buscar a los hijos con mejor score en memoria del árbol, se le aplica a nuevos nodos un multiplicador decreciente (prior knowledge bias) que beneficia a los puntos centrales del tablero en las etapas tempranas.
   - También son sesgados incrementalmente aquellos nodos cuyas casillas pertenezcan a la caché reciente de victorias inmediatas (*Killer Moves* generados en simulados previos).

7. **Chequeo de Victoria Rápida y Topología Espacial**
   - Las comprobaciones topológicas aplican deltas adyacentes de la geometría diagonal del hexágono matemático `[(-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0)]` permitiendo una integración perfecta con nuestra matriz disjunta veloz (*DSU / Union-Find*). Esto prescindió de las lentas exploraciones por DFS y garantizó O(1) real en revisiones de subcadenas acrónimas.

8. **Penalización por Longitud de Partida (Length Penalty)**
   - Se imparte un decaimiento progresivo a la recompensa final obtenida sobre la trayectoria simulada (`recompensa = 1.0 - penalidad`). Obliga a la IA a no "jugar con su comida"; priorizando siempre las finalizaciones de partida más cortas imaginables en lugar de hacer bloqueos o movimientos inútiles en un sub-tablero que ya ha vencido estratégicamente.
