#!/usr/bin/env python3
"""
scripts/test_whatsapp_group.py
Interactive CLI tester for WhatsApp Desktop group notifications.
Usage:
    python scripts/test_whatsapp_group.py "Your Exact Group Name"
"""

import sys
from pathlib import Path

# Add project root to sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.tools.whatsapp_desktop import send_to_whatsapp_group, format_job_message
from src.config import get_config

def main():
    cfg = get_config()

    # Determine group name
    if len(sys.argv) > 1:
        target_group = sys.argv[1].strip()
    else:
        target_group = getattr(cfg, "whatsapp_target_group", "")

    if not target_group:
        print("\n❌ Error: No group name provided.")
        print("Usage:")
        print("   python scripts/test_whatsapp_group.py \"Exact WhatsApp Group Name\"")
        print("Or set WHATSAPP_TARGET_GROUP in your .env file.\n")
        sys.exit(1)

    print("\n" + "=" * 65)
    print(" 📲 WHATSAPP DESKTOP GROUP DISPATCH TESTER")
    print("=" * 65)
    print(f" Target Group:  '{target_group}'")
    print(" Requirements:  WhatsApp Desktop should be installed and logged in.")
    print(" Note:          During the test, WhatsApp will open and send a test card.")
    print("=" * 65 + "\n")

    sample_job = {
        "title": "Senior AI / Python Automation Engineer",
        "company": "Tech Innovations Inc",
        "location": "Remote / Bengaluru, India",
        "job_url": "https://www.linkedin.com/jobs/view/1234567890",
        "external_url": "https://careers.techinnovations.com/jobs/ai-python",
        "apply_type": "external",
        "experience_required": 2,
        "jd_summary": "Building autonomous multi-agent pipelines with LangGraph, LLMs (Gemini/Ollama), and stealth web automation. Fast-paced high-impact team."
    }

    message = format_job_message(sample_job, ats_score=88)

    print("📄 Prepared Test Message:\n")
    print("-" * 50)
    print(message)
    print("-" * 50 + "\n")

    print(f"⏳ Triggering WhatsApp Desktop to send message to '{target_group}' in 3 seconds...")
    import time
    time.sleep(3)

    success = send_to_whatsapp_group(target_group, message)

    if success:
        print(f"\n🎉 [SUCCESS] Test message successfully delivered to WhatsApp group: '{target_group}'!\n")
    else:
        print(f"\n❌ [FAILED] Could not send message to '{target_group}'. Ensure WhatsApp Desktop is open and group exists.\n")

if __name__ == "__main__":
    main()
