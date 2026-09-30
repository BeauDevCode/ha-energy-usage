"""Provider registry and common request-boundary contracts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, cast

import aiohttp
import pytest
import voluptuous as vol
from custom_components.energy_usage import provider
from custom_components.energy_usage.errors import UnknownProviderError
from custom_components.energy_usage.models import ProviderDescriptor
from custom_components.energy_usage.provider import (
    IntervalPage,
    IntervalRequest,
    ProviderFactory,
)


@pytest.fixture(autouse=True)
def empty_registry(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(provider, "_PROVIDERS", {})


def factory(key: str, name: str) -> ProviderFactory:
    return ProviderFactory(
        descriptor=ProviderDescriptor(key=key, name=name, country_codes=frozenset({"US"})),
        auth_schema=lambda: vol.Schema({vol.Required("username"): str}),
        create=lambda _session, _auth: cast(Any, object()),
    )


@pytest.mark.parametrize("key", ["", "Entergy", "bad-key", "x" * 33])
def test_provider_descriptor_rejects_invalid_keys(key: str) -> None:
    with pytest.raises(ValueError):
        ProviderDescriptor(key=key, name="Provider", country_codes=frozenset({"US"}))


def test_provider_descriptor_rejects_unsafe_metadata() -> None:
    with pytest.raises(ValueError):
        ProviderDescriptor(key="safe", name="Provider\nSecret", country_codes=frozenset({"US"}))
    with pytest.raises(ValueError):
        ProviderDescriptor(key="safe", name="Provider", country_codes=frozenset({"usa"}))


def test_registry_is_deterministic_and_rejects_duplicates() -> None:
    provider.register_provider(factory("zeta", "Zeta"))
    provider.register_provider(factory("alpha", "Alpha"))
    assert [item.key for item in provider.provider_descriptors()] == ["alpha", "zeta"]
    with pytest.raises(ValueError):
        provider.register_provider(factory("alpha", "Different"))


def test_unknown_provider_fails_without_echoing_untrusted_key() -> None:
    with pytest.raises(UnknownProviderError) as error:
        provider.provider_auth_schema("private-canary")
    assert "private-canary" not in str(error.value)
    assert "private-canary" not in repr(error.value)


def test_factory_schema_and_creation_are_selected_by_key() -> None:
    selected = factory("entergy", "Entergy")
    provider.register_provider(selected)
    assert set(provider.provider_auth_schema("entergy").schema) == {"username"}
    session = cast(aiohttp.ClientSession, object())
    assert provider.create_provider("entergy", session, {"username": "private"}) is not None


def test_provider_bootstrap_registers_released_entergy_adapter() -> None:
    from custom_components.energy_usage import providers

    providers.register_all()
    assert [item.key for item in provider.provider_descriptors()] == ["entergy"]


@pytest.mark.parametrize(
    "values",
    [
        ("", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC), None),
        ("location", datetime(2026, 1, 1), datetime(2026, 1, 2, tzinfo=UTC), None),
        ("location", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2), None),
        (
            "location",
            datetime(2026, 1, 2, tzinfo=UTC),
            datetime(2026, 1, 1, tzinfo=UTC),
            None,
        ),
        ("location", datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 2, tzinfo=UTC), ""),
        (
            "location",
            datetime(2026, 1, 1, tzinfo=UTC),
            datetime(2026, 1, 2, tzinfo=UTC),
            "x" * 257,
        ),
    ],
)
def test_interval_request_rejects_invalid_private_boundaries(values: tuple[Any, ...]) -> None:
    with pytest.raises(ValueError, match="invalid interval request"):
        IntervalRequest(*values)


def test_interval_page_requires_coherent_cursor_and_completion() -> None:
    assert IntervalPage((), next_cursor="page-2", complete=False).next_cursor == "page-2"
    for values in (
        {"next_cursor": "page-2", "complete": True},
        {"next_cursor": "", "complete": False},
        {"next_cursor": "x" * 257, "complete": False},
        {"complete": cast(Any, 1)},
    ):
        with pytest.raises(ValueError, match="invalid interval page"):
            IntervalPage((), **values)

    first = cast(Any, type("Interval", (), {"start": datetime(2026, 1, 2, tzinfo=UTC)})())
    second = cast(
        Any,
        type("Interval", (), {"start": datetime(2026, 1, 1, tzinfo=UTC)})(),
    )
    with pytest.raises(ValueError, match="invalid interval page"):
        IntervalPage((first, second))
