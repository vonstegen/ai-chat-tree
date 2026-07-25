"""VaultManager — the authoritative layer for turn file operations.

Implements:
- Turn/Branch/Trunk/Fruit CRUD with atomic writes
- Per-turn fruit scaffolding (D-008)
- Revision tracking (D-010)
- Ancestry/children walks (D-XXX)
- Link integrity checking
- Import helpers
"""
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
    TRUNK_DIR = "_trunks"
    META_DIR = "_metadata"

    def __init__(self, vault_root: str):
        self.vault_root = Path(vault_root).expanduser().absolute()
        self.turn_repo = self.vault_root / self.TURN_DIR
        self.fruit_repo = self.vault_root / self.FRUIT_DIR
        self.trunk_repo = self.vault_root / self.TRUNK_DIR
        self.meta_dir = self.vault_root / self.META_DIR
        self._validate()

    # ─── Validation ───────────────────────────────────────

    def _validate(self) -> None:
        """Ensure vault directories exist."""
        for p in [self.turn_repo, self.fruit_repo, self.trunk_repo, self.meta_dir]:
            p.mkdir(parents=True, exist_ok=True)

    # ─── Directories ──────────────────────────────────────

    def turno_dir(self, branch: Optional[str] = None) -> Path:
        if branch:
            d = self.turn_repo / branch
            d.mkdir(parents=True, exist_ok=True)
            return d
        return self.turn_repo

    def trunks_dir(self) -> Path:
        return self.trunk_repo

    def branch_dir(self) -> Path:
        d = self.meta_dir / "branches"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def fruits_dir(self) -> Path:
        d = self.fruit_repo
        d.mkdir(parents=True, exist_ok=True)
        return d

    # ─── Public mutation interface ────────────────────────

    def create_trunk(self, name: str, description: str = "") -> Trunko:
        """Create a trunk with metadata file."""
        trunk = Trunko(id=new_id("trunk"), name=name, description=description)
        trunk_dir = self.trunks_dir() / trunk.id
        trunk_dir.mkdir(parents=True, exist_ok=True)
        path = trunk_dir / "_trunk.md"
        path.write_text(trunk.to_markdown())
        return trunk

    def create_brancho(self, parent_turn: str = "trunk-001", name: str = "") -> Brancho:
        """Create a branch linked from a trunk."""
        branch = Brancho(parent_turn=parent_turn, name=name)
        path = self.branch_dir() / f"{branch.id}.md"
        path.write_text(branch.to_markdown())
        # Update trunk's branch list
        self._update_trunk_branches(branch.id)
        return branch

    def create_turno(self,
                     branch_id: str,
                     prompt: str = "",
                     response: str = "",
                     model: str = "default",
                     source: str = "manual",
                     success_score: float = 0.0,
                     tags: List[str] = None,
                     parent_turn: Optional[str] = None) -> Turno:
        """Create a turn with atomic write and fruit scaffold."""
        turno = Turno(
            id=new_id("turn"),
            branch=branch_id,
            model=model,
            prompt=prompt,
            response=response,
            success_score=success_score,
            tags=tags or [],
            source=source,
            parent_turn=parent_turn,
        )
        turn_dir = self.turno_dir(branch_id)
        turn_dir.mkdir(parents=True, exist_ok=True)
        path = turn_dir / f"{turno.id}.md"
        path.write_text(turno.to_markdown())
        # Scaffold fruits directory (D-008)
        fruits_dir = turn_dir / f"{turno.id}-fruits"
        fruits_dir.mkdir(exist_ok=True)
        return turno

    def create_rotation(self, turno_id: str, content: str,
                        fruit_type: str = "script",
                        notes: str = "") -> Fruito:
        """Create a fruit (output/asset) attached to a turn."""
        turno = None
        for node, _path in self.list_nodes("turn"):
            if node.id == turno_id:
                turno = node
                break
        if not turno:
            raise FileNotFoundError(f"Turn {turno_id} not found for fruit creation")

        fruit = Fruito(
            id=new_id("fruit"),
            turno_id=turno_id,
            branch=turno.branch,
            content=content,
            fruit_type=fruit_type,
            notes=notes,
            file_path=None,  # Will be set if external file saved
        )
        # Write fruit markdown in fruit repo
        path = self.fruits_dir() / f"{fruit.id}.md"
        path.write_text(fruit.to_markdown())
        # Also place in turno's fruits dir
        turno_fruits = self.turno_dir(turno.branch) / f"{turno_id}-fruits"
        turno_fruits.mkdir(parents=True, exist_ok=True)
        ext = self._extension_for_type(fruit_type)
        if ext:
            file_path = turno_fruits / f"{fruit.id}{ext}"
            file_path.write_text(content)
            fruit.file_path = f"{turno_id}-fruits/{file_path.name}"
            path.write_text(fruit.to_markdown())
        else:
            fruit.file_path = f"{turno_id}-fruits/{fruit.id}.txt"
            file_path = turno_fruits / fruit.file_path
            file_path.write_text(content)
        return fruit

    def delete_node(self, node_id: str, cascade: bool = True) -> str:
        """Delete a node file. Optionally cascade delete children/fruits."""
        found = self._find_file(node_id)
        if not found:
            raise FileNotFoundError(f"Node {node_id} not found")
        path_str = str(found.relative_to(self.vault_root))
        found.unlink()
        if cascade:
            # Remove fruits dir if it exists
            turno_fruits = found.parent / f"{node_id}-fruits"
            if turno_fruits.exists():
                import shutil
                shutil.rmtree(turno_fruits)
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
        file_path.write_text(node.to_markdown())
        return node.id

    def create_revision(self, turno_id: str, new_prompt: str,
                        change_reason: str = "", model: str = "default") -> Turno:
        """Create a revision node (D-010: inline linked node)."""
        original = None
        for node, _path in self.list_nodes("turn"):
            if node.id == turno_id:
                original = node
                break
        if not original:
            raise FileNotFoundError(f"Turn {turno_id} not found for revision creation")

        revision = Turno(
            id=new_id("rev"),
            branch=original.branch,
            model=model or original.model,
            prompt=new_prompt,
            response="",
            revision_of=turno_id,
            revision_number=original.revision_number + 1,
            change_reason=change_reason,
            source="revision",
            parent_turn=original.id,
        )
        revision_dir = self.turno_dir(revision.branch)
        revision_dir.mkdir(parents=True, exist_ok=True)
        path = revision_dir / f"{revision.id}.md"
        path.write_text(revision.to_markdown())
        # Update original's revision link
        self.update_field(turno_id, revision_number=original.revision_number)
        return revision

    # ─── Public query interface ───────────────────────────

    def list_nodes(self, node_type: str = "turn", branch: Optional[str] = None,
                   limit: int = 50) -> List[Tuple[Node, str]]:
        """List all nodes. Returns list of (Node, relative_path) tuples."""
        if node_type == "trunk":
            repo = self.trunks_dir()
        elif node_type == "branch":
            repo = self.branch_dir()
        elif node_type == "fruit":
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
                results.append((node, str(path.relative_to(self.vault_root))))
            except Exception:
                continue
            if len(results) >= limit:
                break
        return results

    def get_ancestors(self, node_id: str) -> List[Node]:
        """Walk parent chain from a node (ancestry walk)."""
        ancestors = []
        current_id = node_id
        visited = set()
        while current_id:
            if current_id in visited:
                break
            visited.add(current_id)
            found = None
            for node, _path in self.list_nodes("turn"):
                if node.id == current_id:
                    found = node
                    break
            if not found:
                break
            if found.parent_turn:
                ancestors.insert(0, found)
                current_id = found.parent_turn
            else:
                break
        return ancestors

    def get_children(self, node_id: str) -> List[Node]:
        """Walk children of a node (scans for turns where parent_id == node_id)."""
        children = []
        for node, _path in self.list_nodes("turn"):
            if node.parent_turn == node_id or node.revision_of == node_id:
                children.append(node)
        return children

    def list_branches(self, active_only: bool = True) -> List[Brancho]:
        """List all branches."""
        branches = []
        for node, _path in self.list_nodes("branch"):
            if active_only and not node.active:
                continue
            branches.append(node)
        return branches

    def traverse_tree(self, branch_id: Optional[str] = None) -> dict:
        """Traverse the full tree from a branch or trunk."""
        tree = {}
        if branch_id:
            # Trunk-level tree
            node_map = {}
            for node, _path in self.list_nodes("turn"):
                node_map[node.id] = node

            # Find roots (no parent_turn)
            roots = [n for n in node_map.values() if not n.parent_turn]
            for root in roots:
                node_map[root.id] = {"node": root, "children": []}

            for nid, node in list(node_map.items()):
                entry = node_map.get(nid)
                if entry and isinstance(entry, dict):
                    entry["node"] = node

            for nid, node in list(node_map.items()):
                parent = node.parent_turn
                if parent and parent in node_map and isinstance(node_map[parent], dict):
                    node_map[parent]["children"].append({"node": node, "children": []})
                elif not parent:
                    pass  # root

            tree = {nid: node_map.get(nid, {}) for nid in node_map}
        else:
            tree = {"turns": [(n.id, n.to_dict()) for n, _ in self.list_nodes("turn")],
                    "branches": [(b.id, b.to_dict()) for b in self.list_branches(False)],
                    "trunks": [(t.id, t.to_dict()) for t, _ in self.list_nodes("trunk")]}
        return tree

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
        for repo in [self.trunks_dir(), self.branch_dir(), self.turno_dir(), self.fruits_dir()]:
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
                "trunk": Trunko, "branch": Brancho,
                "turn": Turno, "fruit": Fruito,
            }
            return type_map.get(m.group(1), Turno)
        return Turno

    def node_from_markdown(self, content: str) -> Node:
        """Factory that parses markdown frontmatter and returns the correct Node."""
        m = re.search(r"^type:\s+(\w+)", content, re.MULTILINE)
        if not m:
            raise ValueError("No type field in content")
        node_type = m.group(1)
        factory = {
            "trunk": Trunko.from_markdown,
            "branch": Brancho.from_markdown,
            "turn": Turno.from_markdown,
            "fruit": Fruito.from_markdown,
        }
        if node_type in factory:
            return factory[node_type](content)
        raise ValueError(f"Unknown type: {node_type}")

    def _update_trunk_branches(self, branch_id: str) -> None:
        """Update the trunk's branch list to include a new branch."""
        for trunk in self.trunks_dir().glob("*"):
            trunk_file = trunk / "_trunk.md"
            if not trunk_file.exists():
                continue
            try:
                content = trunk_file.read_text()
                trunk_obj = Trunko.from_markdown(content)
                trunk_obj.branches.append(branch_id)
                trunk_file.write_text(trunk_obj.to_markdown())
            except Exception:
                pass

    def _extension_for_type(self, fruit_type: str) -> Optional[str]:
        """Return file extension for a given fruit_type."""
        ext_map = {
            "script": ".py", "image": ".png", "diagram": ".svg",
            "terminal": ".sh", "diff": ".diff", "other": ".txt",
        }
        return ext_map.get(fruit_type)
