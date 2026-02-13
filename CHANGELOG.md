# Changelog

All notable changes to this project will be documented in this file.

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
