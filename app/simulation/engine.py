"""
Core simulation engine.
Orchestrates SimPy environment, visitor generation, movement, and state capture.
"""
from __future__ import annotations

import math
import random
from typing import Optional

import simpy

from app.core.config import (
    DEFAULT_TOTAL_VISITORS,
    DEFAULT_SIMULATION_DURATION,
    METRICS_SAMPLE_INTERVAL,
    SIMULATION_STEP_SIZE,
)
from app.core.constants import (
    STATE_MOVING,
    STATE_QUEUING,
    STATE_PROCESSING,
    STATE_EVACUATING,
    STATE_EXITED,
    NODE_ZONE,
    GATE_OPEN,
    GATE_CLOSED,
)
from app.simulation.routing import (
    build_graph,
    update_edge_congestion,
    get_zone_nodes,
)
from app.simulation.arrivals import get_inter_arrival_time
from app.simulation.queues import GateManager
from app.simulation.agents import create_visitor, visitor_lifecycle
from app.simulation.density import DensityAnalyzer
from app.simulation.metrics import MetricsCollector
from app.simulation.evacuation import trigger_emergency, check_evacuation_complete
from app.simulation.recommendations import generate_recommendations
from app.simulation.scenarios import apply_gate_overrides


class SimulationEngine:
    """
    Main simulation engine using SimPy for discrete-event simulation
    and NetworkX for venue graph routing.
    """

    def __init__(
        self,
        venue_data: dict,
        scenario: Optional[dict] = None,
        total_visitors: int = DEFAULT_TOTAL_VISITORS,
        arrival_pattern: str = "poisson",
        duration: float = DEFAULT_SIMULATION_DURATION,
    ):
        self.venue_data = venue_data
        self.scenario = scenario or {}
        self.total_visitors = total_visitors
        self.arrival_pattern = arrival_pattern
        self.duration = duration

        # Apply scenario gate overrides
        gate_overrides = self.scenario.get("gate_overrides")
        if gate_overrides:
            self.venue_data = apply_gate_overrides(venue_data, gate_overrides)

        # SimPy environment
        self.env = simpy.Environment()

        # Build venue graph
        self.graph = build_graph(self.venue_data)
        self.nodes: dict[str, dict] = {}
        for node in self.venue_data["nodes"]:
            self.nodes[node["id"]] = node

        # Gate manager
        self.gate_manager = GateManager(self.env)
        for gate_id, gate_cfg in self.venue_data["gates"].items():
            self.gate_manager.add_gate(
                gate_id=gate_id,
                capacity=gate_cfg.get("capacity", 3),
                service_time=gate_cfg.get("service_time", 5.0),
                status=gate_cfg.get("status", GATE_OPEN),
            )

        # Density analyzer
        self.density_analyzer = DensityAnalyzer(self.venue_data["zones"])

        # Zone occupancy (alias to density_analyzer)
        self.zone_occupancy = self.density_analyzer.zone_occupancy

        # Metrics collector
        self.metrics = MetricsCollector()

        # Active visitors
        self.active_visitors: dict[int, object] = {}
        self._visitor_counter = 0

        # Edge usage tracking
        self._edge_usage: dict[tuple[str, str], int] = {}

        # State
        self.emergency_mode = False
        self._running = False
        self._setup_done = False
        self._last_sample_time = -METRICS_SAMPLE_INTERVAL

        # Auto emergency trigger
        self._emergency_at = self.scenario.get("emergency_at")

    def setup(self) -> None:
        """Initialize and start the arrival process."""
        if self._setup_done:
            return
        self.env.process(self._arrival_process())
        self._running = True
        self._setup_done = True

    def step(self, dt: float = SIMULATION_STEP_SIZE) -> dict:
        """
        Advance the simulation by dt time units.
        Returns the current state snapshot.
        """
        if not self._setup_done:
            self.setup()

        target_time = self.env.now + dt
        try:
            self.env.run(until=target_time)
        except simpy.core.EmptySchedule:
            pass

        # Check auto-emergency
        if (
            self._emergency_at is not None
            and not self.emergency_mode
            and self.env.now >= self._emergency_at
        ):
            self.trigger_emergency()

        # Check evacuation completion
        if self.emergency_mode:
            check_evacuation_complete(self)

        # Update edge congestion on graph
        update_edge_congestion(self.graph, self._edge_usage)

        # Sample metrics periodically
        if self.env.now - self._last_sample_time >= METRICS_SAMPLE_INTERVAL:
            self._sample_metrics()
            self._last_sample_time = self.env.now

        return self.get_state()

    def get_state(self) -> dict:
        """
        Capture the complete current state of the simulation.
        Returns a dict suitable for JSON serialization and frontend rendering.
        """
        # Visitor positions
        visitors_data = []
        for vid, visitor in self.active_visitors.items():
            x, y = self._get_visitor_position(visitor)
            visitors_data.append({
                "id": visitor.id,
                "x": round(x, 1),
                "y": round(y, 1),
                "state": visitor.state,
                "vtype": visitor.vtype,
                "target": visitor.target_zone,
            })

        # Gate states
        gates_data = {}
        for gid, gate in self.gate_manager.gates.items():
            stats = gate.get_stats()
            gates_data[gid] = stats

        # Zone states
        zones_data = {}
        for zone_id in self.venue_data["zones"]:
            occupancy = self.density_analyzer.get_zone_occupancy(zone_id)
            capacity = self.venue_data["zones"][zone_id].get("capacity", 100)
            density = self.density_analyzer.get_zone_density(zone_id)
            zones_data[zone_id] = {
                "zone_id": zone_id,
                "occupancy": occupancy,
                "capacity": capacity,
                "density": round(density, 3),
            }

        # Alerts
        alerts = self.density_analyzer.generate_alerts()

        # Metrics summary
        metrics_summary = self.metrics.get_summary()

        # Chart point
        chart_point = {
            "time": round(self.env.now, 1),
            "gate_queues": {
                gid: g.queue_length for gid, g in self.gate_manager.gates.items()
            },
            "zone_densities": self.density_analyzer.get_all_densities(),
            "gate_throughput": {
                gid: g.total_processed for gid, g in self.gate_manager.gates.items()
            },
        }

        return {
            "type": "state",
            "time": round(self.env.now, 1),
            "visitors": visitors_data,
            "gates": gates_data,
            "zones": zones_data,
            "metrics": metrics_summary,
            "alerts": alerts,
            "emergency_mode": self.emergency_mode,
            "is_complete": self.is_complete(),
            "chart_point": chart_point,
        }

    def get_final_report(self) -> dict:
        """Generate final report with recommendations and chart data."""
        recommendations = generate_recommendations(self)
        return {
            "type": "complete",
            "metrics": self.metrics.get_summary(),
            "recommendations": recommendations,
            "chart_data": self.metrics.get_chart_data(),
            "gate_stats": self.gate_manager.get_all_stats(),
        }

    def is_complete(self) -> bool:
        """Check if simulation has finished."""
        # Complete if: all visitors generated and all exited, or time exceeded
        all_generated = self.metrics.total_generated >= self.total_visitors
        all_exited = len(self.active_visitors) == 0

        if all_generated and all_exited:
            return True

        # Time limit
        if self.env.now >= self.duration * 2:
            return True

        # Emergency complete
        if self.emergency_mode and all_exited and all_generated:
            return True

        return False

    def trigger_emergency(self) -> None:
        """Activate emergency evacuation mode."""
        trigger_emergency(self)

    def remove_visitor(self, visitor_id: int) -> None:
        """Remove a visitor from active tracking."""
        self.active_visitors.pop(visitor_id, None)

    def zone_add_visitor(self, zone_id: str, visitor_id: int) -> None:
        """Add a visitor to a zone's occupancy tracking."""
        self.density_analyzer.add_visitor_to_zone(zone_id, visitor_id)

    def zone_remove_visitor(self, zone_id: str, visitor_id: int) -> None:
        """Remove a visitor from a zone's occupancy tracking."""
        self.density_analyzer.remove_visitor_from_zone(zone_id, visitor_id)

    def edge_usage_increment(self, from_id: str, to_id: str) -> None:
        """Track a visitor starting to traverse an edge."""
        key = tuple(sorted([from_id, to_id]))
        self._edge_usage[key] = self._edge_usage.get(key, 0) + 1
        self.density_analyzer.increment_edge(from_id, to_id)

    def edge_usage_decrement(self, from_id: str, to_id: str) -> None:
        """Track a visitor finishing edge traversal."""
        key = tuple(sorted([from_id, to_id]))
        self._edge_usage[key] = max(0, self._edge_usage.get(key, 0) - 1)
        self.density_analyzer.decrement_edge(from_id, to_id)

    # ── Private methods ──────────────────────────────────

    def _arrival_process(self):
        """SimPy process: generate visitors over time."""
        generated = 0

        while generated < self.total_visitors:
            # Check if we should stop generating (e.g., emergency)
            if self.emergency_mode:
                return

            # Calculate inter-arrival time
            iat = get_inter_arrival_time(
                pattern=self.arrival_pattern,
                total_visitors=self.total_visitors,
                duration=self.duration,
                current_time=self.env.now,
                visitor_index=generated,
            )
            yield self.env.timeout(max(iat, 0.1))

            if self.emergency_mode:
                return

            # Create visitor
            self._visitor_counter += 1
            visitor = create_visitor(self._visitor_counter, self)
            visitor.arrival_time = self.env.now

            self.active_visitors[visitor.id] = visitor
            self.metrics.record_generation()

            # Start visitor lifecycle process
            proc = self.env.process(visitor_lifecycle(self.env, visitor, self))
            visitor.process = proc

            generated += 1

    def _get_visitor_position(self, visitor) -> tuple[float, float]:
        """
        Calculate current visual position of a visitor.
        Uses interpolation for moving visitors.
        """
        if visitor.state == STATE_QUEUING:
            # Position near gate with queue offset
            gate_node = self.nodes.get(visitor.gate_id, {})
            base_x = gate_node.get("x", visitor.x)
            base_y = gate_node.get("y", visitor.y)

            # Find queue position
            gate = self.gate_manager.get_gate(visitor.gate_id)
            if gate and visitor.id in gate.waiting_visitors:
                idx = gate.waiting_visitors.index(visitor.id)
            else:
                idx = 0

            col = idx % 6
            row = idx // 6
            offset_x = (col - 2.5) * 8
            offset_y = 18 + row * 8

            return base_x + offset_x, base_y + offset_y

        elif visitor.state == STATE_PROCESSING:
            gate_node = self.nodes.get(visitor.gate_id, {})
            return gate_node.get("x", visitor.x), gate_node.get("y", visitor.y) + 8

        elif visitor.state in (STATE_MOVING, STATE_EVACUATING):
            # Interpolate between move_from and move_to
            if visitor.move_end > visitor.move_start:
                progress = (self.env.now - visitor.move_start) / (
                    visitor.move_end - visitor.move_start
                )
                progress = max(0.0, min(1.0, progress))
                x = visitor.move_from[0] + (
                    visitor.move_to[0] - visitor.move_from[0]
                ) * progress
                y = visitor.move_from[1] + (
                    visitor.move_to[1] - visitor.move_from[1]
                ) * progress
                return x, y
            return visitor.x, visitor.y

        else:
            # At destination or other: add small random offset for visual spread
            node = self.nodes.get(visitor.current_node, {})
            base_x = node.get("x", visitor.x)
            base_y = node.get("y", visitor.y)

            # Deterministic scatter based on visitor ID
            scatter_x = ((visitor.id * 7) % 60) - 30
            scatter_y = ((visitor.id * 13) % 40) - 20
            return base_x + scatter_x, base_y + scatter_y

    def _sample_metrics(self) -> None:
        """Record metrics snapshot for time-series charts."""
        gate_queues = {
            gid: g.queue_length for gid, g in self.gate_manager.gates.items()
        }
        zone_densities = self.density_analyzer.get_all_densities()
        gate_processed = {
            gid: g.total_processed for gid, g in self.gate_manager.gates.items()
        }

        self.metrics.sample_queues(self.env.now, gate_queues)
        self.metrics.sample_densities(self.env.now, zone_densities)
        self.metrics.sample_throughput(self.env.now, gate_processed)
