# MASTER-Checklist.md — AI Chat Tree 🌳

> **Vision:** Build the most powerful, structured, and memory-rich AI conversation interface ever created.

**Project Status:** Phase 1 complete · Phase 2 complete · Phase 3 complete
**Last Updated:** 2026-07-25
**Version:** 0.2.0
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

- [x] **D-001: Execution environment** — ✅ **RESOLVED: Option C′ (Plugin + Python engine)**
  - Plugin: thin TypeScript HTTP client for Obsidian
  - Engine: `ai-chat-tree-engine` — Python/FastAPI service (sqlite-vec, RLM, embeddings)
  - Split: TS plugin shell + Python sidecar via HTTP IPC
  - Blocks: none — unblocked Phase 1+

- [x] **D-002: Vector DB backend** — **RESOLVED: sqlite-vec**
  - Single-file, zero-config, WASM-friendly
  - Blocks: none

- [x] **D-003: Default embedding model** — **RESOLVED: nomic-embed-text**
  - Ollama-native, solid on code + prose
  - Blocks: none

- [x] **D-004: RLM orchestration framework** — **RESOLVED: Custom minimal scaffold**
  - Avoid framework bloat, retain debug transparency
  - Blocks: none

- [x] **D-005: LLM routing layer** — **RESOLVED: LiteLLM**
  - Cleanest multi-provider abstraction
  - Blocks: none

- [x] **D-011: Guardian integration path** — **RESOLVED: Python mirroring**
  - Faster path to enforcement; migrate to TypeScript when pi-infra is active runtime
  - Blocks: none

- [x] **D-006: Primary language for core** — ✅ **RESOLVED: TypeScript + Python hybrid (HTTP IPC)**
  - TypeScript: Obsidian plugin UI layer
  - Python: ai-chat-tree-engine (vault ops, RLM, embeddings, vector DB)
  - HTTP boundary between plugin and engine
  - Blocks: none

- [x] **D-007: Repo license** — **RESOLVED: MIT**
  - Blocks: none

- [x] **D-008: Fruit storage** — **RESOLVED: Per-turn `Turn-XXX-fruits/` subfolder**
  - Matches architecture.md, keeps fruits collocated with turns
  - Blocks: none

- [x] **D-009: Local LLM default** — **RESOLVED: Ollama**
  - Most mature, scriptable, widely adopted
  - Blocks: none

- [x] **D-010: Revision strategy** — **RESOLVED: Inline linked revision node**
  - Lighter weight, preserves branch semantics
  - Blocks: none

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
- [x] `docs/rlm-system-prompts.md` — full RLM template + tool signatures
- [x] `docs/roadmap.md` — public-facing roadmap (distinct from this internal checklist)
- [x] `docs/contributing.md`
- [x] `LICENSE` file committed (MIT)
- [x] `CHANGELOG.md` at repo root
- [x] GitHub repo `ai-chat-tree` initialized and first commit pushed
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
- [x] Finalize Turn frontmatter schema
  - Required: `type`, `id`, `timestamp`, `branch`, `parent_turn`, `model`, `success_score`, `tags`, `vector_id` ✓
  - Optional: `revision_of`, `revision_number`, `change_reason`, `source` ✓
- [x] Trunk frontmatter schema
- [x] Branch index / metadata file schema
- [x] Fruit classification convention (script / image / terminal / diff / diagram / other)

### File System Operations
- [x] Create turn (atomic write + fruits folder scaffold)
- [x] Create branch (fork from turn)
- [x] Create revision node (immutable, links to original)
- [x] Attach fruit to turn
- [x] Read turn (markdown + frontmatter parse)
- [x] List nodes in branch
- [x] Ancestry walk (get_ancestors)
- [x] Children walk (get_children)

### Validation
- [x] Schema validator for all node types (Pydantic in `validation.py`)
- [x] Link integrity checker (no dangling wikilinks) (`check_integrity()`)
|[x] CLI dry-run mode for all mutations (2026-07-25)
  - Added `dry_run` parameter to all 7 VaultManager mutation methods: create_trunk, create_brancho, create_turno, create_rotation, create_revision, delete_node, update_field
  - Added `--dry-run` flag to all 8 CLI mutation subparsers: create, branch, fruit, rotate, trunk, delete, init, import
  - All handlers check args.dry_run, pass through to VaultManager, and emit `[DRY RUN]` preview without writing

