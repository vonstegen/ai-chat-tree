"""CLI entry point for ai-chat-tree-engine.

Usage:
    act create --branch main --prompt "hello"        # create turn
    act branch --name dev --parent-turn Turn-001     # create branch
    act fruit --turn Turn-001 --type script          # attach fruit
    act walk --turn Turn-001 --mode ancestors        # ancestry
    act walk --turn trunk-001 --mode children        # children
    act integrity                                    # link integrity check
    act embed --turn Turn-001                        # generate + store embeddings

    act dry-run create --turn Turn-001              # validate without writing
"""
from __future__ import annotations

import argparse
import json
import sys
import os
from pathlib import Path

# Add engine to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from ai_chat_tree.vault_manager import VaultManager
from ai_chat_tree.vectors import VectorStore
from ai_chat_tree.model import Turno, Brancho, Fruito, Trunko, Node


VAULT_DEFAULT = os.path.expanduser("~/.local/share/ai-chat-tree/vault")


def _get_vault(args: argparse.Namespace) -> VaultManager:
    """Get VaultManager from args."""
    return VaultManager(args.vault or VAULT_DEFAULT)


def _get_vectors(vault: VaultManager) -> VectorStore:
    """Get VectorStore from vault config."""
    db_path = os.path.join(str(vault.vault_root), "vector_store.db")
    return VectorStore(db_path)


# ─── Create Commands ────────────────────────────────

def cmd_create(args: argparse.Namespace) -> None:
    """Create a new turn."""
    vault = _get_vault(args)
    dry_run = getattr(args, 'dry_run', False)
    turno = vault.create_turno(
        branch_id=args.branch,
        prompt=args.prompt or "",
        response=args.response or "",
        model=args.model or "default",
        source=args.source or "manual",
        success_score=args.score or 0.0,
        tags=_parse_tags(args.tags) if args.tags else [],
        parent_turn=getattr(args, 'parent_turn', None),
        dry_run=dry_run,
    )
    if dry_run:
        print(f"[DRY RUN] Would create turn: {turno.id}")
        return
    print(f"Created turn: {turno.id}")
    
    # Auto-embed if enabled
    if not getattr(args, 'no_embed', False):
        vectors = _get_vectors(vault)
        vectors.ingest_turno(turno)
        print(f"Embedded turn {turno.id}")


def cmd_branch(args: argparse.Namespace) -> None:
    """Create a new branch."""
    vault = _get_vault(args)
    parent = getattr(args, 'parent_turn', 'trunk-001') or 'trunk-001'
    dry_run = getattr(args, 'dry_run', False)
    branch = vault.create_brancho(
        parent_turn=parent,
        name=args.name,
        dry_run=dry_run,
    )
    if dry_run:
        print(f"[DRY RUN] Would create branch: {branch.id} ({branch.name})")
        return
    print(f"Created branch: {branch.id}")


def cmd_fruit(args: argparse.Namespace) -> None:
    """Attach a fruit to a turn."""
    vault = _get_vault(args)
    content = args.content or ""
    content_path = getattr(args, 'file', None)
    if content_path:
        content = Path(content_path).read_text()
    dry_run = getattr(args, 'dry_run', False)
    
    fruit = vault.create_rotation(
        turno_id=args.turn,
        content=content,
        fruit_type=args.type or "other",
        notes=getattr(args, 'notes', '') or "",
        dry_run=dry_run,
    )
    if dry_run:
        print(f"[DRY RUN] Would create fruit: {fruit.id} attached to {fruit.turno_id}")
        return
    print(f"Created fruit: {fruit.id}")


def cmd_rotate(args: argparse.Namespace) -> None:
    """Create a rotation (revision) of a turn."""
    vault = _get_vault(args)
    dry_run = getattr(args, 'dry_run', False)
    rotation = vault.create_revision(
        turno_id=args.turn,
        new_prompt=args.prompt or "rotated prompt",
        change_reason=getattr(args, 'reason', '') or "automatic rotation",
        model=getattr(args, 'model', 'default') or "default",
        dry_run=dry_run,
    )
    if dry_run:
        print(f"[DRY RUN] Would create rotation: {rotation.id} for {rotation.revision_of}")
        return
    print(f"Created rotation: {rotation.id}")


