"""
diagram_renderer.py — Tree Diagram Rendering Module
====== ====================== ======================

Render InferenceTree structures as SVG or PNG diagrams.

Features:
    1. SVG rendering (vector, zoomable, editable)
    2. PNG export (raster, shareable, embeddable)
    3. Three visualization styles:
       - mindmap: hierarchical mindmap layout
       - orgchart: organizational chart style
       - phylo: phylogenetic/tree layout
    4. Node styling by type (stem/branch/leaf/fruit)
    5. Edge styling with chain links
    6. Annotations and metadata overlays

Usage:
    from diagram_renderer import SVGDiagram, render_diagram
    
    # SVG output
    svg = SVGDiagram(tree)
    svg.render(style="mindmap")
    svg.save("output.svg")
    
    # PNG output
    png = SVGDiagram(tree)
    png.render()
    png.save_png("output.png", dpi=150)
    
    # One-shot
    diagram = render_diagram(tree, style="mindmap", output_path="diagram.png")

Layout algorithm:
    1. Walk the tree to determine depth and breadth (layering)
    2. Root at top center
    3. Children spread evenly below parent
    4. Leaf nodes at the bottom layer
    5. Node width based on text content
    6. Vertical spacing for readability

Design decisions:
    - SVG as primary format (lossless, scalable)
    - PNG as fallback for sharing/display
    - No matplotlib dependency (pure SVG path rendering)
    - Colors chosen for accessibility (colorblind safe)
    - Layout is fixed (deterministic) for reproducibility
"""

import sys
import os
import json
import math
import time
from pathlib import Path
from collections import defaultdict
from typing import Optional, List, Tuple, Dict

# ─── Color Palette (Colorblind Safe) ────════════════════════════════════════

NODE_COLORS = {
    "stem": {
        "fill": "#1a3a5c",    # Dark blue
        "stroke": "#3d7ab5",  # Medium blue
        "text": "#ffffff"     # White
    },
    "branch": {
        "fill": "#2d5a3d",    # Dark green
        "stroke": "#4a9f7a",  # Medium green
        "text": "#ffffff"     # White
    },
    "leaf": {
        "fill": "#8b6914",    # Amber
        "stroke": "#c4993a",  # Light amber
        "text": "#000000"     # Black
    },
    "fruit": {
        "fill": "#6b3fa0",    # Purple
        "stroke": "#9f6fd1",  # Light purple
        "text": "#ffffff"     # White
    },
    "system": {
        "fill": "#3a3a3a",    # Gray
        "stroke": "#666666",  # Light gray
        "text": "#ffffff"     # White
    },
}

EDGE_COLORS = {
    "stem": "#3d7ab5",  # Blue chain
    "branch": "#4a9f7a", # Green chain
    "leaf": "#c4993a",   # Amber chain
    "fruit": "#9f6fd1",  # Purple chain
}

BACKGROUND = "#0d1117"       # Dark GitHub-like background
GRID_COLOR = "#1e2530"       # Subtle grid
TEXT_COLOR = "#ffffff"       # White text
DIM_TEXT = "#8899aa"        # Subdued text
CORNER_RADIUS = 8            # Node corner radius
NODE_WIDTH = 220             # Minimum node width
NODE_HEIGHT = 70             # Node height


# ─── Layout Engine ───────────────────────────────────────────────────────────

