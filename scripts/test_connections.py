#!/usr/bin/env python3
"""
scripts/test_connections.py
Comprehensive diagnostic and connectivity tester for the Autonomous Job Hunting System.
Tests:
  1. Ollama connectivity (Local or Colab ngrok tunnel)
  2. Google Gemini Free Tier API
  3. OpenRouter API (for AIHawk stealth browser)
  4. System & environment requirements (RAM, paths, resume files)
"""

import os
import sys
import time
import json
import urllib.request
import urllib.error
from pathlib import Path

# Fix Windows stdout Unicode encoding issues
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent

def load_env(env_path: Path) -> dict:
    """Parse key-value pairs from .env file."""
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

def test_ollama(base_url: str, model_name: str) -> dict:
    """Test connection to Ollama server and run a quick inference test."""
    print(f"\n🔍 [1/3] Testing Ollama Endpoint: {base_url} ...")
    result = {"status": "FAIL", "message": "", "models": []}
    
    tags_url = f"{base_url.rstrip('/')}/api/tags"
    req = urllib.request.Request(tags_url, headers={"User-Agent": "JobAgent-Tester/1.0"})
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                result["models"] = models
                elapsed = time.time() - start_time
                print(f"   ✅ Server reachable ({elapsed:.2f}s)! Available models: {', '.join(models) if models else 'None'}")
                
                # Test prompt generation
                gen_url = f"{base_url.rstrip('/')}/api/generate"
                payload = json.dumps({
                    "model": model_name,
                    "prompt": "Reply with 'READY' if you can read this.",
                    "stream": False
                }).encode("utf-8")
                
                gen_req = urllib.request.Request(
                    gen_url,
                    data=payload,
                    headers={"Content-Type": "application/json", "User-Agent": "JobAgent-Tester/1.0"}
                )
                print(f"   ⏳ Testing inference with model '{model_name}'...")
                gen_start = time.time()
                with urllib.request.urlopen(gen_req, timeout=30) as gen_resp:
                    gen_data = json.loads(gen_resp.read().decode("utf-8"))
                    reply = gen_data.get("response", "").strip()
                    gen_elapsed = time.time() - gen_start
                    print(f"   ✅ Model responded in {gen_elapsed:.2f}s: \"{reply[:50]}\"")
                    result["status"] = "PASS"
                    result["message"] = f"Connected and inferencing ({gen_elapsed:.2f}s)"
                    return result
            else:
                result["message"] = f"HTTP {response.status}"
    except urllib.error.URLError as e:
        result["message"] = f"Connection failed: {e.reason}"
        print(f"   ❌ Ollama connection failed: {e.reason}")
    except Exception as e:
        result["message"] = str(e)
        print(f"   ❌ Ollama test error: {e}")
        
    return result

def test_gemini(api_key: str, model: str = "gemini-2.5-flash") -> dict:
    """Test Google Gemini API connectivity and quota."""
    print(f"\n🔍 [2/3] Testing Google Gemini API ...")
    result = {"status": "SKIPPED", "message": "API key not configured"}
    
    if not api_key or "your_gemini_api_key" in api_key.lower():
        print("   ⚠️  Gemini API Key is not configured yet in .env.")
        print("      👉 Get your free key at: https://aistudio.google.com/apikey")
        return result
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{
            "parts": [{"text": "Reply with 'GEMINI_ONLINE' if you receive this message."}]
        }]
    }).encode("utf-8")
    
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"}
    )
    
    start_time = time.time()
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            data = json.loads(response.read().decode("utf-8"))
            elapsed = time.time() - start_time
            candidates = data.get("candidates", [])
            if candidates:
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                print(f"   ✅ Gemini API Connected ({elapsed:.2f}s)! Response: \"{text[:50]}\"")
                result["status"] = "PASS"
                result["message"] = f"Connected ({elapsed:.2f}s)"
            else:
                result["status"] = "WARN"
                result["message"] = "No candidates returned"
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        print(f"   ❌ Gemini HTTP Error {e.code}: {err_body[:150]}")
        result["status"] = "FAIL"
        result["message"] = f"HTTP {e.code}"
    except Exception as e:
        print(f"   ❌ Gemini test error: {e}")
        result["status"] = "FAIL"
        result["message"] = str(e)
        
    return result

def test_playwright_engine() -> dict:
    """Verify Playwright Chromium browser and stealth installation."""
    print(f"\n🔍 [3/3] Testing Stealth Browser Engine (Playwright Chromium) ...")
    result = {"status": "FAIL", "message": "Playwright not ready"}
    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth.stealth import Stealth
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            Stealth().apply_stealth_sync(page)
            browser.close()
        print("   ✅ Playwright Chromium + Anti-Detection Stealth: READY")
        result["status"] = "PASS"
        result["message"] = "Ready (Anti-Detection Enabled)"
    except Exception as e:
        print(f"   ❌ Browser check error: {e}")
        result["status"] = "FAIL"
        result["message"] = str(e)[:40]
    return result

def check_system_assets():
    """Verify directories and resume assets."""
    print(f"\n📁 Checking Local Workspace Assets ...")
    resumes_dir = WORKSPACE_ROOT / "resumes"
    resumes = list(resumes_dir.glob("*.pdf")) + list(resumes_dir.glob("*.docx")) + list(resumes_dir.glob("*.txt")) + list(resumes_dir.glob("*.md"))
    if resumes:
        print(f"   ✅ Found {len(resumes)} resume file(s) in resumes/: {[r.name for r in resumes]}")
    else:
        print(f"   ⚠️  No resumes found in 'resumes/' yet.")
        print(f"      👉 Drop your resume PDF/DOCX into: {resumes_dir}")

def main():
    print("=" * 65)
    print(" 🚀 AUTONOMOUS JOB HUNTING AGENT — SYSTEM CONNECTIVITY CHECK")
    print("=" * 65)
    
    env_file = WORKSPACE_ROOT / ".env"
    config = load_env(env_file)
    
    ollama_url = config.get("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model = config.get("OLLAMA_MODEL", "llama3.1:8b")
    gemini_key = config.get("GEMINI_API_KEY", "")
    gemini_model = config.get("GEMINI_MODEL", "gemini-2.5-flash")
    
    ollama_res = test_ollama(ollama_url, ollama_model)
    gemini_res = test_gemini(gemini_key, gemini_model)
    browser_res = test_playwright_engine()
    check_system_assets()
    
    print("\n" + "=" * 65)
    print(" 📊 SUMMARY")
    print(f"   Ollama ({ollama_model}):     [{ollama_res['status']}] - {ollama_res['message']}")
    print(f"   Gemini Free Tier:      [{gemini_res['status']}] - {gemini_res['message']}")
    print(f"   Stealth Browser:       [{browser_res['status']}] - {browser_res['message']}")
    print("=" * 65)

if __name__ == "__main__":
    main()
