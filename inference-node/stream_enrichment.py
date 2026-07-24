"""
stream_enrichment.py — JSONL Stream Enrichment Module
=========================================================

Expands InferenceNode JSONL entries with additional metadata fields
for richer audit trails, replay capability, and quality assessment.

Enrichment categories:
  1. **Validation scores** — confidence in capture accuracy
  2. **Cross-references** — links to related nodes/turns/docs
  3. **Tool call traces** — detailed call/output/error records
  4. **Quality metrics** — token counts, latency, model performance
  5. **Semantic metadata** — intent classification, topic extraction
  6. **Guardian audit** — policy verdict references
  7. **Revision history** — node edit/revision tracking

Usage:
    from stream_enrichment import NodeEnricher, StreamEnricher
    
    # Enrich a single node
    enricher = NodeEnricher(node)
    enriched = enricher.apply_all()
    
    # Enrich an entire stream
    stream = StreamEnricher(stream_path)
    enriched_entries = stream.enrich_all()
    stream.save_enriched("enriched_stream.jsonl")

Enrichment strategy:
    - Enrichment is additive, never destructive
    - All original fields are preserved verbatim
    - Enrichment fields are prefixed with _enrich_ namespace
    - Enrichment can be applied in multiple passes (incremental)
    - Each enricher returns a diff of what was added

Design decisions:
    - Enrichment runs post-capture, never during capture
    - This avoids slowing down the capture path
    - Multiple enrichment passes are composable
    - Cross-references are computed via graph analysis, not heuristic
"""

import sys
import os
import json
import time
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict

if str(Path(__file__).parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).parent))
from sandbox import InferenceTree

# ─── Enrichment Types ─────────────────────────────────────────────────────────

class EnrichmentLevel:
    """Pre-configured enrichment presets."""
    MINIMAL = ["validation", "tokens"]           # Quick enrichment, fast path
    STANDARD = ["validation", "tokens", "cross_ref"]  # Default useful set
    FULL = ["validation", "tokens", "cross_ref", "semantic", "guardian", "revision"]  # Complete

ENRICHMENT_FIELDS = {
    "validation": "_enrich_validation",
    "tokens": "_enrich_tokens",
    "cross_ref": "_enrich_cross_ref",
    "semantic": "_enrich_semantic",
    "guardian": "_enrich_guardian",
    "revision": "_enrich_revision",
    "tool_trace": "_enrich_tool_trace",
    "quality": "_enrich_quality",
}


# ─── Node Enrichers ───────────────────────────────────────────────────────────

@dataclass
class ValidationEnrichment:
    """Node validation enrichment."""
    integrity_score: float = 1.0       # 0.0-1.0
    field_completeness: float = 1.0    # What % of fields populated
    chain_intact: bool = True          # Parent/child links verified
    syntax_valid: bool = True          # JSON parsable
    capture_confidence: float = 1.0    # Confidence in capture accuracy
    gaps: list = field(default_factory=list)  # Any missing fields detected
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class TokenEnrichment:
    """Token count and cost enrichment."""
    prompt_chars: int = 0
    response_chars: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    token_efficiency: float = 1.0      # output_chars/prompts_chars
    cost_estimate: float = 0.0         # Model-specific cost
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class CrossReferenceEnrichment:
    """Cross-reference links between nodes."""
    same_topic: list = field(default_factory=list)    # Same topic keywords
    follow_up_from: list = field(default_factory=list) # Parents this follows
    answered_by: list = field(default_factory=list)   # Who answered this
    referenced_by: list = field(default_factory=list) # Who references this
    document_refs: list = field(default_factory=list) # External doc references
    revision_of: Optional[str] = None          # ID of node this revises
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class SemanticEnrichment:
    """Semantic metadata extraction."""
    intent: str = ""
    topics: list = field(default_factory=list)
    sentiment: str = "neutral"
    complexity: str = "medium"  # low/medium/high
    language: str = "en"
    keywords: list = field(default_factory=list)
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k != "language" and v is not None}


