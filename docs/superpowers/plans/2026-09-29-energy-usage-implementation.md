# Energy Usage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and release a provider-neutral Home Assistant integration named Energy Usage for one United States utility location, with Entergy as its first provider adapter, then replace Beaulab's unconfigured Entergy-only component through a protected deployment.

**Architecture:** Create a new independent `ha-energy-usage` repository and permanent `energy_usage` domain. Extract Entergy authentication and response parsing behind a provider protocol while retaining the hardened common ledger, corrections, external statistics, privacy, and release controls. Version 1 permits one config entry and one selected location; future providers implement the same adapter contract without changing public identifiers.

**Tech Stack:** Python 3.14, Home Assistant 2026.9.3 and 2026.9.4, aiohttp, voluptuous, pytest, Ruff, mypy, uv, HACS, Hassfest, GitHub Actions, GitHub artifact attestations.

**Spec:** `docs/superpowers/specs/2026-09-29-energy-usage-integration-design.md`

## Global Constraints

- Public product name is **Energy Usage**; repository is `BeauDevCode/ha-energy-usage`; Home Assistant domain is `energy_usage`.
- Version 1 permits exactly one configured provider account and exactly one selected service location.
- Entergy is the only provider advertised in the first release; broader United States coverage is a long-term adapter roadmap.
- Home Assistant support remains exactly 2026.9.3 and 2026.9.4 on Python 3.14 for the first release candidate.
- No runtime dependency is added without a separate security and licensing review.
- Credentials are accepted only through the trusted local Home Assistant config flow and may never enter chat, commands, fixtures, Git, diagnostics, logs, or workspace documents.
- Provider account IDs, addresses, usernames, and payloads never appear in public identifiers, titles, statistics IDs, CI artifacts, or default logs.
- External statistics use `energy_usage:<location_public_id>_<metric>` and preserve correction-aware cumulative behavior.
- Missing values remain unknown; the integration never invents zero usage, currency, cost, exports, tariff data, or timezone.
- Provider challenges, MFA, CAPTCHA, consent, unsafe redirects, schema drift, and suspicious revisions fail closed.
- The existing `ha-entergy` release, checksums, attestations, license, and attribution remain available.
- Never overwrite `custom_components/entergy_mobile` with Energy Usage files or manually edit `.storage`, Recorder, or Energy dashboard storage.
- No Beaulab credential entry or live deployment occurs before the reviewed release archive, protected backup, checksum, attestation, and `ha core check` gates pass.

## Review Focus

- A login returning zero, one, or several locations must require one valid selection and reject a stale or forged selection; Task 4 adds these flow tests.
- Reauthentication that succeeds but no longer exposes the configured location must preserve the existing credentials and public identity; Task 4 adds this regression test.
- A provider claiming unsupported currency, timezone, export, or cost capability must not create misleading statistics or sensors; Tasks 2, 6, and 7 add contract tests.
- A restart between ledger persistence and Recorder confirmation must requeue the exact correction suffix without duplicate totals; Task 6 retains and generalizes this recovery test.
- Rate limits, oversized payloads, hostile redirects, schema drift, and untrusted exception text must keep last-known-good data without leaking secrets; Tasks 3 and 6 add transport and coordinator tests.

---

## Planned file structure

The new repository is created at `/Users/christ/Documents/ChatGPT/ha-energy-usage` with these responsibilities:

```text
custom_components/energy_usage/
  __init__.py                 # Config-entry lifecycle and migrations
  config_flow.py              # Provider/auth/location setup and options
  const.py                    # Generic domain and common limits
  coordinator.py              # Generic polling, backfill, and orchestration
  diagnostics.py              # Allowlisted generic diagnostics
  entity.py                   # Generic device identity
  errors.py                   # Value-free common error categories
  issues.py                   # Generic repair issues
  ledger.py                   # Atomic provider-neutral interval ledger
  models.py                   # Common immutable normalized values
  provider.py                 # Adapter protocols, registry, request budget
  sensor.py                   # Generic summaries and health entities
  statistics.py               # External Recorder statistics
  providers/
    __init__.py               # Provider package marker
    entergy/
      __init__.py             # Adapter descriptor/factory
      api.py                  # Fixed-origin Entergy transport
      const.py                # Entergy-only endpoints and limits
      parser.py               # Entergy response normalization
  brand/icon.png
  manifest.json
  strings.json
  translations/en.json
tests/
  providers/entergy/          # Entergy transport/parser fixtures and tests
  test_provider.py            # Common adapter contract and registry tests
  test_config_flow.py         # One-entry/one-location/reauth tests
  test_*.py                   # Generalized ledger, coordinator, HA, and policy tests
```

