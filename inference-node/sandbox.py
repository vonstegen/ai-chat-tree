"""
Inference Node Sandbox (Tree Edition)
=====================================
Capture inference cycles as a **rooted tree** — not a linear chain.

Metaphor (Ternary Rod Rig):
  ROOT  — genesis, the origin node
  STEM  — the main inference chain (linear backbone of the session)
  BRANCH — a divergence: alternate hypothesis, side-thread, alternative path
  LEAF  — a terminal branch (no children; represents a conclusion or dead end)
  FRUIT — a resolved branch that carries information back to the stem

All nodes are cryptographically chain-linked. Branches link via parent_hash.
Leaves and fruits are semantic labels for traversal semantics, not structural ones.

Usage:
  python sandbox.py

Output:
  - samples/inference_stream.jsonl   (full tree event stream)
  - samples/SandboxDemo-*.md         (rendered view)
  - samples/tree_diagram.txt         (visual tree diagram)
"""

import json
import hashlib
import time
from datetime import datetime, timezone
from pathlib import Path

# ─── Config ──────────────────────────────────────────────────────────────

BASE_PATH = Path(__file__).parent / "samples"
BASE_PATH.mkdir(parents=True, exist_ok=True)
STREAM_PATH = BASE_PATH / "inference_stream.jsonl"
SESSION_ID = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


# ─── Inference Node ──────────────────────────────────────────────────────

