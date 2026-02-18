"""File-based state helpers for session-context/ directory."""

import json
from pathlib import Path

from .config import SESSION_DIR_NAME, CLAUDE_MD_NAME


def session_dir(project_dir: str) -> Path:
    return Path(project_dir) / SESSION_DIR_NAME


def claude_md(project_dir: str) -> Path:
    return Path(project_dir) / CLAUDE_MD_NAME


def parse_md_sections(content: str) -> dict[str, str]:
    """Parse markdown into {heading: content} by ## headings.

    Handles code blocks correctly — ignores ## inside ``` fences.
    """
    sections: dict[str, str] = {}
    current_heading: str | None = None
    current_lines: list[str] = []
    in_code_block = False

    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("```"):
            in_code_block = not in_code_block

        if not in_code_block and line.startswith("## ") and not line.startswith("### "):
            if current_heading:
                sections[current_heading] = "\n".join(current_lines)
            current_heading = line.strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_heading:
        sections[current_heading] = "\n".join(current_lines)

    return sections


def find_section(sections: dict[str, str], key: str) -> tuple[str | None, str | None]:
    """Find a section by partial case-insensitive match."""
    for heading, body in sections.items():
        if key.lower() in heading.lower():
            return heading, body
    return None, None


def read_json(path: Path) -> dict:
    """Read a JSON file, return empty dict on failure."""
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def write_json(path: Path, data: dict) -> None:
    """Write dict as pretty JSON."""
    path.write_text(json.dumps(data, indent=2))
