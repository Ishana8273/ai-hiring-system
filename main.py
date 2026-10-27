"""
CLI entry point for running the AI Hiring System pipeline.
Usage: python main.py
"""
from __future__ import annotations

import logging
import sys

from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
load_dotenv()

from database.db_models import init_database
from database.db_operations import create_candidate, update_candidate
from graph.state import create_initial_state
from agents.resume_review_agent import resume_review_node
from agents.task_assignment_agent import task_assignment_node
from agents.task_review_agent import task_review_node
from agents.hiring_decision_agent import hiring_decision_node

logger = logging.getLogger(__name__)

SAMPLE_RESUME = """
JOHN DOE - Senior Software Engineer
Email: john.doe@email.com | Phone: (555) 123-4567

SUMMARY: 5+ years in Python, Go, cloud-native technologies. Led teams building
microservices serving 10M+ daily requests.

SKILLS: Python, JavaScript, TypeScript, Go, SQL, Django, FastAPI, React,
Node.js, AWS (EC2, S3, Lambda, RDS), Docker, Kubernetes, PostgreSQL,
MongoDB, Redis, Git, Terraform, Kafka, Grafana, Prometheus, CI/CD

EXPERIENCE:
Senior SWE | TechCorp | 2022-Present
- Led team of 4, microservices platform 10M+ req/day
- FastAPI REST APIs with 99.95% uptime
- CI/CD optimization 60% faster deployments
- Redis caching layer reducing DB load 45%

SWE | StartupXYZ | 2019-2021
- Full-stack React + Django applications
- Kafka real-time data pipeline
- PostgreSQL optimization 40% faster queries

EDUCATION: BS Computer Science, State University, 2019, GPA 3.7
CERTS: AWS Solutions Architect, CKAD, Terraform Associate
"""

SAMPLE_JD = """
Senior Backend Engineer - InnovateTech Solutions (Remote)
Salary: $150K-$200K + equity

Requirements:
- 4+ years software engineering experience
- Strong Python (Django/FastAPI/Flask)
- One other backend language (Go/Java/Rust)
- Microservices architecture and RESTful API design
- SQL and NoSQL databases (PostgreSQL, MongoDB, Redis)
- AWS cloud platform
- Docker and Kubernetes
- CI/CD practices
- Problem-solving and code quality

Nice to Have:
- Event-driven architectures (Kafka, RabbitMQ)
- Infrastructure as Code (Terraform)
- Monitoring tools (Grafana, Prometheus)
- Distributed systems design
"""

SAMPLE_SUBMISSION = """
# Solution: REST API with Rate Limiting

from fastapi import FastAPI, HTTPException, Request, Depends
from redis import Redis
import time, os

app = FastAPI(title="Rate-Limited API")
redis_client = Redis(host=os.getenv("REDIS_HOST", "localhost"))

class RateLimiter:
    def __init__(self, max_requests=100, window=60):
        self.max_requests = max_requests
        self.window = window

    def is_allowed(self, client_id: str) -> bool:
        key = f"rate:{client_id}"
        current = redis_client.get(key)
        if current is None:
            redis_client.setex(key, self.window, 1)
            return True
        if int(current) >= self.max_requests:
            return False
        redis_client.incr(key)
        return True

limiter = RateLimiter()

async def check_rate(request: Request):
    if not limiter.is_allowed(request.client.host):
        raise HTTPException(429, "Rate limit exceeded")

@app.get("/api/data", dependencies=[Depends(check_rate)])
async def get_data():
    return {"message": "data", "timestamp": time.time()}

@app.get("/health")
async def health():
    return {"status": "ok"}

# Tests
def test_rate_limit():
    from fastapi.testclient import TestClient
    client = TestClient(app)
    for _ in range(100):
        assert client.get("/api/data").status_code == 200
    assert client.get("/api/data").status_code == 429
"""


def run_full_pipeline():
    """Run the complete hiring pipeline with sample data."""
    logger.info("=" * 60)
    logger.info("AI HIRING SYSTEM - Full Pipeline Demo")
    logger.info("=" * 60)

    init_database()

    # Stage 1: Resume Review
    logger.info("\n📋 Stage 1: Resume Review")
    state = create_initial_state(
        resume_text=SAMPLE_RESUME, job_description=SAMPLE_JD
    )
    state.update(resume_review_node(state))
    logger.info(
        "  Name: %s | Score: %d | Qualified: %s",
        state["candidate_name"],
        state["resume_score"],
        state["resume_qualified"],
    )

    if not state["resume_qualified"]:
        logger.info("❌ Rejected at resume stage")
        return

    # Stage 2: Task Assignment
    logger.info("\n📋 Stage 2: Task Assignment")
    state.update(task_assignment_node(state))
    candidate_id = create_candidate(state)
    state["candidate_id"] = candidate_id
    logger.info(
        "  Difficulty: %s | Time: %s",
        state["task_difficulty"],
        state["task_estimated_time"],
    )

    # Stage 3: Task Review
    logger.info("\n📋 Stage 3: Task Review")
    state["task_submission"] = SAMPLE_SUBMISSION
    state.update(task_review_node(state))
    update_candidate(
        candidate_id,
        {
            "task_submission": SAMPLE_SUBMISSION,
            "task_score": state["task_score"],
            "task_feedback": state["task_feedback"],
            "task_strengths": state["task_strengths"],
            "task_weaknesses": state["task_weaknesses"],
            "current_stage": "task_reviewed",
        },
    )
    logger.info("  Task Score: %d", state["task_score"])

    # Stage 4: HITL + Decision
    logger.info("\n📋 Stage 4: Hiring Decision")
    state["hitl_status"] = "approved"
    state["hitl_comments"] = "Strong candidate, good technical skills."
    state.update(hiring_decision_node(state))
    logger.info("  Decision: %s", state["final_decision"])
    logger.info("  Justification: %s", state["decision_justification"][:200])

    logger.info("\n✅ Pipeline complete!")


if __name__ == "__main__":
    run_full_pipeline()