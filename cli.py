#!/usr/bin/env python3
"""
cli.py
Interactive Command Center for the Autonomous Job Hunting Agent.
Powered by LangGraph StateGraph, Rich terminal formatting,
Human-in-the-Loop checkpoints, and Observability Inspector.
"""

import sys
import os
import sqlite3
import subprocess
import uuid
from pathlib import Path
from datetime import datetime

# Windows console UTF-8 fix
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm

from src.config import get_config
from src.state import create_initial_state
from src.graph import compile_graph
from src.tools.browser import StealthBrowser

console = Console()
cfg = get_config()

def print_banner():
    banner_text = (
        "[bold cyan]🎯 AUTONOMOUS JOB HUNTING AGENT (v2.0)[/bold cyan]\n"
        "[dim]LangGraph StateGraph • Multi-Brain AI (Ollama + Gemini) • Stealth Anti-Bot Evasion[/dim]"
    )
    console.print(Panel(banner_text, border_style="cyan"))

def get_active_threads() -> list[str]:
    """Fetch all thread IDs stored in the SQLite checkpointer database."""
    db_path = cfg.checkpoints_dir / "job_agent.db"
    if not db_path.exists():
        return []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY checkpoint_id DESC")
        threads = [r[0] for r in cur.fetchall() if r[0]]
        conn.close()
        return threads
    except Exception:
        return []

def run_health_check():
    console.print("\n[bold yellow]🔍 Running System & AI Health Check via LangGraph...[/bold yellow]\n")
    thread_id = f"health_{uuid.uuid4().hex[:6]}"
    app = compile_graph(mode="check_only")
    initial_state = create_initial_state(mode="check_only", thread_id=thread_id)
    
    with console.status("[bold green]Executing Health Check Node...[/bold green]"):
        result = app.invoke(initial_state, config={"configurable": {"thread_id": thread_id}})

    table = Table(title="System Diagnostic Results", border_style="blue")
    table.add_column("Component", style="bold")
    table.add_column("Status")
    table.add_column("Details")

    ollama_status = "[bold green]ONLINE[/bold green]" if result.get("ollama_alive") else "[bold red]OFFLINE[/bold red]"
    models_str = ", ".join(result.get("available_models", [])[:4])
    table.add_row("Ollama Brain", ollama_status, f"Base: {cfg.ollama_base_url} ({models_str})")

    gemini_status = "[bold green]ONLINE[/bold green]" if result.get("gemini_alive") else "[bold yellow]NOT CONFIGURED[/bold yellow]"
    table.add_row("Gemini Free Tier", gemini_status, f"Model: {cfg.gemini_model}")

    browser_status = "[bold green]READY[/bold green]" if result.get("browser_ready") else "[bold red]FAILED[/bold red]"
    table.add_row("Stealth Browser", browser_status, "Playwright Chromium + Anti-Detection")

    resume_info = Path(result.get("resume_path", "")).name if result.get("resume_path") else "None found"
    table.add_row("Candidate Resume", "[bold green]FOUND[/bold green]" if result.get("resume_path") else "[bold red]MISSING[/bold red]", resume_info)

    wa_status = "[bold green]ENABLED[/bold green]" if getattr(cfg, "whatsapp_enabled", False) else "[bold yellow]DISABLED[/bold yellow]"
    wa_details = f"Target Group: '{cfg.whatsapp_target_group}'" if getattr(cfg, "whatsapp_enabled", False) else "Set in .env"
    table.add_row("WhatsApp Desktop", wa_status, wa_details)

    console.print(table)
    Prompt.ask("\nPress [bold cyan]ENTER[/bold cyan] to return to menu")

def run_ats_matcher():
    console.print("\n[bold yellow]🎯 Running ATS Matcher & Resume Tailoring Engine...[/bold yellow]\n")
    thread_id = f"match_{uuid.uuid4().hex[:6]}"
    app = compile_graph(mode="match_only")
    initial_state = create_initial_state(mode="match_only", thread_id=thread_id)

    with console.status("[bold green]Running ATS Scoring & AI Resume Tailoring...[/bold green]"):
        result = app.invoke(initial_state, config={"configurable": {"thread_id": thread_id}})

    score = result.get("ats_score", 0)
    score_color = "green" if score >= 70 else ("yellow" if score >= 45 else "red")
    
    console.print(Panel(
        f"[bold {score_color}]ATS Match Score: {score}%[/bold {score_color}]\n"
        f"[bold]Matched Keywords ({len(result.get('matched_keywords', []))}):[/bold] {', '.join(result.get('matched_keywords', [])[:15])}\n"
        f"[bold]Missing Keywords ({len(result.get('missing_keywords', []))}):[/bold] {', '.join(result.get('missing_keywords', [])[:15])}",
        title="ATS Keyword Analysis",
        border_style=score_color
    ))

    if result.get("tailored_resume_path"):
        console.print(f"✨ [bold green]Tailored Markdown:[/bold green] {result['tailored_resume_path']}")
    if result.get("tailored_pdf_path"):
        console.print(f"📄 [bold green]Tailored ATS PDF:[/bold green] {result['tailored_pdf_path']}")

    Prompt.ask("\nPress [bold cyan]ENTER[/bold cyan] to return to menu")

