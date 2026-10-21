"""
src/prompts/resume_prompts.py
Prompts for ATS keyword gap resolution, STAR bullet point generation, and professional summaries.
"""

def build_resume_tailoring_prompt(
    resume_text: str,
    jd_text: str,
    missing_keywords: list[str],
    candidate_name: str = "Candidate"
) -> str:
    keywords_formatted = ", ".join(missing_keywords[:15]) if missing_keywords else "Relevant industry skills"
    return f"""You are an elite ATS Resume Strategist and Senior Technical Recruiter.
A candidate is applying for the role below. Your task is to rewrite key sections of their resume to maximize ATS match score while maintaining 100% honesty and authenticity.

### Missing ATS Keywords to Naturally Integrate:
{keywords_formatted}

### Original Resume:
\"\"\"{resume_text[:2800]}\"\"\"

### Target Job Description:
\"\"\"{jd_text[:2800]}\"\"\"

### INSTRUCTIONS:
1. **ATS-Optimized Professional Summary**: Write a concise, 3-4 sentence professional summary highlighting candidate strengths and naturally incorporating the high-priority missing keywords.
2. **High-Impact Experience Bullets**: Rewrite or provide 3-5 achievement bullets using the **STAR Method** (Situation, Task, Action, Result) with quantified metrics, embedding missing skills.
3. **Core Technical Competencies**: List recommended skills structured clearly for ATS machine parsers.

Output clean, professional Markdown with clear # and ## headers. Do not include introductory conversational filler.
"""
