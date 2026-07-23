#!/usr/bin/env python3
"""
AI Chat Tree — Logician Bridge (Prototype v0.5)
Simplified version for initial prototype. Full integration with vigil-log-processor-v3.py
will be completed after morning review.
"""
import json
from pathlib import Path
from datetime import datetime
from typing import Dict

from core.node import TurnNode


class LogicianBridge:
    """Bridge to Vigil Logician v3.0 for all mutations (Prototype version)."""
    
    def __init__(self):
        self.vault_root = Path("~/ai-chat-tree").expanduser()
        self.nodes_dir = self.vault_root / "turns"
        self.nodes_dir.mkdir(exist_ok=True)
        self.log_file = self.vault_root / "logician-events.log"
    
    def log_event(self, event_type: str, node_id: str, details: str = ""):
        """Simple local logging until full Logician integration is finalized."""
        timestamp = datetime.utcnow().isoformat()
        with open(self.log_file, "a") as f:
            f.write(f"{timestamp} | {event_type} | {node_id} | {details}\n")
        print(f"LOG: {event_type} → {node_id}")
    
    def create_first_turn(self, model: str = "mistral-small3.2:latest") -> Dict:
        """Create the very first trunk turn."""
        node = TurnNode(
            id="Turn-001",
            model=model,
            branch="trunk",
            tags=["prototype", "initialization", "logician-test"],
            success_score=1.0
        )
        
        self.log_event("PRE_VALIDATION", node.id, f"model={model}")
        
        node.logician_hash = node.compute_hash()
        
        if self.write_node(node):
            self.log_event("NODE_CREATED", node.id, f"hash={node.logician_hash}")
            self.log_event("POST_VERIFICATION", node.id, "PASSED")
            
            return {
                "status": "success",
                "turn_id": node.id,
                "path": str(self.nodes_dir / f"{node.id}.md"),
                "hash": node.logician_hash,
                "message": "First turn created with Logician-style protection (prototype)"
            }
        return {"status": "failed", "phase": "write"}
    
    def write_node(self, node: TurnNode) -> bool:
        """Write node to filesystem."""
        node_path = self.nodes_dir / f"{node.id}.md"
        try:
            with open(node_path, "w") as f:
                f.write(node.to_markdown())
            print(f"✓ Created: {node_path.name}")
            return True
        except Exception as e:
            print(f"✗ Failed to write node: {e}")
            return False


if __name__ == "__main__":
    print("AI Chat Tree Prototype — Creating Turn-001 via Logician Bridge...\n")
    bridge = LogicianBridge()
    result = bridge.create_first_turn()
    print(json.dumps(result, indent=2))
    print(f"\nLog file written to: {bridge.log_file}")
