#!/usr/bin/env python3
"""Session init/reconcile automation for /start skill.

Replaces all Agent Ref sections from SKILL.md with deterministic operations.
All commands output JSON for easy AI consumption.

Usage:
    session-init.py preflight                              # Detect environment
    session-init.py init --soul-purpose "..." --ralph-mode Manual --ralph-intensity ""
    session-init.py validate                               # Check/repair session files
    session-init.py cache-governance                        # Cache CLAUDE.md governance sections
    session-init.py restore-governance                      # Restore cached sections after /init
    session-init.py ensure-governance --ralph-mode Manual   # Add missing governance sections
    session-init.py read-context                            # Read soul purpose + active context
    session-init.py harvest                                 # Scan for promotable content
    session-init.py archive --old-purpose "..." [--new-purpose "..."]
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# Template resolution: plugin bundled templates > home dir fallback
_script_dir = Path(__file__).resolve().parent
_plugin_templates = _script_dir.parent / "templates"
_home_templates = Path.home() / "claude-session-init-templates"

if _plugin_templates.is_dir():
    TEMPLATE_DIR = _plugin_templates
else:
    TEMPLATE_DIR = _home_templates

SESSION_DIR = Path("session-context")
CLAUDE_MD = Path("CLAUDE.md")
GOVERNANCE_CACHE = Path("/tmp/claude-governance-cache.json")

REQUIRED_TEMPLATES = [
    "CLAUDE-activeContext.md",
    "CLAUDE-decisions.md",
    "CLAUDE-patterns.md",
    "CLAUDE-soul-purpose.md",
    "CLAUDE-troubleshooting.md",
    "CLAUDE-mdReference.md",
]

SESSION_FILES = [
    "CLAUDE-activeContext.md",
    "CLAUDE-decisions.md",
    "CLAUDE-patterns.md",
    "CLAUDE-soul-purpose.md",
    "CLAUDE-troubleshooting.md",
]

# Canonical governance section content (matches templates)
GOVERNANCE_SECTIONS = {
    "Structure Maintenance Rules": """\
## Structure Maintenance Rules

> These rules ensure the project stays organized across sessions.

- **CLAUDE.md** stays at root (Claude Code requirement)
- **Session context** files live in `session-context/` - NEVER at root
- **Scripts** (.sh, .ps1, .py, .js, .ts) go in `scripts/<category>/`
- **Documentation** (.md, .txt guides/reports) go in `docs/<category>/`
- **Config** files (.json, .yaml, .toml) go in `config/` unless framework-required at root
- **Logs** go in `logs/`
- When creating new files, place them in the correct category directory
- Do NOT dump new files at root unless they are actively being worked on
- Periodically review root for stale files and move to correct category""",

    "Session Context Files": """\
## Session Context Files (MUST maintain)

After every session, update these files in `session-context/` with timestamp and reasoning:

- `session-context/CLAUDE-activeContext.md` - Current session state, goals, progress
- `session-context/CLAUDE-decisions.md` - Architecture decisions and rationale
- `session-context/CLAUDE-patterns.md` - Established code patterns and conventions
- `session-context/CLAUDE-troubleshooting.md` - Common issues and proven solutions""",

    "IMMUTABLE TEMPLATE RULES": """\
## IMMUTABLE TEMPLATE RULES

> **DO NOT** edit the template files bundled with the plugin.
> Templates are immutable source-of-truth. Only edit the copies in your project.""",

    "Ralph Loop": """\
## Ralph Loop

