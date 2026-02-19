"""Unit tests for atlas_session.session.operations — all 15 session functions.

Covers Tasks 2, 3, 4 of the test plan:
  Task 2: preflight, init, validate (19 tests)
  Task 3: read_context, harvest, archive (12 tests)
  Task 4: governance, clutter, brainstorm, hooks, features, git (22 tests)
"""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


from atlas_session.session.operations import (
    archive,
    cache_governance,
    capability_inventory,
    check_clutter,
    classify_brainstorm,
    ensure_governance,
    features_read,
    git_summary,
    harvest,
    hook_activate,
    hook_deactivate,
    init,
    preflight,
    read_context,
    restore_governance,
    validate,
)
from atlas_session.common.config import (
    GOVERNANCE_CACHE_PATH,
    LIFECYCLE_STATE_FILENAME,
    SESSION_FILES,
)


# =========================================================================
# Task 2 — preflight, init, validate
# =========================================================================


class TestPreflight:
    """Tests for the preflight() function."""

    def test_mode_init_when_no_session_dir(self, project_dir):
        """Mode is 'init' when session-context/ does not exist."""
        result = preflight(str(project_dir))
        assert result["mode"] == "init"

    def test_mode_reconcile_when_session_dir_exists(self, project_with_session):
        """Mode is 'reconcile' when session-context/ exists."""
        result = preflight(str(project_with_session))
        assert result["mode"] == "reconcile"

    def test_git_detected_in_git_repo(self, project_with_git):
        """is_git is True when project is a git repository."""
        result = preflight(str(project_with_git))
        assert result["is_git"] is True

    def test_git_not_detected_in_plain_dir(self, project_dir):
        """is_git is False when project is not a git repository."""
        result = preflight(str(project_dir))
        assert result["is_git"] is False

    def test_root_file_count_excludes_claude_files(self, project_dir):
        """root_file_count excludes files starting with CLAUDE."""
        (project_dir / "CLAUDE.md").write_text("# test")
        (project_dir / "README.md").write_text("# readme")
        (project_dir / "setup.py").write_text("")
        result = preflight(str(project_dir))
        assert result["root_file_count"] == 2  # README.md + setup.py

    def test_has_claude_md_when_present(self, project_with_claude_md):
        """has_claude_md is True when CLAUDE.md exists."""
        result = preflight(str(project_with_claude_md))
        assert result["has_claude_md"] is True

    def test_has_claude_md_when_absent(self, project_dir):
        """has_claude_md is False when CLAUDE.md does not exist."""
        result = preflight(str(project_dir))
        assert result["has_claude_md"] is False

    def test_templates_valid(self):
        """templates_valid is True when all required templates exist."""
        result = preflight(str(Path("/tmp")))
        # TEMPLATE_DIR points to our project's templates/ which has all 6 files
        assert result["templates_valid"] is True
        assert result["template_count"] == 6

    def test_project_signals_readme(self, project_dir):
        """Detects README.md in project signals."""
        (project_dir / "README.md").write_text(
            "# My Project\n\nA description of things.\n"
        )
        result = preflight(str(project_dir))
        assert result["project_signals"]["has_readme"] is True
        assert "A description of things." in result["project_signals"]["readme_excerpt"]

    def test_project_signals_package_json(self, project_dir):
        """Detects package.json and extracts name/description."""
        (project_dir / "package.json").write_text(
            json.dumps({"name": "my-app", "description": "A cool app"})
        )
        result = preflight(str(project_dir))
        signals = result["project_signals"]
        assert signals["has_package_json"] is True
        assert signals["package_name"] == "my-app"
        assert signals["package_description"] == "A cool app"
        assert "node" in signals["detected_stack"]

    def test_project_signals_python_files(self, project_dir):
        """Detects Python files in root."""
        (project_dir / "app.py").write_text("print('hello')")
        result = preflight(str(project_dir))
        signals = result["project_signals"]
        assert signals["has_code_files"] is True
        assert "python" in signals["detected_stack"]

    def test_project_signals_pyproject(self, project_dir):
        """Detects pyproject.toml."""
        (project_dir / "pyproject.toml").write_text("[project]\nname='test'\n")
        result = preflight(str(project_dir))
        assert result["project_signals"]["has_pyproject"] is True
        assert "python" in result["project_signals"]["detected_stack"]

    def test_project_signals_empty_project(self, project_dir):
        """Detects empty project when no code, no manifests, few files."""
        result = preflight(str(project_dir))
        assert result["project_signals"]["is_empty_project"] is True

    def test_session_file_health_in_reconcile(self, project_with_session):
        """session_files dict populated in reconcile mode."""
        result = preflight(str(project_with_session))
        assert result["mode"] == "reconcile"
        assert len(result["session_files"]) == len(SESSION_FILES)
        for f in SESSION_FILES:
            assert f in result["session_files"]
            assert result["session_files"][f]["exists"] is True

    def test_session_files_empty_in_init_mode(self, project_dir):
        """session_files dict is empty in init mode."""
        result = preflight(str(project_dir))
        assert result["mode"] == "init"
        assert result["session_files"] == {}