@dataclass
class GuardianEnrichment:
    """Guardian policy enforcement metadata."""
    verdict: str = "UNVERIFIED"  # ALLOW/HOLD/DENY/UNVERIFIED
    verdict_timestamp: float = 0
    guard_verdict: str = ""
    rule_applied: str = ""
    audit_ref: str = ""
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v is not None and v != "UNVERIFIED"}


@dataclass
class RevisionEnrichment:
    """Node revision tracking."""
    revision_number: int = 1
    previous_id: Optional[str] = None
    change_reason: str = ""
    changes_summary: str = ""
    is_final: bool = True  # Last version
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class ToolTraceEnrichment:
    """Tool call execution trace."""
    calls: list = field(default_factory=list)  # Each call: {name, params, status, result}
    errors: list = field(default_factory=list)
    total_duration_ms: float = 0
    parallel_calls: int = 0
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if k != "errors" and v is not None}


@dataclass
class QualityEnrichment:
    """Quality assessment of an inference turn."""
    clarity: str = "unknown"     # low/medium/high
    completeness: str = "unknown"
    actionability: str = "unknown"  # Can the user act on this?
    model_confidence: float = 0.0
    response_length_quality: str = "unknown"  # too_short/appropriate/too_long
    formatting_quality: str = "unknown"  # messy/acceptable/polished
    
    def to_dict(self):
        return {k: v for k, v in self.__dict__.items() if v != "unknown"}


# ─── Node Enricher ─────────────────────────────────────────────────────────────

