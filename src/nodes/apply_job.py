"""
src/nodes/apply_job.py
LangGraph Node: Automated Job Application Submission.
Drives Playwright Stealth Browser to fill forms, answer questions, and submit applications.
Handles both Easy Apply and External portal jobs.
"""

from datetime import datetime
from src.state import JobAgentState
from src.config import get_config
from src.tools.browser import StealthBrowser
from src.llm import query_llm
from src.prompts.screening_prompts import build_screening_prompt

def screening_answer_callback(question_text: str, candidate_summary: str) -> str:
    prompt = build_screening_prompt(question_text, candidate_summary)
    return query_llm(prompt, fast=True)

def apply_job_node(state: JobAgentState) -> dict:
    cfg = get_config()
    logs = list(state.get("logs", []))
    current_job = state.get("current_job")
    mode = state.get("mode", "supervised")
    pdf_path = state.get("tailored_pdf_path")
    candidate_summary = state.get("resume_text", "")[:1500]
    external_queue = list(state.get("external_apply_queue", []))

    if not current_job:
        logs.append("No active job selected for application.")
        return {"application_status": "skipped", "logs": logs}

    # Respect user decision from HITL review (skip or send to WhatsApp without applying)
    status_override = state.get("application_status")
    if status_override in ("skipped", "sent_whatsapp"):
        logs.append(f"Listing '{current_job.get('title')}' was marked as {status_override.upper()} by user. Bypassing application submission.")
        return {"application_status": status_override, "logs": logs}

    apply_type = current_job.get("apply_type", "easy_apply")

    # ── External Apply: Save to Apply Later Queue ────────────────────
    if apply_type == "external":
        external_entry = {
            "title": current_job.get("title", "Unknown"),
            "company": current_job.get("company", "Unknown"),
            "job_url": current_job.get("job_url", current_job.get("url", "")),
            "external_url": current_job.get("external_url", ""),
            "jd_summary": current_job.get("jd_summary", ""),
            "ats_score": state.get("ats_score", 0),
            "saved_at": datetime.now().isoformat()
        }
        external_queue.append(external_entry)

        job_url = current_job.get("job_url", "")
        ext_url = current_job.get("external_url", "")
        logs.append(f"📌 Saved to Apply Later queue: {current_job.get('title')} at {current_job.get('company')}")
        if job_url:
            logs.append(f"   🔗 LinkedIn: {job_url}")
        if ext_url:
            logs.append(f"   🔗 Portal: {ext_url}")

        return {
            "application_status": "queued_external",
            "external_apply_queue": external_queue,
            "logs": logs
        }

    # ── Easy Apply Flow ──────────────────────────────────────────────
    logs.append(f"Submitting application for '{current_job.get('title')}' at '{current_job.get('company')}'...")

    # If URL is empty (e.g. simulated run or test), simulate clean submission
    if not current_job.get("url"):
        logs.append("Local simulation: Application processed successfully.")
        return {
            "application_status": "submitted",
            "applied_count": state.get("applied_count", 0) + 1,
            "logs": logs
        }

    # Execute browser application
    is_headless = cfg.headless_mode if mode == "headless" else False
    try:
        with StealthBrowser(headless=is_headless) as browser:
            res = browser.apply_to_job(
                job=current_job,
                screening_answer_fn=screening_answer_callback,
                candidate_summary=candidate_summary,
                resume_upload_path=pdf_path
            )
            status = res.get("status", "failed")
            applied_increment = 1 if status == "submitted" else 0
            logs.append(f"Application result for {current_job.get('title')}: {status.upper()}")

            return {
                "application_status": status,
                "applied_count": state.get("applied_count", 0) + applied_increment,
                "logs": logs
            }
    except Exception as e:
        logs.append(f"Error executing application: {e}")
        return {
            "application_status": "failed",
            "logs": logs
        }
