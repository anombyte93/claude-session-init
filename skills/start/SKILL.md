---
name: start
description: "Session initialization and lifecycle management: bootstraps session context, organizes files, generates CLAUDE.md, manages soul purpose lifecycle with completion protocol, feature contract extraction, and active context harvesting. Use when user says /start, /init, bootstrap session, initialize session, or organize project."
user-invocable: true
---

# Session Init & Lifecycle Skill

> User runs `/start`. Questions upfront. Everything else silent. Then seamlessly continue working.

**Plugin root** (resolved at load time):

!`if [ -n "$CLAUDE_PLUGIN_ROOT" ]; then echo "$CLAUDE_PLUGIN_ROOT"; elif p=$(find ~/.claude/plugins -path '*/atlas-session-lifecycle/scripts/session-init.py' -type f 2>/dev/null | head -1) && [ -n "$p" ]; then dirname "$(dirname "$p")"; elif [ -f ~/.claude/skills/start/session-init.py ]; then echo "$HOME/.claude/skills/start"; else echo 'NOT_FOUND'; fi`

Use the resolved path above as `PLUGIN_ROOT`.

**AtlasCoin URL** (resolved at load time):

!`if [ -n "$ATLASCOIN_URL" ]; then echo "$ATLASCOIN_URL"; else echo "http://localhost:3002"; fi`

Use the resolved URL above as `ATLASCOIN_URL`.

All session operations use atlas-session MCP tools directly. AI only handles judgment calls (questions, assessment, continuation).

## Zai MCP Integration (Optional Cost Optimization)

When the Zai MCP server is configured, expensive operations are delegated to cheap GLM agents (~10x cheaper than Claude Max). **Zai is optional** — if unavailable, everything falls back to built-in skills and Task agents.

**Detection**: At the start of Init or Reconcile, check if `mcp__zaiMCP__zai_spawn_agent` is available via ToolSearch. Store result as `ZAI_AVAILABLE` (boolean).

**Zai tools** (when available):

| Tool | Purpose |
|------|---------|
| `mcp__zaiMCP__zai_spawn_agent` | Spawn a background agent (task, isolation, model, timeout_minutes) |
| `mcp__zaiMCP__zai_agent_status` | Check agent progress (agent_id) |
| `mcp__zaiMCP__zai_agent_result` | Get completed agent output (agent_id) |
| `mcp__zaiMCP__zai_list_agents` | List all active/recent agents |
| `mcp__zaiMCP__zai_cancel_agent` | Cancel a running agent (agent_id) |

**Isolation modes**: `worktree` (code changes in isolated branch), `shared` (read-only access to current files), `sandboxed` (temp directory).

**Models**: `claude-3-5-haiku-20241022` (fastest/cheapest, maps to GLM flash), `claude-3-5-sonnet-20241022` (more capable, maps to GLM 4.7).

### Zai Delegation Rules

| Operation | With Zai | Without Zai (fallback) |
|-----------|----------|----------------------|
| Brainstorming | Spawn Zai agent with `shared` isolation + brainstorm context | Use `superpowers:brainstorming` skill |
| Implementation work | Spawn Zai agent with `worktree` isolation per task | Use Claude Task agents via TeamCreate |
| Research | Spawn Zai agent with `shared` isolation | Use Task agent with Explore subagent_type |
| Session operations | Always direct MCP (never Zai) | Always direct MCP |
| User decisions | Always main Claude (never Zai) | Always main Claude |

### Zai Brainstorm Pattern

When `ZAI_AVAILABLE` is true and brainstorm weight is **standard** or **full**:

1. Call `mcp__zaiMCP__zai_spawn_agent` with:
   - `task`: "You are a brainstorming assistant. Given this context: [BRAINSTORM_CONTEXT]. Generate: 1) A clear soul purpose statement, 2) Key constraints and trade-offs, 3) Recommended approach with alternatives. Output as structured markdown."
   - `isolation`: "shared"
   - `model`: "claude-3-5-sonnet-20241022" (use capable model for brainstorming)
   - `timeout_minutes`: 10
