"""
GridGuard — SCADA Telemetry Simulator
Generates realistic energy grid telemetry with 4 injectable attack scenarios.
Feeds live data into tools/scada_reader.py for agent consumption.
"""

import random
import time
import threading
from datetime import datetime, timezone
from typing import Callable

from simulator.attack_scenarios import (
    inject_ransomware,
    inject_unauthorized_access,
    inject_ddos,
    inject_data_exfiltration,
)

# Normal operating parameters — IEC 60038 European grid standard
NORMAL_VOLTAGE = (218.0, 242.0)       # 230V ±5%
NORMAL_FREQUENCY = (49.8, 50.2)       # 50Hz ±0.4%
NORMAL_CURRENT = (10.0, 100.0)        # Amperes
NORMAL_POWER_FACTOR = (0.92, 1.00)

NODE_IDS = [f"SUBSTATION_{i:03d}" for i in range(1, 13)]  # 12 grid nodes


class SCADASimulator:
    """
    Simulates a 12-node energy grid SCADA system.
    Runs a background thread pushing telemetry every interval_seconds.
    Supports on-demand attack injection for demo purposes.
    """

    def __init__(self, interval_seconds: float = 2.0):
        self.interval = interval_seconds
        self._running = False
        self._thread: threading.Thread | None = None
        self._callbacks: list[Callable[[dict], None]] = []
        self._active_attack: str | None = None
        self._attack_node: str | None = None
        self._attack_duration: int = 0   # remaining ticks
        self._node_states: dict[str, str] = {n: "NORMAL" for n in NODE_IDS}

    def register_callback(self, fn: Callable[[dict], None]) -> None:
        """Register a function to receive each telemetry tick."""
        if fn not in self._callbacks:
            self._callbacks.append(fn)

    def start(self) -> None:
        """Start the background telemetry generation thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        print(f"[SCADA] Simulator started — {len(NODE_IDS)} nodes, {self.interval}s interval")

    def stop(self) -> None:
        """Stop the telemetry generation thread."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def inject_attack(self, attack_type: str, node_id: str | None = None, duration_ticks: int = 15) -> dict:
        """
        Inject an attack scenario. Called by the demo control panel.

        Args:
            attack_type: 'ransomware' | 'unauthorized_access' | 'ddos' | 'data_exfiltration'
            node_id: Specific node to target, or random if None
            duration_ticks: How many telemetry ticks to sustain the attack

        Returns:
            Dict confirming the injection with target node and attack type.
        """
        target = node_id or random.choice(NODE_IDS)
        self._active_attack = attack_type
        self._attack_node = target
        self._attack_duration = duration_ticks
        self._node_states[target] = "THREAT"

        print(f"[SCADA] ⚠️  Attack injected: {attack_type} on {target} for {duration_ticks} ticks")
        return {
            "injected": True,
            "attack_type": attack_type,
            "target_node": target,
            "duration_ticks": duration_ticks,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def get_node_states(self) -> dict[str, str]:
        """Return current state of all nodes (for dashboard map)."""
        return dict(self._node_states)

    def generate_normal_reading(self, node_id: str | None = None) -> dict:
        """Generate a single normal telemetry reading."""
        node = node_id or random.choice(NODE_IDS)
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "node_id": node,
            "voltage": round(random.uniform(*NORMAL_VOLTAGE), 2),
            "frequency": round(random.uniform(*NORMAL_FREQUENCY), 3),
            "current": round(random.uniform(*NORMAL_CURRENT), 1),
            "power_factor": round(random.uniform(*NORMAL_POWER_FACTOR), 3),
            "access_log": self._generate_normal_access_log(),
            "command_log": [],
            "status": "NORMAL",
            "attack_type": None
        }

    def _run_loop(self) -> None:
        """Background thread: emit telemetry ticks continuously."""
        while self._running:
            reading = self._generate_tick()
            for cb in self._callbacks:
                try:
                    cb(reading)
                except Exception as e:
                    print(f"[SCADA] Callback error: {e}")
            time.sleep(self.interval)

    def _generate_tick(self) -> dict:
        """Generate one telemetry tick, injecting attack if active."""
        if self._active_attack and self._attack_duration > 0:
            reading = self._generate_attack_reading()
            self._attack_duration -= 1
            if self._attack_duration <= 0:
                # Attack window ended — return node to normal
                self._node_states[self._attack_node] = "NORMAL"
                print(f"[SCADA] Attack window ended — {self._attack_node} returning to NORMAL")
                self._active_attack = None
                self._attack_node = None
        else:
            # Generate readings for all nodes, mostly normal
            reading = self.generate_normal_reading()

        return reading

    def _generate_attack_reading(self) -> dict:
        """Dispatch to the appropriate attack scenario generator."""
        base = self.generate_normal_reading(self._attack_node)
        attack_injectors = {
            "ransomware": inject_ransomware,
            "unauthorized_access": inject_unauthorized_access,
            "ddos": inject_ddos,
            "data_exfiltration": inject_data_exfiltration,
        }
        injector = attack_injectors.get(self._active_attack)
        if injector:
            return injector(base)
        return base

    def _generate_normal_access_log(self) -> list[dict]:
        """Generate a plausible normal access log (1-3 entries)."""
        users = ["operator_01", "supervisor_02", "maintenance_03"]
        actions = ["READ_STATUS", "READ_TELEMETRY", "HEARTBEAT"]
        internal_ips = ["10.0.1.5", "192.168.1.10", "172.16.0.3"]

        entries = []
        for _ in range(random.randint(0, 2)):
            entries.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user": random.choice(users),
                "source_ip": random.choice(internal_ips),
                "action": random.choice(actions),
                "result": "SUCCESS"
            })
        return entries


# Module-level singleton — import this in main.py
simulator = SCADASimulator(interval_seconds=2.0)
