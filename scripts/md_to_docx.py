"""Convert a markdown file to a formatted .docx document.

Used to generate docs/BUILD_PLAN.docx from docs/BUILD_PLAN.md.
Run:
    uv run --with python-docx python scripts/md_to_docx.py docs/BUILD_PLAN.md docs/BUILD_PLAN.docx
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import docx
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
from docx.shared import Inches, Pt, RGBColor


def set_cell_background(cell, hex_color: str):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    tcPr.append(shd)


def add_formatted_text(p, text: str):
    # Parses bold **text**, italic *text*, inline code `text`
    tokens = re.split(r"(\*\*.*?\*\*|\*.*?\*|`.*?`)", text)
    for token in tokens:
        if not token:
            continue
        if token.startswith("**") and token.endswith("**"):
            run = p.add_run(token[2:-2])
            run.bold = True
        elif token.startswith("*") and token.endswith("*"):
            run = p.add_run(token[1:-1])
            run.italic = True
        elif token.startswith("`") and token.endswith("`"):
            run = p.add_run(token[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(9.5)
            run.font.color.rgb = RGBColor(0x7C, 0x2D, 0x12)
        else:
            p.add_run(token)


def md_to_docx(src: Path, dest: Path):
    doc = docx.Document()

    # Page layout
    sections = doc.sections
    for s in sections:
        s.top_margin = Inches(1.0)
        s.bottom_margin = Inches(1.0)
        s.left_margin = Inches(1.0)
        s.right_margin = Inches(1.0)

    # Style defaults
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)
    style.font.color.rgb = RGBColor(0x1F, 0x29, 0x37)

    lines = src.read_text(encoding="utf-8").splitlines()
    in_code_block = False
    code_lines = []
    in_table = False
    table_rows = []

    def flush_table():
        nonlocal in_table, table_rows
        if not table_rows:
            in_table = False
            return
        # Parse table_rows: rows are list of cell strings
        num_cols = max(len(r) for r in table_rows)
        tbl = doc.add_table(rows=len(table_rows), cols=num_cols)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = True

        for r_idx, row in enumerate(table_rows):
            is_header = (r_idx == 0)
            for c_idx in range(num_cols):
                cell_text = row[c_idx] if c_idx < len(row) else ""
                cell = tbl.cell(r_idx, c_idx)
                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(3)
                p.paragraph_format.space_after = Pt(3)
                add_formatted_text(p, cell_text)
                if is_header:
                    for run in p.runs:
                        run.bold = True
                    set_cell_background(cell, "E5E7EB")
                elif r_idx % 2 == 1:
                    set_cell_background(cell, "F9FAFB")

        doc.add_paragraph()  # spacing
        table_rows = []
        in_table = False

    def flush_code():
        nonlocal in_code_block, code_lines
        if code_lines:
            code_text = "\n".join(code_lines)
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(6)
            p.paragraph_format.left_indent = Inches(0.25)
            run = p.add_run(code_text)
            run.font.name = "Consolas"
            run.font.size = Pt(9.5)
            run.font.color.rgb = RGBColor(0x37, 0x41, 0x51)
        code_lines = []
        in_code_block = False

    i = 0
    while i < len(lines):
        line = lines[i]

        # Code blocks
        if line.strip().startswith("```"):
            if in_code_block:
                flush_code()
            else:
                if in_table:
                    flush_table()
                in_code_block = True
                code_lines = []
            i += 1
            continue

        if in_code_block:
            code_lines.append(line)
            i += 1
            continue

        # Tables (lines starting with |)
        if line.strip().startswith("|") and line.strip().endswith("|"):
            # Check if separator row like |---|---|
            parts = [c.strip() for c in line.strip()[1:-1].split("|")]
            if all(re.match(r"^:?-+:?$", p) for p in parts if p):
                i += 1
                continue
            table_rows.append(parts)
            in_table = True
            i += 1
            continue
        elif in_table:
            flush_table()

        # Horizontal rule
        if re.match(r"^---+$", line.strip()):
            p = doc.add_paragraph()
            p.paragraph_format.space_before = Pt(6)
            p.paragraph_format.space_after = Pt(6)
            r = p.add_run("____________________________________________________________")
            r.font.color.rgb = RGBColor(0xD1, 0xD5, 0xDB)
            i += 1
            continue

        # Headings
        if line.startswith("# "):
            h = doc.add_heading(level=0)
            h.paragraph_format.space_before = Pt(16)
            h.paragraph_format.space_after = Pt(6)
            add_formatted_text(h, line[2:].strip())
            i += 1
            continue
        elif line.startswith("## "):
            h = doc.add_heading(level=1)
            h.paragraph_format.space_before = Pt(14)
            h.paragraph_format.space_after = Pt(4)
            add_formatted_text(h, line[3:].strip())
            i += 1
            continue
        elif line.startswith("### "):
            h = doc.add_heading(level=2)
            h.paragraph_format.space_before = Pt(10)
            h.paragraph_format.space_after = Pt(3)
            add_formatted_text(h, line[4:].strip())
            i += 1
            continue
        elif line.startswith("#### "):
            h = doc.add_heading(level=3)
            h.paragraph_format.space_before = Pt(8)
            h.paragraph_format.space_after = Pt(2)
            add_formatted_text(h, line[5:].strip())
            i += 1
            continue

        # Blockquote
        if line.startswith("> "):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Inches(0.4)
            p.paragraph_format.space_before = Pt(4)
            p.paragraph_format.space_after = Pt(6)
            r = p.add_run("“ ")
            r.font.size = Pt(14)
            r.font.color.rgb = RGBColor(0x9C, 0xA3, 0xAF)
            add_formatted_text(p, line[2:].strip())
            p.runs[-1].italic = True
            i += 1
            continue

        # Bullet list
        if re.match(r"^[-*]\s+", line.strip()):
            content = re.sub(r"^[-*]\s+", "", line.strip())
            p = doc.add_paragraph(style="List Bullet")
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(2)
            add_formatted_text(p, content)
            i += 1
            continue

        # Numbered list
        if re.match(r"^\d+\.\s+", line.strip()):
            content = re.sub(r"^\d+\.\s+", "", line.strip())
            p = doc.add_paragraph(style="List Number")
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(2)
            add_formatted_text(p, content)
            i += 1
            continue

        # Empty lines
        if not line.strip():
            i += 1
            continue

        # Regular paragraph
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(4)
        p.paragraph_format.line_spacing = 1.15
        add_formatted_text(p, line)
        i += 1

    if in_table:
        flush_table()
    if in_code_block:
        flush_code()

    dest.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(dest))
    print(f"Successfully converted {src} to {dest}")


if __name__ == "__main__":
    src_file = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("docs/BUILD_PLAN.md")
    dest_file = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("docs/BUILD_PLAN.docx")
    md_to_docx(src_file, dest_file)
