# Bridge Architecture — 2026-07-23

## Overview

The Bridge integrates Hermes Agent with the AI Chat Tree engine, capturing every interaction from every source (Matrix, CLI, Discord, Telegram, WhatsApp, etc.) as structured tree nodes.

## Problem Solved

**Before:** Hermes had two separate session stores — gateway sessions (Matrix/Telegram/etc.) and terminal sessions — with no unified graph structure or cross-platform conversation continuity.

**After:** All interactions flow through a single AI Chat Tree API at `localhost:8765`, creating a persistent conversation graph that survives platform changes and session boundaries.

## Components

### 1. Bridge Hook
**Location:** `~/.hermes/hooks/tree-node/`

#### HOOK.yaml
```yaml
name: tree-node
description: Connects every Hermes interaction to the AI Chat Tree
events:
  - agent:step
  - session:end
category: integration
```

**Events:**
- `agent:step` — captures tool calls and intermediate steps in real-time
- `session:end` — does a full canonical sync of the entire session transcript

**Key insight:** The `session:end` event is the primary high-fidelity sync point. The hook's `agent:end` response field is truncated to 500 chars, but `session:end` gives us access to the full session file on disk.

#### handler.py
**Two-tier write strategy:**

1. **Real-time (agent:step):** Captures tool calls, intermediate reasoning steps
   - Writes to `steps` endpoint of tree API
   - Low-fidelity but immediate
   - Useful for debugging and tracing the agent's thought process

2. **Canonical (session:end):** Full session sync
   - Reads complete session file from disk
   - Writes every turn as a complete turno
   - No truncation — the truth
   - Extracts model metadata from session JSON files

**Model extraction fix:**
```python
async def read_session_metadata(session_dir: Path, session_id: str) -> dict:
    """Read model and platform from session JSON metadata."""
    for f in session_dir.glob(f"{session_id}*.json"):
        if f.suffix == '.json':
            try:
                meta = json.loads(f.read_text())
                return {
                    "model": meta.get("model", "unknown"),
                    "platform": meta.get("platform", "unknown"),
                }
            except (json.JSONDecodeError, IOError):
                pass
    return {"model": "unknown", "platform": "unknown"}
```

### 2. Tree Engine
**Location:** `/home/vigil/ai-chat-tree/ai-chat-tree-engine/ai_chat_tree/engine.py`
**Status:** Running on `http://localhost:8765`
**Vault:** `/home/vigil/Documents/obsidian-chat-tree`

**API endpoints:**
- `POST /branches` — Create or update conversation branches
- `POST /turnos` — Write a single turn (prompt + response)
- `POST /steps` — Capture agent step/tool calls
- `GET /branches` — List all branches
- `GET /turnos?branch={branch_key}` — Get all turns in a branch
- `GET /ping` — Health check

**Data model:**
```
Trunko (root of conversation hierarchy)
  └── Brancho (conversation/thread)
        └── Turno (atomic Turn → prompt + response)
              └── Fruito (additional outputs attached to a turn)
```

### 3. Cron Jobs
**Location:** `~/.hermes/cron/`

#### a) Daily Cron Digest (every day at 6 AM)
**Job ID:** `1a4d4b65f6aa`
**Name:** `cron-digest-to-matrix`

Reads all cron output directories, checks for incidents, posts summary to Matrix.

**Cron job directories (13 total):**
- `hermes-self-health` — System health probe
- `tnn-fleet-health` — Fleet status
- `hrr-status-probe` — Hot Rod Rig status
- `cron-alert-bridge` — Incident detection
- `incidents/` — Unprocessed incidents
- `daily-research-council` — Council outputs
- `hrr-config` — Configuration state
- `hrr-mission-state` — Mission tracking
- `d2-validation` — D2 validation results
- `incident-notes` — Incident documentation
- `tapo-state-watcher` — Tapo device states
- `80a0b9ef03e2` — Session history
- `0d9f0a234d08` — Additional history

#### b) Weekly Session Export (every Sunday at 7 AM)
**Job ID:** `a1a2c81470d7`
**Name:** `weekly-session-export`

