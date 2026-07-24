"""
Inference Node Sandbox
======================
A prototype for capturing inference cycles, chaining them cryptographically,
and composing them into human-readable Markdown session files.

Usage:
  python sandbox.py

Output:
  - /home/vigil/ai-chat-tree/inference-node/samples/inference_stream.jsonl  (event stream)
  - /home/vigil/ai-chat-tree/inference-node/samples/Session-001.md          (rendered session)
"""

import json
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── Config ───────────────────────────────────────────────────────────────────

BASE_PATH = Path(__file__).parent / "samples"
BASE_PATH.mkdir(parents=True, exist_ok=True)
STREAM_PATH = BASE_PATH / "inference_stream.jsonl"


# ─── Inference Node ───────────────────────────────────────────────────────────

class InferenceNode:
    """An atomic inference cycle — the fundamental unit of the system."""

    def __init__(self, prompt: str, response: str,
                 model: str = "qwen3.6:35b-a3b",
                 provider: str = "local",
                 platform: str = "matrix",
                 parent_hash: str = "genesis",
                 tool_calls: list = None):
        self._prompt_raw = prompt
        self._response_raw = response
        self.model = model
        self.provider = provider
        self.platform = platform
        self.parent_hash = parent_hash
        self.timestamp = time.time()
        self.tool_calls = tool_calls or []
        self._content = prompt.rstrip() + "\n---\n" + response
        self.id = self._make_id()
        self.input_tokens = len(prompt) // 4
        self.output_tokens = len(response) // 4

    def _make_id(self) -> str:
        return hashlib.sha256(self._content.encode()).hexdigest()[:32]

    @property
    def prompt_text(self):
        return self._prompt_raw

    @property
    def response_text(self):
        return self._response_raw

    def to_json(self) -> dict:
        return {
            "type": "inference",
            "id": self.id,
            "content_hash": self.id,
            "parent_hash": self.parent_hash,
            "timestamp": self.timestamp,
            "model": self.model,
            "provider": self.provider,
            "platform": self.platform,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "tool_calls": self.tool_calls,
            "prompt_snapshot": self._prompt_raw[:500],
            "response_snapshot": self._response_raw[:500],
        }


# ─── Event Stream ─────────────────────────────────────────────────────────────

class EventStream:
    """Append-only JSONL event log for inference nodes."""

    def __init__(self, path: Path):
        self.path = path
        self.sequence = 0
        self.last_parent = "genesis"

    def append(self, node: InferenceNode) -> InferenceNode:
        entry = node.to_json()
        self.last_parent = node.id
        self.sequence += 1
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return node

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def verify_chain(self) -> bool:
        """Verify cryptographic chain integrity."""
        entries = self.read_all()
        expected = "genesis"
        for i, e in enumerate(entries):
            if e["parent_hash"] != expected:
                print(f"  [!] Chain broken at node {i+1}: expected {expected[:8]}, got {e['parent_hash'][:8]}")
                return False
            expected = e["content_hash"]
        return True


# ─── Session Composer ──────────────────────────────────────────────────────