class TestInit:
    """Tests for the init() function."""

    def test_creates_session_dir(self, project_dir):
        """init() creates the session-context/ directory."""
        result = init(str(project_dir), "Build something great")
        assert result["status"] == "ok"
        assert (project_dir / "session-context").is_dir()

    def test_creates_all_five_files(self, project_dir):
        """init() creates all 5 session files."""
        result = init(str(project_dir), "Build something great")
        assert result["files_created"] == 5
        assert result["expected"] == 5
        for f in SESSION_FILES:
            assert (project_dir / "session-context" / f).is_file()

    def test_sets_soul_purpose(self, project_dir):
        """init() writes the soul purpose to CLAUDE-soul-purpose.md."""
        init(str(project_dir), "Build a REST API")
        sp = (project_dir / "session-context" / "CLAUDE-soul-purpose.md").read_text()
        assert "Build a REST API" in sp

    def test_seeds_active_context(self, project_dir):
        """init() seeds active context with purpose, date, and status."""
        init(str(project_dir), "Build a REST API", ralph_mode="Manual")
        ac = (project_dir / "session-context" / "CLAUDE-activeContext.md").read_text()
        assert "Build a REST API" in ac
        assert "Initialized" in ac
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        assert today in ac

    def test_idempotent_on_rerun(self, project_dir):
        """Running init() twice succeeds and overwrites cleanly."""
        result1 = init(str(project_dir), "First purpose")
        result2 = init(str(project_dir), "Second purpose")
        assert result1["status"] == "ok"
        assert result2["status"] == "ok"
        sp = (project_dir / "session-context" / "CLAUDE-soul-purpose.md").read_text()
        assert "Second purpose" in sp
        assert "First purpose" not in sp

    def test_ralph_config_stored(self, project_dir):
        """init() stores ralph mode and intensity in active context."""
        init(
            str(project_dir),
            "Test purpose",
            ralph_mode="automatic",
            ralph_intensity="long",
        )
        ac = (project_dir / "session-context" / "CLAUDE-activeContext.md").read_text()
        assert "automatic" in ac
        assert "long" in ac

    def test_ralph_default_intensity_na(self, project_dir):
        """init() defaults ralph intensity to N/A when empty."""
        init(str(project_dir), "Test purpose", ralph_mode="Manual")
        ac = (project_dir / "session-context" / "CLAUDE-activeContext.md").read_text()
        assert "N/A" in ac


class TestValidate:
    """Tests for the validate() function."""

    def test_all_ok_when_complete(self, project_with_session):
        """All files in 'ok' when session-context is complete."""
        result = validate(str(project_with_session))
        assert result["status"] == "ok"
        assert len(result["ok"]) == 5
        assert result["repaired"] == []
        assert result["failed"] == []

    def test_repairs_missing_file(self, project_with_session):
        """Repairs a single missing file from templates."""
        (project_with_session / "session-context" / "CLAUDE-decisions.md").unlink()
        result = validate(str(project_with_session))
        assert result["status"] == "ok"
        assert "CLAUDE-decisions.md" in result["repaired"]
        assert (
            project_with_session / "session-context" / "CLAUDE-decisions.md"
        ).is_file()

    def test_repairs_multiple_missing(self, project_with_session):
        """Repairs multiple missing files."""
        (project_with_session / "session-context" / "CLAUDE-decisions.md").unlink()
        (project_with_session / "session-context" / "CLAUDE-patterns.md").unlink()
        result = validate(str(project_with_session))
        assert result["status"] == "ok"
        assert "CLAUDE-decisions.md" in result["repaired"]
        assert "CLAUDE-patterns.md" in result["repaired"]
        assert len(result["repaired"]) == 2

    def test_leaves_existing_alone(self, project_with_soul_purpose):
        """Existing files with content are not overwritten."""
        sp_before = (
            project_with_soul_purpose / "session-context" / "CLAUDE-soul-purpose.md"
        ).read_text()
        result = validate(str(project_with_soul_purpose))
        sp_after = (
            project_with_soul_purpose / "session-context" / "CLAUDE-soul-purpose.md"
        ).read_text()
        assert sp_before == sp_after
        assert "CLAUDE-soul-purpose.md" in result["ok"]

    def test_error_when_no_session_dir(self, project_dir):
        """Returns error when session-context/ does not exist."""
        result = validate(str(project_dir))
        assert result["status"] == "error"
        assert "does not exist" in result["message"]

    def test_repairs_empty_file(self, project_with_session):
        """Repairs a file that exists but is empty (0 bytes)."""
        (project_with_session / "session-context" / "CLAUDE-patterns.md").write_text("")
        result = validate(str(project_with_session))
        assert "CLAUDE-patterns.md" in result["repaired"]


# =========================================================================
# Task 3 — read_context, harvest, archive
# =========================================================================


class TestReadContext:
    """Tests for the read_context() function."""

    def test_reads_soul_purpose(self, project_with_soul_purpose):
        """Reads the active soul purpose text."""
        result = read_context(str(project_with_soul_purpose))
        assert result["soul_purpose"] == "Build a widget factory"

    def test_status_hint_no_purpose(self, project_with_session):
        """status_hint is 'no_purpose' when soul purpose is template default."""
        result = read_context(str(project_with_session))
        # Template has no non-comment, non-heading, non-separator content
        assert result["soul_purpose"] == ""
        assert result["status_hint"] == "no_purpose"

    def test_detects_open_tasks(self, project_with_soul_purpose):
        """Detects items with [ ] as open tasks."""
        result = read_context(str(project_with_soul_purpose))
        assert len(result["open_tasks"]) == 2
        # The tasks have "[ ]" in them and are stripped of "- "
        assert any("Implement widget builder" in t for t in result["open_tasks"])
        assert any("Add widget tests" in t for t in result["open_tasks"])

    def test_detects_completed_tasks(self, project_with_soul_purpose):
        """Detects items with [x] as recent progress."""
        result = read_context(str(project_with_soul_purpose))
        assert len(result["recent_progress"]) >= 1
        assert any("Set up project structure" in t for t in result["recent_progress"])

    def test_active_context_summary(self, project_with_soul_purpose):
        """Returns first 60 lines of active context as summary."""
        result = read_context(str(project_with_soul_purpose))
        assert "Active Context" in result["active_context_summary"]
        assert (
            "Widget factory" in result["active_context_summary"]
            or "widget factory" in result["active_context_summary"].lower()
        )

    def test_ralph_config_default(self, project_with_session):
        """Ralph config defaults to empty strings when no CLAUDE.md."""
        result = read_context(str(project_with_session))
        assert result["ralph_mode"] == ""
        assert result["ralph_intensity"] == ""

    def test_ralph_config_from_claude_md(self, project_with_claude_md):
        """Reads ralph mode and intensity from CLAUDE.md."""
        # project_with_claude_md has Ralph Loop section with Mode: Manual
        result = read_context(str(project_with_claude_md))
        assert result["ralph_mode"] == "manual"

    def test_has_archived_purposes_false(self, project_with_soul_purpose):
        """has_archived_purposes is False when no [CLOSED] entries."""
        result = read_context(str(project_with_soul_purpose))
        assert result["has_archived_purposes"] is False

    def test_has_archived_purposes_true(self, project_with_soul_purpose):
        """has_archived_purposes is True when [CLOSED] entries exist."""
        sp_file = (
            project_with_soul_purpose / "session-context" / "CLAUDE-soul-purpose.md"
        )
        sp_file.write_text(
            "# Soul Purpose\n\n"
            "Current purpose\n\n"
            "---\n\n"
            "## [CLOSED] --- 2026-02-17\n\n"
            "Old purpose\n"
        )
        result = read_context(str(project_with_soul_purpose))
        assert result["has_archived_purposes"] is True
        # Purpose reading stops at [CLOSED] line
        assert result["soul_purpose"] == "Current purpose"


class TestHarvest:
    """Tests for the harvest() function."""

    def test_returns_harvestable_content(self, project_with_soul_purpose):
        """Returns has_content when active context has real content."""
        result = harvest(str(project_with_soul_purpose))
        assert result["status"] == "has_content"
        assert "active_context" in result
        assert "target_files" in result
        assert "decisions" in result["target_files"]
        assert "patterns" in result["target_files"]
        assert "troubleshooting" in result["target_files"]

    def test_empty_when_template_state(self, project_with_session):
        """Returns 'nothing' when active context is still the template."""
        result = harvest(str(project_with_session))
        assert result["status"] == "nothing"

    def test_empty_when_no_active_context(self, project_dir):
        """Returns 'nothing' when active context file doesn't exist."""
        # Create session dir but no active context
        (project_dir / "session-context").mkdir()
        result = harvest(str(project_dir))
        assert result["status"] == "nothing"

    def test_empty_when_content_too_short(self, project_with_session):
        """Returns 'nothing' when active context has less than 100 chars."""
        ac = project_with_session / "session-context" / "CLAUDE-activeContext.md"
        ac.write_text("# Active Context\n\nShort note.\n")
        result = harvest(str(project_with_session))
        assert result["status"] == "nothing"


class TestArchive:
    """Tests for the archive() function."""

    def test_archives_old_purpose_with_closed(self, project_with_soul_purpose):
        """Archived purposes get [CLOSED] marker with date."""
        result = archive(
            str(project_with_soul_purpose), "Build a widget factory", "New project"
        )
        assert result["status"] == "ok"
        sp = (
            project_with_soul_purpose / "session-context" / "CLAUDE-soul-purpose.md"
        ).read_text()
        assert "[CLOSED]" in sp
        assert "Build a widget factory" in sp

    def test_sets_new_purpose(self, project_with_soul_purpose):
        """New purpose is written at the top of the file."""
        archive(
            str(project_with_soul_purpose), "Build a widget factory", "New purpose here"
        )
        sp = (
            project_with_soul_purpose / "session-context" / "CLAUDE-soul-purpose.md"
        ).read_text()
        assert "New purpose here" in sp
        # New purpose should be before the [CLOSED] marker
        new_pos = sp.index("New purpose here")
        closed_pos = sp.index("[CLOSED]")
        assert new_pos < closed_pos

    def test_resets_active_context(self, project_with_soul_purpose):
        """Active context is reset to template after archive."""
        result = archive(
            str(project_with_soul_purpose), "Build a widget factory", "New purpose"
        )
        assert result["active_context_reset"] is True
        ac = (
            project_with_soul_purpose / "session-context" / "CLAUDE-activeContext.md"
        ).read_text()
        # Should be reset to template (contains placeholder text)
        assert "[DATE]" in ac or "Active Context" in ac

    def test_archive_without_new_purpose(self, project_with_soul_purpose):
        """Archives with '(No active soul purpose)' when new_purpose is empty."""
        result = archive(str(project_with_soul_purpose), "Build a widget factory")
        assert result["new_purpose"] == "(No active soul purpose)"
        sp = (
            project_with_soul_purpose / "session-context" / "CLAUDE-soul-purpose.md"
        ).read_text()
        assert "(No active soul purpose)" in sp

    def test_archive_return_values(self, project_with_soul_purpose):
        """Verify return dict keys and values."""
        result = archive(
            str(project_with_soul_purpose), "Build a widget factory", "New thing"
        )
        assert result["archived_purpose"] == "Build a widget factory"
        assert result["new_purpose"] == "New thing"
        assert result["active_context_reset"] is True

    def test_archive_truncates_long_purpose(self, project_with_soul_purpose):
        """Purposes longer than 80 chars are truncated in return value."""
        long_purpose = "A" * 100
        result = archive(str(project_with_soul_purpose), long_purpose, "New")
        assert result["archived_purpose"].endswith("...")
        assert len(result["archived_purpose"]) == 83  # 80 + "..."

    def test_archive_error_when_no_file(self, project_dir):
        """Returns error when soul purpose file doesn't exist."""
        (project_dir / "session-context").mkdir()
        result = archive(str(project_dir), "old", "new")
        assert result["status"] == "error"


# =========================================================================
# Task 4 — governance, clutter, brainstorm, hooks, features, git
# =========================================================================


class TestCacheGovernance:
    """Tests for the cache_governance() function."""

    def test_caches_sections(self, project_with_claude_md):
        """Caches governance sections from CLAUDE.md."""
        result = cache_governance(str(project_with_claude_md))
        assert result["status"] == "ok"
        assert len(result["cached_sections"]) > 0
        assert GOVERNANCE_CACHE_PATH.is_file()
        cached = json.loads(GOVERNANCE_CACHE_PATH.read_text())
        # project_with_claude_md has all 4 governance sections
        assert "Structure Maintenance Rules" in cached or len(cached) > 0

    def test_error_when_no_claude_md(self, project_dir):
        """Returns error when CLAUDE.md does not exist."""
        result = cache_governance(str(project_dir))
        assert result["status"] == "error"
        assert "not found" in result["message"]

    def test_reports_missing_sections(self, project_with_session):
        """Reports sections that are missing from CLAUDE.md."""
        # Create a minimal CLAUDE.md with no governance sections
        (project_with_session / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\nMinimal file.\n"
        )
        result = cache_governance(str(project_with_session))
        assert result["status"] == "ok"
        assert len(result["missing_sections"]) > 0


class TestRestoreGovernance:
    """Tests for the restore_governance() function."""

    def test_round_trips_sections(self, project_with_claude_md):
        """Cache then restore preserves governance sections."""
        # First cache
        cache_governance(str(project_with_claude_md))

        # Wipe the CLAUDE.md to just a header
        (project_with_claude_md / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\nStripped file.\n"
        )

        # Restore
        result = restore_governance(str(project_with_claude_md))
        assert result["status"] == "ok"
        assert len(result["restored"]) > 0

        # Verify content was restored
        content = (project_with_claude_md / "CLAUDE.md").read_text()
        assert (
            "Structure Maintenance Rules" in content
            or "Session Context Files" in content
        )

    def test_handles_no_cache(self, project_with_claude_md):
        """Returns error when no governance cache exists."""
        # Ensure no cache file
        GOVERNANCE_CACHE_PATH.unlink(missing_ok=True)
        result = restore_governance(str(project_with_claude_md))
        assert result["status"] == "error"
        assert "No governance cache" in result["message"]

    def test_already_present_sections_not_duplicated(self, project_with_claude_md):
        """Sections already present in CLAUDE.md are not re-added."""
        cache_governance(str(project_with_claude_md))
        # Restore without wiping — sections still present
        result = restore_governance(str(project_with_claude_md))
        assert result["status"] == "ok"
        assert len(result["already_present"]) > 0


class TestEnsureGovernance:
    """Tests for the ensure_governance() function."""

    def test_adds_missing_sections(self, project_with_session):
        """Adds governance sections to a CLAUDE.md missing them."""
        (project_with_session / "CLAUDE.md").write_text("# CLAUDE.md\n\nBasic file.\n")
        result = ensure_governance(str(project_with_session))
        assert result["status"] == "ok"
        assert len(result["added"]) > 0
        content = (project_with_session / "CLAUDE.md").read_text()
        assert "Structure Maintenance Rules" in content

    def test_skips_existing_sections(self, project_with_claude_md):
        """Does not duplicate sections that already exist."""
        result = ensure_governance(str(project_with_claude_md))
        assert result["status"] == "ok"
        assert len(result["already_present"]) > 0
        # All 4 governance sections already present in project_with_claude_md
        assert len(result["added"]) == 0

    def test_includes_ralph_config(self, project_with_session):
        """Ralph config values are interpolated into the Ralph Loop section."""
        (project_with_session / "CLAUDE.md").write_text("# CLAUDE.md\n\nBasic file.\n")
        ensure_governance(
            str(project_with_session), ralph_mode="automatic", ralph_intensity="long"
        )
        content = (project_with_session / "CLAUDE.md").read_text()
        assert "automatic" in content
        assert "long" in content

    def test_creates_claude_md_if_missing(self, project_dir):
        """Creates CLAUDE.md from scratch if it doesn't exist."""
        result = ensure_governance(str(project_dir))
        assert result["status"] == "ok"
        assert (project_dir / "CLAUDE.md").is_file()


class TestCheckClutter:
    """Tests for the check_clutter() function."""

    def test_clean_root(self, project_dir):
        """Reports clean when root has only whitelisted files."""
        (project_dir / "package.json").write_text("{}")
        (project_dir / "README.md").write_text("# Hi")
        (project_dir / ".gitignore").write_text("node_modules/")
        result = check_clutter(str(project_dir))
        assert result["status"] == "clean"
        assert result["clutter_count"] == 0

    def test_detects_cluttered_root(self, project_dir):
        """Detects non-whitelisted files as clutter."""
        (project_dir / "notes.md").write_text("# Notes")
        (project_dir / "screenshot.png").write_text("fake image")
        (project_dir / "deploy.sh").write_text("#!/bin/bash")
        result = check_clutter(str(project_dir))
        assert result["status"] == "cluttered"
        assert result["clutter_count"] >= 3
        # Each clutter item should have file, target, category
        for item in result["moves"]:
            assert "file" in item
            assert "target" in item
            assert "category" in item

    def test_whitelisted_files_ignored(self, project_dir):
        """Whitelisted files (package.json, .gitignore, etc.) are not clutter."""
        (project_dir / "package.json").write_text("{}")
        (project_dir / "tsconfig.json").write_text("{}")
        (project_dir / ".gitignore").write_text("")
        (project_dir / ".env").write_text("SECRET=x")
        result = check_clutter(str(project_dir))
        assert result["status"] == "clean"
        assert result["whitelisted_count"] == 4

    def test_backup_files_flagged_for_deletion(self, project_dir):
        """Backup files (.bak, .orig) are suggested for deletion."""
        (project_dir / "config.bak").write_text("old config")
        result = check_clutter(str(project_dir))
        assert result["status"] == "cluttered"
        assert result["deletable_count"] == 1
        assert result["deletable"][0]["file"] == "config.bak"

    def test_claude_prefixed_files_excluded_from_count(self, project_dir):
        """Files starting with CLAUDE are excluded from root_file_count."""
        (project_dir / "CLAUDE.md").write_text("# test")
        (project_dir / "CLAUDE-special.md").write_text("# test")
        result = check_clutter(str(project_dir))
        assert result["root_file_count"] == 0


class TestClassifyBrainstorm:
    """Tests for the classify_brainstorm() function."""

    def test_lightweight_directive_and_content(self):
        """directive + has_content = lightweight."""
        signals = {"has_readme": True, "has_code_files": True}
        result = classify_brainstorm("Build a REST API server", signals)
        assert result["weight"] == "lightweight"
        assert result["has_directive"] is True
        assert result["has_content"] is True

    def test_standard_directive_and_empty(self):
        """directive + empty project = standard."""
        signals = {"has_readme": False, "has_code_files": False}
        result = classify_brainstorm("Build a REST API server", signals)
        assert result["weight"] == "standard"
        assert result["has_directive"] is True
        assert result["has_content"] is False

    def test_lightweight_no_directive_and_content(self):
        """no directive + has_content = lightweight."""
        signals = {"has_readme": True}
        result = classify_brainstorm("hi", signals)  # less than 3 words
        assert result["weight"] == "lightweight"
        assert result["has_directive"] is False
        assert result["has_content"] is True

    def test_full_no_directive_and_empty(self):
        """no directive + empty project = full."""
        signals = {}
        result = classify_brainstorm("go", signals)  # 1 word
        assert result["weight"] == "full"
        assert result["has_directive"] is False
        assert result["has_content"] is False

    def test_directive_threshold_exactly_three_words(self):
        """Exactly 3 words counts as a directive."""
        signals = {}
        result = classify_brainstorm("build the thing", signals)
        assert result["has_directive"] is True

    def test_directive_threshold_two_words(self):
        """Two words does not count as a directive."""
        signals = {}
        result = classify_brainstorm("build thing", signals)
        assert result["has_directive"] is False

    def test_content_detection_package_json(self):
        """has_package_json counts as content."""
        signals = {"has_package_json": True}
        result = classify_brainstorm("do", signals)
        assert result["has_content"] is True

    def test_content_detection_pyproject(self):
        """has_pyproject counts as content."""
        signals = {"has_pyproject": True}
        result = classify_brainstorm("do", signals)
        assert result["has_content"] is True


class TestHookActivate:
    """Tests for the hook_activate() function."""

    def test_creates_lifecycle_file(self, project_with_session):
        """Creates .lifecycle-active.json in session-context/."""
        result = hook_activate(str(project_with_session), "Build widgets")
        assert result["status"] == "ok"
        state_file = project_with_session / "session-context" / LIFECYCLE_STATE_FILENAME
        assert state_file.is_file()

    def test_file_contains_purpose(self, project_with_session):
        """Lifecycle state file contains the soul purpose."""
        hook_activate(str(project_with_session), "Build widgets")
        state_file = project_with_session / "session-context" / LIFECYCLE_STATE_FILENAME
        state = json.loads(state_file.read_text())
        assert state["soul_purpose"] == "Build widgets"
        assert state["active"] is True
        assert "activated_at" in state
        assert "project_dir" in state

    def test_error_when_no_session_dir(self, project_dir):
        """Returns error when session-context/ does not exist."""
        result = hook_activate(str(project_dir), "Build widgets")
        assert result["status"] == "error"


class TestHookDeactivate:
    """Tests for the hook_deactivate() function."""

    def test_removes_file(self, project_with_session):
        """Removes the lifecycle state file."""
        hook_activate(str(project_with_session), "Build widgets")
        result = hook_deactivate(str(project_with_session))
        assert result["status"] == "ok"
        assert result["was_active"] is True
        state_file = project_with_session / "session-context" / LIFECYCLE_STATE_FILENAME
        assert not state_file.is_file()

    def test_idempotent_when_no_file(self, project_with_session):
        """Returns ok even when no lifecycle file exists."""
        result = hook_deactivate(str(project_with_session))
        assert result["status"] == "ok"
        assert result["was_active"] is False


class TestFeaturesRead:
    """Tests for the features_read() function."""

    def test_no_features_file(self, project_with_session):
        """Returns exists=False when CLAUDE-features.md doesn't exist."""
        result = features_read(str(project_with_session))
        assert result["exists"] is False
        assert result["claims"] == []
        assert result["total"] == 0

    def test_parses_feature_claims(self, project_with_session):
        """Parses feature claims by status from markdown checkboxes."""
        features_file = project_with_session / "session-context" / "CLAUDE-features.md"
        features_file.write_text(
            "# Feature Claims\n\n"
            "- [x] Authentication system works\n"
            "- [ ] Dashboard renders correctly\n"
            "- [!] Email notifications send\n"
            "- [x] API endpoints respond\n"
        )
        result = features_read(str(project_with_session))
        assert result["exists"] is True
        assert result["total"] == 4
        assert result["counts"]["verified"] == 2
        assert result["counts"]["pending"] == 1
        assert result["counts"]["failed"] == 1
        # Check individual claim texts
        texts = [c["text"] for c in result["claims"]]
        assert "Authentication system works" in texts
        assert "Dashboard renders correctly" in texts
        assert "Email notifications send" in texts

    def test_ignores_non_checkbox_lines(self, project_with_session):
        """Lines without checkbox markers are ignored."""
        features_file = project_with_session / "session-context" / "CLAUDE-features.md"
        features_file.write_text(
            "# Feature Claims\n\n"
            "Some intro text\n"
            "- Regular bullet point\n"
            "- [x] Real feature claim\n"
        )
        result = features_read(str(project_with_session))
        assert result["total"] == 1


