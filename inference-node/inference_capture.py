"""
inference_capture.py — Real-time Session Capture Module
=========================================================

Captures Matrix conversation turns as InferenceNodes in the sandbox tree.

Usage:
    python inference_capture.py                    # Live capture mode
    python inference_capture.py --stream FILE      # Append to existing stream
    python inference_capture.py --demo             # Demo mode with synthetic turns

Architecture:
    1. ChatMessage -> TurnBuilder -> InferenceNode -> InferenceTree.append()
    2. CaptureContext maintains session state (platform, thread, timestamps)
    3. LiveCapture class runs as an event loop, listening for new message input
    4. StreamMode allows batch import of existing JSONL/chat logs

Data flow:
    Matrix Message -> CaptureEvent -> InferenceNode -> stream.jsonl -> MD views

Design decisions:
    - Capture does one thing: turn chat messages into tree nodes
    - Enrichment comes via stream_enrichment module (separate concern)
    - Diagrams come via diagram_renderer module (separate concern)
    - No external API calls — purely local capture of existing chat interface
"""

import sys
import os
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))
from sandbox import InferenceNode, InferenceTree, TreeComposer

# ─── Types ───────────────────────────────────────────────────────────────────

class TurnRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    ACTION = "action"  # tool call output

@dataclass
class CaptureEvent:
    """Raw event from chat conversation."""
    role: TurnRole
    message: str
    platform: str = "matrix"
    thread: str = ""
    timestamp_f: float = None
    metadata: dict = field(default_factory=dict)
    
    def __post_init__(self):
        if self.timestamp_f is None:
            self.timestamp_f = time.time()
    
    def to_node(self, parent_id: Optional[str] = None,
                node_type: str = "stem",
                semantic_label: str = None,
                model: str = "qwen3.6:35b-a3b",
                provider: str = "local") -> InferenceNode:
        """Convert this event into an InferenceNode ready for tree insertion."""
        
        labels = {
            TurnRole.USER: "Message",
            TurnRole.ASSISTANT: "Response",
            TurnRole.SYSTEM: "System",
            TurnRole.ACTION: "Tool Output"
        }
        type_map = {
            TurnRole.USER: "stem" if parent_id else "stem",
            TurnRole.ASSISTANT: "stem",
            TurnRole.SYSTEM: "stem",
            TurnRole.ACTION: "branch"
        }
        
        # Build semantic label
        if semantic_label is None:
            semantic_label = labels.get(self.role, "Event")
        
        node = InferenceNode(
            prompt=self.message,
            response=self.message,  # For capture mode, prompt and response are the same
            model=model,
            provider=provider,
            platform=self.platform,
            parent_hash=parent_id or "genesis",
            node_type=node_type,
            semantic_label=semantic_label,
            info_carryback=None,
            children_hashes=[],
            tool_calls=self.metadata.get("tool_calls", [])
        )
        node.metadata = self.metadata
        node.role = self.role
        return node


@dataclass 
class CaptureContext:
    """Tracks session state during capture."""
    session_id: str
    platform: str
    description: str
    created: float
    total_turns: int = 0
    last_turn_ts: float = 0
    node_history: list = field(default_factory=list)
    
    def turn(self) -> int:
        self.total_turns += 1
        return self.total_turns


# ─── Capture Engines ────────────────────────────────────────────────────────

