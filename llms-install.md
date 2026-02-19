# Atlas Session Lifecycle

> Persistent project memory and session lifecycle management for AI coding assistants

---

## Installation

```bash
curl -fsSL https://raw.githubusercontent.com/anombyte93/atlas-session-lifecycle/main/install.sh | bash
```

Then run `/start` in any project.

---

## What It Does

AI coding assistants have no persistent memory between sessions. Every new conversation starts from zero. This creates three compounding problems:

- **No persistent memory** -- Context, decisions, and progress are lost between sessions
- **Project sprawl** -- Files accumulate at the project root with no organization
- **No lifecycle management** -- Projects have goals but no mechanism to track progress or verify completion

`/start` solves all three with a structured five-file memory bank, automatic file organization, and a soul purpose lifecycle that tracks your project from inception through completion.

---

## Quick Start

1. Install the skill:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/anombyte93/atlas-session-lifecycle/main/install.sh | bash
   ```

2. Run `/start` in any AI coding assistant project

3. Answer the questions to set your project's soul purpose

4. Continue working -- your session context is now persistent

---

## Features

### Session Memory Bank

Five files in `session-context/` give your AI persistent memory across sessions:

| File | Purpose |
|------|---------|
| `CLAUDE-activeContext.md` | Current session state, goals, and progress |
| `CLAUDE-decisions.md` | Architecture decisions and rationale |
| `CLAUDE-patterns.md` | Established code patterns and conventions |
| `CLAUDE-troubleshooting.md` | Common issues and proven solutions |
| `CLAUDE-soul-purpose.md` | Soul purpose definition and completion criteria |

### Auto-Detection Mode

```
/start
  |
  +-- session-context/ exists? --> Reconcile Mode
  |                                  +-- Validate & repair session files
  |                                  +-- Refresh project context
  |                                  +-- Self-assess soul purpose status
  |                                  +-- Offer: Continue / Close / Redefine
  |
  +-- No session-context/ -------> Init Mode
                                     +-- Capture soul purpose
                                     +-- Bootstrap 5-file memory bank
                                     +-- Organize root files
                                     +-- Generate project CLAUDE.md
```

### File Organization

Automatically organizes scattered root files into proper directories:
- `scripts/<category>/` -- Shell scripts, Python scripts, automation
- `docs/<category>/` -- Documentation, guides, reports
- `config/` -- Configuration files (JSON, YAML, TOML)
- `logs/` -- Log files

### Soul Purpose Lifecycle

Every project has a soul purpose -- the single objective it exists to achieve:

```
Define --> Work --> Reconcile --> Assess --> Close or Continue
  |                                |              |
  |                                |              +--> Harvest learnings
  |                                |              +--> Archive purpose
  |                                |              +--> Redefine (optional)
  |                                |
  |                                +--> Self-assess completion
  |                                +--> User decides (never AI)
  |
  +--> Captured during Init Mode
```

**Key invariant**: The AI never closes a soul purpose. It assesses and suggests; the user decides.

### Included Skills

- `/start` -- Main session lifecycle orchestrator
- `/stop` -- Session closure with context harvesting
- `/sync` -- Update session files with current progress
- `/stepback` -- Strategic reassessment for stuck debugging

---

## Configuration

### custom.md

Edit `custom.md` in the skill directory to modify behavior:

```markdown
## During Init
- After brainstorming, always suggest a git branching strategy
- Skip file organization for monorepo projects

## During Reconcile
- Check for uncommitted changes before assessing soul purpose
- If soul purpose mentions "API", verify endpoints are documented

## Always
- Keep tone direct and concise. No fluff.
- When creating session context entries, include the git branch name
```

---

## Requirements

- AI coding assistant (Claude Code, Cline, or compatible)
- Python 3.8+
- Git (optional -- enables `git mv` for tracked files)

---

## Repository

https://github.com/anombyte93/atlas-session-lifecycle

---

## License

MIT

---

## Version

3.0.0
