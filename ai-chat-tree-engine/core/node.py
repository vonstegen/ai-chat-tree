from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict
import hashlib
import json


@dataclass
class TurnNode:
    """Immutable conversation node with Logician enforcement."""
    
    id: str                      # Turn-001, Turn-002, etc.
    model: str
    type: str = "turn"
    timestamp: str = ""
    branch: str = "trunk"
    parent_turn: Optional[str] = None
    success_score: float = 0.0
    tags: List[str] = None
    vector_id: Optional[str] = None
    revision_of: Optional[str] = None
    logician_hash: Optional[str] = None
    fruits: List[Dict] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.fruits is None:
            self.fruits = []
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()
    
    def compute_hash(self) -> str:
        """Create deterministic hash for Logician verification."""
        data = asdict(self)
        # Remove mutable/runtime fields for hash
        clean = {k: v for k, v in data.items() if k not in ['logician_hash', 'vector_id']}
        return hashlib.sha256(
            json.dumps(clean, sort_keys=True).encode()
        ).hexdigest()[:16]
    
    def to_markdown(self) -> str:
        """Convert to Obsidian markdown with frontmatter."""
        frontmatter = f"""---
type: {self.type}
id: {self.id}
timestamp: {self.timestamp}
branch: {self.branch}
parent_turn: {self.parent_turn or 'null'}
model: {self.model}
success_score: {self.success_score}
tags: {json.dumps(self.tags)}
vector_id: {self.vector_id or 'null'}
revision_of: {self.revision_of or 'null'}
logician_hash: {self.logician_hash or 'pending'}
---

# Turn {self.id.replace('Turn-', '')} — {self.branch}

"""
        return frontmatter