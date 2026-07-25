"""AI Chat Tree Engine — MVP implementation."""
__version__ = "0.1.0"

from ai_chat_tree.model import Turno, Brancho, Fruito, Trunko, Node
from ai_chat_tree.vault_manager import VaultManager
from ai_chat_tree.vectors import VectorStore
from ai_chat_tree.engine import create_app, serve
from ai_chat_tree.validation import (
    TurnoSchema, BranchoSchema, FruitoSchema, TrunkoSchema,
    IntegrityReport, IntegrityIssue, check_integrity,
)

__all__ = [
    "Turno", "Brancho", "Fruito", "Trunko", "Node",
    "VaultManager", "VectorStore", "create_app", "serve",
    "TurnoSchema", "BranchoSchema", "FruitoSchema", "TrunkoSchema",
    "IntegrityReport", "IntegrityIssue", "check_integrity",
]
