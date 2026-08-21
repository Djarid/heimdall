"""Invariant 3.6's invocation boundary: who actually calls Gjoll's gate (D96).

Run from the repo root:

    python -m ontology.tests.gjoll_invocation_harness

Why this exists. `ontology/nornir/gjoll.py` is the action-time gate enforcing invariant
3.6: correctly implemented, and exercised by five harness obligations including a
cross-domain staging case and a live-Memgraph run (D58, D63, D64, D89, D93). But nothing
in `engine.py` ever constructs a `gjoll.ActionProposal` or calls `gjoll.evaluate` or
`gjoll.enforce`: that wiring is Himinbjörg's job (`gjoll.md` section 2,
`himinbjorg.md` section 2), Himinbjörg is essentially unbuilt (D73, D74), and D74's
scoped R-1 exception explicitly excludes Gjöll's action-time gate from what may be
built early. That absence is the phase-mapped intended state, not a defect
(NEUROSYMBOLIC_FILTER_INVARIANTS.md section 5, Phase 1: "Gjöll dormant"). The risk is
not the absence itself; it is a PROSE caveat describing the absence going stale, which
already happened once (`AGENTS.md` line 90 described the D79-D82 mitigations as unwired
after D84 and D85 had wired them in). This module is the mechanised form of that
caveat, on the exact pattern `pipeline_score_harness.integration_status()` and
`print_integration_banner()` already use for a different wiring claim, and on the
allowlist polarity `ontology/nornir/symbolic_guard.py` uses for the invariant 3.1
import boundary (D71).

What it detects. Every site in the repo constructing `gjoll.ActionProposal` or calling
`gjoll.evaluate` or `gjoll.enforce`, resolved by AST through the actual import (a
`from ...gjoll import enforce`, a qualified `gjoll.enforce(...)` through a module alias
or both), never by a substring match on the name "enforce" or "evaluate" alone: an
unrelated function sharing that name elsewhere in the repo is not a Gjoll call site, and
a substring check could not tell the difference (the same AST-not-grep reasoning
`symbolic_guard.py` gives for why it parses rather than searches text).

Test-side only, by design. This module lives under `ontology/tests/`, so it never
touches invariant 3.1's authorisation-path scan scope
(`symbolic_guard._authorisation_files` covers only `ontology/yggdrasil/`,
`ontology/nornir/` and `poc/symbolic.py`, and excludes `ontology/tests/` by name). It
arms nothing, changes no authorisation-path byte, and the external test running against
this build is not measuring a moving target.

What it reports and what is fatal (design brief section 6, open question 1). The COUNT
of test call sites is reporting-only, never a failure: how many test harnesses invoke
the gate is evidence for invariant 3.6 being DEMONSTRATED, not a defect to fix, and the
count is expected to grow as more harnesses are added. A NON-TEST call site is fatal
ONLY if it is not on the designated `NON_TEST_ALLOWLIST` below, which is empty today
because nothing outside `ontology/tests/` calls the gate. The polarity matches
`ALLOWED_IMPORT_ROOTS` (D71): a non-test call site must be EARNED by a reviewed,
allowlisted entry, never granted by silence. The moment Himinbjörg (or anything else)
adds a real call site, this obligation fails loudly until that site is named on the
allowlist with a justification and a decision reference, which forces the wiring to be
a deliberate, reviewed act rather than a quiet import.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

# The three symbols this detector tracks, all exported by ontology/nornir/gjoll.py.
# Constructing ActionProposal or calling evaluate/enforce is what it means to invoke
# the gate; nothing else in gjoll.py (GateDecision, Actuator, CONSUME_INERT,
# CONSUME_ACTION) is itself a wiring call site.
GJOLL_SYMBOLS: frozenset[str] = frozenset({"ActionProposal", "evaluate", "enforce"})

# Directories never scanned: virtual environments and caches carry no repo-authored
# call site, and scanning them would slow this down for no signal.
_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({".venv", "__pycache__", ".git"})

# The gate's own definition file. Excluded for the same reason symbolic_guard.py
# excludes itself: `enforce`'s internal call to `evaluate` (gjoll.py:251) is the gate
# calling its own other half, not a wiring call site proposing an action, and counting
# it would report a spurious "non-test call site" inside the gate's own module on
# every run.
_GJOLL_DEFINITION_FILE = "gjoll.py"


@dataclass(frozen=True)
class NonTestAllowlistEntry:
    """A designated non-test call site permitted to construct `ActionProposal` or call
    `gjoll.evaluate`/`gjoll.enforce`. Adding an entry here is a deliberate, reviewed
    trust-boundary decision, on the same footing as adding a root to
    `ALLOWED_IMPORT_ROOTS` (the `hashlib` precedent, D94): it must carry a
    justification (why this call site is a reviewed wiring, not a quiet import) and a
    decision reference (the `DECISIONS.md` row that approved it), and the entry in
    this tuple should be preceded by an inline comment repeating both, so the reason
    is visible at the point of the edit and not only in this docstring."""

    path: str            # repo-relative path, e.g. "ontology/himinbjorg/control_surface.py"
    justification: str   # why this call site is a deliberate, reviewed wiring
    decision_ref: str    # the DECISIONS.md row that approved it, e.g. "D97"


# THE ALLOWLIST (D96, on the ALLOWED_IMPORT_ROOTS/D71 polarity). Empty today: nothing
# outside ontology/tests/ constructs ActionProposal or calls evaluate/enforce, because
# Himinbjörg (the intended caller, gjoll.md section 2, himinbjorg.md section 2) is
# essentially unbuilt (D73, D74) and D74's scoped R-1 exception explicitly excludes
# Gjöll's action-time gate from what may be wired before D67-fix closes. Widening this
# tuple is how a future session records the wiring as a reviewed decision rather than
# a change that happens to make this obligation pass; each addition needs its own
# comment naming the justification and the decision, following the pattern below.
NON_TEST_ALLOWLIST: tuple[NonTestAllowlistEntry, ...] = ()

for _entry in NON_TEST_ALLOWLIST:
    # Deliberately a real `raise`, not a bare `assert` (Minor 4, quality review): this
    # is meant to be an enforced control on a reviewed trust-boundary decision, not a
    # debug-only check, and Python removes `assert` entirely under `-O`, which would
    # silently disable this validation.
    if not (_entry.justification and _entry.decision_ref):
        raise ValueError(
            "a NON_TEST_ALLOWLIST entry must carry both a justification and a decision "
            "reference; see NonTestAllowlistEntry's docstring")


def _iter_repo_python_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for p in repo_root.rglob("*.py"):
        if any(part in _EXCLUDED_DIR_NAMES for part in p.parts):
            continue
        if p.name == _GJOLL_DEFINITION_FILE and p.parent.name == "nornir":
            continue
        files.append(p)
    return files


def _gjoll_bound_names(tree: ast.Module) -> dict[str, str]:
    """Names this module binds, by a direct `from ...gjoll import X [as Y]`, to one of
    GJOLL_SYMBOLS. Maps the bound local name to the canonical symbol name."""
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == "gjoll":
            for alias in node.names:
                if alias.name in GJOLL_SYMBOLS:
                    bound[alias.asname or alias.name] = alias.name
    return bound


def _gjoll_module_aliases(tree: ast.Module) -> set[str]:
    """Access paths (not just bound names) that resolve to the gjoll MODULE itself, so a
    qualified call (`gjoll.enforce(...)`, `g.ActionProposal(...)`,
    `ontology.nornir.gjoll.enforce(...)`) is resolved without a blind attribute-suffix
    match, the same alias-tracking shape symbolic_guard.py uses for `builtins` (D95).

    Important 1 (quality review, D96 follow-up): a plain `import a.b.gjoll` with no `as`
    binds ONLY the top-level name `a` in this module's namespace, not the leaf `gjoll`
    (https://docs.python.org/3/reference/import.html#the-import-statement). Reaching the
    module therefore requires the FULL dotted chain `a.b.gjoll.enforce(...)`, never the
    bare `gjoll.enforce(...)`: that bare form would in fact be a NameError at runtime,
    and treating it as a hit would be exactly the false-attribution risk this detector
    must avoid (an unrelated local object happening to be named `gjoll`). So for an
    unaliased `import a.b.gjoll` this function records the full dotted import path
    (`a.b.gjoll`), not the leaf, as the qualifying prefix; `_scan_module`'s
    `target.rpartition(".")` then matches that full prefix directly against a call
    target like `a.b.gjoll.enforce`. Only `import a.b.gjoll AS x` (or a bare
    `from ...nornir import gjoll [as x]`, which always binds a single name) records the
    short bound name, because that is genuinely the only name Python bound."""
    aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[-1] == "gjoll":
                    if alias.asname:
                        aliases.add(alias.asname)
                    else:
                        # No `as`: Python binds only the top-level package name, so the
                        # full dotted chain is required to reach the module. Recording
                        # the leaf `gjoll` here (the prior bug) would wrongly match a
                        # bare, unrelated `gjoll.enforce(...)` local reference.
                        aliases.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                if alias.name == "gjoll":
                    aliases.add(alias.asname or alias.name)
    return aliases


class _ParseFailure(Exception):
    """Raised by `_scan_module` when a file cannot be parsed (Important 2, quality
    review). `ontology/nornir/symbolic_guard.py`'s own `_scan_module` treats a
    `SyntaxError` as fail-closed (it returns a `Violation`, not an empty result); this
    detector must hold the same discipline, because "cannot verify this file" must
    never be read as "verified this file is clean". Caught by `_scan_repo` and
    surfaced as a fatal `parse_failures` entry, never silently swallowed into an empty
    hit list."""


def _call_target(func: ast.expr) -> str:
    """Dotted name of a call target, e.g. 'gjoll.enforce', or '' if not a plain
    attribute/name chain.

    Minor 3 (quality review): this duplicates
    `ontology/nornir/symbolic_guard.py`'s `_call_target` (currently lines 288-308)
    almost verbatim. Left duplicated rather than factored into a shared helper,
    because the only place a shared test-only helper could legally live is under
    `ontology/tests/`, and having `symbolic_guard.py` (inside
    `ontology/nornir/`, on the invariant-3.1 authorisation path) import from
    `ontology/tests/` for a ten-line function would add a real dependency edge from
    the authorisation path onto test code, which is a worse module-boundary cost than
    the duplication it would remove. If `symbolic_guard.py`'s copy moves, update the
    line reference here; this file's own copy is currently lines 185-206."""
    parts: list[str] = []
    cur = func
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def _scan_module(path: Path) -> list[int]:
    """Return the line numbers of every Gjoll call site (constructing ActionProposal,
    or calling evaluate/enforce) in this file, resolved through its own imports. Empty
    if this file imports none of GJOLL_SYMBOLS from gjoll, or imports them but never
    calls them.

    Raises `_ParseFailure` if the file cannot be parsed (Important 2, quality review):
    a `SyntaxError` here must never be swallowed into a silent empty result, on the
    same fail-closed discipline `symbolic_guard._scan_module` already applies (there,
    a parse failure becomes a `Violation`, not a clean scan)."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as e:
        raise _ParseFailure(f"{path}: could not parse: {e}") from e
    bound = _gjoll_bound_names(tree)
    module_aliases = _gjoll_module_aliases(tree)
    if not bound and not module_aliases:
        return []  # this file never imports anything from gjoll; nothing to resolve
    hits: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        target = _call_target(node.func)
        if not target:
            continue
        if target in bound:
            hits.append(node.lineno)
            continue
        obj, sep, attr = target.rpartition(".")
        if sep and obj in module_aliases and attr in GJOLL_SYMBOLS:
            hits.append(node.lineno)
    return sorted(hits)


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _scan_repo(repo_root: Path) -> tuple[dict[str, list[int]], list[str]]:
    """Scan every repo Python file for Gjoll call sites. Returns `(sites,
    parse_failures)`: `sites` maps repo-relative path to sorted hit line numbers;
    `parse_failures` lists repo-relative paths that could not be parsed (Important 2,
    quality review). A parse failure is never folded silently into an empty `sites`
    entry: a file this detector cannot read is reported as a failure to verify, not as
    evidence of a clean file, on the same fail-closed discipline
    `symbolic_guard._scan_module` already applies to its own parse failures."""
    sites: dict[str, list[int]] = {}
    parse_failures: list[str] = []
    for f in _iter_repo_python_files(repo_root):
        try:
            hits = _scan_module(f)
        except _ParseFailure as e:
            parse_failures.append(str(e))
            continue
        if hits:
            sites[str(f.relative_to(repo_root))] = hits
    return sites, sorted(parse_failures)


def gjoll_call_sites(repo_root: "Path | None" = None) -> dict[str, list[int]]:
    """Detect every site in the repo constructing gjoll.ActionProposal or calling
    gjoll.evaluate/gjoll.enforce. Returns a mapping of repo-relative file path to the
    sorted line numbers where a call site was found in that file. Does not
    distinguish test from non-test; `classify_call_sites` does that. Does not surface
    parse failures either (this function's return type has no room for them); callers
    that must not silently drop an unparseable file should use `classify_call_sites`,
    whose `parse_failures` key exists for exactly that reason."""
    if repo_root is None:
        repo_root = _default_repo_root()
    sites, _parse_failures = _scan_repo(repo_root)
    return sites


def _is_test_path(rel_path: str) -> bool:
    return Path(rel_path).parts[:2] == ("ontology", "tests")


def classify_call_sites(repo_root: "Path | None" = None) -> dict:
    """Classify every detected Gjoll call site as test (`ontology/tests/`) or
    non-test, and split non-test sites into allowlisted and unallowlisted. Returns a
    dict with `sites` (the raw file-to-lines map), `test_files`, `non_test_files`,
    `allowlisted_non_test`, `unallowlisted_non_test` (sorted lists of repo-relative
    paths) and `parse_failures` (Important 2, quality review: repo-relative paths, with
    the parser's own error text, that could not be parsed at all; fail-closed, not
    silently dropped from the scan; callers should treat a non-empty
    `parse_failures` as fatal, the same as an unallowlisted non-test call site)."""
    if repo_root is None:
        repo_root = _default_repo_root()
    sites, parse_failures = _scan_repo(repo_root)
    test_files = sorted(p for p in sites if _is_test_path(p))
    non_test_files = sorted(p for p in sites if not _is_test_path(p))
    allowed_paths = {e.path for e in NON_TEST_ALLOWLIST}
    allowlisted_non_test = [p for p in non_test_files if p in allowed_paths]
    unallowlisted_non_test = [p for p in non_test_files if p not in allowed_paths]
    return {
        "sites": sites,
        "test_files": test_files,
        "non_test_files": non_test_files,
        "allowlisted_non_test": allowlisted_non_test,
        "unallowlisted_non_test": unallowlisted_non_test,
        "parse_failures": parse_failures,
    }


# Negative-control probes (invariant 3.10, D10): before trusting a clean scan, confirm
# the detector actually catches a planted Gjoll call site, resolved either through a
# direct import or through a module alias, and does not flag a source that merely
# mentions the names without calling them through gjoll. A detector that cannot catch a
# planted call site is theatre, exactly as an uncontrolled soundness check would be.
_MUST_CATCH = (
    ("direct-import construction of ActionProposal",
     "from ontology.nornir.gjoll import ActionProposal\n"
     "p = ActionProposal('a', 'sink:x', {})\n"),
    ("direct-import call to enforce",
     "from ontology.nornir.gjoll import enforce\n"
     "enforce(None, {}, frozenset(), None)\n"),
    ("qualified call to evaluate through a bare-name module alias "
     "(`from ...nornir import gjoll as g`)",
     "from ontology.nornir import gjoll as g\n"
     "g.evaluate(None, {}, frozenset())\n"),
    # Important 1 (quality review): a plain `import a.b.gjoll` with NO `as` binds
    # only the top-level name `a`, so the call must be resolved through the FULL
    # dotted chain, not the bare leaf `gjoll`. This probe is the one that would have
    # been MISSED entirely by the pre-fix `_gjoll_module_aliases`, which recorded the
    # bare leaf and so never matched the qualified form actually reachable here.
    ("plain dotted import with no alias, called through the full dotted chain "
     "(`import a.b.gjoll` binds only `a`, not `gjoll`)",
     "import ontology.nornir.gjoll\n"
     "ontology.nornir.gjoll.enforce(None, {}, frozenset(), None)\n"),
    # Important 1: `import a.b.c as x` binds `x`; the reference is `x.enforce(...)`.
    ("dotted import with an explicit alias (`import a.b.gjoll as g`)",
     "import ontology.nornir.gjoll as g\n"
     "g.enforce(None, {}, frozenset(), None)\n"),
)
_MUST_NOT_CATCH = (
    ("a comment mentioning ActionProposal, no import",
     "# ActionProposal is constructed by the caller, not here\n"
     "x = 1\n"),
    ("an unrelated function also named enforce, imported from elsewhere",
     "from somewhere_else import enforce\n"
     "enforce(1, 2)\n"),
    ("importing gjoll but never calling one of its three symbols",
     "from ontology.nornir.gjoll import CONSUME_ACTION, GateDecision\n"
     "x = CONSUME_ACTION\n"),
    # Important 1's false-attribution control (quality review): a plain, unaliased
    # `import a.b.gjoll` binds ONLY the top-level name `a`, never the bare leaf
    # `gjoll`. So an unrelated local object that happens to be named `gjoll` must NOT
    # be caught merely because an (unused, in terms of that local) `import
    # ...gjoll` statement exists elsewhere in the file. Before the Important 1 fix,
    # `_gjoll_module_aliases` wrongly recorded the bare leaf `gjoll` for this exact
    # import form, which would have made this probe a false positive; this MUST NOT
    # CATCH locks that regression out.
    ("plain dotted import with no alias, plus an unrelated local object also named "
     "`gjoll` (the false-attribution risk the fix must not worsen)",
     "import ontology.nornir.gjoll\n"
     "\n"
     "class gjoll:\n"
     "    @staticmethod\n"
     "    def enforce(*args):\n"
     "        pass\n"
     "\n"
     "gjoll.enforce(1, 2, 3, 4)\n"),
)


def control_check() -> list[str]:
    """Run the negative control. Returns a list of failure descriptions (empty if the
    detector behaves): each MUST_CATCH source must produce at least one hit, each
    MUST_NOT_CATCH source must produce none, and a genuinely unparseable file must
    raise `_ParseFailure` rather than silently scanning clean (Important 2, quality
    review)."""
    import tempfile

    failures: list[str] = []
    d = Path(tempfile.mkdtemp())
    for label, src in _MUST_CATCH:
        f = d / "probe.py"
        f.write_text(src)
        if not _scan_module(f):
            failures.append(f"detector FAILED to catch a planted {label}")
    for label, src in _MUST_NOT_CATCH:
        f = d / "probe.py"
        f.write_text(src)
        if _scan_module(f):
            failures.append(f"detector WRONGLY flagged a benign source ({label})")

    # Fail-closed control (Important 2, quality review): a file that cannot be parsed
    # must be flagged, not silently treated as "no call sites found". Mirrors
    # symbolic_guard.py's own control discipline for its parse-failure handling.
    bad = d / "probe.py"
    bad.write_text("def broken(:\n    pass\n")
    try:
        _scan_module(bad)
    except _ParseFailure:
        pass
    else:
        failures.append(
            "detector FAILED to fail-closed on an unparseable file (returned a "
            "result instead of raising _ParseFailure)")
    return failures


def print_invocation_banner(repo_root: "Path | None" = None) -> bool:
    """Print the Gjoll invocation-boundary banner and return True unless an
    unallowlisted non-test call site exists.

    This is the mechanism that makes the invocation caveat self-maintaining, on the
    same pattern `pipeline_score_harness.print_integration_banner()` already
    established for a different wiring claim: a future session does not have to
    remember, in prose, that Gjoll's gate is invoked only from test harnesses. Running
    this states the count live and stops stating it the moment a non-test call site
    appears outside NON_TEST_ALLOWLIST."""
    status = classify_call_sites(repo_root)
    n_test = len(status["test_files"])
    n_non_test = len(status["non_test_files"])
    n_unallowlisted = len(status["unallowlisted_non_test"])
    n_parse_failures = len(status["parse_failures"])

    print(f"GJOLL INVOCATION BOUNDARY (detected live, not asserted): {n_test} test call "
          f"site(s), {n_non_test} non-test call site(s). Invariant 3.6 is DEMONSTRATED "
          f"under harness invocation only, not under live, non-test invocation.")
    for f in status["test_files"]:
        print(f"  + test call site: {f}")
    for f in status["allowlisted_non_test"]:
        entry = next(e for e in NON_TEST_ALLOWLIST if e.path == f)
        print(f"  + allowlisted non-test call site: {f} ({entry.decision_ref}: {entry.justification})")
    if n_unallowlisted:
        for f in status["unallowlisted_non_test"]:
            print(f"  [CRITICAL] unallowlisted non-test call site: {f}")
    if n_parse_failures:
        # Important 2, quality review: a file this detector could not parse is a
        # failure to verify, never silent evidence of a clean boundary.
        for pf in status["parse_failures"]:
            print(f"  [CRITICAL] could not parse (fail-closed, not silently skipped): {pf}")
    if n_unallowlisted or n_parse_failures:
        return False
    return True


def main() -> int:
    control_failures = control_check()
    if control_failures:
        print("GJOLL INVOCATION BOUNDARY negative control FAILED:")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    ok = print_invocation_banner()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
