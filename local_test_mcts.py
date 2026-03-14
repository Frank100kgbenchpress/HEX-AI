"""Script local para probar SmartPlayer (NO incluir en la entrega).

Uso:
    python local_test_mcts.py
"""

from __future__ import annotations

import random
import sys
import time
import types
from dataclasses import dataclass
from typing import List, Optional, Tuple


Move = Tuple[int, int]
MOVE_TIME_LIMIT_SECONDS = 5.0


@dataclass
class Player:
    player_id: int

    def play(self, board: "HexBoard") -> Move:
        raise NotImplementedError


class HexBoard:
    def __init__(self, size: int):
        self.size = size
        self.board = [[0 for _ in range(size)] for _ in range(size)]

    def clone(self) -> "HexBoard":
        clone = HexBoard(self.size)
        clone.board = [row[:] for row in self.board]
        return clone

    def place_piece(self, row: int, col: int, player_id: int) -> bool:
        if not (0 <= row < self.size and 0 <= col < self.size):
            return False
        if self.board[row][col] != 0:
            return False
        self.board[row][col] = player_id
        return True

    def check_connection(self, player_id: int) -> bool:
        n = self.size
        visited = [[False] * n for _ in range(n)]
        stack: List[Move] = []

        if player_id == 1:
            for r in range(n):
                if self.board[r][0] == 1:
                    stack.append((r, 0))
                    visited[r][0] = True
            target_col = n - 1
            while stack:
                r, c = stack.pop()
                if c == target_col:
                    return True
                for nr, nc in _neighbors_even_r(r, c, n):
                    if not visited[nr][nc] and self.board[nr][nc] == 1:
                        visited[nr][nc] = True
                        stack.append((nr, nc))
            return False

        for c in range(n):
            if self.board[0][c] == 2:
                stack.append((0, c))
                visited[0][c] = True
        target_row = n - 1
        while stack:
            r, c = stack.pop()
            if r == target_row:
                return True
            for nr, nc in _neighbors_even_r(r, c, n):
                if not visited[nr][nc] and self.board[nr][nc] == 2:
                    visited[nr][nc] = True
                    stack.append((nr, nc))
        return False


def _neighbors_even_r(r: int, c: int, n: int):
    if r % 2 == 0:
        deltas = [(-1, -1), (-1, 0), (0, -1), (0, 1), (1, -1), (1, 0)]
    else:
        deltas = [(-1, 0), (-1, 1), (0, -1), (0, 1), (1, 0), (1, 1)]
    for dr, dc in deltas:
        nr, nc = r + dr, c + dc
        if 0 <= nr < n and 0 <= nc < n:
            yield nr, nc


def _legal_moves(board: HexBoard) -> List[Move]:
    result: List[Move] = []
    for r in range(board.size):
        for c in range(board.size):
            if board.board[r][c] == 0:
                result.append((r, c))
    return result


class RandomPlayer(Player):
    def play(self, board: HexBoard) -> Move:
        moves = _legal_moves(board)
        return random.choice(moves)


# Inyecta módulos esperados por solution.py (player.py y board.py)
player_module = types.ModuleType("player")
player_module.Player = Player
board_module = types.ModuleType("board")
board_module.HexBoard = HexBoard
sys.modules["player"] = player_module
sys.modules["board"] = board_module

from solution import SmartPlayer  # noqa: E402


def run_game(
    size: int,
    p1: Player,
    p2: Player,
    verbose: bool = False,
) -> Tuple[int, List[float], List[float]]:
    board = HexBoard(size)
    current = p1
    p1_times: List[float] = []
    p2_times: List[float] = []

    for _ in range(size * size):
        start = time.perf_counter()
        move = current.play(board.clone())
        dt = time.perf_counter() - start
        if current is p1:
            p1_times.append(dt)
        else:
            p2_times.append(dt)

        if not isinstance(move, tuple) or len(move) != 2:
            winner = 2 if current.player_id == 1 else 1
            return winner, p1_times, p2_times

        row, col = move
        if not board.place_piece(row, col, current.player_id):
            winner = 2 if current.player_id == 1 else 1
            return winner, p1_times, p2_times

        if board.check_connection(current.player_id):
            return current.player_id, p1_times, p2_times

        current = p2 if current is p1 else p1

    return 0, p1_times, p2_times


def run_match(num_games: int = 20, size: int = 7) -> None:
    wins = {0: 0, 1: 0, 2: 0}
    smart_wins = 0
    smart_move_times: List[float] = []
    violations = 0
    total_start = time.perf_counter()

    for game_index in range(num_games):
        if game_index % 2 == 0:
            p1: Player = SmartPlayer(1)
            p2: Player = RandomPlayer(2)
            smart_id = 1
        else:
            p1 = RandomPlayer(1)
            p2 = SmartPlayer(2)
            smart_id = 2

        winner, p1_times, p2_times = run_game(size=size, p1=p1, p2=p2, verbose=False)
        wins[winner] += 1
        if winner == smart_id:
            smart_wins += 1

        game_smart_times = p1_times if smart_id == 1 else p2_times
        smart_move_times.extend(game_smart_times)
        game_violations = sum(1 for t in game_smart_times if t > MOVE_TIME_LIMIT_SECONDS)
        violations += game_violations

        outcome = "gano" if winner == smart_id else "perdio" if winner != 0 else "empate"
        game_max = max(game_smart_times) if game_smart_times else 0.0
        print(
            f"Partida {game_index + 1:02d}: SmartPlayer ({smart_id}) -> {outcome} | "
            f"max_jugada={game_max:.3f}s | >5s={game_violations}"
        )

    elapsed = time.perf_counter() - total_start
    print("\nResumen:")
    print(f"  Smart wins: {smart_wins}")
    print(f"  Victorias Jugador 1: {wins[1]}")
    print(f"  Victorias Jugador 2: {wins[2]}")
    print(f"  Empates: {wins[0]}")
    if smart_move_times:
        avg_move = sum(smart_move_times) / len(smart_move_times)
        max_move = max(smart_move_times)
        print(f"  Jugadas Smart medidas: {len(smart_move_times)}")
        print(f"  Tiempo promedio por jugada (Smart): {avg_move:.3f}s")
        print(f"  Tiempo maximo por jugada (Smart): {max_move:.3f}s")
        print(f"  Jugadas > {MOVE_TIME_LIMIT_SECONDS:.1f}s: {violations}")
        print(
            "  Cumple limite 5s/jugada: "
            + ("SI" if violations == 0 else "NO")
        )
    print(f"  Tiempo total: {elapsed:.2f}s")


if __name__ == "__main__":
    run_match(num_games=12, size=7)