def run_supervised_session():
    console.print("\n[bold yellow]⚡ Launching Supervised Application Session (Human-in-the-Loop)...[/bold yellow]\n")
    
    threads = get_active_threads()
    thread_id = None
    app = compile_graph(mode="supervised")

    # Check if user wants to resume an interrupted session
    if threads:
        console.print(f"[dim]Found {len(threads)} previous session thread(s) in SQLite checkpoints.[/dim]")
        if Confirm.ask("Would you like to resume an existing thread or start fresh?", default=False):
            table = Table(title="Saved Checkpoint Threads", border_style="cyan")
            table.add_column("No.", style="bold")
            table.add_column("Thread ID")
            for idx, th in enumerate(threads[:8], 1):
                table.add_row(str(idx), th)
            console.print(table)
            sel = int(Prompt.ask("Select thread to resume (number)", default="1"))
            if 1 <= sel <= len(threads):
                thread_id = threads[sel - 1]
                console.print(f"🔄 [bold green]Resuming thread:[/bold green] {thread_id}")

    if not thread_id:
        role = Prompt.ask("Enter Target Role", default=cfg.target_roles[0] if cfg.target_roles else "Software Engineer")
        location = Prompt.ask("Enter Location", default=cfg.target_location)
        max_apps = int(Prompt.ask("Max Applications this batch", default="3"))

        thread_id = f"session_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        state = create_initial_state(
            mode="supervised",
            target_role=role,
            target_location=location,
            max_applications=max_apps,
            thread_id=thread_id
        )
        config_dict = {"configurable": {"thread_id": thread_id}}
        console.print(f"[dim]Started new thread: {thread_id}[/dim]")
        current_state = app.invoke(state, config=config_dict)
    else:
        config_dict = {"configurable": {"thread_id": thread_id}}
        state_snapshot = app.get_state(config_dict)
        console.print(f"Current thread step: Next node = {state_snapshot.next}")
        current_state = app.invoke(None, config=config_dict)

    # Human-in-the-Loop loop
    while True:
        state_snapshot = app.get_state(config_dict)
        next_nodes = state_snapshot.next

        # If interrupted right before apply_job
        if "apply_job" in next_nodes:
            current_job = state_snapshot.values.get("current_job") or {}
            score = state_snapshot.values.get("ats_score", 0)

            console.print("\n" + "=" * 65)
            console.print("[bold cyan]🧑 HUMAN-IN-THE-LOOP CHECKPOINT (Interrupted by LangGraph)[/bold cyan]")
            console.print("=" * 65)
            console.print(f"   [bold]Target Role:[/bold]    {current_job.get('title')}")
            console.print(f"   [bold]Company:[/bold]        {current_job.get('company')}")
            console.print(f"   [bold]ATS Score:[/bold]      {score}%")
            console.print(f"   [bold]Posting URL:[/bold]    {current_job.get('url') or 'N/A'}")
            console.print(f"   [bold]Session Thread:[/bold] {thread_id} [dim](Saved in SQLite checkpoint DB)[/dim]")
            console.print("=" * 65)

            wa_group = getattr(cfg, "whatsapp_target_group", "WhatsApp")
            console.print("\n[bold]Choose an action for this listing:[/bold]")
            console.print("  [bold cyan][1][/bold cyan] ✅ Approve & Submit (via Stealth Browser)")
            console.print(f"  [bold cyan][2][/bold cyan] 📲 Send to WhatsApp Group ('{wa_group}') & Next")
            console.print(f"  [bold cyan][3][/bold cyan] 🚀 Both (Submit via Browser & Send to WhatsApp)")
            console.print("  [bold cyan][4][/bold cyan] ⏭️ Skip Listing")

            choice = Prompt.ask("👉 Action", choices=["1", "2", "3", "4"], default="1")

            if choice == "1":
                console.print("[bold green]Resuming graph execution to submit...[/bold green]")
                current_state = app.invoke(None, config=config_dict)
            elif choice == "2":
                console.print(f"[bold green]Posting job card to WhatsApp group '{wa_group}'...[/bold green]")
                try:
                    from src.tools.whatsapp_desktop import send_to_whatsapp_group, format_job_message
                    send_to_whatsapp_group(wa_group, format_job_message(current_job, ats_score=score))
                    console.print("[bold green]✅ Delivered to WhatsApp group![/bold green]")
                except Exception as e:
                    console.print(f"[bold red]Notice during WhatsApp dispatch: {e}[/bold red]")

                app.update_state(config_dict, {"application_status": "sent_whatsapp", "sent_to_whatsapp": True})
                current_state = app.invoke(None, config=config_dict)
            elif choice == "3":
                console.print(f"[bold green]Posting job card to WhatsApp group '{wa_group}'...[/bold green]")
                try:
                    from src.tools.whatsapp_desktop import send_to_whatsapp_group, format_job_message
                    send_to_whatsapp_group(wa_group, format_job_message(current_job, ats_score=score))
                    console.print("[bold green]✅ Delivered to WhatsApp group![/bold green]")
                except Exception as e:
                    console.print(f"[bold red]Notice during WhatsApp dispatch: {e}[/bold red]")

                app.update_state(config_dict, {"sent_to_whatsapp": True})
                console.print("[bold green]Resuming graph execution to submit...[/bold green]")
                current_state = app.invoke(None, config=config_dict)
            elif choice == "4":
                console.print("[yellow]Listing skipped by user. Advancing to next listing...[/yellow]")
                app.update_state(config_dict, {"application_status": "skipped"})
                current_state = app.invoke(None, config=config_dict)
        else:
            # Completed graph execution
            break

    applied = current_state.get("applied_count", 0)
    console.print(f"\n🎉 [bold green]Session complete! Submitted {applied} application(s).[/bold green]")
    Prompt.ask("\nPress [bold cyan]ENTER[/bold cyan] to return to menu")