2. Poll `mcp__zaiMCP__zai_agent_status` until complete
3. Get result via `mcp__zaiMCP__zai_agent_result`
4. Present Zai's brainstorm output to user for refinement
5. AI (main Claude) makes the final judgment call on soul purpose

For **lightweight** brainstorms, skip Zai — main Claude handles directly (1-2 quick questions, minimal cost).

### Zai Work Execution Pattern

When `ZAI_AVAILABLE` is true and work requires implementation:

1. Instead of `TeamCreate` + Claude Task agents, spawn Zai agents per task:
   ```
   mcp__zaiMCP__zai_spawn_agent:
     task: "[Detailed task description with file paths, acceptance criteria]"
     isolation: "worktree"  (for code changes)
     model: "claude-3-5-haiku-20241022"  (cheap for implementation)
     timeout_minutes: 30
   ```
2. Main Claude monitors via `zai_agent_status` and coordinates
3. Review results via `zai_agent_result` — check git diffs before accepting
4. Merge approved changes from worktree branches

**File ownership still applies**: Each Zai agent gets its own worktree branch, preventing conflicts naturally.

## Directive Capture

Capture any text after `/start` as `DIRECTIVE`. If empty, the soul purpose is the directive.
The skill NEVER finishes with "ready to go" and stops. After setup, immediately begin working.

## UX Contract (MANDATORY)

1. **NEVER announce step names** — no "Init Step 1", no "Wave 2"
2. **NEVER narrate internal process** — no "Detecting environment...", no "Calling MCP tools..."
3. **NEVER explain what you're about to do** — just ask questions, then do it silently
4. **User sees ONLY**: questions and seamless continuation into work
5. **Batch questions** — as few rounds as possible
6. **No "done" message that stops** — after setup, immediately begin working

## Co-pilot Voice

The skill should feel like a sharp, experienced mentor — not a silent script runner.

**Tone**: Direct, warm, occasionally wry. Think "senior engineer who genuinely wants you to succeed."

**When to speak up** (brief, 1-2 sentences max):
- When brainstorm weight is determined: explain WHY this weight was chosen
  - Example: "Your project already has structure, so I'll keep this light — just confirming direction."
  - Example: "Starting from scratch — let's think this through properly before writing code."
- When soul purpose assessment is made in Reconcile: share the reasoning
  - Example: "You've got 3 open tasks and no blockers — picking up where you left off."
  - Example: "Everything looks done, but I haven't verified it myself. Want me to check?"
- When Ralph Loop intensity is set: contextualize the choice
  - Example: "Long intensity means we'll generate a full PRD first — this is the thorough path."
- At settlement: acknowledge the work done
  - Example: "5 commits, 2 features verified. Solid session."

**When to stay silent** (NEVER add commentary):
- During MCP tool calls
- During file operations
- During agent spawning
- Between steps of a sequence

**Anti-patterns**:
- Never cheerleader ("Great job! Amazing work!")
- Never narrate process ("Now I'm going to call the preflight tool...")
- Never apologize for tool limitations
- Never use emojis unless the user does first

## Hard Invariants

1. **User authority is absolute** — AI NEVER closes a soul purpose. Only suggests; user decides.
2. **Zero unsolicited behavior** — Skill ONLY runs when user types `/start`.
3. **Human-visible memory only** — All state lives in files.
4. **Idempotent** — Safe to run multiple times.
5. **Templates are immutable** — NEVER edit bundled template files.
6. **NEVER** auto-invoke doubt agent. Only offer it.
7. **Trust separation** — bounty creation and verification must use separate verification logic.
8. **AtlasCoin is optional** — if the service is down, tell the user and continue without bounty tracking.

## MCP Tool Reference

All session operations are performed via `atlas-session` MCP tools. The main thread calls these directly:

