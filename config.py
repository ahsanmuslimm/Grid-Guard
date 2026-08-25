"""Runtime environment normalization shared by local and cloud entry points."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def configure_environment() -> None:
    """Load ``.env`` and normalize current Google ADK environment names."""
    load_dotenv()
    region = os.getenv("GOOGLE_CLOUD_LOCATION") or os.getenv("GOOGLE_CLOUD_REGION")
    if region:
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", region)
        os.environ.setdefault("GOOGLE_CLOUD_REGION", region)
    if os.getenv("GOOGLE_CLOUD_PROJECT"):
        os.environ.setdefault("GOOGLE_GENAI_USE_ENTERPRISE", "1")

    # ADC is preferred for local development. A stale key path would otherwise
    # prevent google-auth from falling back to `gcloud auth application-default`.
    credentials = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
    if credentials and not Path(credentials).expanduser().is_file():
        os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

