#!/usr/bin/env python3
"""
scripts/stealth_browser_agent.py
100% Free Stealth Browser Automation Agent.
Uses Playwright with anti-detection evasion, persistent browser profiles,
and queries Local Ollama (llama3.2:3b) or Google Gemini directly.
Zero OpenRouter dependency.
"""

import os
import sys
import time
import json
import random
import argparse
import urllib.request
from pathlib import Path

# Fix Windows stdout Unicode
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

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

def ask_llm(prompt: str, config: dict) -> str:
    """Query Gemini if configured, otherwise fallback to local Ollama."""
    gemini_key = config.get("GEMINI_API_KEY", "")
    ollama_url = config.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = config.get("OLLAMA_FAST_MODEL") or config.get("OLLAMA_MODEL", "llama3.2:3b")

    if gemini_key and "your_gemini_api_key" not in gemini_key.lower():
        try:
            model = config.get("GEMINI_MODEL", "gemini-2.5-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={gemini_key}"
            payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode("utf-8")
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=15) as response:
                data = json.loads(response.read().decode("utf-8"))
                return data["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception:
            pass

    # Fallback to local Ollama
    gen_url = f"{ollama_url.rstrip('/')}/api/generate"
    payload = json.dumps({
        "model": ollama_model,
        "prompt": prompt,
        "stream": False
    }).encode("utf-8")
    req = urllib.request.Request(gen_url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode("utf-8"))
            return data.get("response", "").strip()
    except Exception as e:
        return f"Error querying local model: {e}"

def answer_screening_question(question_text: str, candidate_context: str, config: dict) -> str:
    """Use AI brain to generate concise, professional answer to screening question."""
    prompt = f"""
You are an applicant filling out a job application.
Question: "{question_text}"
Candidate Background:
\"\"\"{candidate_context[:1500]}\"\"\"

Provide a concise, direct, professional answer (1-2 sentences maximum).
If it asks for a numerical value (like years of experience), return just the number or concise phrase.
Answer:"""
    return ask_llm(prompt, config)

def get_candidate_summary() -> str:
    """Load text of the candidate's resume (supports PDF, TXT, MD)."""
    resumes_dir = WORKSPACE_ROOT / "resumes"
    pdf_files = list(resumes_dir.glob("*.pdf"))
    if pdf_files:
        try:
            import pypdf
            reader = pypdf.PdfReader(str(pdf_files[0]))
            return "\n".join([page.extract_text() or "" for page in reader.pages])
        except Exception:
            pass
    text_files = list(resumes_dir.glob("*.txt")) + list(resumes_dir.glob("*.md"))
    if text_files:
        with open(text_files[0], "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
    return "AI Engineer and Data Scientist with experience in Python, PyTorch, LLMs, and RAG."

def open_login_session():
    """Launch headed browser so user can log into LinkedIn / Indeed once."""
    from playwright.sync_api import sync_playwright
    from playwright_stealth.stealth import Stealth

    profile_dir = WORKSPACE_ROOT / "browser_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    
    print("\n" + "=" * 65)
    print(" 🌐 LAUNCHING STEALTH BROWSER FOR ONE-TIME LOGIN")
    print("=" * 65)
    print(" 1. The browser window will open.")
    print(" 2. Log into LinkedIn and/or Indeed with your account.")
    print(" 3. When you are logged in, return to this terminal and press ENTER.")
    print(f" 4. All session cookies will be saved in: {profile_dir}")
    print("=" * 65 + "\n")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=False,
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        page = context.pages[0] if context.pages else context.new_page()
        Stealth().apply_stealth_sync(page)
        
        try:
            page.goto("https://www.linkedin.com/login", wait_until="commit", timeout=60000)
        except Exception as e:
            print(f"⚠️ Page load notice: {e}. The browser window is open.")
            
        print("👉 Browser is open at LinkedIn login. Please log in with your credentials...")
        input("✅ Press ENTER here once you have finished logging in: ")
        
        print("💾 Saving session cookies and state...")
        context.close()
        print("🎉 Login profile saved! Future runs will stay logged in automatically.\n")

def run_application_session(role: str, location: str, max_apps: int = 5, headed: bool = True):
    """Execute a batch of applications using persistent profile and local AI."""
    from playwright.sync_api import sync_playwright
    from playwright_stealth.stealth import Stealth

    config = load_env(WORKSPACE_ROOT / ".env")
    profile_dir = WORKSPACE_ROOT / "browser_profile"
    candidate_info = get_candidate_summary()
    min_delay = int(config.get("MIN_DELAY_SECONDS", 45))
    max_delay = int(config.get("MAX_DELAY_SECONDS", 90))

    print(f"\n🚀 Launching application batch:")
    print(f"   Target Role: {role}")
    print(f"   Location:    {location}")
    print(f"   Max Apps:    {max_apps}")
    print(f"   Mode:        {'Visible (Headed)' if headed else 'Headless'}")
    print(f"   AI Brain:    Local Ollama / Gemini (Zero OpenRouter)\n")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=not headed,
            viewport={"width": 1280, "height": 800},
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox"
            ]
        )
        page = context.pages[0] if context.pages else context.new_page()
        Stealth().apply_stealth_sync(page)

        # 1. Navigate to LinkedIn Jobs Search
        search_query = f"https://www.linkedin.com/jobs/search/?keywords={urllib.parse.quote(role)}&location={urllib.parse.quote(location)}&f_AL=true"
        try:
            page.goto(search_query, wait_until="commit", timeout=60000)
            page.wait_for_load_state("domcontentloaded", timeout=15000)
        except Exception:
            pass
        time.sleep(random.uniform(4, 7))

        # Check if user is logged in
        if "login" in page.url or page.locator("a[href*='login']").count() > 2:
            print("⚠️ Not logged in! Please run 'python scripts/stealth_browser_agent.py --login' first to save your session.")
            context.close()
            return

        # Find job cards
        cards = page.locator(".job-card-container, .jobs-search-results__list-item").all()
        print(f"📋 Found {len(cards)} job listings on page.")

        applied_count = 0
        for i, card in enumerate(cards[:max_apps]):
            try:
                print(f"\n[{i+1}/{max_apps}] Inspecting job card...")
                card.scroll_into_view_if_needed()
                time.sleep(random.uniform(1.5, 3))
                card.click()
                time.sleep(random.uniform(2, 4))

                # Look for Easy Apply button
                easy_apply_btn = page.locator("button.jobs-apply-button, button:has-text('Easy Apply')").first
                if easy_apply_btn.is_visible():
                    print("   ✅ Found 'Easy Apply' button! Opening application form...")
                    easy_apply_btn.click()
                    time.sleep(random.uniform(2, 4))

                    # Process modal steps
                    modal = page.locator(".jobs-easy-apply-modal, div[role='dialog']").first
                    if modal.is_visible():
                        # Fill text inputs if empty
                        inputs = modal.locator("input[type='text'], textarea").all()
                        for inp in inputs:
                            val = inp.input_value()
                            if not val:
                                label = inp.get_attribute("aria-label") or "Question"
                                answer = answer_screening_question(label, candidate_info, config)
                                print(f"      Q: {label[:40]}... -> A: {answer[:30]}")
                                inp.fill(answer)
                                time.sleep(random.uniform(0.5, 1.5))

                        # Look for Next / Review / Submit button
                        submit_btn = modal.locator("button:has-text('Submit application'), button:has-text('Submit')").first
                        next_btn = modal.locator("button:has-text('Next'), button:has-text('Review')").first

                        if submit_btn.is_visible():
                            print("   🎯 Ready to Submit Application!")
                            if headed:
                                print("   👁️ Supervised mode: Submitting application...")
                            submit_btn.click()
                            applied_count += 1
                            print(f"   🎉 Application #{applied_count} submitted successfully!")
                        elif next_btn.is_visible():
                            print("   ➡️ Multi-step form detected: Proceeding to next step...")
                            next_btn.click()
                            time.sleep(random.uniform(1, 2))

                    # Human pacing pause
                    delay = random.randint(min_delay, max_delay)
                    print(f"   ⏳ Anti-ban safety pause: Waiting {delay} seconds before next job...")
                    time.sleep(delay)
                else:
                    print("   ⏭️ No Easy Apply button found on this posting (external link). Skipping.")

            except Exception as e:
                print(f"   ⚠️ Could not complete card {i+1}: {e}")
                continue

        print(f"\n✅ Session finished. Submitted {applied_count} application(s).")
        context.close()

def main():
    parser = argparse.ArgumentParser(description="100% Free Stealth Browser Agent (Zero OpenRouter)")
    parser.add_argument("--login", action="store_true", help="Launch browser for one-time login setup")
    parser.add_argument("--apply", action="store_true", help="Run automated application cycle")
    parser.add_argument("--role", type=str, default="Software Engineer", help="Job title to apply for")
    parser.add_argument("--location", type=str, default="Remote", help="Job location")
    parser.add_argument("--max", type=int, default=5, help="Max applications this session")
    parser.add_argument("--headless", action="store_true", help="Run browser in background")
    args = parser.parse_args()

    if args.login:
        open_login_session()
    elif args.apply:
        run_application_session(role=args.role, location=args.location, max_apps=args.max, headed=not args.headless)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
