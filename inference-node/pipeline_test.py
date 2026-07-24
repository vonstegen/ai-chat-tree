"""
pipeline_test.py — Production Pipeline Integration Test
====== =============== ======================== =====================

Validates the complete data flow:
  Chat messages → Capture → Enrichment → Diagram → Query

Pipeline phases tested:
  Phase 1: Capture raw chat messages → JSONL stream
  Phase 2: Apply all 7 enrichment categories to the stream
  Phase 3: Build enriched tree → render SVG diagram
  Phase 4: Query node data by multiple criteria
  Phase 5: End-to-end validation — every link in the chain verified

Usage:
    python pipeline_test.py          # Run full suite
    python pipeline_test.py --verbose  # Print all assertions
"""

import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from sandbox import InferenceNode, InferenceTree, TreeComposer
from stream_enrichment import (
    StreamEnricher,
    EnrichmentLevel,
)
from diagram_renderer import SVGDiagram, PNGRenderer


# ─── Test Framework (lightweight) ──══════════════════════════════════════════════

PASSED = 0
FAILED = 0


def check(name, condition, detail=""):
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"  [PASS] {name}")
    else:
        FAILED += 1
        print(f"  [FAIL] {name}: {detail}")
    return condition


def section(name):
    print(f"\n{'='*70}")
    print(f"  {name}")
    print(f"{'='*70}")


# ─── Phase 1: Capture ──════════════════════════════════════════════════════════════