---

## 🧠 Phase 2 — RLM Engine

### REPL Environment
- [x] Sandboxed Python REPL (isolated per session, resource-limited)
- [x] Inject tools at session start
- [x] Capture stdout/stderr back to LLM
- [x] Recursion depth limit (MAX_DEPTH = 4)
- [x] Session transcript persistence (for debugging)

### Core REPL Tools
- [x] `list_nodes(branch=None, limit=50)`
- [x] `read_node(turn_id)`
- [x] `read_fruit(turn_id, fruit_type="all")`
- [x] `get_ancestors(turn_id)`
- [x] `get_children(turn_id)`
- [x] `vector_search(query, k=12, min_score=0.75)` — stub (Phase 3 completes)
- [x] `get_similar_nodes(turn_id, k=8)` — stub (Phase 3 completes)
- [x] `list_branches()`
- [x] `create_branch(parent_turn_id, name)`
- [x] `save_fruit(turn_id, content, filename, type="script")`
- [x] `llm_subquery(sub_prompt, context_nodes=None)` — recursion primitive
- [x] `get_success_patterns(branch=None)`

### Prompts
- [x] Root RLM system prompt (production-ready version)
- [x] Sub-query system prompt
- [x] `<FINAL_ANSWER>` extraction contract

### Orchestration Loop
- [x] `rlm_generate_response()` entry point (in `rlm_orchestrator.py`)
- [x] `execute_rlm_session()` recursive driver (in `rlm_orchestrator.py`)
- [x] Code block extraction + safe execution (in `rlm_orchestrator.py`)
- [x] Final answer detection & exit (`<FINAL_ANSWER>` in `rlm_orchestrator.py`)
- [x] Error path back to LLM (in `rlm_orchestrator.py`)

---

## 🧬 Phase 3 — Memory Layer (Vector + Graph)

### Embeddings
- [x] Chunking strategy (headings, code blocks, paragraphs, ~500–1000 tokens)
  - `smart_chunking.py` — `smart_chunk_text()` splits by markdown headings/code blocks/paragraphs
  - `chunk_turno()` — multi-field chunking across prompt + response
- [x] Embedding pipeline (on turn save)
  - `ExtendedVectorStore.ingest_chunk(s)` — chunk + embed + insert in single transaction
- [x] Re-embed on revision
  - `ExtendedVectorStore.reembed_turno()` — deletes old vectors, regenerates from latest source
- [x] Batch re-index command
  - `ExtendedVectorStore.batch_reindex()` — bulk re-index by turn IDs or full reset

### Vector Store
- [x] Schema: `id`, `turn_id`, `chunk_text`, `embedding`, metadata (branch, model, success, fruit_types, timestamp)
  - Extended via `meta` table with `branch`, `model`, `success_score`, `fruit_types`, `tag` indexes
- [x] Similarity search (cosine)
  - sqlite-vec vec0 with `distance=cosine`, ANNS via `num_candidates`
- [x] Hybrid search (vector + BM25/keyword)
  - `HybridSearch.search()` — alpha-weighted combination of vector + TF-like keyword scoring
- [x] Metadata filters (by branch, by model, by success threshold)
  - All filters supported in `HybridSearch.search()` params and VectorStore SQL

### Graph Layer
- [x] Edge types: `parent_of`, `revision_of`, `similar_to`, `merged_into`, `fruit_of`
  - `memory_graph.py` — `Edge` dataclass + directed adjacency list in sqlite
- [x] Graph traversal helpers
  - `get_children()`, `get_parents()`, `get_outgoing/incoming_edges()`
  - `walk_ancestry()` (BFS up parent chain), `walk_descendants()` (BFS down)
- [x] Optional: GraphRAG-style community detection for large trees
  - `find_similar_clusters()` — connected components on `similar_to` edges above threshold
  - `branch_fanout()` — subtree size analysis

### Retrieval Strategy
- [x] Scoped retrieval (ancestors + top-k vector + weighted by success)
  - `ScopedRetriever.retrieve_scoped_context()` — composite scoring: 40% vector + 30% success + 20% ancestry + 10% time_decay
