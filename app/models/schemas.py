"""
Pydantic schemas for API request / response validation.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


# ── Request schemas ────────────────────────────────────

class SimulationParams(BaseModel):
    """Parameters to start a new simulation run."""
    scenario_id: str = Field(default="normal_flow", description="Scenario identifier")
    total_visitors: int = Field(default=300, ge=10, le=5000)
    arrival_pattern: str = Field(default="poisson", description="uniform|poisson|peak_hour|ticket_slot|group")
    speed_multiplier: float = Field(default=5.0, ge=0.5, le=100.0)
    duration: float = Field(default=600.0, ge=60.0, le=7200.0, description="Simulation duration in seconds")
    gate_overrides: Optional[dict] = Field(default=None, description="Override gate capacities/status")
    emergency_at: Optional[float] = Field(default=None, description="Auto-trigger emergency at this sim time")


class SpeedChangeRequest(BaseModel):
    """Change simulation speed."""
    speed_multiplier: float = Field(ge=0.5, le=100.0)


class EmergencyRequest(BaseModel):
    """Trigger emergency mode."""
    trigger: bool = True


# ── Response schemas ───────────────────────────────────

class VisitorState(BaseModel):
    """Single visitor state for frontend rendering."""
    id: int
    x: float
    y: float
    state: str
    vtype: str
    target: Optional[str] = None


class GateState(BaseModel):
    """Gate state snapshot."""
    gate_id: str
    queue_length: int = 0
    waiting: int = 0
    processing: int = 0
    processed: int = 0
    status: str = "open"
    utilization: float = 0.0


class ZoneState(BaseModel):
    """Zone state snapshot."""
    zone_id: str
    occupancy: int = 0
    capacity: int = 100
    density: float = 0.0


class MetricsSummary(BaseModel):
    """Aggregated metrics."""
    total_entered: int = 0
    total_exited: int = 0
    active_count: int = 0
    avg_wait_time: float = 0.0
    max_wait_time: float = 0.0
    max_queue_length: int = 0
    evacuation_time: Optional[float] = None


class ChartDataPoint(BaseModel):
    """Single data point for time-series charts."""
    time: float
    gate_queues: dict = {}
    zone_densities: dict = {}
    gate_throughput: dict = {}


class SimulationStateResponse(BaseModel):
    """Full simulation state pushed via WebSocket."""
    type: str = "state"
    time: float = 0.0
    visitors: list[VisitorState] = []
    gates: list[GateState] = []
    zones: list[ZoneState] = []
    metrics: MetricsSummary = MetricsSummary()
    alerts: list[str] = []
    emergency_mode: bool = False
    is_complete: bool = False
    chart_point: Optional[ChartDataPoint] = None
    recommendations: list[str] = []


class ScenarioInfo(BaseModel):
    """Scenario description for the UI."""
    id: str
    name: str
    description: str
    default_visitors: int = 300
    default_arrival: str = "poisson"
    default_duration: float = 600.0
    gate_overrides: Optional[dict] = None
    emergency_at: Optional[float] = None


class VenueInfo(BaseModel):
    """Venue metadata for the UI."""
    name: str
    width: int
    height: int
    nodes: list[dict]
    edges: list[dict]
    gates: dict
    zones: dict
