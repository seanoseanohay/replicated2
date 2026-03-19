import logging
import uuid
from pathlib import Path

from celery import Celery
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy import create_engine
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
    task_soft_time_limit=540,   # seconds — raises SoftTimeLimitExceeded
    task_time_limit=600,        # hard kill
    task_reject_on_worker_lost=True,
    beat_schedule={
        "cleanup-stuck-bundles": {
            "task": "tasks.cleanup_stuck_bundles",
            "schedule": 300.0,  # every 5 minutes
        }
    },
)

log = logging.getLogger(__name__)


def _make_sync_session() -> tuple[any, Session]:
    """Create a synchronous SQLAlchemy engine + session for use inside Celery tasks."""
    sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
    engine = create_engine(sync_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    return engine, SessionLocal()


@celery_app.task(bind=True, name="tasks.process_bundle", max_retries=3)
def process_bundle(self, bundle_id: str) -> dict:
    """
    Download, extract, and parse a support bundle, persisting Evidence records.
    """
    from app.models.bundle import Bundle
    from app.models.evidence import Evidence
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

        # 2. Mark as processing
        bundle.status = "processing"
        bundle.error_message = None
        session.commit()
        log.info(f"Bundle {bundle_id} marked as processing")

        # 3. Download + extract
        extractor = BundleExtractor(storage_service)
        s3_key = bundle.s3_key
        if not s3_key:
            raise ValueError(f"Bundle {bundle_id} has no s3_key")

        with extractor.extract(s3_key) as bundle_root:
            log.info(f"Bundle {bundle_id} extracted to {bundle_root}")

            # 4. Run all parsers
            evidence_list = run_all_parsers(bundle_root, uuid.UUID(bundle_id))
            log.info(f"Parsed {len(evidence_list)} evidence records for bundle {bundle_id}")

        # 5. Bulk insert evidence
        if evidence_list:
            session.bulk_save_objects(evidence_list)
            session.commit()
            log.info(f"Inserted {len(evidence_list)} evidence records for bundle {bundle_id}")

        # 6. Run detection rules
        from app.detection.registry import run_all_rules
        findings = run_all_rules(uuid.UUID(bundle_id), session)
        if findings:
            session.bulk_save_objects(findings)
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
                session.bulk_save_objects(created_events)
                session.commit()
            except Exception as evt_exc:
                log.warning(f"Failed to record finding created events: {evt_exc}")

        # 7. Send notifications (best-effort)
        try:
            from app.services.notifications import notify_bundle_findings
            notify_bundle_findings(bundle_id, session)
        except Exception as notif_exc:
            log.warning(f"Notification delivery failed for bundle {bundle_id}: {notif_exc}")

        # 8. Mark as ready
        bundle.status = "ready"
        bundle.error_message = None
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
            log.error(f"Failed to update error status for bundle {bundle_id}: {inner_exc}")
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
        session.query(Finding).filter(Finding.bundle_id == uuid.UUID(bundle_id)).delete()
        session.commit()

        # Re-run detection rules on existing evidence
        from app.detection.registry import run_all_rules
        findings = run_all_rules(uuid.UUID(bundle_id), session)
        if findings:
            session.bulk_save_objects(findings)
            session.commit()
            log.info(f"Reanalysis inserted {len(findings)} findings for bundle {bundle_id}")

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
                session.bulk_save_objects(created_events)
                session.commit()
            except Exception as evt_exc:
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
            log.error(f"Failed to update error status for bundle {bundle_id}: {inner_exc}")
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
        stuck = session.query(Bundle).filter(
            and_(
                Bundle.status == "processing",
                Bundle.updated_at < cutoff,
            )
        ).all()
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


# Make celery_app importable as `app` for the CLI command
app = celery_app
