Feature: Promotions get a prompt response

  Scenario: a promoted booking is confirmed or cancelled within 15 seconds
    When a booking is "promoted"
    Then a booking is confirmed or cancelled within "15" seconds
