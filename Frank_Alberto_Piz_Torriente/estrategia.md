# Estrategia del Agente Hex

Este agente usa **MCTS (Monte Carlo Tree Search)** con mejoras heurísticas avanzadas para jugar rápido y de forma táctico-estratégica en tableros de Hex.

## Resumen de la estrategia

1. **MCTS con Asignación de Tiempo Dinámico**
   - Ejecuta iteraciones de selección, expansión, rollout y retropropagación.
   - El límite de tiempo por cada jugada no es rígido, asigna un menor tiempo general de cálculo en aperturas y finales (donde hay poca ramificación o ya es resuelto), y alcanza su clímax de presupuesto durante el medio-juego del tablero donde la disputa requerirá ramificarse más.

2. **Libro de Aperturas y Atajos Tácticos (Mate en 1 y Mate en 2)**
   - Durante las primeras 2 jugadas del tablero extrae posiciones del centro y puentes inmediatos de un libro cacheado para no perder tiempo en el árbol de búsqueda en un tablero vacío.
   - En el juego se buscan jugadas ganadoras inmediatas, bloqueos de rivales al instante y, opcionalmente al reducir opciones, _amenazas dobles o tenedores_ ("foks") que generen dos o más amenazas imparables al oponente.

3. **RAVE (AMAF) Simétrico en Selección**
   - La selección de hijos mezcla el valor UCT clásico con estadísticas RAVE, habiendo elevado el parámetro de RAVE para afianzar la exploración inicial.
   - Se aprovecha la simetría de rotación de 180º del Hex para registrar a la vez retropropagaciones RAVE equivalentes, lo que multiplica el conocimiento y reduce iteraciones innecesarias ("shadow learning").

4. **Rollout Probabilístico Guiado**
   En lugar de la caída rígida en cascada, ahora se aplican selecciones aleatorias usando pesos ponderados basados en las siguientes evaluaciones:
   - **Victorias / Bloqueos directos:** Continúa teniendo la máxima jerarquía.
   - **Amenazas o Conexiones Múltiples:** Cuenta y evalúa la capacidad de una celda de solucionar múltiples "puentes" rotos a la vez o formar nuevas conexiones virtuales en diamante ("virtual connections"). Aquellas que formen más sumarán más peso.
   - **LGR (Last Good Reply):** Si un movimiento reciente fue una respuesta exitosa ante una casilla tirada por el oponente en el recorrido de la simulación ganadora anterior, tratará de contestar de nuevo agresivamente con ese mismo contraataque.
   - Para no extender el cómputo, los rollouts detienen su simulación rebasado un estimado del 60% de las casillas en un límite artificial conservando la precisión.

5. **Optimización con Algoritmos de Búsqueda y Poda de Nodos Relevantes**
   - En *Expansión* se eliminan "Cells Muertas", donde se podan posiciones irrelevantes que no colindan con huecos libres en etapas de gran amplitud del ramal ("Captured Spaces").
   - Las reglas de *amenazas inminentes de un puente (must-play)* actúan como filtro excluyente. Si el oponente busca romper un diamante en "mid-game", el motor no explorará en otra zona distante.

6. **Killer Moves & Conocimiento del Dominio**
   - Al buscar a los hijos con mejor score en memoria del árbol, se le aplicará a nuevos nodos un multiplicador decreciente (prior knowledge bias) que beneficia a los puntos centrales del tablero en las etapas tempranas de vida del nodo.
   - También son sesgados incrementalmente aquellos nodos cuyas casillas pertenezcan inherentemente a la lista global en caché reciente de victorias inmediatas (*Killer Moves* generados en simulados previos).

7. **Chequeo de victoria de DSU (Union-Find) veloz**
   - Durante las rutinas no se emplea el BFS en la evaluación profunda. Mantiene una matriz virtual disjunta rápida que une nodos falsos de bordes.
