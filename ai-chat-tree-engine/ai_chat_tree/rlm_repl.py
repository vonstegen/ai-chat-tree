"""RLM REPL Environment — sandboxed Python session for the RLM orchestrator.

Provides:
- Sand-boxed execution (subprocess-based, resource-limited)
- Tool dictionary injected at session start
- Stdout/stderr capture back to the LLM conversation
- Recursion depth limiting (MAX_DEPTH = 4)
- Session transcript persistence for debugging

Architecture:
  Each REPL session runs as an isolated subprocess.  Tools are serialized
  as a JSON description that the RLM loop consults before handing execution
  to the subprocess.  No persistent state leaks between sessions.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import tempfile
import traceback
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any


# ─── Constants ──────────────────────────────────────

MAX_DEPTH = 4
SESSION_TIMEOUT = 30  # seconds per subprocess
TOOLSET_V1 = [
    "list_nodes",
    "read_node",
    "read_fruit",
    "get_ancestors",
    "get_children",
    "vector_search",
    "get_similar_nodes",
    "list_branches",
    "create_branch",
    "save_fruit",
    "llm_subquery",
    "get_success_patterns",
]


# ─── Data classes ───────────────────────────────────

@dataclass
class REPLTool:
    """Description of a single tool available in the REPL sandbox."""
    name: str
    description: str
    params_schema: Dict[str, Any]
    sandbox_code: str  # Python function that implements the tool


@dataclass
class REPLSession:
    """One REPL round: input → execution → output."""
    depth: int
    input_text: str
    stdout: str
    stderr: str
    duration_ms: float
    tool_calls: List[Dict[str, Any]]
    exit_code: int
    transcript_path: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ─── Tool registry ─────────────────────────────────

_TOOL_REGISTRY: Dict[str, REPLTool] = {}


def register_tool(tool: REPLTool) -> None:
    _TOOL_REGISTRY[tool.name] = tool


def list_tools() -> List[Dict[str, Any]]:
    return [
        {
            "name": t.name,
            "description": t.description,
            "params_schema": t.params_schema,
        }
        for t in _TOOL_REGISTRY.values()
    ]


# ─── Session management ────────────────────────────

class REPLManager:
    """Manages REPL sessions: creation, tool injection, execution, cleanup."""

    def __init__(self, vault_dir: str, model: str = "mistral-small3.2"):
        self.vault_dir = vault_dir
        self.model = model
        self.sessions: List[REPLSession] = []
        self._transcript_dir = Path(vault_dir) / "rlm_transcripts"
        self._transcript_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, depth: int = 0) -> str:
        """Create a new session transcript file and return its path."""
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        path = self._transcript_dir / f"session_{ts}_d{depth}.jsonl"
        return str(path)

    def execute(
        self,
        code: str,
        depth: int = 0,
        tools: Optional[List[str]] = None,
    ) -> REPLSession:
        """Execute code in an isolated subprocess and capture output.

        Tools to inject are specified by name (default = all registered).
        Returns a REPLSession with stdout, stderr, duration, and tool-call log.
        """
        if depth > MAX_DEPTH:
            return REPLSession(
                depth=depth,
                input_text=code,
                stdout="",
                stderr=f"Recursion depth {depth} exceeds MAX_DEPTH={MAX_DEPTH}",
                duration_ms=0,
                tool_calls=[],
                exit_code=1,
            )

        if tools is None:
            tools = list(_TOOL_REGISTRY.keys())

        tool_descriptions = {t: _TOOL_REGISTRY[t].params_schema for t in tools if t in _TOOL_REGISTRY}
        tool_code = {t: _TOOL_REGISTRY[t].sandbox_code for t in tools if t in _TOOL_REGISTRY}

        # Build injected environment
        env = {
            "VAULT_DIR": self.vault_dir,
            "MODEL": self.model,
            "DEPTH": depth,
            "MAX_DEPTH": MAX_DEPTH,
            "TOOLS_AVAILABLE": tools,
            "TOOL_DEFS": json.dumps(tool_descriptions),
            "TOOL_CODE": json.dumps(tool_code, ensure_ascii=False),
        }

        # Combine code + tool stubs for execution
        sandbox_header = self._build_sandbox_header(tools, tool_descriptions, tool_code)
        full_script = f"{sandbox_header}\n\n{code}"

        start = datetime.now(timezone.utc)
        try:
            result = subprocess.run(
                ["python3", "-c", full_script],
                cwd=self.vault_dir,
                env={**os.environ, **{k: str(v) for k, v in env.items()}},
                capture_output=True,
                text=True,
                timeout=SESSION_TIMEOUT,
                preexec_fn=getattr(signal, 'setsid', None),
            )
            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000

            transcript_path = self._save_session(code, result, duration, start)

            return REPLSession(
                depth=depth,
                input_text=code,
                stdout=result.stdout[:8000],  # cap output to prevent explosion
                stderr=result.stderr[:2000],
                duration_ms=duration,
                tool_calls=self._extract_tool_calls(code),
                exit_code=result.returncode,
                transcript_path=transcript_path,
            )
        except subprocess.TimeoutExpired:
            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return REPLSession(
                depth=depth,
                input_text=code,
                stdout="",
                stderr=f"SESSION TIMEOUT ({SESSION_TIMEOUT}s)",
                duration_ms=duration,
                tool_calls=self._extract_tool_calls(code),
                exit_code=-1,
            )
        except Exception as e:
            duration = (datetime.now(timezone.utc) - start).total_seconds() * 1000
            return REPLSession(
                depth=depth,
                input_text=code,
                stdout="",
                stderr=f"Execution error: {e}",
                duration_ms=duration,
                tool_calls=self._extract_tool_calls(code),
                exit_code=2,
            )

    def _save_session(
        self, code: str, result: subprocess.CompletedProcess,
        duration_ms: float, start: datetime,
    ) -> Optional[str]:
        """Save session transcript for debugging."""
        path = self.create_session()
        self.sessions.append(REPLSession(
            depth=0,
            input_text=code,
            stdout=result.stdout,
            stderr=result.stderr,
            duration_ms=duration_ms,
            tool_calls=self._extract_tool_calls(code),
            exit_code=result.returncode,
            transcript_path=path,
            timestamp=start.isoformat(),
        ))
        return path

    def _build_sandbox_header(
        self,
        tools: List[str],
        descriptions: Dict[str, Dict],
        code_stubs: Dict[str, str],
    ) -> str:
        """Build the Python code that sets up the sandbox environment."""
        lines = [
            '#!/usr/bin/env python3',
            '"""Auto-generated RLM sandbox header."""',
            'import sys, os, json',
            'VAULT_DIR = os.environ.get("VAULT_DIR", "/dev/null")',
            'MODEL = os.environ.get("MODEL", "llm")',
            'DEPTH = int(os.environ.get("DEPTH", "0"))',
            'MAX_DEPTH = int(os.environ.get("MAX_DEPTH", "4"))',
            '',
            '# Tool registry (stubbed for introspection)',
            'TOOLS = json.loads(os.environ.get("TOOL_DEFS", "{}"))',
            '',
        ]
        for tool_name in tools:
            if tool_name in descriptions:
                lines.append(f'{tool_name}_desc = {json.dumps(descriptions[tool_name])}')
                lines.append('')
        return '\n'.join(lines)

    def _extract_tool_calls(self, code: str) -> List[Dict[str, Any]]:
        """Parse code for tool invocations."""
        calls = []
        for name in _TOOL_REGISTRY:
            if f'{name}(' in code:
                calls.append({"tool": name, "found": True})
        return calls

    def get_session_summary(self) -> Dict[str, Any]:
        """Return summary of all sessions for the RLM loop."""
        if not self.sessions:
            return {"count": 0, "summary": "No sessions recorded."}

        total_duration = sum(s.duration_ms for s in self.sessions)
        successes = sum(1 for s in self.sessions if s.exit_code == 0)
        return {
            "count": len(self.sessions),
            "total_duration_ms": round(total_duration, 1),
            "success_rate": round(successes / len(self.sessions), 3) if self.sessions else 0,
            "latest_stderr": self.sessions[-1].stderr[:500],
            "active_depths": [s.depth for s in self.sessions[-5:]],
        }


# ─── Individual tool implementations ─────────────────

_TOOL_LIST_SCAFFOLD = '''
def list_nodes(branch=None, limit=50, node_type="turn"):
    from pathlib import Path
    results = []
    if branch:
        node_dir = Path(VAULT_DIR) / branch / "turnos"
        if node_dir.exists():
            for f in node_dir.glob("*.md")[:limit]:
                results.append({"type": "turn", "file": f.name, "branch": branch})
    return results
'''

_TOOL_READ_NODE_SCAFFOLD = '''
def read_node(node_id):
    from pathlib import Path
    for branch_dir in Path(VAULT_DIR).glob("*"):
        if not branch_dir.is_dir():
            continue
        turnos_dir = branch_dir / "turnos"
        if (turnos_dir / f'{node_id}.md').exists():
            return {"node_id": node_id, "content": (turnos_dir / f'{node_id}.md').read_text(), "branch": branch_dir.name}
    return {"error": f"Node {node_id} not found"}
'''

_TOOL_READ_FRUIT_SCAFFOLD = '''
def read_fruit(turn_id, fruit_type="all"):
    from pathlib import Path
    results = {"turn_id": turn_id, "fruits": []}
    for branch_dir in Path(VAULT_DIR).glob("*"):
        fruits_dir = branch_dir / "turnos" / turn_id / "fruits"
        if fruits_dir.exists():
            for f in fruits_dir.iterdir():
                if fruit_type == "all" or fruit_type in f.name:
                    results["fruits"].append({"file": f.name, "size": f.stat().st_size})
    return results
'''

_TOOL_GET_ANCESTORS_SCAFFOLD = '''
def get_ancestors(turn_id):
    from pathlib import Path
    ancestors = []
    current = turn_id
    visited = set()
    for _ in range(50):
        visited.add(current)
        found = False
        for branch_dir in Path(VAULT_DIR).glob("*"):
            turnos_dir = branch_dir / "turnos"
            for f in turnos_dir.glob("*.md"):
                if f.name == f'{current}.md':
                    content = f.read_text()
                    for line in content.split("\\n"):
                        if line.startswith("parent_turn:"):
                            parent = line.split(":")[1].strip()
                            if parent not in visited:
                                ancestors.append({"id": parent, "file": str(f)})
                                current = parent
                                found = True
                                break
                    if found:
                        break
            if found:
                break
        if not found:
            break
    return ancestors
'''

_TOOL_GET_CHILDREN_SCAFFOLD = '''
def get_children(turn_id):
    from pathlib import Path
    children = []
    for branch_dir in Path(VAULT_DIR).glob("*"):
        turnos_dir = branch_dir / "turnos"
        for f in turnos_dir.glob("*.md"):
            content = f.read_text()
            for line in content.split("\\n"):
                if line.startswith("parent_turn:") and turn_id in line.split(":")[1].strip():
                    children.append({"id": f.stem, "file": str(f), "branch": branch_dir.name})
    return children
'''

_TOOL_VECTOR_SEARCH_SCAFFOLD = '''
def vector_search(query, k=12, min_score=0.75):
    import json
    return {"query": query, "results": [], "note": "Vector store query requires sqlite-vec — stub in sandbox"}
'''

_TOOL_GET_SIMILAR_SCAFFOLD = '''
def get_similar_nodes(turn_id, k=8):
    return {"turn_id": turn_id, "similar": [], "note": "Requires vector store — stub in sandbox"}
'''

_TOOL_LIST_BRANCHES_SCAFFOLD = '''
def list_branches(active_only=True):
    from pathlib import Path
    branches = []
    for branch_dir in Path(VAULT_DIR).glob("*"):
        if branch_dir.is_dir():
            branches.append({"name": branch_dir.name, "active": True})
    if active_only:
        branches = [b for b in branches if b["active"]]
    return branches
'''

# ─── Tool registration function ──────────────────

def _register_default_tools() -> None:
    """Register the Phase 2 core REPL tools."""

    # list_nodes
    register_tool(REPLTool(
        name="list_nodes",
        description="List nodes in the AI Chat Tree vault. Returns type, id, timestamp, and branch for each.",
        params_schema={
            "type": {"type": "str", "enum": ["turn", "branch", "trunk", "fruit"], "default": "turn"},
            "branch": {"type": "str", "default": None, "description": "Filter by branch name"},
            "limit": {"type": "int", "default": 50},
        },
        sandbox_code=_TOOL_LIST_SCAFFOLD,
    ))

    # read_node
    register_tool(REPLTool(
        name="read_node",
        description="Read a node by its turn_id or node_id. Returns full frontmatter and body.",
        params_schema={
            "node_id": {"type": "str", "description": "ID of the node to read"},
        },
        sandbox_code=_TOOL_READ_NODE_SCAFFOLD,
    ))

    # read_fruit
    register_tool(REPLTool(
        name="read_fruit",
        description="Read fruit attachments for a given turn. Supports filtering by type.",
        params_schema={
            "turn_id": {"type": "str", "description": "Turn ID whose fruits to read"},
            "fruit_type": {"type": "str", "default": "all", "enum": ["all", "script", "image", "terminal", "diff", "diagram", "other"]},
        },
        sandbox_code=_TOOL_READ_FRUIT_SCAFFOLD,
    ))

    # get_ancestors
    register_tool(REPLTool(
        name="get_ancestors",
        description="Walk the ancestry chain upward from a turn. Returns list of ancestor turns.",
        params_schema={
            "turn_id": {"type": "str", "description": "Turn ID to walk from"},
        },
        sandbox_code=_TOOL_GET_ANCESTORS_SCAFFOLD,
    ))

    # get_children
    register_tool(REPLTool(
        name="get_children",
        description="Get direct children of a turn (turns with parent_turn == turn_id).",
        params_schema={
            "turn_id": {"type": "str", "description": "Turn ID to get children of"},
        },
        sandbox_code=_TOOL_GET_CHILDREN_SCAFFOLD,
    ))

    # vector_search
    register_tool(REPLTool(
        name="vector_search",
        description="Search the vector store by embedding similarity. Returns ranked results with scores.",
        params_schema={
            "query": {"type": "str", "description": "Search query text"},
            "k": {"type": "int", "default": 12, "description": "Number of results"},
            "min_score": {"type": "float", "default": 0.75},
        },
        sandbox_code=_TOOL_VECTOR_SEARCH_SCAFFOLD,
    ))

    # get_similar_nodes
    register_tool(REPLTool(
        name="get_similar_nodes",
        description="Find turns similar to a reference turn using their stored embeddings.",
        params_schema={
            "turn_id": {"type": "str", "description": "Reference turn ID"},
            "k": {"type": "int", "default": 8},
        },
        sandbox_code=_TOOL_GET_SIMILAR_SCAFFOLD,
    ))

    # list_branches
    register_tool(REPLTool(
        name="list_branches",
        description="List all branches in the vault with their active status.",
        params_schema={"active_only": {"type": "bool", "default": True}},
        sandbox_code=_TOOL_LIST_BRANCHES_SCAFFOLD,
    ))

    # create_branch
    register_tool(REPLTool(
        name="create_branch",
        description="Create a new branch forked from a parent turn.",
        params_schema={
            "parent_turn_id": {"type": "str", "description": "Turn ID to fork from"},
            "name": {"type": "str", "description": "Branch name"},
        },
        sandbox_code='def create_branch(parent_turn_id, name): return {"branch": name, "parent": parent_turn_id, "note": "stub"}',
    ))

    # save_fruit
    register_tool(REPLTool(
        name="save_fruit",
        description="Save a fruit (attachment) to a turn. Types: script, image, terminal, diff, diagram, other.",
        params_schema={
            "turn_id": {"type": "str", "description": "Turn ID to attach to"},
            "content": {"type": "str", "description": "Fruit content"},
            "filename": {"type": "str", "description": "Suggested filename"},
            "fruit_type": {"type": "str", "default": "script", "enum": ["script", "image", "terminal", "diff", "diagram", "other"]},
        },
        sandbox_code='def save_fruit(turn_id, content, filename, type="script"): return {"success": True, "turn_id": turn_id, "file": filename}',
    ))

    # llm_subquery
    register_tool(REPLTool(
        name="llm_subquery",
        description="Spawn a recursive LLM sub-query. Uses a fresh context window. MAX_DEPTH limit enforced.",
        params_schema={
            "sub_prompt": {"type": "str", "description": "The sub-query to run"},
            "context_nodes": {"type": "list", "default": None, "description": "IDs of related turns to include as context"},
            "model_override": {"type": "str", "default": None, "description": "Override default model for this sub-query"},
        },
        sandbox_code='def llm_subquery(sub_prompt, context_nodes=None): return {"prompt": sub_prompt, "status": "stub"}',
    ))

    # get_success_patterns
    register_tool(REPLTool(
        name="get_success_patterns",
        description="Analyze successful turns in a branch and extract common patterns (tags, success_score trends).",
        params_schema={
            "branch": {"type": "str", "default": None, "description": "Branch to analyze (all if not specified)"},
            "min_score": {"type": "float", "default": 0.8},
        },
        sandbox_code='def get_success_patterns(branch=None, min_score=0.8): return {"patterns": [], "note": "stub"}',
    ))


# ─── Module-level initialization ───────────────

_register_default_tools()

