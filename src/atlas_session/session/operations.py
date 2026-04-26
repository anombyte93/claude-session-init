"""Core session lifecycle operations.

Extracted from session-init.py — all logic preserved, adapted to be
called as functions (not CLI subcommands) returning dicts instead of
printing JSON.

SECURITY: All project_dir parameters are resolved and validated to
prevent path traversal attacks.
"""

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from ..common.config import (
    GOVERNANCE_CACHE_PATH,
    GOVERNANCE_SECTIONS,
    LIFECYCLE_STATE_FILENAME,
    REQUIRED_TEMPLATES,
    SESSION_FILES,
    TEMPLATE_DIR,
)
from ..common.state import (
    claude_md,
    find_section,
    parse_md_sections,
    session_dir,
)

# Capability inventory cache constants
CAPABILITY_CACHE_FILENAME = ".capability-cache.json"
CAPABILITY_INVENTORY_FILENAME = "CLAUDE-capability-inventory.md"


def _resolve_project_dir(project_dir: str) -> Path:
    """Resolve and validate project_dir to prevent path traversal.

    Returns:
        Resolved absolute Path object

    Raises:
        ValueError: If resolved path is outside home directory or /tmp.
    """
    path = Path(project_dir).resolve()

    home = Path.home().resolve()
    tmp = Path("/tmp").resolve()
    if not (str(path).startswith(str(home)) or str(path).startswith(str(tmp))):
        raise ValueError(f"Project directory must be under home or /tmp: {path}")

    return path


# ---------------------------------------------------------------------------
# preflight
# ---------------------------------------------------------------------------


def preflight(project_dir: str) -> dict:
    """Detect environment, return structured data."""
    sd = session_dir(project_dir)
    cmd = claude_md(project_dir)
    root = Path(project_dir)

    result: dict = {
        "mode": "reconcile" if sd.is_dir() else "init",
        "is_git": False,
        "has_claude_md": cmd.is_file(),
        "root_file_count": 0,
        "templates_valid": False,
        "template_count": 0,
        "session_files": {},
    }

    # Git check
    try:
        subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            check=True,
            cwd=project_dir,
        )
        result["is_git"] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Root file count
    root_files = [f for f in root.iterdir() if f.is_file() and not f.name.startswith("CLAUDE")]
    result["root_file_count"] = len(root_files)

    # Project signals
    signals = _detect_project_signals(root, root_files)
    result["project_signals"] = signals

    # Template validation
    existing = [f for f in REQUIRED_TEMPLATES if (TEMPLATE_DIR / f).is_file()]
    result["template_count"] = len(existing)
    result["templates_valid"] = len(existing) == len(REQUIRED_TEMPLATES)

    # Session file validation (if reconcile)
    if result["mode"] == "reconcile":
        for f in SESSION_FILES:
            path = sd / f
            result["session_files"][f] = {
                "exists": path.is_file(),
                "has_content": path.is_file() and path.stat().st_size > 0,
            }

    return result


