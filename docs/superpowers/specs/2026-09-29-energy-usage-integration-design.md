# Energy Usage integration design

**Status:** Approved direction; detailed design awaiting owner review

**Product name:** Energy Usage

**Target repository:** `BeauDevCode/ha-energy-usage`

**Home Assistant domain:** `energy_usage`

**Initial provider:** Entergy

## Objective

Create a provider-neutral Home Assistant custom integration that imports delayed
whole-home electricity usage and source-provided cost for one United States
service location. Entergy is the first supported provider. Additional utilities
are added through reviewed provider adapters without changing the product name,
Home Assistant domain, common data model, or dashboard statistics contract.

The first release succeeds when it:

- configures exactly one utility provider and one service location;
- imports validated interval usage through the Entergy adapter;
- provides stable Home Assistant Energy dashboard statistics;
- keeps provider credentials and private utility identifiers out of logs,
  diagnostics, entity IDs, statistics IDs, repository files, and chat;
- exposes accurate freshness and operational status;
- preserves the hardened ledger, correction, backfill, and release guarantees of
  the reviewed Entergy release; and
- defines a repeatable qualification process for future United States providers.

## Scope and product promises

Version 1 supports one configured location and one active provider account per
Home Assistant installation. If a provider login returns multiple locations,
the setup flow requires the user to select exactly one. The integration does not
combine buildings, accounts, meters, or providers.

The long-term goal is broad United States provider coverage. The UI and project
documentation list only providers with a released, tested adapter. The project
must not claim that every United States utility works before that coverage is
implemented and verified.

The first release covers:

- provider selection, local credential entry, location selection,
  reauthentication, options, unload, and removal;
- imported and returned energy when the provider supplies both;
- provider-supplied cost and compensation when the currency contract is valid;
- correction-aware external Recorder statistics for the Energy dashboard;
- delayed summary, freshness, backfill, and health entities;
- a private canonical ledger with bounded history and recovery markers;
- explicit unsupported-challenge and schema-drift handling; and
- reproducible builds, security checks, releases, installation, and rollback.

It does not cover real-time watts, bill payment, tariff prediction, estimated
cost invented from incomplete rates, electrical-panel hardware, multiple
locations, or simultaneous providers. Utility data may be delayed and must not
be described as live or revenue-grade.

## Product identity and repository transition

`energy_usage` is a new Home Assistant integration identity. Home Assistant
requires the manifest domain to match the component directory and treats that
domain as permanent. The package therefore lives at:

```text
custom_components/energy_usage/
```

The generic project belongs in a new independent repository,
`BeauDevCode/ha-energy-usage`. The existing `BeauDevCode/ha-entergy` repository
remains available as the attributable, auditable Entergy-specific fork. Its
release history, checksums, attestations, license, and notices are retained. It
receives a transition notice pointing to Energy Usage and is archived only after
the replacement has a verified release and migration guidance.

The new repository retains the applicable MIT attribution and adds a notice that
credits the original Entergy project and hardened fork. It uses a generic
electricity icon and must not imply endorsement by Entergy or another utility.

An availability check against the installed Home Assistant 2026.9.3 component
set and the owner's GitHub repositories found no current `energy_usage` domain
or `BeauDevCode/ha-energy-usage` repository. Those checks are repeated before
repository creation and before the first release because they are not global
name reservations.

## Architecture

Energy Usage has a common Home Assistant layer and isolated provider adapters:

```text
Home Assistant config flow
        |
        v
Provider registry ---> Entergy adapter
        |              Future provider adapters
        v
Normalized location and interval models
        |
        v
Coordinator ---> private ledger ---> Recorder external statistics
        |                                  |
        v                                  v
Operational sensors                 Energy dashboard
```

The common layer owns identity, lifecycle, storage, scheduling, summaries,
statistics, diagnostics, repair issues, and UI translations. A provider adapter
owns only the remote service contract: authentication, location discovery,
bounded data retrieval, provider-specific response parsing, and provider-specific
rate limits.

The initial manifest uses `integration_type: service`, `iot_class:
cloud_polling`, `config_flow: true`, and `single_config_entry: true`. The one-entry
rule enforces the one-location product scope in Home Assistant as well as in the
flow.

## Component boundaries

The proposed package uses these boundaries:

- `const.py`: domain, generic option keys, common limits, and supported provider
  keys; no provider URL or brand text.
- `models.py`: immutable normalized location, capability, currency, interval,
  ledger, and snapshot values with no Home Assistant imports.
- `provider.py`: adapter protocols and the provider registry.
- `providers/entergy/`: the fixed-origin Entergy transport, authentication state
  machine, parser, metadata, localized provider strings, and synthetic fixtures.
