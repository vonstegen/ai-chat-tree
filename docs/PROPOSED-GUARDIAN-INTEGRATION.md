# PROPOSED GUARDIAN INTEGRATION — AI Chat Tree + pi-infra

**Date:** 2026-07-24  
**Author:** VIGIL (on behalf of Core)  
**Status:** Draft — Awaiting Core Review  
**Replaces:** `PROPOSED-IMPROVEMENTS-LOGICIAN-INTEGRATION.md` (superseded)

---

## 1. Objective

Integrate the **Guardian** (the deterministic policy enforcement layer from `pi-infra/packages/guardian/`) into AI Chat Tree as the authority for all node mutations.

This replaces the earlier "Logician v3" concept with the actual Guardian architecture that pi-infra ships today.

---

## 2. What Actually Exists on Disk

### 2.1 pi-infra Guardian (canonical source of truth)

Location: `Developer/pi-infra/packages/guardian/`

| Component | What it is |
|---|---|
| `engine.ts` | Deterministic rule evaluation engine. Evaluates `Dispatch` objects against rules, returns `ALLOW | HOLD | DENY` verdicts with reasoning. First DENY/HOLD wins; otherwise ALLOW. |
| `types.ts` | `Verdict = "ALLOW" | "HOLD" | "DENY"`, `Autonomy = "GREEN" | "YELLOW" | "RED"`, `Dispatch` interface (id, action, target, payload, model, autonomy, is_external_call, machine_id, etc.), `GuardianRule` interface |
| `rules/constitution.ts` | Six constitutional rules: SoulConstitutionRule, SovereignModeRule, NoHallucinationRule, AutonomyTierRule (GREEN/HOLD/DENY tiering), RepoWriteRule, MatrixTokenCrashGuard |
| `guardian-loader.ts` | Loads machine-specific rules, initializes the engine |
| `PERSONA.md` | Persona definition — "You are the Guardian" with core directives (rule enforcement, zero tolerance for drift, auditability, protect sovereignty, clarity over politeness) |
| `skills/guardian-policy/SKILL.md` | Skills-layer documentation — verdict meanings, constitutional rules location, commands (`/persona guardian`, `/infra-status`) |
| **Integration** | `packages/integrations/hermes/` symlinks identity/personas/skills/memory into `~/.hermes/`. Hermes config lists `guardian` as active persona. |

**Guardian is TypeScript. It runs on machines that have pi-infra installed with node/runtime.**

### 2.2 AI Chat Tree — Current State (as of 2026-07-24)

| Component | Status |
|---|---|
| Tree engine (`engine.py`) | ✅ Running on `localhost:8765`, FastAPI server |
| Data models (`model.py`) | ✅ `Turno`, `Brancho`, `Fruito`, `Trunko`, `Node` — markdown serialization |
| Vault manager (`vault_manager.py`) | ✅ CRUD: create_trunoo, create_brancho, create_turno, etc. |
| Vector store (`vectors.py`) | Exists — embedding infrastructure ready |
| Obsidian bridge hook | ✅ `~/.hermes/hooks/tree-node/handler.py` — two-tier (agent:step real-time, session:end canonical) |
| Cron jobs | ✅ `cron-digest-to-matrix` (1a4d4b65f6aa) + `weekly-session-export` (a1a2c81470d7) |
| Obsidian plugin | ⚠️ Schema scaffold only (manifest, esbuild, tabs, styles). Not functional. |
| **Guardian integration** | ❌ **Not implemented.** The tree engine is fully standalone. No connection to pi-infra's Guardian. |

### 2.3 What the Old Document (PROPOSED-IMPROVEMENTS-LOGICIAN-INTEGRATION.md) Claimed

- "Phase 0.5 Prototype built" — **False.** Only stub files exist: `core/node.py` (TurnNode dataclass) and `core/logician_bridge.py` (a log-writer, literally says "Simplified version for initial prototype. Full integration with vigil-log-processor-v3.py will be completed after morning review." — that morning was 31 days ago).
- "Dynamic model tagging" — Not implemented.
- "Real-time verification using guardian-verify.sh" — Not implemented.
- "Graceful degradation (queue + retry)" — Not implemented.
- "CLI for creating first trunk + turns" — `cli.py` does not exist.

### 2.4 What Was Built (from June 22)

- `TurnNode` dataclass with `logician_hash` field (renamed field will be `guardian_hash`)
- Stub `LogicianBridge` class that calls `TurnNode.compute_hash()` and writes to a local `.log` file
- One synthetic `Turn-001.md` created via the stub (hash chain intact but verified, not enforced)
- First commit pushed to `github.com/vonstegen/ai-chat-tree`

---

