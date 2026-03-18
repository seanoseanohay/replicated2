import time

from celery import Celery

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


@celery_app.task(bind=True, name="tasks.process_bundle", max_retries=3)
def process_bundle(self, bundle_id: str) -> dict:
    """
    Placeholder task for processing a support bundle.
    Phase 1 will implement actual extraction and analysis.
    """
    import logging

    import psycopg2

    log = logging.getLogger(__name__)
    log.info(f"Starting processing for bundle {bundle_id}")

    # Synchronous DB update using psycopg2 (Celery workers are sync)
    db_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

    try:
        conn = psycopg2.connect(db_url)
        conn.autocommit = True
        cur = conn.cursor()

        # Mark as processing
        cur.execute(
            "UPDATE bundles SET status = %s, updated_at = NOW() WHERE id = %s",
            ("processing", bundle_id),
        )
        log.info(f"Bundle {bundle_id} marked as processing")

        # Placeholder: simulate work
        time.sleep(1)

        # Mark as ready
        cur.execute(
            "UPDATE bundles SET status = %s, updated_at = NOW() WHERE id = %s",
            ("ready", bundle_id),
        )
        log.info(f"Bundle {bundle_id} marked as ready")

        cur.close()
        conn.close()
    except Exception as exc:
        log.error(f"Failed to process bundle {bundle_id}: {exc}")
        try:
            conn = psycopg2.connect(db_url)
            conn.autocommit = True
            cur = conn.cursor()
            cur.execute(
                "UPDATE bundles SET status = %s, error_message = %s, updated_at = NOW() WHERE id = %s",
                ("error", str(exc), bundle_id),
            )
            cur.close()
            conn.close()
        except Exception:
            pass
        raise self.retry(exc=exc, countdown=5)

    return {"bundle_id": bundle_id, "status": "ready"}


# Make celery_app importable as `app` for the CLI command
app = celery_app
