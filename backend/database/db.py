import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "acm.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # Prevents database locked errors
    conn.execute("PRAGMA busy_timeout=30000")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Satellites table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS satellites (
            id TEXT PRIMARY KEY,
            x REAL, y REAL, z REAL,
            vx REAL, vy REAL, vz REAL,
            fuel_kg REAL DEFAULT 50.0,
            dry_mass REAL DEFAULT 500.0,
            status TEXT DEFAULT 'NOMINAL',
            slot_x REAL, slot_y REAL, slot_z REAL,
            last_updated TEXT
        )
    """)

    # Debris table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS debris (
            id TEXT PRIMARY KEY,
            x REAL, y REAL, z REAL,
            vx REAL, vy REAL, vz REAL,
            last_updated TEXT
        )
    """)

    # Maneuvers table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS maneuvers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            satellite_id TEXT,
            burn_id TEXT,
            burn_time TEXT,
            dv_x REAL, dv_y REAL, dv_z REAL,
            status TEXT DEFAULT 'SCHEDULED',
            created_at TEXT
        )
    """)

    # Collision events log
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS collision_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            satellite_id TEXT,
            debris_id TEXT,
            tca TEXT,
            miss_distance REAL,
            severity TEXT,
            logged_at TEXT
        )
    """)

    # Simulation state table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sim_state (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    # Insert default simulation time
    cursor.execute("""
        INSERT OR IGNORE INTO sim_state (key, value)
        VALUES ('current_time', '2026-03-12T08:00:00.000Z')
    """)

    conn.commit()
    conn.close()
    print("✅ All database tables ready")

def get_sim_time():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM sim_state WHERE key='current_time'")
    row = cursor.fetchone()
    conn.close()
    return row["value"] if row else "2026-03-12T08:00:00.000Z"

def set_sim_time(new_time: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE sim_state SET value=? WHERE key='current_time'", (new_time,))
    conn.commit()
    conn.close()