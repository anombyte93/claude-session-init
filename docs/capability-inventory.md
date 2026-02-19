# Capability Inventory

## Overview

The capability inventory is a comprehensive mapping of what your project code does, what it claims to do, and what's been tested. It bridges the gap between documentation claims and code reality, making it easy to identify validation gaps.

Generated as `session-context/CLAUDE-capability-inventory.md`, the inventory provides:

- **MCP Tools Inventory**: Every tool with test coverage status
- **Security Claims**: Security features mapped to code and tests
- **Feature Claims**: Documentation claims vs implementation reality
- **Test Coverage Matrix**: Critical untested code by priority
- **Validation Checklist**: Actionable items for `/research-before-coding`

---

## When It's Generated

### Automatic Generation

The inventory is generated automatically during `/start` reconcile mode when:

- First run (no cache exists)
- Git HEAD has changed since last generation
- Cache was invalidated or deleted

### Manual Generation

Run `/sync --full` to force regeneration regardless of cache state. This bypasses the git HEAD check and triggers a fresh full codebase analysis.

### Caching Behavior

| Condition | Behavior |
|-----------|----------|
| Git repo, HEAD unchanged | Cache hit -- reuse existing inventory |
| Git repo, HEAD changed | Cache miss -- regenerate inventory |
| Non-git project | Always regenerate -- no caching |
| `/sync --full` | Force refresh -- ignore cache |

Cache metadata is stored in `session-context/.capability-cache.json` with:
- `git_head`: Commit hash used for cache key
- `generated_at`: ISO timestamp of last generation

---

## What It Contains

### MCP Tools Inventory

Every `@mcp.tool` decorator gets catalogued:

| Field | Description |
|-------|-------------|
| Tool | Function name |
| File | Source file path |
| Line | Line number in source |
| Purpose | Description from docstring |
| Test | Path to test file (if any) |
| Status | ✅ tested / ⚠️ partial / 🔴 untested |

Example:

```markdown
### Session Domain

| Tool | File | Line | Purpose | Test | Status |
|------|------|------|---------|------|--------|
| session_preflight | operations.py | 62 | Detect environment for mode selection | test_session_operations.py | ✅ tested |
| session_capability_inventory | operations.py | 1054 | Manage capability inventory cache | test_capability_inventory.py | ✅ tested |
```

### Security Claims

Security-related features extracted from:

- `CLAUDE-decisions.md` -- architecture security decisions
- `SECURITY.md` -- security documentation
- GitHub issues -- security vulnerabilities and fixes

Each claim includes:

| Field | Description |
|-------|-------------|
| Claim | Security feature description |
| Source | Document where claim originates |
| Code Location | Function/file:line implementing it |
| Test Coverage | Whether tests verify the security property |
| Risk Level | HIGH / MEDIUM / LOW if untested |

### Feature Claims

Features documented in:

- `README.md` -- "What It Does" section
- `CHANGELOG.md` -- released features
- Project documentation

Maps claims to evidence:

| Field | Description |
|-------|-------------|
| Claim | Feature description from docs |
| Source | Document making the claim |
| Evidence | Code implementing the feature |
| Test Status | Verified / Partial / Missing |

### Test Coverage Matrix

Shows testing status across the codebase:

```markdown
### Untested Code (Critical)

| File | Function | Risk | Priority |
|------|----------|------|----------|
| operations.py | _resolve_project_dir | Path traversal | HIGH |
| tools.py | register_all | Tool registration | MEDIUM |
```

### Code-to-Claim Mapping

Two-way comparison:

**What Code EXISTS to Do**: Actual behavior from static analysis
**What Code CLAIMS to Do**: Documentation claims

Gaps appear where claims lack evidence or code exists without documentation.

### External Dependencies

Tracks third-party libraries:

| Dependency | Version | Purpose | Security Consideration |
|------------|---------|---------|------------------------|
| fastmcp | latest | MCP server framework | -- |
| pydantic | 2.x | Data validation | -- |

---

## Using with /research-before-coding

The inventory generates research topics for validation:

