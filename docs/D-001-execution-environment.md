# D-001: Execution Environment for AI Chat Tree

**Status:** Proposed (awaiting approval)
**Date:** 2026-04-24
**Decision owner:** Andre (von Stegen)
**Related decisions:** D-005 (LLM routing), D-006 (primary language), D-009 (local LLM default)

---

## Context

AI Chat Tree needs a host environment before any implementation work can start. Three options were originally on the table:

- **Option A** — Obsidian plugin (leverages existing editor + ecosystem; closed-source host; plugin API constraints)
- **Option B** — Standalone Tauri or Electron app (full control; rebuilds vault/editor from scratch)
- **Option C** — Hybrid: plugin-first MVP → standalone fork later

Research surfaced a fourth option worth considering:

- **Option C′** — Plugin as a thin HTTP client + separately-installed Python engine (the `obsidian-llm-wiki-local` pattern). Engine is a local FastAPI service; plugin calls it. Any future standalone app reuses the same engine.

This document picks one.

---

## Requirements AI Chat Tree places on the host

Derived from `architecture.md`, `memory.md`, `files.md`, and the node-centric / RLM workflow:

1. **Plain Markdown vault as canonical storage** — `Turn-XXX.md` + `Turn-XXX-fruits/`, fully portable, human-editable
2. **Custom tree / graph view** — left sidebar showing the family tree / node graph
3. **Custom chat pane** — center pane for reading and composing turns
4. **Right sidebar / workspace** — properties, backlinks, fruit previews
5. **Local LLM routing** — Ollama by default, LM Studio, OpenAI-compatible HTTP
6. **Local embeddings** — nomic-embed-text / bge-small via Ollama or in-process
7. **Vector DB** — sqlite-vec or equivalent for fast hybrid retrieval
8. **RLM REPL** — programmable Python-like environment for recursive tool use (the "LLM writes code to explore the tree" pattern)
9. **Fruit file attachments** — save scripts, images, execution logs as separate files per turn
10. **Multi-model routing** — switch models per branch, compare side-by-side
11. **Streaming LLM output** — token-level streaming into the chat pane
12. **Git-style revisions** — immutable turns + revision nodes via frontmatter links
13. **Obsidian-native feel** — the aesthetic the UI conversation converged on
14. **Mobile parity (eventually)** — design conversation explicitly called for mobile-native experience

---

## Capability matrix

Legend: ✅ native · ⚠️ possible with meaningful work · ❌ blocker

