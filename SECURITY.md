# Security reporting

Security fixes are considered for the latest reviewed release candidate or release. Authentication, privacy, fixed-origin transport, ledger and Recorder integrity, dependency risk, and release supply chain are in scope.

Use [GitHub private vulnerability reporting](https://github.com/BeauDevCode/ha-energy-usage/security/advisories/new) for sensitive reports. If that form is unavailable, contact [@BeauDevCode](https://github.com/BeauDevCode) through GitHub to arrange a private channel. Do not post secrets or production data in a public issue. No bounty, response deadline, remediation SLA, or confidentiality outcome is promised.

Provide the smallest synthetic reproduction. Exclude usernames, passwords, tokens, private location IDs, service addresses, raw provider payloads, databases, backups, and Home Assistant runtime files. See the [privacy policy](docs/PRIVACY.md).

## Temporary upstream dependency exception

The reviewed Home Assistant 2026.9.3 and 2026.9.4 environments currently pin `cryptography==48.0.1` and `PyJWT==2.13.0`. A fresh September 29 audit reports three unique cryptography advisories (`PYSEC-2026-3552`, `PYSEC-2026-3553`, and `PYSEC-2026-3554`) and ten unique PyJWT advisories (`CVE-2026-101917`, `CVE-2026-102265` through `CVE-2026-102269`, and `CVE-2026-102271` through `CVE-2026-102274`). The audit emits 16 rows because the three cryptography findings are duplicated by aliases; policy compares 13 normalized package/version/advisory tuples. Published fixes require cryptography 49.0.0 or 50.0.0 and PyJWT 2.14.0, which conflict with the reviewed Home Assistant pins.

Energy Usage adds no runtime dependency and does not override host pins. CI accepts only this exact, expiring finding set while installed Home Assistant metadata still requires both exact versions. It rejects tool errors, skipped packages, malformed evidence, inventory changes, new or disappeared findings, changed host pins, and expired exceptions.

The current review deadline is 2026-10-29 00:00:00 UTC. This is not a clean audit or a claim that the findings are harmless. Review sooner when a compatible patched Home Assistant release is available, recreate both environments, rerun every gate, and remove or explicitly re-review the exception.