class NodeEnricher:
    """Enriches a single InferenceNode (or dict) with metadata."""
    
    def __init__(self, node, nodes_by_id: dict = None):
        self.node = node
        self.nodes_by_id = nodes_by_id or {}
        self._enrichments = {}
    
    def enrich_validation(self) -> ValidationEnrichment:
        """Validate the node and return a ValidationEnrichment."""
        gaps = []
        completeness = 1.0
        
        # Check required fields
        for field in ["id", "node_type", "status", "model", "platform"]:
            val = self._get_field(field)
            if val is None or val == "":
                completeness -= 0.15
                gaps.append(field)
        
        integrity = 1.0
        if "parent_hash" in self.node:
            ph = self.node.get("parent_hash")
            if ph == "genesis":
                pass
            elif ph in self.nodes_by_id:
                pass
            else:
                integrity = 0.5
                gaps.append(f"parent({ph[:16]}...) not found")
        
        chain = all(cid in self.nodes_by_id for cid in self.node.get("children_hashes", []))
        
        ve = ValidationEnrichment(
            integrity_score=integrity,
            field_completeness=completeness,
            chain_intact=chain,
            syntax_valid=True,
            capture_confidence=completeness,
            gaps=gaps
        )
        self._enrichments["validation"] = ve
        return ve
    
    def enrich_tokens(self) -> TokenEnrichment:
        """Calculate token and cost metrics."""
        prompt = self._get_field("prompt_snapshot") or self._get_field("prompt_text") or ""
        response = self._get_field("response_snapshot") or self._get_field("response_text") or ""
        
        pe = TokenEnrichment(
            prompt_chars=len(prompt),
            response_chars=len(response),
            estimated_input_tokens=len(prompt) // 4,
            estimated_output_tokens=len(response) // 4,
            token_efficiency = len(response) / len(prompt) if len(prompt) > 0 else 0,
            cost_estimate = self._estimate_cost(
                len(prompt) // 4, len(response) // 4
            )
        )
        self._enrichments["tokens"] = pe
        return pe
    
    def enrich_cross_references(self) -> CrossReferenceEnrichment:
        """Build cross-reference links between nodes."""
        cref = CrossReferenceEnrichment()
        
        self_id = self._get_field("id")
        parent_hash = self._get_field("parent_hash")
        
        # Follow up from parent
        if parent_hash and parent_hash != "genesis" and parent_hash in self.nodes_by_id:
            follow = self.nodes_by_id[parent_hash]
            cref.follow_up_from.append(self._id_for(follow))
        
        # Rev references (by label matching)
        label = self._get_field("semantic_label") or ""
        if "revision_of" in self.node:
            rev = self.node["revision_of"]
            cref.revision_of = rev
            cref.previous_id = self._id_for(self.nodes_by_id.get(rev))
        
        self._enrichments["cross_ref"] = cref
        return cref
    
    def enrich_semantic(self) -> SemanticEnrichment:
        """Add semantic metadata (could be from an LLM or heuristic)."""
        # Simple heuristic extraction
        prompt = self._get_field("prompt_snapshot") or self._get_field("prompt_text") or ""
        intent = self._extract_intent(prompt)
        topics = self._extract_topics(prompt)
        sentiment = self._extract_sentiment(prompt)
        
        se = SemanticEnrichment(
            intent=intent,
            topics=topics,
            sentiment=sentiment,
            complexity="high" if len(prompt) > 500 else "medium" if len(prompt) > 100 else "low"
        )
        self._enrichments["semantic"] = se
        return se
    
    def enrich_guardian(self, verdict: str = "UNVERIFIED", **kwargs) -> GuardianEnrichment:
        """Add Guardian policy enforcement metadata."""
        ge = GuardianEnrichment(
            verdict=verdict,
            verdict_timestamp=time.time(),
            rule_applied=kwargs.get("rule_applied", ""),
            audit_ref=kwargs.get("audit_ref", "")
        )
        self._enrichments["guardian"] = ge
        return ge
    
    def enrich_revision(self, reason: str = "", **kwargs) -> RevisionEnrichment:
        """Add revision tracking."""
        current_rev = self.node.get("_enrich_revision", {})
        rev = (current_rev.get("revision_number", 0) or 0) + 1
        
        re = RevisionEnrichment(
            revision_number=rev,
            change_reason=reason,
            changes_summary=kwargs.get("changes_summary", reason),
        )
        self._enrichments["revision"] = re
        return re
    
    def enrich_tool_trace(self, calls: list = None) -> ToolTraceEnrichment:
        """Add tool call execution traces."""
        te = ToolTraceEnrichment(
            calls=calls or [],
            errors=[c for c in calls if c.get("status") in ("error", "failed")],
            total_duration_ms=sum(c.get("duration_ms", 0) for c in calls or []),
            parallel_calls=len(calls) if calls and len(calls) > 1 else 1
        )
        self._enrichments["tool_trace"] = te
        return te
    
    def enrich_quality(self, **kwargs) -> QualityEnrichment:
        """Add quality assessment."""
        qe = QualityEnrichment(
            clarity=kwargs.get("clarity", "medium"),
            completeness=kwargs.get("completeness", "medium"),
            actionability=kwargs.get("actionability", "medium"),
            model_confidence=kwargs.get("model_confidence", 0.0),
            response_length_quality=kwargs.get("response_length", "approp"),
            formatting_quality=kwargs.get("formatting", "acceptable")
        )
        self._enrichments["quality"] = qe
        return qe
    
    def apply_all(self, level: EnrichmentLevel = EnrichmentLevel.STANDARD) -> dict:
        """Apply all enrichment fields and return enriched node dict."""
        level_map = {
            EnrichmentLevel.MINIMAL: ["validation", "tokens"],
            EnrichmentLevel.STANDARD: ["validation", "tokens", "cross_ref"],
            EnrichmentLevel.FULL: ["validation", "tokens", "cross_ref", "semantic", "guardian", "revision"],
        }
        
        enrichers = {
            "validation": self.enrich_validation,
            "tokens": self.enrich_tokens,
            "cross_ref": self.enrich_cross_references,
            "semantic": self.enrich_semantic,
            "guardian": lambda: self.enrich_guardian(
                kwargs.get("guardian_verdict", "UNVERIFIED")
            ),
            "revision": lambda: self.enrich_revision(
                kwargs.get("revision_reason", "auto")
            ),
        }
        
        applied = []
        for name in level_map[level]:
            fn = enrichers.get(name)
            if fn:
                try:
                    fn()
                    applied.append(name)
                except Exception as e:
                    print(f"  [!] Enrichment '{name}' failed: {e}")
        
        return self.to_enriched_dict(applied)
    
    def to_enriched_dict(self, applied: list = None) -> dict:
        """Convert enriched node to dict with enrichment fields included."""
        if isinstance(self.node, dict):
            base = dict(self.node)
        else:
            base = {
                "id": self.node.id,
                "node_type": self.node.node_type,
                "status": self.node.status,
                "parent_hash": self.node.parent_hash,
                "children_hashes": self.node.children_hashes,
                "semantic_label": self.node.semantic_label,
                "model": self.node.model,
                "platform": self.node.platform,
                "timestamp": self.node.timestamp,
                "prompt_snapshot": self.node._prompt_raw[:500] if hasattr(self.node, '_prompt_raw') else str(self.node),
                "response_snapshot": self.node._response_raw[:500] if hasattr(self.node, '_response_raw') else str(self.node),
            }
        
        if applied is None:
            applied = list(self._enrichments.keys())
        
        for name in applied:
            enrichment = self._enrichments.get(name)
            if enrichment:
                prefix = ENRICHMENT_FIELDS[name]
                base[prefix] = enrichment.to_dict()
        
        return base
    
    def get_diff(self) -> list[str]:
        """Get list of enrichment fields that were added."""
        if isinstance(self.node, dict):
            base_keys = set(self.node.keys())
        else:
            base_keys = {
                "id", "node_type", "status", "parent_hash", "children_hashes",
                "semantic_label", "model", "provider", "platform", "timestamp",
                "input_tokens", "output_tokens", "tool_calls",
                "prompt_snapshot", "response_snapshot",
            }
        
        enriched = set()
        for name, enrichment in self._enrichments.items():
            prefix = ENRICHMENT_FIELDS.get(name, f"_enrich_{name}")
            if enrichment.to_dict():
                enriched.add(prefix)
        
        return list(enriched.difference(base_keys))
    
    def _get_field(self, field: str):
        """Extract field from node (handles both dict and InferenceNode)."""
        if isinstance(self.node, dict):
            return self.node.get(field)
        return getattr(self.node, field, None)
    
    def _id_for(self, node) -> Optional[str]:
        """Get ID string for a node."""
        if isinstance(node, dict):
            return node.get("id")
        return node.id
    
    def _estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Crude cost estimate (USD per million tokens)."""
        rates = {
            "qwen2.5:32b": (0.17, 0.69),
            "qwen3:32b": (0.20, 0.80),
            "llama3.1:8b": (0.05, 0.15),
            "mistral-small3.2": (0.10, 0.30),
        }
        model = self._get_field("model") or "qwen2.5:32b"
        rate_input, rate_output = rates.get(model, (0.10, 0.30))
        return (input_tokens / 1_000_000) * rate_input + (output_tokens / 1_000_000) * rate_output
    
    def _extract_intent(self, text: str) -> str:
        """Simple heuristic intent classification."""
        text_lower = text.lower()
        
        if any(w in text_lower for w in ["can", "could", "would", "should", "do you"]):
            return "question"
        elif any(w in text_lower for w in ["please", "could you", "can you"]):
            return "request"
        elif any(w in text_lower for w in ["the suite is", "yes", "confirmed", "pushed"]):
            return "affirmation"
        elif any(w in text_lower for w in ["no", "not yet", "failed", "error"]):
            return "negation"
        elif any(w in text_lower for w in ["here", "this shows", "the structure is"]):
            return "explanation"
        else:
            return "other"
    
    def _extract_topics(self, text: str) -> list:
        """Simple heuristic topic extraction."""
        text_lower = text.lower()
        topic_keywords = {
            "architecture": ["architect", "design", "structure", "system", "tree", "node"],
            "testing": ["test", "pass", "fail", "assertion", "suite", "validate"],
            "deployment": ["push", "commit", "merge", "deploy", "install"],
            "debugging": ["error", "bug", "fix", "patch", "debug", "trace"],
            "inference": ["inference", "model", "prompt", "response", "token"],
        }
        
        topics = []
        for topic, keywords in topic_keywords.items():
            for kw in keywords:
                # Simple word boundary check
                import re
                pattern = r'\b' + re.escape(kw) + r'\b'
                if re.search(pattern, text_lower):
                    topics.append(topic)
                    break
        
        return topics if topics else ["general"]
    
    def _extract_sentiment(self, text: str) -> str:
        """Simple heuristic sentiment extraction."""
        text_lower = text.lower()
        
        positive = ["yes", "confirmed", "complete", "fixed", "passed", "done", "good", "great"]
        negative = ["error", "failed", "no", "bug", "issue", "broken", "wrong"]
        
        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)
        
        if pos_count > neg_count:
            return "positive"
        elif neg_count > pos_count:
            return "negative"
        return "neutral"


# ─── Stream Enricher ─────────────────────────────────────────────────────────

class StreamEnricher:
    """Enriches an entire JSONL stream."""
    
    def __init__(self, stream_path: Path, enrichment_level: EnrichmentLevel = EnrichmentLevel.FULL):
        self.stream_path = stream_path
        self.enrichment_level = enrichment_level
        self.entries = []
        self.nodes_by_id = {}
    
    def load(self):
        """Load stream entries into memory."""
        if not self.stream_path.exists():
            raise FileNotFoundError(f"Stream not found: {self.stream_path}")
        
        with open(self.stream_path) as f:
            self.entries = [json.loads(line) for line in f if line.strip()]
        
        # Build nodes_by_id lookup (for cross-references)
        for entry in self.entries:
            self.nodes_by_id[entry["id"]] = entry
        
        print(f"[✓] Loaded {len(self.entries)} entries from {self.stream_path}")
        return self
    
    def enrich_all(self) -> list[dict]:
        """Enrich every entry in the stream."""
        enriched = []
        for i, entry in enumerate(self.entries):
            enric = NodeEnricher(entry, self.nodes_by_id)
            
            # Apply standard enrichment set
            ve = enric.enrich_validation()
            te = enric.enrich_tokens()
            cref = enric.enrich_cross_references()
            
            if self.enrichment_level in (EnrichmentLevel.FULL, EnrichmentLevel.STANDARD):
                sent = enric.enrich_semantic()
            
            # Apply Guardian enrichment
            verdict = "UNVERIFIED"
            rule_applied = ""
            for key in entry:
                if key.startswith("_guardian_") or "guardian" in key.lower():
                    verdict = entry[key].get("verdict", "UNVERIFIED")
                    rule_applied = entry[key].get("rule_applied", "")
                    break
            
            enric.enrich_guardian(verdict, rule_applied=rule_applied)
            
            enriched_entry = enric.to_enriched_dict(
                applied=["validation", "tokens", "cross_ref"] + 
                (["semantic", "guardian"] if self.enrichment_level in (EnrichmentLevel.FULL, EnrichmentLevel.STANDARD) else [])
            )
            
            # Track enrichment stats
            enriched_entry["_enrich_stats"] = {
                "enriched_fields": list(enric._enrichments.keys()),
                "validation_score": ve.integrity_score,
                "token_count": f"{te.estimated_input_tokens}in/{te.estimated_output_tokens}out",
                "enrichment_level": self.enrichment_level.value
            }
            
            enriched.append(enriched_entry)
            print(f"  [✓] Enriched entry {i+1}/{len(self.entries)}: {entry.get('semantic_label', entry['id'][:12])}...")
        
        self.entries = enriched
        return enriched
    
    def save_enriched(self, output_path: Path = None):
        """Save enriched entries to a new file."""
        if output_path is None:
            output_path = self.stream_path.parent / f"enriched_{self.stream_path.name}"
        
        with open(output_path, "w") as f:
            for entry in self.entries:
                f.write(json.dumps(entry, ensure_ascii=False, indent=2) + "\n")
        
        print(f"[✓] Enriched stream written to {output_path}")
        return output_path
    
    def generate_report(self) -> str:
        """Generate a human-readable enrichment report."""
        if not self.entries:
            return (
                "STREAM ENRICHMENT REPORT\n"
                "="*50 + "\n"
                "  No entries loaded.\n"
            )
        
        total = len(self.entries)
        
        # Compute summary stats
        validation_scores = []
        token_totals = {
            "input": 0,
            "output": 0,
            "cost": 0.0
        }
        intents = defaultdict(int)
        topics = defaultdict(int)
        
        for entry in self.entries:
            stats = entry.get("_enrich_stats", {})
            validation_scores.append(stats.get("validation_score", 1.0))
            
            token_str = stats.get("token_count", "")
            if "in" in token_str and "out" in token_str:
                parts = token_str.split("/")
                token_totals["input"] += int(parts[0].replace("in", ""))
                token_totals["output"] += int(parts[1].replace("out", ""))
            
            semantic = entry.get("_enrich_semantic")
            if semantic:
                intents[semantic.get("intent", "other")] += 1
                topics.update(semantic.get("topics", []))
        
        # Build report
        lines = []
        lines.append("STREAM ENRICHMENT REPORT")
        lines.append("="*50)
        lines.append(f"  Entries:    {total}")
        lines.append(f"  Validation: {sum(validation_scores)/total:.3f} avg integrity")
        lines.append(f"  Tokens:     {token_totals['input']:>8,} in  /  {token_totals['output']:>8,} out")
        
        if intents:
            lines.append(f"\n  Intent distribution:")
            for intent, count in sorted(intents.items(), key=lambda x: -x[1]):
                lines.append(f"    {intent:12s}: {count}")
        
        if topics:
            lines.append(f"\n  Topic distribution:")
            for topic, count in sorted(topics.items(), key=lambda x: -x[1]):
                lines.append(f"    {topic:12s}: {count}")
        
        return "\n".join(lines)
    
    @classmethod
    def from_tree(cls, tree: InferenceTree, enrichment_level: EnrichmentLevel = EnrichmentLevel.FULL):
        """Create a StreamEnricher from an InferenceTree."""
        entries = []
        for entry in tree:
            entries.append(entry)
        
        path = tree.path
        enh = cls(path, enrichment_level)
        enh.entries = entries
        enh.nodes_by_id = tree.nodes_by_id
        return enh


# ─── Demo ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    import argparse
    
    parser = argparse.ArgumentParser(description="Inference Node Stream Enrichment")
    parser.add_argument("--stream", type=str, required=True, help="Stream file to enrich")
    parser.add_argument("--level", type=str, default="full", 
                        choices=["minimal", "standard", "full"])
    parser.add_argument("--report", action="store_true", help="Print enrichment report")
    args = parser.parse_args()
    
    level_map = {
        "minimal": EnrichmentLevel.MINIMAL,
        "standard": EnrichmentLevel.STANDARD,
        "full": EnrichmentLevel.FULL,
    }
    
    stream_path = Path(args.stream)
    if not stream_path.exists():
        print(f"[✗] Stream not found: {stream_path}")
        sys.exit(1)
    
    enh = StreamEnricher(stream_path, level_map.get(args.level, EnrichmentLevel.FULL))
    enh.load()
    
    print(f"\n{'='*50}")
    print("Enrichment report:")
    print("="*50)
    report = enh.generate_report()
    print(report)
    
    output = enh.save_enriched()
    print(f"\nEnriched stream saved to: {output}")
    print()
