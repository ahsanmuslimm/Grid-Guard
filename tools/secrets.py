"""
GridGuard — GCP Secret Manager Utility
All API keys retrieved from Secret Manager at runtime.
Zero hardcoded credentials anywhere in codebase.
"""

import os
import functools
from typing import Optional


@functools.lru_cache(maxsize=32)
def get_secret(secret_id: str, version: str = "latest") -> str:
    """
    Retrieve a secret from GCP Secret Manager.
    Results are cached in-process to minimize API calls.

    Args:
        secret_id: The secret name in Secret Manager (e.g. 'PHOENIX_API_KEY')
        version: Secret version, defaults to 'latest'

    Returns:
        The secret value as a string.

    Raises:
        RuntimeError: If the secret cannot be retrieved and no env fallback exists.
    """
    try:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
        project = os.getenv("GOOGLE_CLOUD_PROJECT", "gridguard-agent-2026")
        name = f"projects/{project}/secrets/{secret_id}/versions/{version}"

        response = client.access_secret_version(request={"name": name})
        value = response.payload.data.decode("UTF-8").strip()

        if value:
            return value

    except Exception as e:
        print(f"[secrets] Secret Manager unavailable for '{secret_id}': {e}")

    # Fallback to environment variable (local development)
    env_value = os.getenv(secret_id, "")
    if env_value:
        return env_value

    raise RuntimeError(
        f"Secret '{secret_id}' not found in Secret Manager or environment. "
        f"Run: echo -n 'YOUR_KEY' | gcloud secrets create {secret_id} --data-file=-"
    )


def get_secret_optional(secret_id: str, default: str = "") -> str:
    """
    Like get_secret() but returns default instead of raising on missing key.
    Use for optional integrations (e.g. NVD_API_KEY improves rate limits but isn't required).
    """
    try:
        return get_secret(secret_id)
    except (RuntimeError, Exception):
        return default
