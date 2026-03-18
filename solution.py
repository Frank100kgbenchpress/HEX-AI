from player import Player
from board import HexBoard

from dataclasses import dataclass, field
import math
import random
import time
from typing import Dict, List, Optional, Set, Tuple


Move = Tuple[int, int]


class _DSU:
	def __init__(self, size: int):
		self.parent = list(range(size))
		self.rank = [0] * size

	def find(self, x: int) -> int:
		while self.parent[x] != x:
			self.parent[x] = self.parent[self.parent[x]]
			x = self.parent[x]
		return x

	def union(self, a: int, b: int) -> None:
		ra = self.find(a)
		rb = self.find(b)
		if ra == rb:
			return
		if self.rank[ra] < self.rank[rb]:
			ra, rb = rb, ra
		self.parent[rb] = ra
		if self.rank[ra] == self.rank[rb]:
			self.rank[ra] += 1

	def connected(self, a: int, b: int) -> bool:
		return self.find(a) == self.find(b)


def _copy_matrix(board: HexBoard) -> List[List[int]]:
	if hasattr(board, "board"):
		return [row[:] for row in board.board]
	return [row[:] for row in board]


def _board_size(board: HexBoard) -> int:
	if hasattr(board, "size"):
		return int(board.size)
	return len(board)


def _legal_moves(matrix: List[List[int]]) -> List[Move]:
	moves: List[Move] = []
	n = len(matrix)
	for r in range(n):
		row = matrix[r]
		for c in range(n):
			if row[c] == 0:
				moves.append((r, c))
	return moves


def _pruned_expansion_moves(matrix: List[List[int]], player_id: int) -> List[Move]:
	enemy_id = 2 if player_id == 1 else 1
	n = len(matrix)
	occupied: List[Move] = []
	legal: List[Move] = []
	for r in range(n):
		for c in range(n):
			if matrix[r][c] == 0:
				legal.append((r, c))
			else:
				occupied.append((r, c))

	if not legal:
		return []
	if not occupied:
		return legal

	# A. "Must-Play" - Si hay un puente amenazado por el oponente, es mandatorio defenderlo.
	must_play = []
	for move in legal:
		if _threatened_bridge_count(matrix, move, player_id, enemy_id) > 0:
			must_play.append(move)
	if must_play:
		return must_play

	# C. Distancia a la Línea de Frente
	candidates: Set[Move] = set()
	for r, c in occupied:
		for n1r, n1c in _neighbors_even_r(r, c, n):
			if matrix[n1r][n1c] == 0:
				candidates.add((n1r, n1c))
			for n2r, n2c in _neighbors_even_r(n1r, n1c, n):
				if matrix[n2r][n2c] == 0:
					candidates.add((n2r, n2c))

	if not candidates:
		return legal

	pruned = []
	for move in legal:
		if move not in candidates:
			continue
		
		# B. Celdas capturadas / sin vecinos vacíos
		r, c = move
		empty_neighbors = 0
		for nr, nc in _neighbors_even_r(r, c, n):
			if matrix[nr][nc] == 0:
				empty_neighbors += 1
		
		if empty_neighbors == 0 and len(legal) > 1:
			continue
			
		pruned.append(move)

	# Mantener orden para consistencia predictiva
	return pruned if pruned else legal


def _frontier_moves(matrix: List[List[int]], legal: List[Move]) -> List[Move]:
	if not legal:
		return []
	n = len(matrix)
	frontier: List[Move] = []
	for r, c in legal:
		for nr, nc in _neighbors_even_r(r, c, n):
			if matrix[nr][nc] != 0:
				frontier.append((r, c))
				break
	return frontier


def _neighbors_even_r(r: int, c: int, n: int):
	if r % 2 == 0:
		deltas = [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 0)]
	else:
		deltas = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, 0), (1, 1)]
	for dr, dc in deltas:
		nr, nc = r + dr, c + dc
		if 0 <= nr < n and 0 <= nc < n:
			yield nr, nc


def _cell_index(r: int, c: int, n: int) -> int:
	return r * n + c


