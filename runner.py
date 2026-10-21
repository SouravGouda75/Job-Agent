#!/usr/bin/env python3
"""
runner.py
Headless execution runner for the Autonomous Job Hunting Agent.
Designed for Windows Task Scheduler and automated background autopilot.
"""

import sys
import uuid
from datetime import datetime
from src.config import get_config
from src.state import create_initial_state
from src.graph import compile_graph

# Windows console encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def run_headless_cycle():
    cfg = get_config()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    thread_id = f"auto_{timestamp}"
    log_file = cfg.logs_dir / f"run_{timestamp}.log"

    def write_log(msg: str):
        line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
        print(line, end="", flush=True)
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(line)
        except Exception:
            pass

    write_log("=" * 65)
    write_log("🤖 STARTING HEADLESS LANGGRAPH JOB HUNTING CYCLE")
    write_log(f"Thread ID: {thread_id}")
    write_log("=" * 65)

    app = compile_graph(mode="headless")
    state = create_initial_state(
        mode="headless",
        target_role=cfg.target_roles[0] if cfg.target_roles else "Software Engineer",
        target_location=cfg.target_location,
        max_applications=cfg.max_applications_per_cycle,
        thread_id=thread_id
    )

    try:
        config_dict = {"configurable": {"thread_id": thread_id}}
        final_state = app.invoke(state, config=config_dict)
        
        applied = final_state.get("applied_count", 0)
        write_log(f"Cycle completed successfully. Total applications submitted: {applied}")
        write_log("State trace logs:")
        for l in final_state.get("logs", []):
            write_log(f"  • {l}")
    except Exception as e:
        write_log(f"❌ Error during headless execution: {e}")

    write_log("=" * 65)
    write_log("✅ HEADLESS EXECUTION COMPLETED")
    write_log("=" * 65)

if __name__ == "__main__":
    run_headless_cycle()