| Tool | Purpose |
|------|---------|
| `mcp__atlas-session__session_preflight` | Detect mode, git, CLAUDE.md, templates, session files |
| `mcp__atlas-session__session_init` | Bootstrap session-context, seed active context |
| `mcp__atlas-session__session_validate` | Check/repair session files from templates |
| `mcp__atlas-session__session_read_context` | Read soul purpose + active context summary |
| `mcp__atlas-session__session_harvest` | Scan active context for promotable content |
| `mcp__atlas-session__session_archive` | Archive soul purpose, reset active context |
| `mcp__atlas-session__session_check_clutter` | Scan root for misplaced files |
| `mcp__atlas-session__session_cache_governance` | Cache governance sections from CLAUDE.md |
| `mcp__atlas-session__session_restore_governance` | Restore cached governance sections |
| `mcp__atlas-session__session_ensure_governance` | Add missing governance sections to CLAUDE.md |
| `mcp__atlas-session__contract_health` | Check if AtlasCoin service is available |
| `mcp__atlas-session__contract_create` | Create bounty with executable test criteria |
| `mcp__atlas-session__contract_get_status` | Get current contract and bounty status |
| `mcp__atlas-session__contract_run_tests` | Execute contract criteria deterministically |
| `mcp__atlas-session__contract_submit` | Submit solution to AtlasCoin |

All tools take `project_dir: str` as the first parameter. Use the current working directory.

---

# INIT MODE

> Triggered when preflight returns `"mode": "init"`.

## Step 1: Preflight

Call `mcp__atlas-session__session_preflight` with the current project directory.

The result includes:
- `mode`: "init" or "reconcile"
- `project_signals`: existing files, readme, code presence
- `root_file_count`: number of files at project root
- `is_git`: whether the project is a git repository

**In parallel**, ask the user Ralph questions:

**Question 1**: "How should Ralph Loop work?"
- Options: "Automatic", "Manual", "Skip"

**Question 2** (only if Ralph = Automatic): "What intensity?"
- Options: "Small (5 iterations)", "Medium (20 iterations)", "Long (100 iterations + PRD)"

Store as `RALPH_MODE`, `RALPH_INTENSITY` (default to "Small" if Automatic but no intensity given).

## Step 2: Determine Brainstorm Weight

Using `DIRECTIVE` and `project_signals` from preflight result, classify:

| Condition | Weight | Brainstorm Behavior |
|-----------|--------|---------------------|
| DIRECTIVE has 3+ words AND project has code/readme | **lightweight** | 1-2 quick clarifying questions, confirm direction, produce soul purpose |
| DIRECTIVE has 3+ words AND empty project | **standard** | Explore what to build, 3-5 questions, produce soul purpose + approach |
| No directive AND project has readme/code | **lightweight** | Present what you see in project_signals, ask 1-2 questions to focus the session |
| No directive AND empty project | **full** | Full brainstorm — purpose, constraints, approach, design |

Store `BRAINSTORM_WEIGHT` and `BRAINSTORM_CONTEXT` for use in Step 4.

**Co-pilot note**: When announcing the brainstorm weight, briefly explain why to the user. This is one of the few moments where the skill speaks up — use it to build trust.

### File organization (only if `root_file_count > 15`)

Call `mcp__atlas-session__session_check_clutter`.

If result `status` is "cluttered", present the grouped move map to the user for approval:

"Your project root has [N] misplaced files. Proposed cleanup: [M] docs → docs/archive/, [P] screenshots → docs/screenshots/, [Q] scripts → scripts/, [R] to delete. Approve cleanup?"
- Options: "Yes, clean up", "Show details first", "Skip"

**If "Show details first"**: Display the full `moves_by_dir` grouped listing, then re-ask.
**If "Yes, clean up"**: Execute the moves (using `git mv` if `is_git`).
**If "Skip"**: Continue.

## Step 3: Silent Bootstrap

Call MCP tools in sequence:

1. `mcp__atlas-session__session_init` with:
   - `project_dir`: current directory
   - `soul_purpose`: DIRECTIVE or "(Pending brainstorm)"
   - `ralph_mode`: RALPH_MODE
   - `ralph_intensity`: RALPH_INTENSITY

