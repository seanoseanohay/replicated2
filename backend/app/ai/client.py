import anthropic

from app.core.config import settings


def get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
