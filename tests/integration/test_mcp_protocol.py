"""Integration tests: MCP protocol layer.

Tests tools through the FastMCP Client to catch serialization bugs,
parameter handling issues, and verify the JSON wire format matches
expected schemas.
"""

import pytest

from fastmcp import Client
from atlas_session.server import mcp


@pytest.fixture
async def mcp_client():
    """Create a FastMCP Client connected to the atlas-session server."""
    async with Client(mcp) as client:
        yield client


# ---------------------------------------------------------------------------
# TestSessionToolsViaMCP
# ---------------------------------------------------------------------------


class TestSessionToolsViaMCP:
    """Test session tools through the MCP protocol layer."""

    async def test_preflight_via_mcp(self, mcp_client, project_dir):
        """Call session_preflight via MCP, verify mode and project_signals keys."""
        result = await mcp_client.call_tool(
            "session_preflight",
            {"project_dir": str(project_dir)},
        )
        data = result.data

        # Verify top-level keys
        assert "mode" in data
        assert data["mode"] == "init"  # fresh project
        assert "is_git" in data
        assert "has_claude_md" in data
        assert "root_file_count" in data
        assert "templates_valid" in data
        assert "template_count" in data
        assert "session_files" in data
        assert "project_signals" in data

        # Verify project_signals structure
        signals = data["project_signals"]
        assert "has_readme" in signals
        assert "is_empty_project" in signals
        assert "detected_stack" in signals
        assert isinstance(signals["detected_stack"], list)

    async def test_init_via_mcp(self, mcp_client, project_dir):
        """Call session_init via MCP, verify session-context directory created."""
        result = await mcp_client.call_tool(
            "session_init",
            {
                "project_dir": str(project_dir),
                "soul_purpose": "Build integration tests",
                "ralph_mode": "Manual",
                "ralph_intensity": "",
            },
        )
        data = result.data

        assert data["status"] == "ok"
        assert data["files_created"] == data["expected"]

        # Verify files on disk
        sd = project_dir / "session-context"
        assert sd.is_dir()
        assert (sd / "CLAUDE-soul-purpose.md").is_file()
        assert (sd / "CLAUDE-activeContext.md").is_file()

    async def test_read_context_via_mcp(self, mcp_client, project_with_soul_purpose):
        """Call session_read_context on project with soul purpose."""
        result = await mcp_client.call_tool(
            "session_read_context",
            {"project_dir": str(project_with_soul_purpose)},
        )
        data = result.data

        assert data["soul_purpose"] == "Build a widget factory"
        assert data["status_hint"] != "no_purpose"
        assert isinstance(data["open_tasks"], list)
        assert isinstance(data["recent_progress"], list)

    async def test_classify_brainstorm_via_mcp(self, mcp_client):
        """Call session_classify_brainstorm with directive + signals, verify weight."""
        result = await mcp_client.call_tool(
            "session_classify_brainstorm",
            {
                "directive": "Build a REST API for widgets with authentication",
                "project_signals": {
                    "has_readme": True,
                    "has_code_files": True,
                    "has_package_json": False,
                    "has_pyproject": False,
                    "has_cargo_toml": False,
                    "has_go_mod": False,
                },
            },
        )
        data = result.data

        assert data["weight"] == "lightweight"  # directive + content
        assert data["has_directive"] is True
        assert data["has_content"] is True

    async def test_git_summary_via_mcp(self, mcp_client, project_with_git):
        """Call session_git_summary on project with git, verify structure."""
        result = await mcp_client.call_tool(
            "session_git_summary",
            {"project_dir": str(project_with_git)},
        )
        data = result.data

        assert data["is_git"] is True
        assert isinstance(data["branch"], str)
        assert len(data["branch"]) > 0
        assert isinstance(data["commits"], list)
        assert len(data["commits"]) > 0
        assert "hash" in data["commits"][0]
        assert "message" in data["commits"][0]
        assert data["commits"][0]["message"] == "initial"

    async def test_capability_inventory_via_mcp(self, mcp_client, project_with_git):
        """Call session_capability_inventory, verify cache and structure."""
        # First call should create cache (cache_hit=False)
        result1 = await mcp_client.call_tool(
            "session_capability_inventory",
            {"project_dir": str(project_with_git)},
        )
        data1 = result1.data

        assert data1["status"] == "ok"
        assert data1["is_git"] is True
        assert "git_head" in data1
        assert isinstance(data1["git_head"], str)
        assert len(data1["git_head"]) > 0
        assert data1["cache_hit"] is False
        assert data1["needs_generation"] is True
        assert "inventory_file" in data1

        # Second call should hit cache (cache_hit=True)
        result2 = await mcp_client.call_tool(
            "session_capability_inventory",
            {"project_dir": str(project_with_git)},
        )
        data2 = result2.data

        assert data2["status"] == "ok"
        assert data2["git_head"] == data1["git_head"]
        assert data2["cache_hit"] is True
        assert data2["needs_generation"] is False
        assert data2["git_changed"] is False

        # Force refresh should bypass cache
        result3 = await mcp_client.call_tool(
            "session_capability_inventory",
            {"project_dir": str(project_with_git), "force_refresh": True},
        )
        data3 = result3.data

        assert data3["status"] == "ok"
        assert data3["cache_hit"] is False
        assert data3["needs_generation"] is True