| # | Requirement | A: Obsidian Plugin | B: Standalone Tauri | C′: Plugin + Python engine |
|---|---|---|---|---|
| 1 | Markdown vault | ✅ | ⚠️ must implement | ✅ (inherits from Obsidian) |
| 2 | Custom tree view | ✅ (`registerView`, precedent: Dataview, Smart Connections) | ✅ full control | ✅ (same as A) |
| 3 | Custom chat pane | ⚠️ must coexist with Obsidian's editor conventions | ✅ | ⚠️ (same as A) |
| 4 | Right sidebar | ✅ | ✅ | ✅ |
| 5 | LLM routing (HTTP) | ✅ Copilot / Smart Connections precedent | ✅ | ✅ (engine handles it) |
| 6 | Local embeddings | ✅ two paths: Transformers.js in-process, or HTTP to Ollama | ✅ | ✅ (engine does this via Ollama) |
| 7 | Vector DB | ⚠️ sqlite-vec is native — desktop-only via `child_process`. Pure-JS alternatives (lunr, hnswlib-wasm, Smart Connections' `.ajson` approach) work cross-platform but are heavier. | ✅ sqlite-vec as Rust dep or via sidecar | ✅ engine owns the DB |
| 8 | **RLM REPL** | ❌ **mobile blocker** (no Node.js, no `child_process`, Pyodide is ~10MB+ and hits RAM ceilings on phones). ⚠️ desktop works via Python sidecar. | ✅ Python sidecar via `externalBin` is the canonical pattern | ✅ engine IS the REPL — plugin just calls it |
| 9 | Fruit file attachments | ✅ via Vault API | ✅ | ✅ |
| 10 | Multi-model routing | ✅ | ✅ | ✅ |
| 11 | Streaming output | ✅ `fetch` + ReadableStream | ✅ | ✅ |
| 12 | Git-style revisions | ✅ just new files with frontmatter links | ✅ | ✅ |
| 13 | Obsidian-native feel | ✅ literally IS Obsidian | ⚠️ must rebuild editor + graph (months, cautionary tale: Reor) | ✅ |
| 14 | Mobile parity | ⚠️ only if we avoid Node.js everywhere in the plugin (and the engine stays on a reachable host) | ✅ Tauri v2 has iOS + Android | ⚠️ plugin runs on mobile; engine needs LAN / tunnel. Deferred but not blocked. |

### Reading the matrix

- **A is blocked on requirement #8 for mobile** — the RLM REPL cannot run in-process on iOS/Android. Obsidian's own docs state the Node.js / Electron APIs will crash the plugin on mobile.
- **B is blocked on requirement #13** — recreating the Obsidian editor, graph view, command palette, and plugin ecosystem is a multi-month effort with a real graveyard (Reor has not shipped an update in 10 months at time of writing).
- **C′ has no blockers** — it splits the blocker cleanly: the engine takes on the heavy native work (Python, sqlite-vec, RLM) and the plugin stays light enough to ship everywhere Obsidian runs.

---

## Effort / time-to-MVP

Assumptions: solo dev, evenings + weekends, Andre's stack (Python, FastAPI, Qdrant, WSL2, Docker, Node.js), AI-assisted coding.

### MVP definition (from MASTER-Checklist)

Create trunk + first turn · branch from existing turn · RLM generates a response using `vector_search` + `get_ancestors` · one fruit type (code script) saves and links correctly · vault reopens cleanly with embeddings intact · import one old ChatGPT conversation end-to-end.

### Estimates

| Option | MVP effort | Reasoning |
|---|---|---|
| **A (Plugin only)** | 4–6 weeks | Plugin scaffold (1) · file ops + frontmatter (1) · Ollama HTTP + streaming (1) · embeddings + vector search in TS (1) · minimal RLM loop (1–2). Slower path if we want the REPL; faster if we defer it. |
| **B (Standalone Tauri)** | 14–20 weeks | Editor parity alone is 4–8 weeks (CodeMirror 6 + markdown rendering + wikilinks + live preview). Then everything above, plus install/update infra, plus cross-platform packaging. |
| **C (plain hybrid)** | Same as A for MVP | Same plugin effort; standalone work deferred indefinitely. |
| **C′ (plugin + Python engine)** | **3–5 weeks** | Plugin becomes a thin HTTP client (no vector DB in TS, no RLM logic in TS). Engine is pure Python/FastAPI — Andre's comfort zone. The two halves can be built in parallel. |

C′ is faster than A because all the hardest TypeScript work (in-process embeddings, vector DB, RLM) moves to Python where Andre is more productive and where mature libraries exist.

---

## Risk & reversibility

### Switching cost between options

- **A → B:** Low-to-medium. Vault is plain markdown, already portable. Main loss is TS plugin code; a standalone app would need a new UI layer.
- **A → C′:** Medium. Requires extracting the vector + RLM code from the plugin into a separate service. Doable but not free.
- **C′ → B:** **Very low.** The Python engine is already a standalone service; Tauri shell is "new UI over same engine." The engine is written once and reused.
- **B → A:** Low-to-medium, but nobody does this — standalone users have an install pipeline that's hard to unwind.

### Risk register

| Risk | A | B | C′ |
|---|---|---|---|
| Obsidian API breaks | Medium — we're on their treadmill | None | Medium for plugin, none for engine |
| Mobile never ships | High — RLM needs native | Low — Tauri v2 mobile exists | Medium — engine needs LAN reach; pattern is known |
| Solo-dev scope explosion | Medium — every feature in TS | **High** — editor + graph + plugin system from scratch | Low — engine is Python, UI is thin |
| Supply chain (LiteLLM class) | Low (plugin avoids LiteLLM) | Medium (Python deps) | Medium (Python deps) — mitigated by pinning + not using LiteLLM |
| User install friction | Low (one plugin) | Low (one app) | **Medium** — two pieces to install (plugin + `pip install` or `uv tool install`) |
| Lock-in to closed-source host | High (Obsidian is proprietary) | None | Medium for plugin side |
| Losing existing Obsidian ecosystem (Dataview, Templater, Git plugin, Excalidraw) | None — we get it all | **High** — lose all of it | None |

The pattern: C′ trades modest install friction for the ability to skip almost every other major risk.

---

## Dependency on D-006 (primary language)

Each option implies a language stack:

- **A (plugin only):** TypeScript-primary, with optional Python sidecar for RLM on desktop (mobile would need Pyodide or no REPL).
- **B (standalone):** Rust (Tauri core) + TypeScript (UI) + optional Python (sidecar).
- **C′ (plugin + engine):** TypeScript (plugin) + Python (engine, separately installed). HTTP is the IPC boundary.

C′ aligns exactly with the current D-006 lean ("hybrid — TS plugin shell + Python sidecar"), with one refinement: the Python side is a **separately-installed service**, not a bundled sidecar. That's a cleaner split:

- Engine is testable independently (pytest)
- Engine is reusable (CLI tools: `act import`, `act reflect`, `act export`)
- Engine is a candidate sidecar for a future Tauri app with zero code changes
- Plugin stays `isDesktopOnly: false` in principle (mobile-compatible pending engine reachability)

---

## Precedent projects studied

| Project | What it got right | What it hit walls on |
|---|---|---|
| **Reor** | AI-native desktop app; local embeddings + Ollama + vector DB built in; Electron with good Obsidian-like UX | Lost momentum — no updates in ~10 months per its own GitHub. Warning: rebuilding "Obsidian for AI" is a graveyard. |
| **Copilot for Obsidian** | 100k+ users; TS-only plugin talking to Ollama over HTTP; streaming; vault QA via embeddings. Proves the pattern works. | CORS setup friction (`OLLAMA_ORIGINS=app://obsidian.md*`); freemium model — "Plus" tier behind subscription. |
| **Smart Connections** | In-process Transformers.js embeddings = mobile-compatible; stores data in `.smart-env/` inside vault; "just works" zero-config | Heavy initial indexing (500 MB for 16k notes reported); "source available" license (not OSI-open); performance issues on low-end HW. |
| **obsidian-ai-chat-as-md** | Cleanest existing "branching chat in a markdown file" — proves the concept | Uses heading-nesting in a single file, not per-turn files. Single-file approach doesn't scale to our node-per-turn requirement. |
| **obsidian-llm-wiki-local** | Pattern of "CLI tool + Obsidian as the vault" — closest precedent to Option C′ | CLI-only, no chat UI in Obsidian itself. We'd add the plugin UI layer on top. |
| **Logseq plugin ecosystem** | Shows what's possible when host is open source | Smaller user base than Obsidian; different note model (outliner). Not a fit for our hierarchy. |

The pattern across precedents: **the plugins that succeeded stayed in pure TS and used HTTP for anything heavy**. The projects that tried to replace Obsidian wholesale largely died or stalled.

---

## Recommendation

**Option C′: Plugin + separately-installable Python engine.**

### Concretely

- **`ai-chat-tree-engine`** — Python package (`pip install ai-chat-tree` or `uv tool install ai-chat-tree`). Runs a FastAPI server on `localhost:8765`. Owns: vault operations, RLM REPL, vector DB (sqlite-vec), Ollama calls, embeddings, learning loop, import/export. Also exposes a CLI (`act ingest …`, `act reflect …`) for batch work outside Obsidian.
- **`ai-chat-tree-obsidian`** — TypeScript Obsidian plugin (MIT). Owns: tree view, chat pane, right sidebar, command palette entries, settings UI. Calls the engine over HTTP. Falls back to a polite "engine not reachable — start it with `act serve`" banner when the service is down.
- **Future (deferred):** A Tauri shell that bundles the same engine as a sidecar for a single-app experience. Not in scope for MVP.

### Why this wins

1. **Fastest to MVP** — all heavy lifting happens in Python, which matches Andre's stack. Plugin stays thin.
2. **Testable engine** — RLM logic gets pytest coverage without Obsidian in the loop.
3. **Reversibility** — moving to a Tauri standalone later is "new UI over same engine," not a rewrite.
4. **Plays nicely with the Obsidian ecosystem** — Dataview, Templater, Git plugin, Excalidraw all still work on the same vault.
5. **Sidesteps the LiteLLM class of supply-chain risk** — engine can speak OpenAI-compatible HTTP directly, no broker library required for MVP.
6. **Mobile isn't dead** — it's deferred but not architecturally blocked. A user running the engine at home can reach it from their phone; Tailscale / LAN patterns are well-understood.

### What we give up

- User installs two things, not one.
- We still depend on Obsidian (closed-source host) for the UI side of the MVP.
- CORS / HTTP permissions need a one-time setup (same friction Copilot and ChatGPT MD already solved — documented patterns exist).

These are real costs but they're small compared to the alternative (rebuilding an editor from scratch, or shipping a desktop-only plugin that can never see mobile).

---

## Implications for downstream decisions

If C′ is approved, the following cascade:

- **D-006 (primary language):** Resolved as **TypeScript plugin + Python engine; HTTP is the IPC boundary** (not `child_process`, not Tauri `externalBin`).
- **D-009 (local LLM default):** Reinforces **Ollama** — engine speaks HTTP to it natively; no new wrapper needed.
- **D-005 (LLM routing):** Re-evaluate — we may not need LiteLLM at all. A thin Python layer that calls OpenAI-compatible endpoints (Ollama, LM Studio, OpenAI, Anthropic) covers the MVP. Revisit LiteLLM only if provider-specific quirks (Anthropic's tool use, Bedrock auth, etc.) justify the dependency.
- **D-002 (vector DB):** Unblocked — engine is Python, so sqlite-vec works natively. Leaning confirmed.
- **D-003 (embedding model):** Unblocked — engine calls Ollama's `nomic-embed-text` endpoint. Leaning confirmed.
- **D-004 (RLM framework):** Unblocked — custom minimal scaffold in Python is now the path of least resistance.
- **Phase 4 of MASTER-Checklist** (UI / visualization) gets split: Phase 4a = Obsidian plugin UI; Phase 4b = optional Tauri shell, deferred.

---

## Open questions to close before Phase 1

These surfaced during research and are worth tracking but don't block D-001:

1. Engine auth: localhost-only by default, but do we want an auth token for LAN access (mobile future)?
2. Engine packaging: `uv tool install` (fast, Rust-based) vs `pipx` vs Docker image — probably all three eventually, default to `uv`.
3. CORS: pre-configure `OLLAMA_ORIGINS=app://obsidian.md*` in engine's setup docs so users don't hit the Copilot-era CORS wall.
4. Engine autostart: system service vs `act serve` CLI vs "first plugin call spawns it" — probably manual CLI for MVP, autostart later.
5. Vault path: engine needs to know where the vault lives — plugin tells it on connect, engine caches per-vault.

---

## References

All claims about capabilities and precedent projects were verified against sources from late 2024 through April 2026:

- Obsidian mobile limitations: <https://marcusolsson.github.io/obsidian-plugin-docs/testing/mobile-devices>
- Obsidian plugin `child_process` behavior: <https://forum.obsidian.md/t/inquiry-about-downloading-and-executing-local-executables-in-obsidian-plugins/89716/3>
- Tauri v2 sidecar pattern: <https://v2.tauri.app/develop/sidecar/>
- Tauri v2 mobile support (iOS + Android since late 2024): <https://www.pkgpulse.com/blog/best-desktop-app-frameworks-2026>
- Tauri vs Electron 2026 benchmarks: <https://tech-insider.org/tauri-vs-electron-2026/>
- Reor project status (no updates in 10 months): <https://openalternative.co/reor>
- Copilot for Obsidian architecture: <https://github.com/logancyang/obsidian-copilot>
- Copilot Ollama CORS setup: <https://github.com/logancyang/obsidian-copilot/blob/master/local_copilot.md>
- Smart Connections architecture (Transformers.js, `.smart-env/`): <https://deepwiki.com/brianpetro/obsidian-smart-connections/1.3-installation-and-setup>
- Smart Connections mobile support: <https://smartconnections.app/smart-connections/>
- obsidian-ai-chat-as-md (branching via headings): <https://github.com/cpbotha/obsidian-ai-chat-as-md>
- obsidian-llm-wiki-local (CLI + Obsidian pattern): <https://github.com/kytmanov/obsidian-llm-wiki-local>
- LiteLLM supply chain compromise (March 24, 2026): <https://docs.litellm.ai/blog/security-update-march-2026>
- Tauri + Python + Ollama sidecar case study: <https://dev.to/kination/story-of-smoodit-1-electron-to-tauri-3n7e>

---

## Decision

☐ **Approved as written** — proceed with Option C′ and propagate to MASTER-Checklist, D-006, D-009, Phase 4
☐ **Approved with modifications** (note below)
☐ **Rejected — revisit with new constraints** (note below)

_Notes:_
