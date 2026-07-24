# Inference Node Architecture

## Overview
The Inference Node system captures every model interaction at the boundary of the agent. 
Unlike the AI Chat Tree, which stores finalized, high-level session transcripts, the Inference Node 
system captures the raw, atomic, and cryptographically signed moments of intelligence.

## Core Concepts

### 1. The Inference Node (The Bedrock)
The absolute minimum unit of the system. Every single prompt-and-response cycle is a node.
- **Cryptographic Chain:** Each node contains a `parent_hash`, creating an immutable blockchain-like history.
- **Atomic Timestamps:** Records the exact millisecond the prompt was sent and the response received.
- **Usage Metadata:** Tracks token counts and model provider for every inference.

### 2. The Event Stream (JSONL Source of Truth)
All interactions are appended to an event stream (`inference_stream.jsonl`). 
This stream is write-only, never-modified, and highly efficient for both human and machine parsing.
When a session ends, the stream is treated as the finalized record.

### 3. The Composition Layer (On-Demand Rendering)
The system stitches the raw inference nodes together into human-readable Markdown session files. 
This creates a "glass pane" over the raw data: you read a beautiful chat log, while the system 
maintains the graph database underneath.

### 4. Graph Connectivity
Because nodes are atomic, we can:
- **Branch and Merge:** Multiple responses to one prompt can exist as parallel nodes.
- **Compression:** Working memory can be shrunk by summarizing low-value nodes.
- **Training Data:** Every node is a labeled training sample for Chain-of-Thought (CoT).

## File Structure
```
inference-node/
├── DESIGN.md          # This document
├── sandbox.py         # Core logic prototype
└── tests/
    └── test_composition.py
```
