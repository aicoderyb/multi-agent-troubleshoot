"""Convert project markdown docs to PDF (ReportLab). Usage: python md_to_pdf.py input.md [output.pdf]"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _inline_markup(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    code_spans: list[str] = []

    def _code_placeholder(match: re.Match[str]) -> str:
        code_spans.append(match.group(1))
        return f"@@CODE{len(code_spans) - 1}@@"

    text = re.sub(r"`([^`]+)`", _code_placeholder, text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"\*([^*]+)\*", r"<i>\1</i>", text)
    for idx, code in enumerate(code_spans):
        text = text.replace(
            f"@@CODE{idx}@@",
            f"<font face='Courier' size='9'>{code}</font>",
        )
    return text


def _parse_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|"):
        line = line[:-1]
    return [cell.strip() for cell in line.split("|")]


def _is_table_separator(line: str) -> bool:
    return bool(re.match(r"^\s*\|?[\s\-:|]+\|?\s*$", line))


def _table_style(header: bool) -> TableStyle:
    style = TableStyle(
        [
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ]
    )
    if header:
        style.add("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7"))
        style.add("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold")
    return style


def build_story(md_text: str, styles) -> list:
    story: list = []
    lines = md_text.splitlines()
    i = 0
    in_code = False
    code_lines: list[str] = []

    body = ParagraphStyle(
        "Body",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=10,
        leading=14,
        spaceAfter=8,
        alignment=TA_LEFT,
    )
    h1 = ParagraphStyle(
        "H1",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        spaceBefore=6,
        spaceAfter=12,
    )
    h2 = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        spaceBefore=14,
        spaceAfter=8,
    )
    h3 = ParagraphStyle(
        "H3",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        spaceBefore=10,
        spaceAfter=6,
    )
    bullet = ParagraphStyle(
        "Bullet",
        parent=body,
        leftIndent=14,
        bulletIndent=0,
        spaceAfter=4,
    )
    code_style = ParagraphStyle(
        "CodeBlock",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=7.5,
        leading=9,
        backColor=colors.HexColor("#f4f4f4"),
        borderPadding=6,
        spaceAfter=10,
    )

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                block = "\n".join(code_lines)
                story.append(Preformatted(block, code_style))
                code_lines = []
                in_code = False
            else:
                in_code = True
            i += 1
            continue

        if in_code:
            code_lines.append(line)
            i += 1
            continue

        if not stripped:
            story.append(Spacer(1, 0.08 * inch))
            i += 1
            continue

        if stripped in ("---", "***", "___"):
            story.append(Spacer(1, 0.05 * inch))
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
            story.append(Spacer(1, 0.08 * inch))
            i += 1
            continue

        if stripped.startswith("# "):
            story.append(Paragraph(_inline_markup(stripped[2:]), h1))
            i += 1
            continue
        if stripped.startswith("## "):
            story.append(Paragraph(_inline_markup(stripped[3:]), h2))
            i += 1
            continue
        if stripped.startswith("### "):
            story.append(Paragraph(_inline_markup(stripped[4:]), h3))
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < len(lines) and _is_table_separator(lines[i + 1]):
            table_rows = [_parse_table_row(line)]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_rows.append(_parse_table_row(lines[i]))
                i += 1
            col_count = max(len(r) for r in table_rows)
            normalized = [r + [""] * (col_count - len(r)) for r in table_rows]
            usable_width = letter[0] - 1.25 * inch
            col_w = usable_width / col_count if col_count else usable_width
            tbl = Table(normalized, colWidths=[col_w] * col_count, repeatRows=1)
            tbl.setStyle(_table_style(header=True))
            story.append(tbl)
            story.append(Spacer(1, 0.12 * inch))
            continue

        if stripped.startswith("- "):
            while i < len(lines) and lines[i].strip().startswith("- "):
                item = lines[i].strip()[2:]
                story.append(
                    Paragraph(f"• {_inline_markup(item)}", bullet)
                )
                i += 1
            story.append(Spacer(1, 0.06 * inch))
            continue

        para_lines = [line.rstrip()]
        i += 1
        while i < len(lines):
            nxt = lines[i].strip()
            if (
                not nxt
                or nxt.startswith("#")
                or nxt.startswith("```")
                or nxt.startswith("|")
                or nxt.startswith("- ")
                or nxt in ("---", "***", "___")
            ):
                break
            para_lines.append(lines[i].rstrip())
            i += 1
        text = " ".join(para_lines)
        story.append(Paragraph(_inline_markup(text), body))

    return story


def md_to_pdf(md_path: Path, pdf_path: Path) -> None:
    md_text = md_path.read_text(encoding="utf-8")
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        title=md_path.stem,
    )
    doc.build(build_story(md_text, styles))


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("Usage: python md_to_pdf.py input.md [output.pdf]", file=sys.stderr)
        return 1
    md_path = Path(argv[1]).resolve()
    if not md_path.is_file():
        print(f"Not found: {md_path}", file=sys.stderr)
        return 1
    pdf_path = (
        Path(argv[2]).resolve()
        if len(argv) > 2
        else md_path.with_suffix(".pdf")
    )
    md_to_pdf(md_path, pdf_path)
    print(f"Wrote {pdf_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