class InferenceNode:
    """Atomic inference unit in a rooted tree — not a flat chain."""

    TYPE_STEM = "stem"
    TYPE_BRANCH = "branch"
    TYPE_LEAF = "leaf"
    TYPE_FRUIT = "fruit"

    STATUS_ACTIVE = "active"
    STATUS_RESOLVED = "resolved"
    STATUS_TERMINAL = "terminal"

    def __init__(self, prompt: str, response: str,
                 model: str = "qwen3.6:35b-a3b",
                 provider: str = "local",
                 platform: str = "matrix",
                 parent_hash: str = "genesis",
                 node_type: str = TYPE_STEM,
                 semantic_label: str = None,
                 info_carryback: dict = None,
                 children_hashes: list = None,
                 tool_calls: list = None):
        self._prompt_raw = prompt
        self._response_raw = response
        self.model = model
        self.provider = provider
        self.platform = platform
        self.parent_hash = parent_hash
        self.node_type = node_type          # stem | branch | leaf | fruit
        self.semantic_label = semantic_label # human-readable label
        self.info_carryback = info_carryback # data flowing back from resolved fruit
        self.children_hashes = children_hashes or []
        if node_type == InferenceNode.TYPE_LEAF:
            self.status = InferenceNode.STATUS_TERMINAL
        elif node_type == InferenceNode.TYPE_FRUIT:
            self.status = InferenceNode.STATUS_RESOLVED
        else:
            self.status = InferenceNode.STATUS_ACTIVE
        self.timestamp = time.time()
        self.tool_calls = tool_calls or []
        self._content = prompt.rstrip() + "\n---\n" + response
        self.id = self._make_id()
        self.input_tokens = len(prompt) // 4
        self.output_tokens = len(response) // 4
        self.depth = self._compute_depth(parent_hash)

    def _make_id(self) -> str:
        return hashlib.sha256(self._content.encode()).hexdigest()[:32]

    def _compute_depth(self, parent_hash: str) -> int:
        if parent_hash == "genesis":
            return 0
        return 1  # simplified; actual depth computed by tree walk later

    @property
    def prompt_text(self):
        return self._prompt_raw

    @property
    def response_text(self):
        return self._response_raw

    def to_json(self) -> dict:
        return {
            "type": "inference",
            "node_type": self.node_type,
            "id": self.id,
            "content_hash": self.id,
            "parent_hash": self.parent_hash,
            "children_hashes": self.children_hashes,
            "semantic_label": self.semantic_label,
            "status": self.status,
            "info_carryback": self.info_carryback,
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


# ─── Inference Tree (not chain) ────────────────────────────────────────────

class InferenceTree:
    """Rooted tree of InferenceNodes. Manages branching, fruiting, leafing."""

    def __init__(self, path: Path):
        self.path = path
        self.sequence = 0
        self.nodes_by_id = {}  # id -> InferenceNode
        self.roots = []        # nodes with parent_hash == "genesis"
        self._file_handle = None

        # Clear previous runs
        if path.exists():
            path.unlink()

    def _open(self):
        self._file_handle = open(self.path, "a", encoding="utf-8")

    def _close(self):
        if self._file_handle:
            self._file_handle.close()
            self._file_handle = None

    def append(self, node: InferenceNode) -> InferenceNode:
        """Append a node to the tree. Children linked in-memory only."""
        if node.parent_hash != "genesis":
            parent = self.nodes_by_id.get(node.parent_hash)
            if parent:
                # Only add if not already present
                if node.id not in parent.children_hashes:
                    parent.children_hashes = parent.children_hashes + [node.id]

        if node.parent_hash == "genesis" and not self.roots:
            node.parent_hash = "genesis"
            self.roots.append(node)

        self.nodes_by_id[node.id] = node
        entry = node.to_json()
        self.sequence += 1
        if not self._file_handle:
            self._open()
        self._file_handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._file_handle.flush()
        return node

    def _read_entries(self) -> list:
        if not self.path.exists():
            return []
        with open(self.path, "r", encoding="utf-8") as f:
            return [json.loads(line) for line in f if line.strip()]

    def get_descendants(self, node_id: str) -> list[InferenceNode]:
        """Get all descendants of a node (depth-first)."""
        descendants = []
        queue = [node_id]
        while queue:
            current_id = queue.pop(0)
            node = self.nodes_by_id.get(current_id)
            if not node:
                continue
            descendants.append(node)
            for child_id in node.children_hashes:
                queue.append(child_id)
        return descendants

    def find_leaves(self) -> list[InferenceNode]:
        """Find all terminal nodes (leaves) — nodes with no children."""
        leaves = []
        for node in self.nodes_by_id.values():
            if not node.children_hashes:
                leaves.append(node)
        return leaves

    def find_fruits(self) -> list[InferenceNode]:
        """Find all resolved fruit nodes."""
        return [n for n in self.nodes_by_id.values() if n.node_type == InferenceNode.TYPE_FRUIT]

    def find_branches(self) -> list[InferenceNode]:
        """Find all branch nodes (divergences from stem)."""
        return [n for n in self.nodes_by_id.values() if n.node_type == InferenceNode.TYPE_BRANCH]

    def verify_tree(self) -> bool:
        """Verify all parent-child links are intact."""
        for node in self.nodes_by_id.values():
            if node.parent_hash != "genesis":
                if node.parent_hash not in self.nodes_by_id:
                    print(f"  [!] Lost parent: {node.id[:16]}... refs {node.parent_hash[:16]}...")
                    return False
            for child_id in node.children_hashes:
                if child_id not in self.nodes_by_id:
                    print(f"  [!] Lost child: {node.id[:16]}... refs {child_id[:16]}...")
                    return False
        return True

    def render_diagram(self, node_id: str = None, indent: int = 0, is_root: bool = False, _visited: set = None) -> str:
        """Render a text tree diagram."""
        if _visited is None:
            _visited = set()

        if not node_id:
            if not self.roots:
                return "  (empty tree)"
            node_id = self.roots[0].id

        if node_id in _visited:
            return "  [↻ visited]"

        _visited.add(node_id)
        node = self.nodes_by_id.get(node_id)
        if not node:
            return "  (node not found)"

        prefix = "  " * indent
        if is_root:
            prefix = ""
            marker = "[@]"
        elif node.node_type == InferenceNode.TYPE_LEAF:
            marker = "[✦]"  # terminal
        elif node.node_type == InferenceNode.TYPE_FRUIT:
            marker = "[✿]"  # resolved, carries info
        elif node.node_type == InferenceNode.TYPE_BRANCH:
            marker = "[⇢]"  # divergence
        else:
            marker = "[—]"  # stem

        label = f"{marker} {node.semantic_label or node.id[:12]}..."
        type_tag = f"({node.node_type})"
        lines = [f"{prefix}{label} {type_tag} [{node.status}]"]

        for child_id in node.children_hashes:
            child_node = self.nodes_by_id.get(child_id)
            if child_node:
                child_prefix = prefix + ("  " if is_root else "")
                lines.append(self.render_diagram(child_id, indent + 1, False))

        return "\n".join(lines)


# ─── Multi-View Composer (Tree) ──────────────────────────────────────────

class TreeComposer:
    """Stitches Inference Nodes from a tree into human-readable views."""

    def __init__(self, tree: InferenceTree):
        self.tree = tree

    def _fmt_ts(self, ts: float) -> str:
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S.%f")

    def _elapsed(self, curr_ts: float, prev_ts: float) -> str:
        return f"{int((curr_ts - prev_ts) * 1000):,}ms"

    def _render_node(self, node: InferenceNode, indent: int = 0) -> list[str]:
        """Render a single node as markdown."""
        md = []
        prefix = "  " * indent
        depth_tag = f"{'│'.join(['│'] * max(0, node.depth - 1))} " if node.depth > 1 else ""

        label = node.semantic_label or f"Turn@{self._fmt_ts(node.timestamp)[:8]}"
        md.append(f"{prefix}## {depth_tag}{label} `{node.node_type} [{node.status}]`")
        md.append(f"{prefix}**Model:** {node.model} | **Tokens:** {node.input_tokens}in/{node.output_tokens}out | **Time:** {[self._elapsed(node.timestamp, 0), '—'][1]}")
        md.append(f"{prefix}**ID:** `{node.id}`")
        md.append(f"{prefix}**Parent:** `{node.parent_hash if node.parent_hash == 'genesis' else node.parent_hash[:16]}...`")
        md.append(f"{prefix}**Children:** {len(node.children_hashes)}")
        if node.info_carryback:
            md.append(f"{prefix}**Carryback:** {json.dumps(node.info_carryback)}")
        md.append(f"{prefix}---")
        md.append(f"{prefix}")
        md.append(f"{prefix}> **Prompt**")
        for line in node._prompt_raw.split("\n"):
            md.append(f"{prefix}> {line}")
        md.append(f"{prefix}")
        md.append(f"{prefix}> **Response**")
        for line in node._response_raw.split("\n"):
            # Don't re-quote — just indent
            md.append(f"{prefix}> {line}")
        md.append(f"{prefix}")

        return md

    def compose_stem_view(self) -> str:
        """Render the main stem path (linear backbone of the session)."""
        entries = self._read_stem()
        now = datetime.now(timezone.utc)
        start = entries[0] if entries else None
        end = entries[-1] if entries else None

        md = []
        md.append("# Inference Tree — Stem View")
        md.append("")
        md.append(f"**Date range:** {start.timestamp if start else 'N/A'} — {end.timestamp if end else 'N/A'}")
        md.append(f"**Created:** {now.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        md.append(f"**Stem turns:** {len(entries)}")
        md.append(f"**Branches:** {len(self.tree.find_branches())}")
        md.append(f"**Fruits:** {len(self.tree.find_fruits())}")
        md.append(f"**Leaves:** {len(self.tree.find_leaves())}")
        md.append(f"**Chain verified:** {self.tree.verify_tree()}")
        md.append("")
        md.append("---")
        md.append("")
        md.append("```yaml")
        md.append(f"view: stem")
        md.append(f"mode: linear-backbone")
        md.append(f"tree_verified: true")
        md.append("```")
        md.append("")

        for i, node in enumerate(entries):
            node_md = self._render_node(node, 0)
            md.extend(node_md)
            md.append("")

        return "\n".join(md)

    def compose_branch_view(self) -> str:
        """Render all branches as parallel tracks."""
        branches = self.tree.find_branches()
        fruits = self.tree.find_fruits()
        leaves = self.tree.find_leaves()

        md = []
        md.append("# Inference Tree — Branch View")
        md.append("")
        md.append(f"**Stem turns:** {len(self._read_stem())}")
        md.append(f"**Branches:** {len(branches)}")
        md.append(f"**Fruits (resolved):** {len(fruits)}")
        md.append(f"**Leaves (terminal):** {len(leaves)}")
        md.append("")
        md.append("---")
        md.append("")

        # Stem first
        md.append("## 🌿 Stem (Main Chain)")
        md.append("")
        for node in self._read_stem():
            node_md = self._render_node(node, 1)
            md.extend(node_md)
        md.append("")
        md.append("---")
        md.append("")

        # Branches
        if branches:
            md.append("## ⇢ Branches (Divergences)")
            md.append("")
            for branch in branches:
                descendants = self.tree.get_descendants(branch.id)
                md.append(f"### Branch: `{branch.semantic_label or branch.id[:16]}...`")
                md.append("")
                branch_md = self._render_node(branch, 1)
                md.extend(branch_md)
                md.append("")
                for desc in descendants:
                    desc_md = self._render_node(desc, 2)
                    md.extend(desc_md)
                md.append("")
                md.append("---")
                md.append("")

        # Fruits
        if fruits:
            md.append("## ✿ Fruits (Resolved Branches with Carryback)")
            md.append("")
            for fruit in fruits:
                md.append(f"### Fruit: `{fruit.semantic_label or fruit.id[:16]}...`")
                md.append("")
                fruit_md = self._render_node(fruit, 1)
                md.extend(fruit_md)
                if fruit.info_carryback:
                    md.append("> **Carryback to stem:** " + json.dumps(fruit.info_carryback))
                md.append("")
                md.append("---")
                md.append("")

        # Leaves
        if leaves:
            md.append("## ✦ Leaves (Terminal Points)")
            md.append("")
            for leaf in leaves:
                md.append(f"### Leaf: `{leaf.semantic_label or leaf.id[:16]}...`")
                md.append("")
                leaf_md = self._render_node(leaf, 1)
                md.extend(leaf_md)
                md.append("")

        return "\n".join(md)

    def _read_stem(self) -> list[InferenceNode]:
        """Read the main stem path from genesis to deepest leaf."""
        if not self.tree.roots:
            return []
        stem = [self.tree.roots[0]]
        current = self.tree.roots[0]
        while current.children_hashes:
            next_id = current.children_hashes[0]  # first child = stem continuation
            next_node = self.tree.nodes_by_id.get(next_id)
            if not next_node:
                break
            # Prefer stem over branch
            if next_node.node_type == InferenceNode.TYPE_BRANCH:
                break  # stem ends at branch point
            stem.append(next_node)
            current = next_node
        return stem

    def write_to_file(self, title: str = "Tree View", filename: str = None) -> dict:
        """Write both views (stem + branch) plus diagram."""
        stem_path = BASE_PATH / (filename or f"StemView-{SESSION_ID}.md")
        branch_path = BASE_PATH / (filename or f"BranchView-{SESSION_ID}.md")

        stem_md = self.compose_stem_view()
        branch_md = self.compose_branch_view()

        stem_path.write_text(stem_md, encoding="utf-8")
        branch_path.write_text(branch_md, encoding="utf-8")

        # Also write tree diagram
        diag_path = BASE_PATH / (filename or f"TreeDiagram-{SESSION_ID}.md")
        diagram_lines = [
            "# Inference Tree — Visual Diagram",
            "",
            self.tree.render_diagram(is_root=True),
            "",
            "---",
            "",
            f"**Total nodes:** {len(self.tree.nodes_by_id)}",
            f"**Stem length:** {len(self._read_stem())}",
            f"**Branches:** {len(self.tree.find_branches())}",
            f"**Fruits:** {len(self.tree.find_fruits())}",
            f"**Leaves:** {len(self.tree.find_leaves())}",
            f"**Verified:** {self.tree.verify_tree()}",
        ]
        diag_path.write_text("\n".join(diagram_lines), encoding="utf-8")

        return {"stem": stem_path, "branch": branch_path, "diagram": diag_path}


# ─── Tree Simulation ──────────────────────────────────────────────────────

def simulate_tree_session():
    """Create a realistic branching session for testing."""
    print("[*] Simulating multi-branch inference tree...")
    tree = InferenceTree(STREAM_PATH)
    tree._open()

    # ── Main stems (genesis → root → stem 1 → stem 2) ─────────────
    stem1 = InferenceNode(
        "Design an architecture for capturing every inference in an agent.",
        "Here's the core architecture:\n\n## InCapture System\n"
        "A lightweight capture layer sits between the agent loop and the model.\n"
        "Each inference creates an immutable node with SHA-256 hashing.\n\n"
        "Key layers:\n1. Prompt/response capture at inference boundary\n"
        "2. Append-only JSONL event log\n3. Cryptographic chain links\n"
        "4. On-demand Markdown rendering",
        model="qwen3.6:35b-a3b", semantic_label="Architecture Design", node_type="stem"
    )
    tree.append(stem1)

    stem2 = InferenceNode(
        "What if each node links into Obsidian to form a session graph?",
        "That's the glass-pane pattern:\n\n1. **You** get a clean chat transcript\n"
        "2. **The system** maintains a cryptographic chain underneath\n"
        "3. **MD files** are rendered views, not the source of truth\n"
        "4. **JSONL** is the immutable event stream\n\n"
        "This gives us both human readability and machine traversability.",
        model="qwen3.6:35b-a3b", semantic_label="Graph Concept", node_type="stem",
        parent_hash=stem1.id
    )
    tree.append(stem2)

    # ── Branch 1: Alternative approach ──────────────────────────────
    branch1 = InferenceNode(
        "What about handling parallel hypotheses? Can we branch?",
        "Yes — each inference can spawn a branch node:\n\n"
        "- **STEM**: the main chain (linear backbone)\n"
        "- **BRANCH**: a divergence (alternate approach)\n"
        "- **LEAF**: terminal branch (conclusion or dead end)\n"
        "- **FRUIT**: resolved branch that carries info back to stem\n\n"
        "Branches link to their parent via parent_hash, not the chain.",
        model="qwen3.6:35b-a3b", semantic_label="Branching Concept", node_type="branch",
        parent_hash=stem2.id
    )
    tree.append(branch1)

    branch1_child1 = InferenceNode(
        "How does carryback work? What if a branch proves a hypothesis right or wrong?",
        "Carryback is a structured info field on the fruit node:\n\n"
        "info_carryback: {\n"
        "  status: 'confirmed' | 'rejected' | 'modified',\n"
        "  key_finding: '... the resolved insight',\n"
        "  affects: ['stem_node_A', 'stem_node_B']\n"
        "}\n\n"
        "The stem composer reads carryback and annotates affected stem nodes.",
        model="qwen3.6:35b-a3b", semantic_label="Carryback Protocol", node_type="branch",
        parent_hash=branch1.id
    )
    tree.append(branch1_child1)

    fruit1 = InferenceNode(
        "So fruits are like merge commits — they carry resolved information back to the stem.",
        "Exactly. A fruit is a resolved branch:\n\n"
        "✿ Resolved — the branch reached a conclusion\n"
        "✿ Carries info back to parent stem nodes\n"
        "✿ Maintains full cryptographic chain\n"
        "✿ Can be revisited (regenerated) without losing the record\n\n"
        "The stem view remains clean; the branch view shows everything.",
        model="qwen3.6:35b-a3b", semantic_label="Fruit Model", node_type="fruit",
        parent_hash=branch1_child1.id,
        info_carryback={"status": "confirmed", "key_finding": "Branching is essential for AI reasoning", "affects": ["Architecture Design", "Graph Concept"]}
    )
    tree.append(fruit1)

    # ── Branch 2: Side exploration ──────────────────────────────────
    branch2 = InferenceNode(
        "How do leaves differ from fruits?",
        "Leaves are terminal — they don't carry anything back.\n\n"
        "✦ LEAF: endpoint of exploration, no merge\n"
        "✦ FRUIT: resolved, carries info to parent stem\n\n"
        "Both are structurally identical to stem nodes. The difference is semantic.",
        model="qwen3.6:35b-a3b", semantic_label="Leaf vs Fruit", node_type="branch",
        parent_hash=stem2.id
    )
    tree.append(branch2)

    leaf1 = InferenceNode(
        "Show me what a leaf looks like. A terminated thought.",
        "A leaf node:\n\n1. Has no children (no descendants)\n"
        "2. Represents a terminal exploration\n3. No carryback data\n"
        "4. Still has full prompt/resolution/hash chain\n\n"
        "Use case: exploring an alternative that proved wrong or was abandoned.",
        model="qwen3.6:35b-a3b", semantic_label="Leaf Definition", node_type="leaf",
        parent_hash=branch2.id
    )
    tree.append(leaf1)

    # ── Continue stem ────────────────────────────────────────────────
    stem3 = InferenceNode(
        "Build a test sandbox that works alongside ai-chat-tree with branching support.",
        "Done:\n\n1. **InferenceNode** — supports node_type (stem/branch/leaf/fruit)\n"
        "2. **InferenceTree** — rooted tree with branch/fruit/leaf tracking\n"
        "3. **Carryback protocol** — fruits carry resolved info back to stem\n"
        "4. **Multi-view composer** — stem view + branch view + tree diagram\n"
        "5. **All cryptographic chains intact**\n\n"
        "The sandbox demonstrates everything.",
        model="qwen3.6:35b-a3b", semantic_label="Sandbox Build", node_type="stem",
        parent_hash=stem2.id
    )
    tree.append(stem3)

    tree._close()
    return tree


# ─── Main ─────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("=== Inference Tree Sandbox ===\n")

    # Simulate a branching session
    tree = simulate_tree_session()
    print(f"[+] Tree built: {len(tree.nodes_by_id)} nodes")
    print(f"[+] Roots: {len(tree.roots)}")
    
    # Verify and compose
    verified = tree.verify_tree()
    print(f"[+] Tree verified: {verified}")
    
    # Compose and write all views
    composer = TreeComposer(tree)
    stem_nodes = composer._read_stem()
    print(f"[+] Stem nodes: {len(stem_nodes)}")
    print(f"[+] Branches: {len(tree.find_branches())}")
    print(f"[+] Fruits: {len(tree.find_fruits())}")
    print(f"[+] Leaves: {len(tree.find_leaves())}")
    
    paths = composer.write_to_file("Inference Tree Sandbox Demo")
    print(f"\n[+] Stem view: {paths['stem']}")
    print(f"[+] Branch view: {paths['branch']}")
    print(f"[+] Diagram: {paths['diagram']}")

    # Print tree diagram
    print("\n--- VISUAL TREE ---")
    print(tree.render_diagram(is_root=True))
    print()

    # Print leaf/fruit info
    print("--- LEAVES ---")
    for leaf in tree.find_leaves():
        print(f"  {leaf.id[:16]}... ({leaf.semantic_label})")

    print("\n--- FRUITS ---")
    for fruit in tree.find_fruits():
        print(f"  {fruit.id[:16]}... ({fruit.semantic_label})")
        if fruit.info_carryback:
            for k, v in fruit.info_carryback.items():
                print(f"    {k}: {v}")

    # Print first 100 lines of stem view
    print("\n--- STEM VIEW (first 100 lines) ---")
    print(paths['stem'].read_text()[:2500])

    print("=" * 55)
    print("Tree sandbox complete.")
    print("[+] samples/StemView-*.md    — linear backbone")
    print("[+] samples/BranchView-*.md  — branches + fruits + leaves")
    print("[+] samples/TreeDiagram-*    — visual tree diagram")
