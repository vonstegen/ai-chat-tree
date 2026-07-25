"""Extended Vector Store with hybrid search, metadata filters, and token budgeting.

Extends the base sqlite-vec store with:
- Hybrid search (vector + keyword/BM25-like)
- Metadata filters (branch, model, success threshold, tag)
- Token-aware scoring
- Batch operations
- Scoped retrieval (ancestors + vector + weighted scoring)
"""
from __future__ import annotations

import sqlite3
import hashlib
import json
import math
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any

import subprocess

from .model import Turno
from .smart_chunking import ChunkResult, chunk_turno


class ExtendedVectorStore:
    """sqlite-vec extended vector store with hybrid search and metadata filtering."""

    def __init__(self, db_path: str = "vector_store_extended.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Initialize extended schema with metadata index."""
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
        # Extended metadata table with keyword index
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
                tags       TEXT,
                fruit_types TEXT
            )
        """)
        c.execute("CREATE INDEX IF NOT EXISTS idx_turns ON meta (turn_id)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_meta_branch ON meta (branch)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_meta_model ON meta (model)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_meta_success ON meta (success_score)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_meta_timestamp ON meta (timestamp)")
        conn.commit()
        conn.close()

    # ─── Embedding ────

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

    # ─── Ingestion ────

    def ingest_chunks(self, chunks: List[ChunkResult]) -> int:
        """Ingest multiple chunks in a single transaction."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        stored = 0

        for chunk in chunks:
            try:
                c.execute("SELECT rowid_ref FROM meta WHERE chunk_id = ?", (chunk.id,))
                rowid_ref = c.fetchone()

                if rowid_ref is not None:
                    old_id = rowid_ref[0]
                    c.execute("DELETE FROM meta WHERE chunk_id = ?", (chunk.id,))
                    c.execute("DELETE FROM chunks WHERE rowid = ?", (old_id,))

                c.execute(
                    "INSERT INTO meta (chunk_id, rowid_ref) VALUES (?, -1)",
                    (chunk.id,),
                )
                meta_id = c.lastrowid
                c.execute(
                    "INSERT INTO chunks (rowid, embedding) VALUES (?, ?)",
                    (meta_id, json.dumps(self._embed(chunk.text))),
                )
                c.execute(
                    "UPDATE meta SET rowid_ref = (SELECT rowid FROM chunks WHERE rowid = ?) WHERE chunk_id = ?",
                    (meta_id, chunk.id),
                )
                conn.commit()
                stored += 1
            except Exception:
                conn.rollback()

        conn.close()
        return stored

    def ingest_turno(self, turno: Turno) -> int:
        """Chunk a turno and ingest all sections (re-embeds if existing)."""
        chunks = chunk_turno(
            turno_id=turno.id,
            prompt=turno.prompt,
            response=turno.response,
            tags=turno.tags,
        )
        if not chunks:
            return 0

        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        stored = 0

        for chunk in chunks:
            try:
                c.execute("SELECT rowid_ref FROM meta WHERE chunk_id = ?", (chunk.id,))
                rowid_ref = c.fetchone()

                if rowid_ref is not None:
                    old_id = rowid_ref[0]
                    c.execute("DELETE FROM meta WHERE chunk_id = ?", (chunk.id,))
                    c.execute("DELETE FROM chunks WHERE rowid = ?", (old_id,))

                c.execute(
                    "INSERT INTO meta (chunk_id, rowid_ref, turn_id, chunk_idx, chunk_text, branch, model, timestamp, success_score, tags, fruit_types) "
                    "VALUES (?, -1, ?, 0, ?, ?, ?, ?, ?, ?, ?)",
                    (chunk.id, turno.id, chunk.text, turno.branch,
                     turno.model, turno.timestamp, turno.success_score or 0.0,
                     str(turno.tags) or "[]", ""),
                )
                meta_id = c.lastrowid
                c.execute(
                    "INSERT INTO chunks (rowid, embedding) VALUES (?, ?)",
                    (meta_id, json.dumps(self._embed(chunk.text))),
                )
                c.execute(
                    "UPDATE meta SET rowid_ref = (SELECT rowid FROM chunks WHERE rowid = ?) WHERE chunk_id = ?",
                    (meta_id, chunk.id),
                )
                conn.commit()
                stored += 1
            except Exception:
                conn.rollback()

        conn.close()
        return stored

    def reembed_turno(self, turno_id: str) -> int:
        """Delete and re-ingest all chunks for a specific turno (used on revision)."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        # Find all chunks for this turno and delete them
        c.execute("SELECT c1.turn_id, c1.chunk_id FROM meta c1 LEFT JOIN meta c2 ON c1.turn_id = ? AND c1.chunk_id != c2.turn_id WHERE c1.turn_id = ? AND c1.rowid_ref != -1", (turno_id, turno_id))
        # Simpler: delete by turn_id prefix
        c.execute("SELECT chunk_id FROM meta WHERE turn_id = ? AND rowid_ref != -1", (turno_id,))
        old_chunks = [row[0] for row in c.fetchall()]
        
        for chunk_id in old_chunks:
            c.execute("SELECT rowid_ref FROM meta WHERE chunk_id = ?", (chunk_id,))
            rowid_ref = c.fetchone()
            old_id = rowid_ref[0] if rowid_ref else None
            if old_id:
                c.execute("DELETE FROM chunks WHERE rowid = ?", (old_id,))
            c.execute("DELETE FROM meta WHERE chunk_id = ?", (chunk_id,))
        conn.commit()
        conn.close()
        return len(old_chunks)

    def batch_reindex(self, turno_ids: List[str]) -> int:
        """Re-embed and re-index specific turns (or all if empty list)."""
        conn = sqlite3.connect(str(self.db_path))
        c = conn.cursor()
        reindexed = 0

        if turno_ids:
            for turn_id in turno_ids:
                c.execute(
                    "SELECT chunk_id, rowid_ref FROM meta WHERE turn_id = ? AND rowid_ref != -1",
                    (turn_id,)
                )
                existing = c.fetchall()
                for chunk_id, rowid_ref in existing:
                    old_id = rowid_ref
                    c.execute("DELETE FROM chunks WHERE rowid = ?", (old_id,))
                    c.execute("DELETE FROM meta WHERE chunk_id = ?", (chunk_id,))
                    conn.commit()
                    reindexed += 1
        else:
            conn.close()
            self.db_path.unlink(missing_ok=True)
            self._init_db()
            return 0

        conn.close()
        return reindexed

    def clear_all(self) -> None:
        """Drop all data by removing the file."""
        if self.db_path.exists():
            self.db_path.unlink()
        self._init_db()


# ─── Hybrid Search ─────────

class HybridSearch:
    """Hybrid vector + keyword search over the store.

    Combines cosine similarity scores with keyword frequency scoring
    to produce a weighted hybrid score per result.
    """

    def __init__(self, vec_store: ExtendedVectorStore):
        self.vec_store = vec_store

    def search(
        self,
        query: str,
        k: int = 12,
        alpha: float = 0.7,  # weight for vector vs keyword
        min_score: float = 0.0,
        branch: Optional[str] = None,
        model: Optional[str] = None,
        min_success: Optional[float] = None,
        tags: Optional[List[str]] = None,
        max_tokens: Optional[int] = None,
    ) -> List[Tuple[Turno, float]]:
        """Mixed vector + keyword search with filters.

        Args:
            query: Search text
            k: Number of results
            alpha: Vector weight (1-alpha = keyword weight)
            min_score: Minimum hybrid score threshold
            branch: Filter by branch name
            model: Filter by model name
            min_success: Minimum success_score filter
            tags: Required tag filter (ALL tags must match)
            max_tokens: Token budget for result set

        Returns:
            List of (Turno, relevance_score) tuples sorted by hybrid score.
        """
        conn = sqlite3.connect(str(self.vec_store.db_path))
        c = conn.cursor()

        # Vector component
        query_emb = self.vec_store._embed(query)

        # Build WHERE clause for filters
        where_parts = ["rowid_ref != -1"]
        params: list = [json.dumps(query_emb), k * 10]
        
        if branch:
            where_parts.append("branch = ?")
            params.append(branch)
        if model:
            where_parts.append("model = ?")
            params.append(model)
        if min_success is not None:
            where_parts.append("success_score >= ?")
            params.append(min_success)
        if tags:
            for tag in tags:
                where_parts.append("tags LIKE ?")
                params.append(f"%{tag}%")

        full_where = ""
        if len(where_parts) > 1:
            full_where = " AND " + (" AND ".join(where_parts[1:]))
        
        where_for_subquery = " rowid_ref != -1" + (" AND " + " AND ".join(where_parts[1:]) if len(where_parts) > 1 else "")

        c.execute("""
            SELECT rowid, distance
            FROM chunks
            WHERE chunks.embedding MATCH ?
              AND rowid IN (SELECT rowid_ref FROM meta WHERE 1=1
                            {}
                           )
            OPTIONS '{{"num_candidates": 1000}}'
            LIMIT ?
        """.format(full_where), params)

        vec_results: Dict[int, float] = {}
        for vec_rowid, distance in c.fetchall():
            relevance = max(0.0, 1.0 - distance)
            vec_results[vec_rowid] = relevance

        # Keyword component - simple TF-like scoring
        query_terms = query.lower().split()
        keyword_scores = self._keyword_search(query_terms, c, where_parts=where_parts[1:] if len(where_parts) > 1 else [])
        
        # Normalize keyword scores
        max_kw = max(keyword_scores.values()) if keyword_scores else 1.0
        if max_kw > 0:
            for rowid in keyword_scores:
                keyword_scores[rowid] = keyword_scores[rowid] / max_kw

        # Combine
        all_result_ids = set(list(vec_results.keys()) + list(keyword_scores.keys()))
        best_per_turn: Dict[str, Tuple[Turno, float]] = {}

        for rowid in all_result_ids:
            v_score = vec_results.get(rowid, 0.0)
            k_score = keyword_scores.get(rowid, 0.0)
            hybrid = alpha * v_score + (1 - alpha) * k_score
            if hybrid < min_score:
                continue

            # Fetch metadata
            c.execute("""
                SELECT turn_id, chunk_text, branch, model, timestamp, success_score
                FROM meta WHERE rowid_ref = ?
            """, (rowid,))
            row = c.fetchone()
            if row:
                turn_id, chunk_text, branch, model, ts, score = row
                turno = Turno(
                    id=turn_id, branch=branch or "",
                    prompt=chunk_text[:200],
                    timestamp=ts,
                    success_score=score or 0.0,
                    model=model or "",
                )
                if turno.id not in best_per_turn:
                    best_per_turn[turno.id] = (turno, hybrid)
                elif hybrid > best_per_turn[turno.id][1]:
                    best_per_turn[turno.id] = (turno, hybrid)

        results = sorted(best_per_turn.values(), key=lambda x: x[1], reverse=True)[:k]

        if max_tokens and self._token_count(results) > max_tokens:
            results = self._token_limit(results, max_tokens)

        conn.close()
        return results

    def _keyword_search(
        self,
        query_terms: List[str],
        c: sqlite3.Cursor,
        where_parts: List[str] = None,
    ) -> Dict[int, float]:
        """Keyword scoring for terms in chunk_text (TF-like)."""
        scores: Dict[int, float] = {}
        
        for term in query_terms:
            # Escape for SQL
            safe_term = term.replace("'", "''")
            
            base_where = "rowid_ref != -1"
            if where_parts:
                base_where += " AND " + " AND ".join(where_parts)
            
            c.execute(f"""
                SELECT rowid_ref, LENGTH(LOWER(chunk_text)) - LENGTH(REPLACE(LOWER(chunk_text), '{safe_term}', '')) AS weight
                FROM meta 
                WHERE {base_where}
                  AND LOWER(chunk_text) LIKE '%{safe_term}%'
            """)
            for rowid_ref, weight in c.fetchall():
                if weight > 0:
                    scores[rowid_ref] = scores.get(rowid_ref, 0.0) + weight / 100.0

        return scores

    def _token_count(self, results: List[Tuple[Turno, float]]) -> int:
        """Rough token count (chars / 4 for Western languages)."""
        return sum(len(r[0].prompt) + len(r[0].response) for r in results) // 4

    def _token_limit(
        self,
        results: List[Tuple[Turno, float]],
        max_tokens: int,
    ) -> List[Tuple[Turno, float]]:
        """Truncate results to fit within token budget."""
        total = 0
        kept = []
        for turno, score in results:
            chunk_tokens = max(1, len(turno.prompt) // 4)
            if total + chunk_tokens <= max_tokens:
                kept.append((turno, score))
                total += chunk_tokens
        return kept


# ─── Scoped Retrieval ───────

class ScopedRetriever:
    """Retrieves context-scoped results for LLM consumption.

    Combines:
    - Ancestral chain (walk up to MAX_DEPTH turns)
    - Top-k vector similarity
    - Weighted scoring (success_score * time_decay)

    Produces a final context string within token budget.
    """

    def __init__(
        self,
        vault_dir: str,
        store: ExtendedVectorStore,
        max_depth: int = 4,
    ):
        self.vault_dir = vault_dir
        self.store = store
        self.max_depth = max_depth

    def retrieve_scoped_context(
        self,
        query: str,
        from_turn_id: Optional[str] = None,
        ancestor_limit: int = 5,
        vector_k: int = 12,
        token_budget: int = 4096,
    ) -> str:
        """Retrieve scoped context for an LLM query.

        Strategy:
        1. Gather ancestors of from_turn_id with their best turns
        2. Run hybrid similarity search for the query (with branch filtering)
        3. Score + rank: hybrid of (ancestry_weight, vector_score, success_weight, time_decay)
        4. Assemble context string within token budget

        Returns context string ready for LLM injection.
        """
        conn = sqlite3.connect(str(self.store.db_path))
        c = conn.cursor()

        # 1. Gather ancestors and their best turns
        ancestors: Dict[str, List[Tuple[Turno, float]]] = {}
        if from_turn_id:
            ancestors = self._gather_ancestors(from_turn_id, ancestor_limit)

        # 2. Find branch context for the query turn
        best_branch = self._find_branch(from_turn_id, c=c)
        
        # 3. Vector search with branch context
        hybrid = HybridSearch(self.store)
        vector_results = hybrid.search(
            query=query,
            k=vector_k,
            alpha=0.7,
            branch=best_branch,
            min_success=0.3,
        )

        # 4. Score all results
        scored: Dict[str, Tuple[Turno, float]] = {}

        for turno, vec_score in vector_results:
            key = turno.id
            success_w = turno.success_score if turno.success_score else 0.0
            ancestry_bonus = self._ancestry_bonus(key, ancestors)
            time_decay = self._time_decay_turno(turno)
            
            # Composite score
            hybrid_score = 0.4 * vec_score + 0.3 * success_w + 0.2 * ancestry_bonus + 0.1 * time_decay
            scored[key] = (turno, hybrid_score)

        # 5. Sort and enforce token budget
        ranked = sorted(scored.values(), key=lambda x: x[1], reverse=True)
        return self._assemble_context(ranked, token_budget)

    def _gather_ancestors(
        self, start_id: str, limit: int
    ) -> Dict[str, List[Tuple[Turno, float]]]:
        """Walk ancestry chain and collect up to limit turns per ancestor."""
        ancestor_turns: Dict[str, List[Tuple[Turno, float]]] = {}
        visited = set()
        current = start_id
        depth = 0

        while depth < limit and current not in visited:
            visited.add(current)
            turno = self._find_turno_by_id(current)
            if turno:
                ancestor_turns[current] = [(turno, 1.0)]
            # Find parent
            if turno and turno.parent_turn:
                current = turno.parent_turn
            elif turno:
                # Walk back via meta table
                conn = sqlite3.connect(str(self.store.db_path))
                cc = conn.cursor()
                cc.execute("SELECT turn_id FROM meta WHERE rowid_ref != -1 LIMIT 1")
                row = cc.fetchone()
                conn.close()
                current = row[0] if row else None
            else:
                break
            depth += 1

        return ancestor_turns

    def _find_turno_by_id(self, turn_id: str) -> Optional[Turno]:
        """Find a turno by its ID in the vault."""
        # In practice this queries vault_manager; simplified here
        return Turno(id=turn_id, branch="") if turn_id else None

    def _find_branch(self, start_id: Optional[str], c: sqlite3.Cursor) -> Optional[str]:
        """Find the branch containing start_id."""
        if not start_id:
            return None
        c.execute("SELECT branch FROM meta WHERE rowid_ref != -1 AND turn_id = ? LIMIT 1", (start_id,))
        row = c.fetchone()
        return row[0] if row else None

    def _ancestry_bonus(self, turn_id: str, ancestors: Dict) -> float:
        if turn_id in ancestors:
            return 1.0
        return 0.0

    def _time_decay_turno(self, turno: Turno) -> float:
        """Time decay factor (newer = higher score, capped)."""
        try:
            ts = turno.timestamp[:19] if turno.timestamp else ""
            from datetime import datetime, timezone
            t_created = datetime.fromisoformat(ts)
            t_now = datetime.now(timezone.utc)
            days_old = (t_now - t_created).days
            decay = math.exp(-0.01 * min(days_old, 365))
            return max(0.0, min(1.0, decay))
        except Exception:
            return 0.5

    def _assemble_context(
        self,
        ranked: List[Tuple[Turno, float]],
        token_budget: int,
    ) -> str:
        """Assemble context string from ranked results."""
        parts: List[str] = []
        total_tokens = 0

        for turno, score in ranked:
            chunk_tokens = len(turno.prompt) // 4
            if total_tokens + chunk_tokens > token_budget:
                break
            parts.append(
                f"## Branch {turno.branch} | Turn {turno.id} | Score {score:.3f}\n"
                f"{turno.prompt[:1500]}\n\n"
            )
            total_tokens += chunk_tokens

        return "\n\n".join(parts)


# ─── Module-level convenience ────────

def create_extended_store(db_path: str = "vector_store_extended.db") -> ExtendedVectorStore:
    """Factory for extended vector store."""
    return ExtendedVectorStore(db_path)


def create_hybrid_search(store: ExtendedVectorStore) -> HybridSearch:
    """Factory for hybrid search layer."""
    return HybridSearch(store)


def create_scoped_retriever(vault_dir: str, store: ExtendedVectorStore, max_depth: int = 4) -> ScopedRetriever:
    """Factory for scoped retrieval layer."""
    return ScopedRetriever(vault_dir, store, max_depth)