```markdown
## Research Topics Generated

### Topic 1: Path Traversal Protection in _resolve_project_dir
**CALLER NEEDS TO KNOW**: How path resolution prevents directory traversal attacks
**LIBRARIES IN SCOPE**: pathlib, builtins
**TRIGGER**: Adding file operations to operations.py

### Topic 2: MCP Server Architecture Best Practices
**CALLER NEEDS TO KNOW**: How to structure modular FastMCP server
**LIBRARIES IN SCOPE**: fastmcp, pydantic
**TRIGGER**: Adding new MCP tool
```

Use these topics with `/research-before-coding` before modifying any code to ensure you understand security and architecture implications.

---

## Cache Invalidation

The cache is invalidated when:

1. **Git HEAD changes** -- New commits trigger regeneration
2. **Force refresh** -- `/sync --full` bypasses cache
3. **Cache deleted** -- Removing `.capability-cache.json` forces regeneration
4. **Non-git project** -- No caching, always regenerates

The cache key is the git commit hash from `git rev-parse HEAD`. Non-git projects have no cache key.

---

## Output Location

```
session-context/CLAUDE-capability-inventory.md
```

The inventory file is Markdown formatted for easy reading and editing. It's excluded from git by default (add to `.gitignore` if not already).

---

## MCP Tool

The inventory is managed via the `session_capability_inventory` MCP tool:

```python
session_capability_inventory(
    project_dir: str,
    force_refresh: bool = False,
) -> dict
```

Returns:

| Field | Type | Description |
|-------|------|-------------|
| status | str | "ok" or "error" |
| cache_hit | bool | Whether cache was valid |
| is_git | bool | Whether project is a git repo |
| git_head | str \| None | Current commit hash |
| git_changed | bool | Whether HEAD changed from cache |
| inventory_file | str | Relative path to inventory |
| needs_generation | bool | Whether inventory should be regenerated |
| error | str \| None | Error message if status != "ok" |

---

## Example Output

```markdown
# Capability Inventory

**Generated**: 2026-02-19T10:30:00Z
**Project**: atlas-session-lifecycle
**Git HEAD**: c03f590

---

## Executive Summary

| Category | Count | Status |
|----------|-------|--------|
| MCP Tools | 23 | 87% tested |
| Security Claims | 5 | 60% verified |
| Feature Claims | 12 | 75% verified |
| Critical Untested | 2 | Action needed |

---

## MCP Tools Inventory

### Session Domain

| Tool | File | Line | Purpose | Test | Status |
|------|------|------|---------|------|--------|
| session_preflight | operations.py | 62 | Detect environment | test_session_operations.py | ✅ tested |
| session_init | operations.py | 152 | Bootstrap session-context | test_session_operations.py | ✅ tested |
| session_capability_inventory | operations.py | 1054 | Manage capability inventory | test_capability_inventory.py | ✅ tested |

---

## Validation Checklist

Use this checklist with `/research-before-coding` to verify each claim:

- [ ] Path traversal protection in `_resolve_project_dir`
- [ ] Cache invalidation on git HEAD changes
- [ ] Session file corruption recovery
- [ ] Non-git project compatibility
- [ ] Force refresh bypasses cache correctly
```

---

## Troubleshooting

### "Inventory not generated even though cache missed"

The MCP tool signals `needs_generation=True` but doesn't generate the inventory directly. The caller (skill layer) must spawn an Explore agent to perform the full codebase analysis.

### "Cache not invalidating after commits"

Check that `git rev-parse HEAD` returns different values. If you're in a detached HEAD state or rebasing, the HEAD hash may not change as expected.

### "Permission denied writing inventory file"

Ensure `session-context/` directory exists and is writable. The MCP server runs with the same permissions as the user invoking it.

---

## Integration with /start Reconcile

During `/start` reconcile mode:

1. Call `session_capability_inventory(project_dir)`
2. If `cache_hit == False` or `git_changed == True`, spawn Explore agent
3. Explore agent generates `CLAUDE-capability-inventory.md`
4. Extract critical untested code, security claims, and feature gaps
5. Present findings during soul purpose assessment

This ensures you're always aware of validation gaps before continuing work.
