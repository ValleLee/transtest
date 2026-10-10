"""Candidate evaluation and Judge-facing QA entry points."""
from ..qa.runner import main as run_qa
from ..qa.session import run_candidate_agent

__all__ = ["run_qa", "run_candidate_agent"]
