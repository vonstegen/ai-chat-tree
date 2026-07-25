"""RLM Orchestrator — high-level loop that ties REPL session + LLM inference together.

This module provides:
- rlm_generate_response(): entry point for RLM-driven conversation turns
- execute_rlm_session(): recursive driver that loops through observe→reflect→plan→execute
- code block extraction + safe execution
- final answer detection & exit
- error path back to LLM
"""
from __future__ import annotations

import re
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Dict, Optional, Any, Callable

from ai_chat_tree.rlm_loop import RLMLoop, RLMLoopConfig, RLMEpisode, RLMObservation, RLMReflection
from ai_chat_tree.rlm_repl import REPLManager, list_tools
from ai_chat_tree.rlm_prompts import render_root_prompt, render_sub_query_prompt, FINAL_ANSWER_CONTRACT


# ─── Constants ──────

MAX_LLM_ITERATIONS = 5  # max LLM rounds before force-exit (within MAX_DEPTH)


# ─── Output parsing ────────────

_final_answer_re = re.compile(
    r'<FINAL_ANSWER>\s*\n?(.*?)\n?\s*</FINAL_ANSWER>',
    re.DOTALL | re.IGNORECASE,
)

_error_tag_re = re.compile(
    r'<EQUANT_ERROR>\s*\n?(.*?)\n?\s*</EQUANT_ERROR>',
    re.DOTALL | re.IGNORECASE,
)

_code_block_re = re.compile(
    r'```(?:python|py)?\s*\n(.*?)\n```',
    re.DOTALL,
)


def parse_final_answer(model_text: str) -> Optional[str]:
    """Extract FINAL_ANSWER block from model output. Returns None if not found."""
    m = _final_answer_re.search(model_text)
    return m.group(1).strip() if m else None


def parse_error(model_text: str) -> Optional[str]:
    """Extract EQUANT_ERROR block from model output."""
    m = _error_tag_re.search(model_text)
    return m.group(1).strip() if m else None


def parse_code_blocks(model_text: str) -> List[str]:
    """Extract all Python code blocks from model output."""
    return [m.group(1) for m in _code_block_re.finditer(model_text)]


# ─── Code execution pipeline ─────────────────

def extract_and_execute_code(
    code_text: str,
    repl: REPLManager,
    depth: int = 0,
) -> Dict[str, Any]:
    """Extract code blocks from model text, execute them in sandbox, return results.

    Returns dict with keys:
        - success: bool
        - results: list of execution results
        - errors: list of error strings
        - duration_ms: total execution time
    """
    code_blocks = parse_code_blocks(code_text)
    if not code_blocks:
        return {"success": False, "results": [], "errors": ["No code blocks found in model output"], "duration_ms": 0}

    results = []
    errors = []
    total_duration = 0

    for i, block in enumerate(code_blocks):
        session = repl.execute(code=block, depth=depth)
        total_duration += session.duration_ms
        if session.exit_code == 0:
            results.append({"code": block[:500], "output": session.stdout[:2000]})
        else:
            errors.append(f"Block {i} failed ({session.exit_code}): {session.stderr[:500]}")
            # Execute code blocks that are just print statements (informational)
            if "print(" in block:
                results.append({"code": block[:500], "output": session.stdout[:2000], "note": "informational only"})

    return {
        "success": len(errors) == 0,
        "results": results,
        "errors": errors,
        "duration_ms": total_duration,
    }


# ─── Response generation ───────────────

class RLMResponse:
    """Represents a complete RLM-generated response."""

    def __init__(
        self,
        answer: str,
        reasoning: str,
        episodes: List[RLMEpisode],
        is_complete: bool,
        is_error: bool = False,
        error_message: Optional[str] = None,
        final_answer_raw: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        self.answer = answer
        self.reasoning = reasoning
        self.episodes = episodes
        self.is_complete = is_complete
        self.is_error = is_error
        self.error_message = error_message
        self.final_answer_raw = final_answer_raw
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "answer": self.answer,
            "reasoning": self.reasoning,
            "episodes_count": len(self.episodes),
            "is_complete": self.is_complete,
            "is_error": self.is_error,
            "error_message": self.error_message,
            "timestamp": self.timestamp,
        }

    def __repr__(self) -> str:
        status = "COMPLETE" if self.is_complete else ("ERROR" if self.is_error else "INCOMPLETE")
        return f"RLMResponse([{status}] answer_len={len(self.answer)})"


