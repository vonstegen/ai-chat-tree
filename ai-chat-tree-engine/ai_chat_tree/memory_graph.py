"""Memory Graph — relational structure over turns, branches, and their semantic connections.

Edge types:
  - `parent_of`: Turno A is the parent turn of Turno B (branch point)
  - `revision_of`: Turno A is a revision of Turno B
  - `similar_to`: Turno A and Turno B are semantically similar (above threshold)
  - `merged_into`: Branch A was merged into Turno B
  - `fruit_of`: Fruito is produced by Turno A

Stored in a lightweight sqlite graph (adjacency list), with a separate edge metadata table
for similarity scores, merge dates, etc.
"""
from __future__ import annotations

import sqlite3
import json
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Set, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Edge:
    """A directed edge in the memory graph."""
    src: str          # source node ID
    dst: str          # destination node ID
    edge_type: str    # parent_of, revision_of, similar_to, merged_into, fruit_of
    metadata: Dict[str, Any] = field(default_factory=dict)
    created: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now(timezone.utc).isoformat()

    def to_tuple(self) -> Tuple[str, str, str, str, str]:
        return (self.src, self.dst, self.edge_type, json.dumps(self.metadata), self.created)

    @classmethod
    def from_row(cls, row: Tuple) -> Edge:
        src, dst, edge_type, metadata, created = row
        return cls(
            src=src, dst=dst, edge_type=edge_type,
            metadata=json.loads(metadata) if isinstance(metadata, str) else metadata,
            created=created,
        )


