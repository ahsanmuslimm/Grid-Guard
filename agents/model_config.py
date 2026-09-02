"""Shared Gemini configuration for GridGuard agents."""

from __future__ import annotations

import os

from google.adk.models.google_llm import Gemini
from google.genai import types


def build_gridguard_model() -> Gemini:
    """Create a Gemini client with retries for transient capacity failures."""
    return Gemini(
        model=os.getenv("GRIDGUARD_MODEL", "gemini-3.6-flash"),
        retry_options=types.HttpRetryOptions(
            attempts=6,
            initial_delay=2.0,
            max_delay=30.0,
            exp_base=2.0,
            jitter=0.5,
            http_status_codes=[429, 500, 502, 503, 504],
        ),
    )
