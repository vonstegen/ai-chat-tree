# PROPOSED IMPROVEMENTS — AI Chat Tree + Vigil Logician Integration
**Date:** 2026-06-22  
**Author:** VIGIL (on behalf of Core)  
**Status:** Draft for Morning Review

## 1. Objective

Integrate the **Vigil Logician v3.0** (the automatic immutable logging shield we just built) into AI Chat Tree as the single source of truth for all node mutations.

This turns every conversation turn, branch, and fruit into a cryptographically auditable event.

## 2. Logician Integration Architecture

### Core Principles
- **All mutations must go through Logician** — no direct file writes from the engine or Obsidian plugin.
- **Pre-write validation** — Logician reviews proposed node before creation.
- **Post-write verification** — Logician immediately audits the written node.
- **Branch events** are first-class logged actions.
- **Honcho Benefit**: Structured immutable tree provides high-quality training data for peer memory (user preferences, success patterns, decision traces).

### Integration Points

**A. Node Creation Flow**
1. Engine receives request to create Turn
2. Package proposed node (frontmatter + content) → send to Logician v3
3. Logician validates model, timestamp, parent relationship, schema
4. If approved → atomic write + fruit folder creation
5. Logician performs post-write integrity check
6. Success → return node ID and vector_id stub

**B. Branch Creation Flow**
1. `create_branch(parent_turn_id, name)` 
2. Logician records "BRANCH_CREATED" event with parent reference
3. New branch index file created under `.chat-tree/branches/`

**C. Fruit Attachment**
- All fruits logged as attached artifacts with hash verification.

### Error Handling (v3 features used)
- Dynamic model tagging (detects which model was used per turn)
- Real-time verification using `guardian-verify.sh`
- Graceful degradation if Logician is unavailable (queue + retry)

## 3. Minimal Viable Prototype (MVP) Definition

**Scope — "Phase 0.5" (Tonight's Build)**

**Goals:**
- Prove Logician integration works
- Create first immutable trunk + Turn-001.md
- Support one branch
- Log everything through Vigil Logician v3
- Establish pattern for Honcho benefit (structured decision history)

**Features Implemented in Prototype:**
- `Node` data class with strict schema
- `LogicianBridge` class (calls vigil-log-processor-v3.py)
- CLI: `create-turn`, `create-branch`, `logician-status`
- Basic frontmatter generation (`type`, `id`, `timestamp`, `branch`, `parent_turn`, `model`, `tags`, `logician_hash`)
- Automatic logging of every action

**Out of Scope for Tonight:**
- Full RLM engine
- Vector embeddings
- Obsidian plugin
- SQLite-vec integration

## 4. Benefits to Honcho AI Memory Backend

This integration creates **high-quality structured memory** that Honcho can consume:

- **Immutable decision trees** → Honcho can analyze branching reasoning patterns
- **Success scoring per turn** → Honcho learns what works for Core
- **Tagged fruits** → Rich examples of code, terminal output, and outcomes
- **Model + timestamp metadata** → Honcho can build temporal preference models
- **Guardian verification** → High-trust data for peer profile building

Honcho becomes the **reflective layer** while AI Chat Tree becomes the **immutable source of truth**.

## 5. Next Morning Review Points

1. Is the Logician integration architecture sound?
2. Does the MVP scope feel right?
3. Should we adjust the frontmatter schema before building more?
4. How aggressive should Honcho integration be in Phase 1?

---

**Prototype Implementation Status:** *In Progress* (being built now)
**Files being created:**
- `ai-chat-tree-engine/core/node.py`
- `ai-chat-tree-engine/core/logician_bridge.py`
- `ai-chat-tree-engine/cli.py`
- Updated `README.md` and `MASTER-Checklist.md`

This document will be updated with results after prototype is complete.
