# Atlas Session Lifecycle

[![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)](https://github.com/anombyte93/atlas-session-lifecycle/releases) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT) [![GitHub stars](https://img.shields.io/github/stars/anombyte93/atlas-session-lifecycle)](https://github.com/anombyte93/atlas-session-lifecycle/stargazers) [![Last Commit](https://img.shields.io/github/last-commit/anombyte93/atlas-session-lifecycle)](https://github.com/anombyte93/atlas-session-lifecycle/commits/main) [![GitHub Issues](https://img.shields.io/github/issues/anombyte93/atlas-session-lifecycle)](https://github.com/anombyte93/atlas-session-lifecycle/issues)

Persistent project memory and session lifecycle management for Claude Code.

> **Featured in**: [I just delivered on a $30,000 contract thanks to Claude Code](https://www.reddit.com/r/ClaudeAI/comments/1r0n1qz/i_just_delivered_on_a_30000_contract_thanks_to/) (r/ClaudeAI)

---

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/anombyte93/atlas-session-lifecycle/main/install.sh | bash
```

Then run `/start` in any Claude Code project.

---

## What It Does

Claude Code has no persistent memory between sessions. Every new conversation starts from zero. This creates three compounding problems:

- **No persistent memory** -- Context, decisions, and progress are lost between sessions. You re-explain the same things every time.
- **Project sprawl** -- Files accumulate at the project root with no organization. Scripts, docs, configs, and logs pile up across sessions.
- **No lifecycle management** -- Projects have goals, but no mechanism to track progress, verify completion, or transition to new objectives.

`/start` solves all three with a structured five-file memory bank, automatic file organization, and a soul purpose lifecycle that tracks your project from inception through completion.

---

## How It Works

`/start` auto-detects which mode to run based on directory state:

```
/start
  |
  +-- session-context/ exists? --> Reconcile Mode
  |                                  +-- Validate & repair session files
  |                                  +-- Refresh CLAUDE.md via /init
  |                                  +-- Self-assess soul purpose status
  |                                  +-- Offer: Continue / Close / Redefine
  |                                  +-- Harvest learnings on closure
  |
  +-- No session-context/ -------> Init Mode
                                     +-- Capture soul purpose
                                     +-- Bootstrap 5-file memory bank
                                     +-- Organize root files
                                     +-- Generate CLAUDE.md
                                     +-- Onboard Ralph Loop
```

### Init Mode (first run)

Triggered when `session-context/` does not exist.

- Captures your project's **soul purpose** -- the single objective this project exists to achieve
- Detects environment (git status, existing files, tech stack)
- Bootstraps `session-context/` with 5 memory bank files from immutable templates
- Scans root-level files and proposes an organization map (scripts, docs, config, logs)
- Generates or updates `CLAUDE.md` with project structure and governance sections
- Onboards Ralph Loop (automatic, manual, or skip)

### Reconcile Mode (returning)

Triggered when `session-context/` already exists.

- Validates and repairs session files from templates if corrupted
- Runs Claude's `/init` to refresh `CLAUDE.md` from current codebase state
- Reads soul purpose and active context to understand where you left off
- Self-assesses soul purpose completion (clearly incomplete, probably complete, uncertain)
- Presents lifecycle decision: **Continue**, **Close**, or **Redefine** soul purpose
- Harvests durable knowledge on closure -- promotes decisions, patterns, and troubleshooting entries

---

## Session Memory Bank

Five files in `session-context/` give Claude persistent memory across sessions:

| File | Purpose |
|------|---------|
| `CLAUDE-activeContext.md` | Current session state, goals, and progress |
| `CLAUDE-decisions.md` | Architecture decisions and rationale |
| `CLAUDE-patterns.md` | Established code patterns and conventions |
| `CLAUDE-troubleshooting.md` | Common issues and proven solutions |
| `CLAUDE-soul-purpose.md` | Soul purpose definition and completion criteria |

All files use a structured entry format with timestamps, 5W1H context, git references, and potential issues.

---

## Soul Purpose Lifecycle

Every project has a soul purpose -- the single objective it exists to achieve.

```
Define --> Work --> Reconcile --> Assess --> Close or Continue
  |                                |              |
  |                                |              +--> Harvest learnings
  |                                |              +--> Archive purpose
  |                                |              +--> Redefine (optional)
  |                                |
  |                                +--> Self-assess completion
  |                                +--> Optional doubt agent verification
  |                                +--> User decides (never AI)
  |
  +--> Captured during Init Mode
```

**Key invariant**: The AI never closes a soul purpose. It assesses and suggests; the user decides.

---

## Installation

### One-liner (skill mode, default)

```bash
curl -fsSL https://raw.githubusercontent.com/anombyte93/atlas-session-lifecycle/main/install.sh | bash
```

Installs to `~/.claude/skills/start/`. The SKILL.md orchestrator and `session-init.py` script are placed together.

### Plugin mode

```bash
curl -fsSL https://raw.githubusercontent.com/anombyte93/atlas-session-lifecycle/main/install.sh | bash -s -- --plugin
```

Installs to `~/.claude/plugins/atlas-session-lifecycle/` with full plugin structure including `plugin.json`.

### Manual install

```bash
git clone https://github.com/anombyte93/atlas-session-lifecycle.git
cd atlas-session-lifecycle
./install.sh
```

Or copy files directly:

```bash
mkdir -p ~/.claude/skills/start
cp skills/start/SKILL.md ~/.claude/skills/start/SKILL.md
cp scripts/session-init.py ~/.claude/skills/start/session-init.py
chmod +x ~/.claude/skills/start/session-init.py
mkdir -p ~/claude-session-init-templates
cp templates/* ~/claude-session-init-templates/
```

### Version toggle

```bash
# Install v1 (monolithic SKILL.md, no script)
./install.sh --version v1

# Revert from v2 back to v1 (backs up v2 files first)
./install.sh --revert

# Pull latest version and reinstall
./install.sh --update
```

### Auto-update

The installer records a last-checked timestamp. On each run, if more than 24 hours have passed since the last check, it queries GitHub for newer releases and prompts you to update.

---

## Configuration

### custom.md

Create a `custom.md` file in the plugin root to modify `/start` behavior without editing the skill itself. Instructions are plain English under three headings:

```markdown
## During Init
- (your init-phase customizations)

## During Reconcile
- (your reconcile-phase customizations)

## Always
- (applied in both modes)
```

### Ralph Loop

During Init, the skill asks how Ralph Loop should operate:

- **Automatic** -- starts Ralph Loop after setup with configurable intensity (small, medium, long)
- **Manual** -- user triggers each iteration explicitly
- **Skip** -- no Ralph Loop

The preference is stored in `CLAUDE.md` and respected on subsequent Reconcile runs.

---

## Upgrading from v1

v2 is a backward-compatible evolution. Your existing `session-context/` files, templates, and project structure are unchanged.

The main difference: v1 was a single 867-line SKILL.md where Claude interpreted all operations from prose. v2 extracts deterministic operations into `session-init.py` (9 JSON-outputting subcommands), reducing SKILL.md to a slim orchestrator. The user experience is identical.

To revert at any time:

```bash
./install.sh --revert
```

---

## Plugin Structure

```
atlas-session-lifecycle/
  .claude-plugin/
    plugin.json               # Plugin metadata (name, version, keywords)
  skills/
    start/
      SKILL.md                # AI orchestrator (questions, judgment, continuation)
  scripts/
    session-init.py           # Deterministic ops (9 JSON-outputting subcommands)
  custom.md                   # User customization hook (plain English)
  templates/
    CLAUDE-activeContext.md
    CLAUDE-decisions.md
    CLAUDE-mdReference.md
    CLAUDE-patterns.md
    CLAUDE-soul-purpose.md
    CLAUDE-troubleshooting.md
  v1/
    SKILL.md                  # v1 monolithic skill (867 lines)
  install.sh                  # Installer with version toggle and auto-update
  README.md
  LICENSE
  CONTRIBUTING.md
  CODE_OF_CONDUCT.md
  SECURITY.md
```

---

## Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) CLI
- Python 3.8+
- Git (optional -- enables `git mv` for tracked files during organization)

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## License

[MIT](LICENSE)