def cmd_trunk(args: argparse.Namespace) -> None:
    """Create a new trunk."""
    vault = _get_vault(args)
    dry_run = getattr(args, 'dry_run', False)
    trunk = vault.create_trunk(
        name=args.name,
        description=getattr(args, 'description', '') or "",
        dry_run=dry_run,
    )
    if dry_run:
        print(f"[DRY RUN] Would create trunk: {trunk.id} ({trunk.name})")
        return
    print(f"Created trunk: {trunk.id}")


# ─── List Commands ──────────────────────────────────

def cmd_list(args: argparse.Namespace) -> None:
    """List nodes."""
    vault = _get_vault(args)
    node_type = getattr(args, 'type', 'turn') or 'turn'
    nodes = vault.list_nodes(node_type, limit=getattr(args, 'limit', 50))
    if nodes:
        print(f"\n{len(nodes)} {node_type}s found:\n")
        for node, path in nodes:
            print(f"  {node.node_type:8s}  {node.node_id:30s}  {path}")
    else:
        print(f"No {node_type}s found.")


def cmd_turns(args: argparse.Namespace) -> None:
    """Alias for list turns."""
    cmd_list(argparse.Namespace(type="turn", limit=getattr(args, 'limit', 50), vault=args.vault))


def cmd_branches(args: argparse.Namespace) -> None:
    """Alias for list branches."""
    vault = _get_vault(args)
    branches = vault.list_branches()
    print(f"\n{len(branches)} branches found:\n")
    for b in branches:
        status = "active" if b.active else "inactive"
        print(f"  {b.id:30s}  {b.name:20s}  ({status})")


# ─── Walk Commands ────────────────────────────────────

def cmd_walk(args: argparse.Namespace) -> None:
    """Walk ancestry or children of a turn."""
    vault = _get_vault(args)
    mode = args.mode
    turn_id = args.turn
    
    if mode == "ancestors":
        ancestors = vault.get_ancestors(turn_id)
        print(f"\nAncestors of {turn_id}:\n")
        for a in ancestors:
            print(f"  {a.id:30s}  {a.to_markdown()[:80]}...")
    elif mode == "children":
        children = vault.get_children(turn_id)
        print(f"\nChildren of {turn_id}:\n")
        for c in children:
            print(f"  {c.id:30s}  {c.to_markdown()[:80]}...")
    else:
        print(f"Unknown walk mode: {mode}")


# ─── Other Commands ──────────────────────────────────

def cmd_integrity(args: argparse.Namespace) -> None:
    """Run link integrity check."""
    vault = _get_vault(args)
    report = _get_integrity_report(vault)
    
    if report.valid:
        print(f"✓ Vault integrity check passed ({report.node_count} nodes)")
    else:
        print(f"✗ Found {report.error_count} errors, {report.warning_count} warnings:")
        for issue in report.issues:
            marker = "✗" if issue.severity == "error" else "⚠"
            print(f"  {marker} [{issue.severity.upper()}] {issue.entity_type} {issue.entity_id}")
            print(f"    {issue.issue}")
            if issue.suggestion:
                print(f"    → {issue.suggestion}")


def cmd_embed(args: argparse.Namespace) -> None:
    """Generate and store embeddings for a turn."""
    vault = _get_vault(args)
    vectors = _get_vectors(vault)
    
    turno = None
    for node, _path in vault.list_nodes("turn"):
        if node.id == args.turn:
            turno = node
            break
    if not turno:
        print(f"Turn {args.turn} not found")
        return
    
    count = vectors.ingest_turno(turno)
    print(f"Embedded {count} chunks for turn {turno.id}")


