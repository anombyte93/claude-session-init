# Capability Inventory for /start Reconcile Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add capability inventory generation to `/start` reconcile mode that caches based on git HEAD and produces `CLAUDE-capability-inventory.md` with all MCP tools, tests, security claims, and feature claims for validation testing.

**Architecture:** Extend session operations with `capability_inventory()` function that spawns Explore agent for full codebase analysis when git HEAD changes. Cache results hash in `session-context/.capability-cache.json` and regenerate inventory only when invalidated. Output structured markdown inventory aligned for `/research-before-coding` consumption.

**Tech Stack:** Python 3.8+, pathlib, subprocess (git), Task agent (Explore), existing FastMCP infrastructure

---

## Task 1: Add capability inventory operation to session/operations.py

**Files:**
- Modify: `src/atlas_session/session/operations.py`
- Modify: `src/atlas_session/session/tools.py`

**Step 1: Write test for capability inventory cache behavior**

Create: `tests/unit/test_capability_inventory.py`

```python
"""Test capability inventory operations."""

import json
from pathlib import Path
import pytest

def test_capability_inventory_creates_cache_on_first_run(project_dir):
    """First call should create cache file and return inventory."""
    from atlas_session.session.operations import capability_inventory

    result = capability_inventory(str(project_dir))

    assert result["status"] == "ok"
    assert "cache_hit" in result
    assert result["cache_hit"] is False  # First run = miss
    assert result["inventory_file"] == "session-context/CLAUDE-capability-inventory.md"

    # Cache file should exist
    cache_path = project_dir / "session-context" / ".capability-cache.json"
    assert cache_path.exists()


def test_capability_inventory_returns_cache_on_subsequent_calls(project_dir, mocker):
    """Second call with same git HEAD should return cached result."""
    from atlas_session.session.operations import capability_inventory

    # First call
    capability_inventory(str(project_dir))

    # Mock git rev-parse to return same HEAD
    mocker.patch("subprocess.run", return_value=mocker.Mock(
        stdout=b"abc123\n",
        returncode=0
    ))

    # Second call
    result = capability_inventory(str(project_dir))

    assert result["status"] == "ok"
    assert result["cache_hit"] is True


def test_capability_inventory_invalidates_on_git_change(project_dir, mocker):
    """Git HEAD change should invalidate cache and regenerate."""
    from atlas_session.session.operations import capability_inventory

    # First call
    capability_inventory(str(project_dir))

    # Mock git rev-parse to return different HEAD
    m = mocker.patch("subprocess.run", return_value=mocker.Mock(
        stdout=b"def456\n",  # Different HEAD
        returncode=0
    ))

    # Modify mock to return different values on subsequent calls
    call_count = 0
    def side_effect(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return mocker.Mock(
            stdout=b"abc123\n" if call_count == 1 else b"def456\n",
            returncode=0
        )
    m.side_effect = side_effect

    # Second call with different HEAD
    result = capability_inventory(str(project_dir))

    assert result["status"] == "ok"
    assert result["cache_hit"] is False
    assert "git_changed" in result
    assert result["git_changed"] is True


def test_capability_inventory_handles_non_git(project_dir):
    """Non-git projects should generate inventory on every call."""
    from atlas_session.session.operations import capability_inventory

    # Mock git failure
    import subprocess
    original_run = subprocess.run

    def mock_run(*args, **kwargs):
        if "git" in args[0]:
            raise subprocess.CalledProcessError(1, "git")
        return original_run(*args, **kwargs)

    import subprocess
    subprocess.run = mock_run

    try:
        result = capability_inventory(str(project_dir))

        assert result["status"] == "ok"
        assert result["is_git"] is False
        assert result["cache_hit"] is False  # No git = always regenerate
    finally:
        subprocess.run = original_run
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_capability_inventory.py -v`
Expected: FAIL with "capability_inventory not defined"

**Step 3: Implement cache functions in operations.py**

Add to `src/atlas_session/session/operations.py` after git_summary function:

