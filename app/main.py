"""
FastAPI application entry point.
Mounts all routers, serves templates and static files.
"""
import logging
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import TEMPLATES_DIR, STATIC_DIR
from app.api.routes_venue import router as venue_router
from app.api.routes_scenarios import router as scenarios_router
from app.api.routes_simulation import router as simulation_router, set_shared_service
from app.api.websocket import router as ws_router
from app.services.simulation_service import SimulationService

# ── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── FastAPI app ──────────────────────────────────────────
app = FastAPI(
    title="Event Digital Twin",
    description="2D Event Venue Simulation — Crowd Flow Analysis",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static files & templates ─────────────────────────────
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# ── Shared simulation service for REST endpoints ─────────
shared_service = SimulationService()
set_shared_service(shared_service)

# ── Include routers ──────────────────────────────────────
app.include_router(venue_router)
app.include_router(scenarios_router)
app.include_router(simulation_router)
app.include_router(ws_router)


# ── Template routes ──────────────────────────────────────
@app.get("/")
async def index(request: Request):
    """Serve the main frontend page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "Event Digital Twin"}


# ── Startup / Shutdown events ────────────────────────────
@app.on_event("startup")
async def on_startup():
    logger.info("🚀 Event Digital Twin server starting...")
    # Pre-load venue data
    try:
        shared_service.load_venue()
        shared_service.load_scenarios()
        logger.info("✅ Venue and scenario data loaded successfully")
    except Exception as e:
        logger.error(f"❌ Failed to load data: {e}")


@app.on_event("shutdown")
async def on_shutdown():
    logger.info("🛑 Server shutting down...")
    shared_service.cleanup()