CI, release, privacy, security, and contributor files are carried into the new repository only after their names, paths, domains, versions, and release checks are rewritten and tested.

### Task 1: Bootstrap the independent repository and permanent identity

**Files:**
- Create: `/Users/christ/Documents/ChatGPT/ha-energy-usage/.gitignore`
- Create: `/Users/christ/Documents/ChatGPT/ha-energy-usage/LICENSE`
- Create: `/Users/christ/Documents/ChatGPT/ha-energy-usage/NOTICE.md`
- Create: `/Users/christ/Documents/ChatGPT/ha-energy-usage/pyproject.toml`
- Create: `/Users/christ/Documents/ChatGPT/ha-energy-usage/uv.lock`
- Create: `/Users/christ/Documents/ChatGPT/ha-energy-usage/hacs.json`
- Create: `/Users/christ/Documents/ChatGPT/ha-energy-usage/custom_components/energy_usage/manifest.json`
- Create: `/Users/christ/Documents/ChatGPT/ha-energy-usage/custom_components/energy_usage/const.py`
- Create: `/Users/christ/Documents/ChatGPT/ha-energy-usage/tests/test_repository_policy.py`

**Interfaces:**
- Consumes: The exact reviewed source tree at `ha-entergy@06a89da50c538ffc96d3767ee26165d1a13acedb` and the approved design.
- Produces: A fresh Git repository whose import root is `custom_components.energy_usage`, `DOMAIN == "energy_usage"`, manifest version `0.1.0-rc.1`, and supported test environments for Home Assistant 2026.9.3/2026.9.4.

- [ ] **Step 1: Create the independent repository without copying Git metadata**

Create `/Users/christ/Documents/ChatGPT/ha-energy-usage`, initialize Git with branch `main`, copy only reviewed source-controlled files needed as a starting point, and preserve the MIT license and attribution. Exclude `.git`, virtual environments, caches, `dist`, credentials, databases, ledgers, Home Assistant runtime files, and production payloads.

- [ ] **Step 2: Write failing repository identity tests**

Add tests asserting:

```python
assert manifest["domain"] == "energy_usage"
assert manifest["name"] == "Energy Usage"
assert manifest["version"] == "0.1.0-rc.1"
assert manifest["single_config_entry"] is True
assert not (ROOT / "custom_components/entergy_mobile").exists()
assert "BeauDevCode/ha-energy-usage" in manifest["documentation"]
```

Also assert the package imports use `custom_components.energy_usage`, the archive tree is only `custom_components/energy_usage/`, and the NOTICE credits the original project and hardened fork without implying utility endorsement.

- [ ] **Step 3: Run the identity test and verify it fails**

Run: `uv run pytest -q tests/test_repository_policy.py`

Expected: FAIL on the old domain, package path, repository URL, version, or missing one-entry flag.

- [ ] **Step 4: Implement the generic repository identity**

Set `DOMAIN: Final = "energy_usage"`; use display name `Energy Usage`; set version `0.1.0-rc.1`; set `integration_type: "service"`, `iot_class: "cloud_polling"`, `config_flow: true`, and `single_config_entry: true`. Rewrite package paths, quality configuration, HACS metadata, archive naming, and safe attribution.

- [ ] **Step 5: Install locked development environments and run identity tests**

Run: `uv sync --frozen --all-extras && uv run pytest -q tests/test_repository_policy.py`

Expected: repository-policy tests PASS.

- [ ] **Step 6: Commit**

```bash
git add .
git commit -m "chore: bootstrap Energy Usage integration"
```

### Task 2: Define provider-neutral models and the adapter contract

**Files:**
- Create: `custom_components/energy_usage/provider.py`
- Modify: `custom_components/energy_usage/models.py`
- Modify: `custom_components/energy_usage/errors.py`
- Create: `custom_components/energy_usage/providers/__init__.py`
- Test: `tests/test_provider.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Consumes: `DOMAIN`, common polling bounds, aiohttp session ownership, and the existing immutable interval/ledger model behavior.
- Produces: `ProviderCapabilities`, `ProviderLocation`, `ProviderDescriptor`, `IntervalRequest`, `IntervalPage`, `RequestBudget`, `EnergyProvider`, `ProviderFactory`, `register_provider()`, `provider_descriptors()`, and `create_provider()`.

- [ ] **Step 1: Write failing common model tests**

Test that `ProviderLocation` requires a non-empty private ID, masked label, and validated optional timezone; `ProviderCapabilities` explicitly declares import, return, cost, compensation, currency, interval duration, publication delay, historical range, and minimum poll interval; invalid or contradictory values raise `ValueError`.

- [ ] **Step 2: Write failing provider registry tests**

Test that provider keys match `[a-z0-9_]{1,32}`, duplicate keys fail, descriptors expose only safe metadata, an unknown key raises `UnknownProviderError`, and registry order is deterministic.

- [ ] **Step 3: Run the new tests and verify they fail**

Run: `uv run pytest -q tests/test_provider.py tests/test_models.py`

Expected: FAIL because the generic provider types and registry do not exist.

- [ ] **Step 4: Implement the common types and protocol**

Define these stable signatures:

```python
@dataclass(frozen=True, slots=True)
class ProviderCapabilities: ...

