"""Read-only repository search tool with Git validation for the agent."""

from collections.abc import Sequence
from dataclasses import dataclass, field

from cohere_workshops.chunks import RepositoryChunk
from cohere_workshops.embeddings import EmbedClient, embed_chunks, embed_query
from cohere_workshops.rerank_versions import rerank_hits
from cohere_workshops.reranking import RerankClient
from cohere_workshops.retrieval import retrieve_chunks
from cohere_workshops.version_search import VersionHit, select_level
from cohere_workshops.versions import RevisionSnapshot, VersionedChunk, VersionedCorpus

SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_code",
        "description": (
            "Searches the repository for code that answers a question. "
            "Returns only code that is valid at the target commit."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What to look for, in plain words.",
                }
            },
            "required": ["query"],
        },
    },
}

UNFILTERED_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "search_code",
        "description": (
            "Searches the repository for code that answers a question. "
            "Results can come from more than one revision. "
            "Each result lists the revisions it exists in."
        ),
        "parameters": SEARCH_TOOL["function"]["parameters"],
    },
}


def _version_key(chunk: RepositoryChunk) -> tuple[str, str, str, int, str]:
    return (
        chunk.path,
        chunk.kind,
        chunk.symbol or "",
        chunk.part_index,
        chunk.content_hash,
    )


class TargetValidator:
    """Git rule: code is valid only if it exists, unchanged, at the target commit."""

    def __init__(self, target: RevisionSnapshot) -> None:
        self.revision = target.revision
        self.commit = target.commit
        self._keys = {_version_key(chunk) for chunk in target.chunks}

    def is_valid(self, chunk: RepositoryChunk) -> bool:
        return _version_key(chunk) in self._keys


@dataclass(frozen=True)
class Decision:
    """What the Git rule decided about one candidate."""

    rank: int
    rerank_score: float
    retrieval_rank: int
    item: VersionedChunk
    valid: bool
    evidence_id: str | None


@dataclass
class SearchCall:
    """Everything one tool call did, for the trace."""

    query: str
    decisions: list[Decision] = field(default_factory=list)


def evidence_id(chunk: RepositoryChunk) -> str:
    """Short, stable ID the model can cite."""
    return chunk.chunk_id[:12]


