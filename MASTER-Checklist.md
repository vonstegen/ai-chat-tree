# MASTER-Checklist.md — AI Chat Tree 🌳

> **Vision:** Build the most powerful, structured, and memory-rich AI conversation interface ever created.

**Project Status:** Design complete · Implementation not started
**Last Updated:** 2026-04-24
**Maintainer:** von Stegen
**Repo:** `ai-chat-tree`

**Note:** AI Chat Tree and PI (earendil-works/pi-coding-agent) share the branching conversation concept but are separate projects. PI has built-in session trees; AI Chat Tree targets Obsidian with full RLM + vector memory.

---

## How to Use This Document

This is a **living document**. It grows with the project and is the single source of truth for where we are, what's next, and what's blocked.

### Status Legend
- `[ ]` — Not started
- `[~]` — In progress
- `[x]` — Complete
- `[?]` — Needs decision or research
- `[!]` — Blocked (note the blocker)

### Rules
1. Update this file at the end of every working session
2. Add a Changelog entry (bottom) whenever anything meaningful changes
3. Never delete items — mark them complete, obsolete, or moved
4. When a new decision or task emerges mid-work, add it immediately

---

## 🎯 Critical Decisions Pending (Unblockers)

Resolve these first. Each one gates work downstream.

- [x] **D-001: Execution environment** — ✅ **RESOLVED: Option C′ (Plugin + Python engine)**
  - Plugin: thin TypeScript HTTP client for Obsidian
  - Engine: `ai-chat-tree-engine` — Python/FastAPI service (sqlite-vec, RLM, embeddings)
  - Split: TS plugin shell + Python sidecar via HTTP IPC
  - Blocks: none — unblocked Phase 1+

- [ ] **D-002: Vector DB backend** — sqlite-vec vs. DuckDB+VSS vs. LanceDB vs. Chroma
  - Leaning: sqlite-vec (single-file, WASM-friendly, zero-config)
  - Blocks: Phase 3

- [ ] **D-003: Default embedding model** — nomic-embed-text vs. bge-small-en vs. other
  - Leaning: nomic-embed-text (Ollama-native, solid on code + prose)
  - Blocks: Phase 3

- [ ] **D-004: RLM orchestration framework** — LangGraph vs. custom minimal scaffold vs. existing `rlm` library
  - Leaning: Custom minimal scaffold (avoid framework bloat, retain debug transparency)
  - Blocks: Phase 2

- [ ] **D-005: LLM routing layer** — LiteLLM vs. direct provider SDKs
  - Leaning: LiteLLM (cleanest multi-provider abstraction)
  - Blocks: Phase 2

- [x] **D-006: Primary language for core** — ✅ **RESOLVED: TypeScript + Python hybrid (HTTP IPC)**
  - TypeScript: Obsidian plugin UI layer
  - Python: ai-chat-tree-engine (vault ops, RLM, embeddings, vector DB)
  - HTTP boundary between plugin and engine
  - Blocks: none

- [ ] **D-007: Repo license** — MIT confirmed?
  - Leaning: MIT

- [ ] **D-008: Fruit storage** — per-turn `Turn-XXX-fruits/` subfolder vs. global `Assets/` folder with wikilinks
  - Leaning: Per-turn subfolder (matches architecture.md)
  - Blocks: Phase 1 file operations

- [ ] **D-009: Local LLM default** — Ollama vs. LM Studio vs. Jan.ai as recommended runtime
  - Leaning: Ollama (most mature, scriptable)

- [ ] **D-010: Revision strategy** — inline revision node vs. branch-per-revision
  - Leaning: Inline linked revision node (lighter, preserves branch semantics)

---

## 📁 Phase 0 — Foundation & Documentation

- [x] Design conversation complete (`gork-chat-ai_chat_tree_design.md`)
- [x] `docs/architecture.md`
- [x] `docs/folder-structure.md`
- [x] `docs/files.md`
- [x] `docs/memory.md`
- [x] `docs/instructions.md`
- [x] Root `README.md`
- [x] `.gitignore`
- [x] `docs/D-001-execution-environment.md` — full analysis with Option C′ recommendation
- [ ] `docs/rlm-system-prompts.md` — full RLM template + tool signatures
- [ ] `docs/glossary.md` — define Trunk, Branch, Turn, Fruit, RLM, Fruit types unambiguously
- [ ] `docs/roadmap.md` — public-facing roadmap (distinct from this internal checklist)
- [ ] `docs/contributing.md`
- [x] `LICENSE` file committed (MIT)
- [x] `CHANGELOG.md` at repo root
- [ ] GitHub repo `ai-chat-tree` initialized and first commit pushed
- [x] `MASTER-Checklist.md` added to repo (this file)
- [x] Project structure: `ai-chat-tree-engine/` and `ai-chat-tree-obsidian/` folders created

### Resolved Decisions

