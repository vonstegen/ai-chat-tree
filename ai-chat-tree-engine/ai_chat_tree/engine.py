"""AI Chat Tree Engine — FastAPI HTTP server."""
from __future__ import annotations

import os
import sys
import uvicorn
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, List, Optional

# Add parent to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_chat_tree.vault_manager import VaultManager
from ai_chat_tree.vectors import VectorStore
from ai_chat_tree.model import Turno, Brancho, Fruito, Trunko, Node


# ─── Pydantic input schemas ─────────────────────────────

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


# ─── Engine class ────────────────────────────────────────

class Engine:
    """Main application: vault manager + vector store."""

    def __init__(self, vault_root: str):
        self.vault = VaultManager(vault_root)
        self.vectors = VectorStore(os.path.join(vault_root, "vector_store.db"))


# ─── App factory ─────────────────────────────────────────

_engine: Optional[Engine] = None

def get_engine() -> Engine:
    if _engine is None:
        raise RuntimeError("Engine not initialized — call create_app first")
    return _engine

def create_app(vault_root: str) -> FastAPI:
    global _engine
    _engine = Engine(vault_root)
    app = FastAPI(title="AI Chat Tree Engine", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    vault = _engine.vault
    vectors = _engine.vectors

    # ─ Health ──────────────────────────────────────────────
    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "vault_root": str(vault.vault_root)}

    # ─ Trunks ──────────────────────────────────────────────
    @app.get("/trunks")
    def list_trunks():
        trunks = []
        for node, path in vault.list_nodes("trunoo"):
            trunks.append(node.to_dict())
        return trunks

    @app.post("/trunks")
    def create_trunk(data: TrunkoInput):
        trunk = vault.create_trunoo(data.name, data.description)
        return trunk.to_dict()

    # ─ Branches ─────────────────────────────────────────────
    @app.get("/branches")
    def list_branches():
        branches = []
        for node, path in vault.list_nodes("brancho"):
            branches.append(node.to_dict())
        return branches

    @app.post("/branches")
    def create_branch(data: BranchoInput):
        branch = vault.create_brancho(parent_turn=data.parent_turn, name=data.name)
        return branch.to_dict()

    # ─ Turns ───────────────────────────────────────────────
    @app.get("/turnos")
    def list_turnos(branch: str = Query(None), limit: int = Query(50)):
        turns = []
        for node, path in vault.list_nodes("turno", branch=branch, limit=limit):
            turns.append(node.to_dict())
        return turns

    @app.get("/turnos/{node_id}")
    def get_turno(node_id: str):
        for node, path in vault.list_nodes("turno"):
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

    # ─ Fruits ──────────────────────────────────────────────
    @app.get("/fruits")
    def list_fruits(turno_id: str = Query(None)):
        fruits = []
        for node, path in vault.list_nodes("fruits"):
            fruits.append(node.to_dict())
        return fruits

    @app.post("/fruits")
    def create_fruit(data: FruitoInput):
        fruit = vault.create_fruito(
            turno_id=data.turno_id,
            branch_id=data.branch_id,
            content=data.content,
            fruit_type=data.fruit_type,
            notes=data.notes,
        )
        return fruit.to_dict()

    @app.get("/fruits/{node_id}")
    def get_fruit(node_id: str):
        for node, path in vault.list_nodes("fruits"):
            if node.id == node_id:
                return node.to_dict()
        raise HTTPException(404, f"Fruito {node_id} not found")

    # ─ Search ──────────────────────────────────────────────
    @app.post("/search")
    def search(data: SearchInput):
        results = vectors.search(data.query, k=data.k)
        return {"query": data.query, "results": [(n.to_dict(), sim) for n, sim in results]}

    @app.get("/search")
    def search_get(query: str, k: int = 12):
        results = vectors.search(query, k)
        return {"query": query, "results": [(n.to_dict(), sim) for n, sim in results]}

    # ─ Import ──────────────────────────────────────────────
    @app.post("/import/chatgpt")
    def import_chatgpt(json_path: str):
        count = vault.import_chatgpt(json_path)
        for node, path in vault.list_nodes("turno"):
            vectors.ingest_turno(node)
        return {"imports": count}

    @app.post("/import/claude")
    def import_claude(json_path: str):
        count = vault.import_claude(json_path)
        for node, path in vault.list_nodes("turno"):
            vectors.ingest_turno(node)
        return {"imports": count}

    return app


