"""
API routes for venue data.
"""
from fastapi import APIRouter, HTTPException

from app.services.simulation_service import SimulationService

router = APIRouter(prefix="/api/venue", tags=["venue"])

# Shared service instance
_service = SimulationService()


@router.get("/")
async def get_venue():
    """
    Get the full venue configuration including nodes, edges, gates, and zones.
    Used by the frontend to render the 2D map.
    """
    try:
        venue = _service.load_venue()
        return venue
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Venue data file not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gates")
async def get_gates():
    """Get gate configurations."""
    venue = _service.load_venue()
    return venue.get("gates", {})


@router.get("/zones")
async def get_zones():
    """Get zone configurations."""
    venue = _service.load_venue()
    return venue.get("zones", {})
