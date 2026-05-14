# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project initialization with full design documentation
- Core architecture defined: Trunk → Branch → Turn → Fruit hierarchy
- Dual memory system design: Human (Markdown) + Machine (Vector + Graph)
- RLM (Recursive Language Model) orchestration framework design
- D-001 decision: Option C′ (Plugin + Python Engine via HTTP)
- D-006 decision: TypeScript plugin + Python engine, HTTP IPC boundary
- `MASTER-Checklist.md` with Phases 0-8 and critical decisions tracker
- `docs/D-001-execution-environment.md` with full analysis and precedent research

### Project Structure
- `ai-chat-tree-engine/` - Python/FastAPI service (vector DB, RLM, embeddings)
- `ai-chat-tree-obsidian/` - Obsidian plugin (TypeScript)

## [0.1.0] - 2026-04-24

### Added
- Initial design phase
- Architecture documentation
- Folder structure specification
- Memory system design
- Instructions and guidelines
- Files and Fruits conventions

---

## Future Milestones

### [0.2.0] - Phase 1 Complete
- Core data model implementation
- File system operations for nodes
- Schema validation

### [0.3.0] - Phase 2 Complete
- RLM engine implementation
- REPL environment
- Core REPL tools

### [0.4.0] - Phase 3 Complete
- Vector embeddings
- Hybrid search
- Graph layer

### [0.5.0] - MVP
- Working Obsidian plugin
- Working Python engine
- First conversation import