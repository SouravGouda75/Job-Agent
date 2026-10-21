"""
src/nodes/resume_tailor.py
LangGraph Node: AI Resume Tailoring & ATS PDF Generation.
Optimizes candidate summary and STAR experience bullets for missing keywords.
"""

from pathlib import Path
from src.state import JobAgentState
from src.config import get_config
from src.llm import query_llm
from src.prompts.resume_prompts import build_resume_tailoring_prompt
from src.tools.pdf_builder import compile_markdown_to_pdf

def resume_tailor_node(state: JobAgentState) -> dict:
    cfg = get_config()
    logs = list(state.get("logs", []))

    resume_text = state.get("resume_text", "")
    jd_text = state.get("jd_text", "")
    missing_keywords = state.get("missing_keywords", [])
    resume_path = state.get("resume_path", "")

    if not resume_text or not jd_text:
        logs.append("⚠️ Cannot tailor resume without both resume and JD content.")
        return {"logs": logs}

    logs.append(f"Generating AI-tailored resume targeting {len(missing_keywords)} missing keywords...")
    prompt = build_resume_tailoring_prompt(
        resume_text=resume_text,
        jd_text=jd_text,
        missing_keywords=missing_keywords
    )

    tailored_text = query_llm(prompt, fast=False)
    
    # Save Markdown file
    stem = Path(resume_path).stem if resume_path else "candidate"
    md_output_path = cfg.tailored_resumes_dir / f"tailored_{stem}.md"
    with open(md_output_path, "w", encoding="utf-8") as f:
        f.write(f"# Tailored Resume Materials — {stem}\n")
        f.write(f"**ATS Match Score:** {state.get('ats_score', 0)}%\n\n")
        f.write(f"**Keywords Addressed:** {', '.join(missing_keywords[:15])}\n\n")
        f.write("---\n\n")
        f.write(tailored_text)

    logs.append(f"Saved tailored markdown to: {md_output_path.name}")

    # Compile ATS PDF
    pdf_output_path = md_output_path.with_suffix(".pdf")
    try:
        compile_markdown_to_pdf(tailored_text, pdf_output_path)
        logs.append(f"Compiled ATS PDF to: {pdf_output_path.name}")
    except Exception as e:
        logs.append(f"Notice during PDF compilation: {e}")

    return {
        "tailored_content": tailored_text,
        "tailored_resume_path": str(md_output_path),
        "tailored_pdf_path": str(pdf_output_path),
        "logs": logs
    }
