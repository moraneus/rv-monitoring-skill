Feature: unpaid balance blocks confirmation

  Scenario: a member with an unpaid balance has no booking confirmed
    Given a member's balance is "owed" until a member's balance is "settled"
    Then a member confirms a booking never happens
