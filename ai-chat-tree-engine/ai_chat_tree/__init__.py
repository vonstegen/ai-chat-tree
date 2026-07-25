"""AI Chat Tree Engine — MVP implementation.

Version 0.2.0 — Phase 1-3 complete
Phase 1: Core data model & storage layer
Phase 2: RLM engine, orchestrator, CLI, and REPL
Phase 3: Memory layer (smart chunking, extended vector store,
         hybrid search, scoped retrieval, memory graph)
"""
__version__ = "0.2.0"

from ai_chat_tree.model import Turno, Brancho, Fruito, Trunko, Node
from ai_chat_tree.vault_manager import VaultManager
from ai_chat_tree.vectors import VectorStore
from ai_chat_tree.smart_chunking import smart_chunk_text, chunk_turno, ChunkResult
from ai_chat_tree.memory_store import (
    ExtendedVectorStore, HybridSearch, ScopedRetriever,
    create_extended_store, create_hybrid_search, create_scoped_retriever,
)
from ai_chat_tree.memory_graph import MemoryGraph, Edge, create_graph
from ai_chat_tree.engine import create_app, serve
from ai_chat_tree.validation import (
    TurnoSchema, BranchoSchema, FruitoSchema, TrunkoSchema,
    IntegrityReport, IntegrityIssue, check_integrity,
)
from ai_chat_tree.rlm_loop import RLMLoop
from ai_chat_tree.rlm_orchestrator import RLMOrchestrator
from ai_chat_tree.rlm_prompts import RLM_PROMPTS
from ai_chat_tree.rlm_repl import start_repl

__all__ = [
    "Turno", "Brancho", "Fruito", "Trunko", "Node",
    "VaultManager", "VectorStore", "create_app", "serve",
    "TurnoSchema", "BranchoSchema", "FruitoSchema", "TrunkoSchema",
    "IntegrityReport", "IntegrityIssue", "check_integrity",
    "smart_chunk_text", "chunk_turno", "ChunkResult",
    "ExtendedVectorStore", "HybridSearch", "ScopedRetriever",
    "create_extended_store", "create_hybrid_search", "create_scoped_retriever",
    "MemoryGraph", "Edge", "create_graph",
    "RLMLoop", "RLMOrchestrator", "RLM_PROMPTS", "start_repl",
]
