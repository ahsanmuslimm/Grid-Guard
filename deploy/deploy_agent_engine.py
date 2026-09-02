"""Deploy the three-agent orchestrator to Vertex AI Agent Engine."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Phoenix MCP is hosted by Cloud Run, which includes Node.js/npx. Agent Engine
# does not provide that stdio sidecar.
os.environ["GRIDGUARD_ENABLE_PHOENIX_MCP"] = "false"

from config import configure_environment

configure_environment()

import vertexai
from vertexai import agent_engines

from agents.orchestrator import gridguard_pipeline


def main() -> None:
    project = os.environ.get("GOOGLE_CLOUD_PROJECT", "").strip()
    location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1").strip()
    if not project:
        raise SystemExit("GOOGLE_CLOUD_PROJECT is required")

    service_account = os.getenv(
        "GRIDGUARD_SERVICE_ACCOUNT",
        f"gridguard-sa@{project}.iam.gserviceaccount.com",
    )
    vertexai.init(project=project, location=location)
    app = agent_engines.AdkApp(agent=gridguard_pipeline, app_name="gridguard")
    remote = agent_engines.create(
        agent_engine=app,
        requirements=str(ROOT / "requirements-agent-engine.txt"),
        extra_packages=[
            str(ROOT / "config.py"),
            str(ROOT / "agents"),
            str(ROOT / "tools"),
            str(ROOT / "observability"),
            str(ROOT / "frontend"),
            str(ROOT / "playbooks"),
        ],
        display_name="GridGuard Multi-Agent Pipeline",
        description="Detection, investigation, and response for SCADA cyber incidents",
        env_vars={
            "GOOGLE_CLOUD_PROJECT": project,
            "GOOGLE_CLOUD_LOCATION": location,
            "GOOGLE_GENAI_USE_VERTEXAI": "true",
            "GOOGLE_GENAI_USE_ENTERPRISE": "1",
            "GRIDGUARD_MODEL": os.getenv("GRIDGUARD_MODEL", "gemini-3-flash-preview"),
            "GRIDGUARD_ENABLE_PHOENIX_MCP": "false",
            "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        },
        service_account=service_account,
        min_instances=0,
        max_instances=1,
    )
    print(f"Agent Engine deployed: {remote.resource_name}")


if __name__ == "__main__":
    main()
