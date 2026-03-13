"""
Domain models using dataclasses for internal simulation state.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from app.core.constants import (
    STATE_ARRIVING,
    VISITOR_NORMAL,
    GATE_OPEN,
)
from app.core.config import DEFAULT_WALKING_SPEED


# ── Visitor ────────────────────────────────────────────
@dataclass
class Visitor:
    """Represents a single visitor agent in the simulation."""
    id: int
    vtype: str = VISITOR_NORMAL
    arrival_time: float = 0.0
    walking_speed: float = DEFAULT_WALKING_SPEED
    patience: float = 60.0
    preferred_gate: Optional[str] = None
    target_zone: Optional[str] = None
    current_node: Optional[str] = None
    state: str = STATE_ARRIVING
    group_id: Optional[int] = None

    # Position for visualization
    x: float = 0.0
    y: float = 0.0

    # Movement interpolation data
    move_from: tuple[float, float] = (0.0, 0.0)
    move_to: tuple[float, float] = (0.0, 0.0)
    move_start: float = 0.0
    move_end: float = 0.0

    # Gate tracking
    gate_id: Optional[str] = None
    wait_time: float = 0.0

    # SimPy process reference
    process: object = field(default=None, repr=False)

    # Stay duration at destination
    stay_duration: float = 60.0


# ── Gate ───────────────────────────────────────────────
@dataclass
class GateConfig:
    """Configuration for an entry gate."""
    gate_id: str
    node_id: str
    capacity: int = 3
    service_time: float = 5.0
    status: str = GATE_OPEN
    x: float = 0.0
    y: float = 0.0


# ── Zone ───────────────────────────────────────────────
@dataclass
class ZoneConfig:
    """Configuration for a venue zone."""
    zone_id: str
    node_id: str
    zone_type: str = "entertainment"
    capacity: int = 100
    x: float = 0.0
    y: float = 0.0
    width: float = 100.0
    height: float = 60.0


# ── Graph Node ─────────────────────────────────────────
@dataclass
class GraphNode:
    """A node in the venue graph."""
    id: str
    x: float
    y: float
    node_type: str
    label: str = ""
    zone_id: Optional[str] = None
    capacity: Optional[int] = None
    width: float = 0.0
    height: float = 0.0

    def distance_to(self, other: GraphNode) -> float:
        return math.sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)


# ── Path Edge ──────────────────────────────────────────
@dataclass
class PathEdge:
    """An edge in the venue graph."""
    from_node: str
    to_node: str
    distance: float
    width: float = 2.0
    congestion: float = 0.0


# ── Metrics snapshot ───────────────────────────────────
@dataclass
class MetricsSnapshot:
    """A point-in-time metrics snapshot for charting."""
    time: float = 0.0
    total_entered: int = 0
    total_exited: int = 0
    active_count: int = 0
    avg_wait_time: float = 0.0
    max_wait_time: float = 0.0
    gate_queues: dict = field(default_factory=dict)
    zone_densities: dict = field(default_factory=dict)
    gate_throughput: dict = field(default_factory=dict)


# ── Simulation state for API ───────────────────────────
@dataclass
class SimulationState:
    """Complete state of a running simulation for serialization."""
    time: float = 0.0
    visitors: list = field(default_factory=list)
    gates: dict = field(default_factory=dict)
    zones: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    alerts: list = field(default_factory=list)
    emergency_mode: bool = False
    is_complete: bool = False
    recommendations: list = field(default_factory=list)
    chart_point: dict = field(default_factory=dict)
