"""
src/nodes/ats_scorer.py
LangGraph Node: ATS Keyword Extraction & Match Scoring.
Analyzes resume vs job description to identify keyword matches, gaps, and readiness score.
"""

import re
from pathlib import Path
from collections import Counter
from src.state import JobAgentState
from src.config import get_config
from src.tools.text_extractor import extract_text

COMMON_STOPWORDS = set("""
a about above after again against all am an and any are aren't as at be because been before being below
between both but by can't cannot could couldn't did didn't do does doesn't doing don't down during each
few for from further had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers
herself him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me
more most mustn't my myself no nor not of off on once only or other ought our ours ourselves out over
own same shan't she she'd she'll she's should shouldn't so some such than that that's the their theirs
them themselves then there there's these they they'd they'll they're they've this those through to too
under until up very was wasn't we we'd we'll we're we've were weren't what what's when when's where
where's which while who who's whom why why's with won't would wouldn't you you'd you'll you're you've
your yours yourself yourselves will also role job work working company team candidates experience years
responsibilities requirements skills opportunity join looking candidate position
better career programs including knowledge design way live applications can required complex culture new know
varied backgrounds valued succeed flexibility manage personal develops debugs enhancements products operating
utilities databases internet-related tools hardware education member information portions assigned understanding
support abilities diverse equal opportunity employment affirmative action race color religion sex sexual
orientation gender identity national origin disability protected veteran status participate process accommodation
environment daily exciting mission contribute collaborate global impact across provide ensure maintain apply
""".split())

def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_\-\+\#\.\/]{1,25}\b", text.lower())
    return [t for t in tokens if t not in COMMON_STOPWORDS and len(t) > 2]

def calculate_ats_match(resume_text: str, jd_text: str) -> dict:
    resume_tokens = tokenize(resume_text)
    jd_tokens = tokenize(jd_text)
    
    resume_set = set(resume_tokens)
    jd_counts = Counter(jd_tokens)
    
    top_jd_keywords = [w for w, _ in jd_counts.most_common(30)]
    
    matched = [w for w in top_jd_keywords if w in resume_set]
    missing = [w for w in top_jd_keywords if w not in resume_set]
    
    score = int((len(matched) / len(top_jd_keywords)) * 100) if top_jd_keywords else 0
    
    return {
        "ats_score": score,
        "matched_keywords": matched,
        "missing_keywords": missing,
    }

def ats_scorer_node(state: JobAgentState) -> dict:
    cfg = get_config()
    logs = list(state.get("logs", []))

    # 1. Ensure Resume Text is loaded
    resume_text = state.get("resume_text", "")
    resume_path = state.get("resume_path", "")
    if not resume_text:
        if not resume_path:
            candidates = [
                f for f in cfg.resumes_dir.glob("*.*")
                if f.suffix.lower() in (".pdf", ".docx", ".md", ".txt")
            ]
            if candidates:
                candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                resume_path = str(candidates[0])
        if resume_path and Path(resume_path).exists():
            resume_text = extract_text(resume_path)
            logs.append(f"Extracted candidate resume ({Path(resume_path).name}, {len(resume_text)} chars)")

    # 2. Ensure JD Text is loaded
    jd_text = state.get("jd_text", "")
    if not jd_text:
        current_job = state.get("current_job") or {}
        jd_p = current_job.get("jd_path") or state.get("jd_path")
        if not jd_p:
            candidates = list(cfg.job_descriptions_dir.glob("*.md")) + list(cfg.job_descriptions_dir.glob("*.txt"))
            if candidates:
                jd_p = str(candidates[0])
        if jd_p and Path(jd_p).exists():
            jd_text = extract_text(jd_p)
            logs.append(f"Extracted job description ({Path(jd_p).name}, {len(jd_text)} chars)")

    if not resume_text or not jd_text:
        logs.append("⚠️ Missing resume or JD text for ATS calculation.")
        return {
            "resume_path": resume_path,
            "resume_text": resume_text,
            "jd_text": jd_text,
            "ats_score": 0,
            "matched_keywords": [],
            "missing_keywords": [],
            "logs": logs
        }

    # 3. Calculate match
    result = calculate_ats_match(resume_text, jd_text)
    raw_kw_score = result["ats_score"]

    current_job = state.get("current_job") or {}
    llm_relevance = current_job.get("relevance_score", 0)

    if llm_relevance > 0:
        final_score = max(int(0.6 * llm_relevance + 0.4 * raw_kw_score), raw_kw_score)
        logs.append(f"ATS Match Score: {final_score}% (Blended: {llm_relevance}% semantic + {raw_kw_score}% keywords | {len(result['matched_keywords'])} matched, {len(result['missing_keywords'])} missing)")
    else:
        final_score = raw_kw_score
        logs.append(f"ATS Match Score: {final_score}% ({len(result['matched_keywords'])} matched, {len(result['missing_keywords'])} missing)")

    return {
        "resume_path": resume_path,
        "resume_text": resume_text,
        "jd_text": jd_text,
        "ats_score": final_score,
        "matched_keywords": result["matched_keywords"],
        "missing_keywords": result["missing_keywords"],
        "logs": logs
    }