def cmd_search(args: argparse.Namespace) -> None:
    """Search turns by embedding similarity."""
    vault = _get_vault(args)
    vectors = _get_vectors(vault)
    
    results = vectors.search(args.query, k=getattr(args, 'k', 12))
    if not results:
        print("No results found.")
        return
    
    print(f"\nSearch results for '{args.query}':\n")
    for turno, score in results:
        print(f"  [{score:.3f}] {turno.id}  {turno.prompt[:60]}...")


def cmd_delete(args: argparse.Namespace) -> None:
    """Delete a node."""
    vault = _get_vault(args)
    cascade = getattr(args, 'cascade', True)
    dry_run = getattr(args, 'dry_run', False)
    path = vault.delete_node(args.id, cascade=cascade, dry_run=dry_run)
    if dry_run:
        print(f"[DRY RUN] Would delete {args.id} ({path})")
        return
    print(f"Deleted {args.id} ({path})")


def cmd_dry_run(args: argparse.Namespace) -> None:
    """Validate a turn without writing it."""
    vault = _get_vault(args)
    turno = Turno(
        id="dry-run-test",
        branch=args.branch,
        prompt=args.prompt or "",
        response=args.response or "",
        model=args.model or "default",
    )
    
    report = _get_integrity_report(vault)
    
    print(f"✓ Dry-run validation:")
    print(f"  Turn ID: {turno.id}")
    print(f"  Branch: {turno.branch}")
    print(f"  Model: {turno.model}")
    print(f"  Prompt length: {len(turno.prompt)} chars")
    print(f"  Response length: {len(turno.response)} chars")
    print(f"\nVault integrity: {report.node_count} nodes, {report.error_count} errors")


def cmd_import(args: argparse.Namespace) -> None:
    """Import conversation data."""
    vault = _get_vault(args)
    dry_run = getattr(args, 'dry_run', False)
    source = getattr(args, 'source', 'chatgpt')
    json_path = args.file
    
    if source == "chatgpt":
        count = vault.import_chatgpt(json_path)
    elif source == "claude":
        count = vault.import_claude(json_path)
    else:
        print(f"Unknown source: {source}")
        return
    
    if dry_run:
        print(f"[DRY RUN] Would import {count} turns from {source} data")
        return
    print(f"Imported {count} turns from {source} data")


def cmd_init(args: argparse.Namespace) -> None:
    """Initialize a fresh vault."""
    vault_path = args.vault or VAULT_DEFAULT
    dry_run = getattr(args, 'dry_run', False)
    vault = VaultManager(vault_path)
    trunk = vault.create_trunk(
        name=getattr(args, 'trunk_name', 'default') or 'default',
        dry_run=dry_run,
    )
    if dry_run:
        print(f"[DRY RUN] Would initialize vault at {vault_path}")
        print(f"[DRY RUN] Would create trunk: {trunk.id} ({trunk.name})")
        return
    print(f"Initialized vault at {vault_path}")
    print(f"Created trunk: {trunk.id}")


def cmd_health(args: argparse.Namespace) -> None:
    """Print vault status."""
    vault = _get_vault(args)
    print(f"vault_root: {vault.vault_root}")
    turns = vault.list_nodes("turn")
    branches = vault.list_branches()
    trunks = vault.list_nodes("trunk")
    print(f"  turns: {len(turns)}")
    print(f"  branches: {len(branches)}")
    print(f"  trunks: {len(trunks)}")


# ─── Engine Serve ────────

def cmd_serve(args: argparse.Namespace) -> None:
    """Start the FastAPI HTTP server."""
    vault_root = args.vault or VAULT_DEFAULT
    host = getattr(args, 'host', '0.0.0.0')
    port = args.port
    import threading, time, requests

    def run_server():
        from ai_chat_tree.engine import create_app
        import uvicorn
        app = create_app(vault_root)
        uvicorn.run(app, host=host, port=port, log_level='info')

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    print(f"Starting AI Chat Tree Engine on {host}:{port}...")

    # Wait for server to be ready
    for i in range(30):
        time.sleep(0.5)
        try:
            r = requests.get(f"http://localhost:{port}/healthz", timeout=1)
            if r.status_code == 200:
                print(f"✓ Server ready at http://localhost:{port}")
                print(f"  Vault: {vault_root}")
                return
        except requests.ConnectionError:
            continue
        except requests.exceptions.RequestException:
            continue

    print("⚠ Server may not be ready yet. Check logs.")



