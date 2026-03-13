"""
API routes for scenario management.
"""
from fastapi import APIRouter, HTTPException

from app.services.simulation_service import SimulationService

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])

_service = SimulationService()


@router.get("/")
async def list_scenarios():
    """
    List all available simulation scenarios.
    """
    try:
        scenarios = _service.load_scenarios()
        return {"scenarios": scenarios}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Scenarios file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{scenario_id}")
async def get_scenario(scenario_id: str):
    """
    Get a specific scenario by ID.
    """
    scenarios = _service.load_scenarios()
    for s in scenarios:
        if s["id"] == scenario_id:
            return s
    raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found")
