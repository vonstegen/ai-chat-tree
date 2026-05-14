# AI Chat Tree Engine

Python/FastAPI service for AI Chat Tree — handles vault operations, RLM orchestration, embeddings, and vector search.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Obsidian Plugin                     │
│              (TypeScript HTTP client)                │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP (JSON)
                      ▼
┌─────────────────────────────────────────────────────┐
│              AI Chat Tree Engine                    │
│                   (FastAPI)                          │
├─────────────┬──────────────┬───────────────────────┤
│   Vault     │    RLM       │    Embeddings          │
│  Operations │  Orchestrat. │    + Vector DB         │
│  (Turn.io)  │  (REPL Loop) │    (sqlite-vec)        │
└─────────────┴──────────────┴───────────────────────┘
                      │
                      ▼
              ┌───────────────┐
              │   Ollama      │
              │ (local LLM)   │
              └───────────────┘
```

## Quick Start

```bash
# Install
pip install ai-chat-tree-engine
# or
uv tool install ai-chat-tree-engine

# Start server
act serve --vault /path/to/vault --port 8765

# Or import as library
from chat_tree_engine import VaultManager, RLMEngine
```

## Features

- **Vault Operations**: Create/manage Trunks, Branches, Turns, Fruits
- **RLM REPL**: Recursive tool-use loop for exploration
- **Vector Search**: Hybrid retrieval with sqlite-vec
- **Embeddings**: Local via Ollama (nomic-embed-text)
- **Import**: ChatGPT, Claude, and raw text format parsers

## CLI Commands

```bash
act serve        # Start HTTP server
act ingest       # Import conversation file
act search       # Vector search in vault
act stats        # Vault statistics
```

## Status

Phase 0 (Design) complete. Implementation not yet started.

See [MASTER-Checklist.md](../MASTER-Checklist.md) for full roadmap.