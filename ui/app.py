"""
Streamlit frontend for the AI Hiring System.
Four tabs: New Candidate, Task Submission, Recruiter Review (HITL), Dashboard.
"""
from __future__ import annotations

import logging
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

from database.db_models import init_database
from database.db_operations import (
    create_candidate,
    get_all_candidates,
    get_candidate,
    get_candidates_by_status,
    get_dashboard_metrics,
    get_pending_candidates,
    update_candidate,
)
from graph.state import create_initial_state
from utils.resume_parser import extract_text_from_upload

init_database()

st.set_page_config(
    page_title="AI Hiring System", page_icon="🤖", layout="wide"
)

st.markdown(
    """
<style>
    .score-high { color: #2ca02c; font-weight: bold; }
    .score-medium { color: #ff7f0e; font-weight: bold; }
    .score-low { color: #d62728; font-weight: bold; }
</style>
""",
    unsafe_allow_html=True,
)


def render_progress_stepper(current_stage: str):
    """Render a visual progress indicator for workflow stages."""
    stages = [
        ("📄 Resume", "resume_reviewed"),
        ("📝 Task", "task_assigned"),
        ("🔍 Review", "task_reviewed"),
        ("👤 HITL", "hitl_completed"),
        ("✅ Decision", "decision_made"),
    ]
    current_idx = -1
    for i, (_, sid) in enumerate(stages):
        if current_stage == sid or current_stage.startswith(sid.split("_")[0]):
            current_idx = i
    if current_stage in ("rejected_at_resume", "decision_made"):
        current_idx = len(stages) - 1
    elif current_stage == "awaiting_hitl":
        current_idx = 3
    elif current_stage == "task_submitted":
        current_idx = 2

    cols = st.columns(len(stages))
    for i, (label, _) in enumerate(stages):
        with cols[i]:
            if i < current_idx:
                st.markdown(f"✅ **{label}**")
            elif i == current_idx:
                st.markdown(f"🔵 **{label}**")
            else:
                st.markdown(f"⬜ {label}")


def display_score(score: int, label: str = "Score"):
    """Display a score with color-coded emoji."""
    color = "🟢" if score >= 70 else "🟡" if score >= 50 else "🔴"
    st.metric(label=label, value=f"{score}/100", delta=f"{color}")


# ── TAB 1: NEW CANDIDATE ──────────────────────────────────────────