2. `mcp__atlas-session__session_ensure_governance` with:
   - `project_dir`: current directory
   - `ralph_mode`: RALPH_MODE
   - `ralph_intensity`: RALPH_INTENSITY

3. `mcp__atlas-session__session_cache_governance` with `project_dir`

Then run `/init` in main thread (Claude Code built-in that refreshes CLAUDE.md — must be main thread).

Then call `mcp__atlas-session__session_restore_governance` with `project_dir`.

**Then read the plugin's `custom.md`** if it exists (at `PLUGIN_ROOT/custom.md`), and follow any instructions under "During Init".

## Step 4: Brainstorm + Features + Bounty + Continuation

Transition directly into work. No "session initialized" message.

**Brainstorm runs first (always)**:

Invoke brainstorming with the weight and context determined in Step 2:

- **lightweight**: Invoke `skill: "superpowers:brainstorming"` with args containing the `BRAINSTORM_CONTEXT` + instruction: "This is a lightweight brainstorm. Confirm direction with 1-2 questions, derive a soul purpose statement, then transition to work. Do NOT write a design doc for lightweight brainstorms."
- **standard**: Invoke `skill: "superpowers:brainstorming"` with args containing the `BRAINSTORM_CONTEXT`. Follow normal brainstorm flow but skip design doc if the task is clear enough.
- **full**: Invoke `skill: "superpowers:brainstorming"` with full `BRAINSTORM_CONTEXT` args. Follow complete brainstorm flow including design doc.

After brainstorm completes:

1. **Write soul purpose** via `mcp__atlas-session__session_archive` with:
   - `project_dir`: current directory
   - `old_purpose`: DIRECTIVE or "(Pending brainstorm)"
   - `new_purpose`: DERIVED_SOUL_PURPOSE

1b. **Activate Stop hook enforcement**:
```bash
python3 PLUGIN_ROOT/session-init.py hook-activate --soul-purpose "DERIVED_SOUL_PURPOSE"
```
This enables the Stop hook to block accidental session closes while the soul purpose is active.

2. **Extract and approve features** (if DIRECTIVE contains user-facing claims):
   - Read existing `CLAUDE-features.md` if it exists
   - Parse DIRECTIVE and brainstorm output for user-facing claims
   - Format each claim as: "As a [role], I can [action]"
   - **If new claims found**: Ask user ONE question:
     > "I identified these new features to track: [list claims]. Add to CLAUDE-features.md?"
     - Options: "Yes, add all", "Let me edit first", "Skip"
   - **If "Yes, add all"**: Append claims to `CLAUDE-features.md` with status `pending`
   - **If "Let me edit first"**: Show the claims, let user modify, then add
   - **If "Skip"**: Continue without adding

3. **Create bounty** (if AtlasCoin is available):
   - Call `mcp__atlas-session__contract_health` to check if AtlasCoin service is running
   - If healthy: call `mcp__atlas-session__contract_create` with escrow based on Ralph intensity (see Escrow Scaling below)
   - Write `BOUNTY_ID.txt` to `session-context/`

4. **If AtlasCoin is down**: Tell user: "AtlasCoin is not available at {URL}. Start the service or check the connection. Continuing without bounty tracking."

### Escrow Scaling

| Ralph Intensity | Escrow | Stake (10%) |
|----------------|--------|-------------|
| skip           | 50     | 5           |
| small          | 100    | 10          |
| medium         | 200    | 20          |
| long           | 500    | 50          |

### Ralph Loop Invocation

When `RALPH_MODE = "automatic"`, you MUST use the `Skill` tool to actually start the Ralph Loop.
Construct the invocation based on `RALPH_INTENSITY`:

| Intensity | Skill tool call |
|-----------|----------------|
| **Small** | `skill: "ralph-wiggum:ralph-loop"`, `args: "SOUL_PURPOSE --max-iterations 5 --completion-promise 'You must verify with the doubt agent before claiming soul purpose is fulfilled'"` |
| **Medium** | `skill: "ralph-wiggum:ralph-loop"`, `args: "SOUL_PURPOSE --max-iterations 20 --completion-promise 'You must verify with the doubt agent before claiming soul purpose is fulfilled and code tested'"` |
| **Long** | First invoke `skill: "prd-taskmaster"`, `args: "SOUL_PURPOSE"`. Wait for PRD completion. THEN invoke `skill: "ralph-wiggum:ralph-loop"`, `args: "SOUL_PURPOSE --max-iterations 100 --completion-promise 'You must verify sequentially with 3x doubt agents and 1x finality agent before claiming soul purpose is complete'"` |

Replace `SOUL_PURPOSE` with the derived soul purpose text. Quote the full prompt if it contains spaces.

**CRITICAL**: You must call the `Skill` tool — not just mention it in text.

**MANDATORY**: Every Ralph Loop completion promise includes doubt agent verification. The AI MUST invoke the doubt agent and receive passing verification BEFORE outputting the `<promise>` completion tag. This is non-negotiable regardless of intensity level.

---

# RECONCILE MODE

> Triggered when preflight returns `"mode": "reconcile"`.

**CRITICAL UX REMINDER**: Everything in Steps 1-2 is invisible to the user. Do NOT output "Running reconcile mode", "Assessing context", "Reading soul purpose", or ANY description of what you are doing. The user's first visible interaction is either a question (Step 3) or seamless continuation into work (Step 4). Nothing before that.

## Step 1: Silent Assessment

Call MCP tools in sequence:

1. `mcp__atlas-session__session_validate` with `project_dir` — repairs any missing session files
2. `mcp__atlas-session__session_cache_governance` with `project_dir`
3. Run `/init` in main thread
4. `mcp__atlas-session__session_restore_governance` with `project_dir`
5. `mcp__atlas-session__session_read_context` with `project_dir`

The `read_context` result includes:
- `soul_purpose`: current soul purpose text
- `open_tasks`: any incomplete tasks
- `status_hint`: "no_purpose", "in_progress", "probably_complete", etc.
- `ralph_mode`: "automatic", "manual", or "skip"
- `ralph_intensity`: "small", "medium", or "long"

**Check bounty status** (in parallel with read_context):
- Read `session-context/BOUNTY_ID.txt` if it exists
- Call `mcp__atlas-session__contract_get_status` with the bounty ID
- If no BOUNTY_ID.txt exists, bounty status is "none"

**Then read the plugin's `custom.md`** if it exists (at `PLUGIN_ROOT/custom.md`), and follow any instructions under "During Reconcile".

### Root Cleanup Check

Use `root_file_count` from preflight.

**If `root_file_count > 15`**: Call `mcp__atlas-session__session_check_clutter`.

If result `status` is "cluttered", present the move map to the user as part of Step 3 questions:

"Your project root has [N] misplaced files. Proposed cleanup: [M] docs → docs/archive/, [P] screenshots → docs/screenshots/, [Q] scripts → scripts/, [R] to delete. Approve cleanup?"
- Options: "Yes, clean up", "Show details first", "Skip"

**If "Show details first"**: Display the full `moves_by_dir` grouped listing, then re-ask.
**If "Yes, clean up"**: Execute the moves.
**If "Skip"**: Continue.

## Step 2: Directive Check + Feature Status + Self-Assessment

**Read feature status** from `CLAUDE-features.md` (if exists):
- Count claims by status: `pending`, `verified`, `broken`
- Store as `FEATURE_STATUS` for use in Step 3

**If DIRECTIVE is non-empty (3+ words) AND `status_hint` is `no_purpose`**:
- Call `mcp__atlas-session__session_archive` to set soul purpose to DIRECTIVE
- **Activate Stop hook**: `python3 PLUGIN_ROOT/session-init.py hook-activate --soul-purpose "DIRECTIVE"`
- **Extract new claims** from DIRECTIVE (see Step 4 feature extraction in INIT MODE)
- Skip Step 3, go to Step 4 with a lightweight brainstorm to confirm direction

