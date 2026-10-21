"""
src/graph.py
LangGraph StateGraph Definition for the Autonomous Job Hunting Agent.
Provides cyclic workflows, conditional routing, SQLite checkpointing,
and Human-in-the-Loop review.
"""

import sqlite3
from typing import Optional
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver

from src.state import JobAgentState
from src.config import get_config
from src.nodes.health_check import health_check_node
from src.nodes.scrape_jobs import scrape_jobs_node
from src.nodes.jd_prescreen import jd_prescreen_node
from src.nodes.ats_scorer import ats_scorer_node
from src.nodes.resume_tailor import resume_tailor_node
from src.nodes.safety_check import safety_check_node
from src.nodes.apply_job import apply_job_node
from src.nodes.log_result import log_result_node

# ---------------------------------------------------------------------------
# Routing Functions
# ---------------------------------------------------------------------------

def route_after_health(state: JobAgentState) -> str:
    mode = state.get("mode", "supervised")
    if mode == "check_only":
        return END

    # Ensure at least one AI Brain is functional
    if not state.get("ollama_alive") and not state.get("gemini_alive"):
        state.setdefault("logs", []).append("🛑 No AI Brains available (both Ollama and Gemini offline). Halting.")
        return END

    return "scrape_jobs"

def route_after_scrape(state: JobAgentState) -> str:
    current_job = state.get("current_job")
    mode = state.get("mode", "supervised")
    if not current_job and mode != "match_only":
        return END
    return "jd_prescreen"

def route_after_prescreen(state: JobAgentState) -> str:
    """Route based on pre-screen results: pass to ATS scorer or skip to log."""
    mode = state.get("mode", "supervised")
    if mode == "match_only":
        return "ats_scorer"
    if state.get("prescreen_passed", False):
        return "ats_scorer"
    return "log_result"

def route_after_ats(state: JobAgentState) -> str:
    mode = state.get("mode", "supervised")
    # In supervised or match_only mode, proceed to resume tailor so the user can review in HITL
    if mode in ("match_only", "supervised"):
        return "resume_tailor"

    score = state.get("ats_score", 0)
    cfg = get_config()
    threshold = state.get("ats_threshold") or cfg.min_ats_score_to_show or 20

    if score >= threshold:
        return "resume_tailor"
    else:
        # In autonomous headless mode, skip job if ATS match is below threshold
        state.setdefault("logs", []).append(f"ATS score {score}% below {threshold}% threshold in headless mode. Skipping to next listing.")
        return "log_result"

def route_after_tailor(state: JobAgentState) -> str:
    mode = state.get("mode", "supervised")
    if mode == "match_only":
        return END
    return "safety_check"

def route_after_safety(state: JobAgentState) -> str:
    if not state.get("within_daily_cap", True):
        return END
    return "apply_job"

def route_after_log(state: JobAgentState) -> str:
    mode = state.get("mode", "supervised")
    if mode in ("check_only", "match_only"):
        return END

    jobs = state.get("jobs", [])
    current_index = state.get("current_job_index", 0)
    applied_count = state.get("applied_count", 0)
    max_apps = state.get("max_applications", 5)

    if current_index < len(jobs) and applied_count < max_apps:
        return "scrape_jobs"
    return END

# ---------------------------------------------------------------------------
# Graph Builder
# ---------------------------------------------------------------------------

def build_job_agent_graph() -> StateGraph:
    workflow = StateGraph(JobAgentState)

    # Register Nodes
    workflow.add_node("health_check", health_check_node)
    workflow.add_node("scrape_jobs", scrape_jobs_node)
    workflow.add_node("jd_prescreen", jd_prescreen_node)
    workflow.add_node("ats_scorer", ats_scorer_node)
    workflow.add_node("resume_tailor", resume_tailor_node)
    workflow.add_node("safety_check", safety_check_node)
    workflow.add_node("apply_job", apply_job_node)
    workflow.add_node("log_result", log_result_node)

    # Set Entry Point
    workflow.set_entry_point("health_check")

    # Add Conditional Transitions
    workflow.add_conditional_edges("health_check", route_after_health, {
        "scrape_jobs": "scrape_jobs",
        END: END
    })

    workflow.add_conditional_edges("scrape_jobs", route_after_scrape, {
        "jd_prescreen": "jd_prescreen",
        END: END
    })

    workflow.add_conditional_edges("jd_prescreen", route_after_prescreen, {
        "ats_scorer": "ats_scorer",
        "log_result": "log_result"
    })

    workflow.add_conditional_edges("ats_scorer", route_after_ats, {
        "resume_tailor": "resume_tailor",
        "log_result": "log_result"
    })

    workflow.add_conditional_edges("resume_tailor", route_after_tailor, {
        "safety_check": "safety_check",
        END: END
    })

    workflow.add_conditional_edges("safety_check", route_after_safety, {
        "apply_job": "apply_job",
        END: END
    })

    workflow.add_edge("apply_job", "log_result")

    workflow.add_conditional_edges("log_result", route_after_log, {
        "scrape_jobs": "scrape_jobs",
        END: END
    })

    return workflow

def get_checkpointer(db_path: Optional[str] = None) -> SqliteSaver:
    cfg = get_config()
    target_db = db_path or str(cfg.checkpoints_dir / "job_agent.db")
    conn = sqlite3.connect(target_db, check_same_thread=False)
    return SqliteSaver(conn)

def compile_graph(mode: str = "supervised", checkpointer: Optional[SqliteSaver] = None):
    """
    Compiles graph with persistence and optional Human-in-the-Loop interrupts.
    In 'supervised' mode, pauses right before apply_job for user inspection.
    """
    workflow = build_job_agent_graph()
    saver = checkpointer or get_checkpointer()

    if mode == "supervised":
        return workflow.compile(
            checkpointer=saver,
            interrupt_before=["apply_job"]
        )
    else:
        return workflow.compile(checkpointer=saver)
