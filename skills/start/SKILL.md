---
name: start
description: "Session initialization and lifecycle management: bootstraps session context, organizes files, generates CLAUDE.md, manages soul purpose lifecycle with completion protocol and active context harvesting. Use when user says /start, /init, bootstrap session, initialize session, or organize project."
user-invocable: true
---

# Session Init & Lifecycle Skill

> User runs `/start`. Questions upfront. Everything else silent. Then seamlessly continue working.

All session operations use `atlas-session` MCP tools directly (prefixed `session_*` and `contract_*`). Use `ToolSearch` to discover them.

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
7. **Trust separation** — for bounty verify, spawn a separate finality Task agent. Never the same agent that submits.
8. **AtlasCoin is optional** — if the service is down, tell the user and continue without bounty tracking.

---

# INIT MODE

> Triggered when `session_preflight` returns `"mode": "init"`.

## Step 1: Preflight

1. Call `session_preflight(project_dir)` — get mode, git status, project signals, template validity.

## Step 2: Classify Brainstorm + File Organization

1. Call `session_classify_brainstorm(DIRECTIVE, project_signals)` — returns `{weight, has_directive, has_content}`.
2. Store `BRAINSTORM_WEIGHT` for Step 4.

**File organization** (only if `root_file_count > 15`):

Call `session_check_clutter(project_dir)`. If `status` is "cluttered", present the grouped move map:
- "Your project root has [N] misplaced files. Proposed cleanup: [summary]. Approve?"
- Options: "Yes, clean up", "Show details first", "Skip"
- If approved, execute moves via `git mv` (if `is_git`) or file operations.

## Step 3: Silent Bootstrap

1. Call `session_init(project_dir, DIRECTIVE_OR_PENDING)`
2. Call `session_ensure_governance(project_dir)`
3. Call `session_cache_governance(project_dir)`
4. Run `/init` (Claude Code built-in — refreshes CLAUDE.md. Must run in main thread.)
5. Call `session_restore_governance(project_dir)`
6. Read `custom.md` if it exists, follow instructions under "During Init".

## Step 4: Brainstorm + Activate + Continuation

**Brainstorm runs first (always)**:

Invoke `skill: "superpowers:brainstorming"` with weight from Step 2:
- **lightweight**: Args include instruction: "Lightweight brainstorm. Confirm direction with 1-2 questions, derive soul purpose. No design doc."
- **standard**: Normal brainstorm flow, skip design doc if task is clear.
- **full**: Complete brainstorm flow including design doc.

After brainstorm completes:

1. Call `session_archive(project_dir, DIRECTIVE_OR_PENDING, DERIVED_SOUL_PURPOSE)` — sets the real soul purpose.
2. Call `session_hook_activate(project_dir, DERIVED_SOUL_PURPOSE)` — enables stop hook warnings.
3. Check `session_features_read(project_dir)` — extract any feature claims for tracking.

**Bounty creation** (optional):

Call `contract_health()`. If healthy, call `contract_create(project_dir, DERIVED_SOUL_PURPOSE, escrow, criteria)` using `contract_draft_criteria` for suggestions.

Default escrow: 100. Increase for complex soul purposes at AI's discretion.

If AtlasCoin is down, tell user and continue without bounty.

### Before Starting Work (MANDATORY)

1. Count independent tasks in the soul purpose.
2. If 2+ independent tasks:
   - `TeamCreate("{project}-work")` — assign directory-level file ownership per teammate
   - Lead coordinates via SendMessage — does NOT implement
   - On completion: `SendMessage(type: "shutdown_request")` then `TeamDelete`
3. If single task: proceed without team.
4. NEVER spawn ad-hoc background Task agents for implementation.
5. Invoke `superpowers:test-driven-development` if soul purpose involves code.
6. Invoke `superpowers:writing-plans` if soul purpose has 3+ steps.

### Ralph Loop Invocation

After brainstorm and activation, invoke `/ralph-go` with the derived soul purpose:

```
Skill(skill: "ralph-go", args: "DERIVED_SOUL_PURPOSE")
```

`/ralph-go` handles its own questions (deliverable type, done criteria, size), runs research, calibrates iterations, and launches the loop. No additional configuration needed from `/start`.

**CRITICAL**: You must call the `Skill` tool — not just mention it in text.

---

# RECONCILE MODE

> Triggered when `session_preflight` returns `"mode": "reconcile"`.
>
> **UX**: Everything in Steps 1-2 is invisible to the user. First visible interaction is a question (Step 3) or seamless work continuation (Step 4).

## Step 0: Sync Previous State

Before any assessment, save the current session state so context files reflect reality:

1. Invoke `/sync` — updates all session-context files and MEMORY.md with current progress.
2. This is silent — no output shown to user.

## Step 1: Silent Assessment + Context Reality Check