**If DIRECTIVE is non-empty (3+ words) AND soul purpose exists**:
- **Activate Stop hook**: `python3 PLUGIN_ROOT/session-init.py hook-activate --soul-purpose "DIRECTIVE"`
- **Extract new claims** from DIRECTIVE
- **If new claims found**: Ask user: "I identified these new features: [list]. Add to CLAUDE-features.md?"
- Skip Step 3, go to Step 4 — work on directive (it overrides for this session)

**Otherwise** (no directive): Proceed with self-assessment below.

Using the `read_context` result, classify:

| Classification | Criteria |
|---------------|----------|
| `clearly_incomplete` | open_tasks non-empty, active blockers, criteria not met |
| `probably_complete` | No open tasks, artifacts exist, criteria met |
| `uncertain` | Mixed signals |

## Step 3: User Interaction (conditional)

### If `clearly_incomplete`:
No questions. Skip to continuation. Show feature status if available: "Features: [X] verified, [Y] pending, [Z] broken"

### If `probably_complete` or `uncertain`:
Ask ONE question combining assessment, feature status, bounty status, and decision:

"Soul purpose: '[purpose text]'. [1-2 sentence assessment]. Features: [X verified, Y pending, Z broken]. [Bounty: active/none]. What would you like to do?"
- Options: "Continue", "Verify first", "Close", "Redefine"

**Co-pilot note**: When presenting the assessment, lead with your honest read. "I think this is done, but I'd feel better if we verified X" is better than a dry status report.

**If "Verify first"**: Dispatch doubt-agent to verify features, fold findings into re-presented question (without "Verify first" option).

**If "Close" or "Redefine"**: Run the Settlement Flow (see below).

## Step 4: Continuation

Transition directly into work. No "session reconciled" message.

- **If DIRECTIVE provided**: Begin working on directive.
- **If `ralph_mode` = "automatic"** (from `read_context`): Check if Ralph Loop should start — see "Ralph Loop Invocation (Reconcile)" below.
- **If soul purpose just redefined**: Begin working on new purpose.
- **If `clearly_incomplete`**: Pick up where last session left off using active context.
- **If no active soul purpose**: Ask user what to work on, write as new soul purpose via `mcp__atlas-session__session_archive`.
- **Otherwise**: Resume work using active context as guide.

### Ralph Loop Invocation (Reconcile)

When `ralph_mode` from `read_context` is "automatic", first check if Ralph Loop is already active:

```bash
test -f ~/.claude/ralph-loop.local.md && echo "active" || echo "inactive"
```

- **If active**: Skip invocation. Ralph Loop is already running or was already set up this session.
- **If inactive**: Use the `Skill` tool to start Ralph Loop. Read `ralph_intensity` from the `read_context` result and use the same intensity table as Init mode.

**CRITICAL**: You must call the `Skill` tool — not just mention it in text.

---

# SETTLEMENT FLOW

> Triggered when user chooses "Close" in Reconcile Step 3.

**Read the plugin's `custom.md`** if it exists, and follow any instructions under "During Settlement".

## Step 1: Harvest + Archive

1. Call `mcp__atlas-session__session_harvest` with `project_dir` — check for promotable content
2. If harvest returns content, AI assesses what to promote (judgment call — decisions need rationale, patterns must be reused, troubleshooting must have verified solutions). Present to user for approval. After approval, append promoted content to target files via Edit tool.
3. Call `mcp__atlas-session__session_archive` with:
   - `project_dir`: current directory
   - `old_purpose`: OLD_PURPOSE_TEXT
   - `new_purpose`: NEW_PURPOSE_TEXT (omit for close-without-redefine)

**If "Close" without new purpose**: Ask if user wants to set a new soul purpose. If declined, the archive command writes "(No active soul purpose)".

**Co-pilot note**: Settlement is a moment of closure. Acknowledge what was accomplished — one sentence, no fluff. "3 features shipped, soul purpose met." is perfect.