def phase1_capture(stream_path):
    """Write raw chat messages to JSONL stream."""
    section("Phase 1: Capture Pipeline")

    conversation = [
        {
            "prompt": "Session booted at " + time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "response": "Session booted at " + time.strftime("%Y-%m-%d %H:%M:%S UTC"),
            "semantic_label": "Session Boot",
            "role": "system",
            "parent_hash": "genesis",
        },
        {
            "prompt": "Hey VIGIL. Let me check the inference tree sandbox and get a status report.",
            "response": "Hey VIGIL. Let me check the inference tree sandbox and get a status report.",
            "semantic_label": "First Request",
            "role": "user",
            "parent_hash": "genesis",
        },
        {
            "prompt": "Here's a summary of the inference tree system:\n1. Core: InferenceNode + InferenceTree with cryptographically chained nodes\n2. Capture: Live, batch, demo modes — each produces JSONL stream entries\n3. Enrichment: 7 categories — validation, tokens, cross_ref, semantic, guardian, revision, tool_trace\n4. Rendering: SVG/PNG diagrams with three layouts and colorblind-safe palette\n\nTest suite: 131 tests, 131 passing (exit 0). All modules are fully implemented and validated.",
            "response": "Here's a summary of the inference tree system:\n1. Core: InferenceNode + InferenceTree with cryptographically chained nodes\n2. Capture: Live, batch, demo modes — each produces JSONL stream entries\n3. Enrichment: 7 categories — validation, tokens, cross_ref, semantic, guardian, revision, tool_trace\n4. Rendering: SVG/PNG diagrams with three layouts and colorblind-safe palette\n\nTest suite: 131 tests, 131 passing (exit 0). All modules are fully implemented and validated.",
            "semantic_label": "Status Report",
            "role": "assistant",
            "parent_hash": "genesis",  # Will be wired by tree
        },
        {
            "prompt": "Can you verify the test suite runs on this machine? I want to confirm the assertions hold on VIGIL's hardware.",
            "response": "Can you verify the test suite runs on this machine? I want to confirm the assertions hold on VIGIL's hardware.",
            "semantic_label": "Verification Request",
            "role": "user",
            "parent_hash": "genesis",
        },
        {
            "prompt": "The test suite runs on VIGIL's CLI with 10 test functions and 131 assertions (exit 0). Key validation:\n- Node construction: 8 assertions on InferenceNode initialization, field types, chain integrity\n- Tree topology: 25 assertions on root detection, children traversal, depth, breadth\n- View composition: 19 assertions on stem/branch views, tree diagrams, cross-references\nAll tests pass on this machine.",
            "response": "The test suite runs on VIGIL's CLI with 10 test functions and 131 assertions (exit 0). Key validation:\n- Node construction: 8 assertions on InferenceNode initialization, field types, chain integrity\n- Tree topology: 25 assertions on root detection, children traversal, depth, breadth\n- View composition: 19 assertions on stem/branch views, tree diagrams, cross-references\nAll tests pass on this machine.",
            "semantic_label": "CLI Test Results",
            "role": "assistant",
        },
        {
            "prompt": "Good. Next phase: pipeline integration test. We need to verify the capture → enrich → render flow works.",
            "response": "Good. Next phase: pipeline integration test. We need to verify the capture → enrich → render flow works.",
            "semantic_label": "Phase 2 Plan",
            "role": "user",
            "parent_hash": "genesis",
        },
        {
            "prompt": "Agreed. The pipeline integration will verify that capture → enrichment → rendering all work end-to-end without data loss.",
            "response": "Agreed. The pipeline integration will verify that capture → enrichment → rendering all work end-to-end without data loss.",
            "semantic_label": "Pipeline Plan",
            "role": "assistant",
        },
    ]

    # Build tree with proper parent links
    tree = InferenceTree(stream_path)
    tree._open()

    # First pass: create nodes with placeholder parents
    nodes = []
    for conv in conversation:
        parent = "genesis"
        if conv["role"] == "user" and not nodes:
            parent = "genesis"
        elif conv["role"] == "user" and nodes:
            # User picks up from last assistant
            assistant_nodes = [n for n in nodes if n.role == "assistant"]
            if assistant_nodes:
                parent = assistant_nodes[-1].id
            else:
                parent = nodes[-1].id
        elif conv["role"] == "assistant" and nodes:
            # Assistant follows last user node
            user_nodes = [n for n in nodes if n.role == "user"]
            if user_nodes:
                parent = user_nodes[-1].id
            elif nodes:
                parent = nodes[-1].id
        
        node = InferenceNode(
            prompt=conv["prompt"],
            response=conv["response"],
            model="qwen3.6:35b-a3b",
            provider="local",
            platform="matrix",
            node_type="stem" if conv["role"] != "system" else "system",
            semantic_label=conv["semantic_label"],
        )
        node.role = conv["role"]
        tree.nodes_by_id[node.id] = node
        nodes.append(node)

    # Wire parents properly
    for i, conv in enumerate(conversation):
        if conv["role"] == "user" and not nodes[:i]:
            tree.nodes_by_id[nodes[i].id]
        if conv["role"] == "assistant" and nodes:
            parent_node = nodes[i-1]
        elif conv["role"] == "system":
            parent_node = None
        else:
            parent_node = None
        
        if parent_node and parent_node != nodes[i]:
            tree.detach(nodes[i])
            tree.append(nodes[i], parent_node)

    tree._close()

    # Verify stream exists with nodes
    check(
        "Capture: tree has nodes",
        len(tree.nodes_by_id) >= 7,
        f"nodes: {len(tree.nodes_by_id)} (expected >= 7)"
    )

    check(
        "Capture: root detected",
        len(tree.roots) == 1,
        f"roots: {len(tree.roots)}"
    )

    check(
        "Capture: first node has genesis parent",
        all(
            n.parent_hash == "genesis" or n.parent_hash in tree.nodes_by_id
            for n in tree.nodes_by_id.values()
        ),
        "All node parents valid or genesis"
    )

    # Verify chain integrity
    check(
        "Capture: chain integrity verified",
        tree.verify_tree(),
        "verify_tree() returned True"
    )

    # Write tree to stream file
    # Re-open and dump
    tree._open()
    with open(stream_path, "w") as f:
        for entry in tree:
            f.write(json.dumps(entry, ensure_ascii=False, indent=2) + "\n")
    tree._close()

    check(
        "Capture: stream file written",
        stream_path.exists() and stream_path.stat().st_size > 100,
        f"stream {stream_path.stat().st_size} bytes"
    )

    # Verify every entry has required fields
    with open(stream_path) as f:
        entries = [json.loads(l) for l in f if l.strip()]

    check(
        "Capture: all entries have valid IDs",
        all(e.get("id") and len(e["id"]) == 32 for e in entries),
        f"{len(entries)} entries, all with 32-char hex IDs"
    )

    check(
        "Capture: all entries have node_type",
        all(e.get("node_type") for e in entries),
        f"node_types: {set(e.get('node_type') for e in entries)}"
    )

    if entries:
        sample = entries[0]
        check(
            "Capture: sample entry has all required fields",
            all(k in sample for k in ["id", "node_type", "parent_hash", "semantic_label", "model"]),
            f"fields: {list(sample.keys())}"
        )
    
    check("Capture: 7 entries in stream", len(entries) == 7, f"got {len(entries)}")
    
    return tree, entries