# ---------------------------------------------------------------------------
# TestContractToolsViaMCP
# ---------------------------------------------------------------------------


class TestContractToolsViaMCP:
    """Test contract tools through the MCP protocol layer."""

    async def test_run_tests_via_mcp(self, mcp_client, project_with_contract):
        """Call contract_run_tests on project with contract, verify results."""
        result = await mcp_client.call_tool(
            "contract_run_tests",
            {"project_dir": str(project_with_contract)},
        )
        data = result.data

        # Verify structure
        assert "results" in data
        assert "all_passed" in data
        assert "score" in data
        assert "summary" in data
        assert isinstance(data["results"], list)
        assert len(data["results"]) == 2

        # Both criteria from sample_contract_dict should pass:
        #   - "echo ok" -> exit_code == 0 -> pass
        #   - session-context/CLAUDE-activeContext.md exists and not_empty -> pass
        assert data["all_passed"] is True
        assert data["score"] == 100.0

        # Verify individual result structure
        for r in data["results"]:
            assert "name" in r
            assert "passed" in r
            assert "output" in r
            assert "weight" in r

    async def test_draft_criteria_via_mcp(self, mcp_client):
        """Call contract_draft_criteria, verify tests_pass appears for test soul purpose."""
        result = await mcp_client.call_tool(
            "contract_draft_criteria",
            {
                "soul_purpose": "Build and test a widget",
                "project_signals": {
                    "has_readme": True,
                    "has_code_files": True,
                    "has_package_json": False,
                    "has_pyproject": True,
                    "has_cargo_toml": False,
                    "has_go_mod": False,
                    "detected_stack": ["python"],
                },
            },
        )
        data = result.data

        assert "suggested_criteria" in data
        assert "soul_purpose" in data
        assert "note" in data

        criteria = data["suggested_criteria"]
        assert isinstance(criteria, list)
        assert (
            len(criteria) >= 3
        )  # has_commits, no_open_tasks, tests_pass, session_context_exists at minimum

        # Verify tests_pass appears (soul purpose contains "test")
        names = [c["name"] for c in criteria]
        assert "tests_pass" in names
        assert "has_commits" in names
        assert "session_context_exists" in names

        # Verify tests_pass uses pytest for python stack
        tests_criterion = next(c for c in criteria if c["name"] == "tests_pass")
        assert tests_criterion["command"] == "pytest"
        assert tests_criterion["type"] == "shell"

        # Verify lint_clean appears (has detected_stack)
        assert "lint_clean" in names
        lint_criterion = next(c for c in criteria if c["name"] == "lint_clean")
        assert lint_criterion["command"] == "ruff check ."
