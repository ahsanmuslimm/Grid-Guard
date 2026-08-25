"""Arize Phoenix MCP toolset for the ADK response agent.

The Phoenix MCP server is started over stdio with ``npx``. Integration is
optional at runtime so GridGuard can still contain threats when Node.js, the
API key, or network access is temporarily unavailable.
"""

from __future__ import annotations

import os
import shutil
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_toolset: Any | None = None
_status: dict[str, str | bool] = {
    "enabled": False,
    "configured": False,
    "reason": "not_initialized",
}


def _is_enabled() -> bool:
    value = os.getenv("GRIDGUARD_ENABLE_PHOENIX_MCP", "true")
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _read_only_tool(tool: Any, readonly_context: Any = None) -> bool:
    """Expose only Phoenix inspection tools to the response agent."""
    del readonly_context
    name = str(getattr(tool, "name", "")).lower()
    read_prefixes = ("get", "list", "read", "search", "query", "fetch", "inspect", "show")
    mutation_words = ("create", "update", "delete", "add", "log", "annotate", "upload", "run")
    return name.startswith(read_prefixes) and not any(word in name for word in mutation_words)


def get_phoenix_mcp_toolset() -> Any | None:
    """Return a lazily configured Phoenix MCP toolset, or ``None``."""
    global _toolset, _status
    if _toolset is not None:
        return _toolset
    if not _is_enabled():
        _status = {"enabled": False, "configured": False, "reason": "disabled_by_environment"}
        return None

    api_key = os.getenv("PHOENIX_API_KEY", "").strip()
    if not api_key:
        _status = {"enabled": True, "configured": False, "reason": "missing_api_key"}
        return None

    npx = shutil.which("npx")
    if not npx:
        _status = {"enabled": True, "configured": False, "reason": "npx_not_found"}
        return None

    try:
        from google.adk.tools.mcp_tool import StdioConnectionParams
        from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
        from mcp import StdioServerParameters

        base_url = os.getenv("PHOENIX_BASE_URL", "https://app.phoenix.arize.com").rstrip("/")
        server_env = dict(os.environ)
        server_env["PHOENIX_API_KEY"] = api_key
        server_env["PHOENIX_BASE_URL"] = base_url
        _toolset = McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command=npx,
                    args=[
                        "-y",
                        "@arizeai/phoenix-mcp@latest",
                        "--baseUrl",
                        base_url,
                        "--apiKey",
                        api_key,
                    ],
                    env=server_env,
                ),
                timeout=90,
            ),
            tool_name_prefix="phoenix",
            tool_filter=_read_only_tool,
        )
        _status = {"enabled": True, "configured": True, "reason": "ready"}
        return _toolset
    except Exception as exc:
        _status = {
            "enabled": True,
            "configured": False,
            "reason": f"configuration_error:{type(exc).__name__}",
        }
        return None


def get_phoenix_mcp_status() -> dict[str, str | bool]:
    """Return non-secret MCP configuration status for health endpoints."""
    if _status["reason"] == "not_initialized":
        get_phoenix_mcp_toolset()
    return dict(_status)
