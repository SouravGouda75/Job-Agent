"""
server.py
FastAPI Backend Server & SSE Event Hub for the Job Hunting Agent Web Dashboard.
Provides real-time state streaming, HITL approval webhooks, and REST endpoints.
"""

import sys
import os
import json
import asyncio
import uuid
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List

# Windows console UTF-8 fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from fastapi import FastAPI, BackgroundTasks, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from src.config import get_config
from src.state import create_initial_state, JobAgentState
from src.graph import compile_graph, get_checkpointer
from src.nodes.health_check import health_check_node
from src.nodes.ats_scorer import calculate_ats_match
from src.nodes.resume_tailor import resume_tailor_node
from src.tools.text_extractor import extract_text

cfg = get_config()
app = FastAPI(title="Autonomous Job Hunting Agent Dashboard", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Global In-Memory State & Event Broadcaster
# ---------------------------------------------------------------------------

class EventBroadcaster:
    def __init__(self):
        self.subscribers: List[asyncio.Queue] = []

    async def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue()
        self.subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue):
        if queue in self.subscribers:
            self.subscribers.remove(queue)

    async def broadcast(self, event_type: str, data: Any):
        payload = json.dumps({"event": event_type, "data": data, "timestamp": datetime.now().isoformat()})
        dead = []
        for q in self.subscribers:
            try:
                await q.put(payload)
            except Exception:
                dead.append(q)
        for d in dead:
            self.unsubscribe(d)

broadcaster = EventBroadcaster()

# Current active execution tracker
active_session: Dict[str, Any] = {
    "status": "idle",       # "idle" | "running" | "waiting_approval" | "completed" | "error"
    "thread_id": None,
    "current_node": None,
    "current_job": None,
    "ats_score": 0,
    "applied_count": 0,
    "max_applications": 3,
    "mode": "supervised",
    "logs": []
}

# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class StartSessionRequest(BaseModel):
    mode: str = "supervised"
    target_role: Optional[str] = None
    target_location: Optional[str] = None
    work_types: Optional[List[str]] = None
    date_posted: Optional[str] = None
    max_applications: int = 3
    thread_id: Optional[str] = None

class ApprovalRequest(BaseModel):
    thread_id: str
    action: str = "approve"  # "approve" | "skip" | "whatsapp" | "both"
    approved: Optional[bool] = None

class AtsMatchRequest(BaseModel):
    resume_path: Optional[str] = None
    jd_text: Optional[str] = None
    jd_path: Optional[str] = None
    tailor: bool = False

# ---------------------------------------------------------------------------
# Background Graph Runner
# ---------------------------------------------------------------------------

