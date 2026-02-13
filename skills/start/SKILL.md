---
name: start
description: "Session initialization and lifecycle management: bootstraps session context, organizes files, generates CLAUDE.md, manages soul purpose lifecycle with completion protocol and active context harvesting. Use when user says /start, /init, bootstrap session, initialize session, or organize project."
user-invocable: true
---

# Session Init & Lifecycle Skill

> User runs `/start`. Questions upfront. Everything else silent. Then seamlessly continue working.

**Script path** (resolved at load time):

!`if [ -n "$CLAUDE_PLUGIN_ROOT" ] && [ -f "$CLAUDE_PLUGIN_ROOT/scripts/session-init.py" ]; then echo "$CLAUDE_PLUGIN_ROOT/scripts/session-init.py"; elif p=$(find ~/.claude/plugins -path '*/atlas-session-lifecycle/scripts/session-init.py' -type f 2>/dev/null | head -1) && [ -n "$p" ]; then echo "$p"; elif [ -f ~/.claude/skills/start/session-init.py ]; then echo "$HOME/.claude/skills/start/session-init.py"; else echo 'NOT_FOUND'; fi`

Use the resolved path above as `SESSION_SCRIPT` for all script invocations below.
All commands output JSON. AI only handles judgment calls (questions, assessment, continuation).

## Directive Capture

Capture any text after `/start` as `DIRECTIVE`. If empty, the soul purpose is the directive.
The skill NEVER finishes with "ready to go" and stops. After setup, immediately begin working.

## UX Contract (MANDATORY)

1. **NEVER announce step names** — no "Init Step 1", no "Wave 2"
2. **NEVER narrate internal process** — no "Detecting environment..."
3. **NEVER explain what you're about to do** — just ask questions, then do it silently
4. **User sees ONLY**: questions and seamless continuation into work
5. **Batch questions** — as few rounds as possible
6. **No "done" message that stops** — after setup, immediately begin working

## Hard Invariants

1. **User authority is absolute** — AI NEVER closes a soul purpose. Only suggests; user decides.
2. **Zero unsolicited behavior** — Skill ONLY runs when user types `/start`.
3. **Human-visible memory only** — All state lives in files.
4. **Idempotent** — Safe to run multiple times.
5. **Templates are immutable** — NEVER edit bundled template files.
6. **NEVER** auto-invoke doubt agent. Only offer it.

---

# INIT MODE

> Triggered when preflight returns `"mode": "init"`.

## Step 1: Silent Pre-flight

```bash
python3 SESSION_SCRIPT preflight
```

Returns JSON with: `mode`, `is_git`, `has_claude_md`, `root_file_count`, `templates_valid`, `template_count`, `project_signals`.
If `templates_valid` is false, STOP with error. Set internal flags from JSON. No output to user.

## Step 2: Soul Purpose via Brainstorm

### Determine brainstorm weight

Using `DIRECTIVE` and `project_signals` from preflight, classify the brainstorm weight:

| Condition | Weight | Brainstorm Behavior |
|-----------|--------|---------------------|
| DIRECTIVE has 3+ words AND project has code/readme | **lightweight** | 1-2 quick clarifying questions, confirm direction, produce soul purpose |
| DIRECTIVE has 3+ words AND empty project | **standard** | Explore what to build, 3-5 questions, produce soul purpose + approach |
| No directive AND project has readme/code | **lightweight** | Present what you see in project_signals, ask 1-2 questions to focus the session |
| No directive AND empty project | **full** | Full brainstorm — purpose, constraints, approach, design |

### Build brainstorm context

Construct a brainstorm prompt using available signals:

- If `readme_excerpt` exists: include it as "Project context: [excerpt]"
- If `package_name`/`package_description` exist: include as "This is [name]: [description]"
- If `detected_stack` is non-empty: include as "Stack: [stack]"
- If `DIRECTIVE` exists: include as "User wants to: [directive]"
- If none of the above: "Empty project, no existing context"

### Ask Ralph question (quick, before brainstorm)

Use AskUserQuestion with 1-2 questions (Question 2 only if Ralph = Automatic):

**Question 1**: "How should Ralph Loop work?"
- Options: "Automatic", "Manual", "Skip"

**Question 2** (only if Ralph = Automatic): "What intensity?"
- Options: "Small (5 iterations)", "Medium (20 iterations)", "Long (100 iterations + PRD)"

Store as `RALPH_MODE`, `RALPH_INTENSITY` (default to "Small" if Automatic but no intensity given).

The brainstorm itself runs AFTER silent execution (Step 3) so session-context exists.
Store `BRAINSTORM_WEIGHT` and `BRAINSTORM_CONTEXT` for use in Step 4.

### File organization (only if `root_file_count > 10`)

Use an Explore agent to scan root files and propose a move map. Present to user for approval.
If approved, use a Bash agent to execute `mkdir -p` + `git mv`/`mv` operations.
If skipped or root_file_count <= 10: no file moves.

## Step 3: Silent Execution

Run these commands sequentially. **ZERO output to user.**

Note: Soul purpose is not yet known — it will be derived via brainstorm in Step 4. Use DIRECTIVE as the initial soul purpose if available, otherwise use "(Pending brainstorm)".

