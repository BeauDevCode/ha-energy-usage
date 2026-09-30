# Contributing

Use Python 3.14 and repository-pinned `uv==0.12.19`. Run `uv sync --frozen`; do not resolve or upgrade dependencies merely to execute tests. The current lock targets Home Assistant 2026.9.4, and `requirements/ha-2026.9.3.txt` defines the minimum supported environment.

Before proposing a change, run:

```text
uv run ruff format --check .
uv run ruff check .
uv run mypy --explicit-package-bases custom_components/energy_usage
uv run pytest -q --cov=custom_components.energy_usage --cov-branch --cov-report=json:coverage.json --cov-fail-under=95
uv run python scripts/check_coverage.py coverage.json
```

Repeat pytest and coverage in the minimum environment. Run the dependency audit for both supported Home Assistant versions. CI also runs HACS, Hassfest, CodeQL, release policy, and secret scanning.

Every fixture must be synthetic. Credentials, tokens, private location IDs, addresses, packet captures, databases, ledgers, Home Assistant runtime data, and homelab material must never enter commits, issues, tests, or CI artifacts. New providers require fixed-origin bounded transport, schema validation, capability tests, privacy review, and licensing review. Runtime dependencies, migrations, Recorder behavior, endpoints, action pins, and security controls require explicit review.

A contribution does not imply acceptance, release, support, or a relationship with any utility. See [providers](docs/PROVIDERS.md) and [security reporting](SECURITY.md).
