"""
Hiring Decision Agent - Agent 4.
Combines resume_score + task_score + recruiter HITL input to generate
a final hiring decision with comprehensive justification.
"""
from __future__ import annotations

import logging
from typing import Any

from database.db_operations import update_candidate
from graph.state import GraphState
from utils.llm_client import get_llm_client
from utils.prompts import HIRING_DECISION_SYSTEM, HIRING_DECISION_USER

logger = logging.getLogger(__name__)


def hiring_decision_node(state: GraphState) -> dict[str, Any]:
    """LangGraph node: make the final hiring decision."""
    logger.info("═══ HIRING DECISION AGENT: Making decision ═══")
    try:
        llm = get_llm_client()
        user_prompt = HIRING_DECISION_USER.format(
            candidate_name=state.get("candidate_name", "Unknown"),
            candidate_email=state.get("candidate_email", ""),
            experience_years=state.get("experience_years", 0),
            resume_score=state.get("resume_score", 0),
            extracted_skills=", ".join(state.get("extracted_skills", [])),
            skill_gaps=", ".join(state.get("skill_gaps", [])),
            resume_summary=state.get("resume_summary", ""),
            assigned_task_summary=state.get("assigned_task", "")[:500],
            task_score=state.get("task_score", 0),
            task_feedback=state.get("task_feedback", ""),
            task_strengths=", ".join(state.get("task_strengths", [])),
            task_weaknesses=", ".join(state.get("task_weaknesses", [])),
            hitl_status=state.get("hitl_status", "pending"),
            hitl_comments=state.get("hitl_comments", ""),
        )
        result = llm.invoke_json(HIRING_DECISION_SYSTEM, user_prompt)

        final_decision = result.get("final_decision", "On Hold")
        if final_decision not in ("Hired", "Rejected", "On Hold"):
            if "hire" in final_decision.lower():
                final_decision = "Hired"
            elif "reject" in final_decision.lower():
                final_decision = "Rejected"
            else:
                final_decision = "On Hold"

        decision_justification = result.get(
            "decision_justification", "No justification provided."
        )

        logger.info("Final decision: %s", final_decision)

        # Persist to database
        candidate_id = state.get("candidate_id", 0)
        if candidate_id:
            try:
                update_candidate(
                    candidate_id,
                    {
                        "final_decision": final_decision,
                        "decision_justification": decision_justification,
                        "current_stage": "decision_made",
                        "workflow_complete": True,
                    },
                )
            except Exception as db_err:
                logger.error("DB persist failed: %s", db_err)

        return {
            "final_decision": final_decision,
            "decision_justification": decision_justification,
            "current_stage": "decision_made",
            "workflow_complete": True,
        }
    except Exception as e:
        logger.error("Hiring Decision failed: %s", e, exc_info=True)
        return {
            "final_decision": "On Hold",
            "decision_justification": f"Decision error: {e}",
            "current_stage": "decision_failed",
            "error_message": str(e),
            "workflow_complete": True,
        }