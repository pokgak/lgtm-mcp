"""Response truncation to prevent context window overflow."""

import json

CHARS_PER_TOKEN = 4
MAX_TOKENS = 6000
MAX_CHARS = MAX_TOKENS * CHARS_PER_TOKEN


def truncate_response(content: object) -> str:
    """Truncate response to stay within token budget."""
    text = content if isinstance(content, str) else json.dumps(content, indent=2, default=str)

    if len(text) <= MAX_CHARS:
        return text

    truncated = text[:MAX_CHARS]
    estimated_tokens = len(text) // CHARS_PER_TOKEN

    return (
        f"{truncated}\n\n--- TRUNCATED ---\n"
        f"Response was ~{estimated_tokens:,} tokens (limit: {MAX_TOKENS:,}). "
        "Use more specific queries or filters to reduce response size."
    )
