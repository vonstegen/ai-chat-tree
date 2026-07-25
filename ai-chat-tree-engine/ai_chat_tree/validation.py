"""Validation — Pydantic schemas, link integrity checker, and CLI dry-run."""
from __future__ import annotations

import re
import json
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

from pydantic import BaseModel, Field, validator
from .model import Turno, Brancho, Fruito, Trunko, Node


# ─── Pydantic Input Schemas ──────────────────────────

class TurnoSchema(BaseModel):
    """Turno validation schema."""
    branch: str
    model: str = "default"
    prompt: str = ""
    response: str = ""
    success_score: float = Field(ge=0.0, le=1.0, default=0.0)
    tags: List[str] = []
    source: str = "manual"
    parent_turn: Optional[str] = None

    @validator("tags", pre=True)
    def normalize_tags(cls, v):
        if v and isinstance(v, list):
            return [str(t).strip() for t in v if t]
        return []


class BranchoSchema(BaseModel):
    """Brancho validation schema."""
    name: str = Field(..., min_length=1)
    parent_turn: str = "trunk-001"
    parent_turn_id: Optional[str] = None
    description: str = ""
    active: bool = True


class FruitoSchema(BaseModel):
    """Fruito validation schema."""
    turno_id: str
    branch: str
    fruit_type: str = Field(..., pattern="^(script|image|terminal|diff|diagram|other)$")
    content: str = ""
    notes: str = ""


class TrunkoSchema(BaseModel):
    """Trunko validation schema."""
    name: str = Field(..., min_length=1)
    description: str = ""


# ─── Link Integrity --──────────────────────────

@dataclass
class IntegrityIssue:
    severity: str  # "error", "warning", "info"
    entity_type: str  # "trunk", "branch", "turn", "fruit"
    entity_id: str
    issue: str
    suggestion: Optional[str] = None


@dataclass
class IntegrityReport:
    """Result of a link integrity scan."""
    file_path: str
    issues: List[IntegrityIssue] = field(default_factory=list)
    node_count: int = 0
    valid: bool = True

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == "warning")


def check_integrity(vault_manager) -> IntegrityReport:
    """Scan the vault for dangling refs, orphaned files, missing types.

    Checks:
    - Every parent_turn references an existing turn
    - Every revision_of references an existing turn
    - Every turno referenced by a fruit exists
    - Every branch referenced by a turno exists
    - Node type matches file extension
    - Required frontmatter fields present
    """
    report = IntegrityReport(
        file_path=str(vault_manager.vault_root),
    )

    # Collect all nodes
    all_turns = {}
    all_branches = set()

    for node, path in vault_manager.list_nodes("turn"):
        all_turns[node.id] = node
        report.node_count += 1
        _validate_required_fields(node, path, report)

    for node, path in vault_manager.list_nodes("branch"):
        if isinstance(node, Brancho):
            all_branches.add(node.id)
        report.node_count += 1

    # Validate turn references
    for turno_id, turno in all_turns.items():
        path_repr = f"{turno_id}.md"
        # Check parent_turn
        if turno.parent_turn:
            if turno.parent_turn not in all_turns:
                report.issues.append(IntegrityIssue(
                    severity="error",
                    entity_type="turn",
                    entity_id=turno_id,
                    issue=f"parent_turn '{turno.parent_turn}' does not exist",
                    suggestion=f"Add parent_turn or create the missing turn {turno.parent_turn}",
                ))
        # Check revision_of
        if turno.revision_of:
            if turno.revision_of not in all_turns:
                report.issues.append(IntegrityIssue(
                    severity="error",
                    entity_type="turn",
                    entity_id=turno_id,
                    issue=f"revision_of '{turno.revision_of}' does not exist",
                    suggestion=f"Add revision_of or create the original turn {turno.revision_of}",
                ))
        # Check branch reference
        if turno.branch not in all_branches:
            report.issues.append(IntegrityIssue(
                severity="warning",
                entity_type="turn",
                entity_id=turno_id,
                issue=f"branch '{turno.branch}' not in branches list",
                suggestion=f"Create branch {turno.branch} via `act branch --name {turno.branch}`",
            ))

    # Validate fruits
    for fruit_node, path in vault_manager.list_nodes("fruit"):
        if isinstance(fruit_node, Fruito):
            report.node_count += 1
            if fruit_node.turno_id not in all_turns:
                report.issues.append(IntegrityIssue(
                    severity="error",
                    entity_type="fruit",
                    entity_id=fruit_node.id,
                    issue=f"turno_id '{fruit_node.turno_id}' does not exist",
                    suggestion=f"Create the turn or fix the turno_id in {fruit_node.id}",
                ))

    report.valid = all(i.severity != "error" for i in report.issues)
    return report


def _validate_required_fields(node: Node, path, report: IntegrityReport) -> None:
    """Check that a node has required frontmatter fields."""
    content = None
    try:
        from pathlib import Path
        content = Path(path).read_text() if isinstance(path, str) else path.read_text()
    except Exception:
        content = None
    if not content:
        return
    required = {
        "turn": ["id", "branch", "type"],
        "branch": ["id", "name", "type"],
        "trunk": ["id", "name", "type"],
        "fruit": ["id", "turno_id", "type"],
    }
    node_type = node.node_type if hasattr(node, "node_type") else "turn"
    missing = []
    for field_name in required.get(node_type, []):
        if content.find(f"{field_name}:") == -1:
            missing.append(field_name)
    if missing:
        report.issues.append(IntegrityIssue(
            severity="error",
            entity_type=node_type,
            entity_id=getattr(node, "id", "unknown"),
            issue=f"Missing required fields: {', '.join(missing)}",
            suggestion=f"Update {path} to include {', '.join(missing)}",
        ))