## Step 2: Feature Verification + Bounty Submission

**Verify features first** (if `CLAUDE-features.md` exists):

1. Read `CLAUDE-features.md` and extract all claims with proof paths
2. For each claim with proof:
   - Run the proof (E2E test, unit test, etc.)
   - Update status: `verified` if pass, `broken` if fail
3. Count results: `[X] verified, [Y] broken, [Z] pending (no proof)`
4. Write updated status back to `CLAUDE-features.md`

**If any claims are `broken`**:
- Present failure to user: "Feature verification failed: [list broken claims]"
- Options: "Fix and re-verify" / "Close anyway (incomplete)" / "Continue working"
- Do NOT submit bounty until all claims are `verified`

**If all claims are `verified` OR no features file exists**, proceed to bounty:

**If bounty exists** (BOUNTY_ID.txt present and bounty status confirmed active):

1. Call `mcp__atlas-session__contract_run_tests` to execute contract criteria
2. If tests pass, call `mcp__atlas-session__contract_submit` with evidence:
   - `soul_purpose`: from read_context
   - `commits_summary`: from `git log --oneline -20`
   - `open_tasks`: from read_context
   - `session_files_have_content`: check session-context files have real content
   - `features_verified`: count of verified claims from CLAUDE-features.md

3. **If verified (passed)**:
   - Tell user: "Soul purpose verified and settled. [X] AtlasCoin tokens earned. [Y] features verified."

4. **If verification failed**:
   - Present failure to user with options: "Fix and re-verify" / "Close anyway (forfeit bounty)" / "Continue working"
   - **Fix and re-verify**: Return to active work, re-run settlement when ready
   - **Close anyway**: Bounty forfeited, session closes
   - **Continue working**: Return to Step 4 of Reconcile

**If no bounty exists**: Skip bounty submission, just archive and close.

## Step 3: Deactivate Stop Hook

Call `hook-deactivate` to remove the Stop hook enforcement:

```bash
python3 PLUGIN_ROOT/session-init.py hook-deactivate
```

This allows the session to close cleanly without the Stop hook blocking.

## Step 4: Automatic PR Creation

**If on a feature branch** (not `main` or `master`):

1. Check current branch: `git branch --show-current`
2. If branch is `main` or `master`: skip PR creation, notify user
3. Push branch to remote: `git push -u origin BRANCH_NAME`
4. Check if PR already exists: `gh pr list --head BRANCH_NAME --state open`
5. If PR exists: notify user with existing PR URL, skip creation
6. If no PR exists, create one:

```bash
gh pr create --title "SOUL_PURPOSE_SHORT" --body "$(cat <<'EOF'
## Summary

Soul purpose: SOUL_PURPOSE_TEXT

## Changes

COMMITS_SUMMARY (from git log --oneline -20)

## Verification

- Features verified: X
- Bounty status: settled/none
- Doubt agent verification: passed/skipped

---

Generated by /start settlement flow
EOF
)"
```

7. Return PR URL to user

**If no remote configured or `gh` not available**: Skip silently, notify user: "No remote configured. Push manually when ready."

**User override**: Before creating PR, ask:
> "Ready to create a PR from `BRANCH_NAME` to `main`. Proceed?"
> Options: "Yes, create PR", "Skip PR", "Let me customize"

---

# Work Execution: Agent Teams Enforcement

> The session lifecycle above handles bootstrapping and context management. This section governs how **actual work** (implementation, PRD tasks, Ralph Loop iterations) is executed.

## Rule: When 2+ Independent Tasks Exist, MUST Use Agent Teams

| Condition | Action |
|-----------|--------|
| Soul purpose requires 2+ independent implementation tasks | **MUST** create work team via `TeamCreate` |
| PRD/TaskMaster generates parallelizable task list | **MUST** create work team |
| Ralph Loop with Long intensity (100+ iterations) | **MUST** create work team |
| Single sequential task | Regular execution (no team needed) |

