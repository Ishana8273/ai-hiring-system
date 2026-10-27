"""
Task Assignment Agent - Agent 2.
Generates a role-specific technical assessment task adjusted for
the candidate's experience level and skill profile.
"""
from __future__ import annotations

import logging
from typing import Any

from graph.state import GraphState
from utils.llm_client import get_llm_client
from utils.prompts import TASK_ASSIGNMENT_SYSTEM, TASK_ASSIGNMENT_USER

logger = logging.getLogger(__name__)


def task_assignment_node(state: GraphState) -> dict[str, Any]:
    """LangGraph node: generate a technical assessment task."""
    logger.info("═══ TASK ASSIGNMENT AGENT: Generating task ═══")
    try:
        llm = get_llm_client()
        user_prompt = TASK_ASSIGNMENT_USER.format(
            job_description=state["job_description"],
            candidate_name=state["candidate_name"],
            extracted_skills=", ".join(state.get("extracted_skills", [])),
            experience_years=state.get("experience_years", 0),
            resume_score=state.get("resume_score", 0),
            skill_gaps=", ".join(state.get("skill_gaps", [])),
        )
        result = llm.invoke_json(TASK_ASSIGNMENT_SYSTEM, user_prompt)

        logger.info(
            "Task generated: difficulty=%s, time=%s",
            result.get("task_difficulty"),
            result.get("task_estimated_time"),
        )

        return {
            "assigned_task": result.get("assigned_task", "No task generated."),
            "task_difficulty": result.get("task_difficulty", "Medium"),
            "task_estimated_time": result.get("task_estimated_time", "1 hour"),
            "current_stage": "task_assigned",
        }
    except Exception as e:
        logger.error("Task Assignment failed: %s", e, exc_info=True)
        return {
            "assigned_task": f"Error generating task: {e}",
            "task_difficulty": "Unknown",
            "task_estimated_time": "Unknown",
            "current_stage": "task_assignment_failed",
            "error_message": str(e),
        }