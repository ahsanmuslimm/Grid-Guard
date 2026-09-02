import os
import unittest
from types import SimpleNamespace

os.environ["PHOENIX_API_KEY"] = ""
os.environ["GRIDGUARD_ENABLE_PHOENIX_MCP"] = "false"

import agents.pipeline_runner as pipeline_runner
from agents.pipeline_runner import _parse_result
from google.genai import types
from fastapi.testclient import TestClient
from frontend.main import app
from frontend.state import (
    get_incident_replay,
    push_approval_request,
    register_incident,
    set_approval_result,
)
from observability.evaluators import evaluate_incident
from simulator.scada_simulator import SCADASimulator
from tools.playbook_executor import execute_playbook


class EvaluationTests(unittest.TestCase):
    def test_grounded_claims_pass(self):
        evaluation = evaluate_incident(
            "INC-TEST-1",
            "ransomware",
            {
                "cves": [{"id": "CVE-2024-12345"}],
                "mitre_techniques": [{"technique_id": "T0804"}],
                "claimed_cves": [{"id": "CVE-2024-12345"}],
                "claimed_mitre_techniques": [{"technique_id": "T0804"}],
                "recommended_playbook": "ransomware",
            },
            {"response_status": "executed", "playbook": "ransomware"},
        )
        self.assertFalse(evaluation["hallucination_flagged"])
        self.assertEqual(evaluation["quality_score"], 1.0)

    def test_well_formed_but_ungrounded_claim_is_flagged(self):
        evaluation = evaluate_incident(
            "INC-TEST-2",
            "ddos",
            {
                "cves": [{"id": "CVE-2024-11111"}],
                "mitre_techniques": [{"technique_id": "T0814"}],
                "claimed_cves": [{"id": "CVE-2024-99999"}],
                "claimed_mitre_techniques": [{"technique_id": "T0814"}],
                "recommended_playbook": "ddos",
            },
            {"response_status": "executed", "playbook": "ddos"},
        )
        self.assertTrue(evaluation["hallucination_flagged"])
        self.assertEqual(evaluation["ungrounded_cves"], ["CVE-2024-99999"])
        self.assertEqual(evaluation["quality_score"], 0.8)

    def test_escalated_timeout_is_not_a_completed_response(self):
        evaluation = evaluate_incident(
            "INC-TEST-TIMEOUT",
            "unauthorized_access",
            {
                "cves": [{"id": "CVE-2024-12345"}],
                "claimed_cves": [{"id": "CVE-2024-12345"}],
                "recommended_playbook": "unauthorized_access",
            },
            {
                "response_status": "escalated",
                "approval_status": "timeout",
                "playbook": "unauthorized_access",
                "report_generated": False,
            },
        )
        self.assertFalse(evaluation["response_completed"])
        self.assertEqual(evaluation["quality_score"], 0.7)


class PipelineParsingTests(unittest.TestCase):
    def test_markdown_json_is_parsed(self):
        result = _parse_result(
            '```json\n{"response_status":"executed","playbook":"ddos"}\n```',
            "INC-1",
            "ddos",
        )
        self.assertEqual(result["response_status"], "executed")
        self.assertEqual(result["incident_id"], "INC-1")

    def test_invalid_output_is_not_reported_as_success(self):
        result = _parse_result("not json", "INC-2", "ddos")
        self.assertEqual(result["response_status"], "error")
        self.assertFalse(result["report_generated"])


class PipelineSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_runner_receives_a_created_session(self):
        original_runner = pipeline_runner._runner

        class FakeRunner:
            async def run_async(self, *, user_id, session_id, **kwargs):
                session = await pipeline_runner._session_service.get_session(
                    app_name="gridguard", user_id=user_id, session_id=session_id
                )
                if session is None:
                    raise AssertionError("ADK session was not created")
                payload = (
                    '{"response_status":"executed","playbook":"ddos",'
                    '"approval_status":"not_required","report_generated":true}'
                )
                yield SimpleNamespace(
                    author="response_agent",
                    content=types.Content(role="model", parts=[types.Part(text=payload)]),
                )

        pipeline_runner._runner = FakeRunner()
        try:
            result = await pipeline_runner.run_pipeline_for_attack(
                "ddos", "SUBSTATION_002", {"status": "ANOMALY", "attack_type": "ddos"}
            )
        finally:
            pipeline_runner._runner = original_runner
        self.assertEqual(result["response_status"], "executed")


class SimulatorTests(unittest.TestCase):
    def test_attack_injection_emits_immediate_snapshot(self):
        simulator = SCADASimulator(interval_seconds=60)
        received = []
        simulator.register_callback(received.append)
        result = simulator.inject_attack("data_exfiltration", node_id="SUBSTATION_003")
        self.assertEqual(len(received), 1)
        self.assertEqual(result["telemetry_snapshot"]["attack_type"], "data_exfiltration")
        self.assertEqual(received[0]["node_id"], "SUBSTATION_003")

    def test_replacing_attack_clears_previous_threat_node(self):
        simulator = SCADASimulator(interval_seconds=60)
        simulator.inject_attack("ddos", node_id="SUBSTATION_007")
        simulator.inject_attack("ransomware", node_id="SUBSTATION_008")
        states = simulator.get_node_states()
        self.assertEqual(states["SUBSTATION_007"], "NORMAL")
        self.assertEqual(states["SUBSTATION_008"], "THREAT")


class PlaybookSafetyTests(unittest.TestCase):
    def test_playbook_name_cannot_escape_allowlist(self):
        result = execute_playbook("../secrets", "INC-PATH-TEST")
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["actions_taken"], [])

    def test_gated_playbook_is_blocked_without_operator_approval(self):
        result = execute_playbook("ransomware", "INC-NOT-APPROVED")
        self.assertEqual(result["status"], "blocked_approval_required")
        self.assertEqual(result["actions_taken"], [])

    def test_gated_playbook_executes_after_operator_approval(self):
        incident_id = "INC-APPROVED-PLAYBOOK"
        set_approval_result(incident_id, "approved")
        result = execute_playbook("unauthorized_access", incident_id)
        self.assertEqual(result["status"], "executed")
        self.assertGreater(len(result["actions_taken"]), 0)


class ApiAndReplayTests(unittest.TestCase):
    def test_health_and_invalid_approval(self):
        with TestClient(app) as client:
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.post("/api/approve/INC-MISSING").status_code, 404)

    def test_approval_events_are_in_replay(self):
        incident_id = "INC-REPLAY-TEST"
        register_incident(incident_id, "ransomware", "SUBSTATION_001")
        push_approval_request({
            "incident_id": incident_id,
            "recommended_playbook": "ransomware",
        })
        set_approval_result(incident_id, "approved")
        actions = [event["action"] for event in get_incident_replay(incident_id)["events"]]
        self.assertIn("requesting_human_approval", actions)
        self.assertIn("approval_approved", actions)


if __name__ == "__main__":
    unittest.main()
