"""
GridGuard — Arize Phoenix Observability Setup
MUST be imported before any agent execution.
Registers Phoenix as the OTel tracer provider and auto-instruments Gemini/VertexAI.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def initialize_phoenix():
    """
    Initialize Arize Phoenix tracing.
    Call this once at application startup before any agent runs.
    Returns the configured tracer instance.
    """
    from phoenix.otel import register
    from opentelemetry import trace

    phoenix_api_key = _get_phoenix_api_key()
    phoenix_base_url = os.getenv("PHOENIX_BASE_URL", "https://app.phoenix.arize.com")

    # Register Phoenix as the OTel tracing backend
    tracer_provider = register(
        project_name="gridguard",
        endpoint=f"{phoenix_base_url}/v1/traces",
        headers={"api_key": phoenix_api_key},
    )

    # Auto-instrument Vertex AI (ADK uses Vertex AI under the hood)
    try:
        from openinference.instrumentation.vertexai import VertexAIInstrumentor
        VertexAIInstrumentor().instrument(tracer_provider=tracer_provider)
        print("[OK] VertexAI auto-instrumentation enabled")
    except Exception as e:
        print(f"[SKIP] VertexAI instrumentation: {e}")

    # Auto-instrument direct Gemini API calls
    try:
        from openinference.instrumentation.google_genai import GoogleGenAIInstrumentor
        GoogleGenAIInstrumentor().instrument(tracer_provider=tracer_provider)
        print("[OK] GoogleGenAI auto-instrumentation enabled")
    except Exception as e:
        print(f"[SKIP] GoogleGenAI instrumentation: {e}")

    tracer = trace.get_tracer("gridguard")
    print(f"[OK] Phoenix tracing initialized -> {phoenix_base_url}/projects/gridguard")
    return tracer


def _get_phoenix_api_key() -> str:
    """Get Phoenix API key — tries Secret Manager first, falls back to env var."""
    # Try GCP Secret Manager in production
    if os.getenv("GRIDGUARD_ENV", "development") != "development":
        try:
            from tools.secrets import get_secret
            return get_secret("PHOENIX_API_KEY")
        except Exception:
            pass

    # Fall back to environment variable (local dev)
    key = os.getenv("PHOENIX_API_KEY", "")
    if not key:
        print("[WARN] PHOENIX_API_KEY not set - traces will not be sent to Phoenix")
    return key


# Initialize on import — module-level tracer for use across all tools
try:
    tracer = initialize_phoenix()
except Exception as e:
    # Graceful degradation — app runs without observability if Phoenix is unavailable
    print(f"[WARN] Phoenix initialization failed: {e} - running without tracing")
    from opentelemetry import trace
    tracer = trace.get_tracer("gridguard_noop")