```python
# ---------------------------------------------------------------------------
# capability_inventory
# ---------------------------------------------------------------------------

CAPABILITY_CACHE_FILENAME = ".capability-cache.json"
CAPABILITY_INVENTORY_FILENAME = "CLAUDE-capability-inventory.md"


def _get_git_head(project_dir: str) -> str | None:
    """Get current git HEAD commit hash."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            cwd=project_dir,
            text=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def _get_capability_cache_path(project_dir: str) -> Path:
    """Get path to capability cache file."""
    return session_dir(project_dir) / CAPABILITY_CACHE_FILENAME


def _load_capability_cache(project_dir: str) -> dict | None:
    """Load cached inventory if exists and valid."""
    cache_path = _get_capability_cache_path(project_dir)
    if not cache_path.exists():
        return None

    try:
        data = json.loads(cache_path.read_text())
        return data
    except (json.JSONDecodeError, IOError):
        return None


def _save_capability_cache(project_dir: str, data: dict) -> None:
    """Save capability cache data."""
    cache_path = _get_capability_cache_path(project_dir)
    cache_path.write_text(json.dumps(data, indent=2))


def capability_inventory(project_dir: str, force_refresh: bool = False) -> dict:
    """Generate or load cached capability inventory.

    Args:
        project_dir: Path to project directory
        force_refresh: Force regeneration even if cache valid

    Returns:
        Dict with:
            status: "ok" or "error"
            cache_hit: bool - whether cache was used
            is_git: bool - whether project is git repo
            git_head: str | None - current commit hash
            git_changed: bool - whether HEAD changed from cache
            inventory_file: str - path to generated inventory
            error: str | None - error message if status != "ok"
    """
    root = Path(project_dir)
    inventory_file = session_dir(project_dir) / CAPABILITY_INVENTORY_FILENAME

    # Get current git state
    git_head = _get_git_head(project_dir)
    is_git = git_head is not None

    # Try to load cache
    cache = _load_capability_cache(project_dir) if is_git else None
    cache_hit = False
    git_changed = False

    if cache and not force_refresh:
        cached_head = cache.get("git_head")
        if cached_head == git_head:
            # Cache valid - inventory file should already exist
            cache_hit = True
        else:
            # Git changed - need to regenerate
            git_changed = True

    # If cache miss or git changed, need to generate inventory
    # For now, return status indicating inventory generation needed
    # (The actual Explore agent spawning happens in the skill layer)

    if not cache_hit or force_refresh:
        # Update cache
        _save_capability_cache(project_dir, {
            "git_head": git_head,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        })

    return {
        "status": "ok",
        "cache_hit": cache_hit,
        "is_git": is_git,
        "git_head": git_head,
        "git_changed": git_changed,
        "inventory_file": str(inventory_file.relative_to(root)),
        "needs_generation": not cache_hit or force_refresh,
    }
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/unit/test_capability_inventory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add tests/unit/test_capability_inventory.py src/atlas_session/session/operations.py
git commit -m "feat: add capability inventory cache operations"
```

---

## Task 2: Register capability inventory MCP tool

**Files:**
- Modify: `src/atlas_session/session/tools.py`

**Step 1: Add import for new operation**

At the top of tools.py, ensure the new function is accessible (already imported via `from . import operations as ops`)

**Step 2: Register the tool**

Add to the `register()` function in `src/atlas_session/session/tools.py` after `session_git_summary`:

```python
    @mcp.tool
    def session_capability_inventory(
        project_dir: str,
        force_refresh: bool = False,
    ) -> dict:
        """Get or generate capability inventory for the project.

        Returns cached inventory if git HEAD unchanged, otherwise
        triggers full codebase analysis via Explore agent.

        The inventory maps all MCP tools, tests, security claims, and
        feature claims for validation testing with /research-before-coding.

        Args:
            project_dir: Path to project directory
            force_refresh: Force regeneration even if cache valid

        Returns:
            Dict with cache status and inventory file path.
            If needs_generation=True, caller should spawn Explore agent.
        """
        return ops.capability_inventory(project_dir, force_refresh)
```

**Step 3: Verify tool is registered**

Run: `python -m atlas_session.server &` then check tool list
Or add test:

```python
def test_capability_inventory_tool_registered():
    """Tool should be registered on MCP server."""
    from atlas_session.session import tools

    # Check tool is in registry
    assert hasattr(tools, "register")
    # Tool should be accessible when server starts
```