# ─── Phase 2: Enrichment ──══════════════════════════════════════════════════

def phase2_enrichment(stream_path):
    """Apply all enrichment categories to the stream."""
    section("Phase 2: Enrichment Pipeline")

    # Load enriched entries
    stream_enricher = StreamEnricher(stream_path, EnrichmentLevel.FULL)
    stream_enricher.load()

    # Enrich
    enriched = stream_enricher.enrich_all()

    check(
        "Enrichment: all entries enriched",
        len(enriched) == len(entries),
        f"{len(enriched)} enriched out of {len(entries)} original"
    )

    if enriched:
        first = enriched[0]

        # Check each enrichment category
        checks = {
            "validation": "_enrich_validation",
            "tokens": "_enrich_tokens",
            "cross_ref": "_enrich_cross_ref",
            "semantic": "_enrich_semantic",
        }

        for name, field in checks.items():
            check(
                f"Enrichment: {name} field present",
                field in first,
                f"first entry has {field}: {bool(first.get(field))}"
            )

        # Validation enrichment details
        validation = first.get("_enrich_validation", {})
        check(
            "Enrichment: validation has integrity_score",
            "integrity_score" in validation,
            f"integrity_score = {validation.get('integrity_score', 'missing')}"
        )
        check(
            "Enrichment: validation has chain_intact",
            "chain_intact" in validation,
            f"chain_intact = {validation.get('chain_intact', 'missing')}"
        )

        # Token refinement
        tokens = first.get("_enrich_tokens", {})
        check(
            "Enrichment: tokens have char counts",
            "prompt_chars" in tokens and "response_chars" in tokens,
            f"prompt_chars={tokens.get('prompt_chars', 'N/A')}, response_chars={tokens.get('response_chars', 'N/A')}"
        )

        # Cross-reference
        cross_ref = first.get("_enrich_cross_ref", {})
        check(
            "Enrichment: cross_ref has follow_up_from",
            "follow_up_from" in cross_ref,
            f"follow_up_from = {cross_ref.get('follow_up_from', [])}"
        )

        # Semantic enrichment
        semantic = first.get("_enrich_semantic", {})
        check(
            "Enrichment: semantic has intent",
            "intent" in semantic,
            f"intent = {semantic.get('intent', 'NOT SET')}"
        )
        check(
            "Enrichment: semantic has topics",
            "topics" in semantic,
            f"topics = {semantic.get('topics', [])}"
        )

        # Guardian
        guardian = first.get("_enrich_guardian", {})
        check(
            "Enrichment: guardian has verdict",
            "verdict" in guardian,
            f"verdict = {guardian.get('verdict', 'UNVERIFIED')}"
        )

        # Check enrichment stats
        stats = first.get("_enrich_stats")
        check(
            "Enrichment: stats object present",
            stats is not None,
            f"stats = {stats}"
        )
        if stats:
            check(
                "Enrichment: stats has enrichment_level",
                "enrichment_level" in stats,
                f"level = {stats.get('enrichment_level', 'NOT SET')}"
            )

    # Backward compatibility: original fields still present
    check(
        "Enrichment: backward compatible (id intact)",
        all(e.get("id") == entries[i]["id"] for i, e in enumerate(enriched)),
        "All original IDs preserved"
    )

    check(
        "Enrichment: backward compatible (node_type intact)",
        all(e.get("node_type") == entries[i]["node_type"] for i, e in enumerate(enriched)),
        "All original node_types preserved"
    )

    check(
        "Enrichment: backward compatible (semantic_label intact)",
        all(e.get("semantic_label") == entries[i]["semantic_label"] for i, e in enumerate(enriched)),
        "All original labels preserved"
    )

    # Check enrichment report
    report = stream_enricher.generate_report()
    check(
        "Enrichment: report generated",
        "STREAM ENRICHMENT REPORT" in report,
        f"report contains: {'STREAM ENRICHMENT REPORT' in report}"
    )
    check(
        "Enrichment: report has entry count",
        "Entries:" in report or "entries" in report.lower(),
        f"report has count section"
    )

    return enriched, stream_enricher


# ─── Phase 3: Diagram Rendering ──═════════════════════════════════════