Exports all Hermes sessions from the past 7 days to JSONL archive files.

**Output:** `~/.hermes/archives/`
**Delivery:** Local save only (no Matrix delivery)

## Data Flow

```
User message → Any platform (Matrix/CLI/Discord/Telegram)
    ↓
Hermes Gateway receives message
    ↓
Agent processes (tool calls, reasoning, responses)
    ↓
agent:step fires → Bridge captures tool calls → POST to tree API
    ↓
agent:end fires → Bridge records turno (500 char truncated)
    ↓
session:end fires → Bridge reads full session file → POST complete turnos to tree API
    ↓
Tree Engine → Stores in vault as graph structure
    ↓
obsidian-chat-tree → Observable as markdown/nodes
```

## Key Decisions

1. **Use session:end as primary sync point** — Hook's agent:end response is truncated to 500 chars. session:end gives access to the full session file on disk.

2. **Model metadata from session files** — Hook context doesn't always include the model name. Session JSON files contain this metadata.

3. **Two-tier write strategy** — Real-time for debugging/tracing (agent:step → steps endpoint), canonical for completeness (session:end → turnos endpoint).

4. **Branch creation on first encounter** — Branches are auto-created in the tree when first seen. Cache files in `~/.hermes/tree_cache/` prevent duplicate requests.

5. **Error tolerance** — Bridge errors never block the agent pipeline. Network failures are silently logged but don't interrupt conversation.

## Current Limitations

- **agent:step tool capture** — `tool_args` and `tool_result` fields in hook context may be truncated or incomplete
- **session:end timing** — Sync only happens when sessions end (reset, /new, timeout, gateway restart). Real-time sync is limited to step-level data.
- **No Obsidian sync** — Tree engine writes to the vault but doesn't trigger Obsidian to refresh. Manual refresh may be needed.
- **No bidirectional sync** — Tree to Obsidian works, but Obsidian changes don't propagate back to the tree.

## Future Work

- [ ] Fix agent:end response truncation at hook level (requires patching Hermes gateway)
- [ ] Add agent:start event for session creation tracking
- [ ] Implement Obsidian refresh trigger after sync
- [ ] Add search functionality from tree to query all conversations across platforms
- [ ] Support for branch merging in the tree (currently only branching is supported)
- [ ] Historical import of existing sessions into the tree
- [ ] Web interface for browsing the conversation tree
- [ ] Integration with Honcho memory for decision tracing

## Files Created/Modified

### During this session (2026-07-23):
1. `~/.hermes/hooks/tree-node/HOOK.yaml` — Hook manifest
2. `~/.hermes/hooks/tree-node/handler.py` — Bridge handler (6,001 bytes)
3. `~/.hermes/cron/` jobs — `cron-digest-to-matrix` (1a4d4b65f6aa) and `weekly-session-export` (a1a2c81470d7)
4. `~/.hermes/tree_cache/` — Branch cache directory (auto-created)

### Previous (from earlier work):
1. `/home/vigil/ai-chat-tree/ai-chat-tree-engine/ai_chat_tree/engine.py` — Tree engine (port 8765)
2. `/home/vigil/ai-chat-tree/ai-chat-tree-engine/ai_chat_tree/model.py` — Data models (Trunko, Brancho, Turno, Fruito)
3. `/home/vigil/ai-chat-tree/ai-chat-tree-engine/ai_chat_tree/vault_manager.py` — Vault write operations
4. `/home/vigil/ai-chat-tree/ai-chat-tree-engine/ai_chat_tree/vectors.py` — Vector embeddings

## System Status

**Tree Engine:** ✅ Running on port 8765
- Health check: `curl http://localhost:8765/ping` → `{"status":"ok","vault":"/home/vigil/Documents/obsidian-chat-tree"}`
- Vault: `/home/vigil/Documents/obsidian-chat-tree`

**Gateway:** Active (status check pending restart)
**Hook Discovery:** Automatic on gateway restart
**Cron Scheduler:** Active (13 job directories detected)

---

*Documentation written by VIGIL during bridge architecture implementation.*
*Date: 2026-07-23*
