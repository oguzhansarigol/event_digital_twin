"""
Scenario management: loading, applying, and comparing scenarios.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from app.core.config import DATA_DIR


def load_scenarios(filepath: Optional[Path] = None) -> list[dict]:
    """
    Load scenario definitions from JSON file.

    Returns:
        List of scenario configuration dicts.
    """
    if filepath is None:
        filepath = DATA_DIR / "scenarios.json"

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data.get("scenarios", [])


def get_scenario_by_id(scenario_id: str, scenarios: Optional[list[dict]] = None) -> Optional[dict]:
    """
    Find a scenario by its ID.
    """
    if scenarios is None:
        scenarios = load_scenarios()

    for scenario in scenarios:
        if scenario["id"] == scenario_id:
            return scenario

    return None


def apply_gate_overrides(venue_data: dict, gate_overrides: Optional[dict]) -> dict:
    """
    Apply gate configuration overrides from a scenario to venue data.
    Returns modified venue data (does not mutate original).

    Args:
        venue_data: Original venue configuration
        gate_overrides: Dict of gate_id -> override values
            e.g. {"gate_b": {"status": "closed", "capacity": 0}}
    """
    if not gate_overrides:
        return venue_data

    import copy
    modified = copy.deepcopy(venue_data)

    for gate_id, overrides in gate_overrides.items():
        if gate_id in modified["gates"]:
            modified["gates"][gate_id].update(overrides)

    return modified


def build_scenario_summary(scenario: dict, metrics: dict) -> dict:
    """
    Build a summary of a completed scenario for comparison.
    """
    return {
        "scenario_id": scenario.get("id", "unknown"),
        "scenario_name": scenario.get("name", "Unknown"),
        "description": scenario.get("description", ""),
        "total_visitors": metrics.get("total_generated", 0),
        "total_entered": metrics.get("total_entered", 0),
        "total_exited": metrics.get("total_exited", 0),
        "avg_wait_time": metrics.get("avg_wait_time", 0),
        "max_wait_time": metrics.get("max_wait_time", 0),
        "evacuation_time": metrics.get("evacuation_time"),
    }


def compare_scenarios(summaries: list[dict]) -> dict:
    """
    Compare multiple scenario summaries and identify the best/worst.
    """
    if not summaries:
        return {"error": "No scenarios to compare"}

    comparison = {
        "scenarios": summaries,
        "best_wait_time": None,
        "worst_wait_time": None,
        "best_throughput": None,
    }

    # Find best/worst by avg wait time
    valid = [s for s in summaries if s.get("avg_wait_time", 0) > 0]
    if valid:
        best = min(valid, key=lambda s: s["avg_wait_time"])
        worst = max(valid, key=lambda s: s["avg_wait_time"])
        comparison["best_wait_time"] = {
            "scenario": best["scenario_name"],
            "value": best["avg_wait_time"],
        }
        comparison["worst_wait_time"] = {
            "scenario": worst["scenario_name"],
            "value": worst["avg_wait_time"],
        }

    # Find best throughput
    if valid:
        best_tp = max(valid, key=lambda s: s.get("total_entered", 0))
        comparison["best_throughput"] = {
            "scenario": best_tp["scenario_name"],
            "value": best_tp["total_entered"],
        }

    return comparison