class MemoryGraph:
    """Directed graph over turns/branches with typed edges.

    Uses sqlite for persistence, adjacency-list schema:
      edges(src, dst, edge_type, metadata, created) — PK = (src, dst, edge_type)
      nodes(id, type, label)                           — node registry
    """

    def __init__(self, db_path: str = "memory_graph.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    # ─── DB Init ──

    def _init_db(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS nodes (
                id     TEXT PRIMARY KEY,
                type   TEXT NOT NULL,   -- turno, branch, fruit
                label  TEXT
            )
        """)
        c.execute("""
            CREATE TABLE IF NOT EXISTS edges (
                src       TEXT NOT NULL,
                dst       TEXT NOT NULL,
                edge_type TEXT NOT NULL,
                metadata  TEXT DEFAULT '{}',
                created   TEXT,
                PRIMARY KEY (src, dst, edge_type)
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_edges_dst ON edges (dst)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_edges_type ON edges (edge_type)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes (type)")
        conn.commit()
        conn.close()

    # ─── Node Operations ──

    def add_node(self, node_id: str, node_type: str, label: str = "") -> bool:
        """Add a node (turn, branch, or fruit) to the graph."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute(
                "INSERT OR IGNORE INTO nodes (id, type, label) VALUES (?, ?, ?)",
                (node_id, node_type, label),
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def remove_node(self, node_id: str) -> bool:
        """Remove a node and all its edges."""
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute("DELETE FROM edges WHERE src = ? OR dst = ?", (node_id, node_id))
            c.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def node_exists(self, node_id: str) -> bool:
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("SELECT 1 FROM nodes WHERE id = ?", (node_id,))
        exists = c.fetchone() is not None
        conn.close()
        return exists

    # ─── Edge Operations ──

    EDGE_TYPES = {"parent_of", "revision_of", "similar_to", "merged_into", "fruit_of"}

    def add_edge(self, src: str, dst: str, edge_type: str, metadata: Dict = None) -> bool:
        """Add a typed directed edge."""
        if edge_type not in self.EDGE_TYPES:
            return False
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute(
                "INSERT OR IGNORE INTO edges (src, dst, edge_type, metadata, created) VALUES (?, ?, ?, ?, ?)",
                (src, dst, edge_type, json.dumps(metadata or {}), datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def remove_edge(self, src: str, dst: str, edge_type: str) -> bool:
        try:
            conn = sqlite3.connect(str(self.db_path))
            c = conn.cursor()
            c.execute(
                "DELETE FROM edges WHERE src = ? AND dst = ? AND edge_type = ?",
                (src, dst, edge_type),
            )
            conn.commit()
            conn.close()
            return c.rowcount > 0
        except Exception:
            return False

    def edges_count(self, edge_type: str = None) -> int:
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        if edge_type:
            c.execute("SELECT COUNT(*) FROM edges WHERE edge_type = ?", (edge_type,))
        else:
            c.execute("SELECT COUNT(*) FROM edges")
        count = c.fetchone()[0]
        conn.close()
        return count

    # ─── Traversal Helpers ──

    def get_children(self, node_id: str, edge_type: str = None) -> List[str]:
        """Get all nodes that n node_id points to."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        if edge_type:
            c.execute("SELECT dst FROM edges WHERE src = ? AND edge_type = ?", (node_id, edge_type))
        else:
            c.execute("SELECT dst FROM edges WHERE src = ?", (node_id,))
        nodes = [r[0] for r in c.fetchall()]
        conn.close()
        return nodes

    def get_parents(self, node_id: str, edge_type: str = None) -> List[str]:
        """Get all nodes that point to n node_id."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        if edge_type:
            c.execute("SELECT src FROM edges WHERE dst = ? AND edge_type = ?", (node_id, edge_type))
        else:
            c.execute("SELECT src FROM edges WHERE dst = ?", (node_id,))
        nodes = [r[0] for r in c.fetchall()]
        conn.close()
        return nodes

    def get_outgoing_edges(self, node_id: str, edge_type: str = None) -> List[Edge]:
        """Get all outgoing edges from a node."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        sql = "SELECT src, dst, edge_type, metadata, created FROM edges WHERE src = ?"
        params = [node_id]
        if edge_type:
            sql += " AND edge_type = ?"
            params.append(edge_type)
        c.execute(sql, params)
        edges = [Edge.from_row(r) for r in c.fetchall()]
        conn.close()
        return edges

    def get_incoming_edges(self, node_id: str, edge_type: str = None) -> List[Edge]:
        """Get all incoming edges to a node."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        sql = "SELECT src, dst, edge_type, metadata, created FROM edges WHERE dst = ?"
        params = [node_id]
        if edge_type:
            sql += " AND edge_type = ?"
            params.append(edge_type)
        c.execute(sql, params)
        edges = [Edge.from_row(r) for r in c.fetchall()]
        conn.close()
        return edges

    def walk_ancestry(self, start_id: str, max_depth: int = 10) -> List[str]:
        """Walk up the parent_of chain from start_id."""
        chain = [start_id]
        visited = {start_id}
        current = start_id
        depth = 0

        while depth < max_depth and current:
            parents = self.get_parents(current, edge_type="parent_of")
            if not parents:
                break
            parent = parents[0]  # single parent in a turn chain
            if parent in visited:
                break
            visited.add(parent)
            chain.append(parent)
            current = parent
            depth += 1

        return chain

    def walk_descendants(self, start_id: str, max_depth: int = 10) -> Dict[str, List[str]]:
        """Walk down (all child nodes) from start_id, returns {node: [children]}."""
        result: Dict[str, List[str]] = {}
        visited = {start_id: []}
        queue = [start_id]
        depth = 0

        while queue and depth < max_depth:
            next_queue = []
            for node in queue:
                children = self.get_children(node)
                result[node] = children
                next_queue.extend(children)
            queue = next_queue
            depth += 1

        return result

    def walk_descendants_flat(self, start_id: str, max_depth: int = 10) -> List[str]:
        """Walk down and return all descendant node IDs."""
        descendants: List[str] = []
        visited = {start_id}
        queue = [start_id]
        depth = 0

        while queue and depth < max_depth:
            depth += 1
            queue.extend([c for child in queue for c in self.get_children(child) if c not in visited])
            for child in queue:
                if child not in visited:
                    descendants.append(child)
                    visited.add(child)

        return descendants

    # ─── Graph Analysis ──

    def find_similar_clusters(self, min_size: int = 2, similarity_threshold: float = 0.7) -> List[List[str]]:
        """Find groups of turns that are mutually similar (graphRAG-style community detection).

        Uses naive connected components on similar_to edges above a threshold.
        """
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        # Get all similar edges
        c.execute("SELECT src, dst, CAST(metadata AS TEXT) FROM edges WHERE edge_type = 'similar_to'")
        similar_edges = c.fetchall()

        # Build adjacency with similarity filter
        adj: Dict[str, Set[str]] = {}
        for src, dst, meta_str in similar_edges:
            metadata = json.loads(meta_str) if isinstance(meta_str, str) else meta_str
            score = metadata.get("score", 0.0)
            if score >= similarity_threshold:
                adj.setdefault(src, set()).add(dst)
                adj.setdefault(dst, set()).add(src)

        # Connected components via BFS
        visited = set()
        clusters: List[List[str]] = []

        for node in adj:
            if node in visited:
                continue
            # BFS from this node
            cluster = []
            queue = [node]
            while queue:
                current = queue.pop(0)
                if current in visited:
                    continue
                visited.add(current)
                cluster.append(current)
                for neighbor in adj.get(current, set()):
                    if neighbor not in visited:
                        queue.append(neighbor)
            if len(cluster) >= min_size:
                clusters.append(cluster)

        conn.close()

        # Remove clusters that are subsets of larger ones
        filtered = []
        for c in clusters:
            if not any(set(c).issubset(set(l)) and len(l) > len(c) for l in filtered):
                filtered.append(c)

        return filtered

    def branch_fanout(self, trunk_id: str) -> Dict[str, int]:
        """Count descendants per branch from a trunk."""
        trunk_children = self.get_children(trunk_id, edge_type="merged_into")
        fanout = {}
        for branch_start in trunk_children:
            fans = self.walk_descendants_flat(branch_start, max_depth=10)
            fanout[branch_start] = len(fans)
        return fanout

    # ─── Graph Summary ──

    def summary(self) -> Dict[str, Any]:
        """Get a quick summary of the graph structure."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        c.execute("SELECT type, COUNT(*) FROM nodes GROUP BY type")
        node_counts = dict(c.fetchall())

        c.execute("SELECT edge_type, COUNT(*) FROM edges GROUP BY edge_type")
        edge_counts = dict(c.fetchall())

        c.execute("SELECT MIN(created) FROM edges")
        oldest = c.fetchone()[0]
        c.execute("SELECT MAX(created) FROM edges")
        newest = c.fetchone()[0]

        conn.close()

        return {
            **node_counts,
            "edge_counts": edge_counts,
            "total_edges": sum(edge_counts.values()) if edge_counts else 0,
            "oldest_edge": oldest,
            "newest_edge": newest,
        }

    def clear(self) -> None:
        """Drop all graph data."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("DELETE FROM nodes")
        c.execute("DELETE FROM edges")
        conn.commit()
        conn.close()


# ─── Module-level convenience ──

def create_graph(db_path: str = "memory_graph.db") -> MemoryGraph:
    return MemoryGraph(db_path)
