"""Bootstrap the reviewed Energy Usage provider adapters."""

from ..provider import provider_descriptors, register_provider
from .entergy import ENTERGY_FACTORY


def register_all() -> None:
    """Register every adapter shipped in this exact release."""
    registered = {descriptor.key for descriptor in provider_descriptors()}
    if ENTERGY_FACTORY.descriptor.key not in registered:
        register_provider(ENTERGY_FACTORY)


__all__ = ["register_all"]
