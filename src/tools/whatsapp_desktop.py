"""
src/tools/whatsapp_desktop.py
Automates the Windows WhatsApp Desktop application to send job links and summaries
to a designated WhatsApp group or contact.
"""

import sys
import time
import subprocess
import logging
from typing import Dict, Any, Optional

try:
    import pyautogui
    import pyperclip
    pyautogui.FAILSAFE = False
    HAS_GUI_AUTOMATION = True
except ImportError:
    HAS_GUI_AUTOMATION = False

logger = logging.getLogger("whatsapp_desktop")

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass


def format_job_message(job: Dict[str, Any], ats_score: int = 0) -> str:
    """Formats a structured, readable WhatsApp message with job details and links."""
    title = job.get("title", "Target Position")
    company = job.get("company", "Target Company")
    location = job.get("location", "Remote")
    job_url = job.get("job_url") or job.get("url") or ""
    external_url = job.get("external_url") or ""
    apply_type = job.get("apply_type", "easy_apply")
    jd_summary = job.get("jd_summary") or ""
    exp_req = job.get("experience_required", 0)

    lines = [
        "🎯 *NEW JOB OPPORTUNITY DISCOVERED*",
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        f"🏢 *Company:* {company}",
        f"💼 *Role:* {title}",
        f"📍 *Location:* {location}",
    ]

    if ats_score > 0:
        lines.append(f"📊 *ATS Match Score:* {ats_score}%")

    if exp_req > 0:
        lines.append(f"⏳ *Required Experience:* {exp_req}+ years")

    lines.append(f"⚡ *Apply Type:* {'LinkedIn Easy Apply' if apply_type == 'easy_apply' else 'External Portal'}")

    if jd_summary:
        # Preserve rich summary (mission, duties, tech stack) up to 800 chars
        summary_clean = jd_summary.strip()
        if len(summary_clean) > 800:
            summary_clean = summary_clean[:797] + "..."
        lines.extend([
            "",
            "📝 *Role & Requirements Overview:*",
            summary_clean,
        ])

    lines.append("")
    if job_url:
        lines.append(f"🔗 *LinkedIn Posting:* {job_url}")
    if external_url and external_url != job_url:
        lines.append(f"🌐 *Direct Career Portal:* {external_url}")

    lines.extend([
        "━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "_Sent autonomously by Job Hunting Agent_"
    ])

    return "\n".join(lines)


def send_to_whatsapp_group(group_name: str, message: str) -> bool:
    """
    Activates the Windows WhatsApp Desktop application, searches for the specified
    group, and sends the formatted message into the chat.
    
    Parameters:
        group_name: The exact title/name of the WhatsApp group.
        message: The text/links to send.
        
    Returns:
        bool: True if automated steps completed, False otherwise.
    """
    if not HAS_GUI_AUTOMATION:
        logger.error("pyautogui or pyperclip is not installed.")
        return False

    if not group_name or not group_name.strip():
        logger.warning("No WhatsApp group name provided.")
        return False

    group_name = group_name.strip()

    try:
        print("\n⏳ [1/5] Launching WhatsApp Desktop (waiting 8s for app to fully load)...")
        subprocess.run(["cmd", "/c", "start", "whatsapp:"], shell=True)
        time.sleep(8.0)  # Generous wait for WhatsApp Desktop to initialize and render

        print("🔍 [2/5] Switching to Chats tab & opening Search...")
        # 2. Switch to Chats tab (Ctrl + 1)
        pyautogui.hotkey("ctrl", "1")
        time.sleep(1.0)

        # 3. Focus the main Chats Search Bar (Ctrl + F)
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.8)
        pyautogui.hotkey("ctrl", "a")
        time.sleep(0.2)
        pyautogui.press("backspace")
        time.sleep(0.3)

        # 4. Search for the group keyword (e.g. 'Comeback' matches 'Comeback 💪')
        search_keyword = group_name.split()[0] if group_name.strip() else group_name
        print(f"🔎 [3/5] Searching for '{search_keyword}'...")
        pyperclip.copy(search_keyword)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(2.5)  # Wait for WhatsApp search index to find the group

        # 5. Navigate down to the first search result and open it
        print(f"📂 [4/5] Opening group chat: '{group_name}'...")
        pyautogui.press("down")
        time.sleep(0.5)
        pyautogui.press("enter")
        time.sleep(2.0)  # Wait for the chat messages and message input field to render

        # 6. Copy message to clipboard and paste (preserves newlines, formatting & emojis)
        print("📝 [5/5] Pasting job card and sending...")
        pyperclip.copy(message)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(1.2)

        # 7. Press Enter to send the message
        pyautogui.press("enter")
        time.sleep(1.0)

        logger.info(f"Successfully posted job message to WhatsApp group: '{group_name}'")
        return True

    except Exception as e:
        logger.error(f"Failed to send message to WhatsApp group '{group_name}': {e}")
        return False


def notify_whatsapp_if_enabled(job: Dict[str, Any], ats_score: int = 0) -> bool:
    """
    Helper function to inspect config and send notification if WhatsApp is enabled
    and the job qualifies.
    """
    from src.config import get_config
    cfg = get_config()

    enabled = getattr(cfg, "whatsapp_enabled", False)
    group_name = getattr(cfg, "whatsapp_target_group", "")
    min_score = getattr(cfg, "whatsapp_min_ats_score", 40)

    if not enabled or not group_name:
        return False

    if ats_score < min_score and job.get("apply_type") != "external":
        return False

    message = format_job_message(job, ats_score=ats_score)
    return send_to_whatsapp_group(group_name, message)
