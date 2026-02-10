# claude-session-init

[![Claude Code Skill](https://img.shields.io/badge/Claude_Code-Skill-8A2BE2)](https://github.com/anombyte93/claude-session-init)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/anombyte93/claude-session-init/blob/main/LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/anombyte93/claude-session-init)](https://github.com/anombyte93/claude-session-init/stargazers)
[![GitHub last commit](https://img.shields.io/github/last-commit/anombyte93/claude-session-init)](https://github.com/anombyte93/claude-session-init/commits)
[![GitHub issues](https://img.shields.io/github/issues/anombyte93/claude-session-init)](https://github.com/anombyte93/claude-session-init/issues)

A Claude Code skill designed for vibe coders who have trouble organizing their folders and keeping track of their project state.

The skill bootstraps structured session context for any project. Initializes a memory bank system with templates, organizes messy project roots into clean directory structures, and generates/updates `CLAUDE.md` files.

## What It Does

1. **Asks your soul purpose** - Captures the project's core mission
2. **Detects environment** - Git status, existing files, current structure
3. **Bootstraps `session-context/`** - Memory bank with 5 template files for persistent context across sessions
4. **Scans & categorizes** - Auto-detects file types and proposes organization (scripts, docs, config, logs)
5. **Proposes organization map** - Shows you the plan before moving anything
6. **Executes file moves** - Uses `git mv` or `mv` as appropriate
7. **Generates/updates `CLAUDE.md`** - Project-specific instructions with structure maintenance rules
8. **Loads context** - Silently reads all session files and launches your workflow

## Memory Bank Templates

The skill uses 6 template files that get copied into each project:

| Template | Purpose |
|----------|---------|
| `CLAUDE-activeContext.md` | Current session state, goals, progress |
| `CLAUDE-decisions.md` | Architecture decision log (ADR format) |
| `CLAUDE-patterns.md` | Code patterns and conventions |
| `CLAUDE-soul-purpose.md` | Project soul purpose definition |
| `CLAUDE-troubleshooting.md` | Common issues and proven solutions |
| `CLAUDE-mdReference.md` | CLAUDE.md template (becomes the project's CLAUDE.md) |

## Installation

### Quick Install

```bash
# Clone the repo
git clone https://github.com/anombyte93/claude-session-init.git

# Run the install script
cd claude-session-init
./install.sh
```

### Manual Install

```bash
# 1. Copy the skill to your Claude Code skills directory
cp start.md ~/.claude/skills/start.md

# 2. Copy templates to a known location
mkdir -p ~/claude-session-init-templates
cp templates/* ~/claude-session-init-templates/

# 3. Update the template path in start.md
# Replace ~/Hermes/CLAUDE-templates/ with ~/claude-session-init-templates/
```

## Usage

From any project directory in Claude Code:

```
/start
/init
```

Or say:
- "bootstrap session"
- "initialize session"
- "organize project"

## How Session Context Works

After initialization, your project will have a `session-context/` directory:

```
your-project/
  CLAUDE.md                              # Project instructions for Claude Code
  session-context/
    CLAUDE-activeContext.md               # What you're working on now
    CLAUDE-decisions.md                   # Why you made architectural choices
    CLAUDE-patterns.md                    # Code conventions for this project
    CLAUDE-soul-purpose.md               # The project's core mission
    CLAUDE-troubleshooting.md            # Known issues and solutions
```

These files persist across Claude Code sessions. The skill reads them on startup so Claude picks up where you left off.

## File Organization

For projects with many files at root (>10), the skill proposes an organization:

| File Pattern | Target Directory |
|-------------|-----------------|
| `.sh`, `.bash`, `.ps1` | `scripts/<category>/` |
| `.py`, `.js`, `.ts` | `scripts/` or `src/` |
| Guides, READMEs | `docs/guides/` |
| Reports, audits | `docs/reports/` |
| `.json`, `.yaml`, `.toml` | `config/` |
| `.log` | `logs/` |

Scripts are further sub-categorized by name (ssh, setup, diagnostics, fixes, network).

Files that always stay at root: `CLAUDE.md`, `README.md`, `LICENSE`, `package.json`, `.gitignore`, `Dockerfile`, framework configs.

## Customization

Edit `start.md` after installation to:

- Change template paths
- Modify the category map for file organization
- Adjust which files stay at root
- Change the script subcategory detection patterns
- Remove or modify the Ralph Loop integration (Step 8)

## Requirements

- [Claude Code](https://claude.ai/code) CLI
- Git (optional, but recommended)

## License

MIT
