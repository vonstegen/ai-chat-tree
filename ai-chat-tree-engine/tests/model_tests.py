"""Tests for Core Data Model (Turno, Brancho, Fruito, Trunko)."""
import sys
import os
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import json
from dataclasses import asdict

from ai_chat_tree.model import Turno, Brancho, Fruito, Trunko, Node, new_id


# ─── Test: new_id format ───────────────────────

def test_new_id_format():
    """IDs should follow format: prefix-YYYYMMDD-HHMMSS-XXXX"""
    nid = new_id("test")
    assert nid.startswith("test-")
    # Check structure: test-20240101-120000-AB
    parts = nid.split("-")
    assert len(parts) == 3


def test_new_id_uniqueness():
    """Multiple IDs should be unique."""
    ids = [new_id("x") for _ in range(100)]
    assert len(set(ids)) == 100


# ─── Test: Turno to_markdown/from_markdown roundtrip ────────

def test_turno_roundtrip():
    """Turno should serialize and deserialize correctly."""
    original = Turno(
        id="turn-001",
        branch="main",
        model="default",
        prompt="Hello",
        response="Hi there!",
        tags=["greeting", "test"],
        success_score=0.8,
        parent_turn="trunk-001",
    )
    md = original.to_markdown()
    restored = Turno.from_markdown(md)

    assert restored.id == "turn-001"
    assert restored.branch == "main"
    assert restored.model == "default"
    assert restored.prompt == "Hello"
    assert restored.response == "Hi there!"
    assert "greeting" in restored.tags
    assert "test" in restored.tags
    assert restored.success_score == 0.8
    assert restored.parent_turn == "trunk-001"
    assert restored.node_type == "turn"


def test_turno_empty_fields():
    """Turno should handle empty/null fields gracefully."""
    t = Turno(id="t1", branch="b1")
    md = t.to_markdown()
    r = Turno.from_markdown(md)
    assert r.id == "t1"
    assert r.prompt == ""
    assert r.response == ""
    assert r.tags == []


# ─── Test: Brancho to_markdown/from_markdown roundtrip ────────

def test_brancho_roundtrip():
    """Brancho should serialize and deserialize correctly."""
    original = Brancho(
        id="branch-001",
        name="dev",
        parent_turn="trunk-001",
        description="Development branch",
        active=True,
    )
    md = original.to_markdown()
    restored = Brancho.from_markdown(md)

    assert restored.id == "branch-001"
    assert restored.name == "dev"
    assert restored.parent_turn == "trunk-001"
    assert restored.description == "Development branch"
    assert restored.active is True
    assert restored.node_type == "branch"


def test_brancho_inactive():
    """Brancho should handle inactive state."""
    b = Brancho(id="b1", name="archived", active=False)
    md = b.to_markdown()
    r = Brancho.from_markdown(md)
    assert r.active is False


# ─── Test: Fruito to_markdown/from_markdown roundtrip ────────

def test_fruito_roundtrip():
    """Fruito should serialize and deserialize correctly."""
    original = Fruito(
        id="fruit-001",
        turno_id="turn-001",
        branch="main",
        content="#!/usr/bin/env python\nprint('hello')",
        fruit_type="script",
        notes="Test script",
    )
    md = original.to_markdown()
    restored = Fruito.from_markdown(md)

    assert restored.id == "fruit-001"
    assert restored.turno_id == "turn-001"
    assert restored.branch == "main"
    assert restored.fruit_type == "script"
    assert "print('hello')" in restored.content
    assert "Test script" in restored.notes


def test_fruito_all_types():
    """Fruito should handle all fruit types."""
    for ft in ["script", "image", "terminal", "diff", "diagram", "other"]:
        f = Fruito(id=f"f-{ft}", turno_id="t1", branch="b1", fruit_type=ft)
        md = f.to_markdown()
        r = Fruito.from_markdown(md)
        assert r.fruit_type == ft, f"Failed for {ft}"


# ─── Test: Trunko to_markdown/from_markdown roundtrip ────────

