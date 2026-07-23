Feature: device activation ordering

  # Rule 1: a device may only be activated immediately after its provisioning
  # check passed -- activation must be the very NEXT thing after provision_ok,
  # not just any time later. "immediately after" -> previously (immediate
  # predecessor), not before (any earlier point).
  Scenario: a device is only activated immediately after its provision check passed
    When a device is "activated"
    Then a device is "provision_ok" previously