| ID | Decision | Resolution |
|----|----------|------------|
| D-001 | Execution environment | Option C′: Obsidian plugin + Python engine via HTTP |
| D-006 | Primary language | TypeScript plugin + Python engine, HTTP IPC boundary |

---

## 🏗️ Phase 1 — Core Data Model & Storage

### Node Schema (v1.0)
- [ ] Finalize Turn frontmatter schema
  - Required: `type`, `id`, `timestamp`, `branch`, `parent_turn`, `model`, `success_score`, `tags`, `vector_id`
  - Optional: `revision_of`, `revision_number`, `change_reason`, `source` (e.g. `imported`)
- [ ] Trunk frontmatter schema
- [ ] Branch index / metadata file schema
- [ ] Fruit classification convention (script / image / terminal / diff / other)

### File System Operations
- [ ] Create turn (atomic write + fruits folder scaffold)
- [ ] Create branch (fork from turn)
- [ ] Create revision node (immutable, links to original)
- [ ] Attach fruit to turn
- [ ] Read turn (markdown + frontmatter parse)
- [ ] List nodes in branch
- [ ] Ancestry walk (get_ancestors)
- [ ] Children walk (get_children)

### Validation
- [ ] Schema validator for all node types
- [ ] Link integrity checker (no dangling wikilinks)
- [ ] CLI dry-run mode for all mutations

---

## 🧠 Phase 2 — RLM Engine

### REPL Environment
- [ ] Sandboxed Python REPL (isolated per session, resource-limited)
- [ ] Inject tools at session start
- [ ] Capture stdout/stderr back to LLM
- [ ] Recursion depth limit (MAX_DEPTH = 4)
- [ ] Session transcript persistence (for debugging)

### Core REPL Tools
- [ ] `list_nodes(branch=None, limit=50)`
- [ ] `read_node(turn_id)`
- [ ] `read_fruit(turn_id, fruit_type="all")`
- [ ] `get_ancestors(turn_id)`
- [ ] `get_children(turn_id)`
- [ ] `vector_search(query, k=12, min_score=0.75)`
- [ ] `get_similar_nodes(turn_id, k=8)`
- [ ] `list_branches()`
- [ ] `create_branch(parent_turn_id, name)`
- [ ] `save_fruit(turn_id, content, filename, type="script")`
- [ ] `llm_subquery(sub_prompt, context_nodes=None)` — recursion primitive
- [ ] `get_success_patterns(branch=None)`

### Prompts
- [ ] Root RLM system prompt (production-ready version)
- [ ] Sub-query system prompt
- [ ] `<FINAL_ANSWER>` extraction contract

### Orchestration Loop
- [ ] `rlm_generate_response()` entry point
- [ ] `execute_rlm_session()` recursive driver
- [ ] Code block extraction + safe execution
- [ ] Final answer detection & exit
- [ ] Error path back to LLM

---

## 🧬 Phase 3 — Memory Layer (Vector + Graph)

### Embeddings
- [ ] Chunking strategy (headings, code blocks, paragraphs, ~500–1000 tokens)
- [ ] Embedding pipeline (async, on turn save)
- [ ] Re-embed on revision
- [ ] Batch re-index command

### Vector Store
- [ ] Schema: `id`, `turn_id`, `chunk_text`, `embedding`, metadata (branch, model, success, fruit_types, timestamp)
- [ ] Similarity search (cosine)
- [ ] Hybrid search (vector + BM25/keyword)
- [ ] Metadata filters (by branch, by model, by success threshold)

### Graph Layer
- [ ] Edge types: `parent_of`, `revision_of`, `similar_to`, `merged_into`
- [ ] Graph traversal helpers
- [ ] Optional: GraphRAG-style community detection for large trees

### Retrieval Strategy
- [ ] Scoped retrieval (ancestors + top-k vector + weighted by success)
- [ ] Token budgeting
- [ ] Context assembly for LLM

---

## 🔌 Phase 4 — Obsidian Integration / UI

*Scope depends on D-001 + D-006. Split into plugin (4a) and standalone shell (4b, deferred).*

### Phase 4a — Obsidian Plugin Shell (if Obsidian plugin)
- [ ] `manifest.json`
- [ ] Settings pane (LLM provider, API keys, embedding model, paths)
- [ ] Command palette actions (new turn, new branch, run RLM, re-embed, import)
- [ ] Status bar (embedding status, current branch, token usage)

### Phase 4b — Standalone Tauri Shell (deferred)
- [ ] Not in MVP scope — future work after plugin proves the concept

### Custom Views
- [ ] Chat pane (center) — prompt input + streaming response + inline fruit preview
- [ ] Family Tree sidebar — list/outline first, graph later
- [ ] Right sidebar — node details, backlinks, fruits, revision history
- [ ] Branch comparison view (side-by-side)

