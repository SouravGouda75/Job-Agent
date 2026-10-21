"""
src/nodes/scrape_jobs.py
LangGraph Node: Job Discovery & Queue Management.
Discovers relevant job postings via Stealth Browser or local job queue.
"""

from pathlib import Path
from typing import Dict, Any, List
from src.state import JobAgentState
from src.config import get_config
from src.tools.browser import StealthBrowser
from src.tools.text_extractor import extract_text

def scrape_jobs_node(state: JobAgentState) -> dict:
    cfg = get_config()
    logs = list(state.get("logs", []))
    jobs = list(state.get("jobs", []))
    current_index = state.get("current_job_index", 0)
    mode = state.get("mode", "supervised")

    # If no jobs in queue, discover them
    if not jobs:
        target_role = state.get("target_role", "Software Engineer")
        target_loc = state.get("target_location", "Remote")
        max_apps = state.get("max_applications", 5)

        # In match_only mode or if local JDs are present and browser isn't needed:
        if mode == "match_only":
            jd_path = state.get("jd_path", "")
            if not jd_path:
                candidates = list(cfg.job_descriptions_dir.glob("*.md")) + list(cfg.job_descriptions_dir.glob("*.txt"))
                if candidates:
                    jd_path = str(candidates[0])
            
            jobs = [{
                "index": 1,
                "title": target_role,
                "company": "Target Company",
                "location": target_loc,
                "url": "",
                "has_easy_apply": True,
                "jd_path": jd_path,
                "applied": False
            }]
            logs.append(f"Queued local job posting for ATS analysis: {Path(jd_path).name if jd_path else 'Default'}")

        else:
            # Discover live jobs on LinkedIn via Stealth Browser
            work_types = state.get("target_locations") or cfg.target_locations
            cities = state.get("target_cities") or cfg.target_cities
            date_posted = state.get("date_posted") or cfg.date_posted_filter
            logs.append(f"Searching LinkedIn for '{target_role}' in '{target_loc}' [Types: {', '.join(work_types)} | Date: {date_posted or 'any'}]...")
            try:
                # In supervised mode, keep headed if user prefers; otherwise headless
                is_headless = cfg.headless_mode if mode == "headless" else False
                with StealthBrowser(headless=is_headless) as browser:
                    discovered = browser.scrape_linkedin_jobs(
                        role=target_role,
                        location=target_loc,
                        limit=max_apps,
                        work_types=work_types,
                        include_external=cfg.include_external_apply,
                        cities=cities,
                        date_posted=date_posted
                    )
                    if discovered:
                        jobs = discovered
                        easy_count = sum(1 for j in jobs if j.get("apply_type") == "easy_apply")
                        ext_count = len(jobs) - easy_count
                        logs.append(f"Discovered {len(jobs)} listings ({easy_count} Easy Apply, {ext_count} External).")
                    else:
                        logs.append("No live listings scraped; falling back to local job queue.")
            except Exception as e:
                logs.append(f"Notice during live job search: {e}")

        # Fallback if scraping yielded nothing
        if not jobs:
            jd_candidates = list(cfg.job_descriptions_dir.glob("*.md")) + list(cfg.job_descriptions_dir.glob("*.txt"))
            jd_p = str(jd_candidates[0]) if jd_candidates else ""
            jobs = [{
                "index": 1,
                "title": target_role,
                "company": "Target Organization",
                "location": target_loc,
                "url": "",
                "has_easy_apply": True,
                "jd_path": jd_p,
                "applied": False
            }]
            logs.append("Populated fallback job listing from workspace descriptions.")

    # Select current job from queue
    current_job = jobs[current_index] if current_index < len(jobs) else None
    
    # Resolve JD text for current job
    jd_text = ""
    if current_job and current_job.get("jd_snippet"):
        jd_text = current_job["jd_snippet"]
    elif state.get("jd_text"):
        jd_text = state["jd_text"]
    else:
        jd_p = state.get("jd_path") or (current_job.get("jd_path") if current_job else "")
        if not jd_p:
            candidates = list(cfg.job_descriptions_dir.glob("*.md")) + list(cfg.job_descriptions_dir.glob("*.txt"))
            if candidates:
                jd_p = str(candidates[0])
        if jd_p and Path(jd_p).exists():
            try:
                jd_text = extract_text(jd_p)
            except Exception:
                pass

    return {
        "jobs": jobs,
        "current_job_index": current_index,
        "current_job": current_job,
        "jd_text": jd_text,
        "logs": logs
    }