def _detect_project_signals(root: Path, root_files: list[Path]) -> dict:
    """Detect context for brainstorm weight classification."""
    signals: dict = {
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
    readme = root / "README.md"
    if not readme.is_file():
        readme = root / "readme.md"
    if readme.is_file():
        signals["has_readme"] = True
        try:
            lines = readme.read_text(errors="replace").split("\n")
            content_lines = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#")][:3]
            signals["readme_excerpt"] = " ".join(content_lines)[:200]
        except Exception:
            pass

    # package.json
    pkg = root / "package.json"
    if pkg.is_file():
        signals["has_package_json"] = True
        try:
            data = json.loads(pkg.read_text(errors="replace"))
            signals["package_name"] = data.get("name", "")
            signals["package_description"] = data.get("description", "")
        except Exception:
            pass

    # Stack marker files
    if (root / "pyproject.toml").is_file():
        signals["has_pyproject"] = True
        signals["detected_stack"].append("python")
    if (root / "Cargo.toml").is_file():
        signals["has_cargo_toml"] = True
        signals["detected_stack"].append("rust")
    if (root / "go.mod").is_file():
        signals["has_go_mod"] = True
        signals["detected_stack"].append("go")
    if signals["has_package_json"]:
        signals["detected_stack"].append("node")

    # Code file detection
    code_exts = {".py", ".js", ".ts", ".rs", ".go", ".jsx", ".tsx"}
    search_dirs = [root]
    if (root / "src").is_dir():
        search_dirs.append(root / "src")
    for d in search_dirs:
        try:
            for f in d.iterdir():
                if f.is_file() and f.suffix in code_exts:
                    signals["has_code_files"] = True
                    if f.suffix == ".py" and "python" not in signals["detected_stack"]:
                        signals["detected_stack"].append("python")
                    elif f.suffix in (".js", ".jsx", ".ts", ".tsx") and "node" not in signals["detected_stack"]:
                        signals["detected_stack"].append("node")
                    break
        except PermissionError:
            pass

    # CI provider detection
    ci_indicators = [
        (root / ".github" / "workflows", "github-actions"),
        (root / ".gitlab-ci.yml", "gitlab-ci"),
        (root / "Jenkinsfile", "jenkins"),
        (root / ".circleci", "circleci"),
    ]
    signals["has_ci"] = False
    signals["ci_provider"] = ""
    for ci_path, provider in ci_indicators:
        if ci_path.exists():
            signals["has_ci"] = True
            signals["ci_provider"] = provider
            break

    # Empty project detection
    has_manifests = any(
        [
            signals["has_readme"],
            signals["has_package_json"],
            signals["has_pyproject"],
            signals["has_cargo_toml"],
            signals["has_go_mod"],
        ]
    )
    signals["is_empty_project"] = not signals["has_code_files"] and not has_manifests and len(root_files) <= 2

    return signals


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


def init(
    project_dir: str,
    soul_purpose: str,
    ralph_mode: str = "Manual",
    ralph_intensity: str = "",
) -> dict:
    """Bootstrap session-context with templates and soul purpose."""
    sd = session_dir(project_dir)

    if not TEMPLATE_DIR.is_dir():
        return {"status": "error", "message": f"Templates dir missing at {TEMPLATE_DIR}"}

    missing = [f for f in REQUIRED_TEMPLATES if not (TEMPLATE_DIR / f).is_file()]
    if missing:
        return {"status": "error", "message": f"Missing templates: {missing}"}

    sd.mkdir(exist_ok=True)

    # Copy templates (session files only)
    for f in SESSION_FILES:
        src = TEMPLATE_DIR / f
        dst = sd / f
        if src.is_file():
            shutil.copy2(src, dst)

    # Migrate old root-level files
    root = Path(project_dir)
    for f in SESSION_FILES:
        root_file = root / f
        session_file = sd / f
        if root_file.is_file():
            if not session_file.is_file():
                root_file.rename(session_file)
            else:
                root_file.unlink()

    # Write soul purpose
    sp_file = sd / "CLAUDE-soul-purpose.md"
    sp_file.write_text(f"# Soul Purpose\n\n{soul_purpose}\n")

    # Seed active context
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ac_file = sd / "CLAUDE-activeContext.md"
    ac_file.write_text(
        f"# Active Context\n\n"
        f"**Last Updated**: {today}\n"
        f"**Current Goal**: {soul_purpose}\n\n"
        f"## Current Session\n"
        f"- **Started**: {today}\n"
        f"- **Focus**: {soul_purpose}\n"
        f"- **Status**: Initialized\n\n"
        f"## Progress\n"
        f"- [x] Session initialized via /start\n"
        f"- [ ] Begin working on soul purpose\n\n"
        f"## Notes\n"
        f"- Soul purpose established: {today}\n"
        f"- Ralph Loop preference: {ralph_mode}\n"
        f"- Ralph Loop intensity: {ralph_intensity or 'N/A'}\n"
    )

    created = [f for f in SESSION_FILES if (sd / f).is_file()]
    return {
        "status": "ok",
        "files_created": len(created),
        "expected": len(SESSION_FILES),
    }


# ---------------------------------------------------------------------------
# validate
# ---------------------------------------------------------------------------


def validate(project_dir: str) -> dict:
    """Validate session-context files, repair from templates if needed."""
    sd = session_dir(project_dir)
    if not sd.is_dir():
        return {"status": "error", "message": "session-context/ does not exist"}

    results: dict = {"repaired": [], "ok": [], "failed": []}

    for f in SESSION_FILES:
        path = sd / f
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
    return results


# ---------------------------------------------------------------------------
# cache_governance
# ---------------------------------------------------------------------------


def cache_governance(project_dir: str) -> dict:
    """Extract governance sections from CLAUDE.md, save to temp cache."""
    cmd = claude_md(project_dir)
    if not cmd.is_file():
        return {"status": "error", "message": "CLAUDE.md not found"}

    content = cmd.read_text()
    sections = parse_md_sections(content)

    cached: dict[str, str] = {}
    governance_keys = list(GOVERNANCE_SECTIONS.keys())

    for key in governance_keys:
        _, body = find_section(sections, key)
        if body:
            cached[key] = body

    GOVERNANCE_CACHE_PATH.write_text(json.dumps(cached, indent=2))
    return {
        "status": "ok",
        "cached_sections": list(cached.keys()),
        "missing_sections": [k for k in governance_keys if k not in cached],
        "cache_file": str(GOVERNANCE_CACHE_PATH),
    }


# ---------------------------------------------------------------------------
# restore_governance
# ---------------------------------------------------------------------------


def restore_governance(project_dir: str) -> dict:
    """Restore governance sections to CLAUDE.md from cache."""
    cmd = claude_md(project_dir)

    if not cmd.is_file():
        template = TEMPLATE_DIR / "CLAUDE-mdReference.md"
        if template.is_file():
            shutil.copy2(template, cmd)
        else:
            return {"status": "error", "message": "CLAUDE.md and template both missing"}

    if not GOVERNANCE_CACHE_PATH.is_file():
        return {"status": "error", "message": "No governance cache found. Run cache-governance first."}

    cached = json.loads(GOVERNANCE_CACHE_PATH.read_text())
    content = cmd.read_text()
    sections = parse_md_sections(content)

    restored: list[str] = []
    for key, cached_content in cached.items():
        heading, _ = find_section(sections, key)
        if heading is None:
            content = content.rstrip() + f"\n\n---\n\n{cached_content}\n"
            restored.append(key)

    if restored:
        cmd.write_text(content)

    GOVERNANCE_CACHE_PATH.unlink(missing_ok=True)

    return {
        "status": "ok",
        "restored": restored,
        "already_present": [k for k in cached if k not in restored],
    }


# ---------------------------------------------------------------------------
# ensure_governance
# ---------------------------------------------------------------------------


def ensure_governance(
    project_dir: str,
    ralph_mode: str = "Manual",
    ralph_intensity: str = "",
) -> dict:
    """Ensure all governance sections exist in CLAUDE.md."""
    cmd = claude_md(project_dir)

    if not cmd.is_file():
        template = TEMPLATE_DIR / "CLAUDE-mdReference.md"
        if template.is_file():
            shutil.copy2(template, cmd)
        else:
            cmd.write_text("# CLAUDE.md\n\nThis file provides guidance to Claude Code.\n")

    content = cmd.read_text()
    sections = parse_md_sections(content)

    added: list[str] = []
    for key, template_content in GOVERNANCE_SECTIONS.items():
        heading, _ = find_section(sections, key)
        if heading is None:
            section_text = template_content.format(
                ralph_mode=ralph_mode,
                ralph_intensity=ralph_intensity or "N/A",
            )
            content = content.rstrip() + f"\n\n---\n\n{section_text}\n"
            added.append(key)

    if added:
        cmd.write_text(content)

    return {
        "status": "ok",
        "added": added,
        "already_present": [k for k in GOVERNANCE_SECTIONS if k not in added],
    }


# ---------------------------------------------------------------------------
# read_context
# ---------------------------------------------------------------------------


def read_context(project_dir: str) -> dict:
    """Read soul purpose + active context, return structured summary."""
    sd = session_dir(project_dir)
    cmd = claude_md(project_dir)

    result: dict = {
        "soul_purpose": "",
        "has_archived_purposes": False,
        "active_context_summary": "",
        "open_tasks": [],
        "recent_progress": [],
        "status_hint": "unknown",
        "ralph_mode": "",
        "ralph_intensity": "",
        "session_state": None,  # NEW: Active | Paused | Closing
        "focus_status": None,  # NEW: In Progress | Blocked | Done | Moving To Next
    }

    # Read soul purpose
    sp_file = sd / "CLAUDE-soul-purpose.md"
    if sp_file.is_file():
        sp_content = sp_file.read_text(errors="replace")
        lines = sp_content.split("\n")
        purpose_lines: list[str] = []
        for line in lines:
            if "[CLOSED]" in line:
                result["has_archived_purposes"] = True
                break
            if (
                line.strip()
                and not line.startswith("#")
                and line.strip() != "---"
                and not line.strip().startswith("<!--")
            ):
                purpose_lines.append(line.strip())
        result["soul_purpose"] = " ".join(purpose_lines).strip()

        if "(No active soul purpose)" in result["soul_purpose"] or not result["soul_purpose"]:
            result["soul_purpose"] = ""
            result["status_hint"] = "no_purpose"

    # Read active context (first 60 lines)
    ac_file = sd / "CLAUDE-activeContext.md"
    if ac_file.is_file():
        ac_content = ac_file.read_text(errors="replace")
        ac_lines = ac_content.split("\n")[:60]
        result["active_context_summary"] = "\n".join(ac_lines)

        for line in ac_content.split("\n"):
            stripped = line.strip()
            # Parse new fields (Session State, Focus Status)
            if stripped.startswith("- **Session State**:") or "**Session State**:" in stripped:
                for state in ["Active", "Paused", "Closing"]:
                    if state in stripped:
                        result["session_state"] = state.lower()
            elif stripped.startswith("- **Focus Status**:") or "**Focus Status**:" in stripped:
                for status in ["In Progress", "Blocked", "Done", "Moving To Next"]:
                    if status in stripped:
                        result["focus_status"] = status.lower().replace(" ", "_")
            # Legacy "Status:" parsing for backward compatibility
            elif stripped.startswith("- **Status**:"):
                if "In Progress" in stripped:
                    result["focus_status"] = "in_progress"
                elif "Blocked" in stripped:
                    result["focus_status"] = "blocked"
                    result["status_hint"] = "blocked"
                elif "Complete" in stripped:
                    # Legacy "Complete" is ambiguous - interpret based on open_tasks
                    if result.get("open_tasks"):
                        result["focus_status"] = "done"
                        result["status_hint"] = "moving_to_next"
                    else:
                        result["focus_status"] = "done"
                        result["status_hint"] = "probably_complete"
            # Parse tasks
            elif "[ ]" in stripped:
                result["open_tasks"].append(stripped.lstrip("- "))
            elif "[x]" in stripped.lower():
                result["recent_progress"].append(stripped.lstrip("- "))

        # Update status_hint based on new fields
        if result["session_state"] == "closing":
            result["status_hint"] = "closing"
        elif result["focus_status"] == "blocked":
            result["status_hint"] = "blocked"
        elif result["focus_status"] == "done":
            result["status_hint"] = "probably_complete"
        elif result["focus_status"] == "moving_to_next":
            result["status_hint"] = "moving_to_next"
        elif result["open_tasks"]:
            result["status_hint"] = "clearly_incomplete"

    # Extract ralph config from CLAUDE.md
    if cmd.is_file():
        md_content = cmd.read_text()
        md_sections = parse_md_sections(md_content)
        _, ralph_body = find_section(md_sections, "Ralph Loop")
        if ralph_body:
            for line in ralph_body.split("\n"):
                if line.strip().startswith("**Mode**:"):
                    result["ralph_mode"] = line.split("**Mode**:")[1].strip().lower()
                elif line.strip().startswith("**Intensity**:"):
                    result["ralph_intensity"] = line.split("**Intensity**:")[1].strip()

    return result
# ---------------------------------------------------------------------------


def harvest(project_dir: str) -> dict:
    """Scan active context for promotable content."""
    sd = session_dir(project_dir)
    ac_file = sd / "CLAUDE-activeContext.md"
    if not ac_file.is_file():
        return {"status": "nothing", "message": "No active context file."}

    ac_content = ac_file.read_text()
    template_path = TEMPLATE_DIR / "CLAUDE-activeContext.md"
    template = template_path.read_text() if template_path.is_file() else ""

    if ac_content.strip() == template.strip() or len(ac_content.strip()) < 100:
        return {"status": "nothing", "message": "Active context is in template state."}

    return {
        "status": "has_content",
        "active_context": ac_content,
        "target_files": {
            "decisions": str(sd / "CLAUDE-decisions.md"),
            "patterns": str(sd / "CLAUDE-patterns.md"),
            "troubleshooting": str(sd / "CLAUDE-troubleshooting.md"),
        },
    }


# ---------------------------------------------------------------------------
# archive
# ---------------------------------------------------------------------------


def archive(
    project_dir: str,
    old_purpose: str,
    new_purpose: str = "",
) -> dict:
    """Archive soul purpose and optionally set new one. Reset active context."""
    sd = session_dir(project_dir)
    sp_file = sd / "CLAUDE-soul-purpose.md"
    if not sp_file.is_file():
        return {"status": "error", "message": "Soul purpose file not found."}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    existing = sp_file.read_text()

    archived_block = f"## [CLOSED] \u2014 {today}\n\n{old_purpose}\n"

    if new_purpose:
        new_content = f"# Soul Purpose\n\n{new_purpose}\n\n---\n\n{archived_block}"
    else:
        new_content = f"# Soul Purpose\n\n(No active soul purpose)\n\n---\n\n{archived_block}"

    # Preserve existing [CLOSED] entries
    if "[CLOSED]" in existing:
        lines = existing.split("\n")
        for i, line in enumerate(lines):
            if "[CLOSED]" in line:
                old_archives = "\n".join(lines[i:])
                new_content = new_content.rstrip() + f"\n\n{old_archives}\n"
                break

    sp_file.write_text(new_content)

    # Reset active context from template
    ac_template = TEMPLATE_DIR / "CLAUDE-activeContext.md"
    ac_file = sd / "CLAUDE-activeContext.md"
    if ac_template.is_file():
        shutil.copy2(ac_template, ac_file)
    else:
        ac_file.write_text(f"# Active Context\n\n**Last Updated**: {today}\n")

    return {
        "status": "ok",
        "archived_purpose": old_purpose[:80] + "..." if len(old_purpose) > 80 else old_purpose,
        "new_purpose": new_purpose or "(No active soul purpose)",
        "active_context_reset": True,
    }


# ---------------------------------------------------------------------------
# check_clutter
# ---------------------------------------------------------------------------

ROOT_WHITELIST_EXACT = {
    "claude.md",
    "readme.md",
    "license",
    "license.md",
    "cname",
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "tsconfig.json",
    "jsconfig.json",
    "next.config.js",
    "next.config.mjs",
    "next.config.ts",
    "next-env.d.ts",
    "vercel.json",
    "netlify.toml",
    "middleware.ts",
    "middleware.js",
    "instrumentation.ts",
    "tailwind.config.js",
    "tailwind.config.ts",
    "tailwind.config.mjs",
    "postcss.config.js",
    "postcss.config.mjs",
    "postcss.config.cjs",
    "eslint.config.js",
    "eslint.config.mjs",
    ".eslintrc.js",
    ".eslintrc.json",
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.js",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".dockerignore",
    ".gitignore",
    ".gitattributes",
    ".editorconfig",
    "makefile",
    "rakefile",
    "gemfile",
    "gemfile.lock",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "requirements.txt",
    "cargo.toml",
    "cargo.lock",
    "go.mod",
    "go.sum",
    "sanity.config.ts",
    "sanity.config.js",
    "sanity.cli.ts",
    "sanity.cli.js",
    "drizzle.config.ts",
    "drizzle.config.js",
    "vitest.config.ts",
    "vitest.config.js",
    "jest.config.ts",
    "jest.config.js",
    "playwright.config.ts",
    "playwright.config.js",
    "index.html",
    "robots.txt",
    "sitemap.xml",
    "components.json",
    "railway.toml",
    "fly.toml",
    "render.yaml",
    "app.yaml",
    "turbo.json",
    "nx.json",
    "lerna.json",
    "pnpm-workspace.yaml",
    "vitest.setup.ts",
    "vitest.setup.js",
    "jest.setup.ts",
    "jest.setup.js",
    "tsconfig.tsbuildinfo",
    "commitlint.config.js",
    "lint-staged.config.js",
    ".lintstagedrc",
    ".husky",
    ".changeset",
    "biome.json",
    "deno.json",
    "bun.lockb",
}

ROOT_WHITELIST_PATTERNS = [
    ".env",
    ".npmrc",
    ".nvmrc",
    ".node-version",
    ".python-version",
    ".tool-versions",
]

CLUTTER_CATEGORIES = [
    ({".md"}, "docs/archive", "documentation/reports"),
    ({".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico"}, "docs/screenshots", "screenshots/images"),
    ({".sh", ".ps1", ".bash"}, "scripts", "shell scripts"),
    ({".bak", ".orig", ".old"}, None, "backup files (suggest delete)"),
    ({".log"}, "logs", "log files"),
    ({".sql"}, "scripts/db", "SQL scripts"),
    ({".html"}, "docs/reports", "HTML reports"),
]


def _is_whitelisted(filename: str) -> bool:
    lower = filename.lower()
    if lower in ROOT_WHITELIST_EXACT:
        return True
    for pattern in ROOT_WHITELIST_PATTERNS:
        if lower.startswith(pattern):
            return True
    if filename.startswith("."):
        return True
    return False


def _categorize_file(filename: str) -> tuple[str | None, str]:
    suffix = Path(filename).suffix.lower()
    for extensions, target_dir, description in CLUTTER_CATEGORIES:
        if suffix in extensions:
            return target_dir, description
    return "docs/archive", "uncategorized"


def check_clutter(project_dir: str) -> dict:
    """Scan root directory for files that violate structure rules."""
    root = Path(project_dir)
    root_files = sorted(f for f in root.iterdir() if f.is_file() and not f.name.startswith("CLAUDE"))

    clutter: list[dict] = []
    whitelisted: list[str] = []
    deletable: list[dict] = []

    for f in root_files:
        name = f.name
        if _is_whitelisted(name):
            whitelisted.append(name)
            continue

        target_dir, category = _categorize_file(name)
        if target_dir is None:
            deletable.append({"file": name, "category": category})
        else:
            clutter.append(
                {
                    "file": name,
                    "target": f"{target_dir}/{name}",
                    "category": category,
                }
            )

    moves_by_dir: dict[str, list[str]] = {}
    for item in clutter:
        target = item["target"].rsplit("/", 1)[0]
        if target not in moves_by_dir:
            moves_by_dir[target] = []
        moves_by_dir[target].append(item["file"])

    return {
        "status": "clean" if not clutter and not deletable else "cluttered",
        "root_file_count": len(root_files),
        "whitelisted_count": len(whitelisted),
        "clutter_count": len(clutter),
        "deletable_count": len(deletable),
        "moves": clutter,
        "moves_by_dir": moves_by_dir,
        "deletable": deletable,
        "summary": (
            f"{len(clutter)} files to move, {len(deletable)} to delete"
            if clutter or deletable
            else "Root directory is clean"
        ),
    }


# ---------------------------------------------------------------------------
# classify_brainstorm
# ---------------------------------------------------------------------------


def classify_brainstorm(directive: str, project_signals: dict) -> dict:
    """Deterministic brainstorm weight classification.

    Codifies the 4-row weight table:
    - directive (3+ words) + has content → lightweight
    - directive (3+ words) + empty project → standard
    - no directive + has content → lightweight
    - no directive + empty project → full
    """
    has_directive = len(directive.split()) >= 3
    if project_signals is None:
        project_signals = {}
    has_content = (
        project_signals.get("has_readme", False)
        or project_signals.get("has_code_files", False)
        or project_signals.get("has_package_json", False)
        or project_signals.get("has_pyproject", False)
        or project_signals.get("has_cargo_toml", False)
        or project_signals.get("has_go_mod", False)
    )

    if has_directive and has_content:
        weight = "lightweight"
    elif has_directive and not has_content:
        weight = "standard"
    elif not has_directive and has_content:
        weight = "lightweight"
    else:
        weight = "full"

    return {
        "weight": weight,
        "has_directive": has_directive,
        "has_content": has_content,
    }


# ---------------------------------------------------------------------------
# hook_activate
# ---------------------------------------------------------------------------


def hook_activate(project_dir: str, soul_purpose: str) -> dict:
    """Write lifecycle state to session-context/.lifecycle-active.json.

    Project-scoped (not global ~/.claude/) to prevent cross-project
    contamination. The stop hook reads this file to warn on exit.
    """
    sd = session_dir(project_dir)
    if not sd.is_dir():
        return {"status": "error", "message": "session-context/ does not exist"}

    state = {
        "active": True,
        "soul_purpose": soul_purpose,
        "activated_at": datetime.now(timezone.utc).isoformat(),
        "project_dir": project_dir,
    }

    state_file = sd / LIFECYCLE_STATE_FILENAME
    state_file.write_text(json.dumps(state, indent=2))

    return {"status": "ok", "file": str(state_file)}


# ---------------------------------------------------------------------------
# hook_deactivate
# ---------------------------------------------------------------------------


def hook_deactivate(project_dir: str) -> dict:
    """Remove lifecycle state file. Idempotent."""
    sd = session_dir(project_dir)
    state_file = sd / LIFECYCLE_STATE_FILENAME
    was_active = state_file.is_file()

    if was_active:
        state_file.unlink()

    return {"status": "ok", "was_active": was_active}


# ---------------------------------------------------------------------------
# features_read
# ---------------------------------------------------------------------------


def features_read(project_dir: str) -> dict:
    """Parse CLAUDE-features.md into structured claims by status.

    Expected format: markdown with checkbox items.
    - [x] Feature name — verified
    - [ ] Feature name — pending
    - [!] Feature name — failed (convention)
    """
    sd = session_dir(project_dir)
    features_file = sd / "CLAUDE-features.md"

    if not features_file.is_file():
        return {"exists": False, "claims": [], "counts": {}, "total": 0}

    content = features_file.read_text()
    claims: list[dict] = []

    for line in content.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue

        if "[x]" in stripped.lower():
            status = "verified"
            text = stripped.split("]", 1)[1].strip().lstrip("- ")
        elif "[!]" in stripped:
            status = "failed"
            text = stripped.split("]", 1)[1].strip().lstrip("- ")
        elif "[ ]" in stripped:
            status = "pending"
            text = stripped.split("]", 1)[1].strip().lstrip("- ")
        else:
            continue

        claims.append({"text": text, "status": status})

    counts = {
        "verified": sum(1 for c in claims if c["status"] == "verified"),
        "pending": sum(1 for c in claims if c["status"] == "pending"),
        "failed": sum(1 for c in claims if c["status"] == "failed"),
    }

    return {
        "exists": True,
        "claims": claims,
        "counts": counts,
        "total": len(claims),
    }


# ---------------------------------------------------------------------------
# git_summary
# ---------------------------------------------------------------------------


def git_summary(project_dir: str) -> dict:
    """Raw git data: recent commits, changed files, branch, ahead/behind.

    Returns deterministic data only — no staleness judgment. The AI
    compares this against read_context output to decide what to update.
    """
    result: dict = {
        "is_git": False,
        "branch": "",
        "commits": [],
        "files_changed": [],
        "ahead": 0,
        "behind": 0,
    }

    def _run(args: list[str]) -> str | None:
        try:
            proc = subprocess.run(
                args,
                capture_output=True,
                text=True,
                cwd=project_dir,
                timeout=10,
            )
            return proc.stdout.strip() if proc.returncode == 0 else None
        except (subprocess.SubprocessError, FileNotFoundError):
            return None

    # Check if git repo
    if _run(["git", "rev-parse", "--git-dir"]) is None:
        return result
    result["is_git"] = True

    # Current branch
    branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    if branch:
        result["branch"] = branch

    # Recent commits (last 10)
    log_output = _run(
        [
            "git",
            "log",
            "--oneline",
            "--no-decorate",
            "-10",
        ]
    )
    if log_output:
        result["commits"] = [
            {"hash": line.split(" ", 1)[0], "message": line.split(" ", 1)[1] if " " in line else ""}
            for line in log_output.split("\n")
            if line.strip()
        ]

    # Changed files (staged + unstaged + untracked)
    status_output = _run(["git", "status", "--porcelain"])
    if status_output:
        result["files_changed"] = [
            {"status": line[:2].strip(), "file": line[3:]} for line in status_output.split("\n") if line.strip()
        ]

    # Ahead/behind tracking branch
    tracking = _run(
        [
            "git",
            "rev-list",
            "--left-right",
            "--count",
            "HEAD...@{upstream}",
        ]
    )
    if tracking and "\t" in tracking:
        parts = tracking.split("\t")
        result["ahead"] = int(parts[0])
        result["behind"] = int(parts[1])

    return result


# ---------------------------------------------------------------------------
# capability_inventory
# ---------------------------------------------------------------------------


def _get_git_head(project_dir: str) -> str | None:
    """Get current git HEAD commit hash.

    Returns:
        Commit hash as string, or None if not a git repo or command fails.
    """
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=project_dir,
            timeout=10,
        )
        if proc.returncode == 0:
            return proc.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass
    return None


