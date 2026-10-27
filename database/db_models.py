"""SQLite schema definitions and initialization."""
from __future__ import annotations

import logging
import os
import sqlite3
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DATABASE_PATH = os.getenv("DATABASE_PATH", "hiring_system.db")

CREATE_CANDIDATES_TABLE = """
CREATE TABLE IF NOT EXISTS candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL DEFAULT '',
    email TEXT DEFAULT '',
    resume_text TEXT DEFAULT '',
    job_description TEXT DEFAULT '',
    extracted_skills TEXT DEFAULT '[]',
    required_skills TEXT DEFAULT '[]',
    skill_gaps TEXT DEFAULT '[]',
    experience_years INTEGER DEFAULT 0,
    resume_score INTEGER DEFAULT 0,
    resume_qualified INTEGER DEFAULT 0,
    resume_summary TEXT DEFAULT '',
    assigned_task TEXT DEFAULT '',
    task_difficulty TEXT DEFAULT '',
    task_estimated_time TEXT DEFAULT '',
    task_submission TEXT DEFAULT '',
    task_score INTEGER DEFAULT 0,
    task_feedback TEXT DEFAULT '',
    task_strengths TEXT DEFAULT '[]',
    task_weaknesses TEXT DEFAULT '[]',
    hitl_status TEXT DEFAULT 'pending',
    hitl_comments TEXT DEFAULT '',
    final_decision TEXT DEFAULT '',
    decision_justification TEXT DEFAULT '',
    current_stage TEXT DEFAULT 'initialized',
    workflow_complete INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_UPDATE_TRIGGER = """
CREATE TRIGGER IF NOT EXISTS update_candidates_timestamp
AFTER UPDATE ON candidates
FOR EACH ROW
BEGIN
    UPDATE candidates SET updated_at = CURRENT_TIMESTAMP WHERE id = OLD.id;
END;
"""


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get a SQLite database connection with row_factory set."""
    path = db_path or DATABASE_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


def init_database(db_path: Optional[str] = None) -> None:
    """Initialize the database by creating tables if they don't exist."""
    conn = get_connection(db_path)
    try:
        conn.execute(CREATE_CANDIDATES_TABLE)
        conn.execute(CREATE_UPDATE_TRIGGER)
        conn.commit()
        logger.info("Database initialized at: %s", db_path or DATABASE_PATH)
    except sqlite3.Error as e:
        logger.error("Database init failed: %s", e)
        raise
    finally:
        conn.close()