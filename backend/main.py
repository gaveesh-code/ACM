from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import uvicorn

from api.telemetry import router as telemetry_router
from api.maneuver import router as maneuver_router
from api.simulate import router as simulate_router
from api.visualization import router as visualization_router
from database.db import init_db

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print("🚀 ACM System Starting Up...")
    init_db()
    print("✅ Database initialized")
    print("✅ Physics engine ready")
    print("✅ ACM Online — Monitoring constellation...")
    yield
    # Shutdown
    print("🛑 ACM Shutting down...")

app = FastAPI(
    title="Autonomous Constellation Manager",
    description="Orbital Debris Avoidance & Constellation Management System",
    version="1.0.0",
    lifespan=lifespan
)

# Allow frontend to talk to backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register all API routes
app.include_router(telemetry_router, prefix="/api", tags=["Telemetry"])
app.include_router(maneuver_router, prefix="/api", tags=["Maneuver"])
app.include_router(simulate_router, prefix="/api", tags=["Simulation"])
app.include_router(visualization_router, prefix="/api", tags=["Visualization"])

@app.get("/")
def root():
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
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )