"""Shared test fixtures for Atlas Session Lifecycle."""

import json
import shutil
from pathlib import Path

import pytest


@pytest.fixture
def project_dir(tmp_path):
    """Create an isolated project directory with no session-context."""
    return tmp_path


@pytest.fixture
def project_with_session(tmp_path):
    """Create an isolated project with bootstrapped session-context/."""
    templates_dir = Path(__file__).parent.parent / "templates"
    session_dir = tmp_path / "session-context"
    session_dir.mkdir()

    for template in templates_dir.glob("CLAUDE-*.md"):
        dest = session_dir / template.name
        shutil.copy(template, dest)

    return tmp_path


@pytest.fixture
def project_with_soul_purpose(project_with_session):
    """Project with session-context AND an active soul purpose."""
    sp_file = project_with_session / "session-context" / "CLAUDE-soul-purpose.md"
    sp_file.write_text("# Soul Purpose\n\nBuild a widget factory\n")

    ac_file = project_with_session / "session-context" / "CLAUDE-activeContext.md"
    ac_file.write_text(
        "# Active Context\n\n"
        "**Last Updated**: 2026-02-18\n"
        "**Current Goal**: Build a widget factory\n\n"
        "## Current Session\n"
        "- **Started**: 2026-02-18\n"
        "- **Focus**: Widget factory implementation\n"
        "- **Status**: In Progress\n\n"
        "## Progress\n"
        "- [x] Set up project structure\n"
        "- [ ] Implement widget builder\n"
        "- [ ] Add widget tests\n\n"
        "## Notes\n"
        "Working on core logic.\n\n"
        "## Next Session\n"
        "Continue widget builder implementation.\n"
    )
    return project_with_session


@pytest.fixture
def project_with_git(project_with_session):
    """Project with session-context AND a git repo."""
    import subprocess

    subprocess.run(["git", "init"], cwd=project_with_session, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=project_with_session,
        capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=project_with_session,
        capture_output=True,
    )
    (project_with_session / "README.md").write_text("# Test Project\n")
    subprocess.run(["git", "add", "."], cwd=project_with_session, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "initial"],
        cwd=project_with_session,
        capture_output=True,
    )
    return project_with_session


@pytest.fixture
def project_with_claude_md(project_with_session):
    """Project with session-context AND a CLAUDE.md."""
    claude_md = project_with_session / "CLAUDE.md"
    claude_md.write_text(
        "# CLAUDE.md\n\n"
        "## Structure Maintenance Rules\n\n"
        "Keep files organized.\n\n"
        "## Session Context Files\n\n"
        "Maintain session-context/ files.\n\n"
        "## IMMUTABLE TEMPLATE RULES\n\n"
        "Never edit templates.\n\n"
        "## Ralph Loop\n\n"
        "**Mode**: Manual\n"
        "**Intensity**: \n"
    )
    return project_with_session


@pytest.fixture
def sample_contract_dict():
    """A valid contract dictionary for testing."""
    return {
        "soul_purpose": "Build a widget factory",
        "escrow": 100,
        "criteria": [
            {
                "name": "tests_pass",
                "type": "shell",
                "command": "echo ok",
                "pass_when": "exit_code == 0",
                "weight": 2.0,
            },
            {
                "name": "session_context_exists",
                "type": "file_exists",
                "path": "session-context/CLAUDE-activeContext.md",
                "pass_when": "not_empty",
                "weight": 0.5,
            },
        ],
        "bounty_id": "",
        "status": "draft",
    }


@pytest.fixture
def project_with_contract(project_with_session, sample_contract_dict):
    """Project with session-context AND a saved contract.json."""
    contract_path = project_with_session / "session-context" / "contract.json"
    contract_path.write_text(json.dumps(sample_contract_dict, indent=2))
    return project_with_session
