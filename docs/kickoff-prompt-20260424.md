Kickoff: Resolve D-001 — Execution Environment for AI Chat Tree

Goal of this session: make a documented, defensible decision on the execution 
environment before writing any implementation code.

The three options on the table:
  A) Obsidian plugin (leverages existing ecosystem; closed-source host; plugin API constraints)
  B) Standalone Tauri or Electron app (full control; rebuilds vault/editor from scratch)
  C) Hybrid — plugin-first MVP → standalone fork later

Please execute this workflow:

1. Orient
   - Review MASTER-Checklist.md (especially the D-001 entry and linked decisions D-006, D-009)
   - Review architecture.md, memory.md, and files.md for the requirements we're placing 
     on whatever environment we pick

2. Research (web search required — don't rely on training data)
   - Current (2026) state of the Obsidian plugin API: custom views, sidecar/child 
     processes, file I/O, UI freedom, mobile parity
   - Tauri vs. Electron in 2026 for local-first markdown apps (bundle size, IPC, 
     security, ecosystem)
   - Precedent projects to study:
       * Reor (AI-native Obsidian alternative)
       * Copilot for Obsidian
       * Smart Connections
       * obsidian-ai-chat-as-md
       * Logseq plugin ecosystem
     For each: what they got right, what they hit walls on

3. Produce a decision document
   Structure:
   - Requirements AI Chat Tree places on the host (RLM REPL sidecar, local embeddings, 
     custom tree/graph view, streaming LLM, fruit file attachments, vector DB, 
     multi-model routing, Git-style revisions)
   - Capability matrix: for each of A/B/C, mark each requirement as 
     ✅ native / ⚠️ possible with work / ❌ blocker
   - Effort / time-to-MVP estimate per option (in weeks, with assumptions)
   - Risk & reversibility analysis (how hard is it to switch later?)
   - Dependency on D-006 (language choice) — which language pairs naturally with each option
   - Clear recommendation with reasoning

4. On my approval
   - Update MASTER-Checklist.md: mark D-001 complete, write the decision into a new 
     "Resolved Decisions" section, propagate implications to D-006 and Phase 4
   - Add a Changelog entry
   - Stage everything for commit

Constraints:
- No implementation code yet — this session is pure decision work
- Cite sources for any capability claims (web search results, not training data)
- If research reveals an option I haven't considered, surface it