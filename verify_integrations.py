"""Live integration checks for Phoenix MCP, Phoenix API, NVD, and Gemini.

Credential values are never printed. Gemini can use either the local Developer
API key or Vertex AI/Application Default Credentials.
"""

from __future__ import annotations

import argparse
import asyncio
import os

from config import configure_environment

configure_environment()


def _configured(name: str) -> bool:
    return bool(os.getenv(name, "").strip())


def check_configuration(*, gemini: bool, phoenix: bool, nvd: bool) -> bool:
    required: list[str] = []
    optional = ["GRIDGUARD_MODEL"]
    if gemini:
        vertex_mode = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "false").lower() == "true"
        required.append("GOOGLE_CLOUD_PROJECT" if vertex_mode else "GOOGLE_API_KEY")
    if phoenix:
        required.extend(["PHOENIX_API_KEY", "PHOENIX_BASE_URL"])
    if nvd:
        optional.append("NVD_API_KEY")
    print("Configuration (values hidden):")
    for name in required + optional:
        print(f"  {'OK' if _configured(name) else 'MISSING':7} {name}")
    return all(_configured(name) for name in required)


def check_phoenix_api() -> bool:
    from observability.evaluators import get_phoenix_stats

    # An explicit verification command must probe Phoenix even when runtime
    # tracing is disabled for normal local application runs.
    stats = get_phoenix_stats(respect_tracing_setting=False)
    print(
        "Phoenix API: "
        f"status={stats['status']} project={stats.get('project_name')} "
        f"traces_today={stats['total_traces']}"
    )
    if stats.get("error"):
        print(f"  error_type={stats['error']}")
    if stats.get("status_code"):
        print(f"  http_status={stats['status_code']}")
    return stats["status"] == "connected"


async def check_phoenix_mcp() -> bool:
    from observability.phoenix_mcp import get_phoenix_mcp_status, get_phoenix_mcp_toolset

    toolset = get_phoenix_mcp_toolset()
    if toolset is None:
        print(f"Phoenix MCP: unavailable ({get_phoenix_mcp_status()['reason']})")
        return False
    try:
        tools = await toolset.get_tools()
        names = sorted(tool.name for tool in tools)
        print(f"Phoenix MCP: connected ({len(names)} tools)")
        print("  " + ", ".join(names))
        return bool(names)
    except Exception as exc:
        print(f"Phoenix MCP: failed ({type(exc).__name__}: {exc})")
        return False
    finally:
        await toolset.close()


def check_nvd() -> bool:
    from tools.cve_lookup import lookup_cve

    result = lookup_cve("ransomware", "SCADA")
    print(f"NVD: source={result.get('source')} matches={len(result.get('cves', []))}")
    return result.get("source") == "nvd_live"


async def check_gemini(attack_type: str) -> bool:
    from agents.pipeline_runner import run_pipeline_for_attack
    from simulator.scada_simulator import simulator

    injection = simulator.inject_attack(attack_type, node_id="SUBSTATION_005", duration_ticks=3)
    result = await run_pipeline_for_attack(
        attack_type=attack_type,
        node_id=injection["target_node"],
        telemetry_snapshot=injection["telemetry_snapshot"],
    )
    status = result.get("response_status", result.get("status"))
    print(f"Gemini pipeline: attack={attack_type} status={status}")
    if result.get("message"):
        print(f"  message={result['message']}")
    return status not in {None, "error"}


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phoenix-api", action="store_true")
    parser.add_argument("--phoenix-mcp", action="store_true")
    parser.add_argument("--nvd", action="store_true")
    parser.add_argument("--gemini", action="store_true")
    parser.add_argument(
        "--attack",
        choices=["ransomware", "unauthorized_access", "ddos", "data_exfiltration"],
        default="ddos",
        help="Use an automatic-response attack unless an operator is ready to approve.",
    )
    args = parser.parse_args()
    selected = args.phoenix_api or args.phoenix_mcp or args.nvd or args.gemini
    check_configuration(
        gemini=args.gemini,
        phoenix=(not selected or args.phoenix_api or args.phoenix_mcp),
        nvd=(not selected or args.nvd),
    )
    results: list[bool] = []
    if not selected or args.phoenix_api:
        results.append(check_phoenix_api())
    if not selected or args.phoenix_mcp:
        results.append(await check_phoenix_mcp())
    if not selected or args.nvd:
        results.append(check_nvd())
    if args.gemini:
        results.append(await check_gemini(args.attack))
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