- `ledger.py`: provider-neutral durable intervals, deduplication, corrections,
  pruning, cumulative totals, and recovery markers.
- `statistics.py`: provider-neutral external-statistics metadata and import.
- `coordinator.py`: polling, backoff, backfill, correction reconciliation, and
  orchestration through the adapter protocol.
- `config_flow.py`: provider selection, adapter-owned authentication fields,
  single-location selection, reauthentication, and generic options.
- `sensor.py` and `entity.py`: provider-neutral health and delayed summaries.
- `diagnostics.py`: an explicit generic allowlist plus provider-owned sanitized
  capability fields.
- `issues.py`: generic repair issue creation and stable public issue IDs.

Provider implementations must not import Recorder, entity registry, device
registry, config-entry migration, or ledger storage code.

## Provider adapter contract

Each adapter declares immutable metadata and implements a bounded asynchronous
contract equivalent to:

```python
class EnergyProvider(Protocol):
    key: str
    name: str
    country_codes: frozenset[str]

    def auth_schema(self) -> vol.Schema: ...
    async def authenticate(self, auth: Mapping[str, Any], budget: RequestBudget) -> None: ...
    async def list_locations(self, budget: RequestBudget) -> tuple[ProviderLocation, ...]: ...
    async def confirm_location(
        self, private_location_id: str, budget: RequestBudget
    ) -> ProviderLocation: ...
    async def fetch_intervals(
        self, request: IntervalRequest, budget: RequestBudget
    ) -> IntervalPage: ...
    async def logout(self, budget: RequestBudget) -> None: ...
```

The concrete interface may use typed configuration objects instead of mappings,
but it preserves these responsibilities. The adapter returns common normalized
models. It does not choose Home Assistant entity IDs, statistic IDs, storage
keys, polling tasks, or repair issue IDs.

Every provider declares its capabilities explicitly, including:

- imported energy;
- returned energy;
- monetary cost or compensation;
- interval duration and publication delay;
- currency semantics;
- timezone source;
- correction or estimation markers;
- historical range and pagination; and
- provider-specific minimum polling and request-budget rules.

Missing capabilities stay absent. The common layer never synthesizes zeros,
currencies, exports, costs, or timezone semantics that the source did not supply.

## Configuration and one-location rule

The user flow is:

1. Select a released provider from the United States provider list.
2. Read a provider-specific privacy and credential-storage notice.
3. Enter credentials only in the trusted local Home Assistant flow.
4. Authenticate once with a bounded request budget.
5. Select exactly one returned service location.
6. Supply a timezone only when the provider cannot supply a validated one.
7. Review the provider, masked location label, data delay, and supported
   measurements.
8. Create the single config entry.

The config entry stores:

- `provider_key`;
- provider-owned authentication data needed for restart and reauthentication;
- the provider-private location identifier;
- a persistent random `location_public_id`;
- the validated timezone;
- provider capability and schema versions needed for safe migration; and
- ledger initialization markers.

The entry title is a generic masked label such as `Energy Usage · Entergy ·
••••1234`. Account numbers, addresses, email addresses, and usernames are never
used as the config-entry unique ID. The entry unique ID is a persisted random
identifier.

Duplicate and concurrent flow checks use a private provider/location match while
the flow is active. The random public ID remains stable across password changes,
reauthentication, nickname changes, and provider response changes.

Changing to another location or provider is not an options edit because it
changes the measured property and statistics meaning. Version 1 requires a
deliberate removal and new setup, with clear history-retention guidance.

## Identity, storage, and statistics

The random `location_public_id` is the only location value used in public Home
Assistant identifiers.

- Device identifier: `("energy_usage", location_public_id)`
- Entity unique ID: `<location_public_id>_<metric>`
- Ledger key: `energy_usage.ledger_<location_public_id>`
- Migration checkpoint: `energy_usage.migration_<entry_id>`
- Statistic source: `energy_usage`
- Consumption: `energy_usage:<location_public_id>_consumption`
- Return: `energy_usage:<location_public_id>_return`
- Cost: `energy_usage:<location_public_id>_cost`
- Compensation: `energy_usage:<location_public_id>_compensation`

Provider keys may appear in safe display metadata and diagnostics, but provider
account IDs and service addresses do not appear in identifiers. Provider keys
are never embedded in the statistic contract, so adding or renaming an adapter
does not change Energy dashboard sources.

The ledger records the provider key, adapter schema version, normalized interval
fingerprints, timezone, currency mode, and source revision semantics necessary
to reject incompatible data. It retains the current atomic-write, read-back,
pending-statistics, correction, pruning, and restart-recovery guarantees.

## Data flow

At setup, the selected adapter authenticates, enumerates locations, and confirms
the chosen location. After the entry is created, the coordinator:

1. creates a fresh provider client for the entry;
2. authenticates within the adapter request budget;
3. fetches the bounded recent reconciliation window;
4. asks the adapter to parse and normalize the response;
5. validates common interval invariants and declared capabilities;
6. atomically merges verified intervals into the private ledger;
7. queues the correction-aware Recorder statistics suffix;
8. verifies the queued statistics through supported Recorder APIs;
9. publishes summary and health entities from the verified ledger; and
10. logs out or clears in-memory tokens.

Historical backfill runs separately from the normal refresh and obeys both common
daily limits and stricter adapter limits. A provider cannot make the coordinator
poll faster than its declared safe minimum. A faster Home Assistant option is
clamped to that minimum.

## Authentication and secrets

Provider credentials are entered only through Home Assistant's local config
flow. They are never requested in chat, passed as command-line arguments, added
to Git, stored in workspace documentation, or included in diagnostics.

Home Assistant config-entry storage and backups may contain the credentials
required to reconnect. The setup flow and privacy documentation disclose that
Home Assistant is not an encrypted password vault. Protected backups and host
access controls remain required.

Tokens live in memory only and are cleared on unload, authentication failure,
and client disposal. Reauthentication must prove continued access to the same
private provider/location pair before replacing saved credentials. A provider
challenge, MFA request, CAPTCHA, consent step, or unknown redirect fails closed
and requires supported local user action. The integration never recommends
disabling account security.

Each provider adapter has fixed HTTPS origins and a closed method/path allowlist.
Redirects, headers, response size, content type, timeouts, pagination, numeric
precision, and untrusted error text are bounded before use.

## Currency, timezone, and measurements

Every interval is normalized to an absolute UTC time range and retains the
validated service timezone used to interpret provider-local dates. Daylight
saving gaps and repeated hours are tested per adapter. A missing or ambiguous
timezone pauses setup or creates a repair issue; it is never guessed from an
address.

Energy values are non-negative import and return series. Net usage is not used
as a substitute for separate import and return. Monetary values are enabled only
when the provider contract supplies a validated currency and it matches Home
Assistant's configured currency. No automatic currency conversion occurs.

Provider-supplied estimated and corrected intervals retain those markers.
Missing intervals are unknown, not zero. Existing hardened quarantine rules for
large or explicit data revisions remain in the common ledger.

## Entities and user experience

The primary measurements remain Recorder external statistics for Home
Assistant's Energy dashboard. Regular entities provide operational context:

- newest interval;
- data freshness;
- latest, today, seven-day, and month-to-date import;
- matching return values when supported;
- matching monetary values when supported;
- last successful fetch;
- retained and estimated interval counts;
- most recent correction count; and
- historical import progress.

The device page displays the generic product name, selected provider, masked
location label, declared data delay, and supported capabilities. Unsupported
measurements are omitted rather than shown as unavailable placeholders.

## Failure and recovery behavior

Common failures use stable, value-free categories:

- invalid credentials: stop normal retries and start reauthentication;
- unsupported interactive challenge: fail closed and request local action;
- rate limit, server error, or timeout: keep verified data and back off;
- provider schema drift: keep verified data and create a repair issue;
- suspicious correction or retraction: quarantine the candidate data;
- timezone or currency mismatch: keep compatible energy data and suppress only
  invalid dependent measurements;
- ledger corruption or future schema: stop writes and require supported backup
  recovery; and
- stalled backfill: retain current data and raise a warning after the bounded
  health threshold.

An adapter exception is translated to the common error model without including
remote response bodies, account values, addresses, tokens, or exception strings
in user-visible text or default logs.

## Provider qualification

A provider appears in a public release only after all of these are complete:

1. Document the observed or published service contract and data limitations.
2. Fix the HTTPS origins and method/path allowlist.
3. Implement bounded authentication, location discovery, retrieval, and logout.
4. Add synthetic fixtures covering valid, missing, malformed, oversized, and
   hostile responses.
5. Test authentication failures, challenges, redirects, rate limits, timeouts,
   pagination, corrections, timezone changes, currency handling, and logout.
6. Prove that logs, diagnostics, entry titles, device identifiers, entities,
   statistics, CI artifacts, and releases contain no private values.
7. Run the full common contract suite and supported Home Assistant versions.
8. Document the polling delay, historical range, missing features, credential
   storage, and unofficial status.
9. Pass code review and a release-candidate trial with a protected rollback.

Providers may ship at different capability levels. A consumption-only provider
is valid if the UI and metadata accurately omit exports and cost.

## Entergy adapter extraction

The current hardened implementation supplies the starting common code and first
adapter. The extraction moves the fixed Entergy origin, operations, login state
machine, account parsing, weekly-usage parsing, language choice, and Entergy
request limits into `providers/entergy/`.

