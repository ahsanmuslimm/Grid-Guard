"""
GridGuard — SequentialAgent Orchestrator
Chains detection → investigation → response using ADK SequentialAgent.
Session state passes data between agents via output_key pattern.
"""

from google.adk.agents import SequentialAgent
from agents.detection_agent import detection_agent
from agents.investigation_agent import investigation_agent
from agents.response_agent import response_agent

# SequentialAgent executes sub-agents in order:
# 1. detection_agent  → writes session.state["detection_result"]
# 2. investigation_agent reads {detection_result} → writes session.state["investigation_result"]
# 3. response_agent reads both → writes session.state["response_result"]
gridguard_pipeline = SequentialAgent(
    name="gridguard_pipeline",
    description=(
        "GridGuard: Autonomous SCADA cyber threat detection, investigation, "
        "and response pipeline for critical energy infrastructure. "
        "Executes a 3-agent sequential mission: detect anomaly → investigate threat → respond."
    ),
    sub_agents=[
        detection_agent,
        investigation_agent,
        response_agent,
    ],
)