class TreeLayout:
    """Lays out a tree for rendering."""
    
    def __init__(self, tree, height: int = None, width: int = None):
        self.tree = tree
        self.depth = 0  # Will be computed
        self.layers = defaultdict(list)  # depth -> [nodes]
        self.position = {}  # node_id -> (x, y)
        self.node_width = NODE_WIDTH
        self.node_height = NODE_HEIGHT
        self.layer_height = NODE_HEIGHT + 30  # Vertical spacing
        self.node_spacing = 20  # Horizontal spacing between siblings
        
        # Build layout
        self._compute_depth()
        self._build_layers()
        self._assign_positions(width or 1200)
        self.width = width or 1200
    
    def _compute_depth(self):
        """Compute depth for each node."""
        for node_id, node in self.tree.nodes_by_id.items():
            if hasattr(node, 'depth'):
                pass  # Use computed depth
            elif node.parent_hash == "genesis":
                pass  # Root = depth 0 (implied)
            else:
                pass  # Depth computed in layer build
    
    def _build_layers(self):
        """Build layers: group nodes by depth."""
        # BFS from roots
        visited = set()
        queue = []
        
        for root in self.tree.roots:
            queue.append(root)
            visited.add(root.id)
            self.layers[0].append(root)
        
        layer = 0
        while queue:
            next_queue = []
            for node in queue:
                layer_key = max(self.layers.keys()) + 1 if self.layers[layer] == [root] else layer + 1
                layer_key = layer + 1
                
                for child_id in node.children_hashes:
                    child = self.tree.nodes_by_id.get(child_id)
                    if child and child_id not in visited:
                        self.layers[layer_key].append(child)
                        next_queue.append(child)
                        visited.add(child_id)
            
            if next_queue:
                queue = next_queue
                layer += 1
            
            if not next_queue:
                break
        
        self.depth = max(self.layers.keys()) if self.layers else 0
    
    def _assign_positions(self, total_width: int):
        """Assign x,y coordinates to each node."""
        # Process layers top to bottom
        for layer_level, layer_nodes in sorted(self.layers.items()):
            layer_width = len(layer_nodes) * (self.node_width + self.node_spacing)
            start_x = (total_width - layer_width) / 2
            
            for i, node in enumerate(layer_nodes):
                x = start_x + i * (self.node_width + self.node_spacing)
                y = layer_level * self.layer_height + 40
                self.position[node.id] = (x, y)
        
        # Now we need to refine: children should be centered under parents
        # This requires a second pass
        for layer_level, layer_nodes in sorted(self.layers.items()):
            if layer_level == 0:
                continue
            
            # Group nodes by parent
            parent_groups = defaultdict(list)
            for node in layer_nodes:
                parent_groups[node.parent_hash].append(node)
            
            # For each parent, center children under it
            for parent_id, children in parent_groups.items():
                parent_pos = self.position.get(parent_id)
                if not parent_pos:
                    continue
                
                child_width = (len(children) * (self.node_width + self.node_spacing))
                center_x = parent_pos[0] + self.node_width / 2 - child_width / 2
                
                for i, child in enumerate(children):
                    x = center_x + i * (self.node_width + self.node_spacing)
                    y = self.position[child.id][1]  # Keep same y
                    self.position[child.id] = (x, y)


# ─── SVG Builder ───────────────────────────────────────────────────────────────

