"""
GridGuard — Application Entry Point
Initializes all systems and starts the FastAPI dashboard server.
Import order matters: Phoenix MUST be initialized before any agent runs.
"""

import os
from config import configure_environment

# Load environment variables FIRST (.env for local dev)
configure_environment()



# In production — pull secrets from GCP Secret Manager and inject into env
# This runs before Phoenix init so the API key is available
def _inject_gcp_secrets() -> None:
    """Pull secrets from Secret Manager and set as env vars (production only)."""
    if os.getenv("GRIDGUARD_ENV", "development") == "development":
        return
    try:
        from tools.secrets import get_secret_optional
        for secret_id in ("PHOENIX_API_KEY", "NVD_API_KEY"):
            if not os.getenv(secret_id):  # Don't overwrite if already set via --set-env-vars
                value = get_secret_optional(secret_id)
                if value:
                    os.environ[secret_id] = value
                    print(f"[OK] Secret Manager: {secret_id} loaded")
    except Exception as e:
        print(f"[WARN] Secret Manager unavailable: {e} - using env vars")

_inject_gcp_secrets()

# Initialize Arize Phoenix tracing BEFORE importing agents
# This ensures all agent calls are captured from the first run
from observability.phoenix_setup import tracer  # noqa: E402 — intentional import order

# Now import everything else
import uvicorn  # noqa: E402
from frontend.main import app  # noqa: E402


def startup() -> None:
    """Initialize all GridGuard systems."""
    print("\n" + "=" * 60)
    print("  GRIDGUARD - Autonomous Energy Grid Threat Response")
    print("  Google Cloud Rapid Agent Hackathon - Arize Track")
    print("=" * 60 + "\n")

    # FastAPI lifespan owns simulator startup in local and Cloud Run modes.
    print("[OK] SCADA Simulator will start with FastAPI - 12 nodes\n")

    env = os.getenv("GRIDGUARD_ENV", "development")
    port = int(os.getenv("PORT", "8080"))
    print(f"[OK] Environment: {env}")
    print(f"[OK] Dashboard: http://localhost:{port}")
    phoenix_base = os.getenv("PHOENIX_BASE_URL", "https://app.phoenix.arize.com")
    phoenix_project = os.getenv("PHOENIX_PROJECT_NAME", "gridguard")
    print(f"[OK] Phoenix endpoint: {phoenix_base}")
    print(f"[OK] Phoenix project:  {phoenix_project}\n")


if __name__ == "__main__":
    startup()
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(
        "frontend.main:app",
        host="0.0.0.0",
        port=port,
        reload=os.getenv("GRIDGUARD_ENV") == "development",
        log_level=os.getenv("LOG_LEVEL", "info").lower(),
    )
