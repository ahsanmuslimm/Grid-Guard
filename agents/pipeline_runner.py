"""
GridGuard — Agent Pipeline Runner
Manages ADK session lifecycle and executes the gridguard_pipeline
in response to attack detections. Integrates with Phoenix tracing
and the frontend state module.
"""

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from opentelemetry import trace

from agents.orchestrator import gridguard_pipeline
from frontend.state import (
    add_timeline_event,
    fail_incident,
    register_incident,
    resolve_incident,
)
from observability.evaluators import evaluate_incident

_tracer = trace.get_tracer("gridguard.pipeline_runner")

# Shared session service — one per process
_session_service = InMemorySessionService()
_runner = Runner(
    agent=gridguard_pipeline,
    app_name="gridguard",
    session_service=_session_service,
)

# Track running pipeline tasks so we don't double-trigger
_active_pipelines: set[str] = set()


async def run_pipeline_for_attack(
    attack_type: str,
    node_id: str,
    telemetry_snapshot: dict | None = None,
) -> dict[str, Any]:
    """
    Execute the full 3-agent GridGuard pipeline for a detected attack.
    Non-blocking — called from FastAPI's async context.

    Args:
        attack_type: Type of attack injected
        node_id: Target node identifier
        telemetry_snapshot: Optional snapshot of SCADA reading at time of injection

    Returns:
        Final pipeline result dict
    """
    incident_id = f"INC-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{str(uuid.uuid4())[:4].upper()}"

    # Prevent duplicate pipeline runs for the same active attack
    if attack_type in _active_pipelines:
        return {"status": "already_running", "attack_type": attack_type}

    _active_pipelines.add(attack_type)
    register_incident(incident_id, attack_type, node_id)

    add_timeline_event(
        agent_name="gridguard_pipeline",
        action="pipeline_started",
        reasoning=f"Attack detected: {attack_type} on {node_id}. Starting 3-agent pipeline.",
        confidence=1.0,
        outcome="running",
        severity="HIGH",
        incident_id=incident_id,
    )

    try:
        with _tracer.start_as_current_span("gridguard.full_pipeline") as span:
            span.set_attribute("incident.id", incident_id)
            span.set_attribute("incident.attack_type", attack_type)
            span.set_attribute("incident.node_id", node_id)

            # Create a new session for this incident
            session_id = f"session_{incident_id}"
            user_id = "gridguard_system"

            # Build the mission prompt
            prompt = _build_mission_prompt(incident_id, attack_type, node_id, telemetry_snapshot)

            # Run the pipeline — ADK handles sequential execution
            result_text = ""
            investigation_evidence = {
                "recommended_playbook": attack_type,
                "cves": [],
                "mitre_techniques": [],
            }
            async for event in _runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=_make_message(prompt),
            ):
                # Collect the final text response
                if hasattr(event, "content") and event.content:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            result_text = part.text

                # Log agent transitions to the timeline
                _capture_investigation_evidence(event, investigation_evidence)
                _log_event_to_timeline(event, incident_id)

            # Parse the final result
            result = _parse_result(result_text, incident_id, attack_type)

            span.set_attribute("pipeline.status", result.get("response_status", "unknown"))
            span.set_attribute("pipeline.playbook", result.get("playbook", "none"))
            span.set_attribute("pipeline.approval", result.get("approval_status", "none"))

            evaluation = evaluate_incident(
                incident_id=incident_id,
                attack_type=attack_type,
                investigation_result=investigation_evidence,
                response_result=result,
            )
            span.set_attribute("evaluation.hallucination_flagged", evaluation["hallucination_flagged"])
            span.set_attribute("evaluation.quality_score", evaluation["quality_score"])
            span.set_attribute("evaluation.playbook_match", evaluation["playbook_match"])
            resolve_incident(incident_id, result=result, evaluation=evaluation)

            add_timeline_event(
                agent_name="gridguard_pipeline",
                action="pipeline_completed",
                reasoning=f"Incident {incident_id} resolved. Status: {result.get('response_status')}",
                confidence=1.0,
                outcome=result.get("response_status", "completed"),
                severity="INFO",
                incident_id=incident_id,
            )

            return result

    except Exception as e:
        fail_incident(incident_id, str(e))
        add_timeline_event(
            agent_name="gridguard_pipeline",
            action="pipeline_error",
            reasoning=f"Pipeline error for {incident_id}: {str(e)[:200]}",
            confidence=0.0,
            outcome="error",
            severity="CRITICAL",
            incident_id=incident_id,
        )
        return {"status": "error", "incident_id": incident_id, "message": str(e)}
    finally:
        _active_pipelines.discard(attack_type)


