"""Integration tests: capability inventory full flow.

Tests the complete capability inventory lifecycle including:
- preflight -> inventory -> cache -> refresh
- cache invalidation on git changes
- non-git project handling
"""

import json
import subprocess

from atlas_session.session.operations import (
    capability_inventory,
    preflight,
    cache_governance,
    CAPABILITY_INVENTORY_FILENAME,
)


# ---------------------------------------------------------------------------
# TestCapabilityInventoryFullFlow
# ---------------------------------------------------------------------------


class TestCapabilityInventoryFullFlow:
    """Full capability inventory flow: preflight -> inventory -> cache -> refresh.

    Verifies that the capability inventory system correctly manages cache
    lifecycle across multiple invocations with varying git states.
    """

    def test_capability_inventory_full_flow(self, project_with_git):
        """Walk through complete capability inventory sequence: preflight -> inventory -> cache -> refresh."""
        pd = str(project_with_git)
        cache_file = project_with_git / "session-context" / ".capability-cache.json"

        # 1. Preflight -> verify git project detected
        pf = preflight(pd)
        assert pf["mode"] == "reconcile"
        assert pf["is_git"] is True

        # 2. First capability_inventory call -> creates cache, needs generation
        result1 = capability_inventory(pd)
        assert result1["status"] == "ok"
        assert result1["is_git"] is True
        assert result1["git_head"] is not None
        assert result1["cache_hit"] is False
        assert result1["needs_generation"] is True
        assert result1["git_changed"] is False
        assert result1["inventory_file"] == f"session-context/{CAPABILITY_INVENTORY_FILENAME}"

        # Verify cache file was created
        assert cache_file.is_file()
        first_head = result1["git_head"]

        # Verify cache contents
        cache = json.loads(cache_file.read_text())
        assert "git_head" in cache
        assert cache["git_head"] == first_head
        assert "cached_at" in cache

        # 3. Second call with same HEAD -> cache hit
        result2 = capability_inventory(pd)
        assert result2["status"] == "ok"
        assert result2["is_git"] is True
        assert result2["git_head"] == first_head
        assert result2["cache_hit"] is True
        assert result2["needs_generation"] is False
        assert result2["git_changed"] is False

        # 4. Force refresh -> bypass cache, update timestamp
        result3 = capability_inventory(pd, force_refresh=True)
        assert result3["status"] == "ok"
        assert result3["cache_hit"] is False
        assert result3["needs_generation"] is True
        assert result3["git_changed"] is False  # git didn't actually change

        # Cache was updated with new timestamp
        cache_after_force = json.loads(cache_file.read_text())
        assert cache_after_force["git_head"] == first_head
        assert cache_after_force["cached_at"] != cache["cached_at"]

    def test_capability_inventory_with_git_changes(self, project_with_git):
        """Cache invalidation on commit: new HEAD = needs regeneration."""
        pd = str(project_with_git)
        cache_file = project_with_git / "session-context" / ".capability-cache.json"

        # 1. Initial call
        result1 = capability_inventory(pd)
        first_head = result1["git_head"]
        assert result1["cache_hit"] is False
        assert result1["needs_generation"] is True
        assert cache_file.is_file()

        # 2. Verify cache hit on subsequent call
        result2 = capability_inventory(pd)
        assert result2["cache_hit"] is True
        assert result2["needs_generation"] is False
        assert result2["git_head"] == first_head

        # 3. Make a git commit to change HEAD
        (project_with_git / "new_feature.txt").write_text("Feature implementation")
        subprocess.run(["git", "add", "."], cwd=project_with_git, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "Add new feature"],
            cwd=project_with_git,
            capture_output=True,
        )

        # 4. Capability inventory should detect change and invalidate cache
        result3 = capability_inventory(pd)
        assert result3["status"] == "ok"
        assert result3["is_git"] is True
        assert result3["git_head"] != first_head
        assert result3["cache_hit"] is False
        assert result3["git_changed"] is True
        assert result3["needs_generation"] is True

        # Cache file was updated with new HEAD
        new_cache = json.loads(cache_file.read_text())
        assert new_cache["git_head"] == result3["git_head"]
        assert new_cache["git_head"] != first_head

        # 5. Next call should hit cache again
        result4 = capability_inventory(pd)
        assert result4["cache_hit"] is True
        assert result4["needs_generation"] is False
        assert result4["git_head"] == result3["git_head"]

    def test_capability_inventory_non_git(self, project_with_session):
        """Non-git projects always regenerate: no cache file created."""
        pd = str(project_with_session)
        cache_file = project_with_session / "session-context" / ".capability-cache.json"

        # Verify no git repo
        pf = preflight(pd)
        assert pf["is_git"] is False

        # 1. First call -> no cache, needs generation
        result1 = capability_inventory(pd)
        assert result1["status"] == "ok"
        assert result1["is_git"] is False
        assert result1["git_head"] is None
        assert result1["cache_hit"] is False
        assert result1["git_changed"] is False
        assert result1["needs_generation"] is True
        assert result1["inventory_file"] == f"session-context/{CAPABILITY_INVENTORY_FILENAME}"

        # No cache file should be created for non-git projects
        assert not cache_file.is_file()

        # 2. Second call -> still no cache hit (non-git always regenerates)
        result2 = capability_inventory(pd)
        assert result2["status"] == "ok"
        assert result2["is_git"] is False
        assert result2["cache_hit"] is False
        assert result2["needs_generation"] is True

        # Still no cache file
        assert not cache_file.is_file()

        # 3. Force refresh has same effect for non-git
        result3 = capability_inventory(pd, force_refresh=True)
        assert result3["status"] == "ok"
        assert result3["is_git"] is False
        assert result3["cache_hit"] is False
        assert result3["needs_generation"] is True


