#!/usr/bin/env python3
"""
scripts/match_resume.py
ATS Keyword Analysis & Resume Tailoring Engine.
Works with Local Ollama (llama3.1:8b) or Google Gemini.
Calculates keyword match score, identifies ATS gaps, and generates a tailored resume.
"""

import os
import sys
import re
import json
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from collections import Counter

# Fix Windows stdout Unicode encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

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
""".split())

def load_env(env_path: Path) -> dict:
    config = {}
    if not env_path.exists():
        return config
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            config[k.strip()] = v.strip().strip("\"'")
    return config

def extract_text_from_file(file_path: Path) -> str:
    """Extract text from TXT, MD, or PDF."""
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
        
    ext = file_path.suffix.lower()
    if ext in [".txt", ".md"]:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    elif ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(file_path))
            return "\n".join([page.extract_text() or "" for page in reader.pages])
        except ImportError:
            # Fallback: simple binary string extraction
            with open(file_path, "rb") as f:
                raw = f.read().decode("latin1", errors="ignore")
                matches = re.findall(r"\(([A-Za-z0-9 ,.\-_;:\n\r]{3,})\)", raw)
                if matches:
                    return "\n".join(matches)
                return f"[PDF raw content extracted: {file_path.name}]"
    else:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

def tokenize(text: str) -> list[str]:
    """Extract normalized lowercase word tokens."""
    tokens = re.findall(r"\b[a-zA-Z][a-zA-Z0-9_\-\+\#\.\/]{1,25}\b", text.lower())
    return [t for t in tokens if t not in COMMON_STOPWORDS and len(t) > 2]

def calculate_ats_match(resume_text: str, jd_text: str) -> dict:
    """Calculate keyword overlap and ATS score."""
    resume_tokens = tokenize(resume_text)
    jd_tokens = tokenize(jd_text)
    
    resume_set = set(resume_tokens)
    jd_counts = Counter(jd_tokens)
    
    top_jd_keywords = [w for w, _ in jd_counts.most_common(40)]
    
    matched = [w for w in top_jd_keywords if w in resume_set]
    missing = [w for w in top_jd_keywords if w not in resume_set]
    
    score = int((len(matched) / len(top_jd_keywords)) * 100) if top_jd_keywords else 0
    
    return {
        "ats_score": score,
        "total_jd_keywords": len(top_jd_keywords),
        "matched_keywords": matched,
        "missing_keywords": missing,
        "resume_token_count": len(resume_tokens),
        "jd_token_count": len(jd_tokens)
    }

def ask_llm(prompt: str, config: dict, preferred_model: str = "") -> str:
    """Query Gemini if configured, otherwise fallback to local Ollama."""
    gemini_key = config.get("GEMINI_API_KEY", "")
    ollama_url = config.get("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # Check model selection: preferred, or fast model, or default
    ollama_model = preferred_model or config.get("OLLAMA_FAST_MODEL") or config.get("OLLAMA_MODEL", "llama3.2:3b")
    
    # Try Gemini first if key exists
    if gemini_key and "your_gemini_api_key" not in gemini_key.lower():
        try:
            model = config.get("GEMINI_MODEL", "gemini-2.5-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
            payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"⚠️ Gemini request failed ({e}), falling back to local Ollama...", flush=True)

    # Local Ollama generation with 180s timeout
    gen_url = f"{ollama_url.rstrip('/')}/api/generate"
    payload = json.dumps({
        "model": ollama_model,
        "prompt": prompt,
        "stream": False
    }).encode("utf-8")
    req = urllib.request.Request(gen_url, data=payload, headers={"Content-Type": "application/json"})
    print(f"   ⏳ Generating with Ollama model '{ollama_model}'...", flush=True)
    with urllib.request.urlopen(req, timeout=180) as response:
        data = json.loads(response.read().decode("utf-8"))
        return data.get("response", "").strip()

def tailor_resume(resume_text: str, jd_text: str, missing_keywords: list, config: dict) -> str:
    """Generate tailored resume bullet points and summary addressing ATS gaps."""
    prompt = f"""
You are an expert ATS Resume Strategist and Career Coach.
A job seeker is applying for a role with the following Job Description.

### Missing ATS Keywords to Naturally Integrate:
{", ".join(missing_keywords[:15])}

### Original Resume:
\"\"\"{resume_text[:2500]}\"\"\"

### Job Description:
\"\"\"{jd_text[:2500]}\"\"\"

TASK:
1. Provide an ATS-Optimized Professional Summary (3-4 impactful sentences incorporating key missing skills).
2. Rewrite 3-5 high-impact experience bullet points using the STAR method (Situation, Task, Action, Result) with quantified metrics, naturally embedding the missing keywords.
3. List the recommended 'Core Technical Skills' section formatted cleanly for ATS parsers.