```bash
# 1. Bootstrap session-context + seed active context
python3 SESSION_SCRIPT init \
  --soul-purpose "DIRECTIVE_OR_PENDING" \
  --ralph-mode "RALPH_MODE" \
  --ralph-intensity "RALPH_INTENSITY"

# 2. Ensure CLAUDE.md has all governance sections
python3 SESSION_SCRIPT ensure-governance \
  --ralph-mode "RALPH_MODE" \
  --ralph-intensity "RALPH_INTENSITY"

# 3. Cache governance before /init
python3 SESSION_SCRIPT cache-governance
```

Then run `/init` in main thread (Claude command to refresh CLAUDE.md).

```bash
# 4. Restore governance if /init removed sections
python3 SESSION_SCRIPT restore-governance
```

**Then read the plugin's `custom.md`** if it exists (find it next to the script directory), and follow any instructions under "During Init".

## Step 4: Brainstorm + Continuation

Transition directly into work. No "session initialized" message.

**Brainstorm runs first (always)**:

Invoke brainstorming with the weight and context determined in Step 2:

- **lightweight**: Invoke `skill: "superpowers:brainstorming"` with args containing the `BRAINSTORM_CONTEXT` + instruction: "This is a lightweight brainstorm. Confirm direction with 1-2 questions, derive a soul purpose statement, then transition to work. Do NOT write a design doc for lightweight brainstorms."
- **standard**: Invoke `skill: "superpowers:brainstorming"` with args containing the `BRAINSTORM_CONTEXT`. Follow normal brainstorm flow but skip design doc if the task is clear enough.
- **full**: Invoke `skill: "superpowers:brainstorming"` with full `BRAINSTORM_CONTEXT` args. Follow complete brainstorm flow including design doc.

After brainstorm completes, write the derived soul purpose via:

```bash
python3 SESSION_SCRIPT archive \
  --old-purpose "DIRECTIVE_OR_PENDING" \
  --new-purpose "DERIVED_SOUL_PURPOSE"
```

Replace `DERIVED_SOUL_PURPOSE` with the soul purpose text produced by the brainstorm.

Then continue:

- **If RALPH_MODE = "automatic"**: Start Ralph Loop using the intensity-based invocation below.
- **Otherwise**: Begin working on the derived soul purpose.

### Ralph Loop Invocation (Init)

When `RALPH_MODE = "automatic"`, you MUST use the `Skill` tool to actually start the Ralph Loop.
Construct the invocation based on `RALPH_INTENSITY`:

| Intensity | Skill tool call |
|-----------|----------------|
| **Small** | `skill: "ralph-wiggum:ralph-loop"`, `args: "SOUL_PURPOSE --max-iterations 5 --completion-promise 'Soul purpose fulfilled'"` |
| **Medium** | `skill: "ralph-wiggum:ralph-loop"`, `args: "SOUL_PURPOSE --max-iterations 20 --completion-promise 'Soul purpose fulfilled and code tested'"` |
| **Long** | First invoke `skill: "prd-taskmaster"`, `args: "SOUL_PURPOSE"`. Wait for PRD completion. THEN invoke `skill: "ralph-wiggum:ralph-loop"`, `args: "SOUL_PURPOSE --max-iterations 100 --completion-promise 'Must validate sequentially with 3x doubt agents and 1x finality agent'"` |

Replace `SOUL_PURPOSE` with the derived soul purpose text. Quote the full prompt if it contains spaces.

**CRITICAL**: You must call the `Skill` tool — not just mention it in text. The Ralph Loop only activates when `setup-ralph-loop.sh` runs via the Skill tool invocation.

---

# RECONCILE MODE

> Triggered when preflight returns `"mode": "reconcile"`.

**CRITICAL UX REMINDER**: Everything in Steps 1-2 is invisible to the user. Do NOT output "Running reconcile mode", "Assessing context", "Reading soul purpose", or ANY description of what you are doing. The user's first visible interaction is either a question (Step 3) or seamless continuation into work (Step 4). Nothing before that.

## Step 1: Silent Assessment

Run these commands sequentially. **NO output to user.**

```bash
# 1. Validate session files (repair from templates if needed)
python3 SESSION_SCRIPT validate

# 2. Cache governance before /init
python3 SESSION_SCRIPT cache-governance
```

Run `/init` in main thread.

```bash
# 3. Restore governance
python3 SESSION_SCRIPT restore-governance

# 4. Read soul purpose + active context
python3 SESSION_SCRIPT read-context

```

Returns JSON with: `soul_purpose`, `has_archived_purposes`, `active_context_summary`, `open_tasks`, `recent_progress`, `status_hint`, `ralph_mode`, `ralph_intensity`.

**Then read the plugin's `custom.md`** if it exists, and follow any instructions under "During Reconcile".

## Step 2: Directive Check + Self-Assessment

**If DIRECTIVE is non-empty (3+ words) AND `status_hint` is `no_purpose`**:
- Set soul purpose to DIRECTIVE via archive command
- Skip Step 3, go to Step 4 with a lightweight brainstorm to confirm direction

