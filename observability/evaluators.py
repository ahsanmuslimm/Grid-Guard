"""Grounding and response-quality evaluation with Phoenix annotations."""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_incident_evaluations: list[dict[str, Any]] = []
_CVE_PATTERN = re.compile(r"CVE-\d{4}-\d{4,}", re.IGNORECASE)
_MITRE_PATTERN = re.compile(r"T\d{4}(?:\.\d{3})?", re.IGNORECASE)


def _reference_id(item: Any, *keys: str) -> str:
    if isinstance(item, str):
        return item.strip().upper()
    if isinstance(item, dict):
        for key in keys:
            value = item.get(key)
            if value:
                return str(value).strip().upper()
    return ""


def evaluate_incident(
    incident_id: str,
    attack_type: str,
    investigation_result: dict | None,
    response_result: dict | None,
) -> dict[str, Any]:
    """Compare agent claims with exact threat-intelligence tool outputs."""
    investigation = investigation_result or {}
    response = response_result or {}

    grounded_cves = {
        value for value in (
            _reference_id(item, "id", "cve_id") for item in investigation.get("cves", [])
        ) if value
    }
    grounded_mitre = {
        value for value in (
            _reference_id(item, "technique_id", "id")
            for item in investigation.get("mitre_techniques", [])
        ) if value
    }
    claimed_cves = {
        value for value in (
            _reference_id(item, "id", "cve_id")
            for item in investigation.get("claimed_cves", [])
        ) if value
    }
    claimed_mitre = {
        value for value in (
            _reference_id(item, "technique_id", "id")
            for item in investigation.get("claimed_mitre_techniques", [])
        ) if value
    }

    malformed_cves = sorted(value for value in claimed_cves if not _CVE_PATTERN.fullmatch(value))
    malformed_mitre = sorted(value for value in claimed_mitre if not _MITRE_PATTERN.fullmatch(value))
    ungrounded_cves = sorted(claimed_cves - grounded_cves)
    ungrounded_mitre = sorted(claimed_mitre - grounded_mitre)
    hallucination_flagged = bool(
        malformed_cves or malformed_mitre or ungrounded_cves or ungrounded_mitre
    )

    selected_playbook = response.get("playbook") or investigation.get("recommended_playbook")
    playbook_match = selected_playbook == attack_type
    response_status = response.get("response_status", response.get("status"))
    # Only a successfully executed response counts as completed. Escalated,
    # rejected, timed-out, and failed incidents did not apply the playbook.
    completed = response_status == "executed"
    quality_score = round(
        (0.5 if playbook_match else 0.0)
        + (0.3 if completed else 0.0)
        + (0.2 if not hallucination_flagged else 0.0),
        2,
    )

    claim_count = len(claimed_cves) + len(claimed_mitre)
    grounded_claim_count = len(claimed_cves & grounded_cves) + len(claimed_mitre & grounded_mitre)
    evaluation = {
        "incident_id": incident_id,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "hallucination_flagged": hallucination_flagged,
        "malformed_cves": malformed_cves,
        "malformed_mitre_techniques": malformed_mitre,
        "ungrounded_cves": ungrounded_cves,
        "ungrounded_mitre_techniques": ungrounded_mitre,
        "grounded_reference_count": len(grounded_cves) + len(grounded_mitre),
        "claimed_reference_count": claim_count,
        "grounded_claim_count": grounded_claim_count,
        "claim_capture_status": "captured" if claim_count else "no_references_claimed",
        "playbook_match": playbook_match,
        "selected_playbook": selected_playbook,
        "response_completed": completed,
        "quality_score": quality_score,
        "explanation": (
            "All claimed CVE and MITRE references were returned by the lookup tools."
            if not hallucination_flagged
            else "The agent claimed one or more malformed or tool-ungrounded threat references."
        ),
    }
    _incident_evaluations.append(evaluation)
    if len(_incident_evaluations) > 100:
        _incident_evaluations.pop(0)
    return evaluation


def get_incident_evaluations() -> list[dict[str, Any]]:
    return list(reversed(_incident_evaluations))


