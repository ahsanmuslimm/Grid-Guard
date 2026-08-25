"""
GridGuard — Detection Sub-Agent
Monitors SCADA telemetry for anomalies using Gemini reasoning.
Writes detection result to session state via output_key.
"""

import os

from google.adk.agents import LlmAgent
from tools.scada_reader import (
    read_scada_telemetry,
    check_voltage_anomaly,
    check_access_patterns,
    check_command_sequences,
)

detection_agent = LlmAgent(
    name="detection_agent",
    model=os.getenv("GRIDGUARD_MODEL", "gemini-3-flash-preview"),
    description="Monitors SCADA telemetry for anomalies and cyber threats in energy grid infrastructure",
    instruction="""
    You are a SCADA anomaly detection specialist for critical energy infrastructure.
    Your mission is to determine whether the current telemetry indicates a cyber threat.

    PROCEDURE — execute ALL steps in order:

    1. Call read_scada_telemetry to get the current grid readings. If the
       mission prompt contains a telemetry snapshot, pass that complete snapshot
       to the tool (Agent Engine has no in-process simulator).
    2. Call check_voltage_anomaly to analyze voltage levels.
    3. Call check_access_patterns to check for unauthorized access activity.
    4. Call check_command_sequences to detect dangerous SCADA commands.

    DECISION RULES:
    - If ANY of the 3 checks return anomaly_detected=true → threat is present
    - If ALL checks return anomaly_detected=false → no threat detected

    OUTPUT — respond ONLY with a single JSON object (no other text):

    If threat detected:
    {
      "anomaly_detected": true,
      "type": "<voltage_anomaly|access_anomaly|command_sequence_anomaly|combined>",
      "severity": "<CRITICAL|HIGH|MEDIUM|LOW>",
      "attack_indicators": ["<list of indicators found>"],
      "raw_data": {<key fields from telemetry: node_id, voltage, suspicious commands/IPs>},
      "confidence": <0.0-1.0>,
      "detection_summary": "<one sentence plain English description>"
    }

    If no threat:
    {
      "anomaly_detected": false,
      "confidence": <0.0-1.0>,
      "node_id": "<node checked>",
      "detection_summary": "No anomalies detected — all readings within normal parameters"
    }

    IMPORTANT:
    - Never skip a check. Always run all 4 tools.
    - Set severity=CRITICAL only when ransomware commands or root privilege escalation are confirmed.
    - Set confidence based on how many independent checks flagged an anomaly (1 check = 0.7, 2 = 0.85, 3 = 0.95).
    - Output raw JSON only — the next agent reads this directly.
    """,
    tools=[
        read_scada_telemetry,
        check_voltage_anomaly,
        check_access_patterns,
        check_command_sequences,
    ],
    output_key="detection_result",   # Written to session.state["detection_result"]
)
