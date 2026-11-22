"""A read-only, version aware code agent built on Cohere Command."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from cohere_workshops.agent_tools import (
    CodeSearchTool,
    decision_records,
    stale_references,
)
from cohere_workshops.prediction import COMMAND_MODEL

AGENT_PROMPT = """You are a read-only code assistant for one Git repository.
Always call search_code before answering. You may call it again with a better query.
The tool only returns code that is valid at the target commit.
Answer using only that evidence. If it does not answer the question, say so."""

ANSWER_PROMPT = """Answer the question using only the evidence below.
Every piece of evidence is valid at the target commit.
Cite the evidence IDs you used. If the evidence does not answer the question,
set declined to true, explain why in decline_reason and leave answer empty.

Question:
{question}

Evidence:
{evidence}
"""


# Ablation prompts (git_filter=False). Nothing is pre-validated, so the prompts name
# the target and ask the model to decide validity from the revision labels.
UNFILTERED_AGENT_PROMPT = """You are a read-only code assistant for one Git repository.
The question is about the code at target revision {revision} (commit {commit}).
Always call search_code before answering. You may call it again with a better query.
Search results can come from more than one revision. Each result lists the revisions it exists in.
Answer using only code that exists at the target revision. If it does not answer the question, say so."""

UNFILTERED_ANSWER_PROMPT = """Answer the question about the code at target revision {revision} \
(commit {commit}), using only the evidence below.
Evidence can come from more than one revision. Each piece lists the revisions it exists in.
Use only evidence that exists at the target revision.
Cite the evidence IDs you used. If the evidence does not answer the question,
set declined to true, explain why in decline_reason and leave answer empty.

Question:
{question}

Evidence:
{evidence}
"""


def agent_prompt(tool: CodeSearchTool) -> str:
    """System prompt for tool planning, in the tool's mode."""
    if tool.git_filter:
        return AGENT_PROMPT
    return UNFILTERED_AGENT_PROMPT.format(
        revision=tool.validator.revision, commit=tool.validator.commit[:12]
    )


def answer_prompt(tool: CodeSearchTool, question: str, evidence: str) -> str:
    """Prompt for the final answer, in the tool's mode."""
    if tool.git_filter:
        return ANSWER_PROMPT.format(question=question, evidence=evidence)
    return UNFILTERED_ANSWER_PROMPT.format(
        revision=tool.validator.revision,
        commit=tool.validator.commit[:12],
        question=question,
        evidence=evidence,
    )


class ChatClient(Protocol):
    def chat(self, **kwargs: object) -> object: ...


@dataclass
class AgentResult:
    """The final answer plus everything needed to audit it."""

    question: str
    answer: str
    declined: bool
    decline_reason: str
    evidence_ids: list[str]
    references: list[dict[str, object]]
    tool_plans: list[str] = field(default_factory=list)
    forced_search: bool = False
    stale: list[str] = field(default_factory=list)


def answer_schema(evidence_ids: Sequence[str]) -> dict[str, object]:
    """JSON Schema that only allows citing evidence that was sent to Command.

    With the Git filter on, that is only evidence that passed the Git check.
    """
    return {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "declined": {"type": "boolean"},
            "decline_reason": {"type": "string"},
            "evidence_ids": {
                "type": "array",
                "items": {"type": "string", "enum": list(evidence_ids)},
            },
        },
        "required": ["answer", "declined", "decline_reason", "evidence_ids"],
    }


def message_text(message: object) -> str | None:
    """Return the first text block, skipping thinking blocks."""
    for item in getattr(message, "content", None) or []:
        text = getattr(item, "text", None)
        if isinstance(text, str):
            return text
    return None


def _tool_content(
    documents: list[dict[str, object]],
    *,
    git_filter: bool = True,
) -> list[dict[str, object]]:
    if not documents:
        result = "No code valid at the target commit." if git_filter else "No code found."
        documents = [{"id": "none", "result": result}]
    return [
        {"type": "document", "document": {"data": doc, "id": str(doc["id"])}}
        for doc in documents
    ]


