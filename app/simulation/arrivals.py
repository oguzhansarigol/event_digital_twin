"""
Arrival pattern generators for visitor inflow.
Each generator yields inter-arrival times for the SimPy environment.
"""
from __future__ import annotations

import random
import math
from typing import Generator

from app.core.constants import (
    ARRIVAL_UNIFORM,
    ARRIVAL_POISSON,
    ARRIVAL_PEAK,
    ARRIVAL_SLOT,
    ARRIVAL_GROUP,
)


def get_inter_arrival_time(
    pattern: str,
    total_visitors: int,
    duration: float,
    current_time: float = 0.0,
    visitor_index: int = 0,
) -> float:
    """
    Return the next inter-arrival time based on the configured pattern.

    Args:
        pattern: One of the ARRIVAL_* constants
        total_visitors: Total visitors expected
        duration: Total simulation duration
        current_time: Current simulation time
        visitor_index: Index of the visitor being generated

    Returns:
        Inter-arrival time in simulation seconds
    """
    if pattern == ARRIVAL_UNIFORM:
        return _uniform_iat(total_visitors, duration)
    elif pattern == ARRIVAL_POISSON:
        return _poisson_iat(total_visitors, duration)
    elif pattern == ARRIVAL_PEAK:
        return _peak_hour_iat(total_visitors, duration, current_time)
    elif pattern == ARRIVAL_SLOT:
        return _ticket_slot_iat(total_visitors, duration, visitor_index)
    elif pattern == ARRIVAL_GROUP:
        return _group_iat(total_visitors, duration, visitor_index)
    else:
        return _poisson_iat(total_visitors, duration)


def _uniform_iat(total: int, duration: float) -> float:
    """Constant inter-arrival time."""
    base = duration / max(total, 1)
    return max(0.1, base * random.uniform(0.8, 1.2))


def _poisson_iat(total: int, duration: float) -> float:
    """Exponentially distributed inter-arrival times (Poisson process)."""
    rate = total / max(duration, 1.0)
    return random.expovariate(rate)


def _peak_hour_iat(total: int, duration: float, current_time: float) -> float:
    """
    Time-varying arrival rate with a peak in the first third.
    Uses a sinusoidal intensity function:
      λ(t) = λ_base * (1 + A * sin(π * t / peak_window))
    During peak window, rate is 3x the base rate.
    """
    peak_window = duration * 0.35
    base_rate = total / duration

    if current_time < peak_window:
        # Peak period: rate ramps up then down
        phase = math.pi * current_time / peak_window
        intensity = base_rate * (1.0 + 2.0 * math.sin(phase))
    elif current_time < duration * 0.7:
        # Normal period
        intensity = base_rate * 0.8
    else:
        # Tail-off period
        intensity = base_rate * 0.3

    intensity = max(intensity, 0.01)
    return random.expovariate(intensity)


def _ticket_slot_iat(total: int, duration: float, visitor_index: int) -> float:
    """
    Ticket-slot based arrivals: visitors arrive in waves at fixed intervals.
    Each slot gets a batch of visitors.
    """
    num_slots = 5
    slot_duration = duration / num_slots
    visitors_per_slot = total / num_slots

    # Within each slot, arrivals are uniformly distributed
    iat = slot_duration / max(visitors_per_slot, 1)

    # Add some jitter between slots
    slot_index = visitor_index % int(visitors_per_slot)
    if slot_index == 0 and visitor_index > 0:
        return iat + random.uniform(5.0, 15.0)  # gap between slots

    return max(0.1, iat * random.uniform(0.7, 1.3))


def _group_iat(total: int, duration: float, visitor_index: int) -> float:
    """
    Group arrivals: visitors come in groups of 2-6.
    Short interval within group, longer between groups.
    """
    avg_group_size = 4
    num_groups = total / avg_group_size
    between_group_iat = duration / max(num_groups, 1)

    # Within-group: very short interval
    within_group_iat = 0.3

    # Determine if this visitor starts a new group
    if visitor_index % avg_group_size == 0:
        return max(0.5, between_group_iat * random.uniform(0.5, 1.5))
    else:
        return within_group_iat * random.uniform(0.5, 1.5)
