"""Vector store using sqlite for embeddings and similarity search."""
from __future__ import annotations

import sqlite3
import hashlib
from pathlib import Path
from typing import List, Optional, Tuple

from .model import Turno


class VectorStore:
    """sqlite-backed vector store for turn embeddings."""

    def __init__(self, db_path: str = "vector_store.db"):
        self.db_path = Path(db_path)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id TEXT PRIMARY KEY,
                turn_id TEXT,
                chunk_idx INTEGER,
                chunk_text TEXT,
                embedding_bf32 BLOB,
                branch TEXT,
                model TEXT,
                timestamp TEXT,
                success_score REAL,
                tags TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_turns ON chunks (turn_id)")
        conn.commit()
        conn.close()

    def _embed(self, text: str) -> bytes:
        """Generate a 1536-dim float32 embedding using placeholder hashing.

        In production this calls Ollama (nomic-embed-text) or a real embedding provider.
        """
        import struct
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        # Expand hash to 1536 floats in [-1, 1]
        dims = int(1536 * 2)  # need 2 hex chars per float
        raw = [ord(c) / 127.0 - 1.0 for c in (h * 20)[:dims]]
        vec = [raw[i] if i < len(raw) else 0.0 for i in range(1536)]
        return struct.pack(f"{len(vec)}f", *vec)

    def ingest_turno(self, turno: Turno) -> None:
        """Chunk a turno and ingest into vector store."""
        chunks = []
        # Split prompt and response into chunks of ~500 chars
        for field_name, value in [("prompt", turno.prompt), ("response", turno.response)]:
            if not value:
                continue
            for i in range(0, len(value), 500):
                chunk_text = value[i:i+500]
                if len(chunk_text.strip()) < 20:
                    continue
                chunk_id = f"{turno.id}-{field_name}-{i//500}"
                chunks.append((chunk_id, turno.id, i//500, chunk_text, turno.branch,
                              turno.model, turno.timestamp, turno.success_score, str(turno.tags)))

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        for chunk_id, turn_id, idx, text, branch, model, ts, score, tags in chunks:
            embedding = self._embed(text)
            c.execute(
                "INSERT OR REPLACE INTO chunks VALUES (?,?,?,?,?,?,?,?,?,?)",
                (chunk_id, turn_id, idx, text, embedding, branch, model, ts, score, tags),
            )
        conn.commit()
        conn.close()

    def search(self, query: str, k: int = 12) -> List[Tuple[Turno, float]]:
        """Search for similar turns to a query.

        Returns list of (Turno, relevance_score).
        """
        import struct
        query_emb = self._embed(query)
        # Decode query to flat list
        q_vals = struct.unpack(f"{len(query_emb)//4}f", query_emb)
        n = len(q_vals)

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("SELECT turn_id, chunk_idx, chunk_text, branch, model, timestamp, success_score, tags FROM chunks")
        rows = c.fetchall()
        conn.close()

        if not rows:
            return []

        candidates = {}
        for row in rows:
            turn_id, idx, text, branch, model, ts, score, tags = row
            vec_bytes = row[3]  # Wait — need to map columns properly
            # Fix column mapping: [0]=id [1]=turn_id [2]=idx [3]=text [4]=emb [5]=branch ...
            turn_id_c = row[1]
            vec_b = row[4]
            if len(vec_b) != 1536 * 4:
                continue
            vec_c = struct.unpack(f"1536f", vec_b)
            # Cosine similarity
            dot = sum(a * b for a, b in zip(q_vals, vec_c))
            norm_q = sum(a * a for a in q_vals) ** 0.5
            norm_vec = sum(b * b for b in vec_c) ** 0.5
            if norm_q == 0 or norm_vec == 0:
                continue
            similarity = dot / (norm_q * norm_vec)
            if turn_id_c not in candidates:
                candidates[turn_id_c] = (similarity, text)
            else:
                best_sim, best_text = candidates[turn_id_c]
                candidates[turn_id_c] = (max(similarity, best_sim), best_text)

        ranked = sorted(candidates.values(), key=lambda x: x[0], reverse=True)[:k]
        results = []
        seen = set()
        for sim, text in ranked:
            turno = Turno(
                id="placeholder", branch="placeholder", prompt=text[:200],
                response="", timestamp="", success_score=0.0,
            )
            seen.add(turno.id)
            # Store similarity to return
            results.append((turno, sim))

        return results
