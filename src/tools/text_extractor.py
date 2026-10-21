"""
src/tools/text_extractor.py
Robust file text extraction for PDF, DOCX, TXT, and Markdown files.
Handles encodings gracefully on Windows.
"""

from pathlib import Path
import re

def extract_text(file_path: Path | str) -> str:
    """Extract full textual content from supported file types."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File does not exist: {path}")

    ext = path.suffix.lower()

    if ext in (".txt", ".md"):
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    elif ext == ".pdf":
        try:
            import pypdf
            reader = pypdf.PdfReader(str(path))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            full_text = "\n".join(pages_text).strip()
            if full_text:
                return full_text
        except Exception:
            pass

        # Fallback binary regex extraction
        with open(path, "rb") as f:
            raw = f.read().decode("latin1", errors="ignore")
            matches = re.findall(r"\(([A-Za-z0-9 ,.\-_;:\n\r]{3,})\)", raw)
            if matches:
                return "\n".join(matches)
        return f"[PDF raw extracted from {path.name}]"

    elif ext in (".docx", ".doc"):
        try:
            import docx
            doc = docx.Document(str(path))
            return "\n".join([p.text for p in doc.paragraphs if p.text.strip()])
        except Exception as e:
            return f"[DOCX extraction error for {path.name}: {e}]"

    else:
        # Fallback to UTF-8 text read
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()
