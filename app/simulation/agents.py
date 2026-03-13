"""
Visitor agent creation and lifecycle SimPy processes.
"""
from __future__ import annotations

import random
from typing import TYPE_CHECKING

import simpy

from app.core.constants import (
    STATE_ARRIVING,
    STATE_QUEUING,
    STATE_PROCESSING,
    STATE_MOVING,
    STATE_AT_DESTINATION,
    STATE_LEAVING,
    STATE_EVACUATING,
    STATE_EXITED,
    VISITOR_NORMAL,
    VISITOR_VIP,
    VISITOR_STAFF,
    VISITOR_TYPE_WEIGHTS,
    NODE_ZONE,
)
from app.core.config import (
    DEFAULT_WALKING_SPEED,
    WALKING_SPEED_VARIANCE,
    DEFAULT_PATIENCE,
)
from app.models.domain import Visitor

if TYPE_CHECKING:
    from app.simulation.engine import SimulationEngine


def create_visitor(
    visitor_id: int,
    engine: "SimulationEngine",
    group_id: int | None = None,
) -> Visitor:
    """
    Create a new Visitor with randomized properties.
    """
    # Random type based on weights
    types = list(VISITOR_TYPE_WEIGHTS.keys())
    weights = list(VISITOR_TYPE_WEIGHTS.values())
    vtype = random.choices(types, weights=weights, k=1)[0]

    # Walking speed with variance
    speed = DEFAULT_WALKING_SPEED * random.uniform(
        1.0 - WALKING_SPEED_VARIANCE,
        1.0 + WALKING_SPEED_VARIANCE,
    )

    # VIPs walk slower (they're in no hurry), staff walk faster
    speed_modifiers = {
        "normal": 1.0,
        "vip": 0.85,
        "staff": 1.2,
        "security_staff": 1.3,
        "medical_staff": 1.1,
    }
    speed *= speed_modifiers.get(vtype, 1.0)

    # Target zone selection based on visitor type
    target = _select_target_zone(vtype, engine)

    # Patience: VIPs less patient, staff very patient
    patience = DEFAULT_PATIENCE * random.uniform(0.6, 1.4)
    if vtype == VISITOR_VIP:
        patience *= 0.6
    elif vtype in ("staff", "security_staff", "medical_staff"):
        patience *= 2.0

    # Preferred gate (random or None)
    open_gates = [
        gid for gid, g in engine.gate_manager.gates.items() if g.is_open
    ]
    preferred_gate = random.choice(open_gates) if open_gates and random.random() < 0.4 else None

    # Stay duration at destination
    stay_duration = random.uniform(40.0, 200.0)
    if vtype == VISITOR_VIP:
        stay_duration *= 1.5
    elif vtype in ("staff", "security_staff"):
        stay_duration *= 0.5

    visitor = Visitor(
        id=visitor_id,
        vtype=vtype,
        arrival_time=engine.env.now,
        walking_speed=speed,
        patience=patience,
        preferred_gate=preferred_gate,
        target_zone=target,
        state=STATE_ARRIVING,
        group_id=group_id,
        stay_duration=stay_duration,
    )
    return visitor


def _select_target_zone(vtype: str, engine: "SimulationEngine") -> str:
    """Select a target zone based on visitor type."""
    zone_nodes = [
        n for n, d in engine.graph.nodes(data=True)
        if d.get("node_type") == NODE_ZONE
    ]

    if not zone_nodes:
        return "i_c"  # fallback to central hub

    if vtype == VISITOR_VIP:
        # VIPs prefer vip_area or main_stage
        preferred = [z for z in zone_nodes if z in ("vip_area", "main_stage")]
        if preferred:
            return random.choice(preferred)

    if vtype == "medical_staff":
        if "medical" in zone_nodes:
            return "medical"

    # Normal visitors: weighted random based on zone type
    zone_weights = {
        "main_stage": 35,
        "fan_zone": 25,
        "food_court": 20,
        "vip_area": 2,
        "toilets_w": 5,
        "toilets_e": 5,
        "medical": 3,
    }

    available = [z for z in zone_nodes if z in zone_weights]
    if not available:
        return random.choice(zone_nodes)

    weights = [zone_weights.get(z, 5) for z in available]
    return random.choices(available, weights=weights, k=1)[0]