class CodeSearchTool:
    """Embed, then Rerank, then Git validation. Never writes to the repository.

    With git_filter=False (the ablation), the top candidates are sent to the model
    whether or not they are valid at the target. Each one is labelled with the
    revisions it exists in, so the model has to decide validity itself. Git's
    decision is still recorded for every candidate.
    """

    def __init__(
        self,
        client: EmbedClient | RerankClient,
        corpus: VersionedCorpus,
        validator: TargetValidator,
        *,
        candidates: int = 10,
        keep: int = 4,
        git_filter: bool = True,
    ) -> None:
        if candidates < 1 or keep < 1:
            raise ValueError("candidates and keep must be at least 1")

        self.client = client
        self.validator = validator
        self.candidates = candidates
        self.keep = keep
        self.git_filter = git_filter
        self._revisions = (
            TargetValidator(corpus.previous),
            TargetValidator(corpus.current),
        )
        self.items = select_level(corpus.chunks, "symbol")
        self._by_id = {item.chunk.chunk_id: item for item in self.items}
        self._embedded = embed_chunks(client, [item.chunk for item in self.items])
        self.calls: list[SearchCall] = []
        self.evidence: dict[str, VersionedChunk] = {}
        self.rejected: dict[str, VersionedChunk] = {}

    @property
    def definition(self) -> dict[str, object]:
        """The tool definition Command sees in this mode."""
        return SEARCH_TOOL if self.git_filter else UNFILTERED_SEARCH_TOOL

    @property
    def valid_evidence(self) -> dict[str, VersionedChunk]:
        """Evidence sent to the model that is valid at the target."""
        return {
            key: item
            for key, item in self.evidence.items()
            if self.validator.is_valid(item.chunk)
        }

    def revisions_of(self, chunk: RepositoryChunk) -> list[str]:
        """Revisions, among the two indexed, that contain this exact chunk."""
        return [v.revision for v in self._revisions if v.is_valid(chunk)]

    def document(self, item: VersionedChunk) -> dict[str, object]:
        """The evidence document Command sees for one chunk, in this mode."""
        if self.git_filter:
            return evidence_document(item, self.validator)
        return unfiltered_evidence_document(item, self.revisions_of(item.chunk))

    def search(self, query: str) -> list[dict[str, object]]:
        """Run one search and return validated evidence documents."""
        if not query.strip():
            raise ValueError("query must not be empty")

        call = SearchCall(query=query)
        self.calls.append(call)
        if not self.items:
            return []

        query_vector = embed_query(self.client, query)
        retrieved = retrieve_chunks(query_vector, self._embedded, top_k=self.candidates)
        hits = [
            VersionHit(rank, result.score, self._by_id[result.embedded_chunk.chunk.chunk_id])
            for rank, result in enumerate(retrieved, start=1)
        ]
        reranked = rerank_hits(self.client, query, hits)

        documents: list[dict[str, object]] = []
        for candidate in reranked:
            chunk = candidate.item.chunk
            valid = self.validator.is_valid(chunk)
            sendable = valid or not self.git_filter
            cited = sendable and len(documents) < self.keep
            call.decisions.append(
                Decision(
                    rank=candidate.rank,
                    rerank_score=candidate.score,
                    retrieval_rank=candidate.retrieval_rank,
                    item=candidate.item,
                    valid=valid,
                    evidence_id=evidence_id(chunk) if cited else None,
                )
            )
            if not valid:
                self.rejected[evidence_id(chunk)] = candidate.item
            if cited:
                self.evidence[evidence_id(chunk)] = candidate.item
                documents.append(self.document(candidate.item))

        return documents


def evidence_document(item: VersionedChunk, validator: TargetValidator) -> dict[str, object]:
    """The evidence Command sees: code plus where and when it is valid."""
    chunk = item.chunk
    return {
        "id": evidence_id(chunk),
        "path": chunk.path,
        "symbol": chunk.symbol,
        "lines": f"{chunk.start_line}-{chunk.end_line}",
        "valid_at_commit": validator.commit[:12],
        "valid_at_revision": validator.revision,
        "code": chunk.content,
    }


def unfiltered_evidence_document(
    item: VersionedChunk,
    revisions: Sequence[str],
) -> dict[str, object]:
    """Ablation evidence: code plus the revisions it exists in, with no validity claim."""
    chunk = item.chunk
    return {
        "id": evidence_id(chunk),
        "path": chunk.path,
        "symbol": chunk.symbol,
        "lines": f"{chunk.start_line}-{chunk.end_line}",
        "exists_in_revisions": list(revisions),
        "code": chunk.content,
    }


def stale_references(answer: str, tool: CodeSearchTool) -> list[str]:
    """Names of rejected code that the answer still mentions."""
    valid_symbols = {item.chunk.symbol for item in tool.valid_evidence.values()}
    found = []
    for item in tool.rejected.values():
        symbol = item.chunk.symbol
        if not symbol or symbol in valid_symbols:
            continue
        name = symbol.rsplit(".", 1)[-1]
        if name in answer and name not in found:
            found.append(name)
    return found


def decision_records(calls: Sequence[SearchCall]) -> list[dict[str, object]]:
    """Trace of every tool call and every validation decision."""
    return [
        {
            "query": call.query,
            "candidates": [
                {
                    "rank": d.rank,
                    "rerank_score": round(d.rerank_score, 6),
                    "retrieval_rank": d.retrieval_rank,
                    "path": d.item.chunk.path,
                    "symbol": d.item.chunk.symbol,
                    "found_in": d.item.revision,
                    "commit": d.item.commit,
                    "valid_at_target": d.valid,
                    "sent_to_model": d.evidence_id is not None,
                    "evidence_id": d.evidence_id,
                }
                for d in call.decisions
            ],
        }
        for call in calls
    ]
