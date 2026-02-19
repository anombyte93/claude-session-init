# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Project**: [Project Name]
**Goal**: [Primary objective]
**Stack**: [Technologies / platforms]

---

## Project Structure

### Root Files
- `CLAUDE.md` - Claude Code instructions (this file)
- [Other root-level files that stay at root]

### session-context/
CLAUDE memory bank files (managed by /start skill):
- `CLAUDE-activeContext.md` - Current session state, goals, progress
- `CLAUDE-decisions.md` - Architecture decisions and rationale
- `CLAUDE-patterns.md` - Established code patterns and conventions
- `CLAUDE-troubleshooting.md` - Common issues and proven solutions
- `CLAUDE-soul-purpose.md` - Soul purpose definition

### scripts/
- `scripts/[category]/` - [Description]

### docs/
- `docs/[category]/` - [Description]

---

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
- Periodically review root for stale files and move to correct category

---

## Session Context Files (MUST maintain)

After every session, update these files in `session-context/` with timestamp and reasoning:

- `session-context/CLAUDE-activeContext.md` - Current session state, goals, progress
- `session-context/CLAUDE-decisions.md` - Architecture decisions and rationale
- `session-context/CLAUDE-patterns.md` - Established code patterns and conventions
- `session-context/CLAUDE-troubleshooting.md` - Common issues and proven solutions

**Entry Format**:
```markdown
## HH:MM DD/MM/YY
### REASON
Who:
What:
When:
Where:
Why:
How:
References:
Git Commit:
Potential Issues to face:
```

---

## Common Commands

### [Category]
```bash
[Useful command]
```

---

## Current Status

### DONE
- [Completed items]

### NEED TO DO
- [Remaining items]

### CRITICAL WARNINGS
- [Important warnings]

---

## Workflow Before Completing Tasks

1. Use 3 explore agents to understand the issue
2. Invoke `superpower:brainstorm` skill
3. Invoke PLAN mode to create a plan
4. Invoke `prd-taskmaster` skill for task breakdown backed by DEEP research
5. Invoke debugger in parallel if not a sequential task
6. After each parent task: invoke `@doubt-agent` and `@finality-agent` to verify
7. Loop until task complete and verified working from user feedback

**Research**: Use `perplexity-api-free` for comprehensive DEEP research before any work.

---

## Ralph Loop Variables

When user invokes `/ralph-wiggum:ralph-loop`:

```bash
--completion-promise [Define what "done" means for this project]
--max-iterations 5
```

---

## User Commands

### `/ralph-wiggum:ralph-loop <prompt>`
Starts Ralph Loop with variables from Ralph Loop Variables section above.

### `state`
Shows what has been done, what needs to be done, and recent content from context files.
Also updates `session-context/CLAUDE-activeContext.md`, `session-context/CLAUDE-decisions.md`, `session-context/CLAUDE-patterns.md`, `session-context/CLAUDE-troubleshooting.md` if they haven't been updated.

---

## Architecture Decisions

See `session-context/CLAUDE-decisions.md` for full decision log.

---

## Troubleshooting

See `session-context/CLAUDE-troubleshooting.md` for full troubleshooting guide.

---

## IMMUTABLE TEMPLATE RULES

> **DO NOT** edit the template files bundled with the plugin.
> Templates are immutable source-of-truth. Only edit the copies in your project.