class TestGitSummary:
    """Tests for the git_summary() function."""

    def test_returns_branch(self, project_with_git):
        """Returns the current branch name."""
        result = git_summary(str(project_with_git))
        assert result["is_git"] is True
        # git init on modern git defaults to 'master' or 'main'
        assert result["branch"] in ("main", "master")

    def test_returns_commits(self, project_with_git):
        """Returns recent commit history."""
        result = git_summary(str(project_with_git))
        assert len(result["commits"]) >= 1
        assert result["commits"][0]["message"] == "initial"
        assert "hash" in result["commits"][0]

    def test_non_git_directory(self, project_dir):
        """Returns is_git=False for non-git directories."""
        result = git_summary(str(project_dir))
        assert result["is_git"] is False
        assert result["branch"] == ""
        assert result["commits"] == []
        assert result["files_changed"] == []

    def test_detects_changed_files(self, project_with_git):
        """Detects unstaged/untracked file changes."""
        (project_with_git / "new_file.txt").write_text("hello")
        result = git_summary(str(project_with_git))
        assert len(result["files_changed"]) >= 1
        files = [f["file"] for f in result["files_changed"]]
        assert "new_file.txt" in files


# =========================================================================
# Edge Cases — coverage gap tests
# =========================================================================


class TestEdgeCases:
    """Edge cases and error branches for coverage gaps."""

    def test_read_context_literal_no_active_soul_purpose(self, project_with_session):
        """read_context with literal '(No active soul purpose)' returns status_hint='no_purpose'."""
        sp_file = project_with_session / "session-context" / "CLAUDE-soul-purpose.md"
        sp_file.write_text("# Soul Purpose\n\n(No active soul purpose)\n")
        result = read_context(str(project_with_session))
        assert result["soul_purpose"] == ""
        assert result["status_hint"] == "no_purpose"

    def test_archive_with_multiple_closed_entries(self, project_with_session):
        """archive preserves existing [CLOSED] entries when archiving again."""
        sp_file = project_with_session / "session-context" / "CLAUDE-soul-purpose.md"
        # Set up a file with two existing [CLOSED] entries
        sp_file.write_text(
            "# Soul Purpose\n\n"
            "Current active purpose\n\n"
            "---\n\n"
            "## [CLOSED] \u2014 2026-02-15\n\n"
            "Second old purpose\n\n"
            "## [CLOSED] \u2014 2026-02-10\n\n"
            "First old purpose\n"
        )
        result = archive(
            str(project_with_session), "Current active purpose", "Brand new purpose"
        )
        assert result["status"] == "ok"

        content = sp_file.read_text()
        # New purpose at top
        assert "Brand new purpose" in content
        # The newly archived purpose should be present
        assert "Current active purpose" in content
        # Both old [CLOSED] entries should still be present
        assert "2026-02-15" in content
        assert "Second old purpose" in content
        assert "2026-02-10" in content
        assert "First old purpose" in content
        # Count [CLOSED] markers — should be at least 3 (newly archived + 2 old)
        closed_count = content.count("[CLOSED]")
        assert closed_count >= 3

    def test_check_clutter_uncategorized_extensions(self, project_dir):
        """Files with unusual extensions (.xyz, .dat) go to 'docs/archive'."""
        (project_dir / "data.xyz").write_text("xyz content")
        (project_dir / "report.dat").write_text("dat content")
        result = check_clutter(str(project_dir))
        assert result["status"] == "cluttered"
        assert result["clutter_count"] >= 2
        # Verify they are categorized as uncategorized -> docs/archive
        for item in result["moves"]:
            if item["file"] in ("data.xyz", "report.dat"):
                assert item["target"].startswith("docs/archive/")
                assert item["category"] == "uncategorized"

    def test_git_summary_no_tracking_branch(self, project_with_session):
        """git_summary with no remote tracking branch returns ahead=0 and behind=0."""
        proj = project_with_session
        subprocess.run(["git", "init"], cwd=proj, capture_output=True)
        subprocess.run(
            ["git", "config", "user.email", "test@test.com"],
            cwd=proj,
            capture_output=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test"], cwd=proj, capture_output=True
        )
        (proj / "file.txt").write_text("hello")
        subprocess.run(["git", "add", "."], cwd=proj, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=proj, capture_output=True)
        # No remote set, so HEAD...@{upstream} will fail
        result = git_summary(str(proj))
        assert result["is_git"] is True
        assert result["ahead"] == 0
        assert result["behind"] == 0

    def test_preflight_with_large_unusual_readme(self, project_dir):
        """preflight handles README with only headings, no content lines."""
        # README with only headings and empty lines — readme_excerpt should be empty
        (project_dir / "README.md").write_text(
            "# Title\n\n## Section One\n\n## Section Two\n\n### Subsection\n"
        )
        result = preflight(str(project_dir))
        signals = result["project_signals"]
        assert signals["has_readme"] is True
        # All non-blank lines start with # so content_lines should be empty
        assert signals["readme_excerpt"] == ""


# =========================================================================
# Hostile Tests — try to break session operations
# =========================================================================


class TestInitHostile:
    """Hostile inputs that try to break init()."""

    def test_init_with_empty_string_purpose(self, project_dir):
        """init('') creates files but with a blank soul purpose.

        The code does not validate that soul_purpose is non-empty;
        it writes whatever string is provided.
        """
        result = init(str(project_dir), "")
        assert result["status"] == "ok"
        sp = (project_dir / "session-context" / "CLAUDE-soul-purpose.md").read_text()
        # The soul purpose file has the heading and an empty body
        assert sp == "# Soul Purpose\n\n\n"
        ac = (project_dir / "session-context" / "CLAUDE-activeContext.md").read_text()
        assert "**Current Goal**: " in ac

    def test_init_unicode_purpose(self, project_dir):
        """Unicode soul purpose (CJK + emoji) round-trips through init correctly."""
        purpose = "\u6784\u5efa\u5c0f\u90e8\u4ef6\u5de5\u5382 \U0001f3ed"
        result = init(str(project_dir), purpose)
        assert result["status"] == "ok"
        sp = (project_dir / "session-context" / "CLAUDE-soul-purpose.md").read_text()
        assert purpose in sp
        ac = (project_dir / "session-context" / "CLAUDE-activeContext.md").read_text()
        assert purpose in ac


