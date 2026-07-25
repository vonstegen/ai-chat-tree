"""AI Chat Tree Engine — FastAPI HTTP server.

This module creates a single FastAPI app with all routes. No duplicate registrations.
"""
from __future__ import annotations

import os
import sys
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_chat_tree.vault_manager import VaultManager
from ai_chat_tree.vectors import VectorStore
from ai_chat_tree.model import Turno, Brancho, Fruito, Trunko, Node


# ─── Pydantic input schemas ───────────────────────

class TurnoInput(BaseModel):
    branch_id: str
    prompt: str = ""
    response: str = ""
    model: str = "default"
    source: str = "manual"
    success_score: float = 0.0
    tags: List[str] = []

class BranchoInput(BaseModel):
    parent_turn: str = "trunk-001"
    name: str

class FruitoInput(BaseModel):
    turno_id: str
    branch_id: str
    content: str
    fruit_type: str = "text"
    notes: str = ""

class SearchInput(BaseModel):
    query: str
    k: int = 12
    min_score: float = 0.0

class TrunkoInput(BaseModel):
    name: str
    description: str = ""


# ─── App factory ───────────────────────────────────

def create_app(vault_root: str) -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(title="AI Chat Tree Engine", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    vault = VaultManager(vault_root)
    vectors = VectorStore(os.path.join(vault_root, "vector_store.db"))

    # Health
    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "vault_root": str(vault.vault_root)}

    # Trunks
    @app.get("/trunks")
    def list_trunks():
        trunks = []
        for node, path in vault.list_nodes("trunk"):
            trunks.append(node.to_dict())
        return trunks

    @app.post("/trunks")
    def create_trunk(data: TrunkoInput):
        trunk = vault.create_trunk(data.name, data.description)
        return trunk.to_dict()

    # Branches
    @app.get("/branches")
    def list_branches():
        branches = []
        for node, path in vault.list_nodes("branch"):
            branches.append(node.to_dict())
        return branches

    @app.post("/branches")
    def create_branch(data: BranchoInput):
        branch = vault.create_brancho(parent_turn=data.parent_turn, name=data.name)
        return branch.to_dict()

    # Turns
    @app.get("/turnos")
    def list_turnos(branch: str = Query(None), limit: int = Query(50)):
        turns = []
        for node, path in vault.list_nodes("turn", branch=branch, limit=limit):
            turns.append(node.to_dict())
        return turns

    @app.get("/turnos/{node_id}")
    def get_turno(node_id: str):
        for node, path in vault.list_nodes("turn"):
            if node.id == node_id:
                return node.to_dict()
        raise HTTPException(404, f"Turno {node_id} not found")

    @app.post("/turnos")
    def create_turno(data: TurnoInput):
        turno = vault.create_turno(
            branch_id=data.branch_id,
            prompt=data.prompt,
            response=data.response,
            model=data.model,
            source=data.source,
            success_score=data.success_score,
            tags=data.tags,
        )
        vectors.ingest_turno(turno)
        return turno.to_dict()

    @app.get("/turnos/{node_id}/ancestors")
    def get_ancestors(node_id: str):
        ancestors = vault.get_ancestors(node_id)
        return [n.to_dict() for n in ancestors]

    @app.get("/turnos/{node_id}/children")
    def get_children(node_id: str):
        children = vault.get_children(node_id)
        return [n.to_dict() for n in children]

    # Fruits
    @app.get("/fruits")
    def list_fruits(turno_id: str = Query(None)):
        fruits = []
        for node, path in vault.list_nodes("fruit"):
            fruits.append(node.to_dict())
        return fruits

    @app.post("/fruits")
    def create_fruit(data: FruitoInput):
        fruit = vault.create_rotation(
            turno_id=data.turno_id,
            content=data.content,
            fruit_type=data.fruit_type,
            notes=data.notes,
        )
        return fruit.to_dict()

    @app.get("/fruits/{node_id}")
    def get_fruit(node_id: str):
        for node, path in vault.list_nodes("fruit"):
            if node.id == node_id:
                return node.to_dict()
        raise HTTPException(404, f"Fruito {node_id} not found")

    # Search
    @app.post("/search")
    def search(data: SearchInput):
        results = vectors.search(data.query, k=data.k)
        return {"query": data.query, "results": [(n.to_dict(), sim) for n, sim in results]}

    @app.get("/search")
    def search_get(query: str, k: int = 12):
        results = vectors.search(query, k)
        return {"query": query, "results": [(n.to_dict(), sim) for n, sim in results]}

    # Import
    @app.post("/import/chatgpt")
    def import_chatgpt(json_path: str):
        count = vault.import_chatgpt(json_path)
        for node, path in vault.list_nodes("turn"):
            vectors.ingest_turno(node)
        return {"imports": count}

    @app.post("/import/claude")
    def import_claude(json_path: str):
        count = vault.import_claude(json_path)
        for node, path in vault.list_nodes("turn"):
            vectors.ingest_turno(node)
        return {"imports": count}

    return app


def serve(vault_root: str, host: str = "0.0.0.0", port: int = 8765) -> None:
    """Start the server."""
    app = create_app(vault_root)
    print(f"Starting AI Chat Tree Engine on port {port}...")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    vault = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Documents/obsidian-chat-tree")
    serve(vault)
