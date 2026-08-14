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
and `Call` nodes, plus `subprocess`/`os.system` shell-outs, never the source text.

Why an allowlist and not a forbidden list (D71). An earlier form of this guard (D70)
enforced by a forbidden set of model-client modules plus an enumerated set of about
ten network modules. That is a blacklist of module names, the same shape as a blacklist
of hostnames: it fails on the next name not listed. A hosted-inference call via `boto3`
(AWS Bedrock) or `google` (Vertex/Gemini), or egress via `smtplib`, `ssl` or `ctypes`,
needs none of the enumerated network modules and so passed the D70 guard clean, which
is exactly the indirect model call invariant 3.1 forbids, and invariant 3.5's blacklist
trap reproduced one layer over on the very guard meant to enforce the anti-blacklist
discipline. Enforcement is therefore inverted: `ALLOWED_IMPORT_ROOTS` is the boundary.
Any absolute import whose root is not on it is a violation. Relative (intra-package)
imports are exempt. This forbids the whole indirect-egress class by construction, and it
has the correct polarity for this project: safety is earned by a positive match, and a
new dependency is a deliberate trust-boundary decision made in review, not a silent
pass. The forbidden and network sets are kept only to produce a more specific message
for the obvious cases; they are no longer the boundary.

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


# THE BOUNDARY (D71). The known-good top-level import roots the authorisation path is
# permitted. Any absolute import whose root is not here is a violation. This is an
# ALLOWLIST, not a blacklist: it forbids the whole indirect-egress class (hosted
# inference via `boto3`/`google`, egress via `smtplib`/`ssl`/`ctypes`, or any module
# not listed) by construction, rather than enumerating forbidden names and failing on
# the next one. It was derived by scanning the real authorisation path, which imports
# exactly these 12 roots: standard library plus the graph-DB substrate (`neo4j`, the
# spike's `memgraph_store`). Adding a root here is a deliberate trust-boundary decision
# made in review. Relative (intra-package) imports are exempt (handled in _scan_module).
ALLOWED_IMPORT_ROOTS = frozenset({
    # standard library used by the deterministic classifier/reasoner
    "__future__", "collections", "dataclasses", "email", "enum", "json",
    "pathlib", "re", "sys", "typing",
    # the graph-DB substrate Nornir runs over (not a model)
    "neo4j", "memgraph_store",
})

# The following two sets are NO LONGER THE BOUNDARY (D71). They exist only to produce a
# more specific, more useful message for the obvious cases: an import that is both
# not-allowlisted AND a known model client or network module gets named as such rather
# than reported as a generic unlisted import. Enforcement is by ALLOWED_IMPORT_ROOTS.

# Language-model clients and inference libraries (for messaging only).
FORBIDDEN_MODULE_ROOTS = frozenset({
    "mlx", "mlx_lm", "mlx_metal",
    "openai", "anthropic", "cohere", "google", "boto3",
    "llama_cpp", "ctransformers", "vllm", "ollama",
    "transformers", "torch", "sentence_transformers", "sentencepiece",
})

# Network / outbound-HTTP modules (for messaging only). The invariant forbids a model
# call "direct or INDIRECT", and the most likely indirect path is an HTTP call to a
# hosted inference endpoint. These are named for a clearer message; the allowlist is
# what actually forbids them (and every other egress module not in this set).
NETWORK_MODULE_ROOTS = frozenset({
    "requests", "httpx", "aiohttp", "urllib", "urllib3", "http", "socket",
    "websocket", "websockets", "grpc", "smtplib", "ftplib", "pycurl",
})