### Interactions
- [ ] One-click branch from any turn
- [ ] One-click revise prompt → new linked node
- [ ] Apply fruit to vault/file
- [ ] Model switcher per branch
- [ ] Feedback capture (thumbs, score)

---

## 📥 Phase 5 — Ingestion & Migration

- [ ] ChatGPT `conversations.json` parser
- [ ] Claude export parser (current format)
- [ ] Raw text / HTML fallback parser
- [ ] Heuristic classifier: chat vs. terminal vs. code-artifact
- [ ] LLM fallback classifier for ambiguous blocks
- [ ] Fruit extraction (code blocks → files, stdout → logs)
- [ ] Preserve timestamps, role, model when available
- [ ] Dry-run preview before commit
- [ ] Post-import auto-embed

---

## 🔄 Phase 6 — Learning Loop

- [ ] Success signal capture — explicit (thumbs, merge) + implicit (continued, low-error, executed-clean)
- [ ] Reflection agent (periodic RLM pass over successful branches)
- [ ] Pattern extraction → user preference notes
- [ ] Proactive suggestions ("merge these 3 branches?")
- [ ] Personalization profile storage
- [ ] Boost weights in vector retrieval for high-success nodes

---

## 🌌 Phase 7 — Visualization (Deferred)

*Intentionally deferred. UI is a read layer on top of the real system.*

- [ ] 2D force-directed graph with central ring node (Obsidian-style)
- [ ] Variable dot sizing by connection count
- [ ] Straight-line connections
- [ ] Click-to-open-node interaction
- [ ] Filters (by project, model, success, fruit type)
- [ ] Optional 3D sphere mode (long-term)

---

## 📱 Phase 8 — Cross-Platform / Mobile

- [ ] PWA manifest + service worker (if standalone path)
- [ ] Mobile-responsive layout
- [ ] Push notifications (FCM/APNs) for long-running RLM sessions
- [ ] React Native or Capacitor wrapper (post-MVP)
- [ ] Voice input (vibe coding on the go)

---

## 🔬 Research & Open Questions

- [ ] How does RLM recursion interact with streaming responses?
- [ ] Best chunk size for code-heavy turns?
- [ ] How to handle very large fruits (videos, large binaries) without bloating the vault?
- [ ] Merge conflict resolution when combining branches with overlapping fruits
- [ ] Privacy model for shared / git-synced vaults
- [ ] Licensing implications of storing Claude/GPT outputs in a public vault
- [ ] How to benchmark "memory quality" as the tree grows?
- [ ] Can we prototype Obsidian-plugin and standalone paths in parallel cheaply?
- [ ] How do we handle multi-user / team vaults in the future?

---

## 📊 Success Metrics (to define as we build)

- [ ] Define "productive session" metric for vibe coding
- [ ] Define retrieval precision / recall benchmark
- [ ] Define token efficiency vs. linear chat baseline
- [ ] User delight signals (qualitative)
- [ ] Import-fidelity score (how well old chats reconstruct)

---

## 🚀 MVP Definition (proposed — confirm)

Minimum viable demo that proves the architecture:

- [ ] Create trunk + first turn via CLI or Obsidian command
- [ ] Branch from an existing turn
- [ ] RLM generates a response using at least `vector_search` + `get_ancestors`
- [ ] One fruit type (code script) saves correctly and is linked
- [ ] Re-open vault later — everything persists, embeddings intact
- [ ] Import one old ChatGPT conversation end-to-end

---

## 🧭 Next Actions (this session / next)

**2026-06-22 — VIGIL Session (Logician Integration)**
- [x] Created `docs/PROPOSED-IMPROVEMENTS-LOGICIAN-INTEGRATION.md`
- [x] Updated `README.md` with new direction
- [x] Built Phase 0.5 Prototype:
  - `ai-chat-tree-engine/core/node.py` (strict immutable TurnNode)
  - `ai-chat-tree-engine/core/logician_bridge.py` (Vigil Logician v3 integration)
  - First turn creation with pre/post validation
- [ ] Run prototype to create Turn-001.md via Logician
- [ ] Review prototype in morning (Logician integration quality, schema, Honcho synergy)
- [ ] Decide on vector DB (sqlite-vec remains leading candidate)
- [ ] Create `docs/rlm-system-prompts.md`

**Original Phase 0 items remain valid but now gated behind Logician enforcement.**

---

## 📜 Changelog

### 2026-04-24
- Master checklist created
- All Phase 0 design-phase docs reviewed and catalogued
- 10 critical decisions identified as unblockers
- MVP definition proposed
- Phases 1–8 scaffolded with atomic tasks

### 2026-05-14
- D-001 research complete (Option C′: Plugin + Python engine via HTTP)
- D-001 and D-006 marked resolved in checklist
- Resolved Decisions section added
- Continuing Phase 0 documentation setup

---

*Every entry in this checklist is a commit waiting to happen.*
