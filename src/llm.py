"""
src/llm.py
Unified AI Brain wrapper with intelligent fallback.
Combines Google Gemini Free Tier and Local/Remote Ollama into a seamless LangChain LLM interface.
Eliminates duplicated ask_llm implementations across scripts.
"""

import sys
import urllib.request
import json
from typing import Optional
from langchain_core.language_models.chat_models import BaseChatModel
from src.config import get_config

# Ensure Windows stdout never crashes on unicode
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

def _safe_print(msg: str):
    try:
        print(msg, flush=True)
    except Exception:
        try:
            print(msg.encode("ascii", "replace").decode("ascii"), flush=True)
        except Exception:
            pass

def get_gemini_chat() -> Optional[BaseChatModel]:
    """Instantiate ChatGoogleGenerativeAI if key is configured."""
    cfg = get_config()
    if not cfg.has_gemini:
        return None
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=cfg.gemini_model,
            google_api_key=cfg.gemini_api_key,
            temperature=0.3,
            timeout=30
        )
    except Exception as e:
        _safe_print(f"[WARN] Could not initialize Gemini Chat: {e}")
        return None

def get_ollama_chat(fast: bool = False) -> Optional[BaseChatModel]:
    """Instantiate ChatOllama pointing to local or Colab ngrok server."""
    cfg = get_config()
    model = cfg.ollama_fast_model if fast else cfg.ollama_model
    try:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            base_url=cfg.ollama_base_url,
            model=model,
            temperature=0.3,
            timeout=120
        )
    except Exception as e:
        _safe_print(f"[WARN] Could not initialize ChatOllama: {e}")
        return None

def query_llm(prompt: str, fast: bool = False) -> str:
    """
    Unified query runner with automatic multi-tier fallback:
    Tier 1: Gemini Free Tier API (fast & high quality)
    Tier 2: Local Ollama (unlimited, zero cost)
    Tier 3: Raw HTTP Ollama fallback (resilient if LangChain wrapper has issues)
    """
    cfg = get_config()

    # Tier 1: Try Gemini
    if cfg.has_gemini:
        try:
            gemini = get_gemini_chat()
            if gemini:
                res = gemini.invoke(prompt)
                content = getattr(res, "content", "")
                if isinstance(content, list):
                    content = " ".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in content])
                if content and content.strip():
                    return content.strip()
        except Exception as e:
            _safe_print(f"[WARN] Gemini query unavailable ({e}). Falling back to Ollama...")

    # Tier 2: Try LangChain Ollama
    try:
        ollama = get_ollama_chat(fast=fast)
        if ollama:
            res = ollama.invoke(prompt)
            content = getattr(res, "content", "")
            if content and content.strip():
                return content.strip()
    except Exception as e:
        _safe_print(f"[WARN] LangChain Ollama fallback notice ({e}). Trying raw Ollama HTTP...")

    # Tier 3: Direct Ollama HTTP endpoint
    try:
        model = cfg.ollama_fast_model if fast else cfg.ollama_model
        gen_url = f"{cfg.ollama_base_url}/api/generate"
        payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8")
        req = urllib.request.Request(gen_url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("response", "").strip()
    except Exception as e:
        return f"[AI Generation Error: Both Gemini and Ollama were unreachable: {e}]"
