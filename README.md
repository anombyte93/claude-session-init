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

### Capability Inventory

When `/start` runs in Reconcile mode (or when you run `/sync --full`), it generates a comprehensive capability inventory:

- **MCP Tools**: All available tools with test coverage status
- **Security Claims**: Security-related features needing verification
- **Feature Claims**: What the project claims vs what's tested
- **Test Gaps**: Untested code identified by priority

The inventory lives in `session-context/CLAUDE-capability-inventory.md` and is used by `/research-before-coding` to identify what needs validation testing. Results are cached based on git HEAD, so regeneration only happens when your code changes.

### Stepback (bundled skill)

Also included: `/stepback` -- a strategic reassessment protocol for when debugging goes sideways. If you've hit the same error after 2+ fix attempts, `/stepback` forces you to zoom out:

1. Inventory all fix attempts and their assumptions
2. Find the common thread across failures
3. Research the architecture (mandatory Perplexity queries)
4. Test the broadest hypothesis first
5. Present symptom-level vs architecture-level fix options

Invoked separately via `/stepback` or `/atlas-session-lifecycle:stepback`.

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

Edit `custom.md` in the plugin root (or `~/.claude/skills/start/custom.md` for skill installs) to modify `/start` behavior. Write plain English instructions — no code needed. The AI reads these at each lifecycle phase and follows them.

Three headings control when your instructions apply:

```markdown
## During Init
- After brainstorming, always suggest a git branching strategy
- Skip file organization for monorepo projects
- Always ask about deployment target (local, cloud, edge)

## During Reconcile
- Check for uncommitted changes before assessing soul purpose
- If soul purpose mentions "API", verify endpoints are documented
- Always show a progress percentage estimate

## Always
- Keep tone direct and concise. No fluff.
- When creating session context entries, include the git branch name
- Never suggest closing a soul purpose unless all tests pass
```

**How it works**: The skill reads `custom.md` at specific points — during init (after session-context is bootstrapped), during reconcile (after reading context, before assessment), and always (both modes). Your instructions augment the default behavior; they don't replace the skill logic.

**Examples of what you can customize**:
- Tone and verbosity of responses
- Extra questions to ask during brainstorm
- Conditions for when to suggest soul purpose closure
- Project-specific checks during reconcile
- Integration with other tools or workflows

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
      SKILL.md                # Session lifecycle orchestrator
    stepback/
      SKILL.md                # Strategic reassessment for stuck debugging
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
