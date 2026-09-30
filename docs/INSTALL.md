# Installation and updates

**Release procedure only:** Install `0.1.0-rc.2` only after its exact published release archive, SHA-256 checksum, and GitHub artifact attestation have passed review. Never install a moving branch on a production system.

Energy Usage supports Home Assistant 2026.9.3 and 2026.9.4 on Python 3.14. Version 1 supports one provider account and one service location. Before installation, verify that no installed integration already owns the `energy_usage` domain. Create a protected supported Home Assistant backup with the database included, record the release tag and commit, and keep the prior component tree for rollback.

The successor uses `/config/custom_components/energy_usage/`. The older component uses `/config/custom_components/entergy_mobile/`. Never overwrite `custom_components/entergy_mobile/` with Energy Usage files. Do not run both integrations against the same utility account during transition, and do not edit `.storage` or Recorder manually.

## HACS

After publication, add `https://github.com/BeauDevCode/ha-energy-usage` as a custom integration repository and select the exact reviewed release tag. If HACS cannot preserve the exact tag, use the manual archive procedure.

## Manual archive

Download `ha-energy-usage-0.1.0-rc.2.zip` and its `.sha256` file from the same reviewed GitHub release. Verify the checksum with `sha256sum --check ha-energy-usage-0.1.0-rc.2.zip.sha256` or a trusted equivalent, then verify the artifact attestation against `BeauDevCode/ha-energy-usage`. Inspect the archive before extraction: its only top-level tree must be `custom_components/energy_usage/`.

Extract under the Home Assistant config directory so the final path is `/config/custom_components/energy_usage/`. Preserve the existing Home Assistant file ownership convention. Run `ha core check`; if it fails, restore only the staged component tree and stop. If it passes, schedule one planned restart.

After Home Assistant is healthy, add Energy Usage through Settings → Devices & services over a trusted local connection. Select Entergy, enter credentials privately, and select one returned service location. Never put credentials in shell history, chat, issue reports, repository files, or screenshots.

Validate the config entry, newest interval, last successful fetch, freshness, provider capabilities, external statistics, repair issues, and a bounded sanitized startup log. Initial historical backfill is gradual. Do not claim the utility bill or full history matches until enough published intervals have been compared.

For updates, repeat the exact-release review, protected backup, checksum, attestation, `ha core check`, and one planned restart. See [rollback](ROLLBACK.md) before replacing a version that may have written a newer ledger schema.