The following remain common after names are generalized:

- immutable decimal and interval validation;
- atomic canonical ledger and migration checkpoints;
- correction-aware statistics and read-back verification;
- bounded coordinator scheduling and recovery;
- privacy-safe public IDs;
- diagnostics allowlists and repair issues; and
- reproducible CI, release, checksum, and attestation controls.

Tests are split into provider contract tests, Entergy-specific tests, and common
Home Assistant lifecycle/statistics tests. Generic modules must not import the
Entergy adapter directly; the provider registry performs that selection.

## Transition from `ha-entergy`

The published `ha-entergy` release uses the permanent `entergy_mobile` domain in
config entries, device identifiers, ledger keys, repair domains, and Recorder
statistic IDs. Renaming its folder cannot safely migrate those values.

The transition therefore uses these rules:

- do not overwrite `custom_components/entergy_mobile` with generic files;
- publish Energy Usage as a separate `energy_usage` integration;
- keep the old release and audit trail available;
- warn existing users not to run both entries against the same location because
  that duplicates polling and statistics;
- preserve old Recorder history by default;
- provide a separately designed, idempotent migration tool only after its
  cross-domain registry, ledger, rollback, and statistics behavior is tested;
  and
- never edit `.storage`, Recorder SQLite, or Energy dashboard files directly.

The local Beaulab installation has the released `entergy_mobile` files but no
configured utility entry, credentials, ledger, or Energy statistics. Its later
transition can therefore remove the unconfigured old component and install the
verified Energy Usage release through the normal backup, `ha core check`, and
single-restart procedure. That deployment is outside this design phase.

## Testing strategy

The common test matrix covers:

- provider registry and adapter contract enforcement;
- exactly one config entry and one selected location;
- provider/location duplicate and concurrent-flow checks;
- reauthentication identity preservation;
- lifecycle setup, reload, unload, removal, and restart recovery;
- ledger atomicity, pruning, corrections, backfill, and corruption handling;
- statistics IDs, cumulative correction behavior, and Recorder read-back;
- timezone and daylight-saving boundaries;
- currency and capability combinations;
- privacy-safe logs, diagnostics, entities, devices, issues, and artifacts;
- provider schema drift and hostile input bounds;
- release archive contents, checksums, attestations, and dependency policy; and
- current and minimum supported Home Assistant/Python versions.

Every provider runs the same adapter contract suite plus provider-specific
synthetic tests. CI contains no production response, account, address,
credential, token, ledger, database, or Home Assistant runtime file.

## Release and deployment gates

The new repository starts with branch protection, required reviews, secret
scanning, dependency audits, HACS validation, Hassfest, static analysis, current
and minimum Home Assistant tests, tagged immutable archives, checksums, and build
attestations.

Before the first Beaulab deployment:

1. approve the detailed implementation plan;
2. review and merge the exact release commit;
3. publish and verify a signed or attested release archive;
4. create and verify a protected Home Assistant backup;
5. confirm the old Entergy component still has no config entry or data;
6. stage the new component without overwriting the old path;
7. run `ha core check`;
8. schedule one Home Assistant Core restart;
9. add Energy Usage through the trusted local UI;
10. enter utility credentials only in that UI; and
11. validate authentication, location identity, freshness, statistics, bounded
    logs, memory, and rollback evidence.

## Rollback

Before credentials are entered, rollback removes the new component directory,
runs `ha core check`, and restarts Core once. After a config entry or statistics
exist, rollback disables or unloads the entry, restores the exact prior component
tree or supported backup as appropriate, checks Core, and restarts once.

Recorder history is preserved by default. Removing historical statistics is a
separate deliberate action. Rollback never deletes ledger files, `.storage`
entries, Energy dashboard configuration, or Recorder rows manually.

## Future expansion

The one-location rule is a product constraint, not a provider-adapter
limitation. A later reviewed design may allow multiple locations by moving each
location under a shared provider-login config entry or by using Home Assistant
config subentries. Random public location IDs and the provider-neutral adapter
contract are chosen now so that expansion does not rename existing entities or
statistics.

Potential later capabilities include standardized file import for utilities
without a safe automated interface, optional hardware submeter sources, tariffs,
demand measurements, and multiple locations. Each requires its own data and
security design and is not implied by the first release.

## Acceptance criteria

The design is ready for implementation planning when the owner confirms:

- the public name **Energy Usage**;
- the `energy_usage` domain and separate repository;
- one provider and one selected location in version 1;
- Entergy as the first released adapter;
- direct reviewed adapters as the path to broader United States coverage;
- provider-neutral public identifiers and statistics;
- the separate-repository transition and preservation of the Entergy release;
  and
- no deployment or credential entry until the new release passes its gates.