# ---------------------------------------------------------------------------
# TestCapabilityInventoryEdgeCases
# ---------------------------------------------------------------------------


class TestCapabilityInventoryEdgeCases:
    """Edge cases and boundary conditions for capability inventory."""

    def test_capability_inventory_with_governance_cache_coexistence(
        self, project_with_git
    ):
        """Capability cache and governance cache can coexist without interference."""
        pd = str(project_with_git)
        capability_cache = project_with_git / "session-context" / ".capability-cache.json"

        # Create CLAUDE.md first (required for cache_governance)
        (project_with_git / "CLAUDE.md").write_text(
            "# CLAUDE.md\n\n"
            "## Structure Maintenance Rules\n\n"
            "Keep files organized.\n\n"
            "## Session Context Files\n\n"
            "Maintain session-context/ files.\n\n"
            "## IMMUTABLE TEMPLATE RULES\n\n"
            "Never edit templates.\n\n"
            "## Ralph Loop\n\n"
            "**Mode**: Manual\n"
        )

        # 1. Cache governance sections
        governance_result = cache_governance(pd)
        assert governance_result["status"] == "ok"

        # 2. Call capability inventory
        capability_result = capability_inventory(pd)
        assert capability_result["status"] == "ok"
        assert capability_cache.is_file()

        # 3. Both caches should exist independently
        from atlas_session.common.config import GOVERNANCE_CACHE_PATH

        assert GOVERNANCE_CACHE_PATH.is_file()
        assert capability_cache.is_file()

        # 4. They should have different content
        governance_data = json.loads(GOVERNANCE_CACHE_PATH.read_text())
        capability_data = json.loads(capability_cache.read_text())
        assert "git_head" in capability_data
        assert "git_head" not in governance_data  # Governance cache has sections

    def test_capability_inventory_cache_corruption_recovery(self, project_with_git):
        """Corrupted cache file is handled gracefully and replaced."""
        pd = str(project_with_git)
        cache_file = project_with_git / "session-context" / ".capability-cache.json"

        # 1. Create initial valid cache
        result1 = capability_inventory(pd)
        first_head = result1["git_head"]
        assert cache_file.is_file()

        # 2. Corrupt the cache file
        cache_file.write_text("{ invalid json content [[[ ")

        # 3. Next call should recover and create new cache
        result2 = capability_inventory(pd)
        assert result2["status"] == "ok"
        assert result2["cache_hit"] is False  # Invalid cache treated as miss
        assert result2["needs_generation"] is True

        # Cache should be valid now
        new_cache = json.loads(cache_file.read_text())
        assert new_cache["git_head"] == first_head

    def test_capability_inventory_after_repo_init(self, project_with_session):
        """Project initialized as non-git, later becomes git: cache starts working."""
        pd = str(project_with_session)
        cache_file = project_with_session / "session-context" / ".capability-cache.json"

        # 1. Initially non-git
        result1 = capability_inventory(pd)
        assert result1["is_git"] is False
        assert result1["cache_hit"] is False
        assert not cache_file.is_file()

        # 2. Initialize git repo
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
        (project_with_session / "README.md").write_text("# Test\n")
        subprocess.run(["git", "add", "."], cwd=project_with_session, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "init"],
            cwd=project_with_session,
            capture_output=True,
        )

        # 3. Now capability inventory should detect git and create cache
        result2 = capability_inventory(pd)
        assert result2["is_git"] is True
        assert result2["git_head"] is not None
        assert result2["cache_hit"] is False
        assert result2["needs_generation"] is True
        assert cache_file.is_file()

        # 4. Subsequent call should hit cache
        result3 = capability_inventory(pd)
        assert result3["is_git"] is True
        assert result3["cache_hit"] is True
        assert result3["needs_generation"] is False


