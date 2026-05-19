import logging
import uuid

from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

celery_app = Celery(
    "bundle_analyzer",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_soft_time_limit=540,  # seconds — raises SoftTimeLimitExceeded
    task_time_limit=600,  # hard kill
    task_reject_on_worker_lost=True,
    beat_schedule_filename="/tmp/celerybeat-schedule",
    beat_schedule={
        "cleanup-stuck-bundles": {
            "task": "tasks.cleanup_stuck_bundles",
            "schedule": 300.0,  # every 5 minutes
        },
    },
)

log = logging.getLogger(__name__)


def _deduplicate_findings(findings: list) -> list:
    """Suppress cascade findings when the root cause is already captured.

    Rules:
    - high_restart_count is suppressed when all its affected pods already have
      a pod_crashloop finding (same underlying problem, lower-signal rule).
    - BackOff event findings are suppressed when all affected pods are already
      covered by a pod_crashloop finding (BackOff is a symptom of the crash).
    """
    crash_pods: set[str] = set()
    for f in findings:
        if f.rule_id == "pod_crashloop":
            for pod in (f.remediation or {}).get("_affected_pods", []):
                crash_pods.add(pod)

    if not crash_pods:
        return findings

    result = []
    for f in findings:
        if f.rule_id == "high_restart_count":
            affected = set((f.remediation or {}).get("_affected_pods", []))
            if affected and affected.issubset(crash_pods):
                log.info(f"Suppressing high_restart_count finding — all pods already in crash findings: {affected}")
                continue
        elif f.rule_id == "warning_event_reasons" and "BackOff" in f.title:
            affected = set((f.remediation or {}).get("_affected_pods", []))
            if affected and affected.issubset(crash_pods):
                log.info(f"Suppressing BackOff event finding — all affected pods already in crash findings: {affected}")
                continue
        result.append(f)
    return result


