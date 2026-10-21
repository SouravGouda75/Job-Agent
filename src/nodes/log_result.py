"""
src/nodes/log_result.py
LangGraph Node: Application Logging & Anti-Ban Pacing.
Maintains persistent audit logs, updates daily statistics counters,
and applies randomized human-like delays.
"""

import json
import time
import random
from datetime import datetime
from src.state import JobAgentState
from src.config import get_config

def log_result_node(state: JobAgentState) -> dict:
    cfg = get_config()
    logs = list(state.get("logs", []))
    history = list(state.get("application_history", []))
    current_job = state.get("current_job") or {}
    status = state.get("application_status", "unknown")
    daily_stats = dict(state.get("daily_stats", {}))

    record = {
        "timestamp": datetime.now().isoformat(),
        "title": current_job.get("title", "Unknown Role"),
        "company": current_job.get("company", "Unknown Company"),
        "url": current_job.get("url", ""),
        "ats_score": state.get("ats_score", 0),
        "status": status
    }
    history.append(record)

    # If submitted, update persistent daily counter
    if status == "submitted":
        daily_stats["linkedin_count"] = int(daily_stats.get("linkedin_count", 0)) + 1
        stats_file = cfg.logs_dir / "daily_stats.json"
        try:
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(daily_stats, f, indent=2)
            logs.append(f"Updated daily counter: {daily_stats['linkedin_count']} LinkedIn applications today.")
        except Exception as e:
            logs.append(f"Notice writing daily stats: {e}")

    # Append to daily log file
    session_file = cfg.logs_dir / f"session_{datetime.now().strftime('%Y-%m-%d')}.log"
    try:
        with open(session_file, "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%H:%M:%S')}] {record['status'].upper()}: {record['title']} at {record['company']} (ATS: {record['ats_score']}%)\n")
    except Exception:
        pass

    # Advance index
    next_index = state.get("current_job_index", 0) + 1

    # Anti-ban delay if another job is waiting and this one was submitted
    jobs = state.get("jobs", [])
    if next_index < len(jobs) and status == "submitted":
        min_d = min(cfg.min_delay_seconds, 10) if state.get("mode") == "test" else cfg.min_delay_seconds
        max_d = min(cfg.max_delay_seconds, 20) if state.get("mode") == "test" else cfg.max_delay_seconds
        delay = random.randint(min_d, max_d)
        logs.append(f"⏳ Anti-ban safety pacing: pausing for {delay} seconds before next job...")
        time.sleep(delay)

    return {
        "current_job_index": next_index,
        "application_history": history,
        "daily_stats": daily_stats,
        "logs": logs
    }
