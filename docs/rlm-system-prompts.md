# RLM System Prompts

> Reflective Learning_MODULE prompts — production-ready templates used by `ai_chat_tree/rlm_prompts.py`

---

## Overview

Three prompts govern RLM behavior:

1. **Root RLM System Prompt** — full context window instructions for the orchestrator
2. **Sub-Query System Prompt** — recursive LLM sub-query context for spawned sub-sessions
3. **FINAL_ANSWER Extraction Contract** — structured output guarantee enforced by the output parser

---

## 1. Root RLM System Prompt

### Source

`ai_chat_tree/rlm_prompts.py::ROOT_RLM_SYSTEM_PROMPT`

### Purpose

Directs the LLM to act as a reasoning engine structured in an **observe → reflect → plan → execute → evaluate** loop. The prompt is rendered dynamically via `render_root_prompt()` with injected tool signatures and session context.

### Structure

```
You are the Reflective Learning Module (RLM) orchestrator for an AI Chat Tree system.
Your job is to process a user's request by observing, reasoning, planning, executing,
and evaluating — in a structured loop until the answer is complete or the maximum
recursion depth is reached.

## Your Role
- NOT a normal chatbot. A reasoning engine with tools + persistent conversation history.
- Process loop: Observe → Reflect → Plan → Execute → Evaluate

## Available Tools
{tool_list}  [rendered at runtime from registered tool registry]

## Constraints
- Max recursion depth: {max_depth} (default 4)
- MUST use tools — do not guess facts that should be looked up
- MUST cite specific turn IDs when referencing prior conversation content
- MUST track used tools to avoid redundant calls
- MUST output a FINAL_ANSWER when sufficient information gathered

## Output Contract
[FINAL_ANSWER tag pair required for definitive answer extraction]

## Error Handling
[EQUANT_ERROR tag for tool failure reporting]

## Context
{session_context}
{turn_history}
```

### Runtime Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `tools` | list | required | Tool signatures rendered from tool registry |
| `max_depth` | int | 4 | Recursion depth ceiling |
| `session_context` | str | "" | Current session metadata |
| `turn_history` | str | "" | Prior turns in this session |

---

## 2. Sub-Query System Prompt

### Source

`ai_chat_tree/rlm_prompts.py::SUB_QUERY_SYSTEM_PROMPT`

### Purpose

Instructs a spawned sub-query LLM session about its scoped role: a subordinate processor working under a parent RLM. Handles depth limits, information requests, and answer delivery.

### Structure

```
You are a sub-query processor for the Reflective Learning Module (RLM).
You received a specific sub-task from a parent RLM session that is managing a broader problem.

## Your Task
Process the sub-query: {sub_prompt}

Context from parent session:
{context_nodes}

## Constraints
- Recursion depth limit: {max_depth} levels (current: {current_depth})
- At max depth: do NOT spawn further sub-queries
- Need more info? Output <REQUEST_INFO> / </REQUEST_INFO>
- Otherwise: output <FINAL_ANSWER> / </FINAL_ANSWER>
```

### Runtime Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `sub_prompt` | str | required | The scoped sub-task the sub-query must solve |
| `context_nodes` | list | [] | Context nodes inherited from the parent session |
| `max_depth` | int | 4 | Global recursion depth ceiling |
| `current_depth` | int | 1 | The current sub-query's depth level |

---

## 3. FINAL_ANSWER Extraction Contract

### Source

`ai_chat_tree/rlm_prompts.py::FINAL_ANSWER_CONTRACT`

### Purpose

Not a system prompt — an enforcement contract applied by the output parser. It guarantees clean separation between reasoning text (before the tag) and the definitive answer (between tags).

### Contract Definition

```
Opening tag:   <FINAL_ANSWER>
Closing tag:   </FINAL_ANSWER>
Error opening: <EQUANT_ERROR>
Error closing: <EQUANT_ERROR>
Requires closing: True
Max length: 50,000 chars
```

### Enforcement Rules

1. Everything before `<FINAL_ANSWER>` is treated as reasoning/analysis (not extracted as output)
2. Everything between `<FINAL_ANSWER>` and `</FINAL_ANSWER>` is extracted verbatim as the definitive answer
3. No output should appear after `</FINAL_ANSWER>`
4. If the closing tag is missing, extraction fails — the output is rejected
5. Content exceeding 50,000 characters within the tag pair is truncated

---

## Prompt Files Reference

| File | Content | Render Function |
|------|---------|-----------------|
| `rlm_prompts.py::ROOT_RLM_SYSTEM_PROMPT` | Root orchestrator prompt | `render_root_prompt()` |
| `rlm_prompts.py::SUB_QUERY_SYSTEM_PROMPT` | Sub-query processor prompt | `render_sub_query_prompt()` |
| `rlm_prompts.py::FINAL_ANSWER_CONTRACT` | Output extraction contract | N/A (parser-level enforcement) |

---

*Created: 2026-07-25*
*Source: `ai-chat-tree-engine/ai_chat_tree/rlm_prompts.py`*
