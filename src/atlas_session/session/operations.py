"""Core session lifecycle operations.

Extracted from session-init.py — all logic preserved, adapted to be
called as functions (not CLI subcommands) returning dicts instead of
printing JSON.
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
            capture_output=True, check=True, cwd=project_dir,
        )
        result["is_git"] = True
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass

    # Root file count
    root_files = [
        f for f in root.iterdir()
        if f.is_file() and not f.name.startswith("CLAUDE")
    ]
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
            content_lines = [
                ln.strip() for ln in lines
                if ln.strip() and not ln.strip().startswith("#")
            ][:3]
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
    }

    # Read soul purpose
    sp_file = sd / "CLAUDE-soul-purpose.md"
    if sp_file.is_file():
        sp_content = sp_file.read_text()
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

        if "(No active soul purpose)" in sp_content or not result["soul_purpose"]:
            result["soul_purpose"] = ""
            result["status_hint"] = "no_purpose"

    # Read active context (first 60 lines)
    ac_file = sd / "CLAUDE-activeContext.md"
    if ac_file.is_file():
        ac_content = ac_file.read_text()
        ac_lines = ac_content.split("\n")[:60]
        result["active_context_summary"] = "\n".join(ac_lines)

        for line in ac_content.split("\n"):
            stripped = line.strip()
            if "[ ]" in stripped:
                result["open_tasks"].append(stripped.lstrip("- "))
            elif "[x]" in stripped.lower():
                result["recent_progress"].append(stripped.lstrip("- "))

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
# harvest
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
        for line in existing.split("\n"):
            if "[CLOSED]" in line:
                idx = existing.index(line)
                old_archives = existing[idx:]
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
    "claude.md", "readme.md", "license", "license.md", "cname",
    "package.json", "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "tsconfig.json", "jsconfig.json", "next.config.js", "next.config.mjs",
    "next.config.ts", "next-env.d.ts", "vercel.json", "netlify.toml",
    "middleware.ts", "middleware.js", "instrumentation.ts",
    "tailwind.config.js", "tailwind.config.ts", "tailwind.config.mjs",
    "postcss.config.js", "postcss.config.mjs", "postcss.config.cjs",
    "eslint.config.js", "eslint.config.mjs", ".eslintrc.js", ".eslintrc.json",
    ".prettierrc", ".prettierrc.json", ".prettierrc.js",
    "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".dockerignore", ".gitignore", ".gitattributes", ".editorconfig",
    "makefile", "rakefile", "gemfile", "gemfile.lock",
    "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "cargo.toml", "cargo.lock", "go.mod", "go.sum",
    "sanity.config.ts", "sanity.config.js", "sanity.cli.ts", "sanity.cli.js",
    "drizzle.config.ts", "drizzle.config.js",
    "vitest.config.ts", "vitest.config.js", "jest.config.ts", "jest.config.js",
    "playwright.config.ts", "playwright.config.js",
    "index.html", "robots.txt", "sitemap.xml",
    "components.json",
    "railway.toml", "fly.toml", "render.yaml", "app.yaml",
    "turbo.json", "nx.json", "lerna.json", "pnpm-workspace.yaml",
    "vitest.setup.ts", "vitest.setup.js", "jest.setup.ts", "jest.setup.js",
    "tsconfig.tsbuildinfo",
    "commitlint.config.js", "lint-staged.config.js", ".lintstagedrc",
    ".husky", ".changeset",
    "biome.json", "deno.json", "bun.lockb",
}

ROOT_WHITELIST_PATTERNS = [
    ".env", ".npmrc", ".nvmrc", ".node-version",
    ".python-version", ".tool-versions",
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
    root_files = sorted(
        f for f in root.iterdir()
        if f.is_file() and not f.name.startswith("CLAUDE")
    )

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
            clutter.append({
                "file": name,
                "target": f"{target_dir}/{name}",
                "category": category,
            })

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
                args, capture_output=True, text=True, cwd=project_dir,
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
    log_output = _run([
        "git", "log", "--oneline", "--no-decorate", "-10",
    ])
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
            {"status": line[:2].strip(), "file": line[3:]}
            for line in status_output.split("\n")
            if line.strip()
        ]

    # Ahead/behind tracking branch
    tracking = _run([
        "git", "rev-list", "--left-right", "--count", "HEAD...@{upstream}",
    ])
    if tracking and "\t" in tracking:
        parts = tracking.split("\t")
        result["ahead"] = int(parts[0])
        result["behind"] = int(parts[1])

    return result
