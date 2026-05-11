import logging
import urllib.request
import urllib.error
import json

from sqlalchemy import func

from app.models.bundle import Bundle
from app.models.finding import Finding
from app.models.user import User

log = logging.getLogger(__name__)

REPLICATED_SDK_METRICS_URL = "http://replicated:3000/api/v1/app/custom-metrics"


def _send_metrics(payload: dict) -> bool:
    """Send metrics payload to the Replicated SDK in-cluster API."""
    from app.core.config import settings

    if not settings.METRICS_ENABLED:
        log.debug("Metrics disabled; skipping SDK call")
        return False
    try:
        data = json.dumps({"data": payload}).encode("utf-8")
        req = urllib.request.Request(
            REPLICATED_SDK_METRICS_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="PATCH",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            log.info(f"Metrics sent: {resp.status}")
            return True
    except urllib.error.HTTPError as e:
        log.warning(f"Metrics HTTP error {e.code}: {e.read().decode()[:200]}")
        return False
    except Exception as exc:
        log.warning(f"Metrics send failed: {exc}")
        return False


def collect_and_send_metrics_sync() -> dict:
    """Query real app data and send to Replicated Vendor Portal via SDK.

    Creates its own sync DB session so it can be called from Celery or FastAPI.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import settings

    sync_url = settings.DATABASE_URL.replace(
        "postgresql+asyncpg://", "postgresql+psycopg2://"
    )
    engine = create_engine(sync_url, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()

    try:
        # Total bundles ingested
        total_bundles = session.query(func.count(Bundle.id)).scalar() or 0

        # Bundles by status
        ready_bundles = (
            session.query(func.count(Bundle.id))
            .filter(Bundle.status == "ready")
            .scalar()
            or 0
        )
        error_bundles = (
            session.query(func.count(Bundle.id))
            .filter(Bundle.status == "error")
            .scalar()
            or 0
        )

        # Open findings by severity
        open_critical = (
            session.query(func.count(Finding.id))
            .filter(Finding.status == "open", Finding.severity == "critical")
            .scalar()
            or 0
        )
        open_high = (
            session.query(func.count(Finding.id))
            .filter(Finding.status == "open", Finding.severity == "high")
            .scalar()
            or 0
        )
        open_medium = (
            session.query(func.count(Finding.id))
            .filter(Finding.status == "open", Finding.severity == "medium")
            .scalar()
            or 0
        )
        open_low = (
            session.query(func.count(Finding.id))
            .filter(Finding.status == "open", Finding.severity == "low")
            .scalar()
            or 0
        )

        # Total registered users
        total_users = session.query(func.count(User.id)).scalar() or 0

        payload = {
            "bundles_ingested": total_bundles,
            "bundles_ready": ready_bundles,
            "bundles_error": error_bundles,
            "open_critical_findings": open_critical,
            "open_high_findings": open_high,
            "open_medium_findings": open_medium,
            "open_low_findings": open_low,
            "total_users": total_users,
        }

        ok = _send_metrics(payload)
        log.info(f"Metrics collected: {payload} (sent={ok})")
        return {"metrics": payload, "sent": ok}
    except Exception as exc:
        log.error(f"Metrics collection failed: {exc}")
        return {"metrics": {}, "sent": False, "error": str(exc)}
    finally:
        session.close()
        engine.dispose()
