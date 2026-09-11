"""
decider.py — the routing "brain".

Phase 1: simple, transparent, rule-based. Given a prompt, decide which model
to use and RETURN THE REASON too (so the UI can show why).

Later: replace `decide()`'s body with a DB lookup of model/provider specs.
The function signature stays the same, so nothing downstream changes.
"""

from dataclasses import dataclass

# The model names here must match the `model_name` values in your litellm_config.yaml
LOCAL_MODEL = "local-qwen"
EXTERNAL_MODEL = "gemini-flash"

# --- crude cost hint (illustrative only; NOT the conversion layer) ---
# Lower = cheaper to us. Local is ~free once the GPU/CPU is running.
# This is just so the reason string can mention "cheaper".
COST_HINT = {
    LOCAL_MODEL: "very low (our own machine)",
    EXTERNAL_MODEL: "per-token (external API)",
}

# Keywords that suggest a harder / specialist task better sent to the stronger model.
_HARD_KEYWORDS = [
    "code", "python", "javascript", "sql", "regex", "algorithm",
    "legal", "contract", "medical", "translate", "prove", "analyze",
    "essay", "summarize this", "write a report",
]

# Length threshold (characters). Short prompts -> local is usually fine.
_LENGTH_THRESHOLD = 240


@dataclass
class Decision:
    model: str          # the model_name to send to LiteLLM
    reason: str         # human-readable why, shown in the UI
    rule: str           # short rule id, handy for logging/debugging


def decide(prompt: str) -> Decision:
    """Apply simple rules to choose a model. Order matters: first match wins."""
    text = (prompt or "").strip()
    lowered = text.lower()

    # Rule 1 — empty / trivial: send local, no reason to pay.
    if len(text) == 0:
        return Decision(LOCAL_MODEL, "Empty prompt — defaulting to local model.", "empty")

    # Rule 2 — looks like a harder/specialist task: use the stronger external model.
    hit = next((k for k in _HARD_KEYWORDS if k in lowered), None)
    if hit:
        return Decision(
            EXTERNAL_MODEL,
            f"Detected a harder/specialist task (keyword: '{hit}') — routing to the "
            f"stronger external model. Cost: {COST_HINT[EXTERNAL_MODEL]}.",
            "hard_keyword",
        )

    # Rule 3 — long prompt: likely needs more capability.
    if len(text) > _LENGTH_THRESHOLD:
        return Decision(
            EXTERNAL_MODEL,
            f"Long prompt ({len(text)} chars > {_LENGTH_THRESHOLD}) — routing to the "
            f"stronger external model. Cost: {COST_HINT[EXTERNAL_MODEL]}.",
            "long_prompt",
        )

    # Rule 4 — default: short & simple → local model (the profit path).
    return Decision(
        LOCAL_MODEL,
        f"Short, simple prompt ({len(text)} chars) — the local model can handle it. "
        f"Cost: {COST_HINT[LOCAL_MODEL]}. This is the low-cost path.",
        "default_local",
    )


# quick self-test
if __name__ == "__main__":
    tests = [
        "Hi there",
        "Write a python function to reverse a linked list",
        "x" * 300,
        "What's the capital of France?",
    ]
    for t in tests:
        d = decide(t)
        print(f"[{d.rule:14}] -> {d.model:12} | {d.reason}")
