"""
Application-wide constants and enumerations.
"""

# ── Visitor types ──────────────────────────────────────
VISITOR_NORMAL = "normal"
VISITOR_VIP = "vip"
VISITOR_STAFF = "staff"
VISITOR_SECURITY = "security_staff"
VISITOR_MEDICAL = "medical_staff"

VISITOR_TYPES = [VISITOR_NORMAL, VISITOR_VIP, VISITOR_STAFF, VISITOR_SECURITY, VISITOR_MEDICAL]

# Probability weights for random type assignment
VISITOR_TYPE_WEIGHTS = {
    VISITOR_NORMAL: 0.75,
    VISITOR_VIP: 0.10,
    VISITOR_STAFF: 0.08,
    VISITOR_SECURITY: 0.04,
    VISITOR_MEDICAL: 0.03,
}

# ── Visitor states ─────────────────────────────────────
STATE_ARRIVING = "arriving"
STATE_QUEUING = "queuing"
STATE_PROCESSING = "processing"
STATE_MOVING = "moving"
STATE_AT_DESTINATION = "at_destination"
STATE_WANDERING = "wandering"
STATE_LEAVING = "leaving"
STATE_EVACUATING = "evacuating"
STATE_EXITED = "exited"

# ── Node types ─────────────────────────────────────────
NODE_ENTRY_GATE = "entry_gate"
NODE_EMERGENCY_EXIT = "emergency_exit"
NODE_SECURITY = "security"
NODE_INTERSECTION = "intersection"
NODE_ZONE = "zone"

# ── Arrival patterns ──────────────────────────────────
ARRIVAL_UNIFORM = "uniform"
ARRIVAL_POISSON = "poisson"
ARRIVAL_PEAK = "peak_hour"
ARRIVAL_SLOT = "ticket_slot"
ARRIVAL_GROUP = "group"

# ── Zone types ─────────────────────────────────────────
ZONE_ENTERTAINMENT = "entertainment"
ZONE_SERVICE = "service"
ZONE_RESTRICTED = "restricted"

# ── Gate statuses ──────────────────────────────────────
GATE_OPEN = "open"
GATE_CLOSED = "closed"
GATE_LIMITED = "limited"

# ── Scenario IDs ───────────────────────────────────────
SCENARIO_NORMAL = "normal_flow"
SCENARIO_PEAK = "peak_hour"
SCENARIO_GATE_FAILURE = "gate_failure"
SCENARIO_SECURITY_DELAY = "security_delay"
SCENARIO_EVACUATION = "emergency_evacuation"

# ── Colors for frontend ───────────────────────────────
VISITOR_COLORS = {
    VISITOR_NORMAL: "#4A90D9",
    VISITOR_VIP: "#FFD700",
    VISITOR_STAFF: "#27AE60",
    VISITOR_SECURITY: "#8E44AD",
    VISITOR_MEDICAL: "#E74C3C",
}

STATE_COLORS = {
    STATE_QUEUING: "#F39C12",
    STATE_PROCESSING: "#E67E22",
    STATE_MOVING: "#3498DB",
    STATE_AT_DESTINATION: "#2ECC71",
    STATE_EVACUATING: "#E74C3C",
    STATE_LEAVING: "#95A5A6",
}
