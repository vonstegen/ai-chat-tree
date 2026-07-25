# Contributing to AI Chat Tree 🌳

Thank you for your interest in the project. This document covers how to contribute to the codebase and documentation.

---

## Project Structure

```
ai-chat-tree/
├── ai-chat-tree-engine/          # Python/FastAPI backend
│   └── ai_chat_tree/             # Core package
│       ├── model.py              # Data models (Trunko, Brancho, Turno, Fruito)
│       ├── vault_manager.py      # Node persistence, CRUD, link integrity
│       ├── validation.py         # Pydantic schemas, guard clauses
│       ├── rlm_orchestrator.py   # RLM reasoning loop
│       ├── rlm_prompts.py        # System prompts
│       ├── vectors.py            # sqlite-vec embeddings
│       ├── extended_vector_store.py  # Hybrid search + metadata filters
│       ├── memory_graph.py       # Directed graph layer
│       ├── scoped_retriever.py   # Context assembly strategy
│       └── smart_chunking.py     # Turn content chunking
├── ai-chat-tree-obsidian/        # TypeScript Obsidian plugin (scaffolded)
├── docs/                         # This directory
├── MASTER-Checklist.md           # Project tracker
└── CHANGELOG.md                  # Release notes
```

## Development Workflow

### Prerequisites

- Python 3.11+ for the engine
- Node.js + TypeScript compiler for the Obsidian plugin
- Local vector engine (ollama-compatible) for embedding generation
- sqlite-vec dependency (via pip)

### Building the Engine

```bash
cd ai-chat-tree-engine
pip install -e .
python -c "from ai_chat_tree import Turno, Brancho; print('OK')"
```

### Running the Tree Engine Locally

```bash
cd ai-chat-tree-engine
uvicorn main:app --port 8765 --reload
```

The engine will serve the API at `http://localhost:8765`.

### Testing

Tests mirror the Python package structure under `tests/`. Run with:

```bash
cd ai-chat-tree-engine
pytest tests/
```

### Plugin Development

```bash
cd ai-chat-tree-obsidian
npm install
npm run dev    # Builds and watches
```

## Contributing Guidelines

### Code Style

- **Python:** Black formatting, type hints required, docstrings on all public methods
- **TypeScript:** Standard Obsidian plugin conventions, ES modules
- **Commit messages:** Follow conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`)

### Pull Requests

1. Create a branch from `main`
2. Make changes to a single feature or fix
3. Update `CHANGELOG.md` under `[Unreleased]`
4. Update `MASTER-Checklist.md` to reflect progress
5. Ensure all existing tests pass
6. Submit the PR with a clear description of what changed and why

### Documentation

- Architecture decisions belong in `docs/`
- Cross-reference related docs (glossary, architecture, roadmap)
- Keep docs aligned with the code — outdated documentation is worse than none

## Design Philosophy

This project prioritizes:

1. **Immutability** — Turns are never modified. Revisions create new nodes.
2. **Sovereignty** — Everything runs locally. No external API dependencies.
3. **Structured reasoning** — Every interaction follows a documented reasoning pattern (RLM).
4. **Replicability** — The system should be fully clonable and reproducible by others.

## Getting Help

- Open an issue for bugs or feature requests
- Refer to [MASTER-Checklist.md](./MASTER-Checklist.md) for project status
- Check [gork-chat-ai_chat_tree_design.md](./gork-chat-ai_chat_tree_design.md) for the original design conversation

---

*Created: 2026-07-25*
*License: MIT*
