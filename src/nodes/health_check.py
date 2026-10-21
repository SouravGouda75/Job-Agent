"""
src/nodes/health_check.py
LangGraph Node: Health Check & Environment Discovery.
Validates Ollama, Google Gemini, Playwright Chromium, and local resume assets.
"""

import time
import json
import urllib.request
import urllib.error
from pathlib import Path
from src.state import JobAgentState
from src.config import get_config
from src.tools.browser import StealthBrowser

def health_check_node(state: JobAgentState) -> dict:
    """Executes non-destructive health checks across all systems."""
    cfg = get_config()
    logs = list(state.get("logs", []))
    logs.append("Executing System & AI Brain Health Check...")
    
    ollama_alive = False
    available_models = []
    gemini_alive = False
    browser_ready = False

    # 1. Test Ollama
    try:
        req = urllib.request.Request(f"{cfg.ollama_base_url}/api/tags", headers={"User-Agent": "JobAgent/2.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                available_models = [m.get("name", "") for m in data.get("models", [])]
                ollama_alive = True
                logs.append(f"Ollama reachable ({cfg.ollama_base_url}): {', '.join(available_models)}")
    except Exception as e:
        logs.append(f"Ollama connection notice: {e}")

    # 2. Test Gemini (with fast fallback across available models)
    if cfg.has_gemini:
        candidate_models = [cfg.gemini_model, "gemini-flash-latest", "gemini-2.5-flash-lite", "gemini-3.5-flash-lite"]
        seen = set()
        for cand in candidate_models:
            if cand in seen:
                continue
            seen.add(cand)
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{cand}:generateContent?key={cfg.gemini_api_key}"
                payload = json.dumps({"contents": [{"parts": [{"text": "Reply with 'ONLINE'"}]}]}).encode("utf-8")
                req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
                with urllib.request.urlopen(req, timeout=4) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    if data.get("candidates"):
                        gemini_alive = True
                        cfg.gemini_model = cand
                        logs.append(f"Google Gemini Free Tier active ({cand})")
                        break
            except Exception as e:
                logs.append(f"Gemini {cand} check notice: {e}")

    # 3. Test Playwright Chromium
    try:
        browser = StealthBrowser(headless=True)
        browser_ready = browser.check_health()
        if browser_ready:
            logs.append("Playwright Chromium stealth engine ready.")
    except Exception as e:
        logs.append(f"Browser check notice: {e}")

    # 4. Check for default candidate resume if not set (newest first)
    resume_path = state.get("resume_path", "")
    if not resume_path:
        candidates = [
            f for f in cfg.resumes_dir.glob("*.*")
            if f.suffix.lower() in (".pdf", ".docx", ".md", ".txt")
        ]
        if candidates:
            candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
            resume_path = str(candidates[0])
            logs.append(f"Default candidate resume detected: {candidates[0].name}")

    summary = f"Ollama: {'ONLINE' if ollama_alive else 'OFFLINE'} | Gemini: {'ONLINE' if gemini_alive else 'OFFLINE'} | Browser: {'READY' if browser_ready else 'FAILED'}"

    return {
        "ollama_alive": ollama_alive,
        "gemini_alive": gemini_alive,
        "browser_ready": browser_ready,
        "available_models": available_models,
        "resume_path": resume_path,
        "health_summary": summary,
        "logs": logs
    }