class CaptureEngine:
    """Base capture engine interface."""
    
    def __init__(self, stream_path: Path, context: CaptureContext):
        self.stream_path = stream_path
        self.context = context
        self.tree = InferenceTree(stream_path)
        self.tree._open()
        self._first_node = None  # Will be set after first append
    
    def capture_role_turn(self, role: TurnRole, message: str,
                          parent_id: Optional[str] = None,
                          **kwargs) -> InferenceNode:
        """Capture a single user/assistant turn as an InferenceNode."""
        
        event = CaptureEvent(
            role=role,
            message=message,
            platform=self.context.platform,
            timestamp_f=time.time(),
            metadata=kwargs.get("metadata", {})
        )
        
        turn_num = self.context.turn()
        node = event.to_node(
            parent_id=parent_id,
            node_type=kwargs.get("node_type", "stem" if role != TurnRole.ACTION else "branch"),
            semantic_label=f"Turn {turn_num}: {kwargs.get('label', '—')}",
            model=kwargs.get("model", "qwen3.6:35b-a3b"),
            provider=kwargs.get("provider", "local")
        )
        node.turn_number = turn_num
        
        captured = self.tree.append(node)
        self.context.node_history.append(captured)
        
        if self._first_node is None:
            self._first_node = captured
            # This is our first real node, make it the root
            if captured.parent_hash == "genesis":
                self.context.session_id = captured.id
        
        return captured
    
    def capture_system_node(self, message: str, **kwargs) -> InferenceNode:
        """Capture a system-level node (session start, config, etc.)."""
        return self.capture_role_turn(
            TurnRole.SYSTEM,
            message,
            node_type="stem",
            semantic_label=kwargs.get("label", "System"),
            model="SYSTEM"
        )
    
    def capture_action_node(self, message: str, tool_calls: list, **kwargs) -> InferenceNode:
        """Capture a tool call / action output as a branch."""
        return self.capture_role_turn(
            TurnRole.ACTION,
            message,
            node_type="branch",
            semantic_label=kwargs.get("label", "Action"),
            tool_calls=tool_calls,
            **kwargs
        )
    
    def close(self):
        self.tree._close()
    
    @property
    def first(self):
        return self._first_node
    
    @property
    def last(self):
        if self.context.node_history:
            return self.context.node_history[-1]
        return None


