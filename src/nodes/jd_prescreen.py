"""
src/nodes/jd_prescreen.py
LangGraph Node: JD Pre-Screen — Experience Gate & LLM Relevance Check.
Filters jobs by experience requirement and uses a single LLM call to
evaluate relevance AND generate a JD summary (zero extra LLM cost).
"""

import json
from src.state import JobAgentState
from src.config import get_config
from src.llm import query_llm


PRESCREEN_PROMPT = """You are an expert technical recruiter and AI job-matching specialist.
Analyze the following Job Description and Candidate Resume to extract key requirements and assess candidate fit.

## Job Description
\"\"\"
{jd_snippet}
\"\"\"

## Candidate Resume
\"\"\"
{resume_summary}
\"\"\"

## Job Metadata (from scraper)
- Position Title: {job_title}
- Company: {company_name}
- Scraped Experience: {scraped_experience} years

## EVALUATION INSTRUCTIONS

### 1. Minimum Years of Experience (YoE) Extraction:
- Find the MINIMUM general professional experience required for the role.
- **Ranges (e.g. '2-4 years', '3 to 5 years')**: Take the LOWER bound as the minimum (e.g. 2, 3).
- **Entry / Junior / Fresher**: If the JD or title mentions '0-1 years', '0-2 years', 'intern', 'fresher', 'entry level', 'graduate', 'junior', or states no experience requirement, set "experience_years_required" to 0 or 1.
- **Required vs Preferred**: If JD says "2+ years required, 5+ years preferred", use 2.
- **Company History False Positives**: DO NOT confuse company age or tenure (e.g., "Company has been innovating for 15+ years") with candidate experience requirements!
- **Seniority Sanity Check**:
  - Roles with 'Senior', 'Sr.', 'Lead', 'Principal', 'Staff' in title require at least 3-5+ years. If no explicit number is mentioned for a Senior role, infer 4.
  - Standard 'Engineer' or 'Developer' with no stated number: default to 0 or 1.

### 2. Comprehensive, Informative JD Summary:
Write a high-quality, structured summary (4-6 sentences) that provides real substance for human review:
- **Mission & Product Domain**: What specific product, team, or business problem this engineer will work on.
- **Core Responsibilities**: 2-3 specific day-to-day engineering tasks (e.g. developing LLM agents, optimizing RAG pipelines, building REST APIs, deploying on cloud).
- **Required Tech Stack**: Specific languages, frameworks, vector databases, and tools required (e.g. Python, PyTorch, LangChain, FastAPI, Docker, AWS).
DO NOT use generic fluff like "looking for an enthusiastic engineer to join a dynamic team". Be technical and concrete!

### 3. Relevance Assessment (0-100):
- Candidate profile: AI Engineer with 1 year experience in Generative AI, RAG, LLM inference, LangChain, LangGraph, Python, FastAPI, Docker.
- Compare candidate skills and experience against the JD requirements.
- Set "relevant" to true if candidate is a reasonable match for the role.

Respond ONLY with a valid JSON object matching this schema (no markdown fences, no conversational text):
{{
  "experience_years_required": <int>,
  "experience_reasoning": "<short sentence explaining how YoE was determined, citing the exact text from the JD>",
  "relevance_score": <int 0-100>,
  "relevant": <bool>,
  "reason": "<short explanation of candidate fit vs requirements>",
  "jd_summary": "<Structured, detailed summary covering Mission & Domain, Key Responsibilities, and Required Tech Stack>"
}}
"""