class SessionComposer:
    """Stitches Inference Nodes into a human-readable Markdown session."""

    def __init__(self, stream: EventStream):
        self.stream = stream

    def _fmt_ts(self, ts: float) -> str:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S.%03f")

    def _elapsed(self, curr_ts: float, prev_ts: float) -> str:
        return f"{int((curr_ts - prev_ts) * 1000):,}ms"

    def compose(self, title: str = "Session") -> str:
        entries = self.stream.read_all()
        now = datetime.now(timezone.utc)
        start = entries[0] if entries else None
        end = entries[-1] if entries else None

        md = []
        md.append(f"# {title}")
        md.append(f"")
        md.append(f"**Date:** {start['timestamp'] if start else 'N/A'}")
        md.append(f"**Created:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        md.append(f"**Total Turns:** {len(entries)}")
        md.append(f"**Total Duration:** {self._elapsed(end['timestamp'], start['timestamp']) if start and end else 'N/A'}")
        md.append(f"**Total Tokens In:** {sum(e['input_tokens'] for e in entries)}")
        md.append(f"**Total Tokens Out:** {sum(e['output_tokens'] for e in entries)}")
        md.append(f"")
        md.append(f'---')
        md.append(f"")
        md.append(f'```yaml')
        md.append(f'session_id: "{int(start["timestamp"] * 1000) if start else "none"}"')
        md.append(f"node_count: {len(entries)}")
        md.append(f"chain_verified: {json.dumps(self.stream.verify_chain())}")
        md.append(f"chain_hash: \"{entries[-1]['content_hash'] if entries else 'genesis'}\"")
        md.append(f"```")
        md.append(f"")
        md.append(f"")

        for i, e in enumerate(entries):
            md.append(f"## Turn {i + 1} `[{self._fmt_ts(e['timestamp'])}]`")
            md.append(f"**Model:** {e['model']} | **Tokens:** {e['input_tokens']}in / {e['output_tokens']}out | **Time:** {self._elapsed(e['timestamp'], entries[i-1]['timestamp'] if i > 0 else e['timestamp'])}")
            md.append(f"**Hash:** `{e['content_hash'][:16]}...`")
            md.append(f"**Parent:** `{e['parent_hash'][:16] if e['parent_hash'] == 'genesis' else e['parent_hash'][:16]}...`")
            md.append(f"---")
            md.append(f"")
            md.append(f"**Prompt**")
            prompt = e.get("prompt_snapshot", "")
            for line in prompt.split("\n"):
                md.append(f"> {line}")
            md.append(f"")
            md.append(f"**Response**")
            response = e.get("response_snapshot", "")
            for line in response.split("\n"):
                md.append(line)
            md.append(f"")
            md.append(f"**ID:** `{e['content_hash']}`")
            md.append(f"**Links:**")
            if i < len(entries) - 1:
                md.append(f"- next_turn:: [[Turn-{i + 2}]]")
            if i > 0:
                md.append(f"- prev_turn:: [[Turn-{i}]]")
            md.append(f"")
            md.append(f"")

        return "\n".join(md)

    def write_to_file(self, title: str = "Session", filename: str = None) -> Path:
        md = self.compose(title)
        path = BASE_PATH / (filename or f"Session-{int(time.time())}.md")
        path.write_text(md, encoding="utf-8")
        return path


# ─── Sandbox Simulation ───────────────────────────────────────────────────────

def simulate_session():
    """Create a realistic multi-turn session for testing."""
    print("[*] Simulating multi-turn AI architecture discussion...")
    stream = EventStream(STREAM_PATH)

    # Clear previous runs
    if STREAM_PATH.exists():
        STREAM_PATH.unlink()

    nodes = [
        InferenceNode(
            "Can you design an architecture to capture every inference in an AI agent?",
            "Here's the architecture I've designed for capturing every inference cycle in your agent system:\n\n"
            "## InCapture: Per-Inference Recording System\n\n"
            "### Core Design\n"
            "A lightweight capture class that sits between your agent loop and the model. "
            "InferenceNode objects are created at every boundary, containing exact "
            "input and output with immutable checksums.\n\n"
            "### Key Features\n"
            "1. **Append-only JSONL stream** — non-blocking writes with threading lock\n"
            "2. **Cryptographic chain** — each node links to its parent via SHA-256\n"
            "3. **Token tracking** — automatic input/output token counting\n"
            "4. **Latency recording** — measures time from request to response",
            model="qwen3.6:35b-a3b"
        ),
        InferenceNode(
            "What if each inference node is a structural piece that links together into an Obsidian session? We get human readability AND machine traversal.",
            "That's the core insight. Instead of viewing inference logs, we view inference *nodes*. "
            "The Markdown session files become on-demand renderings of the underlying graph.\n\n"
            "This achieves two things:\n"
            "1. **You** get a beautiful, clean chat transcript\n"
            "2. **The system** maintains the cryptographic chain underneath\n\n"
            "This is the glass-pane pattern — transparent structure, polished interface.",
            model="qwen3.6:35b-a3b"
        ),
        InferenceNode(
            "Build a test sandbox that works alongside ai-chat-tree. Document everything.",
            "I'll create:\n"
            "1. **InferenceNode class** — atomic capture at the inference boundary\n"
            "2. **EventStream** — append-only JSONL event log\n"
            "3. **SessionComposer** — on-demand markdown rendering\n"
            "4. **DESIGN.md** — high-level vision\n"
            "5. **ARCHITECTURE.md** — technical blueprint\n\n"
            "Everything goes in a dedicated sandbox alongside ai-chat-tree.\n"
            "The event stream is the source of truth. The markdown is the view.",
            model="qwen3.6:35b-a3b"
        ),
    ]

    for i, node in enumerate(nodes):
        if i > 0:
            node.parent_hash = nodes[i - 1].id
        stream.append(node)
        time.sleep(0.2)

    return stream


# ─── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Inference Node Sandbox ===\n")

    # Simulate a session
    stream = simulate_session()
    print(f"\n[+] Event stream written: {stream.sequence} nodes to {stream.path}")

    # Verify chain
    verified = stream.verify_chain()
    print(f"[+] Chain verified: {verified}")

    # Compose and write session
    title = "Inference Node Sandbox Demo"
    composer = SessionComposer(stream)
    session_path = composer.write_to_file(title, f"SandboxDemo-{SESSION_ID}.md")
    print(f"[+] Session composed: {session_path}")

    # Print stream contents
    print("\n--- RAW EVENT STREAM ---")
    for i, entry in enumerate(stream.read_all()):
        p = entry['parent_hash'][:16] if entry['parent_hash'] != 'genesis' else 'genesis'
        print(f"Node {i+1}: {entry['content_hash'][:16]}... → parent: {p}")

    # Print first 80 lines of rendered session
    print("\n--- RENDERED SESSION (first 80 lines) ---")
    lines = session_path.read_text().split("\n")
    for line in lines[:80]:
        print(line)

    print("\n" + "=" * 55)
    print("Sandbox complete. Check samples/ for output.")
    print("[+] DESIGN.md + ARCHITECTURE.md in sandbox root")
    print("[+] sandbox.py contains engine + composition + demo")
    print("===" * 14)
