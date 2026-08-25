"""
GridGuard — Attack Scenario Injectors
Each function takes a normal SCADA reading and mutates it to look like
a specific attack type. These produce clearly anomalous telemetry that
the detection agent can identify.
"""

import random
from datetime import datetime, timezone



def inject_ransomware(base_reading: dict) -> dict:
    """
    Ransomware attack pattern:
    - Voltage drops (attacker disrupting power control)
    - Dangerous SCADA commands: ENCRYPT_FILES, DISABLE_BACKUP
    - High CPU / unusual process activity in command log
    - External C2 IP in access log
    """
    reading = dict(base_reading)
    reading["voltage"] = round(random.uniform(185.0, 205.0), 2)   # Below 218V threshold
    reading["frequency"] = round(random.uniform(49.2, 49.6), 3)   # Slight frequency drop
    reading["command_log"] = [
        "ENCRYPT_FILES",
        "DISABLE_BACKUP",
        "KILL_PROCESS:scada_monitor",
        "WRITE_RANSOM_NOTE"
    ]
    reading["access_log"] = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": "UNKNOWN",
            "source_ip": "185.234.219.47",   # External IP
            "action": "PRIVILEGE_ESCALATION",
            "result": "SUCCESS"
        },
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": "UNKNOWN",
            "source_ip": "185.234.219.47",
            "action": "ROOT_LOGIN",
            "result": "SUCCESS"
        }
    ]
    reading["status"] = "ANOMALY"
    reading["attack_type"] = "ransomware"
    return reading


def inject_unauthorized_access(base_reading: dict) -> dict:
    """
    Unauthorized access pattern:
    - Normal voltages (attacker is careful not to trigger physical alarms)
    - Foreign IP with failed auth → successful escalation
    - Unusual user agent / login from unexpected geography
    - Privilege escalation in access log
    """
    reading = dict(base_reading)
    # Voltage mostly normal — attacker is stealthy
    reading["voltage"] = round(random.uniform(225.0, 235.0), 2)
    reading["command_log"] = ["READ_CONFIG", "EXPORT_SCHEMA", "LIST_USERS"]
    reading["access_log"] = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": "admin_backup",
            "source_ip": "91.108.56.102",   # External — Eastern Europe range
            "action": "FAILED_AUTH",
            "result": "FAILED"
        },
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": "admin_backup",
            "source_ip": "91.108.56.102",
            "action": "PRIVILEGE_ESCALATION",
            "result": "SUCCESS"
        },
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": "admin_backup",
            "source_ip": "91.108.56.102",
            "action": "FOREIGN_IP_ACCESS",
            "result": "SUCCESS"
        }
    ]
    reading["status"] = "ANOMALY"
    reading["attack_type"] = "unauthorized_access"
    return reading


def inject_ddos(base_reading: dict) -> dict:
    """
    DDoS/Denial of Service pattern:
    - Voltage spikes from overloaded control system processing
    - High current anomalies
    - Flood ping + port scan commands
    - Many access attempts from multiple external IPs
    """
    reading = dict(base_reading)
    reading["voltage"] = round(random.uniform(248.0, 265.0), 2)   # Spike above 242V
    reading["current"] = round(random.uniform(150.0, 200.0), 1)   # Abnormally high
    reading["frequency"] = round(random.uniform(50.4, 50.9), 3)   # Frequency deviation
    reading["command_log"] = [
        "FLOOD_PING:broadcast",
        "PORT_SCAN:all",
        "OVERFLOW_BUFFER:hmi_interface",
        "FLOOD_PING:broadcast"
    ]
    # Many access attempts from different external IPs
    reading["access_log"] = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": "UNKNOWN",
            "source_ip": f"45.{random.randint(100,200)}.{random.randint(1,254)}.{random.randint(1,254)}",
            "action": "FAILED_AUTH",
            "result": "FAILED"
        }
        for _ in range(random.randint(8, 15))  # High volume of attempts
    ]
    reading["status"] = "ANOMALY"
    reading["attack_type"] = "ddos"
    return reading


def inject_data_exfiltration(base_reading: dict) -> dict:
    """
    Data exfiltration pattern:
    - Normal voltages (low-and-slow attack)
    - Large volume read commands
    - Unusual bulk export activity
    - Sustained connection to external IP
    """
    reading = dict(base_reading)
    # Voltages normal — this attack is stealthy
    reading["voltage"] = round(random.uniform(228.0, 232.0), 2)
    reading["command_log"] = [
        "MASS_READ:historian_db",
        "BULK_EXPORT:process_data",
        "MASS_READ:network_map",
        "UNAUTHORIZED_EXPORT:configuration",
        "BULK_EXPORT:alarm_history"
    ]
    reading["access_log"] = [
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": "svc_account_03",
            "source_ip": "198.51.100.42",   # External
            "action": "FOREIGN_IP_ACCESS",
            "result": "SUCCESS"
        },
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": "svc_account_03",
            "source_ip": "198.51.100.42",
            "action": "UNAUTHORIZED_EXPORT",
            "result": "SUCCESS"
        }
    ]
    # Flag unusually high outbound data volume
    reading["outbound_mb"] = round(random.uniform(850.0, 2000.0), 1)
    reading["status"] = "ANOMALY"
    reading["attack_type"] = "data_exfiltration"
    return reading
