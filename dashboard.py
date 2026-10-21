#!/usr/bin/env python3
"""
scripts/dashboard.py
Central Command Console for the Autonomous Job Hunting Agent.
Provides interactive menu for testing, ATS tailoring, running cycles, and scheduling.
"""

import os
import sys
import subprocess
import json
from pathlib import Path

# Windows UTF-8 fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

WORKSPACE_ROOT = Path(__file__).resolve().parent

def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")

def print_banner():
    print("=" * 70)
    print("   🤖 AUTONOMOUS JOB HUNTING AGENT — COMMAND CENTER")
    print("   100% Free AI Brains (Local Ollama / Colab + Google Gemini)")
    print("=" * 70)

def menu():
    while True:
        print_banner()
        print("\n  [1] 🔍 Run System & AI Connectivity Check")
        print("  [2] 🎯 Run ATS Resume Matcher & Tailoring Engine")
        print("  [3] 🌐 Launch AIHawk Stealth Browser (Supervised / Interactive)")
        print("  [4] ⚡ Execute Single Application Cycle (run_cycle.ps1)")
        print("  [5] ⏰ Setup / Manage Windows Task Scheduler (Forever Run)")
        print("  [6] 📁 Open Workspace Folders (resumes, tailored_resumes, logs)")
        print("  [7] ☁️ Google Colab Ollama Server Instructions")
        print("  [0] ❌ Exit")
        print("-" * 70)
        
        choice = input("👉 Select an option (0-7): ").strip()
        
        if choice == "1":
            print("\n[Executing Connectivity Check...]\n")
            subprocess.run([sys.executable, str(WORKSPACE_ROOT / "scripts" / "test_connections.py")])
            input("\nPress Enter to return to menu...")
            
        elif choice == "2":
            print("\n[Running ATS Matcher & AI Tailor...]\n")
            subprocess.run([sys.executable, "-u", str(WORKSPACE_ROOT / "scripts" / "match_resume.py"), "--tailor"])
            input("\nPress Enter to return to menu...")
            
        elif choice == "3":
            print("\n[Launching Stealth Browser Session (Zero OpenRouter)]\n")
            print("  (A) Launch Browser for One-Time Login (LinkedIn / Indeed)")
            print("  (B) Run Supervised Easy Apply Batch (Headed)")
            sub_choice = input("👉 Select (A/B): ").strip().upper()
            agent_script = str(WORKSPACE_ROOT / "scripts" / "stealth_browser_agent.py")
            if sub_choice == "A":
                subprocess.run([sys.executable, "-u", agent_script, "--login"])
            elif sub_choice == "B":
                role_input = input("Target Role [default: Software Engineer]: ").strip() or "Software Engineer"
                subprocess.run([sys.executable, "-u", agent_script, "--apply", "--role", role_input, "--max", "5"])
            input("\nPress Enter to return to menu...")
            
        elif choice == "4":
            print("\n[Executing Single Application Cycle via PowerShell...]\n")
            cycle_script = str(WORKSPACE_ROOT / "scripts" / "run_cycle.ps1")
            subprocess.run(["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", cycle_script, "-Supervised"])
            input("\nPress Enter to return to menu...")
            
        elif choice == "5":
            print("\n[Windows Task Scheduler Management]\n")
            print("  (A) Register Task Scheduler to run every 3 hours")
            print("  (B) Unregister / Remove Task Scheduler job")
            sub_choice = input("Choice (A/B): ").strip().upper()
            sched_script = str(WORKSPACE_ROOT / "scripts" / "setup_scheduler.ps1")
            if sub_choice == "A":
                subprocess.run(["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", sched_script])
            elif sub_choice == "B":
                subprocess.run(["powershell.exe", "-ExecutionPolicy", "Bypass", "-File", sched_script, "-Uninstall"])
            input("\nPress Enter to return to menu...")
            
        elif choice == "6":
            print("\nOpening workspace folders in Windows File Explorer...")
            os.system(f"explorer.exe \"{WORKSPACE_ROOT}\"")
            
        elif choice == "7":
            print("\n" + "=" * 65)
            print(" ☁️ GOOGLE COLAB OLLAMA INSTRUCTIONS (Optional)")
            print("=" * 65)
            print(" NOTE: You ALREADY have Ollama running locally on your laptop with:")
            print("       - llama3.1:8b (4.9 GB)")
            print("       - llama3.2:3b (2.0 GB)")
            print("       You DO NOT need Colab to use this system locally!\n")
            print(" However, if you want to run Ollama on Colab's cloud GPU (e.g. to save laptop battery):")
            print(" 1. Open Google Colab (https://colab.research.google.com)")
            print(f" 2. Upload the notebook: {WORKSPACE_ROOT / 'ollama_server.ipynb'}")
            print(" 3. Run all cells to get your public ngrok URL.")
            print(" 4. Update OLLAMA_BASE_URL in your .env file with the ngrok URL.")
            print("=" * 65)
            input("\nPress Enter to return to menu...")
            
        elif choice == "0":
            print("\nGoodbye! Best of luck with your job hunt!\n")
            break

if __name__ == "__main__":
    menu()