1. Call `session_validate(project_dir)` — repair any missing session files.
2. Call `session_cache_governance(project_dir)`
3. Run `/init` in main thread.
4. Call `session_restore_governance(project_dir)`
5. Call `session_read_context(project_dir)` — get soul purpose, open tasks, Ralph config, status hint.
6. Call `session_git_summary(project_dir)` — get recent commits, changed files, branch state.
7. **Compare** `read_context` against `git_summary`: if context is stale (commits exist that aren't reflected in active context), update `session-context/CLAUDE-activeContext.md` with real progress.
8. Check capability inventory: call `session_capability_inventory(project_dir)`.
   - If `cache_hit == True` and `git_changed == False`: inventory is current.
   - If `needs_generation == True`: inventory requires generation. The MCP tool returns `inventory_path` when ready.
9. Read `CLAUDE-capability-inventory.md` if it exists. Extract untested code, security claims, and feature claims with gaps.
10. Check bounty: if `session-context/BOUNTY_ID.txt` exists, call `contract_get_status(project_dir)`.
11. Read `custom.md` if it exists, follow instructions under "During Reconcile".

### Root Cleanup

If `root_file_count > 15` from preflight: call `session_check_clutter(project_dir)`.
If cluttered, present move map to user (same flow as Init Step 2).

## Step 2: Directive + Features + Self-Assessment

**If DIRECTIVE is non-empty (3+ words) AND `status_hint` is `no_purpose`**:
- Call `session_archive(project_dir, "(pending)", DIRECTIVE)` to set soul purpose
- Skip Step 3, go to Step 4 with lightweight brainstorm

**If DIRECTIVE is non-empty (3+ words) AND soul purpose exists**:
- Skip Step 3, go to Step 4 — work on directive (overrides for this session)

**Otherwise** (no directive):

1. Call `session_features_read(project_dir)` — check feature claim status.
2. Using `read_context` + `features_read` + `git_summary`, classify:
   - `clearly_incomplete`: open tasks non-empty, active blockers, criteria not met
   - `probably_complete`: no open tasks, artifacts exist, criteria met
   - `uncertain`: mixed signals

## Step 3: User Interaction (conditional)

**If `clearly_incomplete`**: No questions. Skip to Step 4.

**If `probably_complete` or `uncertain`**:
Ask ONE question: "Soul purpose: '[text]'. [1-2 sentence assessment]. [Bounty: active/none]. What would you like to do?"
- Options: "Continue", "Verify first", "Close", "Redefine"
- **"Verify first"**: Invoke `superpowers:verification-before-completion`, fold findings into re-presented question.
- **"Close"**: Run Settlement Flow below.
- **"Redefine"**: Ask for new purpose, then run Settlement Flow with new purpose.

## Step 4: Continuation

Transition directly into work. No "session reconciled" message.

- **DIRECTIVE provided**: Begin working on directive.
- **Soul purpose redefined**: Begin working on new purpose.
- **`clearly_incomplete`**: Pick up where last session left off using active context.
- **No active soul purpose**: Ask user what to work on, set as new soul purpose via `session_archive`.

### Before Starting Work (MANDATORY)

1. Count independent tasks in the soul purpose.
2. If 2+ independent tasks:
   - `TeamCreate("{project}-work")` — assign directory-level file ownership per teammate
   - Lead coordinates via SendMessage — does NOT implement
   - On completion: `SendMessage(type: "shutdown_request")` then `TeamDelete`
3. If single task: proceed without team.
4. NEVER spawn ad-hoc background Task agents for implementation.
5. Invoke `superpowers:test-driven-development` if soul purpose involves code.
6. Invoke `superpowers:writing-plans` if soul purpose has 3+ steps.

### Ralph Loop Invocation (Reconcile)

Check if a Ralph Loop is already active:

```bash
test -f ~/.claude/ralph-loop.local.md && echo "active" || echo "inactive"
```

If inactive, invoke `/ralph-go` with the soul purpose:

```
Skill(skill: "ralph-go", args: "SOUL_PURPOSE")
```

---

# SETTLEMENT FLOW

> Triggered when user chooses "Close" in Reconcile Step 3.

Read `custom.md` if it exists, follow instructions under "During Settlement".

## Step 1: Harvest + Promote

1. Call `session_harvest(project_dir)`.
2. If promotable content exists, assess what to promote (decisions need rationale, patterns must be reusable, troubleshooting must have verified solutions). Present to user for approval.
3. After approval, append promoted content to target files via Edit tool.

## Step 2: Feature Verification

1. Call `session_features_read(project_dir)`.
2. If pending features exist, run their proofs (shell commands, file checks).
3. Update feature status in `CLAUDE-features.md`.

## Step 3: Code Review Gate

1. Invoke `superpowers:verification-before-completion` — run doubt review on recent changes.
2. If critical issues found, present to user: "Fix issues first" / "Close anyway" / "Continue working".
3. Invoke `superpowers:requesting-code-review` before PR creation.

## Step 4: Deactivate Hook

Call `session_hook_deactivate(project_dir)` — removes `.lifecycle-active.json`.

## Step 5: PR Creation

1. Push current branch: `git push -u origin HEAD`
2. Create PR: `gh pr create --title "..." --body "..."` with review summary.
3. Return PR URL to user.

## Step 6: Bounty Settlement (if bounty exists)

1. Call `contract_run_tests(project_dir)` — execute all criteria.
2. If tests pass, call `contract_submit(project_dir)`.
3. Spawn a single finality Task agent: `Task(subagent_type: "general-purpose", prompt: "You are finality-agent. Verify bounty [ID] independently. Call contract_verify. Report pass/fail.")`
4. Wait for finality result.
5. If verified: call `contract_settle(project_dir)`. Tell user tokens earned.
6. If failed: present to user — "Fix and re-verify" / "Close anyway (forfeit)" / "Continue working".

## Step 7: Archive + Cleanup

1. Call `session_archive(project_dir, OLD_PURPOSE, NEW_PURPOSE)` — archive soul purpose, reset active context.
2. Remove Ralph Loop indicator: `rm -f ~/.claude/ralph-loop.local.md`
3. Tell user: "Session closed. Soul purpose '[text]' archived." (Include token info if bounty settled.)

---

# Customizations

> Create or edit `custom.md` in the plugin root directory.

The AI reads `custom.md` at each lifecycle phase:
- **During Init**: After session-context is bootstrapped (Step 3)
- **During Reconcile**: After read-context, before assessment (Step 1)
- **During Settlement**: Before harvest + archive (Settlement Step 1)
- **Always**: Applied in all modes