class TestPreflightHostile:
    """Hostile filesystem states that try to break preflight()."""

    def test_preflight_with_broken_symlinks_in_root(self, project_dir):
        """Broken symlinks in project root do not crash iterdir().

        is_file() returns False for broken symlinks, so they are excluded
        from root_file_count and don't appear in project_signals.
        """
        import os

        os.symlink("/nonexistent/target", str(project_dir / "broken_link.txt"))
        os.symlink("/also/nonexistent", str(project_dir / "another_broken.py"))
        result = preflight(str(project_dir))
        # Broken symlinks are not counted as files
        assert result["root_file_count"] == 0
        assert result["project_signals"]["is_empty_project"] is True


class TestReadContextHostile:
    """Hostile file content that tries to break read_context()."""

    def test_read_context_when_active_context_is_binary_garbage(
        self, project_with_session
    ):
        """Binary garbage in CLAUDE-activeContext.md is handled gracefully.

        read_context uses errors='replace' so invalid UTF-8 bytes are
        replaced with U+FFFD instead of crashing.
        """
        ac_file = project_with_session / "session-context" / "CLAUDE-activeContext.md"
        ac_file.write_bytes(b"\x80\x81\x82\xfe\xff\x00binary garbage\xff\xfe")
        result = read_context(str(project_with_session))
        # Should not crash, should return a result with replacement chars
        assert isinstance(result, dict)
        assert "active_context_summary" in result


class TestArchiveHostile:
    """Hostile input that tries to break archive()."""

    def test_archive_duplicate_text_does_not_corrupt(self, project_with_session):
        """Archive with purpose text that appears before [CLOSED] marker.

        The old bug used existing.index(line) which could match a duplicate
        string at the wrong position, corrupting the archive.
        """
        sp_file = project_with_session / "session-context" / "CLAUDE-soul-purpose.md"
        # Set up: purpose text "Build widgets" also appears in an old closed entry
        sp_file.write_text(
            "# Soul Purpose\n\n"
            "Build widgets\n\n"
            "---\n\n"
            "## [CLOSED] \u2014 2026-02-10\n\n"
            "Build widgets\n"
        )
        result = archive(str(project_with_session), "Build widgets", "New purpose")
        assert result["status"] == "ok"
        content = sp_file.read_text()
        # New purpose at top
        assert "New purpose" in content
        # Old [CLOSED] entry preserved (not corrupted)
        assert "2026-02-10" in content
        # Should have exactly 2 [CLOSED] markers (new archive + old one)
        assert content.count("[CLOSED]") == 2

    def test_archive_when_purpose_contains_markdown_syntax(self, project_with_session):
        """Purpose containing ## and [CLOSED] does not corrupt the archive.

        The archive function writes the old purpose in a [CLOSED] block,
        then checks for existing [CLOSED] entries. If the purpose text
        itself contains '[CLOSED]', the code's string search may
        inadvertently match and duplicate content.
        """
        sp_file = project_with_session / "session-context" / "CLAUDE-soul-purpose.md"
        sp_file.write_text("# Soul Purpose\n\nBuild ## widgets [CLOSED] --- stuff\n")

        result = archive(
            str(project_with_session),
            "Build ## widgets [CLOSED] --- stuff",
            "Clean new purpose",
        )
        assert result["status"] == "ok"

        content = sp_file.read_text()
        # The new purpose should be at the top
        assert content.startswith("# Soul Purpose\n\nClean new purpose\n")
        # The old purpose should appear in a [CLOSED] block
        assert "Build ## widgets [CLOSED] --- stuff" in content


class TestHarvestHostile:
    """Boundary tests for harvest()."""

    def test_harvest_when_active_context_exactly_100_chars(self, project_with_session):
        """Active context with exactly 100 stripped chars passes the threshold.

        The check is `len(ac_content.strip()) < 100` — at 100, it's NOT < 100,
        so harvest returns 'has_content'.
        """
        ac_file = project_with_session / "session-context" / "CLAUDE-activeContext.md"
        # Create content that is exactly 100 chars after strip()
        content = "A" * 100
        assert len(content.strip()) == 100
        ac_file.write_text(content)
        result = harvest(str(project_with_session))
        assert result["status"] == "has_content"

    def test_harvest_when_active_context_99_chars(self, project_with_session):
        """Active context with 99 stripped chars is below threshold.

        len(99) < 100 is True, so harvest returns 'nothing'.
        """
        ac_file = project_with_session / "session-context" / "CLAUDE-activeContext.md"
        content = "A" * 99
        ac_file.write_text(content)
        result = harvest(str(project_with_session))
        assert result["status"] == "nothing"


class TestHookActivateHostile:
    """Concurrency test for hook_activate()."""

    def test_hook_activate_overwrites_on_second_call(self, project_with_session):
        """Two rapid hook_activate calls: second overwrites the first.

        No locking mechanism exists. The second write wins.
        """
        result1 = hook_activate(str(project_with_session), "First purpose")
        assert result1["status"] == "ok"

        state_file = project_with_session / "session-context" / LIFECYCLE_STATE_FILENAME
        state1 = json.loads(state_file.read_text())
        assert state1["soul_purpose"] == "First purpose"

        result2 = hook_activate(str(project_with_session), "Second purpose")
        assert result2["status"] == "ok"

        state2 = json.loads(state_file.read_text())
        assert state2["soul_purpose"] == "Second purpose"
        # First purpose is gone — overwritten, not merged
        assert "First purpose" not in state_file.read_text()


