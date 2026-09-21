"""Build a deterministic structural map of a repository."""

from dataclasses import dataclass
from pathlib import Path

from cohere_workshops.documents import load_document
from cohere_workshops.scanner import discover_source_files
from cohere_workshops.structure import CodeSymbol, analyze_python


@dataclass(frozen=True)
class MappedFile:
    """Metadata and structural evidence for one repository file."""

    path: str
    language: str
    content_hash: str
    symbols: tuple[CodeSymbol, ...]
    imports: tuple[str, ...]


@dataclass(frozen=True)
class RepositoryMap:
    """A deterministic map of the supported files in a repository."""

    root: str
    files: tuple[MappedFile, ...]


def map_repository(repository: Path) -> RepositoryMap:
    """Scan and structurally map a repository without using AI."""
    repository = repository.resolve()
    mapped_files: list[MappedFile] = []

    for path in discover_source_files(repository):
        document = load_document(path, repository)
        symbols: tuple[CodeSymbol, ...] = ()
        imports: tuple[str, ...] = ()

        if document.language == "python":
            structure = analyze_python(document)
            symbols = structure.symbols
            imports = structure.imports

        mapped_files.append(
            MappedFile(
                path=document.path,
                language=document.language,
                content_hash=document.content_hash,
                symbols=symbols,
                imports=imports,
            )
        )

    return RepositoryMap(
        root=repository.name,
        files=tuple(mapped_files),
    )