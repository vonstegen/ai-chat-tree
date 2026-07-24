"""Core data model: Trunko, Brancho, Turno, Fruito, and Node.

Each entity maps to one Markdown file with YAML frontmatter inside the Obsidian vault.
All mutations go through VaultManager which handles atomic writes.
"""
from __future__ import annotations

import os
import re
import json
import secrets
from dataclasses import dataclass, asdict, field as dataclass_field
from datetime import datetime, timezone
from typing import Optional, Dict, List, Sequence
from pathlib import Path


# ─── Helper: unique ID generator ──────────────────────────

def new_id(prefix: str = "node") -> str:
    """Generate a unique ID. Format: prefix-YYYYMMDD-HHMMSS-XXXX"""
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y%m%d-%H%M%S")
    suffix = secrets.token_hex(2).upper()
    return f"{prefix}-{ts}-{suffix}"


# ─── Node base class ──────────────────────────────────────

class Node:
    """Immutable node base abstract class."""
    @property
    def node_type(self) -> str:
        raise NotImplementedError

    @property
    def node_id(self) -> str:
        raise NotImplementedError

    def to_markdown(self) -> str:
        raise NotImplementedError

    @classmethod
    def from_markdown(cls, content: str) -> "Node":
        raise NotImplementedError

    def to_dict(self) -> dict:
        """Serialize node to dictionary (for HTTP/API responses)."""
        raise NotImplementedError


# ─── Turno ────────────────────────────────────────────────

@dataclass
class Turno(Node):
    """A single T/A turn inside a branch."""
    id: str
    branch: str
    model: str = "default"
    prompt: str = ""
    response: str = ""
    timestamp: str = ""
    success_score: float = 0.0
    tags: List[str] = dataclass_field(default_factory=list)
    vector_id: Optional[str] = None
    revision_of: Optional[str] = None
    revision_number: int = 0
    change_reason: Optional[str] = None
    source: str = "manual"

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.tags:
            self.tags = []

    @property
    def node_type(self) -> str:
        return "turno"

    @property
    def node_id(self) -> str:
        return self.id

    def to_dict(self) -> dict:
        d = asdict(self)
        # Convert dataclass fields that shouldn't leak
        return d

    def to_markdown(self) -> str:
        fm_tags = ", ".join(self.tags)
        fm = f"""---
type: turno
id: {self.id}
branch: {self.branch}
model: {self.model}
timestamp: "{self.timestamp}"
success_score: {self.success_score}
tags: [{fm_tags}]
vector_id: {self.vector_id or "null"}
revision_of: {self.revision_of or "null"}
revision_number: {self.revision_number}
change_reason: {self.change_reason or "null"}
source: {self.source}
---

# Turno {self.id}

**Model:** {self.model}
**Time:** {self.timestamp}

## Prompt
{self.prompt}

## Response
{self.response or "_empty_"}

"""
        return fm

    @classmethod
    def from_markdown(cls, content: str) -> Turno:
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
        if not m:
            raise ValueError("No frontmatter in turno file")
        fm: str = m.group(1)
        body: str = m.group(2)

        def _get(key: str, default=None, is_list: bool = False):
            for line in fm.splitlines():
                k, rest = line.lower(), line
                if rest.lower().startswith(key + ": "):
                    val = rest.split(": ", 1)[1].strip()
                    if val == "null":
                        return default
                    if is_list:
                        return [x.strip().strip("'\"") for x in val[1:-1].split(",")]
                    if val.lower() == "true":
                        return True
                    if val.lower() == "false":
                        return False
                    try:
                        return int(val)
                    except ValueError:
                        try:
                            return float(val)
                        except ValueError:
                            return val
            return default

        return cls(
            id=_get("id", ""),
            branch=_get("branch", ""),
            model=_get("model", "default"),
            prompt=_get("prompt", ""),
            response=_get("response", ""),
            timestamp=_get("timestamp", ""),
            success_score=_get("success_score", 0.0),
            tags=_get("tags", [], is_list=True),
            vector_id=_get("vector_id"),
            revision_of=_get("revision_of"),
            revision_number=_get("revision_number", 0),
            change_reason=_get("change_reason"),
            source=_get("source", "manual"),
        )

    @classmethod
    def from_data(cls, data: Dict) -> Turno:
        return cls(**data)


# ─── Brancho ──────────────────────────────────────────────

