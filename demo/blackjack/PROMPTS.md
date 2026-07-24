# The prompts that produced this project

Built entirely by a coding agent with only the rv skill and behave-rv 0.3.0
from PyPI; stdlib-only, browser UI served by the app itself. Three turns,
verbatim; a separate session independently re-ran every gate.

## Turn 1 - the build request

> Build me a browser Blackjack game (player vs dealer, one deck,
> hit/stand/new-hand buttons) with runtime verification built in. Each
> dealt hand is the thing I care about. I want to play in the browser and
> watch a behave-rv dashboard alongside, enforcing my table rules:
> 1. Once a hand stands, it must never be dealt another card.
> 2. A hand that busts must never be settled as a win.
> 3. Every hand dealt must reach its settlement - win, lose, or push -
>    within 30 seconds; a hand nobody finishes is a violation.
> 4. A payout may only ever happen after the hand's settlement.
> The game emits its events to the monitor as it runs; also give me a
> scripted demo mode (no browser needed) that plays several hands
> including cheating ones injected as corrupted events - a card dealt
> after stand, a busted hand settled as a win - so the dashboard and a
> replay gate show the violations.

Outcome: the four rules transcribed as user policies with a domain
judgment the rules needed - scoping 1 and 2 to the PLAYER, since dealer
draws after a stand and dealer-bust wins are the game, not violations.
The agent seeded the post-terminal case itself, confirmed a post-close
event slips through, and put the terminal-vs-TTL decision to the user
(who kept the terminal: hands live for seconds). Gates pinned 28/4.

## Turn 2 - a promotion the agent refused to ship broken

> One promotion: 'a hand is never settled twice' becomes my rule - a
> double settlement is how money leaks.

Outcome: the agent STOPPED - it verified its own earlier suggestion was
semantically wrong ("at most once" is a counting property; the scoped
`never` draft fires on every first legitimate settlement, since the scope
opens on the very event it prohibits) and refused to ship a misfiring
rule, offering two verified alternatives with honest boundaries.

## Turn 3 - the user picks the marker

> Go with B: the resettled marker is faithful to what I meant, and I
> accept the boundary that a raw stream-duplicate of the settle event is
> beyond any single-occurrence rule.

Outcome: a `hand.resettled` guard emission, the user's policy on it, an
intended contract change whose pre-save diff the agent read line by line
(including a site-reindexing artifact from inserting the guard above the
existing emission), and a bonus semantics finding: the self-contained
`never` has NO terminal blind spot - the post-close marker is still
caught, proven by seed. Final: five user policies, re-pinned 38/6, green.
