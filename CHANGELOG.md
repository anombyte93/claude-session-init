# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- HMAC secret reads from `ATLAS_HMAC_SECRET` env var (no more hardcoded default in production)
- Path traversal protection in `_resolve_project_dir()` — rejects paths outside `$HOME` and `/tmp`

### Added
- CI provider detection (`has_ci`, `ci_provider`) in project signals
- Pre-commit hooks configuration (ruff, trailing-whitespace, check-yaml/json)
- Capability inventory for `/start` reconcile mode

### Changed
- Version numbers unified to 4.1.0 across all files
- `stripe_client.py` imports `_HMAC_SECRET` from `license.py` (single source of truth)
- Business strategy docs untracked from git (kept on disk)

### Fixed
- `install.sh` pinned commit trimmed from malformed `8c4cbc5feat-productization` to `8c4cbc5`
- Test compatibility for security changes

## [4.1.0] - 2026-02-18

### Added
- Stripe integration — checkout, webhooks, license refresh, customer validation (5 tools)
- Landing page for GitHub Pages
- Stripe setup documentation
- Capability inventory tool (`session_capability_inventory`)

### Changed
- Stripe is a truly optional dependency
- `pyproject.toml` formatted — optional dependencies moved to end

### Fixed
- Landing page rewrite — shows WHY users need this
- Unused variable removed in `stripe_client.py`
- Workflow file restored to match main branch
- Stripe extras installed in CI for test coverage

### Security
- 7 issues fixed from Claude Code Review
- Test compatibility extended for security changes
- Command allowlist extended

## [4.0.0] - 2026-02-17

### Added
- `/start` and `/stop` now run `/sync` first
- CI triggers on feature branches + `workflow_dispatch`
- `atlas-license` CLI entry point wired up
- License management module — activate, revoke, validate
- Python CI + production `pyproject.toml`

### Changed
- Reusable CI, review, and release-please workflows from `anombyte93/copilot@v1`
- `/ralph-go` replaces Ralph questions in `/start` skill

### Fixed
- 4 remaining known bugs — binary crash, None crash, archive destruction, non-dict JSON

### Security
- Shell injection removed — `shlex.split` replaces `shell=True`

## [3.0.0] - 2026-02-16

### Added
- MCP server source brought into repo + 5 new session tools
- `/start` SKILL.md rewrite — MCP-first, 464 to 266 lines
- `/stop` SKILL.md rewrite — MCP-first, 3-intent, 156 lines
- `/sync` skill — fast zero-question save-point
- Comprehensive test suite — 196 tests covering all 23 MCP tools
- 13 edge case tests for verifier, read_context, clutter
- Agent Teams orchestration with AtlasCoin bounty verification
- `/stop` skill for graceful session close
- `check-clutter` command and reconcile cleanup step
- Interactive extra skills prompt in installer
- Bundled `/stepback` strategic reassessment skill
- `custom.md` documentation with concrete examples

### Changed
- Hostile testing rewrite — deleted 28 tautological tests, added 31 hostile tests
- Agent Teams enforced for work execution (not just session lifecycle)

### Fixed
- `read_context` parser checked full file for "(No active soul purpose)"
- Doubt findings addressed in `/stop` skill
- Simple release-type for non-node project
- Review-gate permissions moved to workflow level

## [2.0.0] - 2026-02-14

### Added
- **Reconcile Mode**: Returning session detection with soul purpose completion assessment
- **Soul Purpose Lifecycle**: init -> work -> reconcile -> harvest -> close/continue
- **Active Context Harvesting**: Promote decisions, patterns, troubleshooting on closure
- **Governance Caching**: Cache CLAUDE.md sections before Claude /init, restore after
- **Plugin Format**: `.claude-plugin/` structure for plugin installation
- **custom.md**: Extensibility hook for init/reconcile customization
- **Auto-Update Check**: Non-blocking notification when new version available
- **Deterministic Backend**: Python script handles all file I/O, outputs JSON
- **Dual-Mode Installer**: Supports both skill and plugin installation
- **Stepback Skill**: Bundled `/stepback` strategic reassessment protocol for debugging loops

### Changed
- SKILL.md refactored into thin orchestrator (320 lines) + Python backend (664 lines)
- Templates resolve from plugin-relative path with home directory fallback
- Install script supports both `~/.claude/skills/` and `~/.claude/plugins/` targets
- Repository renamed from `claude-session-init` to `atlas-session-lifecycle`
- File structure reorganized: `skills/start/SKILL.md`, `scripts/session-init.py`

### Migration from v1
- v1 SKILL.md preserved in `v1/` directory
- `install.sh --version v1` still available
- `install.sh --revert` to downgrade

## [1.0.0] - 2025-06-15

### Added
- Initial `/start` skill with session bootstrapping
- Template-based session context files (5-file memory bank)
- File organization for cluttered project roots
- CLAUDE.md generation with governance sections
- Soul purpose capture and tracking
- Ralph Loop onboarding
