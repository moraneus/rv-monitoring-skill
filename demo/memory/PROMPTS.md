# The prompts that produced this project

Built entirely by a coding agent with only the rv skill and behave-rv 0.3.0
from PyPI; stdlib-only, browser UI served by the app itself. Two turns
(plus a crash recovery), verbatim; a separate session independently re-ran
every gate.

## Turn 1 - the build request

> Build me a browser Memory pairs game (a 4x4 grid of face-down cards,
> click two to flip, matches stay up) with runtime verification built in.
> I want the behave-rv dashboard alongside, enforcing my rules:
> 1. A card that is part of a found match must never be flipped again for
>    the rest of that game.
> 2. After a second card of an attempt is flipped, the attempt must
>    resolve - matched or both flipped back - within 3 seconds.
> 3. Once the last pair is found the game is complete - nothing may ever
>    happen in that game again.
> The game emits its events to the monitor as it runs; also give me a
> scripted demo mode (no browser needed) that plays a few games including
> cheating ones injected as corrupted events - re-flipping a matched card,
> an attempt left hanging - so the dashboard and a replay gate show the
> violations.

Outcome: three entity kinds with disciplined keys - cards by the composite
`(game_id, position)`, attempts by `attempt_id` (with game_id kept OUT of
the attempt bindings so attempt events can never settle a game or card
entity), games by `game_id`. Completion deliberately non-terminal so rule
3 stays armed after the last pair, proven by the act-after-complete cheat.
The build also surfaced the grace-vs-deadline interaction now documented
in the cheatsheet: the default 5s reorder grace false-timed-out healthy
3-second attempts on the live board until grace was set below the
deadline. In-browser cheat-injection buttons make violations watchable
live. Gates pinned 83/3.

## Turn 2 - one promotion (report lost to a crash, work verified on disk)

> One promotion: 'every matched card was flipped first' becomes my rule -
> a match appearing out of nowhere is stream corruption I want caught.

Outcome: policy 04 (`When a card is matched / Then a card is flipped
before`, on the card's composite key) reusing existing steps - no contract
change, correctly no `catalog save`; a phantom-match fault seeded in the
gate, the demo, and as a browser cheat button; re-pinned 83/3 -> 137/4.
The agent's report was lost to a connection failure, but the completed
work verified green on disk before the resumed agent re-sent it. Final:
four user policies, gates green.