Output only clean, professional markdown.
"""
    print("⏳ Generating tailored ATS improvements with AI brain...")
    return ask_llm(prompt, config)

def save_as_pdf(content: str, pdf_path: Path):
    """Render markdown text into a clean, professional ATS-friendly PDF."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib import colors
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=36,
            bottomMargin=36
        )
        
        styles = getSampleStyleSheet()
        normal = styles['Normal']
        normal.fontSize = 9
        normal.leading = 12
        
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=15,
            leading=18,
            textColor=colors.HexColor("#1A365D"),
            spaceAfter=4
        )
        
        h2_style = ParagraphStyle(
            'H2Style',
            parent=styles['Heading2'],
            fontSize=11,
            leading=14,
            textColor=colors.HexColor("#2B6CB0"),
            spaceBefore=6,
            spaceAfter=3
        )
        
        bullet_style = ParagraphStyle(
            'BulletStyle',
            parent=normal,
            leftIndent=12,
            firstLineIndent=-8,
            spaceAfter=2
        )
        
        story = []
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("```"):
                continue
            if line.startswith("# "):
                text = line[2:].strip().replace("**", "")
                story.append(Paragraph(f"<b>{text}</b>", title_style))
                story.append(Spacer(1, 4))
            elif line.startswith("## ") or line.startswith("### "):
                text = line.lstrip("#").strip().replace("**", "")
                story.append(Paragraph(f"<b>{text}</b>", h2_style))
                story.append(Spacer(1, 3))
            elif line.startswith("- ") or line.startswith("* "):
                text = line[2:].strip()
                # Bold formatting
                text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", text)
                story.append(Paragraph(f"• {text}", bullet_style))
            elif line.startswith("---"):
                story.append(Spacer(1, 6))
            else:
                text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", line)
                story.append(Paragraph(text, normal))
                story.append(Spacer(1, 2))
                
        doc.build(story)
        print(f"📄 Tailored PDF resume compiled to: {pdf_path}")
    except Exception as e:
        print(f"⚠️ Could not compile PDF: {e}")

def main():
    parser = argparse.ArgumentParser(description="Match resume against Job Description and tailor ATS content.")
    parser.add_argument("--resume", type=str, default="", help="Path to resume file (PDF, TXT, MD)")
    parser.add_argument("--jd", type=str, default="", help="Path to job description file or raw text")
    parser.add_argument("--tailor", action="store_true", help="Generate AI tailored resume improvements")
    parser.add_argument("--output", type=str, default="", help="Output path for tailored resume")
    args = parser.parse_args()
    
    config = load_env(WORKSPACE_ROOT / ".env")
    
    # 1. Resolve Resume
    resume_path = None
    if args.resume:
        resume_path = Path(args.resume)
    else:
        # Check resumes directory
        resumes_dir = WORKSPACE_ROOT / "resumes"
        candidates = list(resumes_dir.glob("*.pdf")) + list(resumes_dir.glob("*.docx")) + list(resumes_dir.glob("*.txt")) + list(resumes_dir.glob("*.md"))
        if candidates:
            resume_path = candidates[0]
            print(f"📄 Using resume: {resume_path.name}")
        else:
            print("❌ No resume found in 'resumes/' directory!")
            print("   Please place your resume in 'resumes/' or specify with --resume <path>")
            return
            
    resume_text = extract_text_from_file(resume_path)
    
    # 2. Resolve Job Description
    jd_text = ""
    if args.jd:
        jd_path = Path(args.jd)
        if jd_path.exists():
            jd_text = extract_text_from_file(jd_path)
        else:
            jd_text = args.jd
    else:
        # Check job_descriptions directory
        jd_dir = WORKSPACE_ROOT / "job_descriptions"
        jd_candidates = list(jd_dir.glob("*.txt")) + list(jd_dir.glob("*.md"))
        if jd_candidates:
            jd_text = extract_text_from_file(jd_candidates[0])
            print(f"📋 Using job description: {jd_candidates[0].name}")
        else:
            print("❌ No job description provided!")
            print("   Please place a JD in 'job_descriptions/' or use --jd <path_or_text>")
            return
            
    # 3. Calculate Score
    results = calculate_ats_match(resume_text, jd_text)
    
    print("\n" + "=" * 60)
    print(f" 🎯 ATS MATCH SCORE: {results['ats_score']}%")
    print("=" * 60)
    print(f" ✅ Matched Keywords ({len(results['matched_keywords'])}):")
    print("   " + ", ".join(results['matched_keywords'][:20]))
    print(f"\n ⚠️  Missing ATS Keywords ({len(results['missing_keywords'])}):")
    print("   " + ", ".join(results['missing_keywords'][:20]))
    print("=" * 60)
    
    # 4. Tailor if requested or if output provided
    if args.tailor or args.output:
        tailored_content = tailor_resume(resume_text, jd_text, results['missing_keywords'], config)
        
        output_file = Path(args.output) if args.output else WORKSPACE_ROOT / "tailored_resumes" / f"tailored_{resume_path.stem}.md"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(f"# Tailored Resume Materials — {resume_path.stem}\n")
            f.write(f"**ATS Match Score:** {results['ats_score']}%\n\n")
            f.write(f"**Target Missing Keywords Addressed:** {', '.join(results['missing_keywords'][:15])}\n\n")
            f.write("---\n\n")
            f.write(tailored_content)
            
        print(f"\n✨ Tailored markdown saved to: {output_file}")
        
        # Also compile to PDF
        pdf_output = output_file.with_suffix(".pdf")
        save_as_pdf(tailored_content, pdf_output)

if __name__ == "__main__":
    main()
