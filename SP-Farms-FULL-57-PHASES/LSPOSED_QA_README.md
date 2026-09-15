# LSPosed QA Bridge Example (Authorized Test Apps Only)

This example is for applications you own or are explicitly authorized to test.
Do not target Facebook, Facebook Lite, Instagram, financial apps, identity apps,
or other third-party security-sensitive software.

Recommended remote profile:
`/data/local/tmp/sp_farms_qa/profile.json`

Recommended bridge:
- SP-Farms pushes versioned JSON.
- SP-Farms sends a broadcast/action owned by your QA module.
- Your QA module reloads the JSON.
- Your QA module acknowledges the active profile version.

Prefer restrictive permissions (`600`) and a package allowlist.

Keep actual Device data separate from QAProfile synthetic data.
