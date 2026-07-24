# Architecture Blueprint

## Data Flow
```text
User Input
    ↓
Inference Boundary (run_agent.py)
    ↓
InferenceNode Object Created
    ↓
Written to Event Stream (append-only JSONL)
    ↓
On-Session-End: SessionComposer()
    ↓
Stitches nodes into Session.md (rendered markdown)
    ↓
Embedding Generation + Graph Linking (VIGIL memory layer)
```

## Technical Details
- **Inference Stream Format:**
  Each line is a JSON object representing one inference cycle.
  
```python
{
  "type": "inference",
  "id": "sha256_of_content",
  "timestamp": 1721849000.200,
  "parent_hash": null_or_sha256,
  "model": "qwen3.6:35b-a3b",
  "input_tokens": 245,
  "output_tokens": 412,
  "prompt": "...",
  "response": "...",
  "metadata": {"tool_calls": []}
}
```

- **Markdown Output:**
  The composition engine looks at the stream, sees the `parent_hash` links, 
  and renders a standard chat log. Hidden in the YAML frontmatter are the 
  cryptographic links for machine traversal.
