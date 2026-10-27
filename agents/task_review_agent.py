"""
Task Review Agent - Agent 3.
Evaluates candidate's task submission using a weighted rubric:
correctness (40%), code quality (30%), completeness (20%), best practices (10%).
"""
from __future__ import annotations

import logging
from typing import Any

from graph.state import GraphState
from utils.llm_client import get_llm_client
from utils.prompts import TASK_REVIEW_SYSTEM, TASK_REVIEW_USER

logger = logging.getLogger(__name__)


def task_review_node(state: GraphState) -> dict[str, Any]:
    """LangGraph node: evaluate the task submission."""
    logger.info("═══ TASK REVIEW AGENT: Evaluating submission ═══")

    task_submission = state.get("task_submission", "")
    if not task_submission.strip():
        logger.warning("Empty task submission received")
        return {
            "task_score": 0,
            "task_feedback": "No submission was provided.",
            "task_strengths": [],
            "task_weaknesses": ["No submission provided"],
            "current_stage": "task_reviewed",
            "hitl_status": "pending",
        }

    try:
        llm = get_llm_client()
        user_prompt = TASK_REVIEW_USER.format(
            assigned_task=state.get("assigned_task", ""),
            task_difficulty=state.get("task_difficulty", "Medium"),
            task_submission=task_submission,
        )
        result = llm.invoke_json(TASK_REVIEW_SYSTEM, user_prompt)

        task_score = max(0, min(100, result.get("task_score", 0)))
        logger.info("Task score: %d", task_score)

        return {
            "task_score": task_score,
            "task_feedback": result.get("task_feedback", "No feedback available."),
            "task_strengths": result.get("task_strengths", []),
            "task_weaknesses": result.get("task_weaknesses", []),
            "current_stage": "task_reviewed",
            "hitl_status": "pending",
        }
    except Exception as e:
        logger.error("Task Review failed: %s", e, exc_info=True)
        return {
            "task_score": 0,
            "task_feedback": f"Error during evaluation: {e}",
            "task_strengths": [],
            "task_weaknesses": ["Review system error"],
            "current_stage": "task_review_failed",
            "error_message": str(e),
        }