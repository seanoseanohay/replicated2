import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

log = logging.getLogger(__name__)

# SDK service name may vary based on Helm release name (e.g., bundle-analyzer-sdk)
_SDK_HOST = os.environ.get("REPLICATED_SDK_HOST", "replicated")
_SDK_PORT = os.environ.get("REPLICATED_SDK_PORT", "3000")
_SDK_BASE = f"http://{_SDK_HOST}:{_SDK_PORT}"

REPLICATED_SDK_APP_INFO_URL = f"{_SDK_BASE}/api/v1/app/info"
REPLICATED_SDK_UPDATES_URL = f"{_SDK_BASE}/api/v1/app/updates"

# Simple in-memory cache: (cached_at, data)
_cache: dict[str, Any] | None = None
_cache_time: datetime | None = None
CACHE_TTL_SECONDS = 300  # 5 minutes


def _fetch_app_info() -> dict[str, Any] | None:
    """Fetch current app info from the Replicated SDK."""
    try:
        req = urllib.request.Request(
            REPLICATED_SDK_APP_INFO_URL,
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            log.debug(f"App info fetched: {data}")
            return data
    except urllib.error.HTTPError as e:
        log.warning(f"App info HTTP error {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as exc:
        log.warning(f"App info fetch failed: {exc}")
        return None


def _fetch_available_updates() -> list[dict[str, Any]] | None:
    """Fetch available releases from the Replicated SDK."""
    try:
        req = urllib.request.Request(
            REPLICATED_SDK_UPDATES_URL,
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            log.debug(f"Available updates fetched: {data}")
            return data if isinstance(data, list) else None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            log.debug("No updates endpoint available")
            return None
        log.warning(f"Updates HTTP error {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as exc:
        log.warning(f"Updates fetch failed: {exc}")
        return None


def clear_cache() -> None:
    """Clear the in-memory update status cache (useful in tests)."""
    global _cache, _cache_time
    _cache = None
    _cache_time = None


def get_update_status() -> dict[str, Any]:
    """Return whether an app update is available.

    Checks the SDK app info and available updates endpoints, compares versions,
    and caches the result for 5 minutes.
    """
    global _cache, _cache_time

    if _cache is not None and _cache_time is not None:
        if datetime.now(timezone.utc) - _cache_time < timedelta(seconds=CACHE_TTL_SECONDS):
            log.debug("Returning cached update status")
            return _cache

    info = _fetch_app_info()
    updates = _fetch_available_updates()

    if info is None:
        # SDK unreachable (local dev) — assume no updates
        result = {
            "available": False,
            "version": None,
            "notes": None,
            "license_valid": None,
            "current_version": None,
        }
        _cache = result
        _cache_time = datetime.now(timezone.utc)
        return result

    current_version = (
        info.get("versionLabel")
        or info.get("appVersion")
        or info.get("currentRelease", {}).get("versionLabel")
    )
    license_valid = info.get("license", {}).get("isValid", True)

    next_update = None
    if updates:
        # Sort by createdAt descending and pick the newest
        sorted_updates = sorted(
            updates,
            key=lambda u: u.get("createdAt", ""),
            reverse=True,
        )
        next_update = sorted_updates[0]

    available = False
    next_version = None
    next_notes = None

    if next_update and current_version:
        next_version = next_update.get("versionLabel")
        next_notes = next_update.get("releaseNotes", "")
        # Compare version labels; available if they differ
        available = next_version is not None and next_version != current_version

    result = {
        "available": available,
        "version": next_version,
        "notes": next_notes,
        "license_valid": license_valid,
        "current_version": current_version,
    }

    _cache = result
    _cache_time = datetime.now(timezone.utc)
    log.info(f"Update status: {result}")
    return result
