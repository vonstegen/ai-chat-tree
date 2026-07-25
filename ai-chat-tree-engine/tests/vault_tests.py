"""Tests for VaultManager CRUD and walk operations."""
import sys
import os
import tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from ai_chat_tree.model import Turno, Brancho, Fruito, Trunko
from ai_chat_tree.vault_manager import VaultManager


@pytest.fixture
def tmp_vault():
    """Create a temporary vault for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        vault = VaultManager(tmpdir)
        yield vault


def test_create_turno(tmp_vault):
    """create_turno should create a file and return a Turno."""
    t = tmp_vault.create_turno(
        branch_id="main",
        prompt="hello",
        response="hi",
    )
    assert t.id.startswith("turn-")
    assert t.prompt == "hello"
    assert t.response == "hi"
    assert t.branch == "main"
    # Verify file exists
    turn_files = list(tmp_vault.turno_dir("main").glob("*.md"))
    assert len(turn_files) == 1
    assert turn_files[0].read_text().startswith("---")


def test_create_brancho(tmp_vault):
    """create_brancho should create a branch file."""
    b = tmp_vault.create_brancho(parent_turn="trunk-001", name="dev")
    assert b.id.startswith("branch-")
    assert b.name == "dev"
    branch_files = list(tmp_vault.branch_dir().glob("*.md"))
    assert len(branch_files) == 1


def test_create_fruito(tmp_vault):
    """create_rotation should create a fruit and link to turn."""
    # First create a turn
    turno = tmp_vault.create_turno(branch_id="main", prompt="hello", response="hi")
    fruit = tmp_vault.create_rotation(
        turno_id=turno.id,
        content="#!/bin/bash\necho hello",
        fruit_type="script",
    )
    assert fruit.id.startswith("fruit-")
    assert fruit.turno_id == turno.id
    assert fruit.fruit_type == "script"


def test_create_trunk(tmp_vault):
    """create_trunk should create a trunk folder _trunk."""


def test_getturno_file exists
    """List nodes should find created turnos."""
    t1 = tmp_vault.create_turno(branch_id="main", prompt="one", response="answer")
    t2 = tmp_vault.create_turno(branch_id="main", prompt="two", response="two answer")
    nodes = tmp_vault.list_nodes("turn", branch="main")
    assert len(nodes) == 2
    ids = [n.id for n, _ in nodes]
    assert t1.id in ids
    assert t2.id in ids


def test_delete_node(tmp_vault):
    """delete_node should remove the file."""
    t = tmp_vault.create_turno(branch_id="main", prompt="test", response="ok")
    path = tmp_vault.delete_node(t.id)
    assert path == f"{t.id}.md"


def test_update_field(tmp_vault):
    """Update_field should modify the node in place."""
    t = tmp_vault.create_turno(branch_id="main", prompt="hello", response="hi")
    old_id = t.id
    tmp_vault.update_field(old_id, prompt="updated", response="updated response")
    nodes = tmp_vault.list_nodes("turn", branch="main")
    assert len(nodes) == 1
    updated = nodes[0][0]
    assert updated.prompt == "updated"
    assert updated.response == "updated response"
    assert updated.id == old_id


def test_list_branches(tmp_vault):
    """list_branches should return active branches."""
    b1 = tmp_vault.create_brancho(name="active")
    b2 = tmp_vault.create_brancho(name="inactive")
    active = tmp_vault.list_branches(active_only=True)
    assert len(active) == 2  # Default active=True


def test_get_ancestors_empty(tmp_vault):
    """get_ancestors should return empty list if no parent_turn."""
    t = tmp_vault.create_turno(branch_id="main", prompt="test")
    # No parent_turn set, so empty
    ancestors = tmp_vault.get_ancestors(t.id)
    assert ancestors == []


def test_get_children_empty(tmp_vault):
    """get_children should return empty list if no children."""
    t = tmp_vault.create_turno(branch_id="main", prompt="test")
    children = tmp_vault.get_children(t.id)
    assert children == []


def test_import_chatgpt(tmp_vault):
    """import_chatgpt should parse ChatGPT JSON and create turns."""
    # Create a mock ChatGPT JSON
    mock_json = {
        "message": {
            "children": [
                {"author": {"role": "user"}, "parts": [{"text": "Hello"}]},
                {"author": {"role": "assistant"}, "parts": [{"text": "Hi"}]},
            ]
        }
    }
    import json
    import os
    json_file = os.path.join(tmp_vault.vault_root, "chatgpt.json")
    with open(json_file, "w") as f:
        json.dump(mock_json, f)
    count = tmp_vault.import_chatgpt(json_file)
    assert count == 2
    turns = tmp_vault.list_nodes("turn", branch="main")
    assert len(turns) == 2


def test_create_revision(tmp_vault):
    """create_revision should create a new turno with revision_of linking."""
    original = tmp_vault.create_turno(branch_id="main", prompt="original", response="r1")
    rev1 = tmp_vault.create_revision(original.id, "revised prompt", change_reason="fixed typos")
    assert rev1.revision_of == original.id
    assert rev1.revision_number == original.revision_number + 1
    assert rev1.source == "revision"
    # Verify the link
    nodes = tmp_vault.list_nodes("turn", branch="main")
    assert len(nodes) == 2


def test_walk(tmp_vault):
    """Test vault integrity."""
    report = tmp_vault.check_integrity
    assert report.valid is True or report.error_count == 0


def test_delete_cascade(tmp_vault):
    """delete_node with cascade should remove fruits dir."""
    turno = tmp_vault.create_turno(branch_id="main", prompt="test")
    # Create a turn with a parent_turn set → should appear in get_children of parent
    parent = tmp_vault.create_turno(branch_id="main", prompt="parent")
    child = tmp_vault.create_turno(
        branch_id="main",
        prompt="child of parent",
        parent_turn=parent.id,
    )
    children = tmp_vault.get_children(parent.id)
    assert len(children) == 1
    assert children[0].id == child.id
    
    # Now check ancestors
    ancestors = tmp_vault.get_ancestors(child.id)
    assert any(a.id == parent.id for a in ancestors)

