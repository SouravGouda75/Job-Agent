"""
src/tools/pdf_builder.py
Generates clean, ATS-scannable PDF documents from markdown using ReportLab.
"""

from pathlib import Path
import re
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def compile_markdown_to_pdf(markdown_content: str, output_pdf_path: Path | str) -> Path:
    """Renders formatted markdown text into an ATS-friendly PDF."""
    target_path = Path(output_pdf_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    doc = SimpleDocTemplate(
        str(target_path),
        pagesize=letter,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()
    normal = styles['Normal']
    normal.fontSize = 9.5
    normal.leading = 13
    normal.textColor = colors.HexColor("#1A202C")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=15,
        leading=18,
        textColor=colors.HexColor("#1A365D"),
        spaceAfter=4
    )

    h2_style = ParagraphStyle(
        'DocH2',
        parent=styles['Heading2'],
        fontSize=11.5,
        leading=15,
        textColor=colors.HexColor("#2B6CB0"),
        spaceBefore=7,
        spaceAfter=3
    )

    bullet_style = ParagraphStyle(
        'DocBullet',
        parent=normal,
        leftIndent=14,
        firstLineIndent=-9,
        spaceAfter=2.5
    )

    story = []
    for line in markdown_content.split("\n"):
        line = line.strip()
        if not line or line.startswith("```"):
            continue

        if line.startswith("# "):
            clean_title = line[2:].strip().replace("**", "")
            story.append(Paragraph(f"<b>{clean_title}</b>", title_style))
            story.append(Spacer(1, 4))
        elif line.startswith("## ") or line.startswith("### "):
            clean_h2 = line.lstrip("#").strip().replace("**", "")
            story.append(Paragraph(f"<b>{clean_h2}</b>", h2_style))
            story.append(Spacer(1, 3))
        elif line.startswith("- ") or line.startswith("* "):
            bullet_text = line[2:].strip()
            bullet_text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", bullet_text)
            story.append(Paragraph(f"• {bullet_text}", bullet_style))
        elif line.startswith("---"):
            story.append(Spacer(1, 6))
        else:
            text = re.sub(r"\*\*(.*?)\*\*", r"<b>\1</b>", line)
            story.append(Paragraph(text, normal))
            story.append(Spacer(1, 2))

    doc.build(story)
    return target_path
