---
name: stop
description: "Gracefully close a session: harvest promotable content, archive soul purpose, settle AtlasCoin bounty, clean up. Use when user says /stop, wrap up, done for the day, finishing up, close session, or end session."
user-invocable: true
---

# Session Stop Skill

> Graceful session close. Harvest → Archive → Settle → Cleanup.

**Plugin root** (resolved at load time):

!`if [ -n "$CLAUDE_PLUGIN_ROOT" ]; then echo "$CLAUDE_PLUGIN_ROOT"; elif p=$(find ~/.claude/plugins -path '*/atlas-session-lifecycle/scripts/session-init.py' -type f 2>/dev/null | head -1) && [ -n "$p" ]; then dirname "$(dirname "$p")"; elif [ -f ~/.claude/skills/start/session-init.py ]; then echo "$HOME/.claude/skills/start"; else echo 'NOT_FOUND'; fi`

Use the resolved path above as `PLUGIN_ROOT`.

**Script path**: `PLUGIN_ROOT/scripts/session-init.py` (via session-ops agent, never directly).

**AtlasCoin URL**:

!`if [ -n "$ATLASCOIN_URL" ]; then echo "$ATLASCOIN_URL"; else echo "http://localhost:3000"; fi`

Use the resolved URL above as `ATLASCOIN_URL`.

---

## UX Contract

- User sees ONE confirmation question, then settlement results. Nothing else.
- Agent Teams are invisible — no team creation, task assignment, or teammate messages shown.
- No step announcements, no narration.

---

## Phase 0: State Detection (no team yet)

Cheap checks before paying team-spawn cost:

1. `test -d session-context/` → if missing: tell user "No active session to close." **EXIT**.
2. Read `session-context/CLAUDE-soul-purpose.md` → extract current soul purpose text (first non-header, non-blank line after `# Soul Purpose`). If empty or file missing: tell user "No active soul purpose." **EXIT**.
3. `test -f session-context/BOUNTY_ID.txt` → store `HAS_BOUNTY` (true/false). If true, read the bounty ID.

---

## Phase 1: User Confirmation

Ask ONE question via AskUserQuestion:

**Question**: "Soul purpose: '[soul purpose text]'. Close this session?"
- **"Close"** — Archive and shut down.
- **"Close and set new purpose"** — Archive current, set a new soul purpose for next session.
- **"Cancel"** — Do nothing. **EXIT**.

If "Close and set new purpose": ask a follow-up question for the new purpose text. Store as `NEW_PURPOSE`.

---

## Phase 2: Team Setup

Check if a session-lifecycle team already exists:

```bash
test -d ~/.claude/teams/session-lifecycle && echo "EXISTS" || echo "NO_TEAM"
```

**If EXISTS**: Read `~/.claude/teams/session-lifecycle/config.json` to discover existing members. Re-spawn any missing agents needed (session-ops is always needed; bounty-agent only if `HAS_BOUNTY`).

**If NO_TEAM**: `TeamCreate("session-lifecycle")`, then spawn fresh.

### Spawn session-ops

Read `PLUGIN_ROOT/prompts/session-ops.md`. Replace `{SESSION_SCRIPT}` with the resolved script path, `{PROJECT_DIR}` with current working directory. Spawn:

```
Task(name="session-ops", team_name="session-lifecycle", subagent_type="general-purpose", prompt=<resolved prompt>)
```

### Spawn bounty-agent (only if HAS_BOUNTY)

Read `PLUGIN_ROOT/prompts/bounty-agent.md`. Replace `{ATLASCOIN_URL}`, `{PROJECT_DIR}`. Spawn:

```
Task(name="bounty-agent", team_name="session-lifecycle", subagent_type="general-purpose", prompt=<resolved prompt>)
```

---

## Phase 3: Settlement

**Read `PLUGIN_ROOT/custom.md`** if it exists, and follow any instructions under "During Settlement".

### Step 1: Harvest + Archive (via session-ops)

1. Message session-ops: run `harvest`.
2. Receive harvest JSON. If promotable content exists:
   - **Main agent judges** what to promote (decisions need rationale, patterns must be reusable, troubleshooting must have verified solutions).
   - Present promotable items to user for approval.
   - After approval, append promoted content to target session-context files via Edit tool.
3. Message session-ops: run `archive --old-purpose "CURRENT_SOUL_PURPOSE"` (add `--new-purpose "NEW_PURPOSE"` if user chose "Close and set new purpose").

### Step 2: Bounty Settlement (only if HAS_BOUNTY)

1. Message bounty-agent: check bounty status via `GET /api/bounties/:id`.
2. If bounty is active, message bounty-agent: submit solution via `POST /api/bounties/:id/submit`.
3. Spawn finality-agent: Read `PLUGIN_ROOT/prompts/finality-agent.md`, replace `{SESSION_SCRIPT}`, `{PROJECT_DIR}`, `{ATLASCOIN_URL}`, `{BOUNTY_ID}`. Spawn as teammate.
4. Finality-agent collects evidence and calls `POST /api/bounties/:id/verify`.
5. **If PASSED**: Message bounty-agent to call `POST /api/bounties/:id/settle`. Tell user: "Soul purpose verified and settled. [X] AtlasCoin tokens earned."
6. **If FAILED**: Ask user:
   - "Fix and re-verify" → return to active work (exit /stop, keep team alive)
   - "Close anyway (forfeit bounty)" → continue to cleanup
   - "Continue working" → exit /stop, keep team alive

### Step 3: Cleanup

1. `SendMessage(type="shutdown_request")` to all active teammates (session-ops, bounty-agent, finality-agent).
2. Wait for shutdown confirmations.
3. `TeamDelete("session-lifecycle")`.
4. Tell user: "Session closed. Soul purpose '[text]' archived." (Include token info if bounty was settled.)
