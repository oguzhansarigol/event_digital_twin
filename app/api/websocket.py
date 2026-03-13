"""
WebSocket handler for real-time simulation streaming.
Primary interface between frontend and simulation engine.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import SIMULATION_STEP_SIZE
from app.services.simulation_service import SimulationService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.websocket("/ws/simulation")
async def simulation_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for simulation control and state streaming.

    Protocol:
    Client -> Server messages (JSON):
        {"action": "start", "params": {...}}   - Start new simulation
        {"action": "emergency"}                - Trigger emergency
        {"action": "speed", "value": 10}       - Change speed
        {"action": "reset"}                    - Reset simulation
        {"action": "stop"}                     - Stop simulation

    Server -> Client messages (JSON):
        {"type": "state", ...}       - Simulation state update
        {"type": "complete", ...}    - Simulation completed with final report
        {"type": "emergency", ...}   - Emergency mode activated
        {"type": "reset"}            - Simulation reset
        {"type": "error", ...}       - Error message
    """
    await websocket.accept()
    service = SimulationService()
    sim_task: asyncio.Task | None = None

    async def simulation_loop():
        """Background task that runs the simulation and pushes state."""
        step_size = SIMULATION_STEP_SIZE
        try:
            while service.is_running() and not service.is_complete():
                # Run one simulation step
                state = service.step(step_size)
                await websocket.send_json(state)

                # Control pacing based on speed multiplier
                real_delay = step_size / max(service.speed_multiplier, 0.5)
                await asyncio.sleep(real_delay)

            # Simulation complete — send final report
            if service.engine is not None:
                final_report = service.get_final_report()
                await websocket.send_json(final_report)

            service.running = False

        except asyncio.CancelledError:
            logger.info("Simulation loop cancelled")
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected during simulation")
        except Exception as e:
            logger.error(f"Simulation loop error: {e}", exc_info=True)
            try:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                })
            except Exception:
                pass

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get("action", "")

            if action == "start":
                # Cancel any existing simulation
                if sim_task and not sim_task.done():
                    sim_task.cancel()
                    try:
                        await sim_task
                    except asyncio.CancelledError:
                        pass

                service.reset()

                params = data.get("params", {})
                try:
                    initial_state = service.create_simulation(params)
                    await websocket.send_json(initial_state)

                    # Start the simulation loop as a background task
                    sim_task = asyncio.create_task(simulation_loop())

                except Exception as e:
                    logger.error(f"Failed to start simulation: {e}", exc_info=True)
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Failed to start: {str(e)}",
                    })

            elif action == "emergency":
                if service.is_running():
                    result = service.trigger_emergency()
                    await websocket.send_json(result)
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No simulation running",
                    })

            elif action == "speed":
                speed = float(data.get("value", 5.0))
                service.set_speed(speed)

            elif action == "reset":
                if sim_task and not sim_task.done():
                    sim_task.cancel()
                    try:
                        await sim_task
                    except asyncio.CancelledError:
                        pass

                service.reset()
                await websocket.send_json({"type": "reset"})

            elif action == "stop":
                service.running = False
                if sim_task and not sim_task.done():
                    sim_task.cancel()
                    try:
                        await sim_task
                    except asyncio.CancelledError:
                        pass
                await websocket.send_json({"type": "stopped"})

            elif action == "get_report":
                report = service.get_final_report()
                await websocket.send_json(report)

    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Cleanup
        if sim_task and not sim_task.done():
            sim_task.cancel()
            try:
                await sim_task
            except asyncio.CancelledError:
                pass
        service.cleanup()