def publish_evaluation_annotations(span_id: str, evaluation: dict[str, Any]) -> str:
    """Attach grounding and quality evaluations to a Phoenix root span."""
    tracing_enabled = os.getenv(
        "GRIDGUARD_ENABLE_PHOENIX_TRACING", "true"
    ).strip().lower() in {"1", "true", "yes", "on"}
    if not tracing_enabled:
        return "skipped_tracing_disabled"
    api_key = os.getenv("PHOENIX_API_KEY", "").strip()
    if not api_key or not span_id:
        return "skipped_not_configured"
    try:
        from phoenix.client import Client

        client = Client(
            base_url=os.getenv("PHOENIX_BASE_URL", "https://app.phoenix.arize.com").rstrip("/"),
            api_key=api_key,
        )
        hallucinated = bool(evaluation["hallucination_flagged"])
        client.spans.add_span_annotation(
            span_id=span_id,
            annotation_name="hallucination",
            annotator_kind="CODE",
            label="hallucinated" if hallucinated else "grounded",
            score=0.0 if hallucinated else 1.0,
            explanation=evaluation["explanation"],
            metadata={"incident_id": evaluation["incident_id"], "evaluator": "gridguard-grounding-v2"},
            identifier="gridguard-grounding-v2",
            sync=False,
        )
        client.spans.add_span_annotation(
            span_id=span_id,
            annotation_name="response_quality",
            annotator_kind="CODE",
            label="pass" if evaluation["quality_score"] >= 0.8 else "review",
            score=float(evaluation["quality_score"]),
            explanation=(
                f"playbook_match={evaluation['playbook_match']}; "
                f"response_completed={evaluation['response_completed']}; "
                f"grounded={not hallucinated}"
            ),
            metadata={"incident_id": evaluation["incident_id"], "evaluator": "gridguard-quality-v2"},
            identifier="gridguard-quality-v2",
            sync=False,
        )
        return "submitted"
    except Exception as exc:
        return f"error:{type(exc).__name__}"


def _field(item: Any, key: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(key, default)
    return getattr(item, key, default)


def get_phoenix_stats(*, respect_tracing_setting: bool = True) -> dict[str, Any]:
    """Fetch real Phoenix trace and evaluation statistics for the dashboard."""
    api_key = os.getenv("PHOENIX_API_KEY", "").strip()
    base_url = os.getenv("PHOENIX_BASE_URL", "https://app.phoenix.arize.com").rstrip("/")
    project = os.getenv("PHOENIX_PROJECT_NAME", "gridguard")
    tracing_enabled = os.getenv(
        "GRIDGUARD_ENABLE_PHOENIX_TRACING", "true"
    ).strip().lower() in {"1", "true", "yes", "on"}
    if respect_tracing_setting and not tracing_enabled:
        return _local_phoenix_stats(base_url, "disabled")
    if not api_key:
        return _local_phoenix_stats(base_url, "disconnected")

    try:
        from phoenix.client import Client

        client = Client(base_url=base_url, api_key=api_key)
        start_of_day = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        spans = client.spans.get_spans(
            project_identifier=project,
            start_time=start_of_day,
            limit=1000,
            timeout=8,
        )
        trace_ids = {
            _field(_field(span, "context", {}), "trace_id", "") for span in spans
        }
        trace_ids.discard("")
        annotations = client.spans.get_span_annotations(
            spans=spans,
            project_identifier=project,
            include_annotation_names=["hallucination", "response_quality"],
            limit=1000,
            timeout=8,
        ) if spans else []

        hallucination_flags = 0
        quality_scores: list[float] = []
        for annotation in annotations:
            name = _field(annotation, "name", "")
            result = _field(annotation, "result", {}) or {}
            label = _field(result, "label", "")
            score = _field(result, "score")
            if name == "hallucination" and label == "hallucinated":
                hallucination_flags += 1
            if name == "response_quality" and isinstance(score, (int, float)):
                quality_scores.append(float(score))

        return {
            "total_traces": len(trace_ids),
            "hallucination_flags": hallucination_flags,
            "avg_quality_score": round(sum(quality_scores) / len(quality_scores), 2) if quality_scores else 0.0,
            "phoenix_url": base_url,
            "project_name": project,
            "status": "connected",
        }
    except Exception as exc:
        stats = _local_phoenix_stats(base_url, "disconnected")
        stats["error"] = type(exc).__name__
        response = getattr(exc, "response", None)
        status_code = getattr(response, "status_code", None)
        if status_code is not None:
            stats["status_code"] = int(status_code)
        return stats


def _local_phoenix_stats(base_url: str, status: str) -> dict[str, Any]:
    local_scores = [item["quality_score"] for item in _incident_evaluations]
    return {
        "total_traces": len(_incident_evaluations),
        "hallucination_flags": sum(
            1 for item in _incident_evaluations if item["hallucination_flagged"]
        ),
        "avg_quality_score": round(sum(local_scores) / len(local_scores), 2) if local_scores else 0.0,
        "phoenix_url": base_url,
        "project_name": os.getenv("PHOENIX_PROJECT_NAME", "gridguard"),
        "status": "local" if _incident_evaluations else status,
    }