async def log_and_broadcast(msg: str, node: Optional[str] = None):
    active_session["logs"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    if node:
        active_session["current_node"] = node
    await broadcaster.broadcast("log", {"message": msg, "node": node, "status": active_session["status"]})

def run_graph_sync(thread_id: str, initial_state: JobAgentState, mode: str, loop: asyncio.AbstractEventLoop):
    global active_session
    graph_app = compile_graph(mode=mode)
    config_dict = {"configurable": {"thread_id": thread_id}}

    try:
        asyncio.run_coroutine_threadsafe(
            log_and_broadcast(f"Starting LangGraph execution (mode: {mode})...", "health_check"),
            loop
        ).result()

        # Step 1: Initial invocation (runs until completion or interrupt)
        current_state = graph_app.invoke(initial_state, config=config_dict)

        while True:
            snapshot = graph_app.get_state(config_dict)
            next_nodes = snapshot.next

            if "apply_job" in next_nodes:
                # Human-in-the-Loop Interruption!
                active_session["status"] = "waiting_approval"
                active_session["current_node"] = "apply_job"
                active_session["current_job"] = snapshot.values.get("current_job")
                active_session["ats_score"] = snapshot.values.get("ats_score", 0)
                active_session["applied_count"] = snapshot.values.get("applied_count", 0)

                job_data = active_session["current_job"] or {}
                asyncio.run_coroutine_threadsafe(
                    broadcaster.broadcast("hitl_approval_required", {
                        "thread_id": thread_id,
                        "current_job": job_data,
                        "title": job_data.get("title", "Target Position"),
                        "company": job_data.get("company", "Target Company"),
                        "location": job_data.get("location", "Remote"),
                        "ats_score": active_session["ats_score"],
                        "matched_keywords": snapshot.values.get("matched_keywords", []),
                        "missing_keywords": snapshot.values.get("missing_keywords", []),
                        "tailored_pdf_path": snapshot.values.get("tailored_pdf_path", ""),
                        "job_url": job_data.get("job_url", job_data.get("url", "")),
                        "jd_summary": job_data.get("jd_summary", ""),
                        "apply_type": job_data.get("apply_type", "easy_apply"),
                        "external_url": job_data.get("external_url", ""),
                        "experience_required": job_data.get("experience_required", 0)
                    }),
                    loop
                ).result()

                asyncio.run_coroutine_threadsafe(
                    log_and_broadcast(f"Paused for Human-in-the-Loop approval: {active_session['current_job'].get('title')} at {active_session['current_job'].get('company')}", "apply_job"),
                    loop
                ).result()

                # Wait until user approves or skips via API endpoint
                return
            elif not next_nodes:
                # Graph fully completed
                active_session["status"] = "completed"
                active_session["current_node"] = "END"
                applied = snapshot.values.get("applied_count", 0)
                active_session["applied_count"] = applied

                asyncio.run_coroutine_threadsafe(
                    log_and_broadcast(f"Session finished! Total applications submitted: {applied}", "END"),
                    loop
                ).result()

                asyncio.run_coroutine_threadsafe(
                    broadcaster.broadcast("session_completed", {
                        "thread_id": thread_id,
                        "applied_count": applied,
                        "history": snapshot.values.get("application_history", [])
                    }),
                    loop
                ).result()
                return
            else:
                next_node_name = next_nodes[0]
                active_session["current_node"] = next_node_name
                asyncio.run_coroutine_threadsafe(
                    log_and_broadcast(f"Processing node: {next_node_name}", next_node_name),
                    loop
                ).result()
                current_state = graph_app.invoke(None, config=config_dict)

    except Exception as e:
        active_session["status"] = "error"
        asyncio.run_coroutine_threadsafe(
            log_and_broadcast(f"Execution error: {e}", "ERROR"),
            loop
        ).result()

def resume_graph_sync(thread_id: str, action: str, loop: asyncio.AbstractEventLoop):
    global active_session
    graph_app = compile_graph(mode="supervised")
    config_dict = {"configurable": {"thread_id": thread_id}}

    try:
        active_session["status"] = "running"
        snapshot = graph_app.get_state(config_dict)
        job = snapshot.values.get("current_job") or {}
        score = snapshot.values.get("ats_score", 0)
        wa_group = getattr(cfg, "whatsapp_target_group", "WhatsApp")

        if action == "whatsapp":
            asyncio.run_coroutine_threadsafe(
                log_and_broadcast(f"Dispatching job card to WhatsApp group: '{wa_group}'...", "apply_job"),
                loop
            ).result()
            try:
                from src.tools.whatsapp_desktop import send_to_whatsapp_group, format_job_message
                send_to_whatsapp_group(wa_group, format_job_message(job, ats_score=score))
                asyncio.run_coroutine_threadsafe(
                    log_and_broadcast(f"✅ Delivered to WhatsApp group: '{wa_group}'", "apply_job"),
                    loop
                ).result()
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    log_and_broadcast(f"Notice during WhatsApp dispatch: {e}", "apply_job"),
                    loop
                ).result()

            graph_app.update_state(config_dict, {"application_status": "sent_whatsapp", "sent_to_whatsapp": True})
            current_state = graph_app.invoke(None, config=config_dict)

        elif action == "both":
            asyncio.run_coroutine_threadsafe(
                log_and_broadcast(f"Posting to WhatsApp group '{wa_group}' & submitting via Stealth Browser...", "apply_job"),
                loop
            ).result()
            try:
                from src.tools.whatsapp_desktop import send_to_whatsapp_group, format_job_message
                send_to_whatsapp_group(wa_group, format_job_message(job, ats_score=score))
                asyncio.run_coroutine_threadsafe(
                    log_and_broadcast(f"✅ Delivered to WhatsApp group: '{wa_group}'", "apply_job"),
                    loop
                ).result()
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    log_and_broadcast(f"Notice during WhatsApp dispatch: {e}", "apply_job"),
                    loop
                ).result()

            graph_app.update_state(config_dict, {"sent_to_whatsapp": True})
            current_state = graph_app.invoke(None, config=config_dict)

        elif action == "approve":
            asyncio.run_coroutine_threadsafe(
                log_and_broadcast("Human approval granted. Submitting via Stealth Browser...", "apply_job"),
                loop
            ).result()
            current_state = graph_app.invoke(None, config=config_dict)

        else:  # "skip"
            asyncio.run_coroutine_threadsafe(
                log_and_broadcast("Listing skipped by user. Advancing to next listing...", "log_result"),
                loop
            ).result()
            graph_app.update_state(config_dict, {"application_status": "skipped"})
            current_state = graph_app.invoke(None, config=config_dict)

        # Loop until next interrupt or finish
        while True:
            snapshot = graph_app.get_state(config_dict)
            next_nodes = snapshot.next

            if "apply_job" in next_nodes:
                active_session["status"] = "waiting_approval"
                active_session["current_node"] = "apply_job"
                active_session["current_job"] = snapshot.values.get("current_job")
                active_session["ats_score"] = snapshot.values.get("ats_score", 0)
                active_session["applied_count"] = snapshot.values.get("applied_count", 0)

                job_data = active_session["current_job"] or {}
                asyncio.run_coroutine_threadsafe(
                    broadcaster.broadcast("hitl_approval_required", {
                        "thread_id": thread_id,
                        "current_job": job_data,
                        "title": job_data.get("title", "Target Position"),
                        "company": job_data.get("company", "Target Company"),
                        "location": job_data.get("location", "Remote"),
                        "ats_score": active_session["ats_score"],
                        "matched_keywords": snapshot.values.get("matched_keywords", []),
                        "missing_keywords": snapshot.values.get("missing_keywords", []),
                        "tailored_pdf_path": snapshot.values.get("tailored_pdf_path", ""),
                        "job_url": job_data.get("job_url", job_data.get("url", "")),
                        "jd_summary": job_data.get("jd_summary", ""),
                        "apply_type": job_data.get("apply_type", "easy_apply"),
                        "external_url": job_data.get("external_url", ""),
                        "experience_required": job_data.get("experience_required", 0)
                    }),
                    loop
                ).result()
                return
            elif not next_nodes:
                active_session["status"] = "completed"
                active_session["current_node"] = "END"
                applied = snapshot.values.get("applied_count", 0)
                active_session["applied_count"] = applied

                asyncio.run_coroutine_threadsafe(
                    log_and_broadcast(f"Session finished! Total applications submitted: {applied}", "END"),
                    loop
                ).result()

                asyncio.run_coroutine_threadsafe(
                    broadcaster.broadcast("session_completed", {
                        "thread_id": thread_id,
                        "applied_count": applied,
                        "history": snapshot.values.get("application_history", [])
                    }),
                    loop
                ).result()
                return
            else:
                next_node_name = next_nodes[0]
                active_session["current_node"] = next_node_name
                asyncio.run_coroutine_threadsafe(
                    log_and_broadcast(f"Advancing node: {next_node_name}", next_node_name),
                    loop
                ).result()
                current_state = graph_app.invoke(None, config=config_dict)

    except Exception as e:
        active_session["status"] = "error"
        asyncio.run_coroutine_threadsafe(
            log_and_broadcast(f"Resume error: {e}", "ERROR"),
            loop
        ).result()

