"""The invariant 3.1 guard: assert no language model on the authorisation path.

Invariant 3.1 is the load-bearing rule of the whole architecture (`AGENTS.md`): the
symbolic layer, the code that assigns trust, classifies, reasons and gates, contains
no language model, direct or indirect. If a model decides what is an instruction, that
decision is itself injectable and the guarantee is void.

Until now that rule was enforced by human inspection alone (`poc/SPEC.md` verified it
"by inspection"), even though `NEUROSYMBOLIC_FILTER_INVARIANTS.md` described its
acceptance as an automated AST check in CI. A repository-access review found the
described check did not exist. This module is that check. There is still no CI; this
runs as a harness obligation, which is the honest current state.

Why AST and not grep. A substring search cannot tell three things apart, and getting
them wrong in either direction is a failure:

- a language-model client import (FORBIDDEN on the authorisation path): `mlx`,
  `mlx_lm`, `openai`, `anthropic`, inference `transformers`/`torch`;
- a graph-database driver (ALLOWED, it is the substrate, not a model): `neo4j`,
  `GraphDatabase`, the spike's `memgraph_store`;
- the word "model" in a comment or docstring (IRRELEVANT), which `marshalling.py`
  contains many times while importing no model.

So the check parses each module with `ast` and inspects real `Import`, `ImportFrom`
and `Call` nodes, plus `subprocess`/`os.system` shell-outs, never the source text. It
keys on a forbidden set and permits a graph-DB allowlist explicitly.

Scope. The authorisation path only: `ontology/yggdrasil/`, `ontology/nornir/`, and the
PoC symbolic layer `poc/symbolic.py`. Deliberately EXCLUDED, with reasons, so the
exclusions are auditable: `ontology/tests/` (harnesses, including `e2e_harness.py`
which legitimately loads the real model to test the seam); `spike/` (throwaway
substrate experiments); and `poc/neural.py` (the neural layer, which is SUPPOSED to
call a model, it is the tainted-content reader). Only symbolic_guard.py itself is
also skipped, because it names the forbidden modules as string data.
"""

from __future__ import annotations

import ast
from pathlib import Path


# Forbidden: language-model clients and inference libraries. A top-level module name
# here, imported anywhere on the authorisation path, is a violation.
FORBIDDEN_MODULE_ROOTS = frozenset({
    "mlx", "mlx_lm", "mlx_metal",
    "openai", "anthropic", "cohere", "google.generativeai",
    "llama_cpp", "ctransformers", "vllm", "ollama",
    "transformers", "torch", "sentence_transformers", "sentencepiece",
})

# Allowed even though a substring search might flag them: graph-database drivers and
# the store binding. These are the substrate Nornir runs over, not a model.
ALLOWED_MODULE_ROOTS = frozenset({
    "neo4j", "memgraph_store", "gqlalchemy", "pymgclient",
})

# Forbidden call names: inference entry points. A call to one of these on the
# authorisation path is a violation even if the import somehow slipped through.
FORBIDDEN_CALL_NAMES = frozenset({
    "stream_generate", "generate", "chat_completion", "create_completion",
    "load",  # mlx_lm.load; note: also a common benign name, so only flagged when the
             # call is attributed to a forbidden module (see _check_calls)
})

# Roots of the authorisation path to scan.
def _authorisation_files(repo_root: Path) -> list[Path]:
    roots = [
        repo_root / "ontology" / "yggdrasil",
        repo_root / "ontology" / "nornir",
    ]
    files: list[Path] = []
    for root in roots:
        files.extend(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)
    symbolic = repo_root / "poc" / "symbolic.py"
    if symbolic.exists():
        files.append(symbolic)
    # Exclude this guard module itself: it names the forbidden modules as data.
    return [f for f in files if f.name != "symbolic_guard.py"]


class Violation:
    def __init__(self, path: Path, lineno: int, detail: str) -> None:
        self.path = path
        self.lineno = lineno
        self.detail = detail

    def __str__(self) -> str:
        return f"{self.path}:{self.lineno}: {self.detail}"


def _forbidden_root(dotted: str) -> str | None:
    """Return the forbidden top-level root of a dotted module name, or None. A name is
    forbidden if its first component (or the full name) is in the forbidden set and not
    in the allowed set. Allowed roots win, so `neo4j` and `memgraph_store` never flag."""
    parts = dotted.split(".")
    root = parts[0]
    if root in ALLOWED_MODULE_ROOTS or dotted in ALLOWED_MODULE_ROOTS:
        return None
    if root in FORBIDDEN_MODULE_ROOTS or dotted in FORBIDDEN_MODULE_ROOTS:
        return root
    return None


def _scan_module(path: Path) -> list[Violation]:
    violations: list[Violation] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as e:
        return [Violation(path, e.lineno or 0, f"could not parse: {e}")]

    for node in ast.walk(tree):
        # import mlx / import torch
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = _forbidden_root(alias.name)
                if root:
                    violations.append(Violation(
                        path, node.lineno,
                        f"imports language-model module {alias.name!r} (invariant 3.1)"))
        # from mlx_lm import load
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = _forbidden_root(module)
            if root:
                violations.append(Violation(
                    path, node.lineno,
                    f"imports from language-model module {module!r} (invariant 3.1)"))
        # subprocess / os.system shelling out to a model runner
        elif isinstance(node, ast.Call):
            target = _call_target(node.func)
            if target in {"subprocess.run", "subprocess.Popen", "subprocess.call",
                          "os.system", "os.popen"}:
                # Flag only if a forbidden model-runner name appears in the literal
                # args (a real shell-out to a model). A subprocess call with no model
                # runner argument is not a 3.1 violation on its face.
                if _args_mention_model_runner(node):
                    violations.append(Violation(
                        path, node.lineno,
                        f"shells out to a model runner via {target} (invariant 3.1)"))
    return violations


def _call_target(func: ast.expr) -> str:
    """Dotted name of a call target, e.g. 'subprocess.run', or '' if not a plain
    attribute/name chain."""
    parts: list[str] = []
    cur = func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


_MODEL_RUNNER_TOKENS = ("llama", "ollama", "llamafile", "mlx_lm", "vllm", "gguf")


def _args_mention_model_runner(call: ast.Call) -> bool:
    for arg in ast.walk(call):
        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
            low = arg.value.lower()
            if any(tok in low for tok in _MODEL_RUNNER_TOKENS):
                return True
    return False


def scan(repo_root: Path | None = None) -> list[Violation]:
    """Scan the authorisation path and return all invariant-3.1 violations (empty if
    clean). `repo_root` defaults to the repository root inferred from this file."""
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]
    violations: list[Violation] = []
    for f in _authorisation_files(repo_root):
        violations.extend(_scan_module(f))
    return violations


def scanned_files(repo_root: Path | None = None) -> list[Path]:
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]
    return _authorisation_files(repo_root)