def _get_capability_cache_path(project_dir: str) -> Path:
    """Get path to capability cache file.

    Returns:
        Path object for session-context/.capability-cache.json
    """
    return session_dir(project_dir) / CAPABILITY_CACHE_FILENAME


def _load_capability_cache(project_dir: str) -> dict | None:
    """Load capability cache from disk.

    Returns:
        Cached data dict, or None if file doesn't exist or invalid JSON.
    """
    cache_path = _get_capability_cache_path(project_dir)
    if not cache_path.is_file():
        return None

    try:
        content = cache_path.read_text()
        return json.loads(content)
    except (json.JSONDecodeError, OSError):
        return None


def _save_capability_cache(project_dir: str, data: dict) -> None:
    """Save capability cache to disk.

    Args:
        project_dir: Project directory path
        data: Cache data to write as indented JSON
    """
    cache_path = _get_capability_cache_path(project_dir)
    cache_path.parent.mkdir(exist_ok=True)
    cache_path.write_text(json.dumps(data, indent=2))


def capability_inventory(project_dir: str, force_refresh: bool = False) -> dict:
    """Manage capability inventory cache with git-aware invalidation.

    The cache stores metadata about the capability inventory file and is
    invalidated when the git HEAD changes, ensuring freshness after commits.

    Args:
        project_dir: Project directory path
        force_refresh: If True, bypass cache and force regeneration

    Returns:
        Dict with:
            - status: "ok"
            - cache_hit: bool (True if cache was valid and used)
            - is_git: bool (True if project is a git repo)
            - git_head: str | None (current commit hash)
            - git_changed: bool (True if HEAD changed since cache)
            - inventory_file: str (relative path to inventory file)
            - needs_generation: bool (True if inventory should be regenerated)
    """
    git_head = _get_git_head(project_dir)
    is_git = git_head is not None

    # Load existing cache if in git repo
    cache = _load_capability_cache(project_dir) if is_git else None

    cache_hit = False
    git_changed = False
    cached_head = None

    if cache:
        cached_head = cache.get("git_head")
        cache_hit = cached_head == git_head and not force_refresh
        git_changed = cached_head != git_head

    # Save new cache entry if not hitting or forcing refresh (git repos only)
    if is_git and (not cache_hit or force_refresh):
        cache_data = {
            "git_head": git_head,
            "cached_at": datetime.now(timezone.utc).isoformat(),
        }
        _save_capability_cache(project_dir, cache_data)

    # Relative path from session-context
    inventory_file = f"session-context/{CAPABILITY_INVENTORY_FILENAME}"

    return {
        "status": "ok",
        "cache_hit": cache_hit,
        "is_git": is_git,
        "git_head": git_head,
        "git_changed": git_changed,
        "inventory_file": inventory_file,
        "needs_generation": not cache_hit or force_refresh,
    }


