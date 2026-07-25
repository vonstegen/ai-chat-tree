"""Smart chunking for vector store ingestion.

Chunks by document structure (headings, code blocks, paragraphs) rather
than raw byte/char offsets. Each chunk is 500–1000 tokens (roughly 2000-4000
characters), preserving semantic boundaries.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple, Optional


@dataclass
class ChunkResult:
    """A single semantic chunk."""
    id: str          # e.g. "turno-123-prompt-0"
    text: str        # chunk content
    start_token: int = 0
    end_token: int = 0
    source_field: str = ""  # "prompt" or "response"


MAX_CHUNK_CHARS = 3500  # ~1000 tokens rough estimate
MIN_CHUNK_CHARS = 150   # skip tiny fragments


def smart_chunk_text(
    field_name: str,
    text: str,
    turn_id: str,
    chunk_idx: int = 0,
) -> List[ChunkResult]:
    """Smart-chunk a text field by document structure.

    Strategy:
    1. Split by headings (Markdown level-1/2 headings)
    2. For sections that are too long, further split by code blocks then by paragraphs
    3. For sections < MIN_CHUNK_CHARS, merge with previous chunk
    4. Each output chunk is in [MIN_CHUNK_CHARS, MAX_CHUNK_CHARS]
    """
    if not text or not text.strip():
        return []

    # Split by markdown headings
    sections = _split_by_headings(text)

    chunks: List[ChunkResult] = []
    current: str = ""

    for section in sections:
        section = section.strip()
        if not section:
            continue

        if len(section) + len(current) < MIN_CHUNK_CHARS:
            current += "\n\n" + section
            continue

        if len(section) + len(current) <= MAX_CHUNK_CHARS:
            current += "\n\n" + section if current else section
        else:
            # Flush current accumulator
            if current.strip():
                chunks.append(_make_chunk(current.strip(), field_name, turn_id, chunk_idx))
                chunk_idx += 1
            current = section

        # If a single section exceeds MAX, do code-block-aware split
        if len(current) > MAX_CHUNK_CHARS:
            current = _split_long_text(current, field_name, turn_id, chunk_idx)
            if isinstance(current, list):
                chunks.extend(current)
                return chunks

    if current.strip():
        chunks.append(_make_chunk(current.strip(), field_name, turn_id, chunk_idx))

    return chunks if chunks else [_force_chunk(text.strip(), field_name, turn_id, chunk_idx)]


def _split_by_headings(text: str) -> List[str]:
    """Split Markdown text by level-1 or level-2 headings."""
    pattern = re.compile(r'^(#{1,2}\s+.+)$', re.MULTILINE)
    parts = pattern.split(text)
    # parts = [before_heading1, heading1, body1, heading2, body2, ...]
    result = []
    for i in range(0, len(parts), 2):
        header = parts[i] if i < len(parts) else ""
        body = parts[i + 1] if i + 1 < len(parts) else ""
        combined = f"{header}\n{body}".strip() if header and body else (header.strip() if header else body.strip())
        if combined:
            result.append(combined)
    return result if result else [text]


def _split_long_text(text: str, field_name: str, turn_id: str, chunk_idx: int) -> List[ChunkResult]:
    """Split text > MAX_CHUNK_CHARS by code blocks, then by paragraph breaks."""
    # Split by code blocks first
    code_pattern = re.compile(r'(```[\s\S]*?```)', re.DOTALL)
    parts = code_pattern.split(text)

    chunks: List[ChunkResult] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if "```" in part:
            # It's a code block — keep together
            chunks.append(_make_chunk(part, field_name, turn_id, chunk_idx))
            chunk_idx += 1
        elif len(part) > MAX_CHUNK_CHARS:
            # Split by paragraph breaks
            paras = re.split(r'\n{2,}', part)
            accumulator = ""
            for para in paras:
                para = para.strip()
                if not para:
                    continue
                if len(accumulator) + len(para) <= MAX_CHUNK_CHARS:
                    accumulator += "\n\n" + para if accumulator else para
                else:
                    chunks.append(_make_chunk(accumulator, field_name, turn_id, chunk_idx))
                    accumulator = para
                    chunk_idx += 1
            if accumulator:
                chunks.append(_make_chunk(accumulator, field_name, turn_id, chunk_idx))
        else:
            chunks.append(_make_chunk(part, field_name, turn_id, chunk_idx))

    return chunks


def _make_chunk(text: str, field_name: str, turn_id: str, chunk_idx: int) -> ChunkResult:
    """Create a normalized chunk result."""
    idx_str = f"chunk-{chunk_idx}"
    return ChunkResult(
        id=f"{turn_id}-{field_name}-{idx_str}",
        text=text,
        source_field=field_name,
    )


def _force_chunk(text: str, field_name: str, turn_id: str, chunk_idx: int) -> ChunkResult:
    """Fallback: chunk even if below minimum."""
    return _make_chunk(text, field_name, turn_id, chunk_idx)


# ─── Bulk chunking helper ──────────

def chunk_turno(
    turno_id: str,
    prompt: str = "",
    response: str = "",
    tags: Optional[List[str]] = None,
) -> List[ChunkResult]:
    """Chunk all fields of a turn for vector ingestion.

    Returns list of ChunkResult objects, one per semantic section.
    """
    results: List[ChunkResult] = []
    chunk_idx = 0

    if prompt:
        results.extend(smart_chunk_text("prompt", prompt, turno_id, chunk_idx))
        chunk_idx = 1

    if response:
        results.extend(smart_chunk_text("response", response, turno_id, chunk_idx))

    return results