## Work Team Pattern

After brainstorm/PRD determines the work requires parallel execution, create a **separate** work team:

```
1. TeamCreate(team_name: "{project-slug}-work", description: "Soul purpose execution")
2. Create tasks via TaskCreate with dependencies (addBlockedBy)
3. Spawn teammates via Task tool with team_name parameter:
   - Each teammate gets clear file ownership boundaries (directory-level)
   - Each teammate gets explicit working directory
   - Use subagent_type: "general-purpose" for implementation
4. Teammates self-claim tasks from shared TaskList
5. Lead coordinates via SendMessage — lead does NOT implement when team is active
6. At checkpoints: lead reviews, runs verification, gates next wave
7. On completion: SendMessage type: "shutdown_request" to all work teammates
8. TeamDelete("{project-slug}-work")
```

## File Ownership (Prevent Merge Conflicts)

When spawning work teammates, assign directory-level ownership:

```
Teammate A: owns client/src/pages/, client/src/components/
Teammate B: owns server/services/, server/routes/
Teammate C: owns server/__tests__/, tests/
```

No two teammates edit the same file. If overlap is unavoidable, make tasks sequential (addBlockedBy).

## Anti-Patterns (NEVER)

- **Ad-hoc background Task agents** without TeamCreate — breaks coordination
- **Lead implementing** when work team is active — lead is coordinator only
- **Spawning without file boundaries** — causes merge conflicts
- **Forgetting shutdown** — always shut down work team after wave/phase completes

## Ralph Loop + Work Team Integration

When Ralph Loop is automatic AND work team is active:
- Ralph Loop runs as the lead's iteration cycle
- Each Ralph iteration can spawn a wave of work teammates
- Doubt agents run between waves as verification gates
- Work team persists across Ralph iterations; shutdown only at soul purpose completion

---

# Customizations

> To customize `/start` behavior, create or edit `custom.md` in the plugin root directory.

The AI reads `custom.md` at each lifecycle phase and follows matching instructions:
- **During Init**: After session-context is bootstrapped (Step 3)
- **During Reconcile**: After read-context, before assessment (Step 1-2)
- **During Settlement**: Before harvest + archive (Settlement Step 1)
- **Always**: Applied in all modes

To customize, just write what you want in English under the relevant heading. No code needed.

---

# Doubt Verification

> Triggered when user says "I doubt [feature] works" or chooses "Verify first" in Reconcile Step 3.

## Feature Doubt Flow

When user doubts a specific feature:

1. **Read CLAUDE-features.md** to find the claim ID and proof path
2. **Run the proof visibly**:
   - For E2E tests: `npx playwright test --headed --grep "[feature name]"`
   - For unit tests: Run with verbose output
   - For manual proof: Open screenshot/video for user to see
3. **Update status** in CLAUDE-features.md:
   - If pass: `status: verified`, update `Verified` date
   - If fail: `status: broken`, note failure reason
4. **Report to user**: "Feature '[claim]' verified ✅" or "Feature '[claim]' broken ❌"

## Visual Verification

For maximum confidence (human-visible proof):

1. Run Playwright with `--headed` flag (browser visible)
2. Take screenshot at key moments
3. User watches AI test the feature
4. Screenshot saved to `docs/screenshots/` as evidence
5. Update proof path to include screenshot

Example:
```
User: "I doubt the login flow works"
AI: Running login test visibly...
    [Browser opens, fills form, submits]
    ✅ Login successful. Screenshot saved.
    Feature F1 verified.
```

## Integration with e2e-full

When running `/e2e-full` skill:

1. e2e-full discovers all features from codebase
2. Generates tests for each user story
3. **Writes to CLAUDE-features.md**: Maps each test to a claim
4. Runs tests and updates status
5. Creates PR with proof links

This creates a feedback loop:
- `/start` extracts claims → `CLAUDE-features.md`
- `/e2e-full` generates tests → updates proof paths
- Doubt verification → runs specific test → updates status
- Settlement → all claims verified → bounty earned