def rlm_generate_response(
    user_query: str,
    repl: REPLManager,
    loop: RLMLoop,
    model: str = "mistral-small3.2",
    current_depth: int = 0,
    max_depth: int = 4,
    on_evaluate: Optional[Callable[[str], bool]] = None,
) -> RLMResponse:
    """Main entry point for RLM-generated responses.

    Orchestrates the full observe→reflect→plan→execute→evaluate cycle.

    Args:
        user_query: The user's original request.
        repl: REPLManager instance for tool execution.
        loop: RLMLoop instance for state tracking.
        model: Model to use for LLM calls.
        current_depth: Current recursion depth.
        max_depth: Maximum allowed recursion depth (default 4).
        on_evaluate: Optional callback(turn, score) for early termination.

    Returns:
        RLMResponse with answer, reasoning, and metadata.
    """
    if current_depth > max_depth:
        return RLMResponse(
            answer="[EQUANT_ERROR] Recursion depth exceeded maximum allowed depth.",
            reasoning="depth_limit_reached",
            episodes=[],
            is_complete=False,
            is_error=True,
            error_message=f"Depth {current_depth} > {max_depth}",
            metadata={"limit": max_depth, "actual": current_depth},
        )

    # Build the root prompt with tool descriptions
    tools = list_tools()
    system_prompt = render_root_prompt(
        tools=tools,
        max_depth=max_depth - current_depth,
        session_context=f"User query: {user_query}",
        turn_history="",
    )

    # Initialize model override
    loop.config = loop.config or RLMLoopConfig(max_depth=max_depth, default_model=model)

    # Run the loop
    episodes = loop.run(
        initial_turns=[
            {"role": "user", "content": user_query},
        ],
        vector_store=None,
        on_evaluate=on_evaluate,
    )

    # Detect if the model output contains a final answer
    latest_output = episodes[-1].output_text if episodes else ""
    final_answer = parse_final_answer(latest_output)
    error_tag = parse_error(latest_output)

    if final_answer:
        return RLMResponse(
            answer=final_answer,
            reasoning=latest_output.split(FINAL_ANSWER_CONTRACT["opening_tag"])[0],
            episodes=episodes,
            is_complete=True,
            final_answer_raw=final_answer,
            metadata=model=model,
        )

    if error_tag:
        return RLMResponse(
            answer="",
            reasoning="equant_error",
            episodes=episodes,
            is_complete=False,
            is_error=True,
            error_message=error_tag,
        )

    # No final answer detected — return reasoning + raw output for debugging
    quality = loop.get_quality_score()
    return RLMResponse(
        answer=latest_output,  # raw output as fallback, may contain reasoning
        reasoning="quality_score_inferior_to_threshold",
        episodes=episodes,
        is_complete=False,
        metadata={"quality_score": quality, "model": model, "max_depth": max_depth}
    )


# ─── Recursive session driver ───────────

def execute_rlm_session(
    query: str,
    repl: REPLManager,
    model: str = "mistral-small3.2",
    current_depth: int = 0,
    max_depth: int = 4,
    accumulated_context: Optional[List[str]] = None,
) -> RLMResponse:
    """Recursive RLM session driver.

    This is the primary interface for multi-depth RLM reasoning.
    Each call:
    1. Generates a response via the orchestrator
    2. Executes any code blocks found in the output
    3. Accumulates results as context
    4. If no final answer found and depth remaining, recurses
    5. Returns the final RLMResponse

    Args:
        query: The query to process.
        repl: REPLManager for sandbox execution.
        model: Model name.
        current_depth: Current recursion depth (default 0).
        max_depth: Maximum recursion depth (default 4).
        accumulated_context: Previous results to include as context.

    Returns:
        RLMResponse with final answer if complete, or partial results if depth exhausted.
    """
    if accumulated_context is None:
        accumulated_context = []

    response = rlm_generate_response(
        user_query=query,
        repl=repl,
        model=model,
        current_depth=current_depth,
        max_depth=max_depth,
        on_evaluate=lambda x: parse_final_answer(x) is not None,
    )

    # Accumulate context
    accumulated_context.append(response.to_dict())

    # If not complete and depth remaining, recurse
    if not response.is_complete and not response.is_error and current_depth < max_depth:
        # Build a follow-up query from the reasoning
        followup = (
            f"Previous attempt produced no final answer. Quality score: {response.metadata.get('quality_score', 'N/A')}. "
            f"Raw reasoning: {response.reasoning[:500]}. "
            f"Try a different approach. Original query: {query}"
        )
        return execute_rlm_session(
            query=followup,
            repl=repl,
            model=model,
            current_depth=current_depth + 1,
            max_depth=max_depth,
            accumulated_context=accumulated_context,
        )

    # Complete or exhausted — return best result
    response.metadata["accumulated_context"] = accumulated_context
    return response
