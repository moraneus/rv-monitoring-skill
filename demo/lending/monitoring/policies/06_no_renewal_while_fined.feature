Feature: fine enforcement

  Scenario: a member with an unpaid fine never renews a loan
    Given a member's fine is "owed" until a member's fine is "paid_off"
    Then a member renews a loan never happens
