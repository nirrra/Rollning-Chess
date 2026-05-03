from __future__ import annotations

from .exceptions import RollingChessError
from .moves import GameStatus
from .state import GameState


def main() -> None:
    state = GameState.initial()
    print("Rolling Chess CLI. Enter moves like e2e4 or a7a8q. Type quit to exit.")
    while True:
        print()
        print(state)
        result = state.result()
        if result.status is GameStatus.CHECKMATE:
            print(f"Checkmate. {result.winner.value} wins.")
            return
        if result.status is GameStatus.STALEMATE:
            print("Stalemate.")
            return
        if state.is_check(state.turn):
            print(f"{state.turn.value} to move is in check.")
        else:
            print(f"{state.turn.value} to move.")
        text = input("> ").strip()
        if text.lower() in {"quit", "exit"}:
            return
        try:
            state = state.apply_move(text)
        except RollingChessError as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()