def _build_rollout_union_finds(
	matrix: List[List[int]],
) -> Tuple[_DSU, _DSU, int, int, int, int]:
	n = len(matrix)
	base = n * n
	left = base
	right = base + 1
	top = base
	bottom = base + 1

	uf_p1 = _DSU(base + 2)
	uf_p2 = _DSU(base + 2)

	for r in range(n):
		for c in range(n):
			owner = matrix[r][c]
			if owner == 0:
				continue
			idx = _cell_index(r, c, n)

			if owner == 1:
				if c == 0:
					uf_p1.union(idx, left)
				if c == n - 1:
					uf_p1.union(idx, right)
				for nr, nc in _neighbors_even_r(r, c, n):
					if matrix[nr][nc] == 1:
						uf_p1.union(idx, _cell_index(nr, nc, n))
			else:
				if r == 0:
					uf_p2.union(idx, top)
				if r == n - 1:
					uf_p2.union(idx, bottom)
				for nr, nc in _neighbors_even_r(r, c, n):
					if matrix[nr][nc] == 2:
						uf_p2.union(idx, _cell_index(nr, nc, n))

	return uf_p1, uf_p2, left, right, top, bottom


def _rollout_winner_dsu(
	uf_p1: _DSU,
	uf_p2: _DSU,
	left: int,
	right: int,
	top: int,
	bottom: int,
) -> int:
	if uf_p1.connected(left, right):
		return 1
	if uf_p2.connected(top, bottom):
		return 2
	return 0


def _would_win_with_move_dsu(
	matrix: List[List[int]],
	move: Move,
	player_id: int,
	uf_p1: _DSU,
	uf_p2: _DSU,
	left: int,
	right: int,
	top: int,
	bottom: int,
) -> bool:
	n = len(matrix)
	r, c = move

	if player_id == 1:
		has_left = c == 0
		has_right = c == n - 1
		for nr, nc in _neighbors_even_r(r, c, n):
			if matrix[nr][nc] != 1:
				continue
			n_idx = _cell_index(nr, nc, n)
			if uf_p1.connected(n_idx, left):
				has_left = True
			if uf_p1.connected(n_idx, right):
				has_right = True
			if has_left and has_right:
				return True
		return has_left and has_right

	has_top = r == 0
	has_bottom = r == n - 1
	for nr, nc in _neighbors_even_r(r, c, n):
		if matrix[nr][nc] != 2:
			continue
		n_idx = _cell_index(nr, nc, n)
		if uf_p2.connected(n_idx, top):
			has_top = True
		if uf_p2.connected(n_idx, bottom):
			has_bottom = True
		if has_top and has_bottom:
			return True
	return has_top and has_bottom


def _apply_move_to_rollout_dsu(
	matrix: List[List[int]],
	move: Move,
	player_id: int,
	uf_p1: _DSU,
	uf_p2: _DSU,
	left: int,
	right: int,
	top: int,
	bottom: int,
) -> None:
	n = len(matrix)
	r, c = move
	matrix[r][c] = player_id
	idx = _cell_index(r, c, n)

	if player_id == 1:
		if c == 0:
			uf_p1.union(idx, left)
		if c == n - 1:
			uf_p1.union(idx, right)
		for nr, nc in _neighbors_even_r(r, c, n):
			if matrix[nr][nc] == 1:
				uf_p1.union(idx, _cell_index(nr, nc, n))
		return

	if r == 0:
		uf_p2.union(idx, top)
	if r == n - 1:
		uf_p2.union(idx, bottom)
	for nr, nc in _neighbors_even_r(r, c, n):
		if matrix[nr][nc] == 2:
			uf_p2.union(idx, _cell_index(nr, nc, n))


def _has_won(matrix: List[List[int]], player_id: int) -> bool:
	n = len(matrix)
	if n == 0:
		return False

	stack = []
	visited = [[False] * n for _ in range(n)]

	if player_id == 1:
		for r in range(n):
			if matrix[r][0] == 1:
				stack.append((r, 0))
				visited[r][0] = True
		target_col = n - 1
		while stack:
			r, c = stack.pop()
			if c == target_col:
				return True
			for nr, nc in _neighbors_even_r(r, c, n):
				if not visited[nr][nc] and matrix[nr][nc] == 1:
					visited[nr][nc] = True
					stack.append((nr, nc))
		return False

	for c in range(n):
		if matrix[0][c] == 2:
			stack.append((0, c))
			visited[0][c] = True
	target_row = n - 1
	while stack:
		r, c = stack.pop()
		if r == target_row:
			return True
		for nr, nc in _neighbors_even_r(r, c, n):
			if not visited[nr][nc] and matrix[nr][nc] == 2:
				visited[nr][nc] = True
				stack.append((nr, nc))
	return False


def _winner(matrix: List[List[int]]) -> int:
	if _has_won(matrix, 1):
		return 1
	if _has_won(matrix, 2):
		return 2
	return 0


