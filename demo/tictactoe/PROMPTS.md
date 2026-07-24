# The prompts that produced this project

Built entirely by a coding agent with only the rv skill and behave-rv 0.3.0
from PyPI; stdlib-only, browser UI served by the app itself. Two turns,
verbatim; a separate session independently re-ran every gate. This build
produced the skill's one-shot-trigger rule.

## Turn 1 - the build request

> Build me a browser tic-tac-toe (two players at one keyboard, X and O
> clicking squares) with runtime verification built in. I want the
> behave-rv dashboard alongside, enforcing the laws of the game as I state
> them:
> 1. The players must strictly alternate: immediately after X moves, the
>    very next move in that game must be O's, and vice versa.
> 2. Once a game is won or drawn, no further move may ever be made in it.
> 3. Every game that starts must eventually finish - won or drawn, none
>    abandoned forever.
> The game emits its events to the monitor as it runs; also give me a
> scripted demo mode (no browser needed) that plays a few games including
> illegal ones injected as corrupted events - a double move by the same
> player, a move after the win - so the dashboard and a replay gate show
> the violations.

Outcome: the build that discovered, empirically, that triggered forms arm
ONCE per entity - a `previously` alternation rule would check only the
first move-pair per game. The agent invented history stamping: the emit
layer stamps `prev_player` from true move order and a self-contained
`never` checks every move. Also: the won/draw finish deliberately NOT the
terminal (`game.ended`, fired when a game leaves the board, is), so law 2
stays armed after the win - with the fault seeded before the terminal per
the terminal-windows rule; and a unified `game.status` lifecycle type so
law 3's `has happened` can settle violated for abandoned games at the
terminal. Gates pinned 15/4.

## Turn 2 - one promotion

> One promotion: 'a move only happens after its game has started' becomes
> my rule - moves from nowhere are stream corruption I want caught.

Outcome: policy 04 using `before` - with the agent applying its own
discovery in reverse: for precedence, settling at the first move is
sufficient and correct (started-before-move-one implies
started-before-every-move). No contract change; re-pinned 15/4 -> 23/5
with the orphan-move fault, honest pendings on the orphan's degenerate
instances explained. Final: four user policies, gates green.
