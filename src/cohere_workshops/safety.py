"""Detect high-confidence secret patterns before external processing."""

import re

SECRET_PATTERNS = {
    "private_key": re.compile(
        r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"
    ),
    "aws_access_key": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "github_token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    "google_api_key": re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"),
    "openai_api_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
    "anthropic_api_key": re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    "slack_token": re.compile(r"\bxox[bp]-[A-Za-z0-9-]{20,}\b"),
    "stripe_secret_key": re.compile(r"\bsk_live_[A-Za-z0-9]{20,}\b"),
}


def detect_secret_types(content: str) -> tuple[str, ...]:
    """Return deterministic labels for high-confidence secret patterns."""
    return tuple(
        name
        for name, pattern in SECRET_PATTERNS.items()
        if pattern.search(content)
    )
