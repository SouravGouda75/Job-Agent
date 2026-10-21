"""
src/config.py
Centralized configuration manager for the Job Hunting Agent.
Replaces duplicate load_env across old scripts with a single cached source of truth.
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from dotenv import load_dotenv

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(WORKSPACE_ROOT / ".env")

@dataclass
class AgentConfig:
    workspace_root: Path = WORKSPACE_ROOT
    
    # AI Brains
    gemini_api_key: str = field(default_factory=lambda: os.getenv("GEMINI_API_KEY", "").strip())
    gemini_model: str = field(default_factory=lambda: os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip())
    ollama_base_url: str = field(default_factory=lambda: os.getenv("OLLAMA_BASE_URL", "http://localhost:11434").strip().rstrip("/"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "llama3.1:8b").strip())
    ollama_fast_model: str = field(default_factory=lambda: os.getenv("OLLAMA_FAST_MODEL", "llama3.2:3b").strip())
    openrouter_api_key: str = field(default_factory=lambda: os.getenv("OPENROUTER_API_KEY", "").strip())

    # Targeting
    target_roles: list[str] = field(default_factory=lambda: [
        r.strip() for r in os.getenv("TARGET_ROLES", "Software Engineer,Data Scientist").split(",") if r.strip()
    ])
    target_locations: list[str] = field(default_factory=lambda: [
        loc.strip() for loc in os.getenv("TARGET_LOCATIONS", os.getenv("TARGET_LOCATION", "Remote")).split(",") if loc.strip()
    ])
    target_cities: list[str] = field(default_factory=lambda: [
        c.strip() for c in os.getenv("TARGET_CITIES", "").split(",") if c.strip()
    ])
    max_applications_per_cycle: int = field(default_factory=lambda: int(os.getenv("MAX_APPLICATIONS_PER_CYCLE", "5")))

    # Job Eligibility Filters
    include_external_apply: bool = field(default_factory=lambda: os.getenv("INCLUDE_EXTERNAL_APPLY", "true").lower() in ("true", "1", "yes"))
    max_experience_years: int = field(default_factory=lambda: int(os.getenv("MAX_EXPERIENCE_YEARS", "2")))
    min_ats_score_to_show: int = field(default_factory=lambda: int(os.getenv("MIN_ATS_SCORE_TO_SHOW", "40")))
    date_posted_filter: str = field(default_factory=lambda: os.getenv("DATE_POSTED_FILTER", "past_week"))

    # WhatsApp Desktop Notifications
    whatsapp_enabled: bool = field(default_factory=lambda: os.getenv("WHATSAPP_ENABLED", "false").lower() in ("true", "1", "yes"))
    whatsapp_target_group: str = field(default_factory=lambda: os.getenv("WHATSAPP_TARGET_GROUP", "").strip())
    whatsapp_min_ats_score: int = field(default_factory=lambda: int(os.getenv("WHATSAPP_MIN_ATS_SCORE", "40")))

    # Safety & Anti-Ban Caps
    daily_max_linkedin: int = field(default_factory=lambda: int(os.getenv("DAILY_MAX_LINKEDIN", "40")))
    daily_max_indeed: int = field(default_factory=lambda: int(os.getenv("DAILY_MAX_INDEED", "25")))
    daily_max_glassdoor: int = field(default_factory=lambda: int(os.getenv("DAILY_MAX_GLASSDOOR", "20")))
    min_delay_seconds: int = field(default_factory=lambda: int(os.getenv("MIN_DELAY_SECONDS", "45")))
    max_delay_seconds: int = field(default_factory=lambda: int(os.getenv("MAX_DELAY_SECONDS", "90")))

    # Browser & Paths
    browser_profile_dir: Path = field(default_factory=lambda: (WORKSPACE_ROOT / os.getenv("BROWSER_PROFILE_DIR", "browser_profile")).resolve())
    headless_mode: bool = field(default_factory=lambda: os.getenv("HEADLESS_MODE", "False").lower() in ("true", "1", "yes"))
    resumes_dir: Path = field(default_factory=lambda: WORKSPACE_ROOT / "resumes")
    job_descriptions_dir: Path = field(default_factory=lambda: WORKSPACE_ROOT / "job_descriptions")
    tailored_resumes_dir: Path = field(default_factory=lambda: WORKSPACE_ROOT / "tailored_resumes")
    logs_dir: Path = field(default_factory=lambda: WORKSPACE_ROOT / "logs")
    checkpoints_dir: Path = field(default_factory=lambda: WORKSPACE_ROOT / "checkpoints")

    def __post_init__(self):
        # Ensure directories exist
        for d in [self.resumes_dir, self.job_descriptions_dir, self.tailored_resumes_dir, self.logs_dir, self.checkpoints_dir, self.browser_profile_dir]:
            d.mkdir(parents=True, exist_ok=True)

    @property
    def has_gemini(self) -> bool:
        return bool(self.gemini_api_key and "your_gemini_api_key" not in self.gemini_api_key.lower())

    @property
    def target_location(self) -> str:
        """Backward-compatible: returns first target location."""
        return self.target_locations[0] if self.target_locations else "Remote"


# Global singleton instance
config = AgentConfig()

def get_config() -> AgentConfig:
    return config
