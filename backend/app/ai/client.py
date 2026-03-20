import anthropic

from app.core.config import settings


def get_client() -> anthropic.Anthropic:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    if settings.LANGSMITH_API_KEY:
        try:
            from langsmith.wrappers import wrap_anthropic
            client = wrap_anthropic(client)
        except ImportError:
            pass
    return client