**Mode**: {ralph_mode}
**Intensity**: {ralph_intensity}""",
}


def _out(data):
    """Print JSON output."""
    print(json.dumps(data, indent=2))


def _parse_md_sections(content):
    """Parse markdown into {heading: (start_line, content)} by ## headings.

    Handles code blocks correctly - ignores ## inside ``` fences.
    """
    sections = {}
    current_heading = None
    current_lines = []
    in_code_block = False

    for line in content.split('\n'):
        # Track code block state
        stripped = line.strip()
        if stripped.startswith('```'):
            in_code_block = not in_code_block

        # Only treat ## as heading outside code blocks
        if not in_code_block and line.startswith('## ') and not line.startswith('### '):
            if current_heading:
                sections[current_heading] = '\n'.join(current_lines)
            current_heading = line.strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_heading:
        sections[current_heading] = '\n'.join(current_lines)

    return sections


def _find_section(sections, key):
    """Find a section by partial case-insensitive match."""
    for heading, body in sections.items():
        if key.lower() in heading.lower():
            return heading, body
    return None, None


# -- Commands ------------------------------------------------------------------

def cmd_preflight(args):
    """Detect environment, return structured data."""
    result = {
        "mode": "reconcile" if SESSION_DIR.is_dir() else "init",
        "is_git": False,
        "has_claude_md": CLAUDE_MD.is_file(),
        "root_file_count": 0,
        "templates_valid": False,
        "template_count": 0,
        "session_files": {},
    }

    # Git check
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True, check=True
        )
        result["is_git"] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Root file count (excluding dirs and CLAUDE* files)
    root_files = [
        f for f in Path(".").iterdir()
        if f.is_file() and not f.name.startswith("CLAUDE")
    ]
    result["root_file_count"] = len(root_files)

    # Project signals -- detect context for brainstorm weight classification
    signals = {
        "has_readme": False,
        "readme_excerpt": "",
        "has_package_json": False,
        "package_name": "",
        "package_description": "",
        "has_pyproject": False,
        "has_cargo_toml": False,
        "has_go_mod": False,
        "has_code_files": False,
        "detected_stack": [],
        "is_empty_project": False,
    }

    # README detection
    readme = Path("README.md")
    if not readme.is_file():
        readme = Path("readme.md")
    if readme.is_file():
        signals["has_readme"] = True
        try:
            lines = readme.read_text(errors="replace").split("\n")
            content_lines = [
                l.strip() for l in lines
                if l.strip() and not l.strip().startswith("#")
            ][:3]
            signals["readme_excerpt"] = " ".join(content_lines)[:200]
        except Exception:
            pass

    # package.json detection
    pkg = Path("package.json")
    if pkg.is_file():
        signals["has_package_json"] = True
        try:
            data = json.loads(pkg.read_text(errors="replace"))
            signals["package_name"] = data.get("name", "")
            signals["package_description"] = data.get("description", "")
        except Exception:
            pass

    # Stack marker files
    if Path("pyproject.toml").is_file():
        signals["has_pyproject"] = True
        signals["detected_stack"].append("python")
    if Path("Cargo.toml").is_file():
        signals["has_cargo_toml"] = True
        signals["detected_stack"].append("rust")
    if Path("go.mod").is_file():
        signals["has_go_mod"] = True
        signals["detected_stack"].append("go")
    if signals["has_package_json"]:
        signals["detected_stack"].append("node")

    # Code file detection (root + src/)
    code_exts = {".py", ".js", ".ts", ".rs", ".go", ".jsx", ".tsx"}
    search_dirs = [Path(".")]
    if Path("src").is_dir():
        search_dirs.append(Path("src"))
    for d in search_dirs:
        try:
            for f in d.iterdir():
                if f.is_file() and f.suffix in code_exts:
                    signals["has_code_files"] = True
                    # Infer stack from extensions if not already detected
                    if f.suffix == ".py" and "python" not in signals["detected_stack"]:
                        signals["detected_stack"].append("python")
                    elif f.suffix in (".js", ".jsx", ".ts", ".tsx") and "node" not in signals["detected_stack"]:
                        signals["detected_stack"].append("node")
                    break  # One hit per directory is enough
        except PermissionError:
            pass

    # Empty project detection
    has_manifests = any([
        signals["has_readme"], signals["has_package_json"],
        signals["has_pyproject"], signals["has_cargo_toml"],
        signals["has_go_mod"],
    ])
    signals["is_empty_project"] = (
        not signals["has_code_files"]
        and not has_manifests
        and len(root_files) <= 2
    )

    result["project_signals"] = signals

    # Template validation
    existing = [f for f in REQUIRED_TEMPLATES if (TEMPLATE_DIR / f).is_file()]
    result["template_count"] = len(existing)
    result["templates_valid"] = len(existing) == len(REQUIRED_TEMPLATES)

    # Session file validation (if reconcile)
    if result["mode"] == "reconcile":
        for f in SESSION_FILES:
            path = SESSION_DIR / f
            result["session_files"][f] = {
                "exists": path.is_file(),
                "has_content": path.is_file() and path.stat().st_size > 0,
            }

    _out(result)


def cmd_init(args):
    """Bootstrap session-context with templates and soul purpose."""
    if not TEMPLATE_DIR.is_dir():
        _out({"status": "error", "message": f"Templates dir missing at {TEMPLATE_DIR}"})
        sys.exit(1)

    missing = [f for f in REQUIRED_TEMPLATES if not (TEMPLATE_DIR / f).is_file()]
    if missing:
        _out({"status": "error", "message": f"Missing templates: {missing}"})
        sys.exit(1)

    SESSION_DIR.mkdir(exist_ok=True)

    # Copy templates (session files only, not mdReference)
    for f in SESSION_FILES:
        src = TEMPLATE_DIR / f
        dst = SESSION_DIR / f
        if src.is_file():
            shutil.copy2(src, dst)

    # Migrate old root-level files
    for f in SESSION_FILES:
        root_file = Path(f)
        session_file = SESSION_DIR / f
        if root_file.is_file():
            if not session_file.is_file():
                root_file.rename(session_file)
            else:
                root_file.unlink()

    # Write soul purpose
    sp_file = SESSION_DIR / "CLAUDE-soul-purpose.md"
    sp_file.write_text(f"# Soul Purpose\n\n{args.soul_purpose}\n")

    # Seed active context
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ac_file = SESSION_DIR / "CLAUDE-activeContext.md"
    ac_file.write_text(f"""# Active Context

