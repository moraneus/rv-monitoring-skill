# The prompts that produced this project

Built entirely by a coding agent with only the rv skill and behave-rv 0.3.0
from PyPI; stdlib-only, browser UI served by the app itself. Two turns,
verbatim; a separate session independently re-ran every gate.

## Turn 1 - the build request

> Build me a browser Snake game with runtime verification built in. A game
> session starts, the snake moves on a grid, eats food, grows, and the
> session ends when the snake dies (hits a wall or itself). I want to play
> it in my browser with the arrow keys, and I want a behave-rv monitor
> running alongside with its live dashboard, watching these rules of mine:
> 1. Once a game is over, no further moves or points may ever be scored
>    for that game.
> 2. Every food eaten must be followed by the snake growing within 2
>    seconds.
> 3. The snake must never reverse straight into itself - a 180-degree turn
>    must never be accepted.
> The game engine should emit its events to the monitor as it runs, and
> there should also be a scripted demo mode (no browser needed) that plays
> a few games including rule-breaking ones injected as corrupted events,
> so I can see violations on the dashboard and in a replay gate.

Outcome: the three rules transcribed as user policies; `game.over`
deliberately NOT a terminal (a terminal would settle rule 1 as satisfied
at death and hide post-over corruption - the false-green trap, cited from
the skill), with a 300s quiescence window disclosed as the real guarantee;
the reversal rule read classify-not-enumerate (a `reversal_accepted`
boolean stamped at the emit layer); the agent played the game in a real
browser to verify. Gates pinned at 15 verdicts, 4 violations.

## Turn 2 - one promotion

> Sanctioned on all counts... One promotion: 'a game must start before
> anything else happens' becomes my rule - anything scoring or moving
> before a start event is exactly the kind of stream corruption I want
> caught. Leave the other two as suggestions.

Outcome: policy 04 as two `before` scenarios (moves and points - the
clarified intent), no contract change (existing steps reused, no save),
re-pinned 15/4 -> 28/6 with the orphan-game faults. Final: four user
policies, gates green.
