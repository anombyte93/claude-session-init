"""Configuration from environment variables and defaults."""

import os
import tempfile
from pathlib import Path

# Template resolution: plugin bundled templates > home dir fallback
_pkg_root = Path(__file__).resolve().parent.parent.parent.parent  # up to plugin root
_plugin_templates = _pkg_root / "templates"
_home_templates = Path.home() / "claude-session-init-templates"

TEMPLATE_DIR = _plugin_templates if _plugin_templates.is_dir() else _home_templates

SESSION_DIR_NAME = "session-context"
CLAUDE_MD_NAME = "CLAUDE.md"
# SECURITY: Use secure tempfile with random name to prevent symlink attacks
_governance_cache = tempfile.NamedTemporaryFile(
    mode="w",
    prefix="claude-governance-",
    suffix=".json",
    delete=False,
)
_governance_cache.close()
GOVERNANCE_CACHE_PATH = Path(_governance_cache.name)
LIFECYCLE_STATE_FILENAME = ".lifecycle-active.json"

ATLASCOIN_URL = os.environ.get("ATLASCOIN_URL", "http://localhost:3000")

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
