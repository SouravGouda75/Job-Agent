import os
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# Fix Windows stdout encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

env_path = Path(".env")
config = {}
with open(env_path, "r", encoding="utf-8") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            config[k.strip()] = v.strip().strip("\"'")

api_key = config.get("GEMINI_API_KEY", "")
print("Testing Gemini Key:", api_key[:8] + "..." + api_key[-6:] if len(api_key) > 14 else "INVALID")

url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
req = urllib.request.Request(url, headers={"User-Agent": "ModelChecker/1.0"})

try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models", [])
        print(f"\n✅ Successfully authenticated! Found {len(models)} total models on your Google AI account.\n")
        
        gen_models = []
        for m in models:
            name = m.get("name", "").replace("models/", "")
            methods = m.get("supportedGenerationMethods", [])
            display = m.get("displayName", "")
            if "generateContent" in methods:
                gen_models.append((name, display))
                
        print("📋 Text & Content Generation Models Available to You:")
        for name, display in gen_models:
            print(f"   • {name:35} ({display})")
            
        # Test candidate models for speed and response
        candidates = [
            "gemini-2.5-flash",
            "gemini-2.0-flash",
            "gemini-1.5-flash",
            "gemini-2.0-flash-lite",
            "gemini-1.5-pro",
            "gemini-2.5-pro"
        ]
        
        print("\n🧪 Benchmark Testing Candidate Models (Speed & Quality):")
        best_model = None
        fastest_time = 999.0
        
        available_names = [name for name, _ in gen_models]
        
        for cand in candidates:
            # Check if candidate or close variant is available
            matching = [n for n in available_names if cand in n]
            target = matching[0] if matching else (cand if cand in available_names else None)
            if not target:
                continue
                
            test_url = f"https://generativelanguage.googleapis.com/v1beta/models/{target}:generateContent?key={api_key}"
            payload = json.dumps({
                "contents": [{"parts": [{"text": "Say 'OK' in one word."}]}]
            }).encode("utf-8")
            test_req = urllib.request.Request(test_url, data=payload, headers={"Content-Type": "application/json"})
            
            import time
            t0 = time.time()
            try:
                with urllib.request.urlopen(test_req, timeout=10) as tresp:
                    tdata = json.loads(tresp.read().decode("utf-8"))
                    dt = time.time() - t0
                    reply = tdata["candidates"][0]["content"]["parts"][0]["text"].strip()
                    print(f"   ⚡ {target:30} -> Response: '{reply}' ({dt:.2f}s)")
                    if dt < fastest_time:
                        fastest_time = dt
                        best_model = target
            except Exception as e:
                print(f"   ❌ {target:30} -> Error: {e}")
                
        print(f"\n🏆 Recommended Best Model: {best_model} (Fastest: {fastest_time:.2f}s)")
        
except urllib.error.HTTPError as e:
    err_body = e.read().decode("utf-8", errors="ignore")
    print(f"❌ HTTP Error {e.code}: {err_body}")
except Exception as e:
    print(f"❌ Connection Error: {e}")