# ---------------------------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------------------------

_cached_health = None
_cached_health_time = 0

@app.get("/api/health")
def get_system_health():
    """Runs system diagnostics non-destructively and returns component status with 30s cache."""
    global _cached_health, _cached_health_time
    import time
    now = time.time()
    if _cached_health and (now - _cached_health_time) < 30:
        return _cached_health

    res = health_check_node({})
    _cached_health = {
        "ollama_alive": res.get("ollama_alive", False),
        "gemini_alive": res.get("gemini_alive", False),
        "browser_ready": res.get("browser_ready", False),
        "available_models": res.get("available_models", []),
        "resume_path": res.get("resume_path", ""),
        "health_summary": res.get("health_summary", ""),
        "ollama_url": cfg.ollama_base_url,
        "gemini_model": cfg.gemini_model
    }
    _cached_health_time = now
    return _cached_health

@app.get("/api/stats/daily")
async def get_daily_statistics():
    """Returns today's application count and anti-ban thresholds."""
    today_str = datetime.now().strftime("%Y-%m-%d")
    stats_file = cfg.logs_dir / "daily_stats.json"
    stats = {"date": today_str, "linkedin_count": 0, "indeed_count": 0, "glassdoor_count": 0}

    if stats_file.exists():
        try:
            with open(stats_file, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if saved.get("date") == today_str:
                    stats = saved
        except Exception:
            pass

    return {
        "stats": stats,
        "limits": {
            "daily_max_linkedin": cfg.daily_max_linkedin,
            "daily_max_indeed": cfg.daily_max_indeed,
            "daily_max_glassdoor": cfg.daily_max_glassdoor,
            "min_delay_seconds": cfg.min_delay_seconds,
            "max_delay_seconds": cfg.max_delay_seconds
        }
    }

@app.get("/api/session/current")
async def get_current_session():
    """Returns the live active session state."""
    return active_session

@app.post("/api/session/start")
async def start_application_session(req: StartSessionRequest, background_tasks: BackgroundTasks):
    """Initiates a new LangGraph StateGraph execution cycle."""
    global active_session
    if active_session["status"] == "running":
        raise HTTPException(status_code=400, detail="A session is already currently running.")

    thread_id = req.thread_id or f"web_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    initial_state = create_initial_state(
        mode=req.mode,
        target_role=req.target_role,
        target_location=req.target_location,
        target_locations=req.work_types,
        date_posted=req.date_posted,
        max_applications=req.max_applications,
        thread_id=thread_id
    )

    active_session = {
        "status": "running",
        "thread_id": thread_id,
        "current_node": "health_check",
        "current_job": None,
        "ats_score": 0,
        "applied_count": 0,
        "max_applications": req.max_applications,
        "mode": req.mode,
        "logs": [f"[{datetime.now().strftime('%H:%M:%S')}] Session initialized: {thread_id}"]
    }

    loop = asyncio.get_event_loop()
    background_tasks.add_task(run_graph_sync, thread_id, initial_state, req.mode, loop)

    return {"status": "started", "thread_id": thread_id}

