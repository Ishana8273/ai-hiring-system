"""CRUD operations for the candidates database."""
from __future__ import annotations

import json
import logging
import sqlite3
from typing import Any, Optional

from database.db_models import get_connection, init_database

logger = logging.getLogger(__name__)


def _serialize(data: list | str) -> str:
    """Convert a Python list to JSON string for storage."""
    return json.dumps(data) if isinstance(data, list) else data


def _deserialize(data: str) -> list:
    """Convert stored JSON string back to Python list."""
    if not data:
        return []
    try:
        result = json.loads(data)
        return result if isinstance(result, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def create_candidate(state: dict[str, Any]) -> int:
    """Insert a new candidate record. Returns the auto-generated ID."""
    init_database()
    conn = get_connection()
    try:
        cursor = conn.execute(
            """INSERT INTO candidates (
                name, email, resume_text, job_description,
                extracted_skills, required_skills, skill_gaps,
                experience_years, resume_score, resume_qualified,
                resume_summary, current_stage
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                state.get("candidate_name", ""),
                state.get("candidate_email", ""),
                state.get("resume_text", ""),
                state.get("job_description", ""),
                _serialize(state.get("extracted_skills", [])),
                _serialize(state.get("required_skills", [])),
                _serialize(state.get("skill_gaps", [])),
                state.get("experience_years", 0),
                state.get("resume_score", 0),
                1 if state.get("resume_qualified", False) else 0,
                state.get("resume_summary", ""),
                state.get("current_stage", "resume_reviewed"),
            ),
        )
        conn.commit()
        candidate_id = cursor.lastrowid
        logger.info("Created candidate ID: %d", candidate_id)
        return candidate_id
    except sqlite3.Error as e:
        logger.error("Failed to create candidate: %s", e)
        raise
    finally:
        conn.close()


def update_candidate(candidate_id: int, updates: dict[str, Any]) -> None:
    """Update specific fields of a candidate record."""
    init_database()
    conn = get_connection()

    list_fields = {
        "extracted_skills", "required_skills", "skill_gaps",
        "task_strengths", "task_weaknesses",
    }
    bool_fields = {"resume_qualified", "workflow_complete"}

    processed = {}
    for key, value in updates.items():
        if key in list_fields:
            processed[key] = _serialize(value)
        elif key in bool_fields:
            processed[key] = 1 if value else 0
        else:
            processed[key] = value

    if not processed:
        return

    set_clause = ", ".join(f"{k} = ?" for k in processed.keys())
    values = list(processed.values()) + [candidate_id]

    try:
        conn.execute(f"UPDATE candidates SET {set_clause} WHERE id = ?", values)
        conn.commit()
        logger.info("Updated candidate %d", candidate_id)
    except sqlite3.Error as e:
        logger.error("Failed to update candidate %d: %s", candidate_id, e)
        raise
    finally:
        conn.close()


def get_candidate(candidate_id: int) -> Optional[dict[str, Any]]:
    """Retrieve a single candidate record by ID."""
    init_database()
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM candidates WHERE id = ?", (candidate_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None
    finally:
        conn.close()


def get_all_candidates() -> list[dict[str, Any]]:
    """Retrieve all candidates ordered by most recent first."""
    init_database()
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM candidates ORDER BY created_at DESC"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_pending_candidates() -> list[dict[str, Any]]:
    """Retrieve candidates awaiting HITL review."""
    init_database()
    conn = get_connection()
    try:
        rows = conn.execute(
            """SELECT * FROM candidates
               WHERE hitl_status = 'pending' AND current_stage = 'task_reviewed'
               ORDER BY created_at DESC"""
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_candidates_by_status(status: str) -> list[dict[str, Any]]:
    """Retrieve candidates filtered by final decision status."""
    init_database()
    conn = get_connection()
    try:
        if status:
            rows = conn.execute(
                "SELECT * FROM candidates WHERE final_decision = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM candidates ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def get_dashboard_metrics() -> dict[str, Any]:
    """Compute aggregate metrics for the dashboard."""
    init_database()
    conn = get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        qualified = conn.execute(
            "SELECT COUNT(*) FROM candidates WHERE resume_qualified = 1"
        ).fetchone()[0]
        hired = conn.execute(
            "SELECT COUNT(*) FROM candidates WHERE final_decision = 'Hired'"
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM candidates WHERE final_decision = 'Rejected'"
        ).fetchone()[0]
        on_hold = conn.execute(
            "SELECT COUNT(*) FROM candidates WHERE final_decision = 'On Hold'"
        ).fetchone()[0]
        pending = conn.execute(
            """SELECT COUNT(*) FROM candidates
               WHERE hitl_status = 'pending' AND current_stage = 'task_reviewed'"""
        ).fetchone()[0]
        avg_resume = (
            conn.execute(
                "SELECT AVG(resume_score) FROM candidates WHERE resume_score > 0"
            ).fetchone()[0]
            or 0
        )
        avg_task = (
            conn.execute(
                "SELECT AVG(task_score) FROM candidates WHERE task_score > 0"
            ).fetchone()[0]
            or 0
        )

        return {
            "total_candidates": total,
            "qualified_count": qualified,
            "qualified_pct": round((qualified / total * 100) if total else 0, 1),
            "hired_count": hired,
            "hired_pct": round((hired / total * 100) if total else 0, 1),
            "rejected_count": rejected,
            "on_hold_count": on_hold,
            "pending_count": pending,
            "avg_resume_score": round(avg_resume, 1),
            "avg_task_score": round(avg_task, 1),
        }
    finally:
        conn.close()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert sqlite3.Row to dict with deserialized lists and booleans."""
    d = dict(row)
    for field in [
        "extracted_skills", "required_skills", "skill_gaps",
        "task_strengths", "task_weaknesses",
    ]:
        if field in d:
            d[field] = _deserialize(d[field])
    if "resume_qualified" in d:
        d["resume_qualified"] = bool(d["resume_qualified"])
    if "workflow_complete" in d:
        d["workflow_complete"] = bool(d["workflow_complete"])
    return d