def view_observability():
    """Observability Inspector & LangSmith Setup Guide."""
    console.print("\n[bold yellow]👁️ LangGraph Observability & Checkpoint Inspector[/bold yellow]\n")
    
    # 1. Check LangSmith status
    langsmith_enabled = os.getenv("LANGCHAIN_TRACING_V2", "").lower() in ("true", "1", "yes")
    ls_api_key = os.getenv("LANGCHAIN_API_KEY", "")
    
    ls_table = Table(title="Tracing & Observability Status", border_style="cyan")
    ls_table.add_column("System", style="bold")
    ls_table.add_column("Status")
    ls_table.add_column("Description")

    if langsmith_enabled and ls_api_key:
        ls_status = "[bold green]ENABLED (Active)[/bold green]"
        ls_desc = f"Tracing to project: {os.getenv('LANGCHAIN_PROJECT', 'job-hunting-agent')}"
    else:
        ls_status = "[bold yellow]AVAILABLE (Free to Enable)[/bold yellow]"
        ls_desc = "Add LANGCHAIN_TRACING_V2=true & LANGCHAIN_API_KEY in .env"

    ls_table.add_row("LangSmith Cloud Tracing", ls_status, ls_desc)

    db_path = cfg.checkpoints_dir / "job_agent.db"
    db_size = f"{db_path.stat().st_size // 1024} KB" if db_path.exists() else "0 KB"
    ls_table.add_row("SQLite Checkpoint DB", "[bold green]ONLINE[/bold green]", f"{db_path.name} ({db_size})")

    daily_file = cfg.logs_dir / "daily_stats.json"
    ls_table.add_row("Daily Anti-Ban Counter", "[bold green]ACTIVE[/bold green]", f"{daily_file.name}")
    console.print(ls_table)

    # 2. Checkpoint Thread Inspector
    threads = get_active_threads()
    console.print(f"\n[bold cyan]Saved Checkpoint Threads in SQLite ({len(threads)} total):[/bold cyan]")
    if threads:
        app = compile_graph(mode="supervised")
        th_table = Table(border_style="dim")
        th_table.add_column("Thread ID", style="bold")
        th_table.add_column("Next Step")
        th_table.add_column("ATS Score")
        th_table.add_column("Target Role")
        th_table.add_column("Applications")

        for th in threads[:6]:
            try:
                snap = app.get_state({"configurable": {"thread_id": th}})
                next_step = ", ".join(snap.next) if snap.next else "[green]Completed[/green]"
                vals = snap.values or {}
                ats = f"{vals.get('ats_score', 0)}%"
                role = vals.get("target_role", "N/A")
                apps = str(vals.get("applied_count", 0))
                th_table.add_row(th, next_step, ats, role, apps)
            except Exception:
                th_table.add_row(th, "Unknown", "N/A", "N/A", "0")
        console.print(th_table)
    else:
        console.print("[dim]No checkpoint threads recorded yet.[/dim]")

    console.print("\n[bold]How to connect visual LangSmith UI in 60 seconds:[/bold]")
    console.print("1. Go to [cyan]https://smith.langchain.com[/cyan] and create a free account.")
    console.print("2. Generate a free API Key in Settings.")
    console.print("3. Paste the following into your [bold].env[/bold] file:")
    console.print("   [green]LANGCHAIN_TRACING_V2=true[/green]")
    console.print("   [green]LANGCHAIN_API_KEY=lsv2_pt_...[/green]")
    console.print("   [green]LANGCHAIN_PROJECT=job-hunting-agent[/green]")
    console.print("4. Next time you run an action, open LangSmith to see live real-time DAG traces, token usage, and latency!\n")

    Prompt.ask("Press [bold cyan]ENTER[/bold cyan] to return to menu")