# Dynamic-import builtins/functions: the textbook INDIRECT import, by which a
# forbidden module could be loaded without a static import statement the guard can
# see. Any use on the authorisation path is a violation, because the path has no
# legitimate need to import a module chosen at runtime.
DYNAMIC_IMPORT_CALLS = frozenset({
    "__import__", "importlib.import_module", "importlib.__import__",
    "import_module",  # bare, when importlib is imported as a name
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


def _import_violation(dotted: str, path: Path, lineno: int) -> Violation | None:
    """Enforce the allowlist (D71). Return a Violation if the absolute import root is
    not on ALLOWED_IMPORT_ROOTS, else None. The forbidden and network sets are consulted
    only to make the message more specific for the obvious cases; the allowlist is the
    boundary, so an unlisted egress module (`boto3`, `smtplib`, `ssl`, ...) is caught
    even though it is on no forbidden list."""
    root = dotted.split(".")[0]
    if root in ALLOWED_IMPORT_ROOTS:
        return None
    if root in FORBIDDEN_MODULE_ROOTS:
        detail = (f"imports language-model module {dotted!r}, which is not on the "
                  f"authorisation-path allowlist (invariant 3.1)")
    elif root in NETWORK_MODULE_ROOTS:
        detail = (f"imports network module {dotted!r}; the authorisation path must make "
                  f"no outbound call, which is how an indirect model call (a hosted "
                  f"inference endpoint) would arrive (invariant 3.1)")
    else:
        detail = (f"imports {dotted!r}, which is not on the authorisation-path allowlist "
                  f"ALLOWED_IMPORT_ROOTS; an unlisted module may reach the network or a "
                  f"model indirectly, so it must be a reviewed trust-boundary decision "
                  f"(invariant 3.1, D71)")
    return Violation(path, lineno, detail)


def _scan_module(path: Path) -> list[Violation]:
    violations: list[Violation] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as e:
        return [Violation(path, e.lineno or 0, f"could not parse: {e}")]

    for node in ast.walk(tree):
        # import json / import boto3 / import requests: every absolute root must be
        # allowlisted (D71).
        if isinstance(node, ast.Import):
            for alias in node.names:
                v = _import_violation(alias.name, path, node.lineno)
                if v:
                    violations.append(v)
        # from . import x (relative, exempt); from urllib import request (absolute,
        # must be allowlisted).
        elif isinstance(node, ast.ImportFrom):
            if node.level and node.level > 0:
                continue  # relative intra-package import: exempt from the allowlist
            module = node.module or ""
            v = _import_violation(module, path, node.lineno)
            if v:
                violations.append(v)
        elif isinstance(node, ast.Call):
            target = _call_target(node.func)
            # subprocess / os.system shelling out to a model runner
            if target in {"subprocess.run", "subprocess.Popen", "subprocess.call",
                          "os.system", "os.popen"}:
                if _args_mention_model_runner(node):
                    violations.append(Violation(
                        path, node.lineno,
                        f"shells out to a model runner via {target} (invariant 3.1)"))
            # dynamic import: the textbook INDIRECT import of a module chosen at
            # runtime, which a static import scan cannot otherwise see.
            elif target in DYNAMIC_IMPORT_CALLS or target.endswith(".import_module"):
                violations.append(Violation(
                    path, node.lineno,
                    f"uses dynamic import {target!r}; the authorisation path must not "
                    f"import a module chosen at runtime (an indirect model import, "
                    f"invariant 3.1)"))
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


# Negative-control probes: sources the guard MUST flag, and sources it MUST NOT. The
# harness runs these before trusting a clean scan, so a guard that has been silently
# neutered (a swallowed exception, an over-broad allowlist, a dropped scope) is caught
# rather than reporting a hollow PASS. This is the mandatory-control discipline the
# project applies to every other check (invariant 3.10, D10); it was missing on the
# guard obligation itself (adversarial review round 2, finding 3.2).
_MUST_CATCH = (
    ("direct model import", "import mlx_lm\n"),
    ("from-import of a model client", "from openai import OpenAI\n"),
    ("dynamic import", "import importlib\nimportlib.import_module('mlx_lm')\n"),
    ("outbound HTTP to an inference endpoint", "import requests\nrequests.post('https://api.openai.com')\n"),
    ("model-runner subprocess", "import subprocess\nsubprocess.run(['ollama', 'run'])\n"),
    # Unlisted-egress probes (D71): these are on NO forbidden or network list, so a
    # blacklist would miss them; the allowlist must catch them, proving the boundary is
    # the allowlist and not the enumerated names. boto3 = AWS Bedrock hosted inference;
    # smtplib = stdlib egress.
    ("unlisted hosted-inference SDK (boto3)", "import boto3\n"),
    ("unlisted stdlib egress (smtplib)", "import smtplib\n"),
)
_MUST_NOT_CATCH = (
    ("graph-DB driver", "from neo4j import GraphDatabase\n"),
    ("store binding", "from memgraph_store import MemgraphReachability\n"),
    ("a 'model' comment", "# the model fills values only\nx = 1\n"),
    ("an allowlisted stdlib import", "import json\nimport re\n"),
    ("a relative intra-package import", "from . import yggdrasil\nfrom ..core import Node\n"),
)


def control_check() -> list[str]:
    """Run the negative control. Returns a list of failure descriptions (empty if the
    guard behaves): each MUST_CATCH source must produce at least one violation, and
    each MUST_NOT_CATCH source must produce none. A non-empty return means the guard
    itself is broken, which is more serious than any single scanned file."""
    import tempfile

    failures: list[str] = []
    d = Path(tempfile.mkdtemp())
    for label, src in _MUST_CATCH:
        f = d / "probe.py"
        f.write_text(src)
        if not _scan_module(f):
            failures.append(f"guard FAILED to catch a planted {label}")
    for label, src in _MUST_NOT_CATCH:
        f = d / "probe.py"
        f.write_text(src)
        if _scan_module(f):
            failures.append(f"guard WRONGLY flagged a benign {label}")
    return failures