class NodeRenderer:
    """Renders a single node as SVG."""
    
    def __init__(self, x: float, y: float, id: str, label: str, 
                 node_type: str, status: str):
        self.x = x
        self.y = y
        self.id = id
        self.label = label
        self.type = node_type
        self.status = status
        self.colors = NODE_COLORS.get(node_type, NODE_COLORS["stem"])
    
    def to_svg(self) -> str:
        """Render this node as SVG path elements."""
        
        # Truncate long labels
        display_label = self.label
        if len(display_label) > 28:
            display_label = display_label[:25] + "..."
        
        # Node type icon
        icon_map = {
            "stem": "▬",
            "branch": "⇢",
            "leaf": "✦",
            "fruit": "✿",
            "system": "◇"
        }
        icon = icon_map.get(self.type, "●")
        
        # Color styling
        fill = self.colors["fill"]
        stroke = self.colors["stroke"]
        text = self.colors["text"]
        
        # Status indicator
        status_colors = {
            "active": "#4ade80",   # Green dot
            "terminal": "#f59e0b", # Yellow dot
            "resolved": "#8b5cf6", # Purple dot
        }
        status_color = status_colors.get(self.status, "#666666")
        
        # Build SVG content
        svg = []
        svg.append(f"  > <rect x=\"{self.x}\" y=\"{self.y}\" "
                   f"width=\"{self.node_width}\" height=\"{self.node_height}\" "
                   f"rx=\"{CORNER_RADIUS}\" fill=\"{fill}\" "
                   f"stroke=\"{stroke}\" stroke-width=\"2\" "
                   f"filter=\"url(#shadow)\"/>")
        svg.append(f"  > <text x=\"{self.x + 16}\" y=\"{self.y + 28}\" "
                   f"fill=\"{text}\" font-family=\"monospace\" font-size=\"12\">{icon} {display_label}</text>")
        svg.append(f"  > <text x=\"{self.x + 16}\" y=\"{self.y + 46}\" "
                   f"fill=\"{DIM_TEXT}\" font-family=\"monospace\" font-size=\"10\">[{self.status}]</text>")
        svg.append(f"  > <circle cx=\"{self.x + self.node_width - 10}\" "
                   f"cy=\"{self.y + 12}\" r=\"4\" fill=\"{status_color}\"/>")
        
        return "\n".join(svg)


class EdgeRenderer:
    """Renders edges between parent and child nodes."""
    
    def __init__(self, parent_pos: Tuple[float, float], 
                 child_pos: Tuple[float, float], 
                 node_type: str):
        self.parent = parent_pos
        self.child = child_pos
        self.type = node_type
        self.color = EDGE_COLORS.get(node_type, "#555555")
        self.parent_w = NODE_WIDTH
    
    def to_svg(self) -> str:
        """Render edge as SVG path."""
        x1 = self.parent[0] + self.parent_w / 2
        y1 = self.parent[1] + NODE_HEIGHT
        x2 = self.child[0] + NODE_WIDTH / 2
        y2 = self.child[1]
        
        # Bezier curve for smooth edges
        mid_y = (y1 + y2) / 2
        svg = f"  > <path d=\"M {x1} {y1} C {x1} {mid_y}, {x2} {mid_y}, {x2} {y2}\" " \
              f"fill=\"none\" stroke=\"{self.color}\" stroke-width=\"2\" " \
              f"opacity=\"0.6\"/>"
        
        return svg