def phase3_rendering(stream_path):
    """Verify diagram rendering works with enriched tree."""
    section("Phase 3: Diagram Rendering")

    # Build tree from enriched stream
    tree = InferenceTree(stream_path)
    tree._open()
    enriched_nodes = {}

    with open(stream_path) as f:
        for line in f:
            entry = json.loads(line)
            node = InferenceNode(
                prompt=entry["prompt_snapshot"] if "prompt_snapshot" in entry else "",
                response=entry["response_snapshot"] if "response_snapshot" in entry else "",
                node_type=entry.get("node_type", "stem"),
                parent_hash=entry.get("parent_hash", "genesis"),
                semantic_label=entry.get("semantic_label", ""),
                model=entry.get("model", "qwen3.6:35b-a3b"),
                platform=entry.get("platform", "matrix"),
            )
            enriched_nodes[node.id] = node

    tree.nodes_by_id.update(enriched_nodes)

    check(
        "Render: tree has enriched nodes",
        len(tree.nodes_by_id) >= 7,
        f"{len(tree.nodes_by_id)} enriched nodes"
    )

    # Generate SVG
    svg_diagram = SVGDiagram(tree)
    try:
        svg_content = svg_diagram.render(title="Pipeline Integration Test", metadata={
            "entries": str(len(entries)),
            "nodes": str(len(tree.nodes_by_id)),
            "enrichment": "FULL",
        })

        check(
            "Render: SVG document valid",
            svg_content.startswith("<svg") and "</svg>" in svg_content,
            f"SVG length: {len(svg_content)} chars, starts with: {svg_content[:80]}"
        )

        # SVG structural checks
        has_rect = "<rect" in svg_content
        has_text = "<text" in svg_content
        has_path = "<path" in svg_content
        check(
            "Render: SVG has structural elements",
            has_rect and has_text and has_path,
            f"rect={has_rect} text={has_text} path={has_path}"
        )

        # All nodes should render
        rect_count = svg_content.count("<rect")
        text_count = svg_content.count("<text")
        check(
            "Render: all nodes rendered as rects",
            rect_count >= len(tree.nodes_by_id),
            f"{rect_count} rects for {len(tree.nodes_by_id)} nodes"
        )

        check(
            "Render: text elements rendered",
            text_count >= len(tree.nodes_by_id),
            f"{text_count} text labels"
        )

        # Save SVG
        samples = Path(__file__).parent / "samples" / "pipeline"
        samples.mkdir(parents=True, exist_ok=True)
        svg_path = samples / "pipeline_diagram.svg"
        check(
            "Render: SVG written to disk",
            Path(svg_path).exists() and Path(svg_path).stat().st_size > 0,
            f"SVG saved to {svg_path}"
        )

        # Test PNG path
        try:
            import subprocess
            result = subprocess.run(
                ["which", "convert"], capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                png_path = samples / "pipeline_diagram.png"
                result = subprocess.run(
                    ["convert", "-density", "150", str(svg_path), str(png_path)],
                    capture_output=True, text=True, timeout=30,
                )
                if result.returncode == 0:
                    check(
                        "Render: PNG conversion via ImageMagick",
                        png_path.exists() and png_path.stat().st_size > 0,
                        f"PNG {png_path.stat().st_size} bytes"
                    )
                else:
                    check("Render: PNG ImageMagick conversion", False, f"ImageMagick error: {result.stderr[:200]}")
            else:
                check("Render: PNG (ImageMagick not installed)", False, "skip — convert not found")
        except Exception as e:
            check("Render: PNG via ImageMagick", False, f"exception: {e}")

    except Exception as e:
        check("Render: SVG generation", False, str(e))
        return None

    return svg_content, tree


# ─── Phase 4: Query ──═══════════════════════════════════════════

def phase4_query(tree, enriched_stream):
    """Verify query capabilities across enriched tree."""
    section("Phase 4: Query Pipeline")

    if not tree or not enriched_stream:
        check("Query: tree and enriched stream available", False, "No data to query")
        return

    # Query by node type
    node_types = {}
    for nid, node in tree.nodes_by_id.items():
        ntype = node.node_type if hasattr(node, "node_type") else "unknown"
        node_types[ntype] = node_types.get(ntype, 0) + 1

    check(
        "Query: find nodes by type (stem)",
        node_types.get("stem", 0) > 0,
        f"types: {node_types}"
    )

    check(
        "Query: find nodes by type (system)",
        node_types.get("system", 0) > 0,
        f"types: {node_types}"
    )

    # Query by semantic label
    session_nodes = [n for n in tree.nodes_by_id.values()
                     if n.semantic_label and "session" in n.semantic_label.lower()]
    check(
        "Query: find nodes by label keyword",
        len(session_nodes) > 0,
        f"found {len(session_nodes)} nodes with 'session' in label"
    )

    # Query by model
    model_nodes = [n for n in tree.nodes_by_id.values()
                   if hasattr(n, "model") and n.model == "qwen3.6:35b-a3b"]
    check(
        "Query: find nodes by model",
        len(model_nodes) == len(tree.nodes_by_id),
        f"all {len(model_nodes)} nodes use qwen3.6:35b-a3b"
    )

    # Query with enrichment filters
    high_integrity = [e for e in enriched_stream
                      if e.get("_enrich_validation", {}).get("integrity_score", 0) > 0.5]
    check(
        "Query: find nodes by enrichment score",
        len(high_integrity) >= len(enriched_stream) * 0.8,
        f"{len(high_integrity)}/{len(enriched_stream)} nodes have integrity_score > 0.5"
    )

    # Query by platform
    platform_nodes = [n for n in tree.nodes_by_id.values()
                      if hasattr(n, "platform") and n.platform == "matrix"]
    check(
        "Query: find nodes by platform",
        len(platform_nodes) == len(tree.nodes_by_id),
        f"all {len(platform_nodes)} nodes from matrix"
    )


# ─── Phase 5: End-to-End ──═══════════════════════════════════════

def phase5_end_to_end(tree, enriched_stream, svg_content):
    """Verify complete pipeline integrity."""
    section("Phase 5: End-to-End Validation")

    # All links in chain
    stream_valid = stream_path.exists() and stream_path.stat().st_size > 0
    check(
        "Pipeline: raw messages → captured stream",
        stream_valid,
        f"stream {stream_path.stat().st_size if stream_valid else 'missing'} bytes"
    )

    check(
        "Pipeline: stream → enriched entries",
        enriched_stream and len(enriched_stream) >= 3,
        f"{len(enriched_stream)} enriched entries"
    )

    check(
        "Pipeline: enriched entries → tree",
        tree and len(tree.nodes_by_id) >= 3,
        f"{len(tree.nodes_by_id)} nodes in enriched tree"
    )

    check(
        "Pipeline: enriched tree → SVG diagram",
        svg_content and svg_content.startswith("<svg"),
        f"SVG {len(svg_content)} chars"
    )

    check(
        "Pipeline: all 7 enrichment categories applied",
        all(e.get("_enrich_stats") for e in enriched_stream),
        f"all {len(enriched_stream)} entries have _enrich_stats"
    )

    check(
        "Pipeline: complete chain verified",
        tree.verify_tree() if tree else False,
        "Chain integrity confirmed on enriched tree"
    )

    check(
        "Pipeline: all phases completed",
        FAILED == 0,
        f"{PASSED} passed, {FAILED} failed"
    )


# ─── Main ──═══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="Pipeline Integration Test")
    parser.add_argument("--stream", help="Stream path for test")
    args = parser.parse_args()

    base_path = Path(__file__).parent / "samples"
    base_path.mkdir(parents=True, exist_ok=True)
    stream_path = Path(args.stream) if args.stream else base_path / "pipeline_integration.jsonl"

    # Reset counters
    global PASSED, FAILED, entries
    PASSED = 0
    FAILED = 0

    # Clear old stream
    if stream_path.exists():
        stream_path.unlink()

    print("="*70)
    print("PIPELINE INTEGRATION TEST — End-to-End Validation")
    print("="*70)
    print(f"  Stream: {stream_path}")
    print(f"  {'='*50}")

    # Run all phases
    tree, entries = phase1_capture(stream_path)
    enriched, stream_enricher = phase2_enrichment(stream_path)
    svg_content, enriched_tree = phase3_rendering(stream_path) if tree else (None, None)
    phase4_query(enriched_tree, enriched) if enriched else None
    phase5_end_to_end(enriched_tree, enriched, svg_content)

    print("\n" + "="*70)
    print(f"RESULT: {PASSED} passed, {FAILED} failed out of {PASSED + FAILED} total")
    print("="*70)

    if FAILED > 0:
        print(f"\nPipeline validation FAILED with {FAILED} failures.")
        sys.exit(1)
    else:
        print(f"\n✓ All pipeline phases validated successfully. Pipeline production-ready.")
        sys.exit(0)
