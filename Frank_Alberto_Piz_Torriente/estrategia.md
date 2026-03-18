# Estrategia del Agente Hex

Este agente usa **MCTS (Monte Carlo Tree Search)** con mejoras para jugar rapido y de forma tactica en tableros grandes.

## Resumen de la estrategia

1. **MCTS con limite de tiempo**
   - Ejecuta iteraciones de seleccion, expansion, rollout y retropropagacion.
   - Usa presupuesto temporal por jugada para respetar el limite de tiempo.

2. **RAVE (AMAF) en seleccion**
   - La seleccion de hijos mezcla el valor UCT clasico con estadisticas RAVE.
   - Al inicio de la busqueda confia mas en RAVE; con mas visitas confia mas en UCT.

3. **Rollout guiado por prioridades tacticas**
   - Prioridad 1: jugar victoria inmediata.
   - Prioridad 2: bloquear victoria inmediata del rival.
   - Prioridad 3: rellenar puentes (bridge) amenazados.
   - Prioridad 4: elegir aleatoriamente en la frontera (vecinos de fichas ya colocadas).

4. **Chequeo de victoria optimizado con DSU (Union-Find)**
   - Durante rollout no usa BFS/DFS en cada paso.
   - Mantiene componentes conectados con nodos virtuales:
     - Jugador 1: `LEFT` y `RIGHT`
     - Jugador 2: `TOP` y `BOTTOM`
   - Hay victoria cuando los nodos virtuales del jugador quedan conectados.

5. **Poda en expansion (virtual connections)**
   - No expande todos los movimientos legales.
   - Solo considera movimientos vacios a distancia 1 o 2 de fichas existentes.
   - Esto reduce el branching factor y concentra la busqueda en la zona relevante.

## Objetivo practico

Combinar **fuerza tactica inmediata** con **eficiencia computacional** para rendir bien dentro del limite de tiempo por jugada.
