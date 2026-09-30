# Changelog

## [0.1.0-rc.2] — Release candidate

- Show a specific setup error when the required no-export confirmation is missing, without attempting provider authentication. No provider transport or credential behavior changed.

## [0.1.0-rc.1] — Release candidate

- Introduced the provider-neutral Energy Usage product, `energy_usage` Home Assistant domain, and pseudonymous public identities.
- Added the first reviewed provider adapter for Entergy with fixed-origin bounded transport and fail-closed interactive challenge handling.
- Added one-account, one-service-location setup with a provider contract designed for separately reviewed future adapters.
- Added a private correction-aware ledger, bounded historical backfill, rolling summaries, and external Recorder statistics.
- Added capability-filtered imported energy, returned energy, cost, and compensation surfaces. Unsupported values stay absent, and money requires matching provider and Home Assistant currencies.
- Added privacy-safe diagnostics, generic repairs, protected migration checks, and deterministic unload and cleanup behavior.
- Supported Home Assistant 2026.9.3 and 2026.9.4 on Python 3.14.
- Retained the disclosed expiring upstream dependency exception described in [SECURITY.md](SECURITY.md); this is not a clean audit.

Utility data may be delayed and is not bill-grade. Installation starts only after the reviewed release archive, checksum, attestation, backup, and `ha core check` gates pass.