def jd_prescreen_node(state: JobAgentState) -> dict:
    """Pre-screens the current job: experience gate + LLM relevance + JD summary."""
    cfg = get_config()
    logs = list(state.get("logs", []))
    current_job = state.get("current_job")

    if not current_job:
        logs.append("⚠️ No current job to pre-screen. Skipping.")
        return {"prescreen_passed": False, "logs": logs}

    title = current_job.get("title", "Unknown")
    company = current_job.get("company", "Unknown")
    jd_snippet = current_job.get("jd_snippet", "")
    if not jd_snippet and state.get("jd_text"):
        jd_snippet = state.get("jd_text", "")

    experience_required = current_job.get("experience_required", 0)
    max_exp = state.get("max_experience_years", cfg.max_experience_years)

    logs.append(f"🔍 Pre-screening: '{title}' at '{company}'...")

    # ── Gate 1: Initial Experience Check ─────────────────────────────
    # If no snippet is available to verify, rely on regex experience
    if not jd_snippet and experience_required > max_exp:
        logs.append(
            f"❌ Experience gate failed: Job requires {experience_required}+ years, "
            f"you're targeting ≤{max_exp} year roles. Auto-skipping."
        )
        enriched_job = dict(current_job)
        enriched_job["jd_summary"] = f"Requires {experience_required}+ years experience (exceeds ≤{max_exp} target)."
        return {
            "prescreen_passed": False,
            "current_job": enriched_job,
            "application_status": "skipped",
            "logs": logs
        }

    # ── Gate 2: LLM Relevance Check + JD Summary + YoE Extraction ────
    if not jd_snippet:
        logs.append("ℹ️ No detailed JD snippet found; creating summary from listing metadata.")
        fallback_summary = (
            f"Role: {title} at {company} ({current_job.get('location', 'Remote')}). "
            f"Detailed job description could not be fetched; review full qualifications via LinkedIn link."
        )
        enriched_job = dict(current_job)
        enriched_job["jd_summary"] = fallback_summary
        return {
            "prescreen_passed": True,
            "current_job": enriched_job,
            "jd_text": "",
            "logs": logs
        }

    resume_text = state.get("resume_text", "")
    if not resume_text:
        from pathlib import Path
        from src.tools.text_extractor import extract_text
        resume_path = state.get("resume_path", "")
        if not resume_path:
            candidates = [
                f for f in cfg.resumes_dir.glob("*.*")
                if f.suffix.lower() in (".pdf", ".docx", ".md", ".txt")
            ]
            if candidates:
                candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                resume_path = str(candidates[0])
        if resume_path and Path(resume_path).exists():
            try:
                resume_text = extract_text(resume_path)
            except Exception:
                pass

    resume_summary = resume_text[:4500] if resume_text else "No resume available."

    prompt = PRESCREEN_PROMPT.format(
        jd_snippet=jd_snippet[:6000],
        resume_summary=resume_summary,
        job_title=title,
        company_name=company,
        scraped_experience=experience_required
    )

    try:
        raw_response = query_llm(prompt, fast=False)

        cleaned = raw_response.strip()
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        elif "{" in cleaned and "}" in cleaned:
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            cleaned = cleaned[start:end]

        result = json.loads(cleaned)

        relevance_score = int(result.get("relevance_score", 0))
        jd_summary = result.get("jd_summary", "").strip()
        reason = result.get("reason", "")
        is_relevant = result.get("relevant", False)
        exp_reason = result.get("experience_reasoning", "")

        # Extract & Sanity Check YoE from LLM
        exp_llm = result.get("experience_years_required")
        if exp_llm is not None:
            try:
                exp_int = int(exp_llm)
                title_lower = title.lower()
                is_senior_title = any(kw in title_lower for kw in ["senior", "sr.", "lead", "principal", "staff"])
                is_entry_title = any(kw in title_lower for kw in ["intern", "fresher", "trainee", "entry", "graduate"])

                if is_senior_title and exp_int < 3:
                    experience_required = max(experience_required, 3)
                elif is_entry_title and exp_int > 2:
                    experience_required = min(exp_int, 1)
                else:
                    experience_required = exp_int
            except (ValueError, TypeError):
                pass

        if not jd_summary:
            jd_summary = f"{title} at {company} ({current_job.get('location', 'Remote')})."

        exp_info = f"{experience_required}yr"
        if exp_reason:
            exp_info += f" ({exp_reason})"
        logs.append(f"📊 LLM Pre-screen: score={relevance_score}/100 | exp={exp_info} | {reason}")

        enriched_job = dict(current_job)
        enriched_job["jd_summary"] = jd_summary
        enriched_job["experience_required"] = experience_required
        enriched_job["relevance_score"] = relevance_score
        enriched_job["experience_reasoning"] = exp_reason

        # Check experience gate with LLM-detected YoE
        if experience_required > max_exp:
            logs.append(
                f"❌ Experience gate failed: Job requires {experience_required}+ years, "
                f"exceeding target ≤{max_exp} years. Auto-skipping."
            )
            return {
                "prescreen_passed": False,
                "current_job": enriched_job,
                "jd_text": jd_snippet,
                "application_status": "skipped",
                "logs": logs
            }

        min_score = min(cfg.min_ats_score_to_show, 25)
        if not is_relevant and relevance_score < min_score:
            logs.append(
                f"❌ Relevance gate failed: score {relevance_score} < {min_score} threshold and not flagged relevant. Auto-skipping."
            )
            return {
                "prescreen_passed": False,
                "current_job": enriched_job,
                "jd_text": jd_snippet,
                "application_status": "skipped",
                "logs": logs
            }

        logs.append(f"✅ Pre-screen passed! Summary: {jd_summary[:100]}...")
        return {
            "prescreen_passed": True,
            "current_job": enriched_job,
            "jd_text": jd_snippet,
            "resume_text": resume_text,
            "resume_path": state.get("resume_path", ""),
            "logs": logs
        }

    except json.JSONDecodeError:
        fallback_summary = raw_response.strip()[:600] if raw_response else f"{title} at {company}."
        enriched_job = dict(current_job)
        enriched_job["jd_summary"] = fallback_summary
        enriched_job["experience_required"] = experience_required
        logs.append("⚠️ LLM pre-screen response parsed as text summary.")
        return {
            "prescreen_passed": True,
            "current_job": enriched_job,
            "jd_text": jd_snippet,
            "logs": logs
        }
    except Exception as e:
        enriched_job = dict(current_job)
        if not enriched_job.get("jd_summary"):
            enriched_job["jd_summary"] = f"Role: {title} at {company}."
        enriched_job["experience_required"] = experience_required
        logs.append(f"⚠️ LLM pre-screen notice: {e}. Passing through.")
        return {
            "prescreen_passed": True,
            "current_job": enriched_job,
            "jd_text": jd_snippet,
            "logs": logs
        }
