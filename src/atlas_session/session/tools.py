"""Session lifecycle MCP tool definitions.

Each tool wraps an operation from operations.py, exposing it as a
FastMCP tool with typed parameters and structured JSON output.
"""

from fastmcp import FastMCP

from . import operations as ops


def register(mcp: FastMCP) -> None:
    """Register all session tools on the given server."""

    @mcp.tool
    def session_preflight(project_dir: str) -> dict:
        """Detect environment: mode (init/reconcile), git status, project
        signals, template validity, session file health. Call this first
        to determine which workflow to follow."""
        return ops.preflight(project_dir)

    @mcp.tool
    def session_init(
        project_dir: str,
        soul_purpose: str,
        ralph_mode: str = "Manual",
        ralph_intensity: str = "",
    ) -> dict:
        """Bootstrap session-context/ with templates, soul purpose, and
        active context. Creates the session-context directory and seeds
        all required files."""
        return ops.init(project_dir, soul_purpose, ralph_mode, ralph_intensity)

    @mcp.tool
    def session_validate(project_dir: str) -> dict:
        """Validate session-context files exist and have content.
        Repairs missing files from templates automatically."""
        return ops.validate(project_dir)

    @mcp.tool
    def session_read_context(project_dir: str) -> dict:
        """Read soul purpose, active context summary, open/completed tasks,
        Ralph config, and status hint. Primary tool for understanding
        current session state."""
        return ops.read_context(project_dir)

    @mcp.tool
    def session_harvest(project_dir: str) -> dict:
        """Scan active context for content worth promoting to decisions,
        patterns, or troubleshooting files. Returns raw content for AI
        judgment on what qualifies."""
        return ops.harvest(project_dir)

    @mcp.tool
    def session_archive(
        project_dir: str,
        old_purpose: str,
        new_purpose: str = "",
    ) -> dict:
        """Archive current soul purpose with [CLOSED] marker and optionally
        set a new one. Resets active context from template."""
        return ops.archive(project_dir, old_purpose, new_purpose)

    @mcp.tool
    def session_check_clutter(project_dir: str) -> dict:
        """Scan project root for misplaced files. Returns categorized
        move map (docs, scripts, images) and deletable backup files."""
        return ops.check_clutter(project_dir)

    @mcp.tool
    def session_cache_governance(project_dir: str) -> dict:
        """Cache governance sections from CLAUDE.md to /tmp before
        running /init (which may overwrite CLAUDE.md)."""
        return ops.cache_governance(project_dir)

    @mcp.tool
    def session_restore_governance(project_dir: str) -> dict:
        """Restore cached governance sections to CLAUDE.md after /init.
        Must call session_cache_governance first."""
        return ops.restore_governance(project_dir)

    @mcp.tool
    def session_ensure_governance(
        project_dir: str,
        ralph_mode: str = "Manual",
        ralph_intensity: str = "",
    ) -> dict:
        """Ensure all required governance sections exist in CLAUDE.md.
        Adds missing Structure Maintenance, Session Context, Template,
        and Ralph Loop sections."""
        return ops.ensure_governance(project_dir, ralph_mode, ralph_intensity)

    @mcp.tool
    def session_classify_brainstorm(
        directive: str,
        project_signals: dict,
    ) -> dict:
        """Deterministic brainstorm weight classification. Returns
        lightweight/standard/full based on directive presence and
        project content signals from preflight."""
        return ops.classify_brainstorm(directive, project_signals)

    @mcp.tool
    def session_hook_activate(
        project_dir: str,
        soul_purpose: str,
    ) -> dict:
        """Write lifecycle state to session-context/.lifecycle-active.json.
        Project-scoped file used by stop hook to warn on unclean exit."""
        return ops.hook_activate(project_dir, soul_purpose)

    @mcp.tool
    def session_hook_deactivate(project_dir: str) -> dict:
        """Remove lifecycle state file. Idempotent. Call during
        settlement or session close."""
        return ops.hook_deactivate(project_dir)

    @mcp.tool
    def session_features_read(project_dir: str) -> dict:
        """Parse CLAUDE-features.md into structured claims by status
        (verified/pending/failed). Returns {exists, claims[], counts, total}."""
        return ops.features_read(project_dir)

    @mcp.tool
    def session_git_summary(project_dir: str) -> dict:
        """Raw git data: recent commits, changed files, branch, ahead/behind.
        Deterministic — no comparison or judgment. AI compares against
        read_context to detect stale context."""
        return ops.git_summary(project_dir)
