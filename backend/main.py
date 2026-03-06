from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import uvicorn
import logging
import os

from api.telemetry import router as telemetry_router
from api.maneuver import router as maneuver_router
from api.simulate import router as simulate_router
from api.visualization import router as visualization_router
from database.db import init_db

# ─── Logging Setup ────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("acm_system.log"),
    ]
)
logger = logging.getLogger("ACM")
# ──────────────────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 ACM System Starting Up...")
    init_db()
    logger.info("✅ Database initialized")
    logger.info("✅ Physics engine ready (RK4 + J2 + KD-Tree)")
    logger.info("✅ Ground station network loaded (6 stations)")
    logger.info("✅ ACM ONLINE — Monitoring constellation...")
    yield
    logger.info("🛑 ACM Shutting down gracefully...")

app = FastAPI(
    title="Autonomous Constellation Manager",
    description="Orbital Debris Avoidance & Constellation Management System — National Space Hackathon 2026",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telemetry_router, prefix="/api", tags=["Telemetry"])
app.include_router(maneuver_router, prefix="/api", tags=["Maneuver"])
app.include_router(simulate_router, prefix="/api", tags=["Simulation"])
app.include_router(visualization_router, prefix="/api", tags=["Visualization"])

static_path = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_path):
    app.mount("/", StaticFiles(directory=static_path, html=True), name="static")
    logger.info(f"✅ Serving frontend from {static_path}")

@app.get("/health")
def health_check():
    logger.info("Health check requested")
    return {
        "system": "Autonomous Constellation Manager",
        "status": "ONLINE",
        "version": "1.0.0",
        "endpoints": [
            "POST /api/telemetry",
            "POST /api/maneuver/schedule",
            "POST /api/simulate/step",
            "GET  /api/visualization/snapshot"
        ]
    }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")