def test_trunko_roundtrip():
    """Trunko should serialize and deserialize correctly."""
    original = Trunko(
        id="trunk-001",
        name="main-trunk",
        description="Root of all branches",
        turno_template="# Turno template",
        branches=["branch-001", "branch-002"],
    )
    md = original.to_markdown()
    restored = Trunko.from_markdown(md)

    assert restored.id == "trunk-001"
    assert restored.name == "main-trunk"
    assert restored.description == "Root of all branches"
    assert "branch-001" in restored.branches
    assert "branch-002" in restored.branches
    assert restored.node_type == "trunk"


def test_trunko_no_template():
    """Trunko should handle missing template gracefully."""
    t = Trunko(id="t1", name="test")
    md = t.to_markdown()
    r = Trunko.from_markdown(md)
    assert r.turno_template == ""
    assert r.branches == []


# ─── Test: to_dict should return serializable data ────────

def test_turno_to_dict():
    """Turno.to_dict should return a dict that json.dumps doesn't choke on."""
    t = Turno(id="t1", branch="b1")
    d = t.to_dict()
    assert isinstance(d, dict)
    json.dumps(d)


def test_brancho_to_dict():
    """Brancho.to_dict should return a dict."""
    b = Brancho(id="b1", name="n")
    d = b.to_dict()
    assert isinstance(d, dict)
    json.dumps(d)


def test_fruito_to_dict():
    """Fruito.to_dict should return a dict."""
    f = Fruito(id="f1", turno_id="t1", branch="b1")
    d = f.to_dict()
    assert isinstance(d, dict)
    json.dumps(d)


def test_trunko_to_dict():
    """Trunko.to_dict should return a dict."""
    t = Trunko(id="t1", name="n")
    d = t.to_dict()
    assert isinstance(d, dict)
    json.dumps(d)


# ─── Test: Empty content parsing should fail ────────

def test_from_markdown_no_frontmatter():
    """Parsing without frontmatter should raise ValueError."""
    with pytest.raises(ValueError, match="No frontmatter"):
        Turno.from_markdown("no frontmatter here")
    with pytest.raises(ValueError, match="No frontmatter"):
        Brancho.from_markdown("no frontmatter here")
    with pytest.raises(ValueError, match="No frontmatter"):
        Fruito.from_markdown("no frontmatter here")
    with pytest.raises(ValueError, match="No frontmatter"):
        Trunko.from_markdown("no frontmatter here")


# ─── Test: node_type property consistency ────────

def test_node_types():
    """All node types should return correct values."""
    assert Turno(id="t1", branch="b1").node_type == "turn"
    assert Brancho(id="b1", name="n").node_type == "branch"
    assert Fruito(id="f1", turno_id="t1", branch="b1").node_type == "fruit"
    assert Trunko(id="t1", name="n").node_type == "trunk"


# ─── Test: from_data factory ────────

def test_turno_from_data():
    """Turno.from_data should create instance from dict."""
    data = {"id": "t1", "branch": "b1"}
    t = Turno.from_data(data)
    assert t.id == "t1"
    assert t.branch == "b1"


def test_brancho_from_data():
    """Brancho.from_data should create instance from dict."""
    data = {"id": "b1", "name": "n"}
    b = Brancho.from_data(data)
    assert b.id == "b1"
    assert b.name == "n"


def test_fruito_from_data():
    """Fruito.from_data should create instance from dict."""
    data = {"id": "f1", "turno_id": "t1", "branch": "b1"}
    f = Fruito.from_data(data)
    assert f.id == "f1"
    assert f.turno_id == "t1"


def test_trunko_from_data():
    """Trunko.from_data should create instance from dict."""
    data = {"id": "t1", "name": "n"}
    t = Trunko.from_data(data)
    assert t.id == "t1"
    assert t.name == "n"


# ─── Test: Turno revision fields ────────

def test_turno_revision_fields():
    """Turno should support revision tracking."""
    t = Turno(
        id="turn-002",
        branch="main",
        revision_of="turn-001",
        revision_number=2,
        change_reason="Fixed typo",
    )
    md = t.to_markdown()
    r = Turno.from_markdown(md)
    assert r.revision_of == "turn-001"
    assert r.revision_number == 2
    assert r.change_reason == "Fixed typo"
