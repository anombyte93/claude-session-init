# Atlas Session vNext Architecture Design

**Date**: 2026-02-17
**Status**: Approved
**Soul Purpose**: Transform /start skill to use atlas-session MCP directly + delegate coding work to Zai agents

---

## Problem Statement

The current `/start` skill has three architectural issues:

1. **Not using the MCP server**: The atlas-session MCP server exists (18 tools, FastMCP-based, fully functional) but SKILL.md ignores it and shells out to `python3 session-init.py` via bash through task agents.

2. **Expensive agent teams**: Session-ops, bounty-agent, finality-agent all run on Claude Max — expensive for operations that are just JSON I/O or API calls.

3. **Not a co-pilot**: The skill is mechanical — runs processes, prints output. User wants an intelligent presence that figures things out and guides them, not a silent script runner.

---

## Target Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Main Claude (Opus/Sonnet)                 │
│                    Smart Orchestrator / Co-pilot             │
└─────────────────────────────────────────────────────────────┘
                            │
                            │ Direct MCP calls (no agents)
                            ▼
        ┌───────────────────────────────────────────┐
        │      atlas-session MCP Server (FastMCP)   │
        │  session_preflight, session_init,          │
        │  session_validate, session_read_context,    │
        │  session_harvest, session_archive,           │
        │  contract_*, session_*                     │
        └───────────────────────────────────────────┘
                            │
                            │ When coding work needed
                            ▼
        ┌───────────────────────────────────────────┐
        │           Zai MCP Server                   │
        │  zai_spawn_agent → spawns cheap ZAI       │
        │  agents (GLM models, ~10x cheaper)        │
        │  for actual implementation work           │
        └───────────────────────────────────────────┘
```

**Key principle**: Session state management = direct MCP calls (cheap). Coding work = Zai agents (cheap). Main Claude = only for decisions and user interaction.

---

## Changes Required

### 1. SKILL.md Rewrite (~870 → ~400 lines)

**Remove**:
- All `TeamCreate` calls
- All session-ops agent spawning
- All `SendMessage` to session-ops
- Bounty-agent spawning (handle via MCP `contract_*` tools instead)
- All the ceremony around "message agent, wait for response, parse JSON"

**Add**:
- Direct MCP tool calls: `mcp__atlas-session__session_preflight`, etc.
- Zai delegation: `mcp__zaiMCP__zai_spawn_agent` for coding tasks
- Personality/humanity in decision points (not silent mechanical steps)

**Result**: Main thread makes decisions and calls tools directly. No agent team overhead.

### 2. Installer Enhancement (`install.sh`)

Current installer works but is not friendly. Add:
- Interactive wizard using `inquirer` or simple terminal prompts
- First-run detection: if atlas-session MCP not configured, guide setup
- Scope selection: global vs project installation
- Post-install verification: "Atlas session MCP is running. You can now run `/start`."

### 3. Zai Integration

Zai MCP already exists (`/home/anombyte/Hermes/Projects/tools/zaiMCP/`). Integration points:
- **Brainstorming phase**: Instead of `superpowers:brainstorming` skill, spawn a Zai agent to do the brainstorming
- **Implementation**: When a design is approved, spawn Zai agents to code it
- **Research**: Spawn Zai agents for research tasks via Perplexity

### 4. Session MCP Tools (Already Exist)

No changes needed — these tools are already built and working:

| Tool | Purpose |
|------|---------|
| `session_preflight` | Detect init vs reconcile mode |
| `session_init` | Bootstrap session-context files |
| `session_validate` | Check/repair session files |
| `session_read_context` | Get soul purpose + active context |
| `session_harvest` | Scan for promotable content |
| `session_archive` | Archive soul purpose |
| `session_check_clutter` | Find misplaced files |
| `session_cache_governance` | Cache CLAUDE.md before /init |
| `session_restore_governance` | Restore governance after /init |
| `session_ensure_governance` | Add missing governance sections |
| `contract_*` | AtlasCoin bounty operations |

---

## Cost Savings Analysis

| Operation | Current Cost | New Cost | Savings |
|-----------|--------------|----------|---------|
| Session preflight | Claude Max agent (via bash) | Direct MCP (free) | ~100% |
| Session init/validate | Claude Max agent | Direct MCP | ~100% |
| Session read-context | Claude Max agent | Direct MCP | ~100% |
| Brainstorming | Claude Max (skill) | Zai agent (~10x cheaper) | ~90% |
| Coding work | Claude Max task agents | Zai agents (~10x cheaper) | ~90% |
| Main orchestrator | Claude Max | Claude Max (unchanged) | 0% |

**Overall**: ~70-80% reduction in Claude Max token usage. Main Claude only used for decisions and user interaction.

---

## Implementation Plan

### Phase 1: MCP-First Rewrite (High Priority)
1. Rewrite SKILL.md Init Mode to call MCP tools directly
2. Rewrite SKILL.md Reconcile Mode to call MCP tools directly
3. Remove all agent team ceremony
4. Test both modes thoroughly

### Phase 2: Zai Integration (High Priority)
1. Integrate Zai spawn calls for brainstorming
2. Integrate Zai spawn calls for coding tasks
3. Ensure context is passed properly to Zai agents

### Phase 3: Interactive Installer (Medium Priority)
1. Add interactive wizard to `install.sh`
2. Add first-run setup guidance
3. Add post-install verification

### Phase 4: Co-pilot Personality (Low Priority)
1. Add helpful commentary at decision points
2. Make the skill feel like a mentor rather than a machine
3. Add "why" explanations for actions taken

---

## Success Criteria

1. `/start` works without spawning any agents for session operations
2. All session state operations complete faster (no agent spawn latency)
3. Coding tasks are delegated to Zai agents
4. Installer provides friendly first-run experience
5. Claude Max token usage reduced by ~70-80%

---

## Open Questions

1. **AtlasCoin integration**: Should `contract_*` operations also use direct MCP calls, or keep bounty-agent for verification? Recommendation: Direct MCP calls for everything — verification is just JSON I/O.

2. **Ralph Loop**: Should Ralph Loop also use Zai agents for its iterations? Recommendation: Yes, each Ralph iteration could spawn a Zai agent instead of Claude Max.

3. **Context passing**: How do we pass sufficient context to Zai agents without flooding their context? Recommendation: Use session MCP's `read_context` to pre-package relevant context for Zai agents.

---

## Files to Modify

1. `/home/anombyte/.claude/skills/start/SKILL.md` — Main rewrite
2. `/home/anombyte/Hermes/Projects/soul_purpose_skill/atlas-session-lifecycle/install.sh` — Add interactive wizard
3. `/home/anombyte/Hermes/Projects/soul_purpose_skill/atlas-session-lifecycle/skills/start/SKILL.md` — Keep in sync with deployed version
