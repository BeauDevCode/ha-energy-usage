# Privacy and data retention

The trusted local Home Assistant config flow collects the selected provider username and password. They remain in Home Assistant's permission-protected config entry so the integration can reconnect after a restart. A config entry is not an encrypted password vault. Protected Home Assistant backups may contain these credentials and need the same care as the utility account itself. Short-lived provider session data remains in process memory and is discarded on unload or failed setup.

The integration processes a private provider location ID and utility intervals inside private runtime and storage boundaries. A random public location ID is used for entity, device, repair, and statistics identities. Downloadable diagnostics use a fixed allowlist: provider key, public ID, declared capabilities and timing, schema versions, safe status categories, timestamps, and counts. Diagnostics exclude usernames, passwords, private location IDs, masked labels, addresses, tokens, raw payloads, headers, and exception text.

Provider requests go only to the fixed HTTPS origins reviewed for each released adapter. The integration sends no analytics or telemetry. Tests and CI use synthetic fixtures and never call a production utility account.

The private ledger retains up to the reviewed history window plus compacted baselines so later corrections do not duplicate totals. Home Assistant Recorder stores external statistics separately and may retain household energy history according to the operator's Recorder policy. Removing the integration does not delete Recorder history. Never edit SQLite or `.storage` directly.

Utility data may be delayed and is not live or bill-grade. Money data is available only when the provider declares it and its currency matches Home Assistant. Energy Usage performs no conversion and invents no missing values, tariffs, exports, or account details.