@dataclass(frozen=True, slots=True, repr=False)
class ProviderLocation: ...

@dataclass(frozen=True, slots=True)
class ProviderDescriptor:
    key: str
    name: str
    country_codes: frozenset[str]

class EnergyProvider(Protocol):
    descriptor: ProviderDescriptor
    capabilities: ProviderCapabilities
    async def authenticate(self, budget: RequestBudget) -> None: ...
    async def async_list_locations(self, budget: RequestBudget) -> tuple[ProviderLocation, ...]: ...
    async def async_confirm_location(self, private_location_id: str, budget: RequestBudget) -> ProviderLocation: ...
    async def async_fetch_intervals(self, request: IntervalRequest, budget: RequestBudget) -> IntervalPage: ...
    async def async_logout(self, budget: RequestBudget) -> None: ...

@dataclass(frozen=True, slots=True)
class ProviderFactory:
    descriptor: ProviderDescriptor
    auth_schema: Callable[[], vol.Schema]
    create: Callable[[ClientSession, Mapping[str, Any]], EnergyProvider]

def register_provider(factory: ProviderFactory) -> None: ...
def provider_descriptors() -> tuple[ProviderDescriptor, ...]: ...
def provider_auth_schema(key: str) -> vol.Schema: ...
def create_provider(key: str, session: ClientSession, auth: Mapping[str, Any]) -> EnergyProvider: ...
```

Move the request budget and value-free error categories into the common layer. Rename Entergy-specific common exception classes while keeping their no-secret string and repr behavior.

- [ ] **Step 5: Run the common tests**

Run: `uv run pytest -q tests/test_provider.py tests/test_models.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add custom_components/energy_usage/provider.py custom_components/energy_usage/models.py custom_components/energy_usage/errors.py custom_components/energy_usage/providers tests/test_provider.py tests/test_models.py
git commit -m "feat: define energy provider contract"
```

### Task 3: Extract and register the Entergy provider adapter

**Files:**
- Create: `custom_components/energy_usage/providers/entergy/__init__.py`
- Create: `custom_components/energy_usage/providers/entergy/api.py`
- Create: `custom_components/energy_usage/providers/entergy/const.py`
- Create: `custom_components/energy_usage/providers/entergy/parser.py`
- Remove: `custom_components/energy_usage/api.py`
- Remove: `custom_components/energy_usage/parser.py`
- Create: `tests/providers/entergy/test_api.py`
- Create: `tests/providers/entergy/test_parser.py`
- Create: `tests/providers/entergy/test_contract.py`

**Interfaces:**
- Consumes: `EnergyProvider`, common normalized models, request budget, and value-free errors from Task 2.
- Produces: `ENTERGY_DESCRIPTOR`, `EntergyProvider`, and a registered `entergy` factory implementing the complete common contract.

- [ ] **Step 1: Move existing synthetic Entergy tests and make imports fail**

Move the current API/parser tests to `tests/providers/entergy/`, change imports to the proposed adapter package, and add assertions that descriptor key/name/country are `entergy`, `Entergy`, and `{"US"}`.

- [ ] **Step 2: Add hostile transport and capability tests**

Pin tests for oversized bodies, invalid content types, unsafe redirects, control characters in headers, invalid retry values, pagination limits, login challenges, zero/multiple locations, timezone omission, currency omission, and exception text containing a synthetic secret. Assert the exception presented to common code contains no secret or payload.

- [ ] **Step 3: Run adapter tests and verify they fail**

Run: `uv run pytest -q tests/providers/entergy`

Expected: FAIL because the provider package and contract implementation do not exist.

- [ ] **Step 4: Implement `EntergyProvider` by extracting reviewed code**

Keep the fixed origin, closed operation allowlist, bounded aiohttp transport, login/challenge state machine, account parsing, weekly usage parsing, and logout. Translate Entergy account objects to `ProviderLocation` and usage responses to `IntervalPage`. Do not change existing security or arithmetic bounds during the move.

- [ ] **Step 5: Register the adapter without importing it from generic runtime modules**

`providers/entergy/__init__.py` registers the factory with the provider registry. Only the provider bootstrap imports adapter packages; coordinator, ledger, sensors, and statistics depend on the protocol.

- [ ] **Step 6: Run adapter and common contract tests**

Run: `uv run pytest -q tests/providers/entergy tests/test_provider.py tests/test_models.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add custom_components/energy_usage/providers custom_components/energy_usage/provider.py tests/providers tests/test_provider.py
git rm custom_components/energy_usage/api.py custom_components/energy_usage/parser.py
git commit -m "feat: add Entergy provider adapter"
```

### Task 4: Implement the one-provider, one-location config flow

**Files:**
- Modify: `custom_components/energy_usage/config_flow.py`
- Modify: `custom_components/energy_usage/const.py`
- Modify: `custom_components/energy_usage/strings.json`
- Modify: `custom_components/energy_usage/translations/en.json`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Consumes: provider descriptors/factory, `ProviderLocation`, provider auth schema, and common error categories.
- Produces: one config entry containing `provider_key`, provider-owned `auth`, `private_location_id`, random `location_public_id`, timezone, capability version, and ledger marker.

- [ ] **Step 1: Write failing provider-selection and one-entry tests**

Test that the first step lists released providers, currently only `entergy`; an existing entry aborts with `single_instance_allowed`; unknown or forged provider keys abort; and no credentials are accepted before a valid provider is selected.

- [ ] **Step 2: Write failing location-selection tests**

Cover zero, one, and multiple returned locations. Even one location requires a review/confirmation step. A stale index, forged private ID, duplicate selection, newline-bearing label, or unreturned location aborts without saving credentials. Exactly one selected location is stored.

- [ ] **Step 3: Write failing reauthentication identity tests**

Assert valid new credentials update only `auth`; `provider_key`, `private_location_id`, `location_public_id`, title, and statistics identity remain unchanged. If the login no longer exposes the configured location, abort and preserve all old entry data.

- [ ] **Step 4: Run config-flow tests and verify they fail**

Run: `uv run pytest -q tests/test_config_flow.py`

Expected: FAIL on old Entergy-only steps and field names.

- [ ] **Step 5: Implement generic setup and reauthentication**

Use these public constants:

```python
CONF_PROVIDER_KEY = "provider_key"
CONF_AUTH = "auth"
CONF_PRIVATE_LOCATION_ID = "private_location_id"
CONF_LOCATION_PUBLIC_ID = "location_public_id"
```

Provider adapters supply their credential schema and masked location labels. The flow allocates the public ID only after the location is confirmed. Provider auth values remain repr-safe and are never logged.

- [ ] **Step 6: Keep generic options bounded by provider minimums**

The options flow presents the maximum of the common minimum and selected provider minimum, clamps legacy values, and triggers exactly one supported reload.

- [ ] **Step 7: Run config-flow tests**

Run: `uv run pytest -q tests/test_config_flow.py`

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add custom_components/energy_usage/config_flow.py custom_components/energy_usage/const.py custom_components/energy_usage/strings.json custom_components/energy_usage/translations/en.json tests/test_config_flow.py
git commit -m "feat: configure one energy service location"
```

