"""The scripted tic-tac-toe traffic, shared by the replay gate and the demo.

Six games driven through the real service: two healthy games played to
completion, then four that inject illegal events as CORRUPTED MOVES (through
``service.force_move``, which bypasses the game's own turn/occupancy/over
guards to model an out-of-policy event reaching the monitor):

  G1  healthy X win           -> all four laws satisfied
  G2  healthy draw            -> all four laws satisfied
  G3  double move by X        -> alternation violated (and, abandoned, law 3)
  G4  a move after the win     -> "no move after finish" violated
  G5  abandoned before finish -> "every game finishes" violated
  G6  a move from nowhere     -> "no orphan moves" violated (never started)

The post-finish move of G4 is injected BEFORE the game's terminal
(``end_game``) on purpose: a terminal settles the prohibition, so a move
arriving after it would be invisible (the terminal-window rule). Every healthy
flow ends with zero violations; the four faults are the only violations.
"""

from __future__ import annotations

from app.game_service import TicTacToeService

# One tic per ordered action keeps event times strictly increasing and readable.
_STEP = 1.0


class Clock:
    """A manually-advanced clock: deterministic for the gate, readable live."""

    def __init__(self, start: float = 0.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def tick(self, dt: float = _STEP) -> None:
        self.now += dt


def run_script(service: TicTacToeService, clock: Clock) -> list[str]:
    """Drive the five games. Returns a short human-readable log of what it did."""
    log: list[str] = []

    def step():
        clock.tick()

    # -- G1: healthy X win (top row) -------------------------------------
    service.new_game("g1"); step()
    for cell in (0, 3, 1, 4, 2):          # X:0 O:3 X:1 O:4 X:2  -> X wins top row
        service.play("g1", cell); step()
    service.end_game("g1"); step()
    log.append("g1: healthy game, X wins the top row")

    # -- G2: healthy draw -------------------------------------------------
    service.new_game("g2"); step()
    for cell in (0, 1, 2, 4, 3, 5, 7, 6, 8):   # a full board with no line
        service.play("g2", cell); step()
    service.end_game("g2"); step()
    log.append("g2: healthy game, ends in a draw")

    # -- G3: a double move by X (corrupted) ------------------------------
    service.new_game("g3"); step()
    service.play("g3", 0); step()          # X (legal opening move)
    service.force_move("g3", "X", 1); step()   # X AGAIN, no O in between: DOUBLE MOVE
    service.end_game("g3", "abandoned"); step()
    log.append("g3: X moves twice in a row (alternation violated)")

    # -- G4: a move after the win (corrupted) ----------------------------
    service.new_game("g4"); step()
    for cell in (0, 3, 1, 4, 2):          # X wins the top row
        service.play("g4", cell); step()
    service.force_move("g4", "O", 5); step()   # a move AFTER the game is won
    service.end_game("g4"); step()             # terminal comes AFTER the bad move
    log.append("g4: a move is made after X has already won (no-move-after-finish violated)")

    # -- G5: abandoned before finishing ----------------------------------
    service.new_game("g5"); step()
    service.play("g5", 4); step()          # X
    service.play("g5", 0); step()          # O
    service.end_game("g5", "abandoned"); step()   # reset before a winner/draw
    log.append("g5: abandoned before finishing (every-game-finishes violated)")

    # -- G6: a move from nowhere (corrupted) -----------------------------
    # No new_game("g6"): the move arrives for a game that never emitted
    # "started". force_move on an unknown game_id emits a bare game.move.
    service.force_move("g6", "X", 0); step()
    log.append("g6: a move for a game that never started (no-orphan-moves violated)")

    return log
