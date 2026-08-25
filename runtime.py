"""GridGuard application runtime lifecycle.

Keeps simulator startup identical whether the app is launched with ``python
main.py`` or directly through Uvicorn/Cloud Run.
"""


from frontend.state import push_threat_event, update_node_states
from simulator.scada_simulator import simulator
from tools.scada_reader import set_telemetry

_initialized = False 


def on_telemetry_tick(reading: dict) -> None:
    set_telemetry(reading, attack_type=reading.get("attack_type"))
    push_threat_event(reading)
    update_node_states(simulator.get_node_states()) 


def start_runtime() -> None:
    global _initialized
    if not _initialized:
        simulator.register_callback(on_telemetry_tick)
        update_node_states(simulator.get_node_states())
        _initialized = True
    simulator.start()


def stop_runtime() -> None:
    simulator.stop()