### Task 5: Generalize lifecycle, identity, and private ledger storage

**Files:**
- Modify: `custom_components/energy_usage/__init__.py`
- Modify: `custom_components/energy_usage/entity.py`
- Modify: `custom_components/energy_usage/ledger.py`
- Test: `tests/test_init.py`
- Test: `tests/test_ledger.py`
- Test: `tests/test_migration.py`

**Interfaces:**
- Consumes: generic config-entry fields from Task 4 and the provider factory from Task 2.
- Produces: runtime entry state, `(DOMAIN, location_public_id)` device identity, `energy_usage.ledger_<location_public_id>` storage, version-1 entry recovery, and atomic ledger guarantees.

- [ ] **Step 1: Rewrite existing tests to the generic identity and verify failure**

Replace `entergy_mobile` keys, Entergy titles, account IDs, and old package imports with generic provider/location fixtures. Assert private IDs never appear in device identifiers, unique IDs, store keys, issue IDs, names, aliases, logs, or diagnostics.

Run: `uv run pytest -q tests/test_init.py tests/test_ledger.py tests/test_migration.py`

Expected: FAIL on old domain, fields, client construction, or migration assumptions.

- [ ] **Step 2: Implement generic lifecycle setup and cleanup**

Create the selected provider from the entry, initialize the generic ledger, create the coordinator, forward sensor setup, and register unload/update listeners. Failure cleanup must log out and cancel owned tasks without exposing provider errors.