def _make_sync_session() -> tuple[Engine, Session]:
    """Create a synchronous SQLAlchemy engine + session for use inside Celery tasks."""
    sync_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )
    engine = create_engine(sync_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return engine, SessionLocal()


@celery_app.task(bind=True, name="tasks.process_bundle", max_retries=3)
def process_bundle(self, bundle_id: str) -> dict:
    """
    Download, extract, and parse a support bundle, persisting Evidence records.
    """
    from app.models.bundle import Bundle
    from app.parsing.extractor import BundleExtractor
    from app.parsing.registry import run_all_parsers
    from app.services.storage import storage_service

    log.info(f"Starting processing for bundle {bundle_id}")

    engine, session = _make_sync_session()
    try:
        # 1. Fetch bundle record
        bundle = session.get(Bundle, uuid.UUID(bundle_id))
        if bundle is None:
            log.error(f"Bundle {bundle_id} not found in database")
            return {"bundle_id": bundle_id, "status": "error", "error": "not found"}

        def _progress(msg: str) -> None:
            bundle.progress_message = msg
            session.commit()
            log.info(f"Bundle {bundle_id}: {msg}")

        # 2. Mark as processing
        bundle.status = "processing"
        bundle.error_message = None
        bundle.progress_message = "Starting analysis…"
        session.commit()

        # 3. Download + extract
        extractor = BundleExtractor(storage_service)
        s3_key = bundle.s3_key
        if not s3_key:
            raise ValueError(f"Bundle {bundle_id} has no s3_key")

        _progress("Downloading bundle from storage…")
        with extractor.extract(s3_key) as bundle_root:
            _progress("Extracting bundle contents…")

            # 4. Run all parsers
            _progress("Parsing Kubernetes resources…")
            evidence_list = run_all_parsers(bundle_root, uuid.UUID(bundle_id))
            log.info(f"Parsed {len(evidence_list)} evidence records for bundle {bundle_id}")

        # 5. Bulk insert evidence
        if evidence_list:
            _progress(f"Storing {len(evidence_list)} evidence records…")
            session.bulk_save_objects(evidence_list)
            session.commit()

        # 6. Run detection rules
        from app.detection.registry import run_all_rules

        _progress("Running detection rules…")
        findings = run_all_rules(uuid.UUID(bundle_id), session)
        findings = _deduplicate_findings(findings)
        if findings:
            _progress(f"Saving {len(findings)} finding(s)…")
            # add_all + flush populates f.id (uuid.uuid4 default) back onto Python objects
            session.add_all(findings)
            session.flush()
            session.commit()
            log.info(f"Inserted {len(findings)} findings for bundle {bundle_id}")

            # Record "created" events for all findings
            try:
                from app.models.finding_event import FindingEvent

                created_events = [
                    FindingEvent(
                        finding_id=f.id,
                        actor="system",
                        event_type="created",
                        new_value=f.status,
                    )
                    for f in findings
                ]
                session.add_all(created_events)
                session.flush()
                session.commit()
            except Exception as evt_exc:
                session.rollback()
                log.warning(f"Failed to record finding created events: {evt_exc}")

        # 7. Send notifications (best-effort)
        try:
            from app.services.notifications import notify_bundle_findings

            notify_bundle_findings(bundle_id, session)
        except Exception as notif_exc:
            log.warning(f"Notification delivery failed for bundle {bundle_id}: {notif_exc}")

        # 9. Mark as ready
        bundle.status = "ready"
        bundle.error_message = None
        bundle.progress_message = None
        session.commit()
        log.info(f"Bundle {bundle_id} marked as ready")

        return {
            "bundle_id": bundle_id,
            "status": "ready",
            "evidence_count": len(evidence_list),
            "finding_count": len(findings),
        }

    except SoftTimeLimitExceeded:
        log.error(f"Bundle {bundle_id} timed out")
        # mark error, don't retry
        try:
            session.rollback()
            bundle = session.get(Bundle, uuid.UUID(bundle_id))
            if bundle:
                bundle.status = "error"
                bundle.error_message = "Processing timed out"
                session.commit()
        except Exception:
            pass
        return {"bundle_id": bundle_id, "status": "error", "error": "timeout"}

    except Exception as exc:
        log.error(f"Failed to process bundle {bundle_id}: {exc}")
        try:
            session.rollback()
            bundle = session.get(Bundle, uuid.UUID(bundle_id))
            if bundle:
                bundle.status = "error"
                bundle.error_message = str(exc)[:2048]
                session.commit()
        except Exception as inner_exc:
            log.error(
                f"Failed to update error status for bundle {bundle_id}: {inner_exc}"
            )
        raise self.retry(exc=exc, countdown=5)
    finally:
        session.close()
        engine.dispose()


@celery_app.task(bind=True, name="tasks.reanalyze_bundle", max_retries=3)
def reanalyze_bundle(self, bundle_id: str) -> dict:
    """
    Re-run detection rules on existing evidence for a bundle.
    Clears old findings then inserts fresh ones.
    """
    from app.models.bundle import Bundle
    from app.models.finding import Finding

    log.info(f"Starting reanalysis for bundle {bundle_id}")

    engine, session = _make_sync_session()
    try:
        bundle = session.get(Bundle, uuid.UUID(bundle_id))
        if bundle is None:
            return {"bundle_id": bundle_id, "status": "error", "error": "not found"}

        bundle.status = "processing"
        bundle.error_message = None
        session.commit()

        # Delete old findings (cascades to events/comments via DB)
        session.query(Finding).filter(
            Finding.bundle_id == uuid.UUID(bundle_id)
        ).delete()
        session.commit()

        # Re-run detection rules on existing evidence
        from app.detection.registry import run_all_rules

        findings = run_all_rules(uuid.UUID(bundle_id), session)
        findings = _deduplicate_findings(findings)
        if findings:
            session.add_all(findings)
            session.flush()
            session.commit()
            log.info(
                f"Reanalysis inserted {len(findings)} findings for bundle {bundle_id}"
            )

            try:
                from app.models.finding_event import FindingEvent

                created_events = [
                    FindingEvent(
                        finding_id=f.id,
                        actor="system",
                        event_type="created",
                        new_value=f.status,
                    )
                    for f in findings
                ]
                session.add_all(created_events)
                session.flush()
                session.commit()
            except Exception as evt_exc:
                session.rollback()
                log.warning(f"Failed to record finding created events: {evt_exc}")

        bundle.status = "ready"
        bundle.error_message = None
        session.commit()
        log.info(f"Bundle {bundle_id} reanalysis complete")

        return {
            "bundle_id": bundle_id,
            "status": "ready",
            "finding_count": len(findings) if findings else 0,
        }

    except SoftTimeLimitExceeded:
        log.error(f"Bundle {bundle_id} reanalysis timed out")
        try:
            session.rollback()
            bundle = session.get(Bundle, uuid.UUID(bundle_id))
            if bundle:
                bundle.status = "error"
                bundle.error_message = "Reanalysis timed out"
                session.commit()
        except Exception:
            pass
        return {"bundle_id": bundle_id, "status": "error", "error": "timeout"}

    except Exception as exc:
        log.error(f"Failed to reanalyze bundle {bundle_id}: {exc}")
        try:
            session.rollback()
            bundle = session.get(Bundle, uuid.UUID(bundle_id))
            if bundle:
                bundle.status = "error"
                bundle.error_message = str(exc)[:2048]
                session.commit()
        except Exception as inner_exc:
            log.error(
                f"Failed to update error status for bundle {bundle_id}: {inner_exc}"
            )
        raise self.retry(exc=exc, countdown=5)
    finally:
        session.close()
        engine.dispose()


@celery_app.task(name="tasks.cleanup_stuck_bundles")
def cleanup_stuck_bundles() -> dict:
    """Reset bundles stuck in 'processing' for more than 30 minutes."""
    from datetime import datetime, timezone, timedelta
    from app.models.bundle import Bundle

    engine, session = _make_sync_session()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)
        # Find bundles stuck in processing
        from sqlalchemy import and_

        stuck = (
            session.query(Bundle)
            .filter(
                and_(
                    Bundle.status == "processing",
                    Bundle.updated_at < cutoff,
                )
            )
            .all()
        )
        count = len(stuck)
        for bundle in stuck:
            bundle.status = "error"
            bundle.error_message = "Processing timed out (cleaned up)"
        session.commit()
        log.info(f"cleanup_stuck_bundles: reset {count} stuck bundles")
        return {"cleaned": count}
    except Exception as exc:
        session.rollback()
        log.error(f"cleanup_stuck_bundles failed: {exc}")
        return {"error": str(exc)}
    finally:
        session.close()
        engine.dispose()


