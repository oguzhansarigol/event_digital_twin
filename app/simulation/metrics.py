"""
Metrics collection and aggregation throughout the simulation.
Tracks gate performance, wait times, zone usage, and evacuation stats.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MetricsCollector:
    """
    Collects and aggregates simulation metrics over time.
    """
    # Gate metrics
    gate_processed: dict[str, int] = field(default_factory=dict)
    gate_wait_times: dict[str, list[float]] = field(default_factory=dict)

    # Visitor tracking
    total_generated: int = 0
    total_entered: int = 0
    total_exited: int = 0
    visitor_entry_times: dict[int, float] = field(default_factory=dict)
    visitor_exit_times: dict[int, float] = field(default_factory=dict)
    visitor_gates: dict[int, str] = field(default_factory=dict)

    # Wait times
    all_wait_times: list[float] = field(default_factory=list)

    # Evacuation
    evacuation_start_time: Optional[float] = None
    evacuation_exit_times: list[float] = field(default_factory=list)
    evacuation_complete_time: Optional[float] = None

    # Time series for charts (sampled periodically)
    queue_history: list[dict] = field(default_factory=list)
    density_history: list[dict] = field(default_factory=list)
    throughput_history: list[dict] = field(default_factory=list)

    def record_generation(self) -> None:
        """Record that a visitor was generated."""
        self.total_generated += 1

    def record_entry(self, visitor_id: int, gate_id: str, time: float) -> None:
        """Record a visitor entering the venue through a gate."""
        self.total_entered += 1
        self.visitor_entry_times[visitor_id] = time
        self.visitor_gates[visitor_id] = gate_id
        self.gate_processed[gate_id] = self.gate_processed.get(gate_id, 0) + 1

    def record_wait_time(self, gate_id: str, wait_time: float) -> None:
        """Record a wait time at a gate."""
        if gate_id not in self.gate_wait_times:
            self.gate_wait_times[gate_id] = []
        self.gate_wait_times[gate_id].append(wait_time)
        self.all_wait_times.append(wait_time)

    def record_exit(self, visitor_id: int, time: float) -> None:
        """Record a visitor exiting the venue."""
        self.total_exited += 1
        self.visitor_exit_times[visitor_id] = time

    def record_evacuation_start(self, time: float) -> None:
        """Record when emergency evacuation was triggered."""
        self.evacuation_start_time = time

    def record_evacuation_exit(self, visitor_id: int, time: float) -> None:
        """Record an evacuating visitor reaching an exit."""
        self.evacuation_exit_times.append(time)

    def record_evacuation_complete(self, time: float) -> None:
        """Record when the last visitor has evacuated."""
        self.evacuation_complete_time = time

    # ── Time series sampling ─────────────────────────────

    def sample_queues(self, time: float, gate_queues: dict[str, int]) -> None:
        """Record a queue length snapshot."""
        point = {"time": round(time, 1)}
        point.update({gid: length for gid, length in gate_queues.items()})
        self.queue_history.append(point)

    def sample_densities(self, time: float, zone_densities: dict[str, float]) -> None:
        """Record a zone density snapshot."""
        point = {"time": round(time, 1)}
        point.update({zid: round(d, 3) for zid, d in zone_densities.items()})
        self.density_history.append(point)

    def sample_throughput(self, time: float, gate_processed: dict[str, int]) -> None:
        """Record a throughput snapshot."""
        point = {"time": round(time, 1)}
        point.update({gid: count for gid, count in gate_processed.items()})
        self.throughput_history.append(point)

    # ── Aggregated metrics ───────────────────────────────

    @property
    def active_count(self) -> int:
        """Number of visitors currently in the venue."""
        return self.total_entered - self.total_exited

    @property
    def avg_wait_time(self) -> float:
        if not self.all_wait_times:
            return 0.0
        return sum(self.all_wait_times) / len(self.all_wait_times)

    @property
    def max_wait_time(self) -> float:
        if not self.all_wait_times:
            return 0.0
        return max(self.all_wait_times)

    @property
    def evacuation_time(self) -> Optional[float]:
        if self.evacuation_start_time is None:
            return None
        if self.evacuation_complete_time is not None:
            return round(self.evacuation_complete_time - self.evacuation_start_time, 1)
        if self.evacuation_exit_times:
            latest = max(self.evacuation_exit_times)
            return round(latest - self.evacuation_start_time, 1)
        return None

    def get_gate_avg_wait(self, gate_id: str) -> float:
        times = self.gate_wait_times.get(gate_id, [])
        return sum(times) / len(times) if times else 0.0

    def get_summary(self) -> dict:
        """Return a summary dict suitable for API response."""
        return {
            "total_generated": self.total_generated,
            "total_entered": self.total_entered,
            "total_exited": self.total_exited,
            "active_count": self.active_count,
            "avg_wait_time": round(self.avg_wait_time, 1),
            "max_wait_time": round(self.max_wait_time, 1),
            "evacuation_time": self.evacuation_time,
        }

    def get_chart_data(self) -> dict:
        """Return accumulated chart data."""
        return {
            "queue_history": self.queue_history[-100:],  # last 100 points
            "density_history": self.density_history[-100:],
            "throughput_history": self.throughput_history[-100:],
        }