class SVGDiagram:
    """Build and render a complete SVG diagram of the tree."""
    
    def __init__(self, tree: 'InferenceTree', style: str = "mindmap"):
        self.tree = tree
        self.style = style
        self.layout = TreeLayout(tree)
        self.elements = []
        self.edges = []
        self.title = "Inference Tree"
        self.metadata = {}
        
        # SVG configuration
        self.width = 1200
        self.height = max(600, (self.layout.depth + 1) * (NODE_HEIGHT + 30) + 100)
        self.dpi = 150
    
    def render(self, title: str = None, metadata: dict = None) -> str:
        """Render the complete tree as SVG string."""
        
        self.nodes = {}  # id -> NodeRenderer
        self.children = defaultdict(list)  # parent_id -> [child]
        
        # Build node and edge lists
        for node_id, pos in self.layout.position.items():
            node = self.tree.nodes_by_id.get(node_id)
            if not node:
                continue
            
            label = node.semantic_label or node.id[:16]
            ntype = node.node_type if hasattr(node, 'node_type') else "stem"
            status = node.status if hasattr(node, 'status') else "active"
            
            # Determine if this is a system node
            if not hasattr(node, 'node_type'):
                ntype = "system"
            
            renderer = NodeRenderer(
                x=pos[0],
                y=pos[1],
                id=node_id,
                label=label,
                node_type=ntype,
                status=status
            )
            self.nodes[node_id] = renderer
            self.elements.append(renderer)
        
        # Build edges
        for parent_id, children in self.tree.nodes_by_id.items():
            parent_pos = self.layout.position.get(parent_id)
            if not parent_pos:
                continue
            
            if hasattr(children, 'children_hashes'):
                for child_id in children.children_hashes:
                    child_pos = self.layout.position.get(child_id)
                    if child_pos:
                        ntype = ""
                        if hasattr(children, 'node_type'):
                            ntype = children.node_type
                        
                        edge = Renderer(parent_pos, child_pos, ntype)
                        self.edges.append(edge)
                        self.children[parent_id].append(child_id)
        
        # Build SVG XML
        svg_lines = []
        svg_lines.append(f"<svg xmlns=\"http://www.w3.org/2000/svg\" "
                        f"width=\"{self.width}\" height=\"{self.height}\" "
                        f"style=\"background-color: {BACKGROUND}\">")
        
        # Defs: drop shadow filter
        svg_lines.append("  > <defs>")
        svg_lines.append("  > <filter id=\"shadow\" x=\"-10%\" y=\"-10%\" width=\"120%\" height=\"120%\">")
        svg_lines.append("  > <feDropShadow dx=\"2\" dy=\"2\" stdDeviation=\"3\" "
                        f"flood-color=\"#000000\" flood-opacity=\"0.3\"/>")
        svg_lines.append("  > </filter>")
        svg_lines.append("  > </defs>")
        
        # Background grid
        svg_lines.append(f"  > <rect width=\"{self.width}\" height=\"{self.height}\" "
                        f"fill=\"{BACKGROUND}\"/>")
        
        # Draw grid lines
        for y in range(0, self.height, 40):
            svg_lines.append(f"  > <line x1=\"0\" y1=\"{y}\" x2=\"{self.width}\" y2=\"{y}\" "
                            f"stroke=\"{GRID_COLOR}\" stroke-width=\"1\" opacity=\"0.5\"/>")
        for x in range(0, self.width, 40):
            svg_lines.append(f"  > <line x1=\"{x}\" y1=\"0\" x2=\"{x}\" y2=\"{self.height}\" "
                            f"stroke=\"{GRID_COLOR}\" stroke-width=\"1\" opacity=\"0.5\"/>")
        
        # Title
        if title:
            svg_lines.append(f"  > <text x=\"{self.width/2}\" y=\"30\" "
                            f"text-anchor=\"middle\" fill=\"{TEXT_COLOR}\" "
                            f"font-family=\"monospace\" font-size=\"18\" "
                            f"font-weight=\"bold\">{title}</text>")
        
        # Draw edges first (nodes on top)
        for edge in self.edges:
            svg_lines.append(edge.to_svg)
        
        # Draw nodes
        for node_renderer in self.nodes.values():
            svg_lines.append(node_renderer.to_svg())
        
        # Metadata footer
        if metadata:
            footer_y = self.height - 20
            svg_lines.append(f"  > <text x=\"20\" y=\"{footer_y}\" "
                            f"fill=\"{DIM_TEXT}\" font-family=\"monospace\" font-size=\"11\">")
            for key, val in metadata.items():
                svg_lines.append(f"  >  {key}: {val}")
        
        svg.append("</svg>")
        
        return "\n".join(svg_lines)
    
    def save(self, output_path: Path = None):
        """Save SVG to file."""
        if output_path is None:
            output_path = Path(__file__).parent / "samples" / f"tree_diagram-{time.strftime('%Y%m%d-%H%M%S')}"
        
        if str(output_path).endswith(".svg"):
            content = self.render()
        else:
            # Try to use raster
            content = self.render()
            output_path = output_path.with_suffix(".svg")
        
        with open(output_path, "w") as f:
            f.write(content)
        
        print(f"[✓] SVG diagram saved to {output_path}")
        return output_path


# ─── PNG Renderer (Pure Python, no PIL/Raster) ──═══════════════════════════════