class LiveCapture:
    """Interactive capture that runs in a loop."""
    
    def __init__(self, stream_path: Path, context: CaptureContext = None):
        self.stream_path = stream_path
        if context is None:
            self.context = CaptureContext(
                session_id=f"live-{time.strftime('%Y%m%d-%H%M%S')}",
                platform="matrix",
                description="Live Matrix capture session",
                created=time.time()
            )
        else:
            self.context = context
        self.engine = CaptureEngine(stream_path, self.context)
        self.running = False
    
    def start(self):
        """Begin live capture mode."""
        print("[*] Live Capture mode started.")
        print(f"  Session: {self.context.session_id}")
        print(f"  Platform: {self.context.platform}")
        print(f"  Stream: {self.stream_path}")
        print(f"  {'='*50}")
        print("  Input format: ROLE:message")
        print("    where ROLE = user | assistant | action | system")
        print("  Type 'exit' to stop.")
        print(f"  {'='*50}\n")
        
        self.running = True
        
        # Capture system boot node
        self.engine.capture_system_node(
            f"Live capture session initialized.\nPlatform: {self.context.platform}\n"
            rf"Start: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Description: {self.context.description}",
            label="Session Boot"
        )
        
        while self.running:
            try:
                raw = input(">>> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            
            if raw.lower() in ("exit", "quit", "q"):
                break
            
            if not raw:
                continue
            
            # Parse role:message
            if ":" in raw:
                role_str, message = raw.split(":", 1)
                role_str = role_str.strip().lower()
                message = message.strip()
            else:
                role_str = "user"
                message = raw
            
            role_map = {
                "u": TurnRole.USER,
                "user": TurnRole.USER,
                "a": TurnRole.ASSISTANT,
                "assistant": TurnRole.ASSISTANT,
                "act": TurnRole.ACTION,
                "action": TurnRole.ACTION,
                "sys": TurnRole.SYSTEM,
                "system": TurnRole.SYSTEM
            }
            
            role = role_map.get(role_str, TurnRole.USER)
            
            node = self.engine.capture_role_turn(role, message, label=f"{role_str}")
            print(f"  [✓] Turn #{node.turn_number}: {node.semantic_label[:50]}...")
        
        self.engine.close()
        self.running = False
        return self.context


class BatchCapture:
    """Capture from a structured JSON input (chat log export)."""
    
    def __init__(self, stream_path: Path, context: CaptureContext = None):
        self.context = context or CaptureContext(
            session_id=f"batch-{time.strftime('%Y%m%d-%H%M%S')}",
            platform="jsonl",
            description="Batch capture from structured input",
            created=time.time()
        )
        self.engine = CaptureEngine(stream_path, self.context)
    
    def capture_from_dict(self, turns: list[dict]) -> list[InferenceNode]:
        """Capture a list of turn dicts into the tree."""
        nodes = []
        last_id = self.context.node_history[0].id if self.context.node_history else None
        
        for turn in turns:
            role_str = turn.get("role", "user").lower()
            role_map = {
                "user": TurnRole.USER,
                "assistant": TurnRole.ASSISTANT,
                "system": TurnRole.SYSTEM,
                "action": TurnRole.ACTION
            }
            role = role_map.get(role_str, TurnRole.USER)
            
            message = turn.get("message", "")
            metadata = turn.get("metadata", {})
            
            # If this is the first user message after system, use genesis parent
            parent_id = turn.get("parent_id", last_id)
            
            node = self.engine.capture_role_turn(
                role, message,
                parent_id=parent_id,
                label=turn.get("label", role_str),
                metadata=metadata
            )
            nodes.append(node)
            last_id = node.id
        
        return nodes
    
    def close(self):
        self.engine.close()


# ─── Demo Mode ──────────────────────────────────────────────────────────────

def run_demo(stream_path: Path = None):
    """Run a demonstration of the capture module with simulated turns."""
    base_path = Path(__file__).parent / "samples"
    base_path.mkdir(parents=True, exist_ok=True)
    
    if stream_path is None:
        stream_path = base_path / f"capture_demo-{time.strftime('%Y%m%d-%H%M%S')}.jsonl"
    
    context = CaptureContext(
        session_id=f"demo-{time.strftime('%Y%m%d-%H%M%S')}",
        platform="matrix",
        description="Demo conversation about tree architecture",
        created=time.time()
    )
    
    engine = CaptureEngine(stream_path, context)
    
    print("="*60)
    print("INFERENCE CAPTURE — Demo Mode")
    print("="*60)
    print(f"  Stream: {stream_path}")
    print(f"  Session: {context.session_id}")
    print("="*60)
    
    # System boot node
    system_node = engine.capture_system_node(
        f"Demo capture session:\n"
        f"Platform: matrix\n"
        f"Start: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
        f"Scenario: Tree architecture discussion",
        label="Session Boot"
    )
    print(f"\n[✓] System boot node: {system_node.semantic_label}")
    
    # User says first turn
    user1 = engine.capture_role_turn(
        TurnRole.USER,
        "Hey VIGIL — are the test files pushed to GitHub now?",
        parent_id=system_node.id,
        label="Question"
    )
    print(f"[✓] User: {user1.semantic_label}")
    print(f"    id={user1.id[:16]}... parent={system_node.id[:16]}...")
    
    # Assistant response
    assistant1 = engine.capture_role_turn(
        TurnRole.ASSISTANT,
        "Yes. All three modules are committed and pushed:\n\n"
        "1. test_tree.py — 129/129 passing (exit 0)\n"
        "2. sandbox.py — fixed and validated\n"
        "3. samples/ — all artifacts written\n\n"
        "Commit: 41aa64f on origin/main.",
        parent_id=user1.id,
        label="Answer"
    )
    print(f"[✓] Assistant: {assistant1.semantic_label}")
    print(f"    id={assistant1.id[:16]}... parent={user1.id[:16]}...")
    
    # User follows up
    user2 = engine.capture_role_turn(
        TurnRole.USER,
        "Can you show me an example InferenceNode so I can see the structure?",
        parent_id=assistant1.id,
        label="Request"
    )
    print(f"[✓] User: {user2.semantic_label}")
    print(f"    id={user2.id[:16]}... parent={assistant1.id[:16]}...")
    
    # Assistant shows node
    assistant2 = engine.capture_role_turn(
        TurnRole.ASSISTANT,
        "Here's the InferenceNode structure:\n\n"
        "  id          : hex SHA-256 hash of content\n"
        "  node_type   : stem | branch | leaf | fruit\n"
        "  status      : active | terminal | resolved\n"
        "  parent_hash : points to parent node\n"
        "  children    : list of child node IDs\n"
        "  prompt/response : the actual conversation content\n"
        "  model/provider : which AI was used\n"
        "  metadata    : tool calls, timestamps, etc.\n\n"
        "Each node is self-contained — the tree links them in-memory.",
        parent_id=user2.id,
        label="Example"
    )
    print(f"[✓] Assistant: {assistant2.semantic_label}")
    print(f"    id={assistant2.id[:16]}... parent={user2.id[:16]}...")
    
    # User requests tree
    user3 = engine.capture_role_turn(
        TurnRole.USER,
        "Let's initialize this to capture our current Matrix conversation.",
        parent_id=assistant2.id,
        label="Init"
    )
    print(f"[✓] User: {user3.semantic_label}")
    print(f"    id={user3.id[:16]}... parent={assistant2.id[:16]}...")
    
    engine.close()
    
    # Re-open the stream to read it back (capture engine already removed file refs)
    print("\n" + "-"*60)
    tree = InferenceTree(stream_path)
    tree._open()
    
    # Rebuild from stream entries
    import json
    with open(stream_path) as f:
        entries = [json.loads(line) for line in f if line.strip()]
    
    # Since CaptureEngine uses append mode, tree was writing to it directly
    # Re-read the stream to confirm
    print(f"  Stream entries: {len(entries)}")
    if entries:
        # Re-add nodes to tree for verification
        for entry in entries:
            node = InferenceNode(
                entry.get("prompt_snapshot", ""),
                entry.get("response_snapshot", ""),
                node_type=entry.get("node_type", "stem"),
                parent_hash=entry.get("parent_hash", "genesis"),
                semantic_label=entry.get("semantic_label"),
            )
            if entry.get("children_hashes") and entry["children_hashes"] != "[]":
                node.children_hashes = entry["children_hashes"] or []
            node.id = entry["id"]
            tree.nodes_by_id[node.id] = node
        
        print(f"  Reconstruction: {len(tree.nodes_by_id)} nodes")
    
    # Generate views via composer on raw entries
    composer = TreeComposer(tree)
    
    return context, engine, stream_path


# ─── CLI Entry ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Inference Tree Capture Engine")
    parser.add_argument("--stream", type=str, help="Stream file path")
    parser.add_argument("--batch", type=str, help="JSON file to batch import")
    parser.add_argument("--demo", action="store_true", help="Run demo mode")
    parser.add_argument("--live", action="store_true", help="Start live capture")
    args = parser.parse_args()
    
    base_path = Path(__file__).parent / "samples"
    base_path.mkdir(parents=True, exist_ok=True)
    
    if args.demo or (not args.batch and not args.live):
        stream = Path(args.stream) if args.stream else None
        run_demo(stream)
    elif args.live:
        stream = Path(args.stream) if args.stream else base_path / "live_capture.jsonl"
        live = LiveCapture(stream)
        live.start()
    elif args.batch:
        stream = Path(args.stream) if args.stream else base_path / "batch_capture.jsonl"
        context = CaptureContext(
            session_id=f"batch-{time.strftime('%Y%m%d-%H%M%S')}",
            platform="batch",
            description=f"Batch capture from {args.batch}",
            created=time.time()
        )
        bc = BatchCapture(stream, context)
        with open(args.batch) as f:
            turns = json.load(f)
        nodes = bc.capture_from_dict(turns)
        bc.close()
        print(f"[✓] Captured {len(nodes)} turns from {args.batch}")
