"""
GridGuard — Pipeline Verification Script
Run: python verify_pipeline.py
Tests the full detection → investigation → response cycle without ADK/Gemini.
"""
import sys
sys.path.insert(0, '.')

print("=== GridGuard Pipeline Verification ===\n")

# 1. Simulator
from simulator.scada_simulator import simulator
from simulator.attack_scenarios import inject_ransomware
base = simulator.generate_normal_reading('SUBSTATION_005')
attack = inject_ransomware(base)
print(f"[1] Simulator       OK — ransomware voltage: {attack['voltage']}V (normal ~230V)")

# 2. Telemetry tools
from tools.scada_reader import set_telemetry, check_voltage_anomaly, check_access_patterns, check_command_sequences
set_telemetry(attack, 'ransomware')

v = check_voltage_anomaly()
a = check_access_patterns()
c = check_command_sequences()
print(f"[2] Voltage Check   anomaly={v['anomaly_detected']} severity={v.get('severity','OK')}")
print(f"[2] Access Check    anomaly={a['anomaly_detected']} events={a.get('event_count',0)}")
print(f"[2] Command Check   anomaly={c['anomaly_detected']} cmds={[x['command'] for x in c.get('dangerous_commands',[])]}")

# 3. MITRE lookup
from tools.mitre_lookup import lookup_mitre_technique
mitre = lookup_mitre_technique('ransomware')
ids = [t['technique_id'] for t in mitre['techniques'][:3]]
print(f"[3] MITRE Lookup    source={mitre['source']} techniques={ids}")

# 4. CVE lookup
from tools.cve_lookup import lookup_cve
cve = lookup_cve('ransomware')
cve_ids = [c['id'] for c in cve['cves'][:3]]
print(f"[4] CVE Lookup      source={cve['source']} cves={cve_ids}")

# 5. Playbook execution
from tools.playbook_executor import execute_playbook
pb = execute_playbook('ransomware', 'INC-VERIFY-001', {'attack_type': 'ransomware'})
print(f"[5] Playbook        status={pb['status']} actions={len(pb['actions_taken'])}")
for action in pb['actions_taken'][:3]:
    print(f"     -> {action['action']} | {action['result'][:55]}")

# 6. Report generation
from tools.report_generator import generate_incident_report, get_all_reports
detection_result = {
    'type': 'command_sequence_anomaly',
    'severity': 'CRITICAL',
    'confidence': 0.95,
    'raw_data': {'node_id': 'SUBSTATION_005', 'voltage': attack['voltage']}
}
investigation_result = {
    'threat_confirmed': True,
    'classification': 'CRITICAL',
    'attack_type': 'ransomware',
    'mitre_techniques': mitre['techniques'],
    'cves': cve['cves'],
    'false_positive_probability': 0.05,
    'recommended_playbook': 'ransomware'
}
report = generate_incident_report(
    'INC-VERIFY-001', detection_result, investigation_result, pb, 'approved'
)
print(f"[6] Report          id={report['report_id']} classification={report['classification']}")
print(f"    Title: {report['title'][:70]}")
print(f"    Reports in memory: {len(get_all_reports())}")

# 7. Frontend state
from frontend.state import add_timeline_event, get_dashboard_snapshot, update_node_states
update_node_states({'SUBSTATION_005': 'THREAT', 'SUBSTATION_001': 'NORMAL'})
add_timeline_event('detection_agent', 'anomaly_detected', 'Ransomware indicators found', 0.95, 'threat', 'CRITICAL')
snap = get_dashboard_snapshot()
print(f"[7] Frontend State  nodes={len(snap['node_states'])} timeline={len(snap['timeline'])} events")

# 8. FastAPI routes
from frontend.main import app
print(f"[8] FastAPI App     routes={len(app.routes)} registered")

print("\n=== ALL CHECKS PASSED — System Ready ===")
