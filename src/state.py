"""
src/state.py
Defines the JobAgentState TypedDict schema for the LangGraph StateGraph.
Provides strict type annotations and helper to generate clean initial states.
"""

from typing import TypedDict, Optional, List, Dict, Any

class JobListing(TypedDict, total=False):
    title: str
    company: str
    location: str
    url: str
    job_url: str                 # LinkedIn profile link for the job posting
    has_easy_apply: bool
    apply_type: str              # "easy_apply" | "external"
    external_url: str            # Company portal redirect URL (for external apply)
    description: str
    jd_snippet: str              # Raw first 2000 chars of JD from LinkedIn
    jd_summary: str              # LLM-generated 2-3 line summary (from prescreen)
    experience_required: int     # Parsed from JD (lower bound years)
    applied: bool
    status: str
    error: Optional[str]

class DailyStats(TypedDict, total=False):
    date: str
    linkedin_count: int
    indeed_count: int
    glassdoor_count: int

class JobAgentState(TypedDict, total=False):
    # Flow & Mode Control
    mode: str                    # "supervised" | "headless" | "check_only" | "match_only"
    thread_id: str
    user_approved: bool
    abort_requested: bool
    
    # AI Brain & System Health
    ollama_alive: bool
    gemini_alive: bool
    browser_ready: bool
    available_models: List[str]
    health_summary: str
    
    # Target Parameters
    target_role: str
    target_location: str
    target_locations: List[str]
    target_cities: List[str]
    date_posted: str
    max_applications: int
    max_experience_years: int
    
    # Job Discovery Pipeline
    jobs: List[Dict[str, Any]]
    current_job_index: int
    current_job: Optional[Dict[str, Any]]
    
    # JD Pre-Screen Results
    prescreen_passed: bool
    
    # ATS Keyword Matching & Tailoring
    resume_path: str
    resume_text: str
    jd_path: str
    jd_text: str
    ats_score: int
    ats_threshold: int           # Minimum match score to qualify for apply (default: 50)
    matched_keywords: List[str]
    missing_keywords: List[str]
    tailored_content: str
    tailored_resume_path: str
    tailored_pdf_path: str
    
    # Application Execution
    application_status: str      # "idle" | "ready_to_submit" | "submitted" | "skipped" | "failed" | "queued_external" | "sent_whatsapp"
    applied_count: int
    sent_to_whatsapp: bool
    application_history: List[Dict[str, Any]]
    external_apply_queue: List[Dict[str, Any]]
    
    # Safety Caps & Anti-ban
    daily_stats: Dict[str, Any]
    within_daily_cap: bool
    safety_reason: str
    
    # Audit, Errors & Logs
    errors: List[str]
    logs: List[str]


def create_initial_state(
    mode: str = "supervised",
    target_role: Optional[str] = None,
    target_location: Optional[str] = None,
    target_locations: Optional[List[str]] = None,
    target_cities: Optional[List[str]] = None,
    date_posted: Optional[str] = None,
    max_applications: Optional[int] = None,
    resume_path: Optional[str] = None,
    jd_path: Optional[str] = None,
    thread_id: str = "default_session"
) -> JobAgentState:
    """Helper to construct a fully initialized state dictionary."""
    from src.config import get_config
    cfg = get_config()

    return {
        "mode": mode,
        "thread_id": thread_id,
        "user_approved": False,
        "abort_requested": False,
        "ollama_alive": False,
        "gemini_alive": False,
        "browser_ready": False,
        "available_models": [],
        "health_summary": "",
        "target_role": target_role or (cfg.target_roles[0] if cfg.target_roles else "Software Engineer"),
        "target_location": target_location or cfg.target_location,
        "target_locations": target_locations or cfg.target_locations,
        "target_cities": target_cities or cfg.target_cities,
        "date_posted": date_posted or cfg.date_posted_filter,
        "max_applications": max_applications or cfg.max_applications_per_cycle,
        "max_experience_years": cfg.max_experience_years,
        "jobs": [],
        "current_job_index": 0,
        "current_job": None,
        "prescreen_passed": False,
        "resume_path": resume_path or "",
        "resume_text": "",
        "jd_path": jd_path or "",
        "jd_text": "",
        "ats_score": 0,
        "ats_threshold": cfg.min_ats_score_to_show,
        "matched_keywords": [],
        "missing_keywords": [],
        "tailored_content": "",
        "tailored_resume_path": "",
        "tailored_pdf_path": "",
        "application_status": "idle",
        "applied_count": 0,
        "sent_to_whatsapp": False,
        "application_history": [],
        "external_apply_queue": [],
        "daily_stats": {},
        "within_daily_cap": True,
        "safety_reason": "",
        "errors": [],
        "logs": []
    }
