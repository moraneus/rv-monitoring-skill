# The prompts that produced this project

Built entirely by a coding agent with only the rv skill and behave-rv 0.3.0
from PyPI; stdlib-only, browser UI served by the app itself. Two turns
(plus a crash recovery), verbatim; a separate session independently re-ran
every gate.

## Turn 1 - the build request

> Build me a browser Minesweeper (8x8, 10 mines, click to reveal,
> right-click to flag) with runtime verification built in. I want to play
> it in the browser with a behave-rv dashboard alongside, enforcing my
> rules:
> 1. Once a mine explodes, that game is over - no further cell may ever be
>    revealed in it.
> 2. A cell that has been revealed must never be revealed again - each
>    cell of each game, individually.
> 3. The number of flags planted must never exceed the number of mines on
>    the board.
> The game emits its events to the monitor as it runs; also give me a
> scripted demo mode (no browser needed) that plays a few boards including
> cheating ones injected as corrupted events - a reveal after the boom, a
> double reveal of the same cell - so the dashboard and a replay gate show
> the violations.

Outcome: three planted traps, three correct answers. Rule 1: no terminal,
so post-boom reveals stay catchable. Rule 2 (per-cell at-most-once, keyed
by the composite `(game_id, cell)`): solved with an action/state split -
the scope opens on the `cell.revealed` STATE event emitted strictly after
the reveal action, so the first reveal is legal and only a repeat
violates. Rule 3 (counting): projected honestly - the game stamps running
flag and mine counts into each flag event and a predicate compares the
payload fields, with the caveat that the counting credit is the app's.
Cheat-injection scaffolding excluded from the contract surface. Gates
pinned 116/3.

## Turn 2 - one promotion (through a crash)

> One promotion: 'nothing happens before the game starts' becomes my rule
> - you said it needs new surface, so add what it needs as one intended
> change.

The agent's first attempt died on a connection failure mid-change - and
the replay gate itself flagged the interrupted state (pin MISMATCH), the
machinery catching a half-applied change exactly as designed. On resume:
the new step as an intended contract change with the genuine pre-save diff
quoted (`game.lifecycle.started: added`, all emit sites unchanged), the
scope honestly narrowed to reveals ("nothing happens" is per-trigger in
the fragment; a stray pre-start flag is not covered - offered as an
extension), re-pinned 116/3 -> 124/4. Final: four user policies, green.
