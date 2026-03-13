"""
Simulation service layer.
Manages simulation lifecycle, bridges API/WebSocket with the engine.
"""
from __future__ import annotations

import json
import copy
from pathlib import Path
from typing import Optional

from app.core.config import (
    DATA_DIR,
    SIMULATION_STEP_SIZE,
    DEFAULT_SPEED_MULTIPLIER,
)
from app.simulation.engine import SimulationEngine
from app.simulation.scenarios import load_scenarios, get_scenario_by_id


class SimulationService:
    """
    Manages the simulation lifecycle and provides a clean interface
    for the API and WebSocket handlers.
    """

    def __init__(self):
        self.engine: Optional[SimulationEngine] = None
        self.speed_multiplier: float = DEFAULT_SPEED_MULTIPLIER
        self.running: bool = False
        self._venue_data: Optional[dict] = None
        self._scenarios: Optional[list[dict]] = None

    def load_venue(self, filepath: Optional[Path] = None) -> dict:
        """Load and cache venue configuration."""
        if self._venue_data is None:
            if filepath is None:
                filepath = DATA_DIR / "venue.json"
            with open(filepath, "r", encoding="utf-8") as f:
                self._venue_data = json.load(f)
        return self._venue_data

    def load_scenarios(self) -> list[dict]:
        """Load and cache scenario definitions."""
        if self._scenarios is None:
            self._scenarios = load_scenarios()
        return self._scenarios

    def create_simulation(self, params: dict) -> dict:
        """
        Create a new simulation engine from parameters.

        Args:
            params: Dict with keys:
                - scenario_id: str
                - total_visitors: int
                - arrival_pattern: str
                - duration: float
                - speed_multiplier: float
                - gate_overrides: dict (optional)
                - emergency_at: float (optional)

        Returns:
            Initial state dict
        """
        venue_data = copy.deepcopy(self.load_venue())
        scenarios = self.load_scenarios()

        scenario_id = params.get("scenario_id", "normal_flow")
        scenario = get_scenario_by_id(scenario_id, scenarios)

        if scenario is None:
            scenario = {
                "id": scenario_id,
                "name": "Custom",
                "description": "Custom scenario",
            }

        # Merge scenario defaults with user params
        total_visitors = params.get(
            "total_visitors",
            scenario.get("default_visitors", 300),
        )
        arrival_pattern = params.get(
            "arrival_pattern",
            scenario.get("default_arrival", "poisson"),
        )
        duration = params.get(
            "duration",
            scenario.get("default_duration", 600),
        )
        self.speed_multiplier = params.get("speed_multiplier", DEFAULT_SPEED_MULTIPLIER)

        # Gate overrides: merge scenario + user overrides
        gate_overrides = scenario.get("gate_overrides")
        user_gate_overrides = params.get("gate_overrides")
        if user_gate_overrides:
            if gate_overrides:
                gate_overrides.update(user_gate_overrides)
            else:
                gate_overrides = user_gate_overrides

        scenario_config = {
            **scenario,
            "gate_overrides": gate_overrides,
            "emergency_at": params.get("emergency_at", scenario.get("emergency_at")),
        }

        self.engine = SimulationEngine(
            venue_data=venue_data,
            scenario=scenario_config,
            total_visitors=total_visitors,
            arrival_pattern=arrival_pattern,
            duration=duration,
        )
        self.engine.setup()
        self.running = True

        return self.engine.get_state()

    def step(self, dt: Optional[float] = None) -> dict:
        """
        Advance simulation by one step.

        Returns:
            Current state dict
        """
        if self.engine is None:
            return {"type": "error", "message": "No simulation running"}

        step_size = dt if dt else SIMULATION_STEP_SIZE
        return self.engine.step(step_size)

    def trigger_emergency(self) -> dict:
        """Trigger emergency evacuation."""
        if self.engine is None:
            return {"type": "error", "message": "No simulation running"}

        self.engine.trigger_emergency()
        return {"type": "emergency", "message": "Emergency mode activated"}

    def set_speed(self, speed: float) -> None:
        """Set simulation speed multiplier."""
        self.speed_multiplier = max(0.5, min(100.0, speed))

    def get_metrics(self) -> dict:
        """Get current metrics summary."""
        if self.engine is None:
            return {}
        return self.engine.metrics.get_summary()

    def get_chart_data(self) -> dict:
        """Get chart time-series data."""
        if self.engine is None:
            return {}
        return self.engine.metrics.get_chart_data()

    def get_recommendations(self) -> list[str]:
        """Get current recommendations."""
        if self.engine is None:
            return []
        from app.simulation.recommendations import generate_recommendations
        return generate_recommendations(self.engine)

    def get_final_report(self) -> dict:
        """Get final simulation report."""
        if self.engine is None:
            return {}
        return self.engine.get_final_report()

    def is_running(self) -> bool:
        """Check if simulation is actively running."""
        return self.running and self.engine is not None

    def is_complete(self) -> bool:
        """Check if simulation has finished."""
        if self.engine is None:
            return True
        return self.engine.is_complete()

    def reset(self) -> None:
        """Reset the simulation service."""
        self.engine = None
        self.running = False

    def cleanup(self) -> None:
        """Clean up resources."""
        self.reset()
