"""
LangGraph StateGraph workflow definition.

Graph structure:
    START -> resume_review -> [qualified?]
        Yes -> task_assignment -> task_review -> human_review -> hiring_decision -> END
        No  -> rejected_end -> END

Key LangGraph concepts used:
    - StateGraph: parameterized by GraphState TypedDict
    - Nodes: functions (state) -> partial_update_dict
    - Conditional edges: dynamic routing via route functions
    - Checkpointer: enables state persistence for HITL interrupt/resume
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import MemorySaver

from agents.resume_review_agent import resume_review_node
from agents.task_assignment_agent import task_assignment_node
from agents.task_review_agent import task_review_node
from agents.hiring_decision_agent import hiring_decision_node
from graph.state import GraphState

logger = logging.getLogger(__name__)


def rejected_end_node(state: GraphState) -> dict[str, Any]:
    """Terminal node for candidates who don't meet the resume threshold."""
    logger.info(
        "═══ REJECTED: %s (score=%d) ═══",
        state.get("candidate_name", "Unknown"),
        state.get("resume_score", 0),
    )
    return {
        "final_decision": "Rejected",
        "decision_justification": (
            f"Did not meet minimum threshold. "
            f"Score: {state.get('resume_score', 0)}/100. "
            f"Gaps: {', '.join(state.get('skill_gaps', []))}"
        ),
        "current_stage": "rejected_at_resume",
        "workflow_complete": True,
        "hitl_status": "not_applicable",
    }


def human_review_node(state: GraphState) -> dict[str, Any]:
    """
    HITL review node.
    In production, this would use LangGraph's interrupt() to pause execution.
    In our Streamlit flow, the UI handles the pause via database polling.
    """
    hitl_status = state.get("hitl_status", "pending")
    if hitl_status in ("approved", "rejected", "on_hold"):
        logger.info("HITL already completed: %s", hitl_status)
        return {"current_stage": "hitl_completed"}
    logger.info("HITL: awaiting recruiter review")
    return {"current_stage": "awaiting_hitl", "hitl_status": "pending"}


def route_after_resume(
    state: GraphState,
) -> Literal["task_assignment", "rejected_end"]:
    """Conditional edge: route based on resume qualification."""
    if state.get("resume_qualified", False):
        logger.info("Routing -> task_assignment (qualified)")
        return "task_assignment"
    logger.info("Routing -> rejected_end (not qualified)")
    return "rejected_end"


def build_hiring_graph() -> StateGraph:
    """Build the complete hiring workflow StateGraph."""
    logger.info("Building hiring workflow graph...")

    graph = StateGraph(GraphState)

    # Register all nodes
    graph.add_node("resume_review", resume_review_node)
    graph.add_node("task_assignment", task_assignment_node)
    graph.add_node("task_review", task_review_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("hiring_decision", hiring_decision_node)
    graph.add_node("rejected_end", rejected_end_node)

    # Entry edge
    graph.add_edge(START, "resume_review")

    # Conditional routing after resume review
    graph.add_conditional_edges(
        "resume_review",
        route_after_resume,
        {
            "task_assignment": "task_assignment",
            "rejected_end": "rejected_end",
        },
    )

    # Linear edges for the qualified path
    graph.add_edge("task_assignment", "task_review")
    graph.add_edge("task_review", "human_review")
    graph.add_edge("human_review", "hiring_decision")

    # Terminal edges
    graph.add_edge("hiring_decision", END)
    graph.add_edge("rejected_end", END)

    logger.info("Graph built successfully")
    return graph


def get_compiled_graph(checkpointer=None):
    """Build and compile graph with checkpointer for HITL support."""
    if checkpointer is None:
        checkpointer = MemorySaver()
    compiled = build_hiring_graph().compile(checkpointer=checkpointer)
    logger.info("Graph compiled with %s", type(checkpointer).__name__)
    return compiled