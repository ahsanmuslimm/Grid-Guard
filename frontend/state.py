"""
GridGuard — Shared Frontend State
In-memory state store bridging the agent pipeline and the WebSocket dashboard.
Thread-safe via simple dict operations (FastAPI runs in async context).
"""

import uuid
from datetime import datetime, timezone
from typing import Any

# ── Live threat feed (pushed to WebSocket clients every 2s) ─────────────────
_latest_threats: list[dict] = []
_node_states: dict[str, str] = {}

# ── Agent decision timeline (appended by agent pipeline) ────────────────────
_decision_timeline: list[dict] = []

# ── Human approval gate ──────────────────────────────────────────────────────
_pending_approvals: dict[str, dict] = {}
_approval_results: dict[str, str] = {}

# ── Active incidents ─────────────────────────────────────────────────────────
_active_incidents: dict[str, dict] = {}


# ── Threat feed API ──────────────────────────────────────────────────────────

def update_node_states(states: dict[str, str]) -> None:
    """Called by simulator to update node health states."""
    global _node_states
    _node_states = dict(states)


def push_threat_event(telemetry: dict) -> None:
    """Called by simulator callback on each tick to update live threat data."""
    global _latest_threats
    _latest_threats = _latest_threats[-49:]  # Keep last 50
    _latest_threats.append({
        "timestamp": telemetry.get("timestamp", datetime.now(timezone.utc).isoformat()),
        "node_id": telemetry.get("node_id", "UNKNOWN"),
        "status": telemetry.get("status", "NORMAL"),
        "attack_type": telemetry.get("attack_type"),
        "voltage": telemetry.get("voltage"),
        "frequency": telemetry.get("frequency"),
    })


def get_dashboard_snapshot() -> dict[str, Any]:
    """Return the full dashboard state payload for WebSocket broadcast."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "node_states": _node_states,
        "recent_threats": _latest_threats[-10:],
        "timeline": _decision_timeline[-20:],
        "pending_approvals": list(_pending_approvals.values()),
        "active_incidents": list(_active_incidents.values()),
    }


# ── Decision timeline API ────────────────────────────────────────────────────

def add_timeline_event(
    agent_name: str,
    action: str,
    reasoning: str,
    confidence: float,
    outcome: str,
    severity: str = "INFO"
) -> None:
    """Append an agent action to the decision timeline."""
    _decision_timeline.append({
        "id": str(uuid.uuid4())[:8],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agent": agent_name,
        "action": action,
        "reasoning": reasoning[:300],  # Truncate for display
        "confidence": round(confidence, 2),
        "outcome": outcome,
        "severity": severity
    })
    # Cap at 200 events
    if len(_decision_timeline) > 200:
        _decision_timeline.pop(0)


def get_timeline() -> list[dict]:
    return list(reversed(_decision_timeline))


def get_all_node_states() -> dict[str, str]:
    """Return all node states for the grid map."""
    return dict(_node_states)


# ── Human approval gate API ──────────────────────────────────────────────────

def push_approval_request(payload: dict) -> None:
    """Push a CRITICAL threat approval request to the dashboard."""
    incident_id = payload["incident_id"]
    _pending_approvals[incident_id] = payload

    # Log to timeline
    add_timeline_event(
        agent_name="response_agent",
        action="requesting_human_approval",
        reasoning=f"CRITICAL threat detected — awaiting operator approval for: {payload.get('recommended_playbook')}",
        confidence=1.0,
        outcome="pending_approval",
        severity="CRITICAL"
    )


def get_approval_result(incident_id: str) -> str | None:
    """Return approval result if operator has responded, else None."""
    return _approval_results.get(incident_id)


def set_approval_result(incident_id: str, result: str) -> None:
    """Called by POST /api/approve/{id} when operator responds."""
    _approval_results[incident_id] = result
    # Remove from pending
    _pending_approvals.pop(incident_id, None)

    add_timeline_event(
        agent_name="operator",
        action=f"approval_{result}",
        reasoning=f"Operator {result} the response for incident {incident_id}",
        confidence=1.0,
        outcome=result,
        severity="HIGH" if result == "approved" else "MEDIUM"
    )


# ── Incident tracking ────────────────────────────────────────────────────────

def register_incident(incident_id: str, attack_type: str, node_id: str) -> None:
    _active_incidents[incident_id] = {
        "incident_id": incident_id,
        "attack_type": attack_type,
        "node_id": node_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "status": "investigating"
    }


def resolve_incident(incident_id: str) -> None:
    if incident_id in _active_incidents:
        _active_incidents[incident_id]["status"] = "resolved"
        _active_incidents[incident_id]["resolved_at"] = datetime.now(timezone.utc).isoformat()