# ─── Main ────────────────────────────────────────────────────────────

def _parse_tags(tags_str: str) -> list[str]:
    """Parse comma-separated tags into a list."""
    return [t.strip() for t in tags_str.split(",") if t.strip()]


def _get_integrity_report(vault) -> object:
    """Get integrity report with minimal import."""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from ai_chat_tree.validation import check_integrity
    return check_integrity(vault)


def main() -> None:
    """Main CLI parser."""
    parser = argparse.ArgumentParser(
        prog="act",
        description="AI Chat Tree CLI — manage turns, branches, and trunks",
        add_help=True,
    )
    parser.add_argument('--vault', '-v', default=VAULT_DEFAULT,
                        help='Path to the vault directory')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # ── create ──
    cmd_create_parser = subparsers.add_parser('create', help='Create a new turn')
    cmd_create_parser.add_argument('--branch', '-b', required=True)
    cmd_create_parser.add_argument('--prompt', '-p', required=True)
    cmd_create_parser.add_argument('--response', '-r', default='')
    cmd_create_parser.add_argument('--model', '-m', default='default')
    cmd_create_parser.add_argument('--score', '-s', type=float, default=0.0)
    cmd_create_parser.add_argument('--tags', '-t', default='')
    cmd_create_parser.add_argument('--source', default='manual')
    cmd_create_parser.add_argument('--no-embed', action='store_true')
    cmd_create_parser.add_argument('--parent-turn', dest='parent_turn', default=None)
    cmd_create_parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False)
    cmd_create_parser.set_defaults(func=cmd_create)

    # ── branch ──
    cmd_branch_parser = subparsers.add_parser('branch', help='Create a new branch')
    cmd_branch_parser.add_argument('--name', '-n', required=True)
    cmd_branch_parser.add_argument('--parent-turn', dest='parent_turn', default='trunk-001')
    cmd_branch_parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False)
    cmd_branch_parser.set_defaults(func=cmd_branch)

    # ── fruit ──
    cmd_fruit_parser = subparsers.add_parser('fruit', help='Attach a fruit to a turn')
    cmd_fruit_parser.add_argument('--turn', required=True)
    cmd_fruit_parser.add_argument('--content', '-c', default='')
    cmd_fruit_parser.add_argument('--file', '-f', default=None)
    cmd_fruit_parser.add_argument('--type', dest='type', default='other')
    cmd_fruit_parser.add_argument('--notes', '-n', default='')
    cmd_fruit_parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False)
    cmd_fruit_parser.set_defaults(func=cmd_fruit)

    # ── rotate ──
    cmd_rotate_parser = subparsers.add_parser('rotate', help='Create a revision/rotation of a turn')
    cmd_rotate_parser.add_argument('--turn', required=True)
    cmd_rotate_parser.add_argument('--prompt', '-p', required=True)
    cmd_rotate_parser.add_argument('--reason', default='automatic rotation')
    cmd_rotate_parser.add_argument('--model', default='default')
    cmd_rotate_parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False)
    cmd_rotate_parser.set_defaults(func=cmd_rotate)

    # ── trunk ──
    cmd_trunk_parser = subparsers.add_parser('trunk', help='Create a new trunk')
    cmd_trunk_parser.add_argument('--name', '-n', required=True)
    cmd_trunk_parser.add_argument('--description', '-d', default='')
    cmd_trunk_parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False)
    cmd_trunk_parser.set_defaults(func=cmd_trunk)

    # ── list ──
    cmd_list_parser = subparsers.add_parser('list', help='List nodes')
    cmd_list_parser.add_argument('--type', dest='type', default='turn')
    cmd_list_parser.add_argument('--limit', '-l', type=int, default=50)
    cmd_list_parser.set_defaults(func=cmd_list)

    # ── turns ──
    cmd_turns_parser = subparsers.add_parser('turns', help='List turns')
    cmd_turns_parser.add_argument('--limit', '-l', type=int, default=50)
    cmd_turns_parser.set_defaults(func=cmd_turns)

    # ── branches ──
    cmd_branches_parser = subparsers.add_parser('branches', help='List branches')
    cmd_branches_parser.set_defaults(func=cmd_branches)

    # ── walk ──
    cmd_walk_parser = subparsers.add_parser('walk', help='Walk ancestry or children')
    cmd_walk_parser.add_argument('--turn', required=True)
    cmd_walk_parser.add_argument('--mode', required=True, choices=['ancestors', 'children'])
    cmd_walk_parser.set_defaults(func=cmd_walk)

    # ── integrity ──
    cmd_integrity_parser = subparsers.add_parser('integrity', help='Run link integrity check')
    cmd_integrity_parser.set_defaults(func=cmd_integrity)

    # ── embed ──
    cmd_embed_parser = subparsers.add_parser('embed', help='Generate embeddings for a turn')
    cmd_embed_parser.add_argument('--turn', required=True)
    cmd_embed_parser.set_defaults(func=cmd_embed)

    # ── search ──
    cmd_search_parser = subparsers.add_parser('search', help='Search turns by similarity')
    cmd_search_parser.add_argument('--query', '-q', required=True)
    cmd_search_parser.add_argument('--k', '-k', type=int, default=12)
    cmd_search_parser.set_defaults(func=cmd_search)

    # ── delete ──
    cmd_del_parser = subparsers.add_parser('delete', help='Delete a node')
    cmd_del_parser.add_argument('--id', required=True)
    cmd_del_parser.add_argument('--cascade', dest='cascade', action='store_true', default=True)
    cmd_del_parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False)
    cmd_del_parser.set_defaults(func=cmd_delete)

    # ── dry-run ──
    cmd_dry_parser = subparsers.add_parser('dry-run', help='Validate without writing')
    cmd_dry_parser.add_argument('--branch', '-b', required=True)
    cmd_dry_parser.add_argument('--prompt', '-p', default='')
    cmd_dry_parser.add_argument('--response', '-r', default='')
    cmd_dry_parser.add_argument('--model', '-m', default='default')
    cmd_dry_parser.set_defaults(func=cmd_dry_run)

    # ── init ──
    cmd_init_parser = subparsers.add_parser('init', help='Initialize a fresh vault')
    cmd_init_parser.add_argument('--trunk-name', dest='trunk_name', default='default')
    cmd_init_parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False)
    cmd_init_parser.set_defaults(func=cmd_init)

    # ── import ──
    cmd_import_parser = subparsers.add_parser('import', help='Import conversation data')
    cmd_import_parser.add_argument('--file', '-f', required=True)
    cmd_import_parser.add_argument('--source', '-s', required=True, choices=['chatgpt', 'claude'])
    cmd_import_parser.add_argument('--dry-run', dest='dry_run', action='store_true', default=False)
    cmd_import_parser.set_defaults(func=cmd_import)

    # ── health ──
    cmd_health_parser = subparsers.add_parser('health', help='Print vault status')
    cmd_health_parser.set_defaults(func=cmd_health)

    # ── serve ──
    cmd_serve_parser = subparsers.add_parser('serve', help='Start the FastAPI HTTP server on a port')
    cmd_serve_parser.add_argument('--host', '-H', default='0.0.0.0')
    cmd_serve_parser.add_argument('--port', '-p', type=int, default=8765)
    cmd_serve_parser.set_defaults(func=cmd_serve)

    args = parser.parse_args()

    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