def visitor_lifecycle(
    env: simpy.Environment,
    visitor: Visitor,
    engine: "SimulationEngine",
):
    """
    Main SimPy process for a visitor's journey through the venue.

    Phases:
    1. Select gate and queue
    2. Get processed through security
    3. Navigate to target zone
    4. Stay at destination
    5. Leave the venue
    """
    try:
        # ── Phase 1: Gate selection and queuing ──────────
        gate_id = engine.gate_manager.select_gate(
            preferred_gate=visitor.preferred_gate,
            visitor_type=visitor.vtype,
        )
        visitor.gate_id = gate_id
        gate = engine.gate_manager.get_gate(gate_id)

        gate_node = engine.nodes[gate_id]
        visitor.x = gate_node["x"]
        visitor.y = gate_node["y"]
        visitor.current_node = gate_id

        visitor.state = STATE_QUEUING
        gate.add_to_queue(visitor.id)
        arrival_at_gate = env.now

        # Request service at gate
        with gate.resource.request() as req:
            yield req

            # ── Phase 2: Being processed (security check) ──
            gate.remove_from_queue(visitor.id)
            visitor.state = STATE_PROCESSING

            service_time = gate.get_service_time(visitor.vtype)
            yield env.timeout(service_time)

            wait_time = env.now - arrival_at_gate
            visitor.wait_time = wait_time
            gate.record_processed(wait_time)
            engine.metrics.record_wait_time(gate_id, wait_time)

        # Check emergency before proceeding
        if engine.emergency_mode:
            yield from _evacuate(env, visitor, engine)
            return

        # ── Phase 3: Navigate to target zone ─────────────
        visitor.state = STATE_MOVING
        engine.metrics.record_entry(visitor.id, gate_id, env.now)

        # Find first interior node connected to this gate
        neighbors = list(engine.graph.neighbors(gate_id))
        interior_nodes = [
            n for n in neighbors
            if engine.graph.nodes[n].get("node_type") != "emergency_exit"
        ]
        if not interior_nodes:
            interior_nodes = neighbors

        first_node = interior_nodes[0] if interior_nodes else gate_id

        # Move from gate to first interior node
        yield from _move_between_nodes(env, visitor, engine, gate_id, first_node)

        if engine.emergency_mode:
            yield from _evacuate(env, visitor, engine)
            return

        # Navigate to target zone
        from app.simulation.routing import find_congestion_aware_path
        path = find_congestion_aware_path(engine.graph, first_node, visitor.target_zone)

        if not path or len(path) < 2:
            # Fallback: go to central hub
            from app.simulation.routing import find_shortest_path
            path = find_shortest_path(engine.graph, first_node, "i_c")

        if path and len(path) >= 2:
            for i in range(len(path) - 1):
                if engine.emergency_mode:
                    yield from _evacuate(env, visitor, engine)
                    return
                yield from _move_between_nodes(env, visitor, engine, path[i], path[i + 1])

        # ── Phase 4: At destination ──────────────────────
        visitor.state = STATE_AT_DESTINATION
        zone_id = visitor.target_zone
        engine.zone_add_visitor(zone_id, visitor.id)

        # Stay at destination in small chunks (to check for emergency)
        remaining = visitor.stay_duration
        chunk_size = 3.0
        while remaining > 0 and not engine.emergency_mode:
            wait = min(remaining, chunk_size)
            yield env.timeout(wait)
            remaining -= wait

        engine.zone_remove_visitor(zone_id, visitor.id)

        if engine.emergency_mode:
            yield from _evacuate(env, visitor, engine)
            return

        # ── Phase 5: Leave the venue ─────────────────────
        visitor.state = STATE_LEAVING
        from app.simulation.routing import find_nearest_exit, find_shortest_path

        exit_node = find_nearest_exit(engine.graph, visitor.current_node)
        if exit_node:
            path = find_shortest_path(engine.graph, visitor.current_node, exit_node)
            if path and len(path) >= 2:
                for i in range(len(path) - 1):
                    if engine.emergency_mode:
                        yield from _evacuate(env, visitor, engine)
                        return
                    yield from _move_between_nodes(env, visitor, engine, path[i], path[i + 1])

        # Exited
        visitor.state = STATE_EXITED
        engine.metrics.record_exit(visitor.id, env.now)
        engine.remove_visitor(visitor.id)

    except simpy.Interrupt:
        # Interrupted by emergency
        yield from _evacuate(env, visitor, engine)


def _move_between_nodes(
    env: simpy.Environment,
    visitor: Visitor,
    engine: "SimulationEngine",
    from_id: str,
    to_id: str,
):
    """
    SimPy generator: move visitor from one node to another.
    Sets interpolation data for smooth frontend rendering.
    """
    from_node = engine.nodes.get(from_id, {})
    to_node = engine.nodes.get(to_id, {})

    fx, fy = from_node.get("x", visitor.x), from_node.get("y", visitor.y)
    tx, ty = to_node.get("x", visitor.x), to_node.get("y", visitor.y)

    import math
    distance = math.sqrt((tx - fx) ** 2 + (ty - fy) ** 2)
    travel_time = distance / max(visitor.walking_speed, 1.0)
    travel_time = max(travel_time, 0.1)

    visitor.state = STATE_MOVING
    visitor.move_from = (fx, fy)
    visitor.move_to = (tx, ty)
    visitor.move_start = env.now
    visitor.move_end = env.now + travel_time

    # Track edge usage for congestion
    engine.edge_usage_increment(from_id, to_id)

    yield env.timeout(travel_time)

    engine.edge_usage_decrement(from_id, to_id)

    visitor.x = tx
    visitor.y = ty
    visitor.current_node = to_id


def _evacuate(
    env: simpy.Environment,
    visitor: Visitor,
    engine: "SimulationEngine",
):
    """
    Emergency evacuation process for a single visitor.
    """
    visitor.state = STATE_EVACUATING

    # Remove from any zone
    for zone_id in list(engine.zone_occupancy.keys()):
        engine.zone_remove_visitor(zone_id, visitor.id)

    # Find nearest exit considering congestion
    from app.simulation.routing import find_nearest_exit, find_congestion_aware_path

    current = visitor.current_node or "i_c"
    exit_node = find_nearest_exit(engine.graph, current)

    if not exit_node:
        visitor.state = STATE_EXITED
        engine.remove_visitor(visitor.id)
        engine.metrics.record_exit(visitor.id, env.now)
        return

    path = find_congestion_aware_path(engine.graph, current, exit_node)
    if not path or len(path) < 2:
        from app.simulation.routing import find_shortest_path
        path = find_shortest_path(engine.graph, current, exit_node)

    if path and len(path) >= 2:
        # Speed boost during evacuation
        original_speed = visitor.walking_speed
        visitor.walking_speed *= 1.4

        for i in range(len(path) - 1):
            yield from _move_between_nodes(env, visitor, engine, path[i], path[i + 1])
            visitor.state = STATE_EVACUATING  # keep state as evacuating

        visitor.walking_speed = original_speed

    visitor.state = STATE_EXITED
    engine.metrics.record_exit(visitor.id, env.now)
    engine.metrics.record_evacuation_exit(visitor.id, env.now)
    engine.remove_visitor(visitor.id)
