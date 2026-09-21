"""Extract structural evidence from Python source files."""

import ast
from dataclasses import dataclass

from cohere_workshops.documents import RepositoryDocument


@dataclass(frozen=True)
class CodeSymbol:
    """A named symbol found in source code."""

    name: str
    kind: str
    line: int


@dataclass(frozen=True)
class PythonStructure:
    """Structural facts extracted from one Python file."""

    path: str
    symbols: tuple[CodeSymbol, ...]
    imports: tuple[str, ...]


def analyze_python(document: RepositoryDocument) -> PythonStructure:
    """Extract symbols and imports without using a language model."""
    if document.language != "python":
        raise ValueError(f"Expected a Python document, received {document.language}")

    tree = ast.parse(document.content, filename=document.path)
    symbols: list[CodeSymbol] = []
    imports: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            symbols.append(CodeSymbol(node.name, "class", node.lineno))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols.append(CodeSymbol(node.name, "function", node.lineno))
        elif isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.add(node.module or "")

    return PythonStructure(
        path=document.path,
        symbols=tuple(sorted(symbols, key=lambda symbol: symbol.line)),
        imports=tuple(sorted(import_name for import_name in imports if import_name)),
    )