- [ ] **Step 3: Preserve ledger atomicity under the new keys**

Keep the existing immutable candidate, atomic save, read-back verification, corrupt-artifact detection, pending-statistics marker, pruning, correction, baseline, and shutdown behavior. Add provider key and provider schema version to the private ledger header and reject mismatches before mutation.

- [ ] **Step 4: Replace legacy cross-domain migration with a clean v1 recovery path**

New entries start at config-entry version 1. Do not import `entergy_mobile` stores or edit its registries. Retain durable same-domain migration primitives for future Energy Usage versions and test that malformed/future checkpoints fail closed.

- [ ] **Step 5: Run lifecycle and ledger tests**

Run: `uv run pytest -q tests/test_init.py tests/test_ledger.py tests/test_migration.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add custom_components/energy_usage/__init__.py custom_components/energy_usage/entity.py custom_components/energy_usage/ledger.py tests/test_init.py tests/test_ledger.py tests/test_migration.py
git commit -m "refactor: generalize energy lifecycle and ledger"
```

### Task 6: Drive polling and Recorder statistics through provider capabilities

**Files:**
- Modify: `custom_components/energy_usage/coordinator.py`
- Modify: `custom_components/energy_usage/statistics.py`
- Test: `tests/test_coordinator.py`
- Test: `tests/test_statistics.py`

**Interfaces:**
- Consumes: `EnergyProvider.async_fetch_intervals()`, provider capabilities, normalized intervals, config entry, and generic ledger.
- Produces: bounded reconciliation/backfill scheduling and external statistics IDs `energy_usage:<location_public_id>_{consumption,return,cost,compensation}`.

- [ ] **Step 1: Write failing capability-driven coordinator tests**

Test consumption-only, import/return, import/cost, full capability, unsupported currency, missing timezone, provider minimum poll interval, rate limit, schema drift, and stale-data behavior. Assert unsupported measurements are absent rather than zero.

- [ ] **Step 2: Write failing restart and correction statistics tests**

Retain same-timestamp correction, cumulative suffix rewrite, pending-marker recovery, read-back verification, restart between save/Recorder confirmation, and no-duplicate-total assertions under the new domain and IDs.

- [ ] **Step 3: Run coordinator/statistics tests and verify they fail**

Run: `uv run pytest -q tests/test_coordinator.py tests/test_statistics.py`

Expected: FAIL on direct Entergy methods, hard-coded USD behavior, or old IDs.

- [ ] **Step 4: Implement adapter-driven scheduling**

Replace Entergy method calls with `async_fetch_intervals(IntervalRequest, RequestBudget)`. Clamp polling/backfill to both common and adapter limits. Translate adapter errors into existing auth, transient, schema, rate-limit, and quarantine paths while retaining last-known-good state.

- [ ] **Step 5: Implement capability-driven statistics**

Change `statistic_ids(location_public_id)` to the new source/domain. Queue return, cost, and compensation only when declared and validated. Require source currency to match Home Assistant currency; do not hard-code USD in common logic.

- [ ] **Step 6: Run coordinator/statistics tests**

