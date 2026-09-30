# Security reporting

Security fixes are considered for the latest reviewed release candidate or release. Authentication, privacy, fixed-origin transport, ledger and Recorder integrity, dependency risk, and release supply chain are in scope.

Use [GitHub private vulnerability reporting](https://github.com/BeauDevCode/ha-energy-usage/security/advisories/new) for sensitive reports. If that form is unavailable, contact [@BeauDevCode](https://github.com/BeauDevCode) through GitHub to arrange a private channel. Do not post secrets or production data in a public issue. No bounty, response deadline, remediation SLA, or confidentiality outcome is promised.

Provide the smallest synthetic reproduction. Exclude usernames, passwords, tokens, private location IDs, service addresses, raw provider payloads, databases, backups, and Home Assistant runtime files. See the [privacy policy](docs/PRIVACY.md).

## Temporary upstream dependency exception

The reviewed Home Assistant 2026.9.3 and 2026.9.4 environments currently include upstream host dependency findings documented and enforced by `scripts/check_dependency_audit.py`. Energy Usage adds no runtime dependency. CI accepts only the exact, expiring reviewed finding set while the installed Home Assistant metadata still requires those exact versions; it rejects tool errors, skipped packages, malformed evidence, inventory changes, new findings, and expired exceptions.

The current review deadline is 2026-10-29 00:00:00 UTC. This is not a clean audit or a claim that the findings are harmless. Review sooner when a compatible patched Home Assistant release is available, recreate both environments, rerun every gate, and remove or explicitly re-review the exception.