# ---------------------------------------------------------------------------
# refresh_claude_md (approximates /init behavior)
# ---------------------------------------------------------------------------


def refresh_claude_md(project_dir: str) -> dict:
    """Approximate Claude Code's /init command behavior.

    Analyzes the codebase and generates/upates CLAUDE.md with:
    - Project Overview (name, goal, stack from package manifests)
    - Project Structure (directories and key files)
    - Development Commands (from package.json scripts, Makefile, etc.)
    - Preserves existing governance sections (Structure Maintenance, Session Context, etc.)

    This is an approximation — the real /init should be run periodically
    to calibrate. This tool bridges the gap for automated workflows.

    Returns:
        dict with status, generated_content, governance_preserved, etc.
    """
    root = _resolve_project_dir(project_dir)
    cmd_path = root / "CLAUDE.md"

    # Step 1: Detect project signals
    root_files = [f for f in root.iterdir() if f.is_file()]
    signals = _detect_project_signals(root, root_files)

    # Step 2: Extract existing governance sections if CLAUDE.md exists
    existing_governance = {}
    if cmd_path.is_file():
        content = cmd_path.read_text()
        for section in GOVERNANCE_SECTIONS:
            found = find_section(content, section)
            if found:
                existing_governance[section] = found

    # Step 3: Build CLAUDE.md content
    lines = []
    lines.append("# CLAUDE.md")
    lines.append("")
    lines.append("This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.")
    lines.append("")

    # Project Overview
    lines.append("## Project Overview")
    lines.append("")

    project_name = signals.get("package_name") or root.name
    project_goal = signals.get("package_description") or "[Primary objective]"
    detected_stack = signals.get("detected_stack", [])

    lines.append(f"**Project**: {project_name}")
    lines.append(f"**Goal**: {project_goal}")
    lines.append(f"**Stack**: {', '.join(detected_stack) if detected_stack else '[Technologies / platforms]'}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Project Structure
    lines.append("## Project Structure")
    lines.append("")

    # Analyze directory structure
    dirs = sorted([d for d in root.iterdir() if d.is_dir() and not d.name.startswith(".")])
    files = sorted([f for f in root.iterdir() if f.is_file() and not f.name.startswith(".")])

    if dirs:
        lines.append("### Directories")
        for d in dirs:
            lines.append(f"- `{d.name}/` - [Description]")
        lines.append("")

    if files:
        lines.append("### Root Files")
        for f in files:
            lines.append(f"- `{f.name}` - {f.suffix.upper() if f.suffix else 'file'}")
        lines.append("")

    # Development Commands
    lines.append("## Development Commands")
    lines.append("")

    # Extract from package.json scripts
    if signals.get("has_package_json"):
        pkg_path = root / "package.json"
        try:
            pkg_data = json.loads(pkg_path.read_text(errors="replace"))
            scripts = pkg_data.get("scripts", {})
            if scripts:
                for name, cmd in scripts.items():
                    lines.append(f"### {name}")
                    lines.append(f"```bash")
                    lines.append(f"{cmd}")
                    lines.append(f"```")
                    lines.append("")
        except Exception:
            pass

    # Check for Makefile
    makefile = root / "Makefile"
    if makefile.is_file():
        lines.append("### Makefile targets")
        try:
            make_content = makefile.read_text(errors="replace")
            # Extract targets (lines ending with :)
            for line in make_content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and line.endswith(":"):
                    target = line[:-1]
                    if not target.startswith("."):
                        lines.append(f"- `make {target}`")
            lines.append("")
        except Exception:
            pass

    lines.append("---")
    lines.append("")

    # Step 4: Append preserved governance sections
    for section_name in GOVERNANCE_SECTIONS:
        if section_name in existing_governance:
            lines.append(f"## {section_name}")
            lines.append("")
            lines.append(existing_governance[section_name])
            lines.append("")
            lines.append("---")
            lines.append("")

    # Add meta footer
    lines.append("")
    lines.append(f"<!-- Generated by atlas-session MCP tool at {datetime.now(timezone.utc).isoformat()} -->")
    lines.append(f"<!-- Last real /init: [not recorded] -->")
    lines.append("")
    lines.append("**Note**: This file was auto-generated by the atlas-session MCP server as an approximation of Claude Code's `/init` command.")
    lines.append("For best results, run `/init` periodically to calibrate this approximation.")

    generated_content = "\n".join(lines)

    # Step 5: Write to CLAUDE.md
    try:
        cmd_path.write_text(generated_content)
        return {
            "status": "ok",
            "claude_md_updated": True,
            "path": str(cmd_path),
            "governance_sections_preserved": list(existing_governance.keys()),
            "project_detected": {
                "name": project_name,
                "stack": detected_stack,
                "has_package_json": signals.get("has_package_json", False),
                "has_pyproject": signals.get("has_pyproject", False),
            },
            "lines_written": len(generated_content.split("\n")),
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "claude_md_updated": False,
        }


# ---------------------------------------------------------------------------
# Composite operations — reduce MCP round-trips by combining granular ops
# ---------------------------------------------------------------------------


def start_composite(project_dir: str, directive: str = "") -> dict:
    """Composite session start: preflight + validate + read_context +
    git_summary + classify_brainstorm + conditional check_clutter.

    Combines the 5-6 MCP calls that always run together at session start
    into a single round-trip. Each sub-operation is independently guarded
    so a failure in one does not block the others.

    Args:
        project_dir: Project directory path.
        directive: Optional directive text for brainstorm classification.

    Returns:
        Dict with keys: preflight, validate, read_context, git_summary,
        classify_brainstorm, clutter (None if root_file_count <= 15).
    """
    result: dict = {
        "preflight": None,
        "validate": None,
        "read_context": None,
        "git_summary": None,
        "classify_brainstorm": None,
        "clutter": None,
    }

    # 1. Preflight — needed to determine mode and root_file_count
    try:
        result["preflight"] = preflight(project_dir)
    except Exception as e:
        result["preflight"] = {"status": "error", "error": str(e)}

    # 2. Validate
    try:
        result["validate"] = validate(project_dir)
    except Exception as e:
        result["validate"] = {"status": "error", "error": str(e)}

    # 3. Read context
    try:
        result["read_context"] = read_context(project_dir)
    except Exception as e:
        result["read_context"] = {"status": "error", "error": str(e)}

    # 4. Git summary
    try:
        result["git_summary"] = git_summary(project_dir)
    except Exception as e:
        result["git_summary"] = {"status": "error", "error": str(e)}

    # 5. Classify brainstorm — needs project_signals from preflight
    try:
        project_signals = {}
        if isinstance(result["preflight"], dict) and "project_signals" in result["preflight"]:
            project_signals = result["preflight"]["project_signals"]
        result["classify_brainstorm"] = classify_brainstorm(directive, project_signals)
    except Exception as e:
        result["classify_brainstorm"] = {"status": "error", "error": str(e)}

    # 6. Check clutter — only if root_file_count > 15
    try:
        root_file_count = 0
        if isinstance(result["preflight"], dict):
            root_file_count = result["preflight"].get("root_file_count", 0)
        if root_file_count > 15:
            result["clutter"] = check_clutter(project_dir)
    except Exception as e:
        result["clutter"] = {"status": "error", "error": str(e)}

    return result


def activate_composite(
    project_dir: str,
    soul_purpose: str,
    old_purpose: str = "(pending)",
) -> dict:
    """Composite session activation: archive + hook_activate + features_read.

    Combines the 3 MCP calls that always run together when activating a
    soul purpose into a single round-trip. Each sub-operation is
    independently guarded for partial failure resilience.

    Args:
        project_dir: Project directory path.
        soul_purpose: The soul purpose to activate.
        old_purpose: Previous purpose to archive (default: "(pending)").

    Returns:
        Dict with keys: archive, hook, features.
    """
    result: dict = {
        "archive": None,
        "hook": None,
        "features": None,
    }

    # 1. Archive — set soul purpose (archives old, sets new)
    try:
        result["archive"] = archive(project_dir, old_purpose, soul_purpose)
    except Exception as e:
        result["archive"] = {"status": "error", "error": str(e)}

    # 2. Hook activate — enable stop hook warnings
    try:
        result["hook"] = hook_activate(project_dir, soul_purpose)
    except Exception as e:
        result["hook"] = {"status": "error", "error": str(e)}

    # 3. Features read — extract feature claims for tracking
    try:
        result["features"] = features_read(project_dir)
    except Exception as e:
        result["features"] = {"status": "error", "error": str(e)}

    return result


def close_composite(project_dir: str) -> dict:
    """Composite session close: harvest + features_read + hook_deactivate.

    Combines the 3 MCP calls that always run together during session
    settlement into a single round-trip. Each sub-operation is
    independently guarded for partial failure resilience.

    Args:
        project_dir: Project directory path.

    Returns:
        Dict with keys: harvest, features, hook.
    """
    result: dict = {
        "harvest": None,
        "features": None,
        "hook": None,
    }

    # 1. Harvest — scan for promotable content
    try:
        result["harvest"] = harvest(project_dir)
    except Exception as e:
        result["harvest"] = {"status": "error", "error": str(e)}

    # 2. Features read — check feature claim status
    try:
        result["features"] = features_read(project_dir)
    except Exception as e:
        result["features"] = {"status": "error", "error": str(e)}

    # 3. Hook deactivate — remove lifecycle state file
    try:
        result["hook"] = hook_deactivate(project_dir)
    except Exception as e:
        result["hook"] = {"status": "error", "error": str(e)}

    return result