## 3. Recommended Architecture: Guardian as Mutation Gate

### 3.1 Integration Points

**A. Node Creation Flow (Python → TypeScript)**

Since Guardian is TypeScript and the tree engine is Python, the integration path is:

1. **Via Hermes hooks** (recommended near-term): When `session:end` fires in handler.py, the bridge calls Guardian's verdict logic (via pi-infra's GuardianEngine or the `/persona guardian` route through Hermes) before writing to the vault.

2. **Via pi-infra CLI** (canonical path): Add a Guardian pre-write step as a Hermes plugin that invokes `pi-infra/packages/guardian/` rule engine before the tree engine executes any mutation.

3. **File-level guard** (immediate): Add a Python-side verification layer that mirrors Guardian's constitutional rules, then migrate to the canonical TypeScript engine when pi-infra is the active runtime.

### 3.2 Constitution Map (what needs to be enforced)

| pi-infra Rule | AI Chat Tree Enforcement |
|---|---|
| **SoulConstitutionRule** | Node creation/branching/revision must not violate identity layer |
| **SovereignModeRule** | All mutations logged; external calls (if any) need explicit verification |
| **NoHallucinationRule** | Claims in turno content (models used, scores, etc.) must be marked verified or sourced |
| **AutonomyTierRule** | GREEN (auto): read-only vault ops. HOLD (verify): mutations to HRR/TNN/pi-infra trees. DENY: cross-machine actions |
| **RepoWriteRule** | Any write to HRR/TNN/pi-infra source trees requires verified, source-attributed payload |
| **MatrixTokenCrashGuard** | Prevent guardian-triggered gateway restarts when token is bad |

---

## 4. What to Do Now

### Priority 1: Rename and Correct

- Rename `PROPOSED-IMPROVEMENTS-LOGICIAN-INTEGRATION.md` → `PROPOSED-GUARDIAN-INTEGRATION.md` (superseded)
- Rename `PROPOSED-LOGICIAN-INTEGRATION.md` → `PROPOSED-GUARDIAN-INTEGRATION.md` (this document)
- Rename `logician_bridge.py` → `guardian_bridge.py`
- Rename `logician_hash` field → `guardian_hash`
- Update `README.md` references from "Vigil Logician v3.0" → "Guardian (pi-infra)"
- Clear stale status claims from master checklist

### Priority 2: Build the Real Bridge

- Replace `logician_bridge.py` stub with a bridge that invokes pi-infra's `packages/guardian/engine.ts` as the mutation gate — or at minimum mirrors the six constitutional rules in Python
- Wire the Hermes tree-node hook to check Guardian verdict before writing to vault
- Add `guardian_verified` flag to Turno schema

### Priority 3: Functionalize the Obsidian Plugin

- The scaffold exists but needs a working chat pane, family tree sidebar, command palette, and settings pane
- Hook into the tree engine (port 8765) for live queries

### Priority 4: Resolve Open Decisions

- D-002 through D-010 (vector DB, embedding model, RLM framework, LLM routing, local LLM default, revision strategy, repo license, fruit storage)

---

## 5. Morning Review Points

1. **Is renaming Logician → Guardian correct?** Core confirmed "Guardian is the new name for the Logician" and "Hermes-Agent should be built on the same architecture as pi-infra"
2. **Should we wire the bridge via Python mirroring or invoke pi-infra's TypeScript engine directly?** Python mirroring is faster; TypeScript invocation is more canonical but requires node runtime
3. **What's the MVP scope for Guardian integration?** Minimal: replace the stub with constitutional rule enforcement on all mutations
4. **Should the TURN-001.md guardian_hash field be migrated to `guardian_hash`?** Yes — but only after the real bridge is wired

---

## 6. Files Changed

| File | Action |
|---|---|
| `docs/PROPOSED-GUARDIAN-INTEGRATION.md` | ✍️ New (this file) |
| `docs/PROPOSED-IMPROVEMENTS-LOGICIAN-INTEGRATION.md` | 🔴 Mark superseded |
| `ai-chat-tree-engine/core/guardian_bridge.py` | ✍️ Replace `logician_bridge.py` stub |
| `ai-chat-tree-engine/core/node.py` | 🔧 Field rename: `logician_hash` → `guardian_hash` |
| `README.md` | 🔧 Update all Logician → Guardian references |
| `MASTER-Checklist.md` | 🔧 Update Phase 0.5 status, clarify Guardian architecture |
| `Turn-001.md` | 🔧 Field rename in frontmatter (after real bridge) |

---

**This document supersedes `PROPOSED-IMPROVEMENTS-LOGICIAN-INTEGRATION.md` (dated 2026-06-22).**

**Status: Awaiting Core review before merging into the bridge implementation.**