# ---------------------------------------------------------------------------
# TestCapabilityInventoryMultiCommit
# ---------------------------------------------------------------------------


class TestCapabilityInventoryMultiCommit:
    """Cache behavior across multiple commits and rapid changes."""

    def test_capability_inventory_multiple_commits(self, project_with_git):
        """Cache tracks HEAD changes across multiple commits."""
        pd = str(project_with_git)
        cache_file = project_with_git / "session-context" / ".capability-cache.json"

        heads_seen = []

        for i in range(3):
            # Create and commit a new file
            new_file = project_with_git / f"commit_{i}.txt"
            new_file.write_text(f"Content {i}")
            subprocess.run(["git", "add", "."], cwd=project_with_git, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", f"Commit {i}"],
                cwd=project_with_git,
                capture_output=True,
            )

            # Check capability inventory
            result = capability_inventory(pd)
            assert result["status"] == "ok"
            assert result["is_git"] is True
            assert result["git_head"] not in heads_seen  # New HEAD each time
            assert result["cache_hit"] is False  # Cache invalid on each commit
            # git_changed is True only if there was a previous cache
            if i > 0:
                assert result["git_changed"] is True
            assert result["needs_generation"] is True

            heads_seen.append(result["git_head"])

            # Immediate second call should hit cache
            result2 = capability_inventory(pd)
            assert result2["cache_hit"] is True
            assert result2["git_head"] == result["git_head"]
            assert result2["git_changed"] is False

        # Verify we tracked 3 distinct commits
        assert len(heads_seen) == 3
        assert len(set(heads_seen)) == 3  # All unique

        # Final cache has the latest HEAD
        final_cache = json.loads(cache_file.read_text())
        assert final_cache["git_head"] == heads_seen[-1]

    def test_capability_inventory_amend_commit(self, project_with_git):
        """Git amend changes HEAD even if commit message is same."""
        pd = str(project_with_git)

        # Initial call
        result1 = capability_inventory(pd)
        first_head = result1["git_head"]

        # Make a change and amend the initial commit
        (project_with_git / "amended.txt").write_text("Amended content")
        subprocess.run(["git", "add", "."], cwd=project_with_git, capture_output=True)
        subprocess.run(
            ["git", "commit", "--amend", "--no-edit"],
            cwd=project_with_git,
            capture_output=True,
        )

        # Capability inventory should detect the HEAD change
        result2 = capability_inventory(pd)
        assert result2["git_head"] != first_head  # HEAD changed after amend
        assert result2["cache_hit"] is False
        assert result2["git_changed"] is True
        assert result2["needs_generation"] is True


# ---------------------------------------------------------------------------
# TestCapabilityInventoryWithPreflightIntegration
# ---------------------------------------------------------------------------


class TestCapabilityInventoryWithPreflightIntegration:
    """Integration between preflight and capability inventory."""

    def test_preflight_git_detection_aligns_with_inventory(self, project_with_git):
        """Preflight git detection aligns with capability inventory for git projects."""
        pd = str(project_with_git)

        # Preflight detects git
        pf = preflight(pd)
        assert pf["is_git"] is True

        # Capability inventory also detects git
        ci = capability_inventory(pd)
        assert ci["is_git"] is True
        assert ci["git_head"] is not None

    def test_preflight_non_git_detection_aligns_with_inventory(self, project_dir):
        """Preflight git detection aligns with capability inventory for non-git projects."""
        pd = str(project_dir)

        # Preflight detects no git
        pf = preflight(pd)
        assert pf["is_git"] is False

        # Capability inventory also detects no git
        ci = capability_inventory(pd)
        assert ci["is_git"] is False
        assert ci["git_head"] is None
