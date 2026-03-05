from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from database.db import get_connection, get_sim_time
from physics.conjunction import find_conjunctions, get_critical_conjunctions
import datetime

router = APIRouter()

# --- Request Models ---
class Vector3(BaseModel):
    x: float
    y: float
    z: float

class SpaceObject(BaseModel):
    id: str
    type: str  # "SATELLITE" or "DEBRIS"
    r: Vector3
    v: Vector3

class TelemetryRequest(BaseModel):
    timestamp: str
    objects: List[SpaceObject]

# --- In-memory state cache (fast access) ---
_satellite_cache = {}
_debris_cache = {}

def get_satellite_cache():
    return _satellite_cache

def get_debris_cache():
    return _debris_cache

@router.post("/telemetry")
async def ingest_telemetry(payload: TelemetryRequest):
    """
    Ingest high-frequency orbital state vectors.
    Updates internal physics state for all objects.
    """
    conn = get_connection()
    cursor = conn.cursor()

    processed = 0
    timestamp = payload.timestamp

    for obj in payload.objects:
        if obj.type.upper() == "DEBRIS":
            # Update debris in DB and cache
            cursor.execute("""
                INSERT INTO debris (id, x, y, z, vx, vy, vz, last_updated)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    x=excluded.x, y=excluded.y, z=excluded.z,
                    vx=excluded.vx, vy=excluded.vy, vz=excluded.vz,
                    last_updated=excluded.last_updated
            """, (
                obj.id,
                obj.r.x, obj.r.y, obj.r.z,
                obj.v.x, obj.v.y, obj.v.z,
                timestamp
            ))

            _debris_cache[obj.id] = {
                "id": obj.id,
                "x": obj.r.x, "y": obj.r.y, "z": obj.r.z,
                "vx": obj.v.x, "vy": obj.v.y, "vz": obj.v.z
            }

        elif obj.type.upper() == "SATELLITE":
            # Check if satellite exists
            cursor.execute("SELECT fuel_kg, slot_x, slot_y, slot_z FROM satellites WHERE id=?", (obj.id,))
            existing = cursor.fetchone()

            if existing:
                cursor.execute("""
                    UPDATE satellites SET
                        x=?, y=?, z=?, vx=?, vy=?, vz=?, last_updated=?
                    WHERE id=?
                """, (
                    obj.r.x, obj.r.y, obj.r.z,
                    obj.v.x, obj.v.y, obj.v.z,
                    timestamp, obj.id
                ))
            else:
                # New satellite — assign slot as current position
                cursor.execute("""
                    INSERT INTO satellites
                        (id, x, y, z, vx, vy, vz, fuel_kg, status,
                         slot_x, slot_y, slot_z, last_updated)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 50.0, 'NOMINAL', ?, ?, ?, ?)
                """, (
                    obj.id,
                    obj.r.x, obj.r.y, obj.r.z,
                    obj.v.x, obj.v.y, obj.v.z,
                    obj.r.x, obj.r.y, obj.r.z,
                    timestamp
                ))

            _satellite_cache[obj.id] = {
                "id": obj.id,
                "x": obj.r.x, "y": obj.r.y, "z": obj.r.z,
                "vx": obj.v.x, "vy": obj.v.y, "vz": obj.v.z
            }

        processed += 1

    conn.commit()
    conn.close()

    # Quick conjunction check on cached data
    satellites = list(_satellite_cache.values())
    debris_list = list(_debris_cache.values())

    active_warnings = 0
    if satellites and debris_list:
        # Quick 10-minute horizon check for warnings
        cdms = find_conjunctions(satellites, debris_list, horizon_seconds=600)
        critical = get_critical_conjunctions(cdms)
        active_warnings = len(critical)

    return {
        "status": "ACK",
        "processed_count": processed,
        "active_cdm_warnings": active_warnings
    }