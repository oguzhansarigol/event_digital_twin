"""
Application configuration settings.
"""
from pathlib import Path

# Directory paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# Simulation defaults
SIMULATION_STEP_SIZE: float = 0.5  # simulation seconds per step
DEFAULT_SPEED_MULTIPLIER: float = 5.0
MAX_VISITORS: int = 5000
DEFAULT_TOTAL_VISITORS: int = 300
DEFAULT_SIMULATION_DURATION: float = 600.0  # seconds

# Visitor defaults
DEFAULT_WALKING_SPEED: float = 30.0  # coordinate-units per sim-second
WALKING_SPEED_VARIANCE: float = 0.3  # ±30% variance
DEFAULT_PATIENCE: float = 60.0  # seconds before considering gate switch
GATE_SWITCH_PROBABILITY: float = 0.3

# Service defaults
DEFAULT_GATE_CAPACITY: int = 3
DEFAULT_SERVICE_TIME: float = 5.0  # seconds per visitor at gate

# Density thresholds
DENSITY_LOW_THRESHOLD: float = 0.3
DENSITY_MEDIUM_THRESHOLD: float = 0.6
DENSITY_HIGH_THRESHOLD: float = 0.8
DENSITY_CRITICAL_THRESHOLD: float = 0.95

# Chart / metrics sampling
METRICS_SAMPLE_INTERVAL: float = 2.0  # record chart data every N sim-seconds

# WebSocket
WS_SEND_INTERVAL: float = 0.05  # real-seconds between state pushes
