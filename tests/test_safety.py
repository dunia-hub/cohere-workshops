from cohere_workshops.safety import detect_secret_types


def test_detects_high_confidence_secret_patterns() -> None:
    content = "\n".join(
        (
            "-----BEGIN " + "PRIVATE KEY-----",
            "AKIA" + "IOSFODNN7EXAMPLE",
            "ghp_" + "abcdefghijklmnopqrstuvwxyzABCDEFGHIJ",
            "AIza" + ("A" * 35),
            "sk-" + ("a" * 40),
            "sk-proj-" + ("b" * 30),
            "sk-ant-" + ("c" * 30),
            "xoxb-" + ("d" * 30),
            "xoxp-" + ("e" * 30),
            "sk_live_" + ("f" * 30),
        )
    )

    assert detect_secret_types(content) == (
        "private_key",
        "aws_access_key",
        "github_token",
        "google_api_key",
        "openai_api_key",
        "anthropic_api_key",
        "slack_token",
        "stripe_secret_key",
    )


def test_does_not_flag_normal_source_code() -> None:
    content = """
def load_api_key() -> str:
    return os.environ["API_KEY"]
"""

    assert detect_secret_types(content) == ()
