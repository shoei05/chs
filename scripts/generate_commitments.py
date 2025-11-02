#!/usr/bin/env python3
"""
Generate structured data that map CHS 2024 commitments
to their corresponding 2018 content, based on the local source files:

- chs_2024_japanese.pdf
- 2018.md
- 対応表.md

Output:
  public/data/commitments.json   (for the HTML app)

The script expects `pdftotext` from poppler to be available to extract text from
the CHS 2024 PDF. It will invoke it with `-layout` so requirement text is kept
together for parsing. The python-markdown package is used to convert 2018
content into HTML.
"""

from __future__ import annotations

import datetime
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


BASE_DIR = Path(__file__).resolve().parent.parent
PDF_PATH = BASE_DIR / "chs_2024_japanese.pdf"
MAPPING_PATH = BASE_DIR / "対応表.md"
SOURCE_2018_PATH = BASE_DIR / "2018.md"

DATA_DIR = BASE_DIR / "public" / "data"

TARGET_SECTIONS = ["パフォーマンス指標", "基本行動", "組織の責任", "ガイダンスノート"]


class GenerationError(Exception):
    """Custom exception used for predictable generation errors."""


def ensure_dependencies() -> None:
    """Verify required tools and source files are present."""
    if not PDF_PATH.exists():
        raise GenerationError(f"PDF not found: {PDF_PATH}")
    if not SOURCE_2018_PATH.exists():
        raise GenerationError(f"2018 Markdown not found: {SOURCE_2018_PATH}")
    if not MAPPING_PATH.exists():
        raise GenerationError(f"対応表 not found: {MAPPING_PATH}")
    try:
        subprocess.run(["pdftotext", "-v"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise GenerationError("pdftotext command not found. Install poppler or make it available in PATH.") from exc
    try:
        import markdown  # noqa: F401
    except ModuleNotFoundError as exc:
        raise GenerationError("python-markdown package is required. Install it with `python3 -m pip install markdown`.") from exc


def run_pdftotext(pdf_path: Path) -> str:
    """Return layout-preserving text extracted from the PDF."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout.decode("utf-8")


def clean_japanese_spacing(text: str) -> str:
    """Remove extra spaces inserted by PDF extraction while keeping necessary ones."""
    text = text.replace("\u3000", " ")
    patterns = [
        (r"([一-龯ぁ-んァ-ンー])\s+([一-龯ぁ-んァ-ンー])", r"\1\2"),
        (r"([一-龯ぁ-んァ-ンー])\s+([、。，．・！？「」『』（）［］｛｝])", r"\1\2"),
        (r"([、。，．・！？「」『』（）［］｛｝])\s+([一-龯ぁ-んァ-ンー])", r"\1\2"),
        (r"(\d)\s+([一-龯ぁ-んァ-ンー])", r"\1\2"),
        (r"([一-龯ぁ-んァ-ンー])\s+(\d)", r"\1\2"),
    ]
    previous = None
    while previous != text:
        previous = text
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)
    text = re.sub(r"\s{2,}", " ", text)
    return text.strip()


def emphasize_guidance_labels(text: str) -> str:
    """Bold the label portion before the first colon in guidance bullet items."""
    pattern = re.compile(r"^(\s*[\*\-]\s*)([^：\n]+)(：)", re.MULTILINE)
    return pattern.sub(lambda m: f"{m.group(1)}**{m.group(2)}{m.group(3)}**", text)


def format_numbered_bullets(text: str) -> str:
    """Lift numbered markers (e.g. * **1.1**) into headings."""
    if not text:
        return text
    number_pattern = re.compile(r"^\s*[\*\-]\s*\*\*(\d+\.\d+)\*\*\s*$")
    lines = text.splitlines()
    formatted: List[str] = []
    for line in lines:
        match = number_pattern.match(line)
        if match:
            formatted.append(f"##### {match.group(1)}")
            formatted.append("")
        else:
            formatted.append(line)
    return "\n".join(formatted)


@dataclass
class Requirement:
    idx: str
    text: str


@dataclass
class Commitment2024:
    number: int
    title: str
    requirements: List[Requirement]


@dataclass
class Commitment2018:
    number: int
    title: str
    intro: str
    sections: Dict[str, str] = field(default_factory=dict)


def parse_2024_commitments(pdf_text: str) -> Dict[int, Commitment2024]:
    """Parse commitments and requirements from the 2024 PDF text."""
    pattern = re.compile(r"コミットメント (\d+)\n(.*?)(?=\f?コミットメント \d+|\Z)", re.S)
    commitments: Dict[int, Commitment2024] = {}
    for match in pattern.finditer(pdf_text):
        number = int(match.group(1))
        block = match.group(2)
        lines = block.splitlines()
        state = "title"
        title_lines: List[str] = []
        requirements: List[Requirement] = []
        current_parts: List[str] = []
        current_idx: str | None = None

        for raw_line in lines:
            line = raw_line.rstrip("\n")
            stripped = line.strip()
            if state == "title":
                if "要件" in stripped:
                    state = "requirements"
                    continue
                if stripped:
                    title_lines.append(stripped)
                continue

            if state == "requirements":
                if not stripped:
                    continue
                if any(keyword in stripped for keyword in ("人道支援の質と説明責任", "www.corehumanitarianstandard.org")):
                    # Footer text from the PDF
                    continue
                match_req = re.match(r"\s*(\d+\.\d+)\s+(.*)", line)
                if match_req:
                    if current_idx is not None:
                        text = clean_japanese_spacing(" ".join(current_parts))
                        requirements.append(Requirement(idx=current_idx, text=text))
                        current_parts = []
                    current_idx = match_req.group(1)
                    current_parts.append(match_req.group(2).strip())
                else:
                    if stripped.isdigit():
                        # Page numbers
                        continue
                    if current_idx is not None:
                        current_parts.append(stripped)

        if current_idx is not None:
            text = clean_japanese_spacing(" ".join(current_parts))
            requirements.append(Requirement(idx=current_idx, text=text))

        title = clean_japanese_spacing(" ".join(title_lines))
        commitments[number] = Commitment2024(number=number, title=title, requirements=requirements)

    if len(commitments) != 9:
        raise GenerationError(f"Expected 9 commitments in 2024 PDF, found {len(commitments)}.")
    return commitments


def parse_2018_commitments(markdown_text: str) -> Dict[int, Commitment2018]:
    """Parse commitments and sections from 2018 Markdown source."""
    pattern = re.compile(r"### \*\*コミットメント(\d+)\*\*\n(.*?)(?=### \*\*コミットメント|\Z)", re.S)
    section_pattern = re.compile(r"#### \*\*(.*?)\*\*")
    commitments: Dict[int, Commitment2018] = {}

    for match in pattern.finditer(markdown_text):
        number = int(match.group(1))
        block = match.group(2)
        heading_lines = block.strip().splitlines()
        title_line = ""
        for line in heading_lines:
            line = line.strip()
            if line:
                title_line = line
                break
        section_matches = list(section_pattern.finditer(block))
        sections: Dict[str, str] = {}
        intro = ""
        if section_matches:
            intro_end = section_matches[0].start()
            intro = block[:intro_end].strip()
            for idx, section_match in enumerate(section_matches):
                name = section_match.group(1)
                start = section_match.end()
                end = section_matches[idx + 1].start() if idx + 1 < len(section_matches) else len(block)
                content = block[start:end].strip()
                sections[name] = content
        else:
            intro = block.strip()

        commitments[number] = Commitment2018(number=number, title=title_line.strip(), intro=intro, sections=sections)

    if len(commitments) != 9:
        raise GenerationError(f"Expected 9 commitments in 2018 Markdown, found {len(commitments)}.")
    return commitments


def parse_mapping(mapping_text: str) -> Dict[int, List[int]]:
    """Parse the 2024 -> 2018 commitment mapping."""
    mapping: Dict[int, List[int]] = {}
    lines = [line.strip() for line in mapping_text.splitlines() if line.strip()]
    # Skip header if present
    if lines and not lines[0][0].isdigit():
        lines = lines[1:]
    for line in lines:
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != 2:
            raise GenerationError(f"Unexpected mapping line format: {line}")
        year_2024 = int(parts[0])
        right = parts[1]
        targets = [piece.strip() for piece in re.split(r"[と,、]", right) if piece.strip()]
        mapping[year_2024] = [int(value) for value in targets]
    return mapping


def ensure_output_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def render_markdown_to_html(markdown_text: str) -> str:
    """Convert markdown text into HTML using python-markdown."""
    if not markdown_text:
        return ""
    import markdown

    return markdown.markdown(
        markdown_text,
        extensions=[
            "extra",
            "sane_lists",
        ],
        output_format="html5",
    )


def generate() -> None:
    ensure_dependencies()
    pdf_text = run_pdftotext(PDF_PATH)
    commitments_2024 = parse_2024_commitments(pdf_text)
    commitments_2018 = parse_2018_commitments(SOURCE_2018_PATH.read_text(encoding="utf-8"))
    mapping = parse_mapping(MAPPING_PATH.read_text(encoding="utf-8"))

    ensure_output_dirs()

    commitments_payload = []
    for number in sorted(commitments_2024):
        commitment = commitments_2024[number]
        target_numbers = mapping.get(number, [])
        legacy_commitments = [commitments_2018[idx] for idx in target_numbers]

        commitments_payload.append(
            {
                "year": 2024,
                "number": number,
                "title": commitment.title,
                "requirements": [{"id": req.idx, "text": req.text} for req in commitment.requirements],
                "legacy_commitments": [
                    {
                        "year": 2018,
                        "number": legacy.number,
                        "title": legacy.title,
                        "intro": legacy.intro.strip(),
                        "intro_html": render_markdown_to_html(legacy.intro.strip()),
                        "sections": {name: legacy.sections.get(name, "").strip() for name in TARGET_SECTIONS},
                        "sections_html": {
                            name: render_markdown_to_html(
                                emphasize_guidance_labels(legacy.sections.get(name, "").strip())
                                if name == "ガイダンスノート"
                                else format_numbered_bullets(legacy.sections.get(name, "").strip())
                                if name in {"基本行動", "組織の責任"}
                                else legacy.sections.get(name, "").strip()
                            )
                            for name in TARGET_SECTIONS
                        },
                    }
                    for legacy in legacy_commitments
                ],
            }
        )

    payload = {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source_files": {
            "chs_2024_pdf": str(PDF_PATH.name),
            "chs_2018_markdown": str(SOURCE_2018_PATH.name),
            "mapping_markdown": str(MAPPING_PATH.name),
        },
        "commitments": commitments_payload,
    }

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "commitments.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    try:
        generate()
    except GenerationError as exc:
        print(f"[generate_commitments] {exc}", file=sys.stderr)
        sys.exit(1)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
        print(f"[generate_commitments] Failed to extract PDF text: {stderr}", file=sys.stderr)
        sys.exit(exc.returncode)
