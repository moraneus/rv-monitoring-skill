# The policy vocabulary (generated - do not edit)

Every phrasing below can be used in a `.feature` policy under
`monitoring/policies/`. Quoted `<placeholders>` take concrete values.
Regenerate this file with `python monitoring/generate_steps_doc.py`.

## `the game has started`

- **identity**: `game.lifecycle.started` (trigger)
- **observes**: event `game.started`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the game has started never happens

  Scenario: <your policy name>  # eventuality
    Then the game has started has happened

  Scenario: <your policy name>  # precedence
    When the game has started
    Then the game has started before

  Scenario: <your policy name>  # deadline
    When the game has started
    Then the game has started within "30" seconds

```

## `a mine explodes`

- **identity**: `game.mine.exploded` (trigger)
- **observes**: event `mine.exploded`, entity key `game_id`

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

## `a cell is revealed`

- **identity**: `game.cell.reveal` (trigger)
- **observes**: event `cell.reveal`, entity key `game_id`

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

## `the same cell has been revealed`

- **identity**: `cell.state.revealed` (trigger)
- **observes**: event `cell.revealed`, entity key `game_id, cell`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the same cell has been revealed never happens

  Scenario: <your policy name>  # eventuality
    Then the same cell has been revealed has happened

  Scenario: <your policy name>  # precedence
    When the same cell has been revealed
    Then the same cell has been revealed before

  Scenario: <your policy name>  # deadline
    When the same cell has been revealed
    Then the same cell has been revealed within "30" seconds

```

## `the same cell is revealed again`

- **identity**: `cell.reveal.repeat` (trigger)
- **observes**: event `cell.reveal`, entity key `game_id, cell`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then the same cell is revealed again never happens

  Scenario: <your policy name>  # eventuality
    Then the same cell is revealed again has happened

  Scenario: <your policy name>  # precedence
    When the same cell is revealed again
    Then the same cell is revealed again before

  Scenario: <your policy name>  # deadline
    When the same cell is revealed again
    Then the same cell is revealed again within "30" seconds

```

## `more flags are planted than there are mines`

- **identity**: `game.flags.exceed_mines` (trigger)
- **observes**: event `flag.placed`, entity key `game_id`

Example scenarios:

```gherkin
  Scenario: <your policy name>  # prohibition
    Then more flags are planted than there are mines never happens

  Scenario: <your policy name>  # eventuality
    Then more flags are planted than there are mines has happened

  Scenario: <your policy name>  # precedence
    When more flags are planted than there are mines
    Then more flags are planted than there are mines before

  Scenario: <your policy name>  # deadline
    When more flags are planted than there are mines
    Then more flags are planted than there are mines within "30" seconds

```

## Combining steps

Any trigger phrasing can be the `When`, the `Then` operand, or the
`Given` scope of the temporal forms - see the operator reference in
the rv skill (or docs/OPERATORS.md in behave-rv) for all nine forms
and their exact semantics. One correlation key per scenario.