def gather_evidence(
    client: ChatClient,
    tool: CodeSearchTool,
    question: str,
    *,
    model: str = COMMAND_MODEL,
    max_tool_calls: int = 3,
) -> tuple[list[str], bool]:
    """Let Command decide what to search for. Our code runs every search."""
    messages: list[object] = [
        {"role": "system", "content": agent_prompt(tool)},
        {"role": "user", "content": question},
    ]
    plans: list[str] = []
    calls_made = 0

    for _ in range(max_tool_calls + 1):
        response = client.chat(
            model=model, messages=messages, tools=[tool.definition], temperature=0
        )
        message = response.message
        tool_calls = getattr(message, "tool_calls", None) or []
        if not tool_calls:
            break

        plan = getattr(message, "tool_plan", None)
        if plan:
            plans.append(plan)
        messages.append(message)

        for tool_call in tool_calls:
            documents: list[dict[str, object]] = []
            if tool_call.function.name == "search_code" and calls_made < max_tool_calls:
                arguments = json.loads(tool_call.function.arguments or "{}")
                query = str(arguments.get("query", "")).strip() or question
                documents = tool.search(query)
                calls_made += 1
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": _tool_content(documents, git_filter=tool.git_filter),
                }
            )

    forced = calls_made == 0
    if forced:
        tool.search(question)
    return plans, forced


def run_agent(
    client: ChatClient,
    tool: CodeSearchTool,
    question: str,
    *,
    model: str = COMMAND_MODEL,
    max_tool_calls: int = 3,
) -> AgentResult:
    """Search, validate with Git, then answer from the evidence that was sent."""
    if not question.strip():
        raise ValueError("question must not be empty")

    plans, forced = gather_evidence(
        client, tool, question, model=model, max_tool_calls=max_tool_calls
    )
    evidence = tool.evidence

    if not evidence:
        return AgentResult(
            question=question,
            answer="",
            declined=True,
            decline_reason=(
                "No code valid at the target commit was found."
                if tool.git_filter
                else "Search returned no code."
            ),
            evidence_ids=[],
            references=[],
            tool_plans=plans,
            forced_search=forced,
        )

    documents = [tool.document(item) for item in evidence.values()]
    response = client.chat(
        model=model,
        messages=[
            {
                "role": "user",
                "content": answer_prompt(
                    tool, question, json.dumps(documents, indent=2)
                ),
            }
        ],
        response_format={"type": "json_object", "schema": answer_schema(list(evidence))},
        temperature=0,
    )
    text = message_text(response.message)
    if text is None:
        raise ValueError("Command returned no text answer")

    payload = json.loads(text)
    cited = [i for i in payload.get("evidence_ids", []) if i in evidence]
    answer = str(payload.get("answer", ""))
    declined = bool(payload.get("declined", False))

    return AgentResult(
        question=question,
        answer=answer,
        declined=declined,
        decline_reason=str(payload.get("decline_reason", "")),
        evidence_ids=cited,
        references=[
            {
                "evidence_id": i,
                "path": evidence[i].chunk.path,
                "symbol": evidence[i].chunk.symbol,
                "lines": f"{evidence[i].chunk.start_line}-{evidence[i].chunk.end_line}",
                "valid_at_target": tool.validator.is_valid(evidence[i].chunk),
                "valid_at_commit": (
                    tool.validator.commit if tool.validator.is_valid(evidence[i].chunk) else None
                ),
            }
            for i in cited
        ],
        tool_plans=plans,
        forced_search=forced,
        stale=stale_references(answer, tool),
    )


def agent_record(
    result: AgentResult,
    tool: CodeSearchTool,
    *,
    run_id: str,
    models: dict[str, str],
) -> dict[str, object]:
    """Full trace: tool calls, validation decisions and the final answer."""
    return {
        "run_id": run_id,
        "question": result.question,
        "target": {"revision": tool.validator.revision, "commit": tool.validator.commit},
        "models": models,
        "git_filter": tool.git_filter,
        "tool_plans": result.tool_plans,
        "forced_search": result.forced_search,
        "tool_calls": decision_records(tool.calls),
        "answer": result.answer,
        "declined": result.declined,
        "decline_reason": result.decline_reason,
        "references": result.references,
        "stale_references": result.stale,
    }
