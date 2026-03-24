import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, get_tenant_id
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.models.bundle import Bundle
from app.models.chat_message import ChatMessage
from app.models.finding import Finding
from app.models.user import User
from app.schemas.chat import ChatMessageRead, ChatRequest

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/bundles", tags=["chat"])

_MAX_HISTORY = 20  # messages to send as context (keeps tokens bounded)
_MAX_MESSAGE_LEN = 2000


async def _get_bundle_for_tenant(
    bundle_id: uuid.UUID, tenant_id: str, db: AsyncSession
) -> Bundle:
    result = await db.execute(
        select(Bundle).where(Bundle.id == bundle_id, Bundle.tenant_id == tenant_id)
    )
    bundle = result.scalar_one_or_none()
    if bundle is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Bundle not found"
        )
    return bundle


async def _get_finding_for_bundle(
    finding_id: uuid.UUID, bundle_id: uuid.UUID, db: AsyncSession
) -> Finding:
    result = await db.execute(
        select(Finding).where(Finding.id == finding_id, Finding.bundle_id == bundle_id)
    )
    finding = result.scalar_one_or_none()
    if finding is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found"
        )
    return finding


@router.get(
    "/{bundle_id}/findings/{finding_id}/chat",
    response_model=list[ChatMessageRead],
)
async def list_chat(
    bundle_id: uuid.UUID,
    finding_id: uuid.UUID,
    tenant_id: str = Depends(get_tenant_id),
    db: AsyncSession = Depends(get_db),
) -> list[ChatMessageRead]:
    await _get_bundle_for_tenant(bundle_id, tenant_id, db)
    await _get_finding_for_bundle(finding_id, bundle_id, db)

    result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.finding_id == finding_id)
        .order_by(ChatMessage.created_at.asc())
    )
    messages = result.scalars().all()
    return [ChatMessageRead.model_validate(m) for m in messages]


@router.post(
    "/{bundle_id}/findings/{finding_id}/chat",
    response_model=ChatMessageRead,
    status_code=status.HTTP_201_CREATED,
)
@limiter.limit("30/minute")
async def send_chat_message(
    request: Request,
    bundle_id: uuid.UUID,
    finding_id: uuid.UUID,
    body: ChatRequest,
    tenant_id: str = Depends(get_tenant_id),
    current_user: User | None = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ChatMessageRead:
    if not settings.AI_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI features are not enabled",
        )

    await _get_bundle_for_tenant(bundle_id, tenant_id, db)
    finding = await _get_finding_for_bundle(finding_id, bundle_id, db)

    message = body.message.strip()
    if not message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty"
        )
    if len(message) > _MAX_MESSAGE_LEN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Message exceeds {_MAX_MESSAGE_LEN} characters",
        )

    actor = current_user.email if current_user else "anonymous"

    # Persist user message
    user_msg = ChatMessage(
        finding_id=finding_id,
        bundle_id=bundle_id,
        role="user",
        content=message,
        actor=actor,
    )
    db.add(user_msg)
    await db.flush()
    await db.refresh(user_msg)

    # Load chat history for context
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.finding_id == finding_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(_MAX_HISTORY)
    )
    history = list(reversed(history_result.scalars().all()))

    # Build message list for API (exclude the message we just saved — it's already last)
    api_messages = [{"role": m.role, "content": m.content} for m in history]

    # Build guardrailed system prompt
    from app.ai.prompts import build_chat_system_prompt

    system_prompt = build_chat_system_prompt(
        finding, finding.ai_explanation, finding.ai_remediation
    )

    # Call AI
    from app.ai.client import get_client

    try:
        client = get_client()
        response = client.messages.create(
            model=settings.AI_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=api_messages,
        )
        reply = response.content[0].text
    except Exception as exc:
        logger.error("chat_ai_error", finding_id=str(finding_id), error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI response failed",
        ) from exc

    # Persist assistant reply
    assistant_msg = ChatMessage(
        finding_id=finding_id,
        bundle_id=bundle_id,
        role="assistant",
        content=reply,
        actor="assistant",
    )
    db.add(assistant_msg)
    await db.flush()
    await db.refresh(assistant_msg)

    logger.info(
        "chat_message_sent", finding_id=str(finding_id), bundle_id=str(bundle_id)
    )
    return ChatMessageRead.model_validate(assistant_msg)
