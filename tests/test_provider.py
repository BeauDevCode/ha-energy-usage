"""Provider registry and common request-boundary contracts."""

from __future__ import annotations

from typing import Any, cast

import aiohttp
import pytest
import voluptuous as vol
from custom_components.energy_usage import provider
from custom_components.energy_usage.errors import UnknownProviderError
from custom_components.energy_usage.models import ProviderDescriptor
from custom_components.energy_usage.provider import ProviderFactory


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