def render_new_candidate_tab():
    """Upload resume + JD, run AI screening, generate task."""
    st.header("📄 New Candidate Screening")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Resume Upload")
        uploaded_file = st.file_uploader(
            "Upload resume (PDF/TXT)", type=["pdf", "txt"], key="resume_upload"
        )
        resume_text = ""
        if uploaded_file:
            try:
                resume_text = extract_text_from_upload(uploaded_file)
                st.success(f"✅ {len(resume_text)} characters extracted")
            except Exception as e:
                st.error(f"Extraction failed: {e}")
        st.markdown("**— OR paste text directly —**")
        pasted = st.text_area(
            "Paste resume text", height=200, key="pasted_resume"
        )
        if pasted.strip():
            resume_text = pasted.strip()

    with col2:
        st.subheader("Job Description")
        job_description = st.text_area(
            "Paste job description", height=400, key="jd_input"
        )

    st.divider()

    if st.button(
        "🚀 Start AI Screening", type="primary", use_container_width=True
    ):
        if not resume_text.strip():
            st.error("Please provide a resume.")
            return
        if not job_description.strip():
            st.error("Please provide a job description.")
            return

        with st.spinner("🔍 AI is analyzing the resume..."):
            try:
                from agents.resume_review_agent import resume_review_node
                from agents.task_assignment_agent import task_assignment_node

                state = create_initial_state(
                    resume_text=resume_text, job_description=job_description
                )
                state.update(resume_review_node(state))
                candidate_id = create_candidate(state)
                state["candidate_id"] = candidate_id
                st.session_state["current_candidate_id"] = candidate_id
                st.session_state["current_state"] = state

                st.success("✅ Resume review complete!")
                render_progress_stepper(state.get("current_stage", ""))

                c1, c2, c3 = st.columns(3)
                with c1:
                    display_score(state.get("resume_score", 0), "Resume Score")
                with c2:
                    st.metric(
                        "Experience",
                        f"{state.get('experience_years', 0)} years",
                    )
                with c3:
                    st.metric(
                        "Status",
                        "✅ Qualified"
                        if state.get("resume_qualified")
                        else "❌ Not Qualified",
                    )

                st.write(
                    f"**Name:** {state.get('candidate_name')} | "
                    f"**Email:** {state.get('candidate_email')}"
                )

                cs, cg = st.columns(2)
                with cs:
                    st.write("**Extracted Skills:**")
                    for s in state.get("extracted_skills", []):
                        st.markdown(f"  • {s}")
                with cg:
                    st.write("**Skill Gaps:**")
                    for g in state.get("skill_gaps", []):
                        st.markdown(f"  • {g}")

                st.info(state.get("resume_summary", ""))

                if state.get("resume_qualified"):
                    st.divider()
                    st.info("📋 Generating technical task...")
                    state.update(task_assignment_node(state))
                    update_candidate(
                        candidate_id,
                        {
                            "assigned_task": state["assigned_task"],
                            "task_difficulty": state["task_difficulty"],
                            "task_estimated_time": state["task_estimated_time"],
                            "current_stage": "task_assigned",
                        },
                    )
                    st.session_state["current_state"] = state
                    st.success(
                        "✅ Task generated! Go to 'Task Submission' tab."
                    )
                    st.write(
                        f"**Difficulty:** {state['task_difficulty']} | "
                        f"**Time:** {state['task_estimated_time']}"
                    )
                    st.markdown(state["assigned_task"])
                else:
                    update_candidate(
                        candidate_id,
                        {
                            "final_decision": "Rejected",
                            "decision_justification": state.get(
                                "resume_summary", ""
                            ),
                            "current_stage": "rejected_at_resume",
                            "workflow_complete": True,
                        },
                    )
            except Exception as e:
                st.error(f"Error: {e}")
                logger.error("Screening error: %s", e, exc_info=True)


# ── TAB 2: TASK SUBMISSION ────────────────────────────────────────


def render_task_submission_tab():
    """View assigned task, submit solution, get AI evaluation."""
    st.header("📝 Task Submission & Review")

    candidates = get_all_candidates()
    task_cands = [
        c
        for c in candidates
        if c.get("current_stage") in ("task_assigned", "task_submitted")
        and c.get("assigned_task")
    ]

    if not task_cands:
        if "current_candidate_id" in st.session_state:
            c = get_candidate(st.session_state["current_candidate_id"])
            if c and c.get("assigned_task"):
                task_cands = [c]
        if not task_cands:
            st.info(
                "No pending tasks. Screen a candidate first in 'New Candidate'."
            )
            return

    options = {
        f"{c['name']} (ID:{c['id']}) Score:{c['resume_score']}": c["id"]
        for c in task_cands
    }
    selected = st.selectbox("Select candidate", list(options.keys()))
    candidate = get_candidate(options[selected])
    if not candidate:
        st.error("Candidate not found.")
        return

    render_progress_stepper(candidate.get("current_stage", ""))

    st.subheader("📋 Assigned Task")
    st.markdown(candidate.get("assigned_task", ""))
    st.write(
        f"**Difficulty:** {candidate.get('task_difficulty')} | "
        f"**Time:** {candidate.get('task_estimated_time')}"
    )
    st.divider()

    st.subheader("✍️ Submit Solution")
    submission = st.text_area(
        "Paste the candidate's solution here", height=400, key="task_sub_input"
    )

    if st.button(
        "📤 Submit & Evaluate", type="primary", use_container_width=True
    ):
        if not submission.strip():
            st.error("Please provide a submission.")
            return
        with st.spinner("🔍 AI is evaluating..."):
            try:
                from agents.task_review_agent import task_review_node

                result = task_review_node(
                    {
                        "assigned_task": candidate.get("assigned_task", ""),
                        "task_difficulty": candidate.get(
                            "task_difficulty", ""
                        ),
                        "task_submission": submission,
                    }
                )
                update_candidate(
                    candidate["id"],
                    {
                        "task_submission": submission,
                        "task_score": result.get("task_score", 0),
                        "task_feedback": result.get("task_feedback", ""),
                        "task_strengths": result.get("task_strengths", []),
                        "task_weaknesses": result.get("task_weaknesses", []),
                        "current_stage": "task_reviewed",
                        "hitl_status": "pending",
                    },
                )
                st.success("✅ Evaluation complete!")
                display_score(result.get("task_score", 0), "Task Score")
                st.write(result.get("task_feedback", ""))

                c1, c2 = st.columns(2)
                with c1:
                    st.write("**Strengths:**")
                    for s in result.get("task_strengths", []):
                        st.markdown(f"  ✅ {s}")
                with c2:
                    st.write("**Weaknesses:**")
                    for w in result.get("task_weaknesses", []):
                        st.markdown(f"  ⚠️ {w}")

                st.info(
                    "Go to 'Recruiter Review' tab to make the HITL decision."
                )
            except Exception as e:
                st.error(f"Error: {e}")
                logger.error("Task eval error: %s", e, exc_info=True)