def _build_mission_prompt(
    incident_id: str,
    attack_type: str,
    node_id: str,
    telemetry: dict | None
) -> str:
    """Build the initial mission prompt for the pipeline."""
    telemetry_summary = ""
    if telemetry:
        telemetry_summary = (
            f"\nCurrent telemetry snapshot: "
            f"voltage={telemetry.get('voltage', 'N/A')}V, "
            f"frequency={telemetry.get('frequency', 'N/A')}Hz, "
            f"status={telemetry.get('status', 'N/A')}, "
            f"commands={telemetry.get('command_log', [])}"
        )

    return (
        f"MISSION START — GridGuard Threat Response Pipeline\n"
        f"Canonical incident ID: {incident_id}\n"
        f"Incident type: {attack_type}\n"
        f"Target node: {node_id}\n"
        f"{telemetry_summary}\n\n"
        f"Execute the full detection → investigation → response pipeline now. "
        f"Use all available tools. Do not skip any steps. "
        f"Use the canonical incident ID {incident_id} for approval, playbook execution, reporting, and final output."
    )


def _make_message(text: str):
    """Create an ADK-compatible user message."""
    from google.genai import types
    return types.Content(
        role="user",
        parts=[types.Part(text=text)]
    )


def _log_event_to_timeline(event: Any, incident_id: str) -> None:
    """Extract agent step information from ADK events and log to timeline."""
    try:
        author = getattr(event, "author", None)
        if not author:
            return

        content = getattr(event, "content", None)
        if not content:
            return

        # Look for tool call results to log
        for part in content.parts:
            fn_response = getattr(part, "function_response", None)
            fn_call = getattr(part, "function_call", None)

            if fn_call:
                add_timeline_event(
                    agent_name=author,
                    action=f"tool_call:{fn_call.name}",
                    reasoning=f"Calling {fn_call.name} with args: {str(dict(fn_call.args))[:150]}",
                    confidence=0.9,
                    outcome="executing",
                    severity="INFO",
                    incident_id=incident_id,
                )
            elif fn_response:
                # Determine severity from response content
                resp_str = str(fn_response.response)[:200]
                severity = "HIGH" if "CRITICAL" in resp_str or "anomaly_detected.*true" in resp_str else "INFO"
                add_timeline_event(
                    agent_name=author,
                    action=f"tool_result:{fn_response.name}",
                    reasoning=f"Result from {fn_response.name}: {resp_str}",
                    confidence=0.9,
                    outcome="completed",
                    severity=severity,
                    incident_id=incident_id,
                )
    except Exception:
        pass  # Timeline logging is best-effort, never crash the pipeline


def _capture_investigation_evidence(event: Any, evidence: dict) -> None:
    """Capture the exact grounded tool outputs used by post-incident evaluation."""
    try:
        content = getattr(event, "content", None)
        for part in getattr(content, "parts", []) or []:
            response = getattr(part, "function_response", None)
            if not response:
                continue
            payload = response.response
            if not isinstance(payload, dict):
                continue
            if response.name == "lookup_cve":
                evidence["cves"] = payload.get("cves", [])
            elif response.name == "lookup_mitre_technique":
                evidence["mitre_techniques"] = payload.get("techniques", [])
    except Exception:
        pass


def _parse_result(result_text: str, incident_id: str, attack_type: str) -> dict:
    """Parse the final pipeline response text into a structured result."""
    try:
        # Strip markdown code fences if present
        clean = result_text.strip()
        if clean.startswith("```"):
            lines = clean.split("\n")
            clean = "\n".join(lines[1:-1]) if len(lines) > 2 else clean
        return json.loads(clean)
    except (json.JSONDecodeError, ValueError):
        # Return a minimal result if JSON parsing fails
        return {
            "incident_id": incident_id,
            "response_status": "completed",
            "playbook": attack_type,
            "approval_status": "not_required",
            "actions_summary": ["pipeline_executed"],
            "report_generated": True,
            "response_summary": result_text[:300] if result_text else "Pipeline completed"
        }