class TestClassifyBrainstormHostile:
    """Hostile inputs for classify_brainstorm()."""

    def test_classify_brainstorm_none_signals_handled(self):
        """Passing None as project_signals is handled gracefully.

        The function treats None signals as empty dict.
        """
        result = classify_brainstorm("Build a thing now", None)
        assert result["weight"] == "standard"  # directive + no content
        assert result["has_directive"] is True
        assert result["has_content"] is False

    def test_classify_brainstorm_empty_dict_signals(self):
        """Empty dict signals (no keys at all) returns 'full' weight."""
        result = classify_brainstorm("go", {})
        assert result["weight"] == "full"
        assert result["has_content"] is False


class TestCheckClutterHostile:
    """Hostile filesystem states for check_clutter()."""

    def test_check_clutter_hidden_dotfiles_are_whitelisted(self, project_dir):
        """Hidden files (starting with .) are always whitelisted.

        _is_whitelisted() returns True for any filename starting with '.',
        but only files (not directories) are considered by check_clutter
        since iterdir() filters with is_file().
        """
        (project_dir / ".hidden_config").write_text("secret=value")
        (project_dir / ".another_hidden").write_text("data")
        result = check_clutter(str(project_dir))
        assert result["status"] == "clean"
        assert result["whitelisted_count"] == 2
        assert result["clutter_count"] == 0


class TestFeaturesReadHostile:
    """Hostile input for features_read()."""

    def test_features_read_uppercase_X_checkbox(self, project_with_session):
        """[X] (uppercase) is counted as verified because the code lowercases.

        The code does `'[x]' in stripped.lower()` which matches both [x] and [X].
        """
        features_file = project_with_session / "session-context" / "CLAUDE-features.md"
        features_file.write_text(
            "# Features\n\n"
            "- [X] Feature with uppercase X\n"
            "- [x] Feature with lowercase x\n"
            "- [ ] Pending feature\n"
        )
        result = features_read(str(project_with_session))
        assert result["total"] == 3
        assert result["counts"]["verified"] == 2  # Both [X] and [x]
        assert result["counts"]["pending"] == 1


# =========================================================================
# capability_inventory — cache operations for capability inventory
# =========================================================================


class TestCapabilityInventory:
    """Tests for the capability_inventory() function."""

    def test_capability_inventory_creates_cache_on_first_run(self, project_with_git):
        """First call should create cache file."""
        import subprocess

        cache_file = project_with_git / "session-context" / ".capability-cache.json"

        # Ensure cache doesn't exist initially
        cache_file.unlink(missing_ok=True)

        result = capability_inventory(str(project_with_git))

        assert result["status"] == "ok"
        assert result["is_git"] is True
        assert result["git_head"] is not None
        assert result["cache_hit"] is False
        assert result["needs_generation"] is True
        assert cache_file.is_file()

        # Verify cache contents
        cache = json.loads(cache_file.read_text())
        assert "git_head" in cache
        assert cache["git_head"] == result["git_head"]
        assert "cached_at" in cache

    def test_capability_inventory_returns_cache_on_subsequent_calls(
        self, project_with_git
    ):
        """Same git HEAD = cache hit."""
        import subprocess

        result1 = capability_inventory(str(project_with_git))
        first_head = result1["git_head"]

        # Second call with same git HEAD should hit cache
        result2 = capability_inventory(str(project_with_git))

        assert result2["status"] == "ok"
        assert result2["is_git"] is True
        assert result2["git_head"] == first_head
        assert result2["cache_hit"] is True
        assert result2["git_changed"] is False
        assert result2["needs_generation"] is False
        assert result2["inventory_file"] == "session-context/CLAUDE-capability-inventory.md"

    def test_capability_inventory_invalidates_on_git_change(self, project_with_git):
        """Different HEAD = regenerate."""
        import subprocess

        # First call
        result1 = capability_inventory(str(project_with_git))
        first_head = result1["git_head"]

        # Make a new commit to change HEAD
        (project_with_git / "newfile.txt").write_text("content")
        subprocess.run(["git", "add", "."], cwd=project_with_git, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "new commit"],
            cwd=project_with_git,
            capture_output=True,
        )

        # Second call should detect git change
        result2 = capability_inventory(str(project_with_git))

        assert result2["status"] == "ok"
        assert result2["is_git"] is True
        assert result2["git_head"] != first_head
        assert result2["cache_hit"] is False
        assert result2["git_changed"] is True
        assert result2["needs_generation"] is True

    def test_capability_inventory_handles_non_git(self, project_with_session):
        """Non-git projects always regenerate."""
        result = capability_inventory(str(project_with_session))

        assert result["status"] == "ok"
        assert result["is_git"] is False
        assert result["git_head"] is None
        assert result["cache_hit"] is False
        assert result["git_changed"] is False
        assert result["needs_generation"] is True
        assert result["inventory_file"] == "session-context/CLAUDE-capability-inventory.md"

        # No cache file should be created for non-git projects
        cache_file = project_with_session / "session-context" / ".capability-cache.json"
        assert not cache_file.is_file()

    def test_capability_inventory_force_refresh(self, project_with_git):
        """force_refresh=True bypasses cache."""
        import subprocess

        # First call to create cache
        result1 = capability_inventory(str(project_with_git))
        assert result1["cache_hit"] is False

        # Second call without force_refresh should hit cache
        result2 = capability_inventory(str(project_with_git), force_refresh=False)
        assert result2["cache_hit"] is True
        assert result2["needs_generation"] is False

        # Third call with force_refresh should bypass cache
        result3 = capability_inventory(str(project_with_git), force_refresh=True)
        assert result3["cache_hit"] is False
        assert result3["needs_generation"] is True
        assert result3["git_changed"] is False  # git didn't change, just forced refresh
