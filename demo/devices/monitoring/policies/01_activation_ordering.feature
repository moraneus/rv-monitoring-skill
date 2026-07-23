Feature: device activation ordering

  Scenario: a device may only be activated immediately after its provisioning check passed
    When a device is "activated"
    Then a device is "provision_ok" previously
