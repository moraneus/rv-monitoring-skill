# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values -
use the exact strings listed under each step (a value the app never
emits will compile but silently never match).
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `a mine explodes`

- **identity**: `board.mine.boom` (trigger)
- **observes**: event `mine.boom`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a mine explodes never happens

  Scenario: <your policy name>  # eventuality
    Then a mine explodes has happened

  Scenario: <your policy name>  # precedence
    When a mine explodes
    Then a mine explodes before

  Scenario: <your policy name>  # deadline
    When a mine explodes
    Then a mine explodes within "30" seconds

```

## `a cell is revealed on the board`

- **identity**: `board.reveal.any` (trigger)
- **observes**: event `board.reveal`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a cell is revealed on the board never happens

  Scenario: <your policy name>  # eventuality
    Then a cell is revealed on the board has happened

  Scenario: <your policy name>  # precedence
    When a cell is revealed on the board
    Then a cell is revealed on the board before

  Scenario: <your policy name>  # deadline
    When a cell is revealed on the board
    Then a cell is revealed on the board within "30" seconds

```

## `the planted flags outnumber the mines`

- **identity**: `board.flags.overflow` (trigger)
- **observes**: event `flag.set`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the planted flags outnumber the mines never happens

  Scenario: <your policy name>  # eventuality
    Then the planted flags outnumber the mines has happened

  Scenario: <your policy name>  # precedence
    When the planted flags outnumber the mines
    Then the planted flags outnumber the mines before

  Scenario: <your policy name>  # deadline
    When the planted flags outnumber the mines
    Then the planted flags outnumber the mines within "30" seconds

```

## `a cell is revealed`

- **identity**: `cell.reveal.occurs` (trigger)
- **observes**: event `cell.reveal`, entity key `game_id, cell`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then a cell is revealed never happens

  Scenario: <your policy name>  # eventuality
    Then a cell is revealed has happened

  Scenario: <your policy name>  # precedence
    When a cell is revealed
    Then a cell is revealed before

  Scenario: <your policy name>  # deadline
    When a cell is revealed
    Then a cell is revealed within "30" seconds

```

## `that cell was already revealed`

- **identity**: `cell.seen.state` (trigger)
- **observes**: event `cell.seen`, entity key `game_id, cell`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then that cell was already revealed never happens

  Scenario: <your policy name>  # eventuality
    Then that cell was already revealed has happened

  Scenario: <your policy name>  # precedence
    When that cell was already revealed
    Then that cell was already revealed before

  Scenario: <your policy name>  # deadline
    When that cell was already revealed
    Then that cell was already revealed within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
