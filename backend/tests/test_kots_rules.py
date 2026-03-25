"""
Unit tests for KOTS detection rules.
Uses an in-memory SQLite database (no Celery or Postgres needed).
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.evidence import Evidence
from app.detection.rules.kots_low_replicas import KotsLowReplicasRule
from app.detection.rules.kots_debug_enabled import KotsDebugEnabledRule
from app.detection.rules.kots_tls_disabled import KotsTlsDisabledRule
from app.detection.rules.kots_low_storage import KotsLowStorageRule
from app.detection.rules.kots_missing_s3 import KotsMissingS3Rule


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def sync_engine():
    engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(sync_engine):
    SessionLocal = sessionmaker(bind=sync_engine, autocommit=False, autoflush=False)
    sess = SessionLocal()
    try:
        yield sess
        sess.rollback()
    finally:
        sess.close()


def make_bundle_id() -> uuid.UUID:
    return uuid.uuid4()


# Sample configvalues structure for generating diffs
SAMPLE_CONFIGVALUES_RAW = {
    "apiVersion": "kots.io/v1beta1",
    "kind": "ConfigValues",
    "metadata": {"name": "test-app"},
    "spec": {
        "values": {
            "replicas": {"value": "1"},
            "debug_mode": {"value": "true"},
            "tls_enabled": {"value": "false"},
            "storage_size": {"value": "5"},
            "s3_bucket": {"value": ""},
        }
    },
}


def make_kots_config_values_evidence(bundle_id, values: dict, configvalues_raw: dict = None):
    return Evidence(
        id=uuid.uuid4(),
        bundle_id=bundle_id,
        kind="KotsConfigValues",
        namespace=None,
        name="test-app",
        source_path="kots/configvalues.yaml",
        raw_data={
            "values": values,
            "_source_file": "configvalues.yaml",
            "_configvalues_raw": configvalues_raw or SAMPLE_CONFIGVALUES_RAW,
        },
    )


# ── KotsLowReplicasRule ───────────────────────────────────────────────────────

class TestKotsLowReplicasRule:
    def test_fires_when_replicas_is_one(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"replicas": {"value": "1"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsLowReplicasRule()
        findings = rule.evaluate(bundle_id, session)

        assert len(findings) == 1
        f = findings[0]
        assert f.severity == "high"
        assert f.rule_id == "kots_low_replicas"
        assert f.remediation["kots_key"] == "replicas"
        assert f.remediation["kots_recommended_value"] == "2"
        assert "kubectl kots set config" in f.remediation["cli_commands"][0]
        assert f.remediation["kots_diff"] != ""
        assert "--- a/configvalues.yaml" in f.remediation["kots_diff"]

    def test_does_not_fire_when_replicas_is_two(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"replicas": {"value": "2"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsLowReplicasRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0

    def test_fires_for_replica_count_key(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"replica_count": {"value": "1"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsLowReplicasRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        assert findings[0].remediation["kots_key"] == "replica_count"

    def test_does_not_fire_for_unrelated_keys(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"memory_limit": {"value": "1"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsLowReplicasRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0


# ── KotsDebugEnabledRule ──────────────────────────────────────────────────────

class TestKotsDebugEnabledRule:
    def test_fires_for_debug_true(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"debug_mode": {"value": "true"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsDebugEnabledRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == "medium"
        assert f.remediation["kots_key"] == "debug_mode"
        assert f.remediation["kots_recommended_value"] == "false"
        assert "kubectl kots set config" in f.remediation["cli_commands"][0]
        assert f.remediation["kots_diff"] != ""
        assert "--- a/configvalues.yaml" in f.remediation["kots_diff"]

    def test_fires_for_log_level_debug(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"log_level": {"value": "debug"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsDebugEnabledRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1

    def test_does_not_fire_when_debug_false(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"debug_mode": {"value": "false"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsDebugEnabledRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0


# ── KotsTlsDisabledRule ───────────────────────────────────────────────────────

class TestKotsTlsDisabledRule:
    def test_fires_for_tls_false(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"tls_enabled": {"value": "false"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsTlsDisabledRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == "high"
        assert f.remediation["kots_key"] == "tls_enabled"
        assert f.remediation["kots_recommended_value"] == "true"
        assert "kubectl kots set config" in f.remediation["cli_commands"][0]
        assert f.remediation["kots_diff"] != ""
        assert "--- a/configvalues.yaml" in f.remediation["kots_diff"]

    def test_fires_for_https_disabled(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"https_enabled": {"value": "disabled"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsTlsDisabledRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1

    def test_does_not_fire_when_tls_enabled(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"tls_enabled": {"value": "true"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsTlsDisabledRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0


# ── KotsLowStorageRule ────────────────────────────────────────────────────────

class TestKotsLowStorageRule:
    def test_fires_for_storage_below_10(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"storage_size": {"value": "5"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsLowStorageRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == "medium"
        assert f.remediation["kots_key"] == "storage_size"
        assert f.remediation["kots_recommended_value"] == "10Gi"
        assert len(f.remediation["cli_commands"]) == 2
        assert f.remediation["kots_diff"] != ""
        assert "--- a/configvalues.yaml" in f.remediation["kots_diff"]

    def test_fires_for_disk_key(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"disk_size": {"value": "8Gi"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsLowStorageRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1

    def test_does_not_fire_when_storage_ok(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"storage_size": {"value": "20"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsLowStorageRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0

    def test_does_not_fire_for_non_numeric_value(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"storage_size": {"value": "auto"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsLowStorageRule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0


# ── KotsMissingS3Rule ─────────────────────────────────────────────────────────

class TestKotsMissingS3Rule:
    def test_fires_for_empty_s3_bucket(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"s3_bucket": {"value": ""}},
        )
        session.add(ev)
        session.flush()

        rule = KotsMissingS3Rule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
        f = findings[0]
        assert f.severity == "high"
        assert f.remediation["kots_key"] == "s3_bucket"
        assert "kubectl kots set config" in f.remediation["cli_commands"][0]
        assert f.remediation["kots_diff"] != ""
        assert "--- a/configvalues.yaml" in f.remediation["kots_diff"]

    def test_fires_for_null_s3_bucket(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"s3_bucket": {"value": None}},
        )
        session.add(ev)
        session.flush()

        rule = KotsMissingS3Rule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1

    def test_does_not_fire_when_s3_configured(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"s3_bucket": {"value": "my-prod-bucket"}},
        )
        session.add(ev)
        session.flush()

        rule = KotsMissingS3Rule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 0

    def test_fires_for_backup_bucket_key(self, session):
        bundle_id = make_bundle_id()
        ev = make_kots_config_values_evidence(
            bundle_id,
            {"backup_bucket": {"value": ""}},
        )
        session.add(ev)
        session.flush()

        rule = KotsMissingS3Rule()
        findings = rule.evaluate(bundle_id, session)
        assert len(findings) == 1
