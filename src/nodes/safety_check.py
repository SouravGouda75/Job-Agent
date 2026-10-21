"""
src/nodes/safety_check.py
LangGraph Node: Anti-Ban & Daily Limit Safety Check.
Protects user accounts against rate-limits and suspicious activity detection.
"""

import json
from datetime import datetime
from src.state import JobAgentState
from src.config import get_config

def safety_check_node(state: JobAgentState) -> dict:
    cfg = get_config()
    logs = list(state.get("logs", []))
    today_str = datetime.now().strftime("%Y-%m-%d")
    stats_file = cfg.logs_dir / "daily_stats.json"

    daily_stats = {
        "date": today_str,
        "linkedin_count": 0,
        "indeed_count": 0,
        "glassdoor_count": 0
    }

    if stats_file.exists():
        try:
            with open(stats_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if saved.get("date") == today_str:
                    daily_stats = saved
        except Exception:
            pass

    current_li_count = int(daily_stats.get("linkedin_count", 0))
    daily_cap = cfg.daily_max_linkedin

    if current_li_count >= daily_cap:
        reason = f"Daily LinkedIn limit reached ({current_li_count}/{daily_cap}). Execution halted for safety."
        logs.append(f"🛑 {reason}")
        return {
            "daily_stats": daily_stats,
            "within_daily_cap": False,
            "safety_reason": reason,
            "logs": logs
        }

    logs.append(f"Safety limits verified: {current_li_count}/{daily_cap} applications submitted today.")
    return {
        "daily_stats": daily_stats,
        "within_daily_cap": True,
        "safety_reason": "",
        "logs": logs
    }