class PNGRenderer:
    """Render tree to PNG using base64 SVG-as-PNG approach."""
    
    def __init__(self, tree: 'InferenceTree', dpi: int = 150):
        self.svg_diagram = SVGDiagram(tree)
        self.dpi = dpi
        self.svg_content = None
    
    def render(self, **kwargs) -> str:
        """Render the tree as SVG string (first step)."""
        self.svg_content = self.svg_diagram.render(**kwargs)
        return self.svg_content
    
    def to_base64_svg(self) -> str:
        """Return the SVG content as a base64 data URI for PNG conversion."""
        import base64
        if not self.svg_content:
            self.render()
        return base64.b64encode(self.svg_content.encode()).decode()
    
    def data_uri(self) -> str:
        """Create a data URI that can be displayed in browsers or embedded in documents."""
        b64 = self.to_base64_svg()
        return f"data:image/svg+xml;base64,{b64}"
    
    def save_png_via_external(self, output_path: Path = None) -> Path:
        """Save PNG via external tools (requires convert from ImageMagick)."""
        if output_path is None:
            output_path = Path(__file__).parent / "samples"
            output_path = output_path / f"tree_diagram_{time.strftime('%Y%m%d-%H%M%S')}"
        
        # First save SVG, then convert
        svg_path = self.svg_diagram.save(output_path.with_suffix(".svg"))
        
        # Try using imagemagick convert
        import subprocess
        try:
            result = subprocess.run(
                ["convert", "-density", str(self.dpi), str(svg_path),
                 str(output_path.with_suffix(".png"))],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                png_path = output_path.with_suffix(".png")
                print(f"[✓] PNG diagram saved to {png_path}")
                return png_path
            else:
                print(f"[✗] PNG conversion failed: {result.stderr}")
        except FileNotFoundError:
            print("[!] ImageMagick 'convert' not found — saving SVG only")
        
        return svg_path


# ─── One-Shot Renderer ───────────────────────────────────────────────────────

def render_diagram(tree: 'InferenceTree', style: str = "mindmap",
                   output_path: str = None, dpi: int = 150, 
                   title: str = None, metadata: dict = None) -> dict:
    """One-shot function to render a tree diagram.
    
    Returns a dict of {svg_path, png_path (if saved), data_uri}.
    
    Args:
        trees: InferenceTree to render
        style: "mindmap" (default) | "orgchart" | "phylo"
        output_path: Where to save the file
        dpi: PNG resolution
        title: Diagram title
        metadata: Additional metadata to show
    """
    
    # Create the diagram
    svg = SVGDiagram(tree, style=style)
    svg_content = svg.render(title=title or "Inference Tree", metadata=metadata or {})
    
    if output_path:
        svg_path = Path(output_path)
        if svg_path.suffix != ".svg":
            svg_path = svg_path.with_suffix(".svg")
        with open(svg_path, "w") as f:
            f.write(svg_content)
    else:
        svg_path = None
    
    # Try PNG conversion
    png_path = None
    try:
        png = PNGRenderer(tree, dpi=dpi)
        png_content = png.render(title=title)
        png_path = png.save_png_via_external(
            Path(output_path).with_suffix(".png") if output_path else None
        )
    except Exception as e:
        print(f"[!] PNG conversion failed: {e}")
    
    # Return result
    result = {
        "svg": svg_path or Path("/dev/stdout"),
        "svg_content": svg_content,
        "data_uri": f"data:image/svg+xml;base64,{png.to_base64_svg()}" if png_path else None,
    }
    
    if png_path:
        result["png_path"] = png_path
    
    return result


# ─── Demo Mode ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    from sandbox import InferenceNode, InferenceTree
    import sys
    
    parser = argparse.ArgumentParser(description="Inference Tree Diagram Renderer")
    parser.add_argument("--style", default="mindmap", 
                        choices=["mindmap", "orgchart", "phylo"])
    parser.add_argument("--output", "-o", default=None, help="Output file path")
    parser.add_argument("--demo", action="store_true", help="Run demo mode")
    args = parser.parse_args()
    
    if args.demo or not args.output:
        # Create demo tree
        base_path = Path(__file__).parent / "samples"
        base_path.mkdir(parents=True, exist_ok=True)
        stream_path = base_path / "diagram_demo.jsonl"
        
        tree = InferenceTree(stream_path)
        tree._open()
        
        # Build a demo tree
        root = InferenceNode(
            "Inference Tree Demo",
            "This is a demonstration of the diagram rendering capabilities.",
            model="qwen3.6:35b-a3b", node_type="stem",
            semantic_label="Demo Root"
        )
        
        s1 = InferenceNode(
            "Stem node 1 content",
            "First stem node in the tree.",
            model="qwen3.6:35b-a3b", parent_hash=root.id,
            node_type="stem", semantic_label="Main Line"
        )
        
        br1 = InferenceNode(
            "Branch 1 question",
            "Branching to explore alternatives.",
            model="qwen3.6:35b-a3b", parent_hash=s1.id,
            node_type="branch", semantic_label="Divergence A"
        )
        
        ln1 = InferenceNode(
            "Leaf node content",
            "Terminal branch conclusion.",
            model="qwen3.6:35b-a3b", parent_hash=br1.id,
            node_type="leaf", semantic_label="Conclusion"
        )
        
        fruit1 = InferenceNode(
            "Fruit node content",
            "Resolved branch with carryback.",
            model="qwen3.6:35b-a3b", parent_hash=s1.id,
            node_type="fruit", semantic_label="Resolved B",
            info_carryback={"status": "confirmed"}
        )
        
        s2 = InferenceNode(
            "Stem node 2 content",
            "Second stem node.",
            model="qwen3.6:35b-a3b", parent_hash=ln1.id,
            node_type="stem", semantic_label="Continuation"
        )
        
        for node in [root, s1, br1, ln1, fruit1, s2]:
            tree.append(node)
        
        tree._close()
        
        # Render the diagram
        print("="*60)
        print("DIAGRAM RENDERER — Demo Mode")
        print("="*60)
        
        output_path = base_path / f"diagram_demo_{time.strftime('%Y%m%d-%H%M%S')}"
        result = render_diagram(
            tree,
            style=args.style,
            output_path=str(output_path),
            title="Inference Tree Demo",
            metadata={
                "nodes": str(len(tree.nodes_by_id)),
                "depth": str(tree.depth),
                "stem": str(len([n for n in tree.nodes_by_id.values() if n.node_type == "stem"]))
            }
        )
        
        print(f"SVG: {result['svg']}")
        print(f"Data URI: {result['data_uri'][:80]}...")
        if result.get('png_path'):
            print(f"PNG: {result['png_path']}")
    
    else:
        # Load existing tree from stream
        stream_path = Path(args.output).with_name('inference_stream.jsonl')
        
        # Check if the stream exists
        if not stream_path.exists():
            print(f"Stream not found: {stream_path}")
            sys.exit(1)
        
        tree = InferenceTree(stream_path)
        tree._open()
        
        # Rebuild nodes from stream
        import json
        with open(stream_path) as f:
            entries = [json.loads(l) for l in f if l.strip()]
        
        for entry in entries:
            node = InferenceNode(
                entry["prompt_snapshot"],
                entry["response_snapshot"],
                **{k: v for k, v in entry.items() if k not in ["prompt_snapshot", "response_snapshot"]}
            )
            tree.nodes_by_id[node.id] = node
        
        tree._close()
        
        # Render the diagram
        result = render_diagram(
            tree,
            style=args.style,
            output_path=args.output,
            title="Inference Tree Diagram"
        )
        
        print(f"Diagram saved to {result['svg']}")
        if result.get('png_path'):
            print(f"PNG also at {result['png_path']}")