**Step 4: Run tests**

Run: `pytest tests/unit/test_capability_inventory.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/atlas_session/session/tools.py
git commit -m "feat: register session_capability_inventory MCP tool"
```

---

## Task 3: Create Explore agent prompt template

**Files:**
- Create: `prompts/capability-inventory-agent.md`

**Step 1: Create the agent prompt template**

Create: `prompts/capability-inventory-agent.md`

```markdown
# Capability Inventory Agent

You are a codebase analysis agent. Your task is to generate a comprehensive capability inventory for `/research-before-coding` validation.

## Input

- **Project directory**: {{project_dir}}
- **Git HEAD**: {{git_head}}
- **Output file**: {{output_file}}

## Analysis Scope

Analyze the following thoroughly:

### 1. MCP Tools (`src/atlas_session/*/tools.py`)

For each `@mcp.tool` decorator:
- Tool name
- File and line number
- Purpose (from docstring)
- Test file covering it (search `tests/`)
- Status: ✅ tested / ⚠️ partial / 🔴 no test

### 2. Security Claims

Extract from:
- `session-context/CLAUDE-decisions.md`
- `SECURITY.md`
- `README.md`
- GitHub issues

For each claim:
- Claim description
- Source document
- Code location (function/file:line)
- Test coverage status
- Risk level: HIGH / MEDIUM / LOW

### 3. Feature Claims

Extract from:
- `README.md` - "What It Does" section
- `docs/unique-value-proposition.md`
- `CHANGELOG.md`

For each claim:
- Feature description
- Source
- Code evidence (functions/modules implementing it)
- Test status

### 4. Test Files

List all test files with:
- File path
- Line count
- What it covers
- What's missing

### 5. Code Capabilities (Static Analysis)

From `src/` analysis:
- Domains identified (session/, contract/, stripe/)
- Entry points
- External dependencies
- Key functions by purpose

## Output Format

Write the inventory to the output file in this EXACT structure:

```markdown
# Capability Inventory

**Generated**: {{timestamp}}
**Project**: {{project_name}}
**Git HEAD**: {{git_head}}

---

## Executive Summary

| Category | Count | Status |
|----------|-------|--------|

---

## MCP Tools Inventory

### Session Domain

| Tool | File | Line | Purpose | Test | Status |
|------|------|------|---------|------|--------|

### Contract Domain

[Same table format]

### Stripe Domain

[Same table format]

---

## Security Claims Inventory

| Claim | Source | Code Location | Test | Status |
|-------|--------|---------------|------|--------|

---

## Feature Claims Inventory

| Claim | Source | Evidence | Test | Status |
|-------|--------|----------|------|--------|

---

## Test Coverage Matrix

### Untested Code (Critical)

| File | Function | Risk | Priority |
|------|----------|------|----------|

---

## Code-to-Claim Mapping

### What Code EXISTS to Do

[List key functions with their actual behavior from code analysis]

### What Code CLAIMS to Do

[Claims from docs, reality comparison]

---

## External Dependencies

| Dependency | Version | Purpose | Security Consideration |
|------------|---------|---------|------------------------|

---

## Validation Checklist

Use this checklist with `/research-before-coding` to verify each claim:

- [ ] Item 1
- [ ] Item 2
...

---

## Research Topics Generated

For each unvalidated claim, list research topic with:
1. Topic name
2. CALLER NEEDS TO KNOW
3. LIBRARIES IN SCOPE
4. TRIGGER
```

## Execution

1. Read all source files in `src/`
2. Read all test files in `tests/`
3. Read documentation files
4. Extract and structure findings
5. Write inventory to output file
6. Return summary of findings
```

**Step 2: Commit**

```bash
git add prompts/capability-inventory-agent.md
git commit -m "docs: add capability inventory agent prompt template"
```

---

## Task 4: Integrate capability inventory into /start reconcile mode

**Files:**
- Modify: `skills/start/SKILL.md`
- Modify: `skills/sync/SKILL.md`

**Step 1: Add capability inventory to /start reconcile flow**

In `skills/start/SKILL.md`, update "Step 1: Silent Assessment + Context Reality Check" to include capability inventory:

Add after "Call `session_git_summary(project_dir)`" line:

```markdown
7. **Compare** `read_context` against `git_summary`: if context is stale, update `session-context/CLAUDE-activeContext.md`.
8. Check capability inventory: call `session_capability_inventory(project_dir)`.
   - If `cache_hit == True` and `git_changed == False`: inventory is current
   - If `needs_generation == True`: spawn Explore agent with prompt from `prompts/capability-inventory-agent.md`
   - Explore agent generates `session-context/CLAUDE-capability-inventory.md`
9. Read `CLAUDE-capability-inventory.md` if exists and extract:
   - Untested code (critical priority)
   - Security claims needing verification
   - Feature claims with gaps
```

**Step 2: Add /sync --full flag support**

In `skills/sync/SKILL.md`, add new section at the end:

```markdown
## /sync --full (Capability Inventory)

When user runs `/sync --full`:

1. Run standard sync (steps 1-6 above)
2. Call `session_capability_inventory(project_dir, force_refresh=True)`
3. If `needs_generation == True`, spawn Explore agent
4. Print summary:

```
Synced. {N} files updated.
- Active context: {1-line summary}
- Decisions: {count new or "no new"}
- Patterns: {count new or "no new"}
- Troubleshooting: {count new or "no new"}
- Memory: {updated or "no changes"}

Capability Inventory: {status}
- MCP Tools: {count} ({tested}% tested)
- Security Claims: {count} ({verified}% verified)
- Feature Claims: {count} ({verified}% verified)
- Critical Untested: {count}
- Inventory file: {path}
```

**Step 3: Commit**

```bash
git add skills/start/SKILL.md skills/sync/SKILL.md
git commit -m "feat: integrate capability inventory into /start reconcile and /sync --full"
```

---

## Task 5: Add integration tests for full flow

**Files:**
- Create: `tests/integration/test_capability_inventory_flow.py`

**Step 1: Write integration test**

Create: `tests/integration/test_capability_inventory_flow.py`

```python
"""Integration test for capability inventory generation."""

import json
from pathlib import pytest
from pathlib import Path


def test_capability_inventory_full_flow(temp_project_dir):
    """Test full flow: preflight -> inventory -> cache -> refresh."""
    from atlas_session.session.operations import (
        capability_inventory,
        preflight,
    )

    project_dir = str(temp_project_dir)

    # 1. Preflight shows reconcile mode
    pre = preflight(project_dir)
    assert pre["mode"] == "reconcile"

    # 2. First call generates inventory
    result1 = capability_inventory(project_dir)
    assert result1["status"] == "ok"
    assert result1["cache_hit"] is False
    assert result1["needs_generation"] is True

    # 3. Simulate Explore agent writing inventory
    inventory_file = temp_project_dir / "session-context" / "CLAUDE-capability-inventory.md"
    inventory_file.write_text("# Capability Inventory\\n\\nTest content")

    # 4. Second call with same git HEAD hits cache
    result2 = capability_inventory(project_dir)
    assert result2["status"] == "ok"
    assert result2["cache_hit"] is True
    assert result2["needs_generation"] is False

    # 5. Force refresh regenerates
    result3 = capability_inventory(project_dir, force_refresh=True)
    assert result3["status"] == "ok"
    assert result3["cache_hit"] is False
    assert result3["needs_generation"] is True


def test_capability_inventory_with_git_changes(temp_git_project_dir):
    """Test cache invalidation on git commit."""
    from atlas_session.session.operations import capability_inventory
    import subprocess

    project_dir = str(temp_git_project_dir)

    # 1. Initial inventory
    result1 = capability_inventory(project_dir)
    head1 = result1["git_head"]
    assert head1 is not None

    # 2. Make a commit
    test_file = temp_git_project_dir / "test.txt"
    test_file.write_text("test")
    subprocess.run(["git", "add", "test.txt"], cwd=project_dir, check=True)
    subprocess.run(
        ["git", "commit", "-m", "test"],
        cwd=project_dir,
        check=True,
        capture_output=True,
    )

    # 3. Cache should be invalidated
    result2 = capability_inventory(project_dir)
    head2 = result2["git_head"]
    assert head2 != head1
    assert result2["git_changed"] is True
    assert result2["cache_hit"] is False


def test_capability_inventory_non_git(temp_project_dir):
    """Test inventory generation for non-git projects."""
    from atlas_session.session.operations import capability_inventory

    project_dir = str(temp_project_dir)

    result = capability_inventory(project_dir)
    assert result["status"] == "ok"
    assert result["is_git"] is False
    assert result["cache_hit"] is False  # No cache for non-git
```

**Step 2: Run integration tests**

Run: `pytest tests/integration/test_capability_inventory_flow.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add tests/integration/test_capability_inventory_flow.py
git commit -m "test: add integration tests for capability inventory flow"
```

---

## Task 6: Update documentation

**Files:**
- Modify: `README.md`
- Create: `docs/capability-inventory.md`

**Step 1: Update README with capability inventory mention**

Add to README.md in "How It Works" section after Reconcile Mode:

```markdown
### Capability Inventory

When `/start` runs in Reconcile mode (or when you run `/sync --full`), it generates a comprehensive capability inventory:

- **MCP Tools**: All available tools with test coverage status
- **Security Claims**: Security-related features needing verification
- **Feature Claims**: What the project claims vs what's tested
- **Test Gaps**: Untested code identified by priority

The inventory lives in `session-context/CLAUDE-capability-inventory.md` and is used by `/research-before-coding` to identify what needs validation testing.
```

**Step 2: Create detailed capability inventory documentation**

Create: `docs/capability-inventory.md`

```markdown
# Capability Inventory

## Overview

The capability inventory is a comprehensive mapping of what your project code does, what it claims to do, and what's been tested.

## When It's Generated

- **Automatic**: On `/start` reconcile when git HEAD changes
- **Manual**: Run `/sync --full` to force regeneration
- **Cached**: Results cached based on git HEAD commit hash

## What It Contains

### MCP Tools Inventory

Every `@mcp.tool` gets catalogued with:
- Function signature and docstring
- File location and line number
- Test file covering it (if any)
- Coverage status: ✅ tested / ⚠️ partial / 🔴 untested

### Security Claims

Security-related features from:
- `CLAUDE-decisions.md` - architecture security decisions
- `SECURITY.md` - security documentation
- GitHub issues - security vulnerabilities

Each claim tracks:
- What the security feature is
- Where it's implemented in code
- Whether tests verify it works
- Risk level if untested

### Feature Claims

Features documented in:
- `README.md` - "What It Does" section
- `CHANGELOG.md` - released features
- Project documentation

Maps claims to:
- Code that implements it
- Tests that verify it
- Gaps where claim lacks evidence

### Test Coverage Matrix

Shows:
- Which test files exist
- What code they cover
- Critical untested functions
- Priority for adding tests

## Using with /research-before-coding

The inventory generates research topics for validation:

```markdown
## Research Topics Generated

### Topic 1: MCP Server Architecture Best Practices
**CALLER NEEDS TO KNOW**: How to structure modular FastMCP server
**LIBRARIES IN SCOPE**: fastmcp, pydantic
**TRIGGER**: Adding new MCP tool
```

Use these topics with `/research-before-coding` before modifying any code.

## Cache Invalidation

The inventory caches based on git HEAD:

- **Cache hit**: Same git HEAD = reuse inventory
- **Cache miss**: New commits = regenerate inventory
- **Non-git**: Always regenerate (no caching)
- **Force refresh**: `/sync --full` ignores cache

## Output Location

`session-context/CLAUDE-capability-inventory.md`
```

**Step 3: Commit**

```bash
git add README.md docs/capability-inventory.md
git commit -m "docs: document capability inventory feature"
```

---

## Summary

After implementing all tasks:

1. ✅ `capability_inventory()` operation manages cache based on git HEAD
2. ✅ `session_capability_inventory` MCP tool exposed
3. ✅ Explore agent prompt template for inventory generation
4. ✅ /start reconcile integrates capability inventory
5. ✅ /sync --full forces inventory refresh
6. ✅ Integration tests validate full flow
7. ✅ Documentation explains the feature

**Total estimated time**: 2-3 hours

**Test coverage**:
- Unit tests for cache behavior
- Integration tests for full flow
- Git change detection tests
- Non-git project tests
