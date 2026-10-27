"""
Shared GraphState definition for the AI Hiring System.

LangGraph uses this state as the single source of truth. Every node
reads from and writes to this shared state. Each node function receives
the current state and returns a partial update dict merged back automatically.
"""
from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


class GraphState(TypedDict):
    """Shared state schema for the AI Hiring System LangGraph workflow."""

    # Stage 1: Input
    candidate_name: str
    candidate_email: str
    resume_text: str
    job_description: str

    # Stage 2: Resume Review
    extracted_skills: list[str]
    required_skills: list[str]
    skill_gaps: list[str]
    experience_years: int
    resume_score: int
    resume_qualified: bool
    resume_summary: str

    # Stage 3: Task Assignment
    assigned_task: str
    task_difficulty: str
    task_estimated_time: str

    # Stage 4: Task Review
    task_submission: str
    task_score: int
    task_feedback: str
    task_strengths: list[str]
    task_weaknesses: list[str]

    # Stage 5: HITL
    hitl_status: str
    hitl_comments: str

    # Stage 6: Decision
    final_decision: str
    decision_justification: str

    # Stage 7: Metadata
    current_stage: str
    candidate_id: int
    error_message: str
    workflow_complete: bool


class CandidateInput(BaseModel):
    """Pydantic model for validating candidate input data."""
    candidate_name: str = Field(default="")
    candidate_email: str = Field(default="")
    resume_text: str = Field(...)
    job_description: str = Field(...)


class ResumeReviewOutput(BaseModel):
    """Structured output from the Resume Review Agent."""
    candidate_name: str
    candidate_email: str
    extracted_skills: list[str]
    required_skills: list[str]
    skill_gaps: list[str]
    experience_years: int
    resume_score: int = Field(ge=0, le=100)
    resume_summary: str


class TaskAssignmentOutput(BaseModel):
    """Structured output from the Task Assignment Agent."""
    assigned_task: str
    task_difficulty: str
    task_estimated_time: str


class TaskReviewOutput(BaseModel):
    """Structured output from the Task Review Agent."""
    task_score: int = Field(ge=0, le=100)
    task_feedback: str
    task_strengths: list[str]
    task_weaknesses: list[str]


class HiringDecisionOutput(BaseModel):
    """Structured output from the Hiring Decision Agent."""
    final_decision: str
    decision_justification: str


def create_initial_state(
    resume_text: str,
    job_description: str,
    candidate_name: str = "",
    candidate_email: str = "",
) -> GraphState:
    """Create an initial GraphState with default values for all fields."""
    return GraphState(
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        resume_text=resume_text,
        job_description=job_description,
        extracted_skills=[],
        required_skills=[],
        skill_gaps=[],
        experience_years=0,
        resume_score=0,
        resume_qualified=False,
        resume_summary="",
        assigned_task="",
        task_difficulty="",
        task_estimated_time="",
        task_submission="",
        task_score=0,
        task_feedback="",
        task_strengths=[],
        task_weaknesses=[],
        hitl_status="pending",
        hitl_comments="",
        final_decision="",
        decision_justification="",
        current_stage="initialized",
        candidate_id=0,
        error_message="",
        workflow_complete=False,
    )