def _play_move(matrix: List[List[int]], move: Move, player_id: int) -> List[List[int]]:
	r, c = move
	new_matrix = [row[:] for row in matrix]
	new_matrix[r][c] = player_id
	return new_matrix


def _threatened_bridge_count(
	matrix: List[List[int]],
	move: Move,
	player_id: int,
	enemy_id: int,
) -> int:
	r, c = move
	n = len(matrix)
	neighbors_move = list(_neighbors_even_r(r, c, n))
	neighbors_move_set = set(neighbors_move)

	count = 0
	for er, ec in neighbors_move:
		if matrix[er][ec] != enemy_id:
			continue
		common = neighbors_move_set.intersection(set(_neighbors_even_r(er, ec, n)))
		own_endpoints = 0
		for pr, pc in common:
			if matrix[pr][pc] == player_id:
				own_endpoints += 1
		if own_endpoints >= 2:
			count += 1
	return count

def _bridge_forming_count(matrix: List[List[int]], move: Move, player_id: int) -> int:
	r, c = move
	n = len(matrix)
	n1 = list(_neighbors_even_r(r, c, n))
	
	bridges = 0
	for nr, nc in n1:
		if matrix[nr][nc] == 0:
			for nnr, nnc in _neighbors_even_r(nr, nc, n):
				if matrix[nnr][nnc] == player_id and (nnr, nnc) != (r, c):
					shared = 0
					for shr, shc in _neighbors_even_r(nnr, nnc, n):
						if (shr, shc) in n1 and matrix[shr][shc] == 0:
							shared += 1
					if shared >= 2:
						bridges += 1
	return bridges // 2



@dataclass
class _Node:
	matrix: List[List[int]]
	to_move: int
	parent: Optional["_Node"] = None
	move_from_parent: Optional[Move] = None
	visits: int = 0
	value_sum: float = 0.0
	children: List["_Node"] = field(default_factory=list)
	untried_moves: List[Move] = field(default_factory=list)
	rave_visits: Dict[Move, int] = field(default_factory=dict)
	rave_value_sum: Dict[Move, float] = field(default_factory=dict)

	def __post_init__(self) -> None:
		if not self.untried_moves and _winner(self.matrix) == 0:
			self.untried_moves = _pruned_expansion_moves(self.matrix, self.to_move)

