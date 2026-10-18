"""Database setup and SQLite connection manager for VoiceDesk."""
import sqlite3
import os
from pathlib import Path
from contextlib import contextmanager
from loguru import logger
from app.config import settings

def get_db_path() -> Path:
    # Handle sqlite:///./voice_desk.db or sqlite:///path
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        path_str = url.replace("sqlite:///", "")
    elif url.startswith("sqlite://"):
        path_str = url.replace("sqlite://", "")
    else:
        path_str = "./voice_desk.db"
    
    path = Path(path_str).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path

@contextmanager
def get_db_connection():
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    # Enable WAL mode for high concurrency
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database transaction error: {e}")
        raise
    finally:
        conn.close()

def init_db():
    """Initializes SQLite schema and tables."""
    db_path = get_db_path()
    logger.info(f"Initializing database at: {db_path}")
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Doctors table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS doctors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                specialization TEXT NOT NULL
            );
        """)

        # 2. Services table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                price_inr INTEGER NOT NULL,
                doctor_id TEXT,
                FOREIGN KEY (doctor_id) REFERENCES doctors (id)
            );
        """)

        # 3. Appointments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS appointments (
                id TEXT PRIMARY KEY,
                patient_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                doctor_id TEXT NOT NULL,
                service_id TEXT NOT NULL,
                date TEXT NOT NULL,
                time_slot TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'confirmed', -- confirmed, cancelled, rescheduled
                notes TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (doctor_id) REFERENCES doctors (id),
                FOREIGN KEY (service_id) REFERENCES services (id)
            );
        """)

        # 4. Call logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS call_logs (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                caller_phone TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                turn_count INTEGER DEFAULT 0,
                avg_latency_ms REAL DEFAULT 0.0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

    logger.info("Database initialized successfully.")