# Module-level app instance for uvicorn compatibility
app = FastAPI(title="AI Chat Tree Engine", version="0.1.0")

# Also register all routes with this app
vault_root = "/home/vigil/Documents/obsidian-chat-tree"
os.makedirs(vault_root, exist_ok=True)
vault = VaultManager(vault_root)
vectors = VectorStore(os.path.join(vault_root, "vector_store.db"))

@app.on_event("startup")
async def startup():
    """Initialize vault and vectors on startup."""
    pass

@app.get("/ping")
async def ping():
    return {"status": "ok", "vault": vault_root}

@app.post("/trunks")
def create_trunk(data: TrunooInput):
    t = vault.create_trunko(name=data.name, description=data.description or "")
    return t.to_dict()

@app.get("/trunks")
def list_trunks():
    trunks = []
    for node, path in vault.list_nodes("trunks"):
        trunks.append(node.to_dict())
    return trunks

@app.post("/branches")
def create_brancho(data: BranchoInput):
    branch = vault.create_brancho(
        parent_turn=data.parent_turn,
        name=data.name,
    )
    return branch.to_dict()
@app.get("/branches")
def list_brancho(trunk_id: str = Query(None)):
    branches = []
    for node, path in vault.list_nodes("brancho", trunk=trunk_id or None):
        branches.append(node.to_dict())
    return branches

@app.get("/traverse")
def traverse_tree(branch_id: str = Query(None)):
    tree = vault.traverse_tree(branch_id or None)
    return tree

@app.get("/turnos")
def list_turnos(branch_id: str = Query(None), limit: int = 100):
    turns = []
    for node, path in vault.list_nodes("turno", branch=branch_id, limit=limit):
        turns.append(node.to_dict())
    return turns

@app.get("/turnos/{node_id}")
def get_turno(node_id: str):
    for node, path in vault.list_nodes("turno"):
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

@app.get("/fruits")
def list_fruits(turno_id: str = Query(None)):
    fruits = []
    for node, path in vault.list_nodes("fruits"):
        fruits.append(node.to_dict())
    return fruits

@app.post("/fruits")
def create_fruit(data: FruitoInput):
    fruit = vault.create_fruito(
        turno_id=data.turno_id,
        branch_id=data.branch_id,
        content=data.content,
        fruit_type=data.fruit_type,
        notes=data.notes,
    )
    return fruit.to_dict()

@app.get("/fruits/{node_id}")
def get_fruit(node_id: str):
    for node, path in vault.list_nodes("fruits"):
        if node.id == node_id:
            return node.to_dict()
    raise HTTPException(404, f"Fruito {node_id} not found")

@app.post("/search")
def search(data: SearchInput):
    results = vectors.search(data.query, k=data.k)
    return {"query": data.query, "results": [(n.to_dict(), sim) for n, sim in results]}

@app.get("/search")
def search_get(query: str, k: int = 12):
    results = vectors.search(query, k)
    return {"query": query, "results": [(n.to_dict(), sim) for n, sim in results]}

@app.post("/import/chatgpt")
def import_chatgpt(json_path: str):
    count = vault.import_chatgpt(json_path)
    for node, path in vault.list_nodes("turno"):
        vectors.ingest_turno(node)
    return {"imports": count}

@app.post("/import/claude")
def import_claude(json_path: str):
    count = vault.import_claude(json_path)
    for node, path in vault.list_nodes("turno"):
        vectors.ingest_turno(node)
    return {"imports": count}


def serve(vault_root: str, host: str = "0.0.0.0", port: int = 8765) -> None:
    """Start the server."""
    app = create_app(vault_root)
    print(f"Starting AI Chat Tree Engine on port {port}...")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    vault = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Documents/obsidian-chat-tree")
    serve(vault)
