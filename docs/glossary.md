# Glossary — AI Chat Tree 🌳

> Definitive definitions for every term used across the project. All names follow a consistent naming pattern: internal Python entities use `-o` suffixed names (from Esperanto convention); user-facing documentation uses the base name.

---

## Core Data Model Terms

### Trunk
**Definition:** The root-level artifact of a conversation hierarchy. A trunk represents the overarching project or topic that branches flow from.

**Entity:** `Trunko`
**File:** `docs/_trunks/<id>/_trunk.md`
**Schema:** `id`, `name`, `description`, `branches` (list of branch IDs)
**Role:** Contains the central idea; serves as the origin point for all branches.

### Branch
**Definition:** A parallel conversation thread that forks from a turn or trunk. Branches represent divergent thinking paths, experiments, or topic explorations within the same trunk.

**Entity:** `Brancho`
**File:** `docs/_metadata/branches/<id>.md`
**Schema:** `id`, `name`, `description`, `parent_turn`, `active` (boolean)
**Role:** Organizes turns under a shared context; can be deactivated (archived) without deletion.

### Turn
**Definition:** An atomic, immutable dialogue node containing a prompt-response pair. Every turn is the fundamental unit of conversation history.

**Entity:** `Turno`
**File:** `docs/turno-logs/<branch>/<id>.md`
**Schema (required):** `id`, `timestamp`, `branch`, `parent_turn`, `model`, `success_score`, `tags`, `vector_id`
**Schema (optional):** `revision_of`, `revision_number`, `change_reason`, `source`
**Role:** Immutable record of a single exchange; forms the backbone of conversation history. Revisions attach to turns rather than replacing them.

### Fruit
**Definition:** Rich, non-dialogue outputs attached to a turn — scripts, images, diffs, diagrams, terminal output, etc. Fruits extend a turn beyond pure prose.

**Entity:** `Fruito`
**File:** `docs/frutos/<id>.md` (+ content file in turn's `-fruits` folder)
**Schema:** `id`, `turno_id`, `branch`, `fruit_type`, `content`, `file_path`, `notes`
**Allowed types:** `script`, `image`, `terminal`, `diff`, `diagram`, `other`
**Role:** Enriches turns with actionable or visual artifacts without cluttering the prose exchange.

---

## Infrastructure Terms

### RLM (Reflective Learning Module)
**Definition:** The reasoning orchestration framework that drives the LLM through a structured Observe → Reflect → Plan → Execute → Evaluate loop, with recursive sub-query capability. Not a RAG system — RLM selects context using an internal reasoning process rather than retrieval-driven prompting.

**Components:** `rlm_orchestrator.py`, `rlm_prompts.py`
**Core functions:** `rlm_generate_response()`, `execute_rlm_session()`
**Constraint:** Recursion limited to `MAX_DEPTH = 4`

### Vector Store
**Definition:** The machine-layer memory system storing semantic embeddings of turns. Uses sqlite-vec with cosine similarity search, hybrid scoring, and metadata filtering.

**Backend:** sqlite-vec (embeddings) + sqlite meta table (branch, model, success_score, tags)
**Capabilities:** Chunking, re-embed on revision, batch re-index, hybrid search, metadata filters
**File:** `ai_chat_tree/vectors.py`, `ai_chat_tree/extended_vector_store.py`

### Memory Graph
**Definition:** A directed graph layer (sqlite-backed) on top of the vector store, tracking semantic and structural relationships between turns: `parent_of`, `revision_of`, `similar_to`, `merged_into`, `fruit_of`.

**Capabilities:** Edge traversal, community detection (`find_similar_clusters`), subtree fanout analysis
**File:** `ai_chat_tree/memory_graph.py`

### Scoped Retriever
**Definition:** The context assembly strategy used during RLM sessions. Combines ancestry context, top-k vector results, and success-weighted scoring to produce a bounded context window.

**Scoring:** 40% vector similarity + 30% success score + 20% ancestry proximity + 10% time decay
**File:** `ai_chat_tree/scoped_retriever.py`

### Guardian
**Definition:** The deterministic policy enforcement layer from pi-infra's `packages/guardian/`. All node mutations (turns, branches, fruits) pass through Guardian as a gate before any write occurs.

**Verdicts:** ALLOW · HOLD · DENY
**Integration:** Guardian enforces rules before tree engine writes; all mutations require a Guardian verdict.
**Docs:** `docs/proposed-guardian-integration.md`

### Bridge
**Definition:** The integration layer that captures every Hermes Agent interaction (Matrix, CLI, Discord, Telegram, etc.) as structured tree nodes. Uses a two-tier write strategy: real-time `agent:step` for debugging, `session:end` for canonical sync.

**Location:** `~/.hermes/hooks/tree-node/`
**Destination:** `ai-chat-tree-engine` at `localhost:8765`
**Vault:** `/home/vigil/Documents/obsidian-chat-tree`

---

## RLM-Specific Terms

### <FINAL_ANSWER>
**Definition:** The output contract delimiter that marks the definitive answer of an RLM session. Everything before the tag is reasoning; everything between the tags is the extracted answer.

**Opening tag:** `<FINAL_ANSWER>`
**Closing tag:** `</FINAL_ANSWER>`
**Max content length:** 50,000 characters

### <REQUEST_INFO>
**Definition:** A sub-query LLM's signal that it needs more information beyond what the parent session provided. Used during recursive reasoning when the current context is insufficient.

**Usage:** Only emitted by sub-query processors; root orchestrator interprets this as a request to gather additional context before resuming the sub-query.

### <EQUANT_ERROR>
**Definition:** An error reporting tag emitted when a tool call or reasoning step fails. Contains a description of what failed and why, allowing the LLM to continue with alternative tools.

**Usage:** Tool-level error signal — not used for session-level failures (those use the `finalize_with_result` path).

### Turno
See **Turn** above. The Python/internal reference uses the `-o` suffixed form.

### Brancho
See **Branch** above.

### Trunko
See **Trunk** above.

### Fruito
See **Fruit** above.

### Smart Chunking
**Definition:** The strategy for splitting turn content into embedding-sized chunks before vector ingestion. Splits by markdown headings, code blocks, and paragraphs — never mid-sentence or mid-code-block.

**File:** `ai_chat_tree/smart_chunking.py`
**Functions:** `smart_chunk_text()`, `chunk_turno()`

### Vector ID
**Definition:** A per-turn reference to the set of vector embeddings generated from that turn. Tracked in the turn's frontmatter to support re-embedding on revision and vector deletion during re-indexing.

**Location:** Turn frontmatter → `vector_id` field
**Scope:** Per-turn in the meta table (not one vector per turn — a turn maps to multiple chunk vectors sharing the same logical vector namespace).

---

## Project Structure Terms

### ai-chat-tree-engine
The Python/FastAPI backend service providing the tree data model, RLM engine, vector store, graph layer, and REST API (port 8765).

### ai-chat-tree-obsidian
The TypeScript Obsidian plugin — currently scaffolded, functional implementation pending. Acts as the thin client that communicates with the engine via HTTP/IPC.

### Master Checklist
**File:** `MASTER-Checklist.md`
The living project tracker — the single source of truth for project status, phase boundaries, and pending items.

---

*Created: 2026-07-25*
*Authority: Internal definitions per `model.py`, `vault_manager.py`, `rlm_prompts.py`, `rlm_orchestrator.py`, `vectors.py`, `memory_graph.py`, `scoped_retriever.py`*
