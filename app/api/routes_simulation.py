"""
REST API routes for simulation control (non-WebSocket).
Useful for polling-based clients or one-off operations.
"""
from fastapi import APIRouter, HTTPException
from app.models.schemas import SimulationParams

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

# NOTE: Primary simulation interaction is via WebSocket.
# These REST endpoints provide supplementary access.

# We'll keep a reference that main.py can set
_shared_service = None


def set_shared_service(service):
    global _shared_service
    _shared_service = service


@router.post("/start")
async def start_simulation(params: SimulationParams):
    """Start a new simulation with given parameters (REST alternative to WebSocket)."""
    if _shared_service is None:
        raise HTTPException(status_code=500, detail="Service not initialized")

    try:
        state = _shared_service.create_simulation(params.model_dump())
        return {"status": "started", "initial_state": state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/step")
async def step_simulation():
    """Advance simulation by one step."""
    if _shared_service is None or not _shared_service.is_running():
        raise HTTPException(status_code=400, detail="No simulation running")

    state = _shared_service.step()
    return state


@router.post("/emergency")
async def trigger_emergency():
    """Trigger emergency evacuation mode."""
    if _shared_service is None or not _shared_service.is_running():
        raise HTTPException(status_code=400, detail="No simulation running")

    result = _shared_service.trigger_emergency()
    return result


@router.get("/metrics")
async def get_metrics():
    """Get current simulation metrics."""
    if _shared_service is None:
        return {}
    return _shared_service.get_metrics()


@router.get("/recommendations")
async def get_recommendations():
    """Get current recommendations."""
    if _shared_service is None:
        return {"recommendations": []}
    return {"recommendations": _shared_service.get_recommendations()}


@router.get("/chart-data")
async def get_chart_data():
    """Get time-series chart data."""
    if _shared_service is None:
        return {}
    return _shared_service.get_chart_data()


@router.post("/reset")
async def reset_simulation():
    """Reset the current simulation."""
    if _shared_service is not None:
        _shared_service.reset()
    return {"status": "reset"}
