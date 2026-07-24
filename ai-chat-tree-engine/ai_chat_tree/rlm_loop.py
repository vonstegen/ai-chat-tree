"""RLM Loop orchestrator — LiteLLM-based reasoning, logging, and mediation.

This module provides a structured reasoning loop over local/remote LLMs using 
LiteLLM as the multi-vendor abstraction. The loop:
  1. Observes the current state (turn history, vector search results)
  2. Reflects on observations (what worked, what didn't)
  3. Plans the next action (what to ask/try next)
  4. Executes (calls the LLM with the chosen action)
  5. Evaluates results (did it work? score = 0-1)

The loop continues until max_iterations reached or confidence threshold met.
"""
from __future__ import annotations

import json
import time
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any, Tuple

import litellm

logger = logging.getLogger(__name__)

# ─── Data classes ───────────────────────────────────────────────


@dataclass
class RLMObservation:
    """An observation captured by the orchestrator."""
    timestamp: str
    category: str  # "state", "quality", "divergence", "new_info"
    description: str
    confidence: float  # 0-1
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RLMAbility:
    """A capability the loop can exercise."""
    id: str
    label: str
    prompt_template: str
    model_id: str
    max_tokens: int = 4096
    temperature: float = 0.7


@dataclass
class RLMReflection:
    """A reflection produced by the orchestrator."""
    timestamp: str
    observations: List[str]
    insight: str
    recommended_action: str
    confidence: float


@dataclass
class RLMEpisode:
    """One planning-execution-evaluation cycle."""
    iteration: int
    observations: List[RLMObservation]
    reflection: RLMReflection
    action: str
    model_id: str
    input_text: str
    output_text: str
    success_score: float
    next_action: str
    done: bool = False


@dataclass
class RLMLoopConfig:
    """Configuration for the reasoning loop."""
    config_path: Optional[str] = None
    default_model: str = "mistral-small3.2"
    models: List[Dict[str, Any]] = field(default_factory=lambda: [
        {"model_id": "primary", "provider": "ollama", "name": "mistral-small3.2",
         "temperature": 0.7, "max_tokens": 4096},
        {"model_id": "backup", "provider": "ollama", "name": "qwen2.5:32b",
         "temperature": 0.7, "max_tokens": 4096},
    ])
    fallback_chain: List[str] = field(default_factory=lambda: ["primary", "backup"])
    max_iterations: int = 5
    max_retries: int = 3
    retry_delay: float = 2.0
    observation_threshold: float = 0.65
    reflection_depth: int = 3
    reflection_mode: str = "auto"


# ─── LiteLLM provider helpers ──────────────────────────────────


def _resolve_litellm_model(model_id: str, config: RLMLoopConfig) -> str:
    """Map a local model_id to a LiteLLM model string."""
    for m in config.models:
        if m.get("model_id") == model_id:
            if m.get("provider") == "ollama":
                return f"ollama/{m['name']}"
            elif m.get("provider") == "openrouter":
                return f"openrouter/{m['name']}"
            elif m.get("provider") == "litellm" or m.get("provider") is None:
                return m.get("name", config.default_model)
    # Default to first model
    return f"ollama/{config.models[0]['name']}" if config.models else config.default_model


