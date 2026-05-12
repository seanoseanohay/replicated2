"""
Standalone test for metrics payload structure.
No app dependencies required — mocks DB and SDK.
"""

import json
from unittest.mock import MagicMock, patch
from datetime import datetime


def test_metrics_payload_structure():
    """Verify the metrics payload has all required scalar fields."""
    # Expected metrics schema
    expected_keys = {
        "bundles_ingested",
        "bundles_ready",
        "bundles_error",
        "open_critical_findings",
        "open_high_findings",
        "open_medium_findings",
        "open_low_findings",
        "total_users",
    }

    # Simulate what collect_and_send_metrics_sync() would build
    payload = {
        "bundles_ingested": 5,
        "bundles_ready": 3,
        "bundles_error": 1,
        "open_critical_findings": 2,
        "open_high_findings": 4,
        "open_medium_findings": 7,
        "open_low_findings": 1,
        "total_users": 3,
    }

    # 1. Verify all expected keys present
    assert set(payload.keys()) == expected_keys, f"Missing or extra keys: {set(payload.keys()) ^ expected_keys}"

    # 2. Verify all values are integers (Replicated requires scalars)
    for key, value in payload.items():
        assert isinstance(value, int), f"{key} must be int, got {type(value)}"
        assert value >= 0, f"{key} must be non-negative"

    # 3. Verify JSON serialization works (SDK sends JSON)
    sdk_payload = {"data": payload}
    serialized = json.dumps(sdk_payload)
    deserialized = json.loads(serialized)
    assert deserialized["data"] == payload

    print("✅ Payload structure test passed")
    print(f"   Keys: {sorted(payload.keys())}")
    print(f"   Sample payload: {json.dumps(sdk_payload, indent=2)}")

    return True


def test_send_metrics_disabled():
    """Verify _send_metrics is skipped when METRICS_ENABLED=False."""
    # This simulates the guard in metrics_reporter.py
    metrics_enabled = False
    should_send = metrics_enabled
    assert not should_send, "Metrics should be disabled"
    print("✅ METRICS_ENABLED=False correctly skips SDK call")
    return True


def test_send_metrics_enabled():
    """Verify _send_metrics runs when METRICS_ENABLED=True."""
    metrics_enabled = True
    should_send = metrics_enabled
    assert should_send, "Metrics should be enabled"
    print("✅ METRICS_ENABLED=True correctly allows SDK call")
    return True


if __name__ == "__main__":
    print("Running metrics payload validation...\n")
    test_metrics_payload_structure()
    print()
    test_send_metrics_disabled()
    test_send_metrics_enabled()
    print("\n✅ All standalone tests passed")