@app.post("/api/session/approve")
async def approve_pending_application(req: ApprovalRequest, background_tasks: BackgroundTasks):
    """Submits human approval for a paused application."""
    global active_session
    if active_session["status"] != "waiting_approval":
        raise HTTPException(status_code=400, detail="No session is currently waiting for approval.")

    action = req.action
    if req.approved is not None:
        action = "approve" if req.approved else "skip"

    loop = asyncio.get_event_loop()
    background_tasks.add_task(resume_graph_sync, req.thread_id, action, loop)
    return {"status": "resumed", "action": action}

@app.get("/api/external-queue")
async def get_external_apply_queue():
    """Returns the Apply Later queue of external-portal jobs."""
    # Try to get from the active graph state if a session is running
    thread_id = active_session.get("thread_id")
    if thread_id:
        try:
            graph_app = compile_graph(mode="supervised")
            config_dict = {"configurable": {"thread_id": thread_id}}
            snapshot = graph_app.get_state(config_dict)
            queue = snapshot.values.get("external_apply_queue", [])
            if queue:
                return {"queue": queue}
        except Exception:
            pass
    return {"queue": []}

@app.get("/api/events")
async def sse_event_stream(request: Request):
    """Server-Sent Events (SSE) live stream for state transitions and logs."""
    queue = await broadcaster.subscribe()

    async def event_generator():
        try:
            # Send initial greeting state
            init_data = json.dumps({"event": "connected", "data": active_session})
            yield f"data: {init_data}\n\n"

            while True:
                if await request.is_disconnected():
                    break
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    # Heartbeat
                    yield ": heartbeat\n\n"
        finally:
            broadcaster.unsubscribe(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@app.post("/api/ats/match")
async def run_ats_matcher_endpoint(req: AtsMatchRequest):
    """Analyzes resume vs job description and returns match % and keyword gaps."""
    # 1. Resolve Resume
    resumes_dir = cfg.resumes_dir
    resume_path = req.resume_path
    if not resume_path:
        candidates = list(resumes_dir.glob("*.pdf")) + list(resumes_dir.glob("*.docx")) + list(resumes_dir.glob("*.md"))
        if candidates:
            resume_path = str(candidates[0])

    if not resume_path or not Path(resume_path).exists():
        raise HTTPException(status_code=400, detail="No resume file found in resumes/ folder.")

    resume_text = extract_text(resume_path)

    # 2. Resolve JD Text
    jd_text = req.jd_text
    if not jd_text:
        jd_p = req.jd_path
        if not jd_p:
            jd_candidates = list(cfg.job_descriptions_dir.glob("*.md")) + list(cfg.job_descriptions_dir.glob("*.txt"))
            if jd_candidates:
                jd_p = str(jd_candidates[0])
        if jd_p and Path(jd_p).exists():
            jd_text = extract_text(jd_p)

    if not jd_text:
        raise HTTPException(status_code=400, detail="No job description text or file provided.")

    # 3. Calculate Score
    results = calculate_ats_match(resume_text, jd_text)

    tailored_pdf_path = None
    tailored_md_path = None

    if req.tailor:
        state_dict = {
            "resume_text": resume_text,
            "jd_text": jd_text,
            "missing_keywords": results["missing_keywords"],
            "resume_path": resume_path,
            "ats_score": results["ats_score"]
        }
        tailor_res = resume_tailor_node(state_dict)
        tailored_pdf_path = tailor_res.get("tailored_pdf_path")
        tailored_md_path = tailor_res.get("tailored_resume_path")

    return {
        "ats_score": results["ats_score"],
        "matched_keywords": results["matched_keywords"],
        "missing_keywords": results["missing_keywords"],
        "resume_name": Path(resume_path).name,
        "tailored_pdf": Path(tailored_pdf_path).name if tailored_pdf_path else None,
        "tailored_md": Path(tailored_md_path).name if tailored_md_path else None
    }

@app.get("/api/checkpoints")
async def list_checkpoints():
    """Lists saved session threads and their last snapshot states."""
    db_path = cfg.checkpoints_dir / "job_agent.db"
    if not db_path.exists():
        return {"threads": []}

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY checkpoint_id DESC LIMIT 15")
        thread_ids = [r[0] for r in cur.fetchall() if r[0]]
        conn.close()

        graph_app = compile_graph(mode="supervised")
        threads_summary = []
        for tid in thread_ids:
            try:
                snap = graph_app.get_state({"configurable": {"thread_id": tid}})
                vals = snap.values or {}
                threads_summary.append({
                    "thread_id": tid,
                    "next_node": ", ".join(snap.next) if snap.next else "Completed",
                    "target_role": vals.get("target_role", "N/A"),
                    "ats_score": vals.get("ats_score", 0),
                    "applied_count": vals.get("applied_count", 0),
                    "mode": vals.get("mode", "supervised")
                })
            except Exception:
                threads_summary.append({
                    "thread_id": tid,
                    "next_node": "Saved",
                    "target_role": "N/A",
                    "ats_score": 0,
                    "applied_count": 0,
                    "mode": "unknown"
                })

        return {"threads": threads_summary}
    except Exception as e:
        return {"threads": [], "error": str(e)}

@app.get("/api/resumes")
async def list_resumes():
    """Lists candidate resumes and generated tailored PDFs."""
    resumes = [f.name for f in cfg.resumes_dir.glob("*.*") if f.suffix.lower() in (".pdf", ".docx", ".md", ".txt")]
    tailored = [f.name for f in cfg.tailored_resumes_dir.glob("*.pdf")]
    return {"candidate_resumes": resumes, "tailored_resumes": tailored}

@app.get("/api/resumes/download/{filename}")
async def download_resume_file(filename: str):
    """Serves tailored PDF or candidate resume for in-browser preview."""
    # Check tailored resumes first
    f_path = cfg.tailored_resumes_dir / filename
    if not f_path.exists():
        f_path = cfg.resumes_dir / filename
    if not f_path.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    
    media_type = "application/pdf" if f_path.suffix.lower() == ".pdf" else "text/plain"
    return FileResponse(f_path, media_type=media_type, filename=filename)

# ---------------------------------------------------------------------------
# Static Web App Mount
# ---------------------------------------------------------------------------

web_dir = cfg.workspace_root / "web"
web_dir.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(web_dir)), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    index_path = web_dir / "index.html"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>Job Hunting Agent Dashboard</h1><p>Frontend files are initializing...</p>"

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("DASHBOARD_PORT", "8765"))
    print("\n" + "=" * 65)
    print(" 🚀 LAUNCHING AUTONOMOUS JOB HUNTING AGENT WEB DASHBOARD")
    print(f" 🌐 URL: http://127.0.0.1:{port}")
    print("=" * 65 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=port)
