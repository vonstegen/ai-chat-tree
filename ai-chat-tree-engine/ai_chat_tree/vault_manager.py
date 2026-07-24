"""VaultManager — the authoritative layer for turn file operations."""
from __future__ import annotations

import os
import re
import json
from datetime import datetime, timezone
from pathlib import Path, PurePath
from typing import Dict, Generator, List, Optional, Tuple

from .model import Turno, Brancho, Fruito, Trunko, Node, new_id


class VaultManager:
    """Manages the Obsidian vault structure, node persistence, and link integrity."""

    TURN_DIR = "turno-logs"
    FRUIT_DIR = "frutos"
    META_DIR = "_metadata"

    def __init__(self, vault_root: str):
        self.vault_root = Path(vault_root).expanduser().absolute()
        self.turn_repo = self.vault_root / self.TURN_DIR
        self.fruit_repo = self.vault_root / self.FRUIT_DIR
        self.meta_dir = self.vault_root / self.META_DIR
        self._validate()

    # ─── Validation ───────────────────────────────────────

    def _validate(self) -> None:
        """Ensure vault directories exist."""
        for path in [self.turn_repo, self.fruit_repo, self.meta_dir, self.branch_dir()]:
            path.mkdir(parents=True, exist_ok=True)

    # ─── Directories ──────────────────────────────────────

    def turno_dir(self, branch: str = None) -> Path:
        if branch:
            d = self.turn_repo / branch
            d.mkdir(parents=True, exist_ok=True)
            return d
        return self.turn_repo

    def trunoo_dir(self) -> Path:
        d = self.meta_dir / "trunks"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def branch_dir(self) -> Path:
        d = self.meta_dir / "branches"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def fruits_dir(self) -> Path:
        d = self.fruit_repo
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ─── Public mutation interface ────────────────────────

    def create_trunoo(self, name: str, description: str = "") -> Trunko:
        t = Trunko(id=new_id("trunk"), name=name, description=description)
        path = self.trunoo_dir() / f"{t.id}.md"
        path.write_text(t.to_markdown())
        return t

    def create_brancho(self, parent_turn: str = "trunk-001", name: str = "") -> Brancho:
        branch = Brancho(parent_turn=parent_turn, name=name)
        path = self.branch_dir() / f"{branch.id}.md"
        path.write_text(branch.to_markdown())
        return branch

    def create_turno(self, branch_id: str, prompt: str = "", response: str = "",
                     model: str = "default", source: str = "manual",
                     success_score: float = 0.0, tags: List[str] = None) -> Turno:
        t = Turno(
            id=new_id("turno"), branch=branch_id, model=model,
            prompt=prompt, response=response,
            success_score=success_score, tags=tags or [], source=source,
        )
        path = self.turno_dir(branch_id) / f"{t.id}.md"
        path.write_text(t.to_markdown())
        return t

    def create_fruito(self, turno_id: str, branch_id: str,
                      content: str, fruit_type: str = "text",
                      notes: str = "") -> Fruito:
        f = Fruito(id=new_id("fruit"), turno_id=turno_id, branch=branch_id,
                   content=content, fruit_type=fruit_type, notes=notes)
        path = self.fruits_dir() / f"{f.id}.md"
        path.write_text(f.to_markdown())
        return f

    def delete_node(self, node_id: str) -> str:
        found = self._find_file(node_id)
        if not found:
            raise FileNotFoundError(f"Node {node_id} not found")
        path_str = found.name
        found.unlink()
        return path_str

    def update_field(self, node_id: str, **kwargs) -> str:
        """Update specific fields on a node."""
        file_path = self._find_file(node_id)
        if not file_path:
            raise FileNotFoundError(f"Node {node_id} not found")
        content = file_path.read_text()
        node_cls = self._detect_node_type(content)
        if node_cls == Turno:
            node: Turno = Turno.from_markdown(content)
        elif node_cls == Brancho:
            node = Brancho.from_markdown(content)
        elif node_cls == Fruito:
            node = Fruito.from_markdown(content)
        elif node_cls == Trunko:
            node = Trunko.from_markdown(content)
        else:
            raise ValueError(f"Unknown node type for {node_id}")
        for k, v in kwargs.items():
            setattr(node, k, v)
        # If ID was updated, remove old file
        if "id" in kwargs and node.id != node_id:
            # Old file removed by new write
            pass
        file_path.write_text(node.to_markdown())
        return node.id

    # ─── Public query interface ───────────────────────────

    def list_nodes(self, node_type: str = "turno", branch: str = None,
                   limit: int = 50) -> List[Tuple[Node, str]]:
        """List all nodes. Returns list of (Node, relative_path) tuples."""
        if node_type == "trunoo":
            repo = self.trunoo_dir()
        elif node_type == "brancho":
            repo = self.branch_dir()
        elif node_type == "fruits":
            repo = self.fruits_dir()
        else:
            repo = self.turno_dir(branch)
        results = []
        for path in sorted(repo.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True):
            if path.stat().st_size == 0:
                continue
            try:
                content = path.read_text()
                node = self.node_from_markdown(content)
                results.append((node, str(path)))
            except Exception:
                continue
            if len(results) >= limit:
                break
        return results

    def get_ancestors(self, node_id: str) -> List[Node]:
        """Walk parent chain from a node."""
        return []  # TODO: implement parent link traversal

    def list_branches(self, active_only: bool = True) -> List[Brancho]:
        branches = []
        for node, _path in self.list_nodes("brancho"):
            if active_only and not node.active:
                continue
            branches.append(node)
        return branches

    # ─── Import helpers ───────────────────────────────────

    def import_chatgpt(self, json_path: str) -> int:
        """Import a ChatGPT conversation exported to JSON."""
        with open(json_path) as f:
            conv = json.load(f)
        count = 0
        for message in conv.get("message", {}).get("children", []):
            role = message.get("author", {}).get("role", "")
            if role not in ("assistant", "user"):
                continue
            parts = message.get("parts", [])
            text = " ".join([p.get("text", "") if isinstance(p, dict) else str(p) for p in parts])
            self.create_turno(
                prompt=text if role == "user" else "",
                response=text if role == "assistant" else "",
                model="chatgpt",
                source="imported",
            )
            count += 1
        return count

    def import_claude(self, json_path: str) -> int:
        """Import a Claude conversation exported to JSON."""
        with open(json_path) as f:
            data = json.load(f)
        if isinstance(data, dict) and "message" in data:
            data = data["message"].get("children", [data["message"]])
        if isinstance(data, dict):
            data = [data]
        count = 0
        for msg in data:
            if isinstance(msg, str):
                msg = {"role": "user", "content": [{"text": msg}]}
            role = msg.get("role", "")
            content = msg.get("content", "")
            if isinstance(content, list):
                text = " ".join([c.get("text", "") if isinstance(c, dict) else c for c in content])
            else:
                text = str(content)
            if role not in ("user", "assistant"):
                continue
            self.create_turno(
                prompt=text if role == "user" else "",
                response=text if role == "assistant" else "",
                model="claude",
                source="imported",
            )
            count += 1
        return count

    # ─── Internal helpers ─────────────────────────────────

    def _find_file(self, node_id: str) -> Optional[Path]:
        """Find a node file by ID across all repos."""
        for repo in [self.trunoo_dir(), self.branch_dir(), self.turno_dir(), self.fruits_dir()]:
            for path in repo.glob("*.md"):
                content = path.read_text()
                match = re.search(r"^id:\s+(\w+-)", content, re.MULTILINE)
                if match and match.group(1) == node_id:
                    return path
        return None

    def _detect_node_type(self, content: str):
        m = re.search(r"^type:\s+(\w+)", content, re.MULTILINE)
        if m:
            type_map = {
                "trunoo": Trunko, "brancho": Brancho,
                "turno": Turno, "fruits": Fruito,
            }
            return type_map.get(m.group(1), Turno)
        return Turno

    @staticmethod
    def node_from_markdown(content: str) -> Node:
        """Factory that parses markdown content and returns the correct Node class."""
        m = re.search(r"^type:\s+(\w+)", content, re.MULTILINE)
        if not m:
            raise ValueError("No type field in content")
        node_type = m.group(1)
        factory = {
            "trunoo": Trunko.from_markdown,
            "brancho": Brancho.from_markdown,
            "turno": Turno.from_markdown,
            "fruits": Fruito.from_markdown,
        }
        if node_type in factory:
            return factory[node_type](content)
        raise ValueError(f"Unknown type: {node_type}")