class SmartPlayer(Player):
	def __init__(self, player_id: int):
		super().__init__(player_id)
		self.enemy_id = 2 if player_id == 1 else 1
		self.exploration = 1.2
		self.rave_equiv = 600.0  # Cota más alta (priorizar UCT al principio)
		self.max_rollout_moves = 200
		self.time_budget_seconds = 4.8
		self.max_iterations = 5000
		self.lgr_table: Dict[Tuple[Move, int], Move] = {}
		self.killer_moves: List[Move] = []
		self._opening_book_cache: Dict[int, List[Move]] = {}

	def _update_lgr(self, played_moves: List[Tuple[Move, int]], winner: int) -> None:
		for i in range(1, len(played_moves)):
			prev_move, prev_player = played_moves[i-1]
			curr_move, curr_player = played_moves[i]
			if curr_player == winner:
				self.lgr_table[(prev_move, prev_player)] = curr_move

	def _get_opening_book(self, n: int) -> List[Move]:
		if n in self._opening_book_cache:
			return self._opening_book_cache[n]
			
		book: List[Move] = []
		center = n // 2
		# Centro exacto como la mejor
		book.append((center, center))
		
		# Las 4 casillas más fuertes/vecinas alrededor del centro (en estrella / forma de puente directo)
		book.append((center - 1, center))
		book.append((center, center - 1))
		book.append((center + 1, center))
		book.append((center, center + 1))
		
		self._opening_book_cache[n] = book
		return book

	def play(self, board: HexBoard) -> tuple:
		matrix = _copy_matrix(board)
		n = _board_size(board)
		moves = _legal_moves(matrix)

		if not moves:
			return (0, 0)
		if len(moves) == 1:
			return moves[0]

		# Usar el libro de aperturas para turnos muy tempranos
		if len(moves) >= n * n - 2:
			book = self._get_opening_book(n)
			for move in book:
				if move in moves:
					return move

		# Tactical shortcut: play immediate winning move if available.
		for move in moves:
			test = _play_move(matrix, move, self.player_id)
			if _winner(test) == self.player_id:
				return move

		# Tactical defense: block opponent immediate win if possible.
		for move in moves:
			test = _play_move(matrix, move, self.enemy_id)
			if _winner(test) == self.enemy_id:
				return move

		# Double Threat Detection (Fors/Ladders): If playing a move yields >= 2 winning continuations next turn,
		# the opponent won't be able to block both. Return this immediate winning double threat.
		if len(moves) <= 40:  # Optimization: Only run N^2 checks when there are less moves left to keep it fast
			for move in moves:
				test = _play_move(matrix, move, self.player_id)
				winning_continuations = 0
				for next_m in moves:
					if next_m == move:
						continue
					test_next = _play_move(test, next_m, self.player_id)
					if _winner(test_next) == self.player_id:
						winning_continuations += 1
						if winning_continuations >= 2:
							return move

		root = _Node(matrix=matrix, to_move=self.player_id)
		start = time.perf_counter()
		iterations = 0

		while iterations < self.max_iterations:
			if time.perf_counter() - start >= self.time_budget_seconds:
				break

			node = root
			path_nodes: List[_Node] = [root]
			path_moves: List[Tuple[Move, int]] = []

			while node.untried_moves == [] and node.children:
				child = self._select_child(node)
				path_moves.append((child.move_from_parent, node.to_move))
				node = child
				path_nodes.append(node)

			if node.untried_moves:
				move = node.untried_moves.pop(random.randrange(len(node.untried_moves)))
				next_matrix = _play_move(node.matrix, move, node.to_move)
				played_by = node.to_move
				child = _Node(
					matrix=next_matrix,
					to_move=2 if node.to_move == 1 else 1,
					parent=node,
					move_from_parent=move,
				)
				node.children.append(child)
				path_moves.append((move, played_by))
				node = child
				path_nodes.append(node)

			last_m, last_p = path_moves[-1] if path_moves else (None, 0)
			reward, rollout_moves = self._rollout(node.matrix, node.to_move, n, last_m, last_p)
			
			all_moves = path_moves + rollout_moves
			self._backpropagate(path_nodes, all_moves, reward)
			
			if reward == 1.0:
				winner = self.player_id
				self.killer_moves.extend([m for m, p in rollout_moves if p == self.player_id])
			elif reward == -1.0:
				winner = self.enemy_id
				self.killer_moves.extend([m for m, p in rollout_moves if p == self.enemy_id])
			else:
				winner = 0

			# Mantener un tamaño controlado de las Killer Moves más recientes
			if len(self.killer_moves) > 50:
				self.killer_moves = self.killer_moves[-50:]

			if winner != 0:
				self._update_lgr(all_moves, winner)

			iterations += 1

		best_child = max(root.children, key=lambda c: c.visits) if root.children else None
		if best_child is None:
			return moves[random.randrange(len(moves))]
		return best_child.move_from_parent

	def _select_child(self, node: _Node) -> _Node:
		parent_visits_log = math.log(max(1, node.visits))
		n = len(node.matrix)
		center = (n - 1) / 2.0

		def score(child: _Node) -> float:
			if child.visits == 0:
				return float("inf")

			m = child.move_from_parent
			q_uct = child.value_sum / child.visits
			r_visits = node.rave_visits.get(m, 0)
			r_q = (node.rave_value_sum[m] / r_visits) if r_visits > 0 else 0.0
			beta = self.rave_equiv / (self.rave_equiv + child.visits)
			mixed_q = (1.0 - beta) * q_uct + beta * r_q
			exploration_term = self.exploration * math.sqrt(parent_visits_log / child.visits)
			
			# Prioridad 1 (Domain Knowledge): Cercanía al centro
			r, c = m
			dist_sq = (r - center)**2 + (c - center)**2
			max_dist_sq = 2 * (center**2) if center > 0 else 1.0
			prior_bonus = 0.5 * (1.0 - math.sqrt(dist_sq) / (math.sqrt(max_dist_sq) + 1e-3)) / (1 + child.visits)

			# Prioridad 2 (Killer Moves): Movimientos exitosos recientes
			k_count = self.killer_moves.count(m)
			killer_bonus = (0.2 * k_count) / (1 + child.visits) if k_count > 0 else 0.0

			return mixed_q + exploration_term + prior_bonus + killer_bonus

		if node.to_move == self.player_id:
			return max(node.children, key=score)
		return min(node.children, key=score)

	def _rollout(self, matrix: List[List[int]], to_move: int, n: int, in_tree_last_move: Optional[Move] = None, in_tree_last_player: int = 0) -> Tuple[float, List[Tuple[Move, int]]]:
		sim = [row[:] for row in matrix]
		player = to_move
		played_moves: List[Tuple[Move, int]] = []
		uf_p1, uf_p2, left, right, top, bottom = _build_rollout_union_finds(sim)
		
		last_move = in_tree_last_move
		last_player = in_tree_last_player

		# Reducir el límite de movimientos del rollout para ahorrar tiempo 
		# (p.ej: no simular hasta la saciedad si no es necesario)
		rollout_limit = int((n * n) * 0.6)

		for _ in range(min(rollout_limit, self.max_rollout_moves)):
			win = _rollout_winner_dsu(uf_p1, uf_p2, left, right, top, bottom)
			if win != 0:
				if win == self.player_id:
					return 1.0, played_moves
				return -1.0, played_moves

			legal = _legal_moves(sim)
			if not legal:
				return 0.0, played_moves

			frontier = _frontier_moves(sim, legal)
			candidates = frontier if frontier else legal

			# Priority 1: if current player has a winning move now, play it.
			move = None
			for candidate in candidates:
				if _would_win_with_move_dsu(
					sim,
					candidate,
					player,
					uf_p1,
					uf_p2,
					left,
					right,
					top,
					bottom,
				):
					move = candidate
					break
			if move is None and candidates is not legal:
				for candidate in legal:
					if _would_win_with_move_dsu(
						sim,
						candidate,
						player,
						uf_p1,
						uf_p2,
						left,
						right,
						top,
						bottom,
					):
						move = candidate
						break

			# Priority 2: block opponent immediate winning move.
			enemy = 2 if player == 1 else 1
			if move is None:
				for candidate in candidates:
					if _would_win_with_move_dsu(
						sim,
						candidate,
						enemy,
						uf_p1,
						uf_p2,
						left,
						right,
						top,
						bottom,
					):
						move = candidate
						break
			if move is None and candidates is not legal:
				for candidate in legal:
					if _would_win_with_move_dsu(
						sim,
						candidate,
						enemy,
						uf_p1,
						uf_p2,
						left,
						right,
						top,
						bottom,
					):
						move = candidate
						break

			# Probabilistic Policy for tactical patterns (Virtual Connections, Double threats, LGR)
			if move is None:
				lgr_move = None
				if last_move is not None:
					response = self.lgr_table.get((last_move, last_player))
					if response is not None:
						rr, rc = response
						if sim[rr][rc] == 0:
							lgr_move = response
							
				weights = []
				for candidate in candidates:
					w = 1.0  # Base logic: random uniform
					
					# Double threats & Virtual connections (Bridges)
					# Defending bridges (more weight if double threat / ladder situation)
					thcb = _threatened_bridge_count(sim, candidate, player, enemy)
					if thcb > 0:
						w += 50.0 * thcb 
					
					# Forming bridges (establishing VCs)
					bfcb = _bridge_forming_count(sim, candidate, player)
					if bfcb > 0:
						w += 20.0 * bfcb
						
					# Last Good Reply
					if candidate == lgr_move:
						w += 30.0
						
					weights.append(w)
				
				# Weighted random selection
				move = random.choices(candidates, weights=weights, k=1)[0]

			_apply_move_to_rollout_dsu(
				sim,
				move,
				player,
				uf_p1,
				uf_p2,
				left,
				right,
				top,
				bottom,
			)
			played_moves.append((move, player))
			last_move = move
			last_player = player
			player = 2 if player == 1 else 1

		win = _rollout_winner_dsu(uf_p1, uf_p2, left, right, top, bottom)
		if win == self.player_id:
			return 1.0, played_moves
		if win == self.enemy_id:
			return -1.0, played_moves
		return 0.0, played_moves

	def _backpropagate(
		self,
		path_nodes: List[_Node],
		played_moves: List[Tuple[Move, int]],
		reward: float,
	) -> None:
		for idx in range(len(path_nodes) - 1, -1, -1):
			node = path_nodes[idx]
			node.visits += 1
			node.value_sum += reward

			seen: Set[Move] = set()
			for move, played_by in played_moves[idx:]:
				if played_by != node.to_move or move in seen:
					continue
				seen.add(move)
				node.rave_visits[move] = node.rave_visits.get(move, 0) + 1
				node.rave_value_sum[move] = node.rave_value_sum.get(move, 0.0) + reward

