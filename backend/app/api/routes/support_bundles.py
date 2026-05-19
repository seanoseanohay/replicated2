from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.deps import get_current_user, require_admin
from app.core.logging import get_logger
from app.models.user import User
from app.workers.tasks import celery_app, generate_and_upload_support_bundle

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/support-bundles", tags=["support-bundles"])


class SupportBundleRequest(BaseModel):
    namespace: str = Field(default="bundle-analyzer", description="Namespace containing the support bundle spec Secret")
    spec_secret: str = Field(default="bundle-analyzer-support-bundle-config", description="Name of the Secret holding the support bundle spec")


class SupportBundleResponse(BaseModel):
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict | None = None


@router.post(
    "",
    response_model=SupportBundleResponse,
    dependencies=[Depends(require_admin)],
)
async def create_support_bundle(
    request: SupportBundleRequest,
    current_user: User = Depends(get_current_user),
) -> SupportBundleResponse:
    """Trigger async support bundle generation and upload to Vendor Portal."""
    task = generate_and_upload_support_bundle.delay(
        namespace=request.namespace,
        spec_secret=request.spec_secret,
    )
    logger.info(
        "support_bundle_requested",
        task_id=task.id,
        user_id=str(current_user.id),
        namespace=request.namespace,
    )
    return SupportBundleResponse(
        task_id=task.id,
        status="queued",
        message="Support bundle generation has started. Poll /support-bundles/{task_id} for status.",
    )


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_support_bundle_status(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> TaskStatusResponse:
    """Check the status of a support bundle generation task."""
    result = celery_app.AsyncResult(task_id)

    if result.state == "PENDING":
        return TaskStatusResponse(task_id=task_id, status="pending", result=None)
    elif result.state == "STARTED" or result.state == "PROGRESS":
        return TaskStatusResponse(task_id=task_id, status="in_progress", result=None)
    elif result.state == "SUCCESS":
        return TaskStatusResponse(
            task_id=task_id,
            status="completed",
            result=result.result,
        )
    elif result.state == "FAILURE":
        return TaskStatusResponse(
            task_id=task_id,
            status="failed",
            result={"error": str(result.result)},
        )
    else:
        return TaskStatusResponse(task_id=task_id, status=result.state, result=None)