# ── TAB 3: RECRUITER REVIEW (HITL) ───────────────────────────────


def render_hitl_review_tab():
    """Approve/Reject/Hold candidates pending HITL review."""
    st.header("👤 Recruiter Review (Human-in-the-Loop)")
    pending = get_pending_candidates()

    if not pending:
        st.info("🎉 No pending reviews!")
        reviewed = [
            c
            for c in get_all_candidates()
            if c.get("hitl_status") in ("approved", "rejected", "on_hold")
        ]
        for c in reviewed[:5]:
            with st.expander(
                f"{c['name']} — {c.get('final_decision', 'Pending')}"
            ):
                st.write(f"**Decision:** {c.get('final_decision')}")
                st.write(
                    f"**Justification:** "
                    f"{c.get('decision_justification', '')[:300]}"
                )
        return

    st.subheader(f"📋 Pending Reviews ({len(pending)})")

    for cand in pending:
        cid = cand["id"]
        with st.expander(
            f"🔍 {cand['name']} | "
            f"Resume:{cand.get('resume_score', 0)} | "
            f"Task:{cand.get('task_score', 0)}",
            expanded=True,
        ):
            render_progress_stepper("task_reviewed")

            c1, c2, c3 = st.columns(3)
            with c1:
                display_score(cand.get("resume_score", 0), "Resume")
            with c2:
                display_score(cand.get("task_score", 0), "Task")
            with c3:
                avg = (
                    cand.get("resume_score", 0) + cand.get("task_score", 0)
                ) // 2
                display_score(avg, "Average")

            st.write(
                f"**Skills:** {', '.join(cand.get('extracted_skills', []))}"
            )
            st.write(
                f"**Gaps:** {', '.join(cand.get('skill_gaps', []))}"
            )
            st.write(f"**Feedback:** {cand.get('task_feedback', '')}")

            st.divider()
            st.subheader("🎯 Your Decision")
            comments = st.text_area("Comments", key=f"comments_{cid}")

            ca, ch, cr = st.columns(3)

            def process_decision(decision: str):
                with st.spinner("🤖 Generating final decision..."):
                    try:
                        from agents.hiring_decision_agent import (
                            hiring_decision_node,
                        )

                        update_candidate(
                            cid,
                            {
                                "hitl_status": decision,
                                "hitl_comments": comments,
                                "current_stage": "hitl_completed",
                            },
                        )
                        state = {
                            "candidate_name": cand.get("name", ""),
                            "candidate_email": cand.get("email", ""),
                            "experience_years": cand.get(
                                "experience_years", 0
                            ),
                            "resume_score": cand.get("resume_score", 0),
                            "extracted_skills": cand.get(
                                "extracted_skills", []
                            ),
                            "skill_gaps": cand.get("skill_gaps", []),
                            "resume_summary": cand.get("resume_summary", ""),
                            "assigned_task": cand.get("assigned_task", ""),
                            "task_score": cand.get("task_score", 0),
                            "task_feedback": cand.get("task_feedback", ""),
                            "task_strengths": cand.get("task_strengths", []),
                            "task_weaknesses": cand.get("task_weaknesses", []),
                            "hitl_status": decision,
                            "hitl_comments": comments,
                            "candidate_id": cid,
                        }
                        result = hiring_decision_node(state)
                        update_candidate(
                            cid,
                            {
                                "final_decision": result.get(
                                    "final_decision", "On Hold"
                                ),
                                "decision_justification": result.get(
                                    "decision_justification", ""
                                ),
                                "current_stage": "decision_made",
                                "workflow_complete": True,
                            },
                        )
                        fd = result.get("final_decision", "On Hold")
                        if fd == "Hired":
                            st.success(f"🎉 **{cand['name']}** — HIRED")
                        elif fd == "Rejected":
                            st.error(f"❌ **{cand['name']}** — REJECTED")
                        else:
                            st.warning(f"⏸️ **{cand['name']}** — ON HOLD")
                        st.write(result.get("decision_justification", ""))
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

            with ca:
                if st.button(
                    "✅ Approve",
                    key=f"ap_{cid}",
                    type="primary",
                    use_container_width=True,
                ):
                    process_decision("approved")
            with ch:
                if st.button(
                    "⏸️ Hold",
                    key=f"ho_{cid}",
                    use_container_width=True,
                ):
                    process_decision("on_hold")
            with cr:
                if st.button(
                    "❌ Reject",
                    key=f"re_{cid}",
                    use_container_width=True,
                ):
                    process_decision("rejected")


