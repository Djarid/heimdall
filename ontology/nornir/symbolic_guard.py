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
also flags `eval`/`exec`/`compile` unconditionally (D95), because a forbidden import
and call can both be smuggled inside a string literal passed to one of them, invisible
to the `ast.Import`/`ast.ImportFrom`/call-target checks above since the smuggled code
is never parsed by `ast.parse` on the outer module.

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
    # hashlib (D94, direction C): stdlib SHA-256 for the declaration-attestation
    # integrity check. Added as a DELIBERATE, REVIEWED trust-boundary decision in the
    # spirit of D71: it is a hashing primitive, not a model client and not a network
    # module, and it reaches neither the network nor a model. It computes a keyed digest
    # over a declaration's canonical bytes to verify who declared it; there is no other
    # use of it on the authorisation path. This is exactly the "adding a root is a
    # reviewed decision" case the allowlist is designed to force.
    "hashlib",
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

# Dynamic code-execution builtins (D95): the textbook route by which a forbidden import
# AND a forbidden call can both be smuggled inside a string literal, invisible to the
# ast.Import/ast.ImportFrom and call-target checks above, because the code inside the
# string is never parsed by ast.parse on the outer module. For example, `exec("import
# requests\nrequests.post(...)")` produces no ast.Import node the scanner can see. The
# authorisation path has no legitimate need to evaluate or execute code assembled at
# runtime, so ANY use is a violation, regardless of what the string contains. The
# guard does not inspect the string content: scanning string content for suspicious
# text is exactly the blacklist-by-content mistake this project rejects elsewhere
# (invariant 3.5); the violation is triggered by the CALL ITSELF, unconditionally.
DYNAMIC_CODE_EXECUTION_CALLS = frozenset({"eval", "exec", "compile"})

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


def _builtins_aliases(tree: ast.Module) -> set[str]:
    """Names this module binds to the `builtins` module itself (Important 1, D95): a
    narrowly-scoped alias resolver, only for `builtins`, not a general import-alias
    resolver. `import builtins` binds the name `builtins`; `import builtins as bi`
    binds `bi`. Used so a qualified call like `bi.eval(...)` is recognised as
    code-execution even when aliased, WITHOUT a blind `target.endswith(".eval")`-style
    check: that broad style is deliberately rejected here (see the comment on the
    qualified-call check in `_scan_module`) because it would flag every unrelated
    `re.compile(...)` call on the scanned path."""
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "builtins":
                    aliases.add(alias.asname or alias.name)
    return aliases


def _is_aliased_builtins_call(target: str, builtins_aliases: set[str]) -> bool:
    """True if `target` is a qualified call whose object half is a name THIS module
    bound to `builtins` (e.g. `bi.eval` when `import builtins as bi` was seen) and
    whose attribute half is one of DYNAMIC_CODE_EXECUTION_CALLS. Deliberately not a
    suffix match (Important 1, Important 3, D95): see the comment at the call site."""
    obj, sep, attr = target.rpartition(".")
    return bool(sep) and obj in builtins_aliases and attr in DYNAMIC_CODE_EXECUTION_CALLS


