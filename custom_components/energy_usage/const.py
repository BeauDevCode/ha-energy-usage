"""Constants for the Entergy integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "energy_usage"

# Provider-neutral config entry fields.
CONF_PROVIDER_KEY: Final = "provider_key"
CONF_AUTH: Final = "auth"
CONF_PRIVATE_LOCATION_ID: Final = "private_location_id"
CONF_LOCATION_PUBLIC_ID: Final = "location_public_id"
PROVIDER_SCHEMA_VERSION: Final = 1

# Temporary legacy field names used until lifecycle generalization is complete.
CONF_ACCOUNT_ID: Final = "account_id"
CONF_LANGUAGE: Final = "language"
CONF_NO_EXPORT: Final = "confirm_no_export"
CONF_SCAN_INTERVAL_SECONDS: Final = "scan_interval_seconds"

DEFAULT_LANGUAGE: Final = "en"
DEFAULT_APP_VERSION: Final = "3.62.0"
DEFAULT_SCAN_INTERVAL_SECONDS: Final = 14400
MIN_SCAN_INTERVAL_SECONDS: Final = 3600
MAX_SCAN_INTERVAL_SECONDS: Final = 86400

API_ORIGIN: Final = "https://prod.entergy.mindgrb.io"
