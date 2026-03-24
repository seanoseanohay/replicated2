"""
Shared fixtures for LLM eval tests.

All eval tests require ANTHROPIC_API_KEY to be set and are skipped otherwise.
Run evals explicitly with:  pytest -m eval
Exclude them with:          pytest -m "not eval"
"""

import pytest
from app.core.config import settings


@pytest.fixture(autouse=True)
def enable_ai(monkeypatch):
    """Temporarily enable AI for every eval test."""
    monkeypatch.setattr(settings, "AI_ENABLED", True)