**Last Updated**: {today}
**Current Goal**: {args.soul_purpose}

## Current Session
- **Started**: {today}
- **Focus**: {args.soul_purpose}
- **Status**: Initialized

## Progress
- [x] Session initialized via /start
- [ ] Begin working on soul purpose

## Notes
- Soul purpose established: {today}
- Ralph Loop preference: {args.ralph_mode}
- Ralph Loop intensity: {getattr(args, 'ralph_intensity', '') or 'N/A'}
""")

    created = [f for f in SESSION_FILES if (SESSION_DIR / f).is_file()]
    _out({
        "status": "ok",
        "files_created": len(created),
        "expected": len(SESSION_FILES),
    })


def cmd_validate(args):
    """Validate session-context files, repair from templates if needed."""
    if not SESSION_DIR.is_dir():
        _out({"status": "error", "message": "session-context/ does not exist"})
        sys.exit(1)

    results = {"repaired": [], "ok": [], "failed": []}

    for f in SESSION_FILES:
        path = SESSION_DIR / f
        if path.is_file() and path.stat().st_size > 0:
            results["ok"].append(f)
        else:
            src = TEMPLATE_DIR / f
            if src.is_file():
                shutil.copy2(src, path)
                results["repaired"].append(f)
            else:
                results["failed"].append(f)

    results["status"] = "ok" if not results["failed"] else "partial"
    _out(results)


def cmd_cache_governance(args):
    """Extract governance sections from CLAUDE.md, save to temp cache."""
    if not CLAUDE_MD.is_file():
        _out({"status": "error", "message": "CLAUDE.md not found"})
        sys.exit(1)

    content = CLAUDE_MD.read_text()
    sections = _parse_md_sections(content)

    cached = {}
    governance_keys = list(GOVERNANCE_SECTIONS.keys())

    for key in governance_keys:
        heading, body = _find_section(sections, key)
        if body:
            cached[key] = body

    GOVERNANCE_CACHE.write_text(json.dumps(cached, indent=2))
    _out({
        "status": "ok",
        "cached_sections": list(cached.keys()),
        "missing_sections": [k for k in governance_keys if k not in cached],
        "cache_file": str(GOVERNANCE_CACHE),
    })


def cmd_restore_governance(args):
    """Restore governance sections to CLAUDE.md from cache."""
    # If CLAUDE.md was deleted by /init, recreate from template
    if not CLAUDE_MD.is_file():
        template = TEMPLATE_DIR / "CLAUDE-mdReference.md"
        if template.is_file():
            shutil.copy2(template, CLAUDE_MD)
        else:
            _out({"status": "error", "message": "CLAUDE.md and template both missing"})
            sys.exit(1)

    if not GOVERNANCE_CACHE.is_file():
        _out({"status": "error", "message": "No governance cache found. Run cache-governance first."})
        sys.exit(1)

    cached = json.loads(GOVERNANCE_CACHE.read_text())
    content = CLAUDE_MD.read_text()
    sections = _parse_md_sections(content)

    restored = []
    for key, cached_content in cached.items():
        heading, _ = _find_section(sections, key)
        if heading is None:
            # Section missing after /init - restore it
            content = content.rstrip() + f"\n\n---\n\n{cached_content}\n"
            restored.append(key)

    if restored:
        CLAUDE_MD.write_text(content)

    # Cleanup cache
    GOVERNANCE_CACHE.unlink(missing_ok=True)

    _out({
        "status": "ok",
        "restored": restored,
        "already_present": [k for k in cached if k not in restored],
    })


def cmd_ensure_governance(args):
    """Ensure all governance sections exist in CLAUDE.md. Add missing ones."""
    if not CLAUDE_MD.is_file():
        template = TEMPLATE_DIR / "CLAUDE-mdReference.md"
        if template.is_file():
            shutil.copy2(template, CLAUDE_MD)
        else:
            CLAUDE_MD.write_text("# CLAUDE.md\n\nThis file provides guidance to Claude Code.\n")

    content = CLAUDE_MD.read_text()
    sections = _parse_md_sections(content)

    ralph_mode = getattr(args, 'ralph_mode', 'Manual')
    ralph_intensity = getattr(args, 'ralph_intensity', '')
    added = []

    for key, template_content in GOVERNANCE_SECTIONS.items():
        heading, _ = _find_section(sections, key)
        if heading is None:
            section_text = template_content.format(ralph_mode=ralph_mode, ralph_intensity=ralph_intensity or 'N/A')
            content = content.rstrip() + f"\n\n---\n\n{section_text}\n"
            added.append(key)

    if added:
        CLAUDE_MD.write_text(content)

    _out({
        "status": "ok",
        "added": added,
        "already_present": [k for k in GOVERNANCE_SECTIONS if k not in added],
    })


def cmd_read_context(args):
    """Read soul purpose + active context, return structured summary."""
    result = {
        "soul_purpose": "",
        "has_archived_purposes": False,
        "active_context_summary": "",
        "open_tasks": [],
        "recent_progress": [],
        "status_hint": "unknown",
        "ralph_mode": "",
        "ralph_intensity": "",
    }

    # Read soul purpose
    sp_file = SESSION_DIR / "CLAUDE-soul-purpose.md"
    if sp_file.is_file():
        sp_content = sp_file.read_text()
        lines = sp_content.split('\n')
        purpose_lines = []
        for line in lines:
            if '[CLOSED]' in line:
                result["has_archived_purposes"] = True
                break
            if line.strip() and not line.startswith('#') and line.strip() != '---' and not line.strip().startswith('<!--'):
                purpose_lines.append(line.strip())
        result["soul_purpose"] = ' '.join(purpose_lines).strip()

        if '(No active soul purpose)' in sp_content or not result["soul_purpose"]:
            result["soul_purpose"] = ""
            result["status_hint"] = "no_purpose"

    # Read active context (first 60 lines for summary)
    ac_file = SESSION_DIR / "CLAUDE-activeContext.md"
    if ac_file.is_file():
        ac_content = ac_file.read_text()
        ac_lines = ac_content.split('\n')[:60]
        result["active_context_summary"] = '\n'.join(ac_lines)

        # Extract tasks
        for line in ac_content.split('\n'):
            stripped = line.strip()
            if '[ ]' in stripped:
                result["open_tasks"].append(stripped.lstrip('- '))
            elif '[x]' in stripped.lower():
                result["recent_progress"].append(stripped.lstrip('- '))

    # Extract ralph config from CLAUDE.md
    if CLAUDE_MD.is_file():
        md_content = CLAUDE_MD.read_text()
        md_sections = _parse_md_sections(md_content)
        _, ralph_body = _find_section(md_sections, "Ralph Loop")
        if ralph_body:
            for line in ralph_body.split('\n'):
                if line.strip().startswith('**Mode**:'):
                    result["ralph_mode"] = line.split('**Mode**:')[1].strip().lower()
                elif line.strip().startswith('**Intensity**:'):
                    result["ralph_intensity"] = line.split('**Intensity**:')[1].strip()

    _out(result)


def cmd_harvest(args):
    """Scan active context for promotable content. Returns candidates."""
    ac_file = SESSION_DIR / "CLAUDE-activeContext.md"
    if not ac_file.is_file():
        _out({"status": "nothing", "message": "No active context file."})
        return

    ac_content = ac_file.read_text()
    template = (TEMPLATE_DIR / "CLAUDE-activeContext.md").read_text() if (TEMPLATE_DIR / "CLAUDE-activeContext.md").is_file() else ""

    # Check if content is still template state
    if ac_content.strip() == template.strip() or len(ac_content.strip()) < 100:
        _out({"status": "nothing", "message": "Active context is in template state."})
        return

    # Return the raw content for AI to assess what's promotable
    # The AI makes judgment calls about what qualifies; this just provides the data
    _out({
        "status": "has_content",
        "active_context": ac_content,
        "target_files": {
            "decisions": str(SESSION_DIR / "CLAUDE-decisions.md"),
            "patterns": str(SESSION_DIR / "CLAUDE-patterns.md"),
            "troubleshooting": str(SESSION_DIR / "CLAUDE-troubleshooting.md"),
        },
    })


def cmd_archive(args):
    """Archive soul purpose and optionally set new one. Reset active context."""
    sp_file = SESSION_DIR / "CLAUDE-soul-purpose.md"
    if not sp_file.is_file():
        _out({"status": "error", "message": "Soul purpose file not found."})
        sys.exit(1)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Read existing content (may contain previous archives)
    existing = sp_file.read_text()

    # Build archived entry
    archived_block = f"## [CLOSED] \u2014 {today}\n\n{args.old_purpose}\n"

    if args.new_purpose:
        new_content = f"# Soul Purpose\n\n{args.new_purpose}\n\n---\n\n{archived_block}"
    else:
        new_content = f"# Soul Purpose\n\n(No active soul purpose)\n\n---\n\n{archived_block}"

    # Preserve any existing [CLOSED] entries
    if '[CLOSED]' in existing:
        # Find where archives start
        for i, line in enumerate(existing.split('\n')):
            if '[CLOSED]' in line:
                old_archives = '\n'.join(existing.split('\n')[i:])
                new_content = new_content.rstrip() + f"\n\n{old_archives}\n"
                break

    sp_file.write_text(new_content)

    # Reset active context from template
    ac_template = TEMPLATE_DIR / "CLAUDE-activeContext.md"
    ac_file = SESSION_DIR / "CLAUDE-activeContext.md"
    if ac_template.is_file():
        shutil.copy2(ac_template, ac_file)
    else:
        ac_file.write_text(f"# Active Context\n\n**Last Updated**: {today}\n")

    _out({
        "status": "ok",
        "archived_purpose": args.old_purpose[:80] + "..." if len(args.old_purpose) > 80 else args.old_purpose,
        "new_purpose": args.new_purpose or "(No active soul purpose)",
        "active_context_reset": True,
    })


# -- Main ---------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Session init/reconcile automation for /start skill"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # preflight
    subparsers.add_parser("preflight", help="Detect environment")

    # init
    init_p = subparsers.add_parser("init", help="Bootstrap session-context")
    init_p.add_argument("--soul-purpose", required=True)
    init_p.add_argument("--ralph-mode", default="Manual")
    init_p.add_argument("--ralph-intensity", default="")

    # validate
    subparsers.add_parser("validate", help="Validate/repair session files")

    # cache-governance
    subparsers.add_parser("cache-governance", help="Cache governance sections from CLAUDE.md")

    # restore-governance
    subparsers.add_parser("restore-governance", help="Restore cached governance sections")

    # ensure-governance
    eg_p = subparsers.add_parser("ensure-governance", help="Add missing governance sections")
    eg_p.add_argument("--ralph-mode", default="Manual")
    eg_p.add_argument("--ralph-intensity", default="")

    # read-context
    subparsers.add_parser("read-context", help="Read soul purpose + active context")

    # harvest
    subparsers.add_parser("harvest", help="Scan for promotable content")

    # archive
    arch_p = subparsers.add_parser("archive", help="Archive soul purpose, reset context")
    arch_p.add_argument("--old-purpose", required=True)
    arch_p.add_argument("--new-purpose", default="")

    args = parser.parse_args()

    commands = {
        "preflight": cmd_preflight,
        "init": cmd_init,
        "validate": cmd_validate,
        "cache-governance": cmd_cache_governance,
        "restore-governance": cmd_restore_governance,
        "ensure-governance": cmd_ensure_governance,
        "read-context": cmd_read_context,
        "harvest": cmd_harvest,
        "archive": cmd_archive,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