Run: `uv run pytest -q tests/test_coordinator.py tests/test_statistics.py`

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add custom_components/energy_usage/coordinator.py custom_components/energy_usage/statistics.py tests/test_coordinator.py tests/test_statistics.py
git commit -m "feat: import provider-neutral energy statistics"
```

### Task 7: Generalize sensors, diagnostics, and repair issues

**Files:**
- Modify: `custom_components/energy_usage/sensor.py`
- Modify: `custom_components/energy_usage/diagnostics.py`
- Modify: `custom_components/energy_usage/issues.py`
- Modify: `custom_components/energy_usage/strings.json`
- Modify: `custom_components/energy_usage/translations/en.json`
- Test: `tests/test_sensor.py`
- Test: `tests/test_diagnostics.py`

**Interfaces:**
- Consumes: coordinator snapshot, provider descriptor/capabilities, public location ID, and common issue categories.
- Produces: generic Energy Usage device/entities, capability-filtered sensor descriptions, allowlisted diagnostics, and provider-neutral repair copy.

- [ ] **Step 1: Write failing sensor capability tests**

Assert consumption summaries always exist; return, cost, and compensation summaries exist only when supported; no entity has an account ID/address/username in its ID, name, attributes, or device data; entity unique IDs remain `<public_id>_<metric>`.

- [ ] **Step 2: Write failing diagnostic and issue privacy tests**

Assert diagnostics allow only provider key, safe capability booleans, public ID, timing, counts, backoff category, and schema versions. Inject synthetic secrets into auth, errors, private IDs, payloads, nicknames, and addresses and assert none appear recursively.

- [ ] **Step 3: Run sensor/diagnostic tests and verify they fail**

Run: `uv run pytest -q tests/test_sensor.py tests/test_diagnostics.py`

Expected: FAIL on hard-coded Entergy names/currency or old diagnostics fields.

- [ ] **Step 4: Implement capability-filtered entities and generic copy**

Build descriptions from provider capabilities, use generic device manufacturer `Energy Usage`, show the provider as a safe model/detail, and preserve masked location labels only where the design permits. Replace Entergy-specific repair text with utility/provider-neutral wording.

- [ ] **Step 5: Run sensor/diagnostic tests**

Run: `uv run pytest -q tests/test_sensor.py tests/test_diagnostics.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add custom_components/energy_usage/sensor.py custom_components/energy_usage/diagnostics.py custom_components/energy_usage/issues.py custom_components/energy_usage/strings.json custom_components/energy_usage/translations/en.json tests/test_sensor.py tests/test_diagnostics.py
git commit -m "feat: expose generic energy health entities"
```

### Task 8: Publish product, privacy, provider, installation, and rollback documentation

**Files:**
- Create: `README.md`
- Create: `SECURITY.md`
- Create: `CONTRIBUTING.md`
- Create: `docs/PRIVACY.md`
- Create: `docs/PROVIDERS.md`
- Create: `docs/INSTALL.md`
- Create: `docs/ROLLBACK.md`
- Create: `CHANGELOG.md`
- Create: `assets/energy-usage-icon.svg`
- Modify: `custom_components/energy_usage/brand/icon.png`
- Test: `tests/test_repository_policy.py`

**Interfaces:**
- Consumes: final product behavior and release identity from Tasks 1-7.
- Produces: accurate public documentation and generic branding for `0.1.0-rc.1`.

- [ ] **Step 1: Add failing documentation policy tests**

Assert required docs contain the unofficial notice, one-location limit, delayed/not-bill-grade warning, credential-storage disclosure, Entergy-only first release, provider qualification policy, exact archive paths, backup/check/restart steps, old-domain warning, and no claim of universal current coverage.

- [ ] **Step 2: Run repository policy tests and verify failure**

Run: `uv run pytest -q tests/test_repository_policy.py`

Expected: FAIL on stale Entergy-only names, URLs, paths, or missing generic documentation.

- [ ] **Step 3: Write generic documentation and provider matrix**

`docs/PROVIDERS.md` lists only Entergy as available, its observed delay/capabilities, and a reviewed-adapter roadmap without dates or unsupported promises. Installation and rollback never tell users to overwrite the `entergy_mobile` directory or delete Recorder history.

- [ ] **Step 4: Produce generic icon assets**

Use a project-owned electricity/usage mark with no utility wordmark. Verify PNG dimensions, format, transparency, and SVG/PNG consistency using repository tests.

- [ ] **Step 5: Run repository policy tests**

Run: `uv run pytest -q tests/test_repository_policy.py`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add README.md SECURITY.md CONTRIBUTING.md CHANGELOG.md docs assets custom_components/energy_usage/brand tests/test_repository_policy.py
git commit -m "docs: publish Energy Usage product guidance"
```

### Task 9: Rebuild CI, release, and supply-chain controls

**Files:**
- Create: `.github/CODEOWNERS`
- Create: `.github/PULL_REQUEST_TEMPLATE.md`
- Create: `.github/dependabot.yml`
- Create: `.github/workflows/ci.yml`
- Create: `.github/workflows/codeql.yml`
- Create: `.github/workflows/release.yml`
- Create: `.github/workflows/secret-scan.yml`
- Modify: `scripts/check_coverage.py`
- Modify: `scripts/check_dependency_audit.py`
- Modify: `tests/test_dependency_audit.py`
- Modify: `tests/test_repository_policy.py`

**Interfaces:**
- Consumes: locked environments and final package tree.
- Produces: deterministic tests, HACS/Hassfest checks, dependency/security policy, exact release archives, checksum, and GitHub attestation for `ha-energy-usage-0.1.0-rc.1.zip`.

- [ ] **Step 1: Write failing workflow/release policy tests**