def _call_litellm(
    model_id: str,
    config: RLMLoopConfig,
    messages: List[Dict[str, str]],
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """Make a single LLM call via LiteLLM with retry logic."""
    model_name = _resolve_litellm_model(model_id, config)
    last_error = None

    for attempt in range(config.max_retries):
        try:
            response = litellm.completion(
                model=model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=config.retry_delay * 10,
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            logger.warning(f"LLM call failed (attempt {attempt+1}/{config.max_retries}): {e}")
            if attempt < config.max_retries - 1:
                time.sleep(config.retry_delay)

    raise RuntimeError(f"All {config.max_retries} LLM retries exhausted") from last_error


# ─── Reflection and observation builders ───────────────────────


def _build_context_messages(
    history: List[Dict[str, Any]],
    observations: List[RLMObservation],
    previous_reflections: List[RLMReflection],
) -> List[Dict[str, str]]:
    """Build the system context + observations for reflection."""
    context_parts = [
        "You are an RLM (Reflective Learning Module) orchestrator. "
        "You observe conversation states, reflect on observations, "
        "and plan the next action to optimize conversation quality."
    ]
    
    if history:
        history_str = json.dumps(history, indent=2, ensure_ascii=False)[:5000]
        context_parts.append(f"\nConversation history (last 2000 chars of latest):\n{history_str}")
    
    if observations:
        obs_text = "\n".join(
            f"  - [{o.category}] ({o.confidence:.2f}) {o.description}"
            for o in observations
        )
        context_parts.append(f"\nRecent observations:\n{obs_text}")
    
    if previous_reflections:
        refl_text = "\n".join(
            f"  Previous reflection #{i+1}: {r.insight[:200]} -> action: {r.recommended_action}"
            for i, r in enumerate(previous_reflections[-5:])
        )
        context_parts.append(f"\nPrevious reflections:\n{refl_text}")
    
    system_msg = "\n\n---\n\n".join(context_parts)
    return [
        {"role": "system", "content": system_msg[:4000]},
        {"role": "user", 
         "content": f"Reflect on the current state. Return a JSON object with keys:\n"
                    f"  - observation: string\n"
                    f"  - insight: string\n"
                    f"  - recommended_action: string\n"
                    f"  - action_confidence: float (0-1)"},
    ]


# ─── Main orchestrator ─────────────────────────────────────────


class RLMLoop:
    """Litellm-powered reasoning loop for AI Chat Tree conversations.
    
    Manages the observe → reflect → plan → execute → evaluate cycle.
    Default model: mistral-small3.2 (configurable via config.yaml).
    """

    def __init__(self, config: Optional[RLMLoopConfig] = None):
        self.config = config or RLMLoopConfig()
        self.episodes: List[RLMEpisode] = []
        self.reflections: List[RLMReflection] = []

    def add_observation(self, category: str, description: str, confidence: float = 1.0,
                       metadata: Optional[Dict] = None) -> RLMObservation:
        """Record an observation about the conversation."""
        obs = RLMObservation(
            timestamp=datetime.now(timezone.utc).isoformat(),
            category=category,
            description=description,
            confidence=confidence,
            metadata=metadata or {},
        )
        self.reflection_log.append(obs)
        return obs

    def reflect(self, history: Optional[List[Dict]] = None) -> RLMReflection:
        """Run the reflection phase using LiteLLM."""
        if len(self.reflection_log) < 2:
            # Need minimum observations to reflect
            insight = "Insufficient observations for reflection."
        else:
            high_conf = [o for o in self.reflection_log if o.confidence >= self.config.observation_threshold]
            if not high_conf:
                insight = "No high-confidence observations available."
            else:
                insight = f"Pattern across {len(high_conf)} high-confidence observations: " + \
                         ", ".join(o.description[:80] for o in high_conf[:3])

        reflection = RLMReflection(
            timestamp=datetime.now(timezone.utc).isoformat(),
            observations=[o.description for o in self.reflection_log[-3:]],
            insight=insight,
            recommended_action="Continue current strategy" if "pattern" in insight else "Consider alternative approach",
            confidence=0.5 if len(self.reflection_log) < 3 else 0.75,
        )
        return reflection

    def run(
        self,
        initial_turns: List[Dict] = None,
        vector_store=None,
        on_evaluate: Any = None,
    ) -> List[RLMEpisode]:
        """Run the RLM loop up to max_iterations.
        
        Args:
            initial_turns: Existing conversation turn history
            vector_store: Optional VectorStore for similarity search
            on_evaluate: Optional callback(turn, score) for evaluation
            
        Returns:
            List of completed episodes
        """
        if initial_turns is None:
            initial_turns = []

        for iteration in range(self.config.max_iterations):
            # Observe
            self.reflection_log.append(RLMObservation(
                timestamp=datetime.now(timezone.utc).isoformat(),
                category="loop_start",
                description=f"Loop iteration {iteration + 1}/{self.config.max_iterations}",
                confidence=0.8,
            ))

            # Reflect
            reflection = self.reflect(initial_turns)
            self.add_observation("reflection", reflection.insight, confidence=reflection.confidence)

            # Plan next action
            if reflection.confidence < 0.3:
                next_action = "pause"
                done = True
            else:
                next_action = reflection.recommended_action
                done = False

            # Execute (use primary or fallback)
            model_id = self.config.fallback_chain[0]
            try:
                context_msgs = _build_context_messages(
                    initial_turns, self.reflection_log, self.reflections
                )
                output = _call_litellm(model_id, self.config, context_msgs)
                
                episode = RLMEpisode(
                    iteration=iteration,
                    observations=list(self.reflection_log),
                    reflection=reflection,
                    action=next_action,
                    model_id=model_id,
                    input_text=json.dumps(context_msgs[-1], indent=2),
                    output_text=output,
                    success_score=reflection.confidence,
                    next_action=next_action,
                    done=done,
                )
                self.episodes.append(episode)
                self.reflections.append(reflection)

                if done or on_evaluate and on_evaluate(output):
                    break

            except Exception as e:
                logger.error(f"Episode {iteration} failed: {e}")
                self.episodes.append(RLMEpisode(
                    iteration=iteration,
                    observations=list(self.reflection_log),
                    reflection=reflection,
                    action="error",
                    model_id=model_id,
                    input_text="",
                    output_text=str(e),
                    success_score=0.0,
                    next_action="retry" if iteration < self.config.max_iterations - 1 else "done",
                    done=True,
                ))
                break

        return self.episodes

    def get_quality_score(self) -> float:
        """Calculate average quality across episodes."""
        if not self.episodes:
            return 0.0
        return sum(e.success_score for e in self.episodes) / len(self.episodes)

    def get_latest_insight(self) -> str:
        """Get the most recent reflection insight."""
        return self.reflections[-1].insight if self.reflections else "No reflections yet"

