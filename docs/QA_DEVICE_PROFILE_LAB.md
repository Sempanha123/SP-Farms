# QA Device Profile Lab

This subsystem is for applications/devices the operator owns or is explicitly authorized to test. It is not intended for platform evasion, account creation, or bypassing third-party security systems.

## Separation and authorization

QA profiles are independent records. They never replace manufacturer, model, serial, Android version, connection state, or other actual inventory reported by ADB or a provider. Per-device QA assignments are also independent from account assignments.

A package must have a valid Android package ID, a non-empty ownership/authorization note, and an enabled allowlist record before a profile can be pushed, reloaded, verified, or restored. Known social, payment, banking, authenticator, Play services, and anti-fraud targets are rejected before the allowlist lookup.

## Profiles

Profiles support create, edit, clone, delete, deterministic compatibility randomization, assignment, and versioned JSON import/export. Synthetic fixture fields use `test_*` names. Compatibility randomization changes only harmless catalog fields such as manufacturer, model, product, hardware, and board; it does not generate identity values.

Operators may explicitly supply `test_*` values from authorized fixtures. The JSON importer rejects unknown schema versions, malformed types, and unknown fields. Actual device values remain visible only in Device Manager.

## Operations

1. Add an owned application package to the allowlist with authorization evidence.
2. Create or select a QA profile.
3. Select an online QA device and save its independent profile assignment.
4. Push, push and reload, verify, or restore defaults.

Each operation returns a typed result. Audits retain actor, operation, device identity, package, profile UUID, timestamp, and outcome—never the profile's synthetic identifiers.
