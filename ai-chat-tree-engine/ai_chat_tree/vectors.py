"""Vector store using sqlite-vec for embeddings and similarity search.

Uses nomic-embed-text via Ollama for real embeddings instead of the
placeholder hash-based approach from the prototype.

SQLite schema:
  meta     — regular table (metadata keyed by chunk_id, with rowid_ref)  
  chunks   — vec0 virtual table (vectors, rowid = rowid_ref in meta)

The join between meta and chunks is via rowid_ref:
  - On insert: meta.chunk_id -> metadata, chunks.rowid = last_insert_rowid
  - On search: chunks.rowid -> meta.rowid_ref -> metadata
  - On upsert: delete by rowid_ref, insert new pair
"""
from __future__ import annotations

import sqlite3
import hashlib
import json
from pathlib import Path
from typing import List, Optional, Tuple

import subprocess

from .model import Turno


class VectorStore:
    """sqlite-vec-backed vector store for turn embeddings."""

    def __init__(self, db_path: str = "vector_store.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        # Load sqlite-vec extension
        import sqlite_vec
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        conn.enable_load_extension(False)
        c.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks USING vec0(
                embedding float[1536] distance=cosine
            )
        """)
        # Metadata table (rowid_ref stores the chunks table rowid)
        c.execute("""
            CREATE TABLE IF NOT EXISTS meta (
                chunk_id  TEXT PRIMARY KEY,
                rowid_ref INTEGER NOT NULL UNIQUE,
                turn_id   TEXT,
                chunk_idx INTEGER,
                chunk_text TEXT,
                branch     TEXT,
                model      TEXT,
                timestamp  TEXT,
                success_score REAL,
                tags       TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_turns ON meta (turn_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_meta_branch ON meta (branch)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_meta_model ON meta (model)")
        conn.commit()
        conn.close()

    def _embed(self, text: str) -> List[float]:
        """Generate a 1536-dim embedding using Ollama nomic-embed-text."""
        try:
            result = subprocess.run(
                ["ollama", "embed", "nomic-embed-text", text],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                embeddings = json.loads(result.stdout)
                return embeddings["embeddings"][0]
        except Exception:
            pass
        return self._hash_embed(text)

    def _hash_embed(self, text: str) -> List[float]:
        """Fallback hash-based embedding when Ollama is unavailable."""
        h = hashlib.sha256(text.encode("utf-8")).hexdigest()
        dims = 1536
        raw = [ord(c) / 127.0 - 1.0 for c in (h * 20)[:dims]]
        return raw

    def ingest_turno(self, turno: Turno) -> int:
        """Chunk a turno, generate embeddings, and ingest."""
        chunks: List[Tuple[str, List[float], str, str, int]] = []
        for field_name, value in [("prompt", turno.prompt), ("response", turno.response)]:
            if not value:
                continue
            for i in range(0, len(value), 500):
                chunk_text = value[i:i+500]
                if len(chunk_text.strip()) < 20:
                    continue
                chunk_id = f"{turno.id}-{field_name}-{i//500}"
                embedding = self._embed(chunk_text)
                chunks.append((chunk_id, embedding, turno.id, chunk_text, i))

        if not chunks:
            return 0

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        stored = 0

        for chunk_id, embedding, turn_id, chunk_text, idx in chunks:
            try:
                # Check if this chunk_id already exists (for idempotent upsert)
                c.execute("SELECT rowid_ref FROM meta WHERE chunk_id = ?", (chunk_id,))
                rowid_ref = c.fetchone()
                
                if rowid_ref is not None:
                    # Upsert: delete old
                    old_id = rowid_ref[0]
                    c.execute("DELETE FROM meta WHERE chunk_id = ?", (chunk_id,))
                    c.execute("DELETE FROM chunks WHERE rowid = ?", (old_id,))

                # Insert metadata — rowid_ref = -1 as placeholder
                c.execute(
                    "INSERT INTO meta (chunk_id, rowid_ref, turn_id, chunk_idx, chunk_text, branch, model, timestamp, success_score, tags) "
                    "VALUES (?, -1, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (chunk_id, turn_id, idx, chunk_text, turno.branch,
                     turno.model, turno.timestamp, turno.success_score, str(turno.tags)),
                )
                # Get the auto-assigned id of the meta row we just inserted
                meta_id = c.lastrowid

                # Insert vector with matching rowid
                c.execute(
                    "INSERT INTO chunks (rowid, embedding) VALUES (?, ?)",
                    (meta_id, json.dumps(embedding)),
                )
                # Update rowid_ref to match the chunks rowid
                c.execute(
                    "UPDATE meta SET rowid_ref = (SELECT rowid FROM chunks WHERE rowid = ?) WHERE chunk_id = ?",
                    (meta_id, chunk_id),
                )
                conn.commit()
                stored += 1
            except Exception:
                conn.rollback()

        conn.close()
        return stored

    def search(self, query: str, k: int = 12) -> List[Tuple[Turno, float]]:
        """Search for similar turns to a query.
        
        Returns list of (Turno, relevance_score) where relevance_score is
        in [0, 1] (higher = more similar).
        """
        query_emb = self._embed(query)

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()

        # sqlite-vec approximate nearest neighbor search
        c.execute("""
            SELECT rowid, distance
            FROM chunks
            WHERE chunks.embedding MATCH ?
              AND rowid IN (SELECT rowid_ref FROM meta WHERE rowid_ref != -1)
            OPTIONS '{"num_candidates": 1000}'
            LIMIT ?
        """, (json.dumps(query_emb), k))

        results = []
        for vec_rowid, distance in c.fetchall():
            c.execute("""
                SELECT turn_id, chunk_idx, chunk_text, branch, model, timestamp, success_score, tags
                FROM meta WHERE rowid_ref = ?
            """, (vec_rowid,))
            row = c.fetchone()
            if row:
                turn_id, idx, text, branch, model, ts, score, tags = row
                relevance = 1.0 - distance if distance < 1.0 else 0.0
                if not any(r[0].id == turn_id for r in results):
                    turno = Turno(
                        id=turn_id, branch=branch, prompt=text[:200],
                        response="", timestamp=ts, success_score=score,
                        tags=eval(tags) if isinstance(tags, str) else tags,
                        model=model,
                    )
                    results.append((turno, relevance))

        conn.close()
        return results

    def count(self) -> int:
        """Return the number of unique turns stored."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        c.execute("SELECT COUNT(DISTINCT turn_id) FROM meta")
        count = c.fetchone()[0]
        conn.close()
        return count

    def clear(self) -> None:
        """Drop all data (for testing)."""
        import os
        # Remove the file rather than DROP — vec0 tables can be tricky to purge live
        if self.db_path.exists():
            self.db_path.unlink()
        self._init_db()
