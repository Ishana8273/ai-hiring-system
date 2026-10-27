"""
Resume Review Agent - Agent 1.
Extracts candidate info, compares skills vs JD, calculates score,
identifies skill gaps, and determines qualification status.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from dotenv import load_dotenv

from graph.state import GraphState
from utils.llm_client import get_llm_client
from utils.prompts import RESUME_PARSE_SYSTEM, RESUME_PARSE_USER

load_dotenv()
logger = logging.getLogger(__name__)

RESUME_SCORE_THRESHOLD = int(os.getenv("RESUME_SCORE_THRESHOLD", "60"))


def resume_review_node(state: GraphState) -> dict[str, Any]:
    """LangGraph node: analyze resume against job description."""
    logger.info("═══ RESUME REVIEW AGENT: Starting ═══")
    try:
        llm = get_llm_client()
        user_prompt = RESUME_PARSE_USER.format(
            resume_text=state["resume_text"],
            job_description=state["job_description"],
        )
        result = llm.invoke_json(RESUME_PARSE_SYSTEM, user_prompt)

        resume_score = max(0, min(100, result.get("resume_score", 0)))
        resume_qualified = resume_score >= RESUME_SCORE_THRESHOLD

        logger.info(
            "Score=%d, Qualified=%s, Skills=%d, Gaps=%d",
            resume_score,
            resume_qualified,
            len(result.get("extracted_skills", [])),
            len(result.get("skill_gaps", [])),
        )

        return {
            "candidate_name": result.get(
                "candidate_name", state.get("candidate_name", "Unknown")
            ),
            "candidate_email": result.get(
                "candidate_email", state.get("candidate_email", "")
            ),
            "extracted_skills": result.get("extracted_skills", []),
            "required_skills": result.get("required_skills", []),
            "skill_gaps": result.get("skill_gaps", []),
            "experience_years": result.get("experience_years", 0),
            "resume_score": resume_score,
            "resume_qualified": resume_qualified,
            "resume_summary": result.get("resume_summary", "No summary available."),
            "current_stage": "resume_reviewed",
        }
    except Exception as e:
        logger.error("Resume Review failed: %s", e, exc_info=True)
        return {
            "resume_score": 0,
            "resume_qualified": False,
            "resume_summary": f"Error during review: {e}",
            "current_stage": "resume_review_failed",
            "error_message": str(e),
        }