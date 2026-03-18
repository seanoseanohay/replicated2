import logging
import uuid
from pathlib import Path

from celery import Celery
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

        # 6. Mark as ready
        bundle.status = "ready"
        bundle.error_message = None
        session.commit()
        log.info(f"Bundle {bundle_id} marked as ready")

        return {"bundle_id": bundle_id, "status": "ready", "evidence_count": len(evidence_list)}

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


# Make celery_app importable as `app` for the CLI command
app = celery_app
