"""
Emergency evacuation logic.
Handles triggering evacuation, interrupting visitors, and tracking completion.
"""
from __future__ import annotations

import simpy
from typing import TYPE_CHECKING

from app.core.constants import STATE_QUEUING, STATE_PROCESSING, STATE_EXITED

if TYPE_CHECKING:
    from app.simulation.engine import SimulationEngine


def trigger_emergency(engine: "SimulationEngine") -> None:
    """
    Activate emergency evacuation mode.
    - Sets emergency flag
    - Records start time
    - Interrupts queuing visitors so they evacuate immediately
    - Visitors in other states will check the flag at their next yield point
    """
    if engine.emergency_mode:
        return  # Already in emergency

    engine.emergency_mode = True
    engine.metrics.record_evacuation_start(engine.env.now)

    # Interrupt visitors who are still queuing (waiting for gate resource)
    interrupted_count = 0
    for vid, visitor in list(engine.active_visitors.items()):
        if visitor.state in (STATE_QUEUING,) and visitor.process is not None:
            try:
                visitor.process.interrupt("emergency")
                interrupted_count += 1
            except RuntimeError:
                # Process may have already finished
                pass

    # Release queuing visitors from gate tracking
    for gate_id, gate in engine.gate_manager.gates.items():
        gate.waiting_visitors.clear()

    return interrupted_count


def check_evacuation_complete(engine: "SimulationEngine") -> bool:
    """
    Check if all visitors have evacuated.
    Returns True if evacuation is complete.
    """
    if not engine.emergency_mode:
        return False

    # Count non-exited visitors
    active = sum(
        1 for v in engine.active_visitors.values()
        if v.state != STATE_EXITED
    )

    if active == 0 and engine.metrics.evacuation_start_time is not None:
        if engine.metrics.evacuation_complete_time is None:
            engine.metrics.record_evacuation_complete(engine.env.now)
        return True

    return False


def get_evacuation_stats(engine: "SimulationEngine") -> dict:
    """
    Get current evacuation statistics.
    """
    if not engine.emergency_mode:
        return {"status": "not_active"}

    total_at_start = engine.metrics.total_entered - engine.metrics.total_exited
    # Count based on evacuation exit records
    evacuated = len(engine.metrics.evacuation_exit_times)

    # Add visitors who already exited before emergency
    still_inside = len(engine.active_visitors)

    evac_time = engine.metrics.evacuation_time

    return {
        "status": "complete" if still_inside == 0 else "in_progress",
        "total_to_evacuate": total_at_start,
        "evacuated": evacuated,
        "still_inside": still_inside,
        "evacuation_time": evac_time,
        "start_time": engine.metrics.evacuation_start_time,
    }


def compare_evacuation_scenarios(results: list[dict]) -> dict:
    """
    Compare evacuation performance across multiple scenario results.
    Each result should contain evacuation stats.
    """
    if not results:
        return {}

    comparison = {
        "scenarios": [],
        "best_time": float("inf"),
        "worst_time": 0.0,
        "best_scenario": None,
        "worst_scenario": None,
    }

    for result in results:
        evac_time = result.get("evacuation_time")
        scenario_name = result.get("scenario_name", "Unknown")

        if evac_time is not None:
            comparison["scenarios"].append({
                "name": scenario_name,
                "evacuation_time": evac_time,
                "still_inside": result.get("still_inside", 0),
            })
            if evac_time < comparison["best_time"]:
                comparison["best_time"] = evac_time
                comparison["best_scenario"] = scenario_name
            if evac_time > comparison["worst_time"]:
                comparison["worst_time"] = evac_time
                comparison["worst_scenario"] = scenario_name

    return comparison