@celery_app.task(name="tasks.report_custom_metrics")
def report_custom_metrics() -> dict:
    """Collect and send custom app metrics to the Replicated SDK."""
    from app.services.metrics_reporter import collect_and_send_metrics_sync

    try:
        result = collect_and_send_metrics_sync()
        return result
    except Exception as exc:
        log.error(f"report_custom_metrics failed: {exc}")
        return {"error": str(exc)}


@celery_app.task(name="tasks.generate_and_upload_support_bundle", bind=True, max_retries=2)
def generate_and_upload_support_bundle(self, namespace: str, spec_secret: str) -> dict:
    """Generate a support bundle and upload it to the Replicated Vendor Portal via SDK."""
    import subprocess
    import os
    import tempfile
    import uuid as uuid_mod

    bundle_path = f"/tmp/support-bundle-{uuid_mod.uuid4().hex}.tar.gz"
    sdk_host = os.environ.get("REPLICATED_SDK_HOST", "bundle-analyzer-sdk")
    sdk_url = f"http://{sdk_host}:3000/api/v1/supportbundle"

    log.info("support_bundle_generation_start spec_secret=%s namespace=%s", spec_secret, namespace)

    try:
        # 1. Generate support bundle
        cmd = [
            "kubectl", "support-bundle",
            f"secret/{namespace}/{spec_secret}",
            "--load-cluster-specs=false",
            "-o", bundle_path,
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if result.returncode != 0:
            log.error(
                "support_bundle_generation_failed stdout=%s stderr=%s",
                result.stdout,
                result.stderr,
            )
            raise self.retry(
                exc=RuntimeError(
                    f"kubectl support-bundle failed: {result.stderr or result.stdout}"
                ),
                countdown=10,
            )

        bundle_size = os.path.getsize(bundle_path)
        log.info("support_bundle_generated path=%s size=%d", bundle_path, bundle_size)

        # 2. Post-process bundle for Vendor Portal compatibility
        import glob
        import json
        import tarfile
        import shutil
        import yaml

        work_dir = tempfile.mkdtemp(prefix="sb-post-")
        fixed_path = f"/tmp/support-bundle-fixed-{uuid_mod.uuid4().hex}.tar.gz"
        try:
            with tarfile.open(bundle_path, "r:gz") as tar_in:
                tar_in.extractall(path=work_dir)

            # Find files anywhere in the extracted tree (bundle may have a root dir)
            def _find(name: str) -> str | None:
                for p in glob.glob(os.path.join(work_dir, "**", name), recursive=True):
                    if os.path.isfile(p):
                        return p
                return None

            # Fix app-info.json: extract raw body from http response envelope
            app_info_path = _find("app-info.json")
            instance_id = None
            if app_info_path:
                with open(app_info_path) as f:
                    app_info = json.load(f)
                body = app_info.get("response", {}).get("body")
                if body:
                    with open(app_info_path, "w") as f:
                        f.write(body)
                    log.info("support_bundle_postprocessed app_info extracted raw body")
                    # grab instance_id for kots compat below
                    try:
                        parsed_app_info = json.loads(body)
                        instance_id = parsed_app_info.get("instanceID") or parsed_app_info.get("instance_id")
                    except Exception:
                        pass

            # Fix license.json → license.yaml: extract raw body and convert to YAML
            license_json_path = _find("license.json")
            license_obj = None
            if license_json_path:
                with open(license_json_path) as f:
                    license_data = json.load(f)
                body = license_data.get("response", {}).get("body")
                if body:
                    license_obj = json.loads(body)
                    license_yaml_path = os.path.join(
                        os.path.dirname(license_json_path), "license.yaml"
                    )
                    with open(license_yaml_path, "w") as f:
                        yaml.dump(license_obj, f, default_flow_style=False, sort_keys=False)
                    os.unlink(license_json_path)
                    log.info("support_bundle_postprocessed license converted json→yaml")

            # Vendor Portal built-in analyzers expect KOTS-style paths and formats
            # for license + app-info even on Helm-only apps.  Create the minimal
            # compat files under kots/admin_console/ so the instance / license
            # insights resolve rather than warn.
            bundle_root = None
            for entry in os.listdir(work_dir):
                candidate = os.path.join(work_dir, entry)
                if os.path.isdir(candidate):
                    bundle_root = candidate
                    break
            if bundle_root and instance_id and license_obj:
                kots_dir = os.path.join(bundle_root, "kots", "admin_console")
                os.makedirs(kots_dir, exist_ok=True)

                # minimal app-info.json with snake_case field that Vendor Portal looks for
                kots_app_info = {"instance_id": instance_id}
                with open(os.path.join(kots_dir, "app-info.json"), "w") as f:
                    json.dump(kots_app_info, f)
                log.info("support_bundle_postprocessed added kots/admin_console/app-info.json")

                # KOTS License CRD yaml so Vendor Portal recognises it
                license_cr = {
                    "apiVersion": "kots.io/v1beta1",
                    "kind": "License",
                    "metadata": {
                        "name": license_obj.get("customerName", "customer")
                    },
                    "spec": license_obj,
                }
                with open(os.path.join(kots_dir, "license.yaml"), "w") as f:
                    yaml.dump(license_cr, f, default_flow_style=False, sort_keys=False)
                log.info("support_bundle_postprocessed added kots/admin_console/license.yaml")

            with tarfile.open(fixed_path, "w:gz") as tar_out:
                for root, dirs, files in os.walk(work_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        arcname = os.path.relpath(full_path, work_dir)
                        tar_out.add(full_path, arcname=arcname)

            bundle_path = fixed_path
            bundle_size = os.path.getsize(bundle_path)
            log.info("support_bundle_repacked path=%s size=%d", bundle_path, bundle_size)
        except Exception as pp_exc:
            log.warning("support_bundle_postprocess_failed error=%s", pp_exc)
            # Continue with original bundle on post-process failure
        finally:
            if os.path.exists(work_dir):
                shutil.rmtree(work_dir)

        # 3. Upload to SDK
        import httpx

        with open(bundle_path, "rb") as f:
            response = httpx.post(
                sdk_url,
                content=f.read(),
                headers={
                    "Content-Type": "application/gzip",
                    "Content-Length": str(bundle_size),
                },
                timeout=120,
            )

        if response.status_code == 201:
            data = response.json()
            log.info(
                "support_bundle_uploaded bundle_id=%s slug=%s",
                data.get("bundleId"),
                data.get("slug"),
            )
            return {
                "status": "uploaded",
                "bundle_id": data.get("bundleId"),
                "slug": data.get("slug"),
            }
        else:
            log.error(
                "support_bundle_upload_failed status_code=%d body=%s",
                response.status_code,
                response.text[:500],
            )
            raise self.retry(
                exc=RuntimeError(
                    f"SDK upload failed: {response.status_code} {response.text[:200]}"
                ),
                countdown=10,
            )

    except subprocess.TimeoutExpired:
        log.error("support_bundle_generation_timeout")
        raise self.retry(exc=RuntimeError("Bundle generation timed out"), countdown=30)
    except Exception as exc:
        log.error("support_bundle_unexpected_error error=%s", exc)
        raise self.retry(exc=exc, countdown=10)
    finally:
        # Clean up temp bundle file
        if os.path.exists(bundle_path):
            os.unlink(bundle_path)
            log.info("support_bundle_cleaned_up path=%s", bundle_path)


# Make celery_app importable as `app` for the CLI command
app = celery_app