- [x] Token budgeting
  - `HybridSearch._token_limit()` truncates results to fit budget
  - `ScopedRetriever._assemble_context()` enforces budget during assembly
- [x] Context assembly for LLM
  - Formatted markdown with branch/turn/score headers and prompt context

---

## 🔌 Phase 4 — Obsidian Integration / UI

*Scope depends on D-001 + D-006. Split into plugin (4a) and standalone shell (4b, deferred).*

### Phase 4a — Obsidian Plugin Shell ✓ COMPLETE

> **Implemented.** Plugin shell, settings, commands, views, and engine serve all wired.

- [x] `manifest.json`
- [x] Settings pane (engine URL, API keys/secret, embedding model, vault path, model-per-branch config)
- [x] Command palette actions (new turn, new branch, RLM regenerate, re-embed-all, import ChatGPT, import Claude)
- [x] Status bar (engine healthz status, current branch icon)
- [x] `engine serve` CLI command (daemon thread + health-check startup)

### Custom Views
- [x] Chat pane — branch/mode dropdown selectors, prompt input, model switcher per branch, inline fruit preview per turn
- [x] Family Tree sidebar — tree-tab.ts with expand/collapse, search, live highlighting
- [ ] Right sidebar — node details, backlinks, fruits, revision history (deferred — requires Obsidian sidebar-pane API)
- [ ] Branch comparison view (side-by-side)

### Interactions
- [x] One-click branch from any turn (🌿 Branch button on each message)
- [x] One-click revise prompt → new linked node (↻ Revise button)
- [x] Apply fruit to vault/file (🍎 Fruit button with type picker)
- [x] Model switcher per branch (model dropdown in header)
- [x] Feedback capture (👍/🤔/👎 per turn with POST /turnos/{id}/score)

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

**2026-07-24 — VIGIL Session (Guardian Integration Review)**
- [x] Audit of original "Logician v3" claims vs. reality done
- [x] Identified Logician → Guardian rename (Guardian is pi-infra's canonical term)
- [x] Created `docs/PROPOSED-GUARDIAN-INTEGRATION.md` — accurate inventory of what exists, what pi-infra ships, recommended architecture
- [x] Updated `README.md` — replaced Logician v3 references with Guardian/pi-infra architecture
- [x] Added D-011 to decision table (Guardian integration path)
- [x] Removed dead `core/` stubs (logician_bridge.py, node.py) — never touched by live engine
- [x] Removed superseded `PROPOSED-IMPROVEMENTS-LOGICIAN-INTEGRATION.md`
- [x] Renamed `logician_hash` → `guardian_hash` in `turns/Turn-001.md`
- [ ] Core review of `PROPOSED-GUARDIAN-INTEGRATION.md` before merge
- [ ] Decide: Python mirroring vs. TypeScript invocation of Guardian

**2026-06-22 — Original Logician Prototype (superseded)**
- [ ] Run prototype to create Turn-001.md via Guardian
- [ ] Review prototype in morning (Guardian integration quality, schema, Honcho synergy)
- [ ] Decide on vector DB (sqlite-vec remains leading candidate)
- [ ] Create `docs/rlm-system-prompts.md`

**Original Phase 0 items remain valid but now gated behind Guardian enforcement.**

---

## 📜 Changelog

### 2026-04-24
- Master checklist created
- All Phase 0 design-phase docs reviewed and catalogued
- 10 critical decisions identified as unblockers
- MVP definition proposed
- Phases 1–8 scaffolded with atomic tasks

### 2026-07-25
- Phase 3 (Memory Layer) complete: smart_chunking.py, rlm_orchestrator.py, rlm_repl.py, rlm_prompts.py, memory_store.py, memory_graph.py
- Package version bumped to 0.2.0
- __init__.py updated with new Phase 3 exports
- MASTER-Checklist.md updated with 2026-07-25 entry
- Phase 1-3 all committed and pushed
- **CLI dry-run mode implemented (Phase 1 Validation):** `dry_run` param added to 7 VaultManager mutation methods and `--dry-run` flag added to 8 CLI subparsers

### 2026-05-14
- D-001 research complete (Option C′: Plugin + Python engine via HTTP)
- D-001 and D-006 marked resolved in checklist
- Resolved Decisions section added
- Continuing Phase 0 documentation setup

---

*Every entry in this checklist is a commit waiting to happen.*