**If DIRECTIVE is non-empty (3+ words) AND soul purpose exists**:
- Skip Step 3, go to Step 4 — work on directive (it overrides for this session)

**Otherwise** (no directive): Proceed with self-assessment below.

Using the `read-context` JSON output, classify:

| Classification | Criteria |
|---------------|----------|
| `clearly_incomplete` | open_tasks non-empty, active blockers, criteria not met |
| `probably_complete` | No open tasks, artifacts exist, criteria met |
| `uncertain` | Mixed signals |

## Step 3: User Interaction (conditional)

### If `clearly_incomplete`:
No questions. Skip to continuation.

### If `probably_complete` or `uncertain`:
Ask ONE question combining assessment and decision:

"Soul purpose: '[purpose text]'. [1-2 sentence assessment]. What would you like to do?"
- Options: "Continue", "Verify first", "Close", "Redefine"

**If "Verify first"**: Dispatch doubt-agent, fold findings into re-presented question (without "Verify first" option).

**If "Close" or "Redefine"**: Run harvest + archive:

```bash
# Check for promotable content
python3 SESSION_SCRIPT harvest
```

If harvest returns content, AI assesses what to promote (judgment call — decisions need rationale, patterns must be reused, troubleshooting must have verified solutions). Present to user for approval. After approval, append promoted content to target files via Edit tool.

```bash
# Archive old purpose, optionally set new one
python3 SESSION_SCRIPT archive \
  --old-purpose "OLD_PURPOSE_TEXT" \
  --new-purpose "NEW_PURPOSE_TEXT"  # omit for close-without-redefine
```

**If "Close" without new purpose**: Ask if user wants to set a new soul purpose. If declined, the archive command writes "(No active soul purpose)".

## Step 4: Continuation

Transition directly into work. No "session reconciled" message.

- **If DIRECTIVE provided**: Begin working on directive.
- **If `ralph_mode` = "automatic"** (from `read-context` JSON): Check if Ralph Loop should start — see "Ralph Loop Invocation (Reconcile)" below.
- **If soul purpose just redefined**: Begin working on new purpose.
- **If `clearly_incomplete`**: Pick up where last session left off using active context.
- **If no active soul purpose**: Ask user what to work on, write as new soul purpose via archive command.
- **Otherwise**: Resume work using active context as guide.

### Ralph Loop Invocation (Reconcile)

When `ralph_mode` from `read-context` is "automatic", first check if Ralph Loop is already active:

```bash
test -f ~/.claude/ralph-loop.local.md && echo "active" || echo "inactive"
```

- **If active**: Skip invocation. Ralph Loop is already running or was already set up this session.
- **If inactive**: Use the `Skill` tool to start Ralph Loop. Read `ralph_intensity` from the `read-context` JSON and use the same intensity table as Init mode:

| Intensity | Skill tool call |
|-----------|----------------|
| **Small** | `skill: "ralph-wiggum:ralph-loop"`, `args: "SOUL_PURPOSE --max-iterations 5 --completion-promise 'Soul purpose fulfilled'"` |
| **Medium** | `skill: "ralph-wiggum:ralph-loop"`, `args: "SOUL_PURPOSE --max-iterations 20 --completion-promise 'Soul purpose fulfilled and code tested'"` |
| **Long** | First invoke `skill: "prd-taskmaster"`, `args: "SOUL_PURPOSE"`. Wait for PRD completion. THEN invoke `skill: "ralph-wiggum:ralph-loop"`, `args: "SOUL_PURPOSE --max-iterations 100 --completion-promise 'Must validate sequentially with 3x doubt agents and 1x finality agent'"` |

Replace `SOUL_PURPOSE` with the actual soul purpose text from `read-context` JSON.

**CRITICAL**: You must call the `Skill` tool — not just mention it in text. The Ralph Loop only activates when `setup-ralph-loop.sh` runs via the Skill tool invocation.

---

# Script Reference

All commands output JSON. Run from project root.

| Command | Purpose |
|---------|---------|
| `preflight` | Detect mode, git, CLAUDE.md, templates, session files |
| `init --soul-purpose "..." --ralph-mode "..." --ralph-intensity "..."` | Bootstrap session-context, seed active context |
| `validate` | Check/repair session files from templates |
| `cache-governance` | Cache governance sections from CLAUDE.md to /tmp |
| `restore-governance` | Restore cached governance sections after /init |
| `ensure-governance --ralph-mode "..." --ralph-intensity "..."` | Add missing governance sections to CLAUDE.md |
| `read-context` | Read soul purpose + active context summary |
| `harvest` | Scan active context for promotable content |
| `archive --old-purpose "..." [--new-purpose "..."]` | Archive soul purpose, reset active context |


---

# Customizations

> To customize `/start` behavior, create or edit `custom.md` in the plugin root directory.

The AI reads `custom.md` at each lifecycle phase and follows matching instructions:
- **During Init**: After session-context is bootstrapped (Step 3)
- **During Reconcile**: After read-context, before assessment (Step 1-2)
- **Always**: Applied in both modes

To customize, just write what you want in English under the relevant heading. No code needed.
