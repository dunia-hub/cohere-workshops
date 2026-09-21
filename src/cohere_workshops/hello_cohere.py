"""Make one minimal Cohere Chat request."""

import os

import cohere
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()

    api_key = os.getenv("COHERE_API_KEY")
    if not api_key:
        raise RuntimeError("COHERE_API_KEY is missing from .env")

    client = cohere.ClientV2(api_key=api_key)

    response = client.chat(
        model="command-a-03-2025",
        messages=[
            {
                "role": "user",
                "content": (
                    "In one sentence, explain why grounding matters "
                    "in an AI system that analyzes source code."
                ),
            }
        ],
        temperature=0,
        max_tokens=80,
    )

    print(response.message.content[0].text)


if __name__ == "__main__":
    main()