# ── TAB 4: DASHBOARD ──────────────────────────────────────────────


def render_dashboard_tab():
    """Overview metrics and candidate table with filters."""
    st.header("📊 Hiring Dashboard")
    m = get_dashboard_metrics()

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.metric("Total", m["total_candidates"])
    with c2:
        st.metric(
            "Qualified", f"{m['qualified_count']} ({m['qualified_pct']}%)"
        )
    with c3:
        st.metric("Hired", f"{m['hired_count']} ({m['hired_pct']}%)")
    with c4:
        st.metric("Rejected", m["rejected_count"])
    with c5:
        st.metric("Pending", m["pending_count"])

    st.divider()
    ca, cb = st.columns(2)
    with ca:
        st.metric("Avg Resume Score", f"{m['avg_resume_score']}/100")
    with cb:
        st.metric("Avg Task Score", f"{m['avg_task_score']}/100")
    st.divider()

    sf = st.selectbox(
        "Filter by Status", ["All", "Hired", "Rejected", "On Hold"]
    )
    candidates = (
        get_all_candidates()
        if sf == "All"
        else get_candidates_by_status(sf)
    )

    if not candidates:
        st.info("No candidates match filters.")
        return

    for c in candidates:
        de = {
            "Hired": "🟢",
            "Rejected": "🔴",
            "On Hold": "🟡",
        }.get(c.get("final_decision", ""), "⚪")
        with st.expander(
            f"{de} {c.get('name', 'Unknown')} | "
            f"R:{c.get('resume_score', 0)} "
            f"T:{c.get('task_score', 0)} | "
            f"{c.get('final_decision', 'In Progress')}"
        ):
            st.write(
                f"**Stage:** {c.get('current_stage')} | "
                f"**HITL:** {c.get('hitl_status')}"
            )
            if c.get("decision_justification"):
                st.write(c["decision_justification"][:300])


# ── MAIN ──────────────────────────────────────────────────────────


def main():
    """Main Streamlit application entry point."""
    with st.sidebar:
        st.title("🤖 AI Hiring")
        st.markdown(
            "**Powered by:**\n"
            "- 🧠 Llama 3.3 70B (Groq)\n"
            "- 🔀 LangGraph\n"
            "- 🐍 LangChain\n\n"
            "**Workflow:**\n"
            "1. Upload Resume + JD\n"
            "2. AI screens candidate\n"
            "3. AI generates task\n"
            "4. Submit solution\n"
            "5. AI evaluates\n"
            "6. Recruiter reviews\n"
            "7. Final decision"
        )

    t1, t2, t3, t4 = st.tabs(
        [
            "📄 New Candidate",
            "📝 Task Submission",
            "👤 Recruiter Review",
            "📊 Dashboard",
        ]
    )
    with t1:
        render_new_candidate_tab()
    with t2:
        render_task_submission_tab()
    with t3:
        render_hitl_review_tab()
    with t4:
        render