# Energy Usage

![Energy Usage icon](assets/energy-usage-icon.svg)

Energy Usage is an independent Home Assistant integration that imports delayed utility energy intervals through reviewed provider adapters. Release `0.1.0-rc.1` supports one provider account and one service location. Entergy is the only available provider in this first release.

Energy Usage is unofficial and is not affiliated with, endorsed by, or supported by any utility. Utility readings can arrive hours or days late. They are not live, real-time, revenue-grade, or bill-grade. Use the newest-interval and last-successful-fetch sensors to judge freshness.

The integration provides rolling consumption summaries and correction-aware external Recorder statistics for the Home Assistant Energy dashboard. Returned energy, cost, and compensation appear only when the active provider explicitly supports them. Money data is shown only when the provider currency matches the Home Assistant currency; no currency conversion or tariff estimate is invented.

Credentials are entered only through the trusted local Home Assistant config flow. They remain in the permission-protected config entry so Home Assistant can reconnect after a restart. That storage is not an encrypted password vault, and backups may contain the credentials. Interactive MFA, CAPTCHA, consent, and unknown challenges fail closed.

The default update interval is four hours and can be set from one to 24 hours, subject to the provider minimum. Normal reconciliation revisits recent intervals, while bounded background backfill imports the provider's declared historical range. A private canonical ledger retains correction history and baselines without putting account numbers or addresses in entity IDs, statistics IDs, or diagnostics.

This release candidate supports Home Assistant 2026.9.3 and 2026.9.4 on Python 3.14. It is not yet published. Do not install a moving branch on a production Home Assistant system.

Read the [provider matrix](docs/PROVIDERS.md), [installation procedure](docs/INSTALL.md), [privacy model](docs/PRIVACY.md), [rollback procedure](docs/ROLLBACK.md), [security policy](SECURITY.md), [contribution guide](CONTRIBUTING.md), [attribution](NOTICE.md), and [changelog](CHANGELOG.md).
