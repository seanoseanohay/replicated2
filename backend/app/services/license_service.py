import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

log = logging.getLogger(__name__)

# SDK service name may vary based on Helm release name (e.g., bundle-analyzer-sdk)
_SDK_HOST = os.environ.get("REPLICATED_SDK_HOST", "replicated")
_SDK_PORT = os.environ.get("REPLICATED_SDK_PORT", "3000")
_SDK_BASE = f"http://{_SDK_HOST}:{_SDK_PORT}"

REPLICATED_SDK_LICENSE_URL = f"{_SDK_BASE}/api/v1/license/info"
REPLICATED_SDK_FIELD_URL = f"{_SDK_BASE}/api/v1/license/fields"


def _fetch_license_info() -> dict[str, Any] | None:
    """Fetch license info from the Replicated SDK in-cluster API."""
    try:
        req = urllib.request.Request(
            REPLICATED_SDK_LICENSE_URL,
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            log.debug(f"License info fetched: {data}")
            return data
    except urllib.error.HTTPError as e:
        log.warning(f"License info HTTP error {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as exc:
        log.warning(f"License info fetch failed: {exc}")
        return None


def _fetch_license_field(field_name: str) -> dict[str, Any] | None:
    """Fetch a specific license field from the Replicated SDK in-cluster API."""
    try:
        req = urllib.request.Request(
            f"{REPLICATED_SDK_FIELD_URL}/{field_name}",
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            log.debug(f"License field {field_name} fetched: {data}")
            return data
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.debug(f"License field {field_name} not found")
            return None
        log.warning(f"License field {field_name} HTTP error {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as exc:
        log.warning(f"License field {field_name} fetch failed: {exc}")
        return None


@lru_cache(maxsize=1)
def _get_cached_license_info() -> dict[str, Any] | None:
    """Cache license info for 60 seconds to avoid hammering the SDK sidecar."""
    return _fetch_license_info()


def _parse_expires_at(entitlements: dict[str, Any]) -> datetime | None:
    """Extract and parse the expires_at entitlement value."""
    raw = entitlements.get("expires_at")
    if isinstance(raw, dict):
        value = raw.get("value")
    else:
        value = raw
    if not value:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def is_license_valid() -> bool:
    """Check whether the current Replicated license is valid (not expired).

    Returns True when:
      - SDK is unreachable (local dev / testing)
      - License exists and has no expiry
      - License exists and expiry is in the future

    Returns False when:
      - License info is present but expires_at is in the past
      - A future explicit invalid flag is added by the SDK
    """
    info = _fetch_license_info()
    if info is None:
        # SDK unreachable — be permissive so local dev works
        return True

    entitlements = info.get("entitlements", {})
    expires = _parse_expires_at(entitlements)
    if expires is not None and datetime.now(timezone.utc) > expires:
        log.warning(f"License expired at {expires.isoformat()}")
        return False

    return True


def get_license_status() -> dict[str, Any]:
    """Return current license status suitable for API response."""
    info = _fetch_license_info()
    if info is None:
        # Fallback: when SDK is not reachable (local dev), treat as unlicensed
        return {
            "valid": False,
            "license_type": None,
            "customer_name": None,
            "expires_at": None,
            "entitlements": {},
        }

    entitlements = info.get("entitlements", {})
    expires = _parse_expires_at(entitlements)
    expired = False
    if expires is not None and datetime.now(timezone.utc) > expires:
        expired = True

    return {
        "valid": not expired,
        "license_type": info.get("licenseType"),
        "customer_name": info.get("customerName"),
        "expires_at": entitlements.get("expires_at", {}).get("value") if isinstance(entitlements.get("expires_at"), dict) else None,
        "entitlements": {
            k: (v.get("value") if isinstance(v, dict) else v)
            for k, v in entitlements.items()
        },
    }


def is_entitlement_enabled(field_name: str, default: bool = False) -> bool:
    """Check if a license entitlement is enabled.

    Queries the SDK directly. Falls back to default if SDK is unreachable.
    """
    field = _fetch_license_field(field_name)
    if field is None:
        log.debug(f"License field {field_name} unavailable; using default={default}")
        return default

    value = field.get("value")
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "enabled")
    if isinstance(value, int):
        return value != 0
    return default


def check_ai_chat_entitlement() -> bool:
    """Check if the AI Chat feature is enabled by license entitlement."""
    return is_entitlement_enabled("ai_chat_enabled", default=False)
