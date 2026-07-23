Feature: fines freeze renewals

  Scenario: a member who owes a fine cannot renew until they pay it off
    Given a member's fine is "owed" until a member's fine is "paid_off"
    Then a member renews a loan never happens