def manage_scheduler():
    console.print("\n[bold yellow]⏰ Windows Task Scheduler Management[/bold yellow]\n")
    console.print("  [1] Register Task Scheduler (Run headless every 3 hours)")
    console.print("  [2] Remove / Unregister Scheduled Task")
    console.print("  [0] Back to main menu")
    choice = Prompt.ask("\nSelect", choices=["0", "1", "2"], default="1")

    task_name = "AutonomousJobAgent_LangGraph"
    python_exe = sys.executable
    runner_script = str(cfg.workspace_root / "runner.py")

    if choice == "1":
        cmd = [
            "schtasks", "/create", "/tn", task_name,
            "/tr", f'"{python_exe}" "{runner_script}"',
            "/sc", "HOURLY", "/mo", "3", "/f"
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            console.print(f"✅ [bold green]Successfully registered Windows Task Scheduler job: {task_name}[/bold green]")
            console.print("   Runs headless every 3 hours automatically.")
        else:
            console.print(f"❌ [bold red]Notice:[/bold red] {res.stderr or res.stdout}")
        Prompt.ask("\nPress ENTER to continue")
    elif choice == "2":
        cmd = ["schtasks", "/delete", "/tn", task_name, "/f"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            console.print(f"✅ [bold green]Removed scheduled task: {task_name}[/bold green]")
        else:
            console.print(f"Notice: {res.stderr or res.stdout}")
        Prompt.ask("\nPress ENTER to continue")

def main():
    while True:
        os.system("cls" if os.name == "nt" else "clear")
        print_banner()
        console.print("\n  [bold cyan][1][/bold cyan] 🔍 Run System & AI Health Check (LangGraph StateGraph)")
        console.print("  [bold cyan][2][/bold cyan] 🎯 Run ATS Resume Matcher & Tailoring Engine")
        console.print("  [bold cyan][3][/bold cyan] 🌐 Launch Stealth Browser for One-Time Login (LinkedIn/Indeed)")
        console.print("  [bold cyan][4][/bold cyan] ⚡ Run Supervised Application Batch (Human-in-the-Loop & Resume)")
        console.print("  [bold cyan][5][/bold cyan] 🤖 Run Headless Application Batch (`runner.py`)")
        console.print("  [bold cyan][6][/bold cyan] 👁️ Observability & Checkpoint Inspector (LangSmith / Local DB)")
        console.print("  [bold cyan][7][/bold cyan] ⏰ Manage Windows Task Scheduler (Autopilot)")
        console.print("  [bold cyan][8][/bold cyan] 📁 Open Workspace Folders in Windows Explorer")
        console.print("  [bold cyan][9][/bold cyan] 🚀 Launch Web Dashboard UI (http://127.0.0.1:8765)")
        console.print("  [bold cyan][0][/bold cyan] ❌ Exit")
        console.print("-" * 70)

        choice = Prompt.ask("👉 Select an option", choices=["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"], default="9")

        if choice == "1":
            run_health_check()
        elif choice == "2":
            run_ats_matcher()
        elif choice == "3":
            with StealthBrowser(headless=False) as b:
                b.launch_login_session()
            Prompt.ask("\nPress ENTER to return to menu")
        elif choice == "4":
            run_supervised_session()
        elif choice == "5":
            console.print("\n[bold green]Launching Headless Batch via runner.py...[/bold green]\n")
            subprocess.run([sys.executable, str(cfg.workspace_root / "runner.py")])
            Prompt.ask("\nPress ENTER to return to menu")
        elif choice == "6":
            view_observability()
        elif choice == "7":
            manage_scheduler()
        elif choice == "8":
            os.system(f'explorer.exe "{cfg.workspace_root}"')
        elif choice == "9":
            console.print("\n[bold cyan]Starting Web Dashboard at http://127.0.0.1:8765 ...[/bold cyan]")
            import webbrowser
            webbrowser.open("http://127.0.0.1:8765")
            subprocess.run([sys.executable, str(cfg.workspace_root / "server.py")])
        elif choice == "0":
            console.print("\n[bold cyan]Goodbye and best of luck with your job hunt![/bold cyan]\n")
            break

if __name__ == "__main__":
    main()