Assert pinned action SHAs, least-privilege permissions, current/minimum HA jobs, Ruff, mypy, coverage thresholds, HACS, Hassfest, secret scan, CodeQL, dependency exception expiry, exact archive root, embedded version/commit, checksum, and attestation commands.

- [ ] **Step 2: Run policy tests and verify failure**

Run: `uv run pytest -q tests/test_repository_policy.py tests/test_dependency_audit.py`

Expected: FAIL on old repository/archive/domain/version references.

- [ ] **Step 3: Rewrite workflows and scripts**

Carry forward reviewed pinned actions and temporary dependency exceptions only after verifying they still apply to the fresh lockfile and have not expired. Release workflow accepts only a matching protected tag and packages only `custom_components/energy_usage/`.

- [ ] **Step 4: Run all local quality gates**

Run:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy custom_components/energy_usage
uv run pytest -q
```

Expected: all commands exit 0 and the complete suite reports zero failures.

- [ ] **Step 5: Build and inspect the release archive locally**

Build the archive with the release script, list every path, verify the embedded manifest version/domain, compute SHA-256, and run the local secret scanner. Expected: only `custom_components/energy_usage/` is present and no secret finding is unexplained.

- [ ] **Step 6: Commit**

```bash
git add .github scripts tests pyproject.toml uv.lock requirements
git commit -m "ci: secure Energy Usage releases"
```

### Task 10: Review the full implementation and create the public repository

**Files:**
- Review: all files in `/Users/christ/Documents/ChatGPT/ha-energy-usage`
- Create remotely: `https://github.com/BeauDevCode/ha-energy-usage`

**Interfaces:**
- Consumes: Tasks 1-9 with a clean local history and reproducible archive.
- Produces: reviewed public repository, protected `main`, and an implementation pull request or reviewed initial-main commit according to GitHub's empty-repository constraints.

- [ ] **Step 1: Run the full supported-version matrix locally**

Run the repository's current and minimum Home Assistant environment commands, full tests, Ruff, mypy, dependency audit, HACS validation, Hassfest, archive inspection, and secret scan. Record exact counts and hashes.

- [ ] **Step 2: Perform a whole-branch security and privacy review**

Review the complete diff against the approved design. Search for credentials, private identifiers, hard-coded production payloads, stale `entergy_mobile` public identity, unrestricted URLs, unbounded JSON/numbers, unsafe logging, missing cleanup, and unsupported coverage claims. Fix findings with test-first commits.

- [ ] **Step 3: Create the public GitHub repository**

Create `BeauDevCode/ha-energy-usage` as a public repository with issues enabled and no generated README/license that would overwrite the reviewed tree. Push a feature branch first. Configure branch protection and required checks before merging to `main` when GitHub permits.

- [ ] **Step 4: Open and attach the implementation pull request**

The PR describes the one-location product, Entergy adapter, security model, provider roadmap, test matrix, archive verification, and explicit non-deployment status. Attach the PR to the current Codex task.

- [ ] **Step 5: Wait for hosted checks and review exact results**

Require every configured job to pass at the exact head commit. Do not merge on a pending, skipped, neutral, or unexplained dependency/security result.

- [ ] **Step 6: Merge only the reviewed exact commit**

After checks and review, merge through GitHub, record the merge commit, and verify local/remote `main` agreement.

### Task 11: Publish the first release candidate and transition the old repository

**Files:**
- Modify in old repo: `README.md`
- Modify in old repo: `docs/INSTALL.md`
- Modify in old repo: `CHANGELOG.md`

**Interfaces:**
- Consumes: merged, protected new-repository commit and passing release workflow.
- Produces: attested `v0.1.0-rc.1` release plus an accurate transition notice on `ha-entergy`.

- [ ] **Step 1: Tag and run the exact release workflow**

Create protected tag `v0.1.0-rc.1` at the reviewed merge commit. Dispatch the release workflow and require the package-and-attest job to succeed.

- [ ] **Step 2: Verify published assets independently**

Download the archive and checksum from the release, run `sha256sum --check`, run `gh attestation verify --repo BeauDevCode/ha-energy-usage`, inspect archive paths, and verify the embedded commit/domain/version.

- [ ] **Step 3: Correct the old repository's status and add a transition notice**

Through a separate reviewed PR, state that `ha-entergy` has a published RC, identify Energy Usage as the successor, preserve all old assets/history, warn against simultaneous polling, and explain that automatic cross-domain data migration is not yet available. Do not archive the repository until the new release is verified.

- [ ] **Step 4: Test and commit the old-repository transition**

Run the old repository's documentation/repository policy tests, then commit only the reviewed transition files:

```bash
git add README.md docs/INSTALL.md CHANGELOG.md
git commit -m "docs: direct users to Energy Usage successor"
```

Push a feature branch, open a PR, require hosted checks, and merge only the reviewed exact commit.

- [ ] **Step 5: Verify both public repositories**

Confirm links, releases, notices, checksums, licenses, security contacts, and installation paths. Search both public histories and current trees for secrets.

### Task 12: Deploy the verified release to Beaulab and hand off local sign-in

**Files:**
- Update: `/Users/christ/Documents/ChatGPT/beaulab-workspace/docs/INVENTORY.md`
- Update: `/Users/christ/Documents/ChatGPT/beaulab-workspace/docs/STATE.md`
- Update: `/Users/christ/Documents/ChatGPT/beaulab-workspace/docs/CHANGELOG.md`
- Update: `/Users/christ/Documents/ChatGPT/beaulab-workspace/plans/NEXT.md`
- Create: `/Users/christ/Documents/ChatGPT/beaulab-workspace/docs/ENERGY-USAGE-DEPLOYMENT-2026-09-29.md`

**Interfaces:**
- Consumes: verified release URL, SHA-256, attestation, protected backup, working SSH access, and confirmed absence of an `entergy_mobile` config entry.
- Produces: installed but user-authenticated Energy Usage integration, validated one-location data/statistics, exact rollback evidence, and current workspace records.

- [ ] **Step 1: Repeat live preflight without making changes**

Confirm Home Assistant/Core/Python versions, free disk, host RAM, thin-pool data/metadata, existing component directories, config entries, Energy sources, bounded logs, and current backup health. Stop if an Entergy config entry, ledger, statistics, or unrelated `energy_usage` owner now exists.

- [ ] **Step 2: Create and verify a protected Home Assistant backup**

Create a supported full backup with database included. Store any recovery key only in the existing protected Mac backup directory with 0700 directory and 0600 file permissions; never print it or place it in the workspace.

- [ ] **Step 3: Preserve exact rollback trees and metadata**

Save root-only hashes and an archive of the current `entergy_mobile` directory and any prior `energy_usage` directory. Record versions, ownership, and paths without secrets.

- [ ] **Step 4: Remove only the unconfigured legacy component and stage Energy Usage**

Verify again that no legacy config entry/data exists. Remove only `/config/custom_components/entergy_mobile/`, extract the verified release to `/config/custom_components/energy_usage/`, set the existing Home Assistant file ownership convention, and verify the staged manifest/tree/hash.

- [ ] **Step 5: Validate and activate with one planned restart**

Run `ha core check`; on failure restore only the component trees and stop. On success, restart Home Assistant Core once, wait for HTTP 200 and healthy Core status, and review a bounded startup log for component errors or secret leakage.

- [ ] **Step 6: Hand off the trusted local config flow**

Open Home Assistant through the existing SSH tunnel, select Energy Usage, select Entergy, and hand the credential fields to the user. The user enters credentials privately. Never request, type, copy, read, or store them through chat or tools.

- [ ] **Step 7: Validate the single location and initial import**

After user submission, verify one config entry, masked location identity, successful authentication, newest interval, fetch time, freshness, provider capabilities, Energy statistics, bounded logs, memory, coordinator health, and backfill progress. Do not claim the utility bill or full 370-day backfill is verified immediately.

- [ ] **Step 8: Document deployment and rollback evidence**

Record the release/tag/commit/hash/attestation, backup slug, protected recovery-key path, component rollback path, one restart, validation results, remaining unknowns, and exact rollback commands without credentials or private account data.

- [ ] **Step 9: Commit the homelab workspace checkpoint**

Review and stage only secret-free relevant homelab documentation. Run `git diff --check` and the workspace secret scan, preserve unrelated dirty changes, and commit with the existing Git identity. Do not push unrelated workspace history.

## Final verification

- [ ] Run the complete new-repository test and quality matrix at the released commit.
- [ ] Verify the release archive checksum and GitHub attestation after downloading the public assets.
- [ ] Confirm the old repository transition notice preserves attribution and does not claim automatic migration.
- [ ] Confirm Beaulab runs exactly one of the two integrations for the selected location.
- [ ] Confirm the Home Assistant dashboard remains unchanged unless the user separately authorizes Energy dashboard configuration.
- [ ] Confirm credentials and private utility data are absent from chat, shell history, repositories, workspace docs, logs, diagnostics, and release artifacts.
- [ ] Confirm rollback artifacts and protected backup recovery information are available and access-restricted.