@dataclass
class Brancho(Node):
    """A split from a trunk."""
    id: str
    name: str
    parent_turn: str = "trunk-001"
    created: str = ""
    model: str = "default"
    description: str = ""
    active: bool = True

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now(timezone.utc).isoformat()

    @property
    def node_type(self) -> str:
        return "brancho"

    @property
    def node_id(self) -> str:
        return self.id

    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self) -> str:
        fm = f"""---
type: brancho
id: {self.id}
name: {self.name}
parent_turn: {self.parent_turn}
created: "{self.created}"
model: {self.model}
description: {self.description}
active: {self.active}
---

# Branch {self.name} ({self.id})
**Model:** {self.model}
**Created:** {self.created}

> _{self.description or "_no description_"}_

"""
        return fm

    @classmethod
    def from_markdown(cls, content: str) -> Brancho:
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
        if not m:
            raise ValueError("No frontmatter in brancho file")
        fm: str = m.group(1)

        def _get(key: str, default=None):
            for line in fm.splitlines():
                rest = line
                if rest.lower().startswith(key + ": "):
                    val = rest.split(": ", 1)[1].strip()
                    if val == "null":
                        return default
                    if val.lower() == "true":
                        return True
                    if val.lower() == "false":
                        return False
                    return val
            return default

        return cls(
            id=_get("id", ""),
            name=_get("name", ""),
            parent_turn=_get("parent_turn", "trunk-001"),
            created=_get("created", ""),
            model=_get("model", "default"),
            description=_get("description", ""),
            active=_get("active", True),
        )

    @classmethod
    def from_data(cls, data: Dict) -> Brancho:
        return cls(**data)


# ─── Fruito ───────────────────────────────────────────────

_fruito_types = ["script", "diff", "terminal", "diagram", "image", "text", "code"]

@dataclass
class Fruito(Node):
    """A fruit attached to a turn."""
    id: str
    turno_id: str
    branch: str
    content: str = ""
    file_path: Optional[str] = None
    fruit_type: str = "text"
    created: str = ""
    notes: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now(timezone.utc).isoformat()

    @property
    def node_type(self) -> str:
        return "fruits"

    @property
    def node_id(self) -> str:
        return self.id

    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self) -> str:
        fm = f"""---
type: fruits
id: {self.id}
turno_id: {self.turno_id}
branch: {self.branch}
fruit_type: {self.fruit_type}
created: "{self.created}"
file_path: {self.file_path or "null"}
---

# Fruito {self.id}

## Content
```
{self.content[:500]}
```

"""
        if self.notes:
            fm += f"## Notes\n{self.notes}"
        return fm

    @classmethod
    def from_markdown(cls, content: str) -> Fruito:
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
        if not m:
            raise ValueError("No frontmatter in fruits file")
        fm: str = m.group(1)

        def _get(key: str, default=None):
            for line in fm.splitlines():
                rest = line
                if rest.lower().startswith(key + ": "):
                    val = rest.split(": ", 1)[1].strip()
                    if val == "null":
                        return default
                    return val
            return default

        return cls(
            id=_get("id", ""),
            turno_id=_get("turno_id", ""),
            branch=_get("branch", ""),
            content=_get("content", ""),
            file_path=_get("file_path"),
            fruit_type=_get("fruit_type", "text"),
            created=_get("created", ""),
            notes=_get("notes", ""),
        )

    @classmethod
    def from_data(cls, data: Dict) -> Fruito:
        return cls(**data)


# ─── Trunko ───────────────────────────────────────────────

@dataclass
class Trunko:
    """A trunk — the root of a branch hierarchy."""
    id: str
    name: str
    created: str = ""
    description: str = ""
    turno_template: str = ""

    def __post_init__(self):
        if not self.created:
            self.created = datetime.now(timezone.utc).isoformat()

    @property
    def node_type(self) -> str:
        return "trunoo"

    @property
    def node_id(self) -> str:
        return self.id

    def to_dict(self) -> dict:
        return asdict(self)

    def to_markdown(self) -> str:
        fm = f"""---
type: trunoo
id: {self.id}
name: {self.name}
created: "{self.created}"
description: {self.description}
---

# Trunko {self.name} ({self.id})

> _{self.description or "_no description_"}_

"""
        if self.turno_template:
            fm += f"## Turno Template\n\n{self.turno_template}"
        return fm

    @classmethod
    def from_markdown(cls, content: str) -> Trunko:
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", content, re.DOTALL)
        if not m:
            raise ValueError("No frontmatter in trunoo file")
        fm: str = m.group(1)

        def _get(key: str, default=None):
            for line in fm.splitlines():
                rest = line
                if rest.lower().startswith(key + ": "):
                    val = rest.split(": ", 1)[1].strip()
                    if val == "null":
                        return default
                    return val
            return default

        return cls(
            id=_get("id", ""),
            name=_get("name", ""),
            created=_get("created", ""),
            description=_get("description", ""),
            turno_template=_get("turno_template", ""),
        )

    @classmethod
    def from_data(cls, data: Dict) -> Trunko:
        return cls(**data)
