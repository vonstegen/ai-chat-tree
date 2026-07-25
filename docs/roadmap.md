# AI Chat Tree — Public Roadmap

> A public-facing view of the project's trajectory. Internal tracking and blockers live in [MASTER-Checklist.md](./MASTER-Checklist.md).

---

## Current Status: v0.2.0 — Memory Layer Complete ✅

All foundational layers are implemented and committed:

- **Phase 0:** Foundation & documentation ✅
- **Phase 1:** Core data model + file system operations ✅
- **Phase 2:** RLM engine + REPL environment ✅
- **Phase 3:** Vector store, memory graph, hybrid search ✅

See [CHANGELOG.md](./CHANGELOG.md) for detailed release notes.

---

## Roadmap

### [0.3.0] — MVP Core
**Goal:** A working, importable conversation system.

| Item | Target Phase | Status |
|------|-------------|--------|
| Guardian integration | Phase 4 | 📋 Planned |
| CLI tool (`act`) | Phase 5 | 📋 Planned |
| Full Obsidian plugin | Phase 6 | 📋 Planned |
| Import pipeline (ChatGPT, Claude, etc.) | Phase 7 | 📋 Planned |
| Web UI / Explorer | Phase 8 | 📋 Planned |
| Guardian engine | Phase 4 | 📋 Planned |

### [0.4.0] — Search & Discovery
**Goal:** The system can find and synthesize across past conversations.

| Item | Notes |
|------|-------|
| Advanced search (text + vector + graph) | Extends Phase 3 hybrid search |
| Cross-branch summarization | Uses memory graph edges |
| Success pattern queries | Leverages Guardian + vector scoring |
| Node quality scoring | Extends existing `success_score` framework |

### [0.5.0] — Platform Integration
**Goal:** The tree becomes the backbone of Andrew's agent interactions.

| Item | Notes |
|------|-------|
| All Hermes gateway channels → tree | Bridge hook already wired |
| Cron digest integration | Already operational |
| Bidirectional Obsidian sync | Pending |
| Branch merging | Pending |

### [0.6.0] — Advanced Features
**Goal:** Power-user features for complex reasoning workflows.

| Item | Notes |
|------|-------|
| Multi-agent collaboration | Branch merging + cross-RLM context |
| RLM template library | Reusable reasoning patterns |
| Automated session review | Quality assessment + feedback loops |

### [0.7.0] — Open Source
**Goal:** Publish the engine and plugin under MIT license (pending code review and documentation).

---

## Long-Term Vision

> Build the most powerful, structured, and memory-rich AI conversation interface ever created.

The AI Chat Tree turns ephemeral AI interactions into a persistent, queryable, searchable knowledge graph — with full reasoning trails, version history, and cross-conversation synthesis. Every conversation becomes an asset rather than a memory.

---

*Created: 2026-07-25*
*Internal tracking: [MASTER-Checklist.md](./MASTER-Checklist.md)*
