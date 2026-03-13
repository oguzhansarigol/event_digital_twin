"""
Gate queue management and service simulation.
Wraps SimPy Resources to add tracking, overflow detection, and gate switching.
"""
from __future__ import annotations

import random
from typing import Optional

import simpy

from app.core.constants import GATE_OPEN, GATE_CLOSED, GATE_LIMITED
from app.core.config import GATE_SWITCH_PROBABILITY


class GateQueue:
    """
    Manages a single gate's queue using a SimPy Resource.
    Tracks waiting visitors, processed counts, and utilization.
    """

    def __init__(
        self,
        env: simpy.Environment,
        gate_id: str,
        capacity: int = 3,
        service_time: float = 5.0,
        status: str = GATE_OPEN,
    ):
        self.env = env
        self.gate_id = gate_id
        self.capacity = capacity
        self.base_service_time = service_time
        self.status = status

        # SimPy resource: capacity = number of service lanes
        self.resource = simpy.Resource(env, capacity=max(capacity, 1))

        # Tracking
        self.waiting_visitors: list[int] = []  # visitor IDs currently in queue
        self.total_processed: int = 0
        self.total_wait_time: float = 0.0
        self.max_queue_length: int = 0
        self.wait_times: list[float] = []
        self._busy_time: float = 0.0
        self._last_busy_check: float = 0.0

    @property
    def queue_length(self) -> int:
        """Current total visitors at gate (waiting + being served)."""
        return len(self.resource.queue) + len(self.resource.users)

    @property
    def waiting_count(self) -> int:
        """Visitors waiting in queue (not yet being served)."""
        return len(self.resource.queue)

    @property
    def processing_count(self) -> int:
        """Visitors currently being served."""
        return len(self.resource.users)

    @property
    def is_open(self) -> bool:
        return self.status == GATE_OPEN

    @property
    def utilization(self) -> float:
        """Fraction of service lanes currently in use."""
        if self.capacity == 0:
            return 0.0
        return len(self.resource.users) / self.capacity

    def get_service_time(self, visitor_type: str = "normal") -> float:
        """
        Get randomized service time for a visitor.
        VIPs get faster service, staff get fastest.
        """
        base = self.base_service_time

        type_multipliers = {
            "normal": 1.0,
            "vip": 0.6,
            "staff": 0.3,
            "security_staff": 0.2,
            "medical_staff": 0.2,
        }
        multiplier = type_multipliers.get(visitor_type, 1.0)
        service_time = base * multiplier

        # Add random variation ±30%
        service_time *= random.uniform(0.7, 1.3)
        return max(0.5, service_time)

    def add_to_queue(self, visitor_id: int) -> None:
        """Track a visitor entering the queue."""
        self.waiting_visitors.append(visitor_id)
        current_len = len(self.waiting_visitors)
        if current_len > self.max_queue_length:
            self.max_queue_length = current_len

    def remove_from_queue(self, visitor_id: int) -> None:
        """Track a visitor leaving the queue (starting service)."""
        if visitor_id in self.waiting_visitors:
            self.waiting_visitors.remove(visitor_id)

    def record_processed(self, wait_time: float) -> None:
        """Record a visitor completing gate processing."""
        self.total_processed += 1
        self.total_wait_time += wait_time
        self.wait_times.append(wait_time)

    def close(self) -> None:
        """Close this gate."""
        self.status = GATE_CLOSED

    def open(self) -> None:
        """Open this gate."""
        self.status = GATE_OPEN

    def set_limited(self, new_capacity: int) -> None:
        """Set gate to limited mode with reduced capacity."""
        self.status = GATE_LIMITED
        self.capacity = new_capacity
        # Note: SimPy Resource capacity can't be changed after creation
        # so we simulate this by controlling admission logic

    def get_stats(self) -> dict:
        """Return current gate statistics."""
        avg_wait = (
            self.total_wait_time / self.total_processed
            if self.total_processed > 0
            else 0.0
        )
        return {
            "gate_id": self.gate_id,
            "queue_length": self.queue_length,
            "waiting": self.waiting_count,
            "processing": self.processing_count,
            "processed": self.total_processed,
            "status": self.status,
            "utilization": round(self.utilization, 2),
            "avg_wait_time": round(avg_wait, 1),
            "max_queue_length": self.max_queue_length,
        }


class GateManager:
    """
    Manages all gates and provides gate selection logic.
    """

    def __init__(self, env: simpy.Environment):
        self.env = env
        self.gates: dict[str, GateQueue] = {}

    def add_gate(
        self,
        gate_id: str,
        capacity: int = 3,
        service_time: float = 5.0,
        status: str = GATE_OPEN,
    ) -> GateQueue:
        """Create and register a new gate."""
        gate = GateQueue(self.env, gate_id, capacity, service_time, status)
        self.gates[gate_id] = gate
        return gate

    def get_gate(self, gate_id: str) -> Optional[GateQueue]:
        return self.gates.get(gate_id)

    def select_gate(
        self,
        preferred_gate: Optional[str] = None,
        visitor_type: str = "normal",
    ) -> str:
        """
        Select the best gate for a visitor.
        Priority: preferred gate (if short queue) > shortest queue among open gates.
        VIP and staff may have preferred access.
        """
        open_gates = {
            gid: g for gid, g in self.gates.items() if g.is_open
        }

        if not open_gates:
            # All gates closed — fall back to any gate
            return list(self.gates.keys())[0]

        # If visitor has a preference and queue is acceptable
        if preferred_gate and preferred_gate in open_gates:
            gate = open_gates[preferred_gate]
            if gate.waiting_count < 15:  # acceptable queue threshold
                return preferred_gate

        # Select gate with shortest queue
        best_gate = min(open_gates, key=lambda gid: open_gates[gid].waiting_count)
        return best_gate

    def should_switch_gate(
        self,
        current_gate_id: str,
        visitor_patience: float,
        time_waiting: float,
    ) -> Optional[str]:
        """
        Check if a visitor should switch to another gate.
        Returns the new gate id or None.
        """
        if time_waiting < visitor_patience * 0.5:
            return None

        current_gate = self.gates.get(current_gate_id)
        if not current_gate:
            return None

        current_queue = current_gate.waiting_count

        # Find gates with significantly shorter queues
        candidates = []
        for gid, gate in self.gates.items():
            if gid == current_gate_id or not gate.is_open:
                continue
            if gate.waiting_count < current_queue * 0.6:
                candidates.append(gid)

        if candidates and random.random() < GATE_SWITCH_PROBABILITY:
            return random.choice(candidates)

        return None

    def get_all_stats(self) -> dict[str, dict]:
        """Return statistics for all gates."""
        return {gid: g.get_stats() for gid, g in self.gates.items()}

    def get_total_processed(self) -> int:
        return sum(g.total_processed for g in self.gates.values())

    def get_all_wait_times(self) -> list[float]:
        times = []
        for g in self.gates.values():
            times.extend(g.wait_times)
        return times
