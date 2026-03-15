from player import Player
from board import HexBoard

from dataclasses import dataclass, field
import math
import random
import time
from typing import List, Optional, Tuple


Move = Tuple[int, int]


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


def _is_threatened_bridge_fill(
	matrix: List[List[int]],
	move: Move,
	player_id: int,
	enemy_id: int,
) -> bool:
	r, c = move
	n = len(matrix)
	neighbors_move = list(_neighbors_even_r(r, c, n))
	neighbors_move_set = set(neighbors_move)

	for er, ec in neighbors_move:
		if matrix[er][ec] != enemy_id:
			continue
		common = neighbors_move_set.intersection(set(_neighbors_even_r(er, ec, n)))
		own_endpoints = 0
		for pr, pc in common:
			if matrix[pr][pc] == player_id:
				own_endpoints += 1
				if own_endpoints >= 2:
					return True
	return False


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

	def __post_init__(self) -> None:
		if not self.untried_moves and _winner(self.matrix) == 0:
			self.untried_moves = _legal_moves(self.matrix)

	def uct(self, exploration: float) -> float:
		if self.visits == 0:
			return float("inf")
		assert self.parent is not None
		exploitation = self.value_sum / self.visits
		exploration_term = exploration * math.sqrt(
			math.log(max(1, self.parent.visits)) / self.visits
		)
		return exploitation + exploration_term


class SmartPlayer(Player):
	def __init__(self, player_id: int):
		super().__init__(player_id)
		self.enemy_id = 2 if player_id == 1 else 1
		self.exploration = 1.2
		self.max_rollout_moves = 200
		self.time_budget_seconds = 1.2
		self.max_iterations = 5000

	def play(self, board: HexBoard) -> tuple:
		matrix = _copy_matrix(board)
		n = _board_size(board)
		moves = _legal_moves(matrix)

		if not moves:
			return (0, 0)
		if len(moves) == 1:
			return moves[0]

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

		root = _Node(matrix=matrix, to_move=self.player_id)
		start = time.perf_counter()
		iterations = 0

		while iterations < self.max_iterations:
			if time.perf_counter() - start >= self.time_budget_seconds:
				break

			node = root

			while node.untried_moves == [] and node.children:
				node = self._select_child(node)

			if node.untried_moves:
				move = node.untried_moves.pop(random.randrange(len(node.untried_moves)))
				next_matrix = _play_move(node.matrix, move, node.to_move)
				child = _Node(
					matrix=next_matrix,
					to_move=2 if node.to_move == 1 else 1,
					parent=node,
					move_from_parent=move,
				)
				node.children.append(child)
				node = child

			reward = self._rollout(node.matrix, node.to_move, n)
			self._backpropagate(node, reward)
			iterations += 1

		best_child = max(root.children, key=lambda c: c.visits) if root.children else None
		if best_child is None:
			return moves[random.randrange(len(moves))]
		return best_child.move_from_parent

	def _select_child(self, node: _Node) -> _Node:
		if node.to_move == self.player_id:
			return max(node.children, key=lambda child: child.uct(self.exploration))
		return min(node.children, key=lambda child: child.uct(self.exploration))

	def _rollout(self, matrix: List[List[int]], to_move: int, n: int) -> float:
		sim = [row[:] for row in matrix]
		player = to_move

		for _ in range(min(n * n, self.max_rollout_moves)):
			win = _winner(sim)
			if win != 0:
				if win == self.player_id:
					return 1.0
				return -1.0

			legal = _legal_moves(sim)
			if not legal:
				return 0.0

			frontier = _frontier_moves(sim, legal)
			candidates = frontier if frontier else legal

			# Priority 1: if current player has a winning move now, play it.
			move = None
			for candidate in candidates:
				test = _play_move(sim, candidate, player)
				if _winner(test) == player:
					move = candidate
					break
			if move is None and candidates is not legal:
				for candidate in legal:
					test = _play_move(sim, candidate, player)
					if _winner(test) == player:
						move = candidate
						break

			# Priority 2: block opponent immediate winning move.
			enemy = 2 if player == 1 else 1
			if move is None:
				for candidate in candidates:
					test = _play_move(sim, candidate, enemy)
					if _winner(test) == enemy:
						move = candidate
						break
			if move is None and candidates is not legal:
				for candidate in legal:
					test = _play_move(sim, candidate, enemy)
					if _winner(test) == enemy:
						move = candidate
						break

			# Priority 3: fill threatened bridge.
			if move is None:
				bridge_moves = [
					candidate
					for candidate in candidates
					if _is_threatened_bridge_fill(sim, candidate, player, enemy)
				]
				if bridge_moves:
					move = bridge_moves[random.randrange(len(bridge_moves))]

			# Priority 4: random move restricted to local frontier.
			if move is None:
				move = candidates[random.randrange(len(candidates))]

			r, c = move
			sim[r][c] = player
			player = 2 if player == 1 else 1

		win = _winner(sim)
		if win == self.player_id:
			return 1.0
		if win == self.enemy_id:
			return -1.0
		return 0.0

	def _backpropagate(self, node: _Node, reward: float) -> None:
		current = node
		while current is not None:
			current.visits += 1
			current.value_sum += reward
			current = current.parent

