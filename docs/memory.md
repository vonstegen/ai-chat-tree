# Memory System

## Dual-Layer Memory Architecture

### 1. Human Layer (Obsidian Vault)
- Plain Markdown files (`Turn-XXX.md`)
- Full history, links, backlinks, Dataview queries
- Human readable and editable

### 2. Machine Layer (Vector + Graph)
- Embeddings of every node (local: nomic-embed-text or bge)
- Vector DB: sqlite-vec / DuckDB
- Graph connections: parent/child, similar nodes, revisions
- Success metadata & learning loop weights

## Memory Operations
- **Ingestion**: Auto-embed on new Turn creation
- **Retrieval**: Hybrid (vector similarity + graph traversal + ancestry)
- **Learning Loop**: Periodic RLM reflection on successful nodes
- **Import**: Old chats parsed into structured nodes + fruits

## Goals
- Token-efficient context for LLMs
- Persistent, improvable long-term memory
- Zero context pollution