def _scan_module(path: Path) -> list[Violation]:
    violations: list[Violation] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as e:
        return [Violation(path, e.lineno or 0, f"could not parse: {e}")]

    # Resolve names bound to the `builtins` module in THIS file only, so a qualified
    # call like `bi.eval(...)` can be matched to DYNAMIC_CODE_EXECUTION_CALLS below
    # without a blind suffix match (Important 1, D95).
    builtins_aliases = _builtins_aliases(tree)

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
            # runtime, which a static import scan cannot otherwise see. This uses a
            # broad `endswith(".import_module")` suffix match deliberately: unlike the
            # code-execution check below, there is no common unrelated call on the
            # scanned path shaped like `x.import_module(...)`, so the wider net carries
            # no false-positive risk here and a shared helper with the narrower
            # code-execution check would only weaken that check for no benefit
            # (Important 4, D95).
            elif target in DYNAMIC_IMPORT_CALLS or target.endswith(".import_module"):
                violations.append(Violation(
                    path, node.lineno,
                    f"uses dynamic import {target!r}; the authorisation path must not "
                    f"import a module chosen at runtime (an indirect model import, "
                    f"invariant 3.1)"))
            # dynamic code execution (D95): the textbook route by which a forbidden
            # import AND a forbidden call can both be smuggled inside a string literal,
            # invisible to the import/call-target checks above because the smuggled
            # code is never parsed by ast.parse on the outer module. Any use is a
            # violation, unconditionally; the string content is deliberately not
            # inspected (invariant 3.5).
            #
            # The qualified form deliberately does NOT use a broad
            # `target.endswith(".eval")`/`.endswith(".compile")` suffix match, unlike
            # the dynamic-import check above (Important 1, Important 4, D95): `.compile`
            # is the attribute name on `re.compile(...)`, used 11+ times in rules.py and
            # every domain_rules/*.py module on the real scanned path, so that style
            # would make the most load-bearing check in the repository fail on its own
            # substrate. Instead the object half of the qualified name is checked
            # against builtins_aliases, the names THIS module actually bound to the
            # `builtins` module (see _builtins_aliases), so `bi.eval(...)` is caught
            # when `bi` really is `builtins` and `re.compile(...)` is never touched
            # because `re` is never bound to `builtins`.
            elif target in DYNAMIC_CODE_EXECUTION_CALLS or _is_aliased_builtins_call(
                target, builtins_aliases):
                violations.append(Violation(
                    path, node.lineno,
                    f"uses {target!r}; the authorisation path must not evaluate or "
                    f"execute code assembled at runtime, which can smuggle a forbidden "
                    f"import and call inside a string literal invisible to static "
                    f"import/call scanning (invariant 3.1)"))
    return violations


def _call_target(func: ast.expr) -> str:
    """Dotted name of a call target, e.g. 'subprocess.run', or '' if not a plain
    attribute/name chain.

    Minor 3 (quality review): `ontology/tests/gjoll_invocation_harness.py`'s
    `_call_target` (currently lines 185-206) duplicates this function almost
    verbatim. Left duplicated rather than factored into a shared helper: the only
    place a shared test-only helper could legally live is under `ontology/tests/`,
    and this module (on the invariant-3.1 authorisation path) importing from
    `ontology/tests/` for a ten-line function would add a real dependency edge from
    the authorisation path onto test code, a worse module-boundary cost than the
    duplication it would remove. If this function moves, update the line reference
    in the other file; this copy is currently lines 288-308."""
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
    # Dynamic code-execution probes: the smuggled import-and-call is inside a string
    # literal, invisible to ast.Import/ast.ImportFrom and call-target detection on the
    # outer module; only the unconditional eval/exec/compile check catches these.
    ("string-smuggled exec of import and network call",
     "exec(\"import requests\\nrequests.post('https://api.openai.com')\")\n"),
    ("string-smuggled eval wrapping compile",
     "eval(compile(\"import requests\\nrequests.post('https://api.openai.com')\", "
     "'<string>', 'exec'))\n"),
    ("bare compile call", "compile(\"import mlx_lm\", '<string>', 'exec')\n"),
    # Qualified/aliased builtins call (Important 2, D95): the three probes above are
    # all bare names (eval/exec/compile), so none of them exercise the qualified-call
    # branch (_is_aliased_builtins_call). This probe does, so a future regression in
    # that branch is caught by the guard's own self-test rather than silently missed.
    ("aliased builtins.eval call",
     "import builtins as bi\nbi.eval(\"import mlx_lm\")\n"),
)
_MUST_NOT_CATCH = (
    ("graph-DB driver", "from neo4j import GraphDatabase\n"),
    ("store binding", "from memgraph_store import MemgraphReachability\n"),
    ("a 'model' comment", "# the model fills values only\nx = 1\n"),
    ("an allowlisted stdlib import", "import json\nimport re\n"),
    ("a relative intra-package import", "from . import yggdrasil\nfrom ..core import Node\n"),
    # hashlib is allowlisted for the D94 declaration-attestation digest (a hashing
    # primitive, not a model or network module). This probe documents that it is
    # intentionally permitted and would fail if a future edit dropped it from the
    # allowlist, so the reviewed decision cannot silently regress.
    ("the attestation hashing primitive", "import hashlib\nhashlib.sha256(b'x')\n"),
    # Locks in Important 1/3 (D95): re.compile(...) is the single most common
    # qualified-call shape on the real scanned path (11+ uses in rules.py and every
    # domain_rules/*.py module). A carelessly-widened code-execution check (e.g. a
    # blind `target.endswith(".compile")` suffix match) would flag it; the
    # alias-scoped check in _is_aliased_builtins_call must not.
    ("an unrelated qualified .compile call (re.compile)", "import re\nre.compile('x')\n"),
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
