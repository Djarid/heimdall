"""Himinbjörg's invocation boundary (D111, `.opencode/plans/himinbjorg-step-three.md`
REQ-28): who actually calls the four public interfaces, who actually calls Gjöll's
gate through this crate, and whether this crate loads its own verified cohort, on
`ontology.tests.vor_invocation_harness`'s token-scan precedent (itself on D96's,
`gjoll_invocation_harness.py`'s, AST-based original).

Run from the repo root:

    python -m ontology.tests.himinbjorg_invocation_harness

Why this exists, on the same footing as D96's and D110's own caveats. `crates/himinbjorg/`
proves the four-interface slice is real (`ontology.tests.rust_gateway_harness` proves its
mechanical posture); it says NOTHING about whether anything, anywhere, actually CALLS
those four interfaces outside this crate's own tests, or about whether Gjöll's gate --
reached from inside this crate at check five -- is itself invoked by anything beyond
that one, single, deliberately-placed call site. Both are DIFFERENT and separately
governed claims from "the gateway is built": the process engine that would call
Himinbjörg's four interfaces is step five, not yet built (section 10 of the step-three
spec). This module is the mechanised form of that fact, on the exact pattern
`vor_invocation_harness.py` and `gjoll_invocation_harness.py` already established, so a
future session does not have to remember it in prose.

**Section 10's own sentence, stated here live, not only in a comment (REQ-28's closing
requirement):** one non-test Rust caller of the gate inside a crate that itself has zero
non-test callers does NOT advance invariant 3.6. "The gate now has one non-test caller in
Rust, in a crate nothing calls" is not "the gate is invoked live against a real action".

Three symbol groups tracked, each answering a different question:

  1. Himinbjörg's own four public interfaces (`build_context`, `enforce_definition`,
     `validate_proposal`, `broker_action`), scanned across the WHOLE repo. Expected
     zero non-test call sites on the day this lands: nothing outside this crate's own
     tests calls them yet.

     A real collision risk exists and is handled explicitly: `boundary-gjoll` declares
     its OWN, unrelated `declaration::validate_proposal` (the D81 five-condition
     validator), reached as a bare `validate_proposal(...)` after
     `use boundary_gjoll::declaration::{..., validate_proposal, ...};` inside its own
     `consequentiality.rs` (a genuine, non-test call, but to a DIFFERENT function of the
     same bare name). A naive bare-name scan (this module's own group 3, and
     `vor_invocation_harness.py`'s whole design) would misattribute that call to
     Himinbjörg. This group is therefore resolved through the crate boundary instead: a
     call counts only when it is reached through `himinbjorg::<name>(...)` (fully
     qualified), through `crate::<name>(...)` from WITHIN `crates/himinbjorg/` itself
     (where `crate::` genuinely means this crate), or through a bare call whose name was
     bound in this file's own scope by a `use himinbjorg::<name> [as alias];` or
     `use himinbjorg::{..., <name>, ...};` import. `boundary-gjoll`'s own
     `declaration::validate_proposal` binds no such name and is never counted.
  2. `boundary_gjoll::consequentiality::evaluate`, scanned across the WHOLE repo.
     Expected EXACTLY ONE non-test call site, inside `crates/himinbjorg/src/gate_bridge.rs`
     (check five, REQ-15). This is an EXPLICIT ALLOWLISTED COUNT CHECK
     (`GATE_CALL_ALLOWLIST`), on `ALLOWED_IMPORT_ROOTS`'s (D71) and
     `gjoll_invocation_harness.NON_TEST_ALLOWLIST`'s (D96) own polarity, but inverted in
     degree: those two allowlists permit UP TO a named set of entries; this one requires
     EXACTLY the one entry it names, so both a second unlisted call site AND the
     allowlisted site disappearing or duplicating are equally fatal. A future second
     call site is a reviewed act, never a silent one (EC-18).

     Resolved the same way group 1 is: a fully or partially qualified call
     (`consequentiality::evaluate(`, reached through any prefix ending in that module
     path) always counts; a bare `evaluate(...)` counts only when this file's own scope
     bound that name from a `use ...consequentiality::evaluate [as alias];` or
     `use ...consequentiality::{..., evaluate, ...};` import, because `evaluate` alone
     is far too common a bare name to scan for unresolved (`boundary-gjoll`'s own crate
     defines it, and nothing rules out an unrelated `evaluate` fn appearing elsewhere).
  3. `hierarchy_vor::load_verified_cohort`, scanned ONLY inside `crates/himinbjorg/`
     (REQ-28's own scoping: "expected to be zero inside this crate"). Expected zero
     non-test call sites: step three takes an already-verified cohort by reference and
     never loads one itself; the loading call site belongs to step five. Unlike groups 1
     and 2, this symbol has no other definition anywhere in the crates tree (confirmed
     directly), so a simple bare word-boundary scan, comments and strings stripped, is
     sufficient and needs no import-resolution step (`vor_invocation_harness.py`'s own,
     simpler precedent for this exact symbol).

What it detects, and the honest limit of how, on `vor_invocation_harness.py`'s own
disclosed weakness. This is a TOKEN scan, not an AST scan: Python has no built-in Rust
parser, so this module strips `//` and `/* */` comments (nesting-aware) and
string/byte-string/raw-string literals with the same hand-written state machine
`vor_invocation_harness.py` uses (duplicated here, not imported, following this
repository's own convention of duplicating a short, test-only helper across sibling
harnesses -- see `gjoll_invocation_harness.py`'s own comment on why `_call_target` is
duplicated rather than shared). The import-resolution added for groups 1 and 2 is
itself a regex-based approximation of Rust's `use` grammar, not a real parser: it
handles the two `use` shapes this repository's own code actually uses (a single-item
`use path::name [as alias];` and a braced group `use path::{a, b as c, ...};`), and a
`use path::*;` glob import, or a `use` spanning multiple lines with a nested `{}` group,
would not be resolved by it. Neither shape appears anywhere in this repository's Rust
source today (confirmed directly); if one is added later, this module's own
`unscanned_files`-style fail-closed reporting does not cover that gap, because it is a
resolution gap, not a tokenisation failure, and is named here rather than silently
assumed away.

Test-side only, by design. This module lives under `ontology/tests/`, exactly as
`vor_invocation_harness.py` and `gjoll_invocation_harness.py` do, so it never touches
invariant 3.1's authorisation-path scan scope and arms nothing.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Directories never scanned: build output and caches carry no repo-authored call
# site, and scanning them would slow this down for no signal (vor_invocation_harness.py's
# own precedent).
_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({".git", "target", ".venv", "__pycache__"})

INTERFACE_SYMBOLS: frozenset[str] = frozenset(
    {"build_context", "enforce_definition", "validate_proposal", "broker_action"}
)

# The crate's own path, in parts, used both to decide when `crate::<name>(` genuinely
# means "himinbjorg's own crate root" (group 1) and to scope group 3's scan.
_HIMINBJORG_CRATE_DIR: tuple[str, ...] = ("crates", "himinbjorg")


@dataclass(frozen=True)
class NonTestAllowlistEntry:
    """A designated non-test call site of `boundary_gjoll::consequentiality::evaluate`
    permitted to exist, on `gjoll_invocation_harness.NonTestAllowlistEntry`'s own shape
    (D96, itself on `ALLOWED_IMPORT_ROOTS`'s/D71's polarity). Unlike that allowlist,
    which permits UP TO its named entries, `GATE_CALL_ALLOWLIST` below requires EXACTLY
    the one entry it names (REQ-28): the check this module runs fails if the live count
    of non-test call sites is anything other than one, whether that is because a second,
    unlisted site appeared, or because the one allowlisted site vanished."""

    path: str            # repo-relative path, e.g. "crates/himinbjorg/src/gate_bridge.rs"
    justification: str   # why this call site is a deliberate, reviewed wiring
    decision_ref: str    # the DECISIONS.md row that approved it, e.g. "D111"


# THE ALLOWLIST (REQ-28, on the ALLOWED_IMPORT_ROOTS/D71 and D96 polarity, inverted in
# degree: exactly one entry is required, not merely permitted). This is check five's
# own real call into the gate (REQ-15, REQ-17); widening this tuple to a second entry
# is how a future session would record a genuinely new call site as a reviewed
# decision, never as a change that happens to make this obligation pass by accident.
GATE_CALL_ALLOWLIST: tuple[NonTestAllowlistEntry, ...] = (
    NonTestAllowlistEntry(
        path="crates/himinbjorg/src/gate_bridge.rs",
        justification=(
            "check five's real call into boundary_gjoll::consequentiality::evaluate "
            "(REQ-15, REQ-17 of the himinbjorg step-three spec): the crate's one, "
            "deliberately singular, non-test call site of the gate"
        ),
        decision_ref="D111",
    ),
)

for _entry in GATE_CALL_ALLOWLIST:
    # A real `raise`, not a bare `assert` (following gjoll_invocation_harness.py's own
    # Minor-4 fix): this is meant to be an enforced control on a reviewed
    # trust-boundary decision, not a debug-only check, and Python removes `assert`
    # entirely under `-O`, which would silently disable this validation.
    if not (_entry.justification and _entry.decision_ref):
        raise ValueError(
            "a GATE_CALL_ALLOWLIST entry must carry both a justification and a "
            "decision reference; see NonTestAllowlistEntry's docstring")


def _default_repo_root() -> Path:
    return REPO_ROOT


def _iter_repo_rust_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for p in repo_root.rglob("*.rs"):
        if any(part in _EXCLUDED_DIR_NAMES for part in p.parts):
            continue
        files.append(p)
    return files


def _is_test_path(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return "unit_tests" in parts or "tests" in parts


def _is_within_himinbjorg_crate(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return parts[: len(_HIMINBJORG_CRATE_DIR)] == _HIMINBJORG_CRATE_DIR


# ---------------------------------------------------------------------------------
# The tokeniser: strips `//` and `/* */` comments (nesting-aware) and
# string/byte-string/raw-string literals, exactly as
# `vor_invocation_harness._strip_comments_and_strings` does. Duplicated, not
# imported, following this repository's own duplication convention for a short,
# test-only helper across sibling harnesses (`gjoll_invocation_harness.py`'s own
# comment on `_call_target` states the reasoning).
# ---------------------------------------------------------------------------------


def _strip_comments_and_strings(src: str) -> tuple[str, bool]:
    """Returns `(cleaned, unscannable)`. See `vor_invocation_harness.py`'s own,
    identical function for the full account of what this hand-written token scan
    can and cannot distinguish (it is not a lexer, and does not disambiguate a
    character literal from a lifetime)."""
    out: list[str] = []
    i = 0
    n = len(src)
    unscannable = False

    def emit_masked(s: str) -> None:
        for ch in s:
            out.append("\n" if ch == "\n" else " ")

    def preceded_by_ident_char() -> bool:
        return i > 0 and (src[i - 1].isalnum() or src[i - 1] == "_")

    while i < n:
        two = src[i : i + 2]

        if two == "//":
            j = src.find("\n", i)
            if j == -1:
                emit_masked(src[i:])
                i = n
            else:
                emit_masked(src[i:j])
                i = j
            continue

        if two == "/*":
            depth = 1
            j = i + 2
            while j < n and depth > 0:
                if src[j : j + 2] == "/*":
                    depth += 1
                    j += 2
                elif src[j : j + 2] == "*/":
                    depth -= 1
                    j += 2
                else:
                    j += 1
            if depth != 0:
                unscannable = True
                emit_masked(src[i:])
                i = n
            else:
                emit_masked(src[i:j])
                i = j
            continue

        raw_m = re.match(r'(b)?r(#*)"', src[i : i + 8])
        if raw_m and not preceded_by_ident_char():
            hashes = raw_m.group(2)
            start = i + raw_m.end()
            closer = '"' + hashes
            j = src.find(closer, start)
            if j == -1:
                unscannable = True
                emit_masked(src[i:])
                i = n
            else:
                end = j + len(closer)
                emit_masked(src[i:end])
                i = end
            continue

        if two == 'b"' and not preceded_by_ident_char():
            j = i + 2
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" and j + 1 < n else 1
            if j >= n:
                unscannable = True
                emit_masked(src[i:])
                i = n
            else:
                j += 1
                emit_masked(src[i:j])
                i = j
            continue

        if src[i] == '"':
            j = i + 1
            while j < n and src[j] != '"':
                j += 2 if src[j] == "\\" and j + 1 < n else 1
            if j >= n:
                unscannable = True
                emit_masked(src[i:])
                i = n
            else:
                j += 1
                emit_masked(src[i:j])
                i = j
            continue

        out.append(src[i])
        i += 1

    return "".join(out), unscannable


# ---------------------------------------------------------------------------------
# Group 1: Himinbjörg's own four public interfaces (REQ-28 bullet 1).
# ---------------------------------------------------------------------------------

_QUALIFIED_INTERFACE_CALL_RE = re.compile(
    r"\bhiminbjorg::(build_context|enforce_definition|validate_proposal|broker_action)\s*\("
)
_CRATE_INTERFACE_CALL_RE = re.compile(
    r"\bcrate::(build_context|enforce_definition|validate_proposal|broker_action)\s*\("
)
_USE_HIMINBJORG_SINGLE_RE = re.compile(
    r"use\s+himinbjorg::(\w+)(?:\s+as\s+(\w+))?\s*;"
)
_USE_HIMINBJORG_GROUP_RE = re.compile(r"use\s+himinbjorg::\{([^}]*)\}\s*;")


def _himinbjorg_bound_names(cleaned: str) -> set[str]:
    """Names bound in this file's own scope that resolve to one of
    `INTERFACE_SYMBOLS` via a `use himinbjorg::...` import, mirroring
    `gjoll_invocation_harness._gjoll_bound_names`'s own resolution shape for
    Python, expressed here as a Rust token scan (see the module docstring for
    exactly which `use` shapes this resolves)."""
    bound: set[str] = set()
    for name, alias in _USE_HIMINBJORG_SINGLE_RE.findall(cleaned):
        if name in INTERFACE_SYMBOLS:
            bound.add(alias or name)
    for group_body in _USE_HIMINBJORG_GROUP_RE.findall(cleaned):
        for item in group_body.split(","):
            item = item.strip()
            if not item:
                continue
            parts = [p.strip() for p in item.split(" as ")]
            name = parts[0]
            alias = parts[1] if len(parts) > 1 else None
            if name in INTERFACE_SYMBOLS:
                bound.add(alias or name)
    return bound


def _interface_call_sites(cleaned: str, rel_path: str) -> list[int]:
    """Line numbers of every call to one of Himinbjörg's four public interfaces in
    this already-comment-and-string-stripped file. See the module docstring for
    why `boundary-gjoll`'s own, unrelated `declaration::validate_proposal` is never
    misattributed here: only a `himinbjorg::`-qualified call, a `crate::`-qualified
    call from genuinely within `crates/himinbjorg/`, or a bare call whose name this
    file's own `use himinbjorg::...` import bound, ever counts."""
    hits: set[int] = set()
    for m in _QUALIFIED_INTERFACE_CALL_RE.finditer(cleaned):
        hits.add(cleaned.count("\n", 0, m.start()) + 1)
    if _is_within_himinbjorg_crate(rel_path):
        for m in _CRATE_INTERFACE_CALL_RE.finditer(cleaned):
            hits.add(cleaned.count("\n", 0, m.start()) + 1)
    for bound_name in _himinbjorg_bound_names(cleaned):
        for m in re.finditer(rf"(?<!::){re.escape(bound_name)}\s*\(", cleaned):
            hits.add(cleaned.count("\n", 0, m.start()) + 1)
    return sorted(hits)


# ---------------------------------------------------------------------------------
# Group 2: boundary_gjoll::consequentiality::evaluate (REQ-28 bullet 2, EC-18).
# ---------------------------------------------------------------------------------

_QUALIFIED_EVALUATE_CALL_RE = re.compile(r"consequentiality::evaluate\s*\(")
_USE_EVALUATE_SINGLE_RE = re.compile(
    r"use\s+[\w:]*consequentiality::evaluate(?:\s+as\s+(\w+))?\s*;"
)
_USE_EVALUATE_GROUP_RE = re.compile(r"use\s+[\w:]*consequentiality::\{([^}]*)\}\s*;")


def _evaluate_bound_names(cleaned: str) -> set[str]:
    """Names bound in this file's own scope that resolve to
    `boundary_gjoll::consequentiality::evaluate` via a `use ...consequentiality::
    evaluate [as alias];` or `use ...consequentiality::{..., evaluate, ...};`
    import. `evaluate` alone is far too common a bare name to scan for unresolved
    (`boundary-gjoll` itself defines the only `fn evaluate` in the crates tree, but
    nothing rules out an unrelated one appearing elsewhere later), so a bare call
    counts only when this resolution step actually bound it."""
    bound: set[str] = set()
    for alias in _USE_EVALUATE_SINGLE_RE.findall(cleaned):
        bound.add(alias or "evaluate")
    for group_body in _USE_EVALUATE_GROUP_RE.findall(cleaned):
        for item in group_body.split(","):
            item = item.strip()
            if not item:
                continue
            parts = [p.strip() for p in item.split(" as ")]
            name = parts[0]
            alias = parts[1] if len(parts) > 1 else None
            if name == "evaluate":
                bound.add(alias or "evaluate")
    return bound


def _evaluate_call_sites(cleaned: str) -> list[int]:
    """Line numbers of every call to `boundary_gjoll::consequentiality::evaluate`
    in this already-stripped file, whether reached by a fully or partially
    qualified path (any prefix ending in `consequentiality::evaluate(`) or by a
    bare call after this file's own scope bound that name from a `use` import
    naming the `consequentiality` module specifically."""
    hits: set[int] = set()
    for m in _QUALIFIED_EVALUATE_CALL_RE.finditer(cleaned):
        hits.add(cleaned.count("\n", 0, m.start()) + 1)
    for bound_name in _evaluate_bound_names(cleaned):
        for m in re.finditer(rf"(?<!::){re.escape(bound_name)}\s*\(", cleaned):
            hits.add(cleaned.count("\n", 0, m.start()) + 1)
    return sorted(hits)


# ---------------------------------------------------------------------------------
# Group 3: hierarchy_vor::load_verified_cohort, scoped to crates/himinbjorg/ only
# (REQ-28 bullet 3). No other definition of this name exists anywhere in the
# crates tree (confirmed directly), so a bare word-boundary scan needs no
# import-resolution step, on `vor_invocation_harness.py`'s own, simpler precedent
# for this exact symbol.
# ---------------------------------------------------------------------------------

_LOAD_VERIFIED_COHORT_RE = re.compile(r"\bload_verified_cohort\b")


def _load_verified_cohort_call_sites(cleaned: str) -> list[int]:
    return sorted(
        {cleaned.count("\n", 0, m.start()) + 1 for m in _LOAD_VERIFIED_COHORT_RE.finditer(cleaned)}
    )


# ---------------------------------------------------------------------------------
# The unified scan: one tokenisation pass per file, feeding all three groups.
# ---------------------------------------------------------------------------------


@dataclass
class ScanResult:
    interface_sites: dict[str, list[int]] = field(default_factory=dict)
    evaluate_sites: dict[str, list[int]] = field(default_factory=dict)
    cohort_sites: dict[str, list[int]] = field(default_factory=dict)
    unscanned_files: list[str] = field(default_factory=list)


def scan_repo(repo_root: "Path | None" = None) -> ScanResult:
    """Scan every repo `.rs` file once, feeding all three symbol groups from the
    same tokenised text. An unscannable file (an unterminated block comment or
    string, EC-19's own precedent) is reported once and contributes no hits to
    any of the three groups: a file this detector cannot verify is a failure to
    verify, never silent evidence of a clean boundary."""
    if repo_root is None:
        repo_root = _default_repo_root()
    result = ScanResult()
    for f in _iter_repo_rust_files(repo_root):
        rel = str(f.relative_to(repo_root))
        src = f.read_text(encoding="utf-8", errors="replace")
        cleaned, unscannable = _strip_comments_and_strings(src)
        if unscannable:
            result.unscanned_files.append(rel)
            continue
        interface_hits = _interface_call_sites(cleaned, rel)
        if interface_hits:
            result.interface_sites[rel] = interface_hits
        evaluate_hits = _evaluate_call_sites(cleaned)
        if evaluate_hits:
            result.evaluate_sites[rel] = evaluate_hits
        if _is_within_himinbjorg_crate(rel):
            cohort_hits = _load_verified_cohort_call_sites(cleaned)
            if cohort_hits:
                result.cohort_sites[rel] = cohort_hits
    result.unscanned_files.sort()
    return result


def classify(sites: dict[str, list[int]]) -> tuple[list[str], list[str]]:
    """Splits a file-to-lines map into `(test_files, non_test_files)`, both
    sorted."""
    test_files = sorted(p for p in sites if _is_test_path(p))
    non_test_files = sorted(p for p in sites if not _is_test_path(p))
    return test_files, non_test_files


# ---------------------------------------------------------------------------------
# Negative-control probes (invariant 3.10, D10): before trusting a clean scan,
# confirm each of the three groups actually catches a planted call site (and, for
# group 1, that it does NOT misattribute boundary-gjoll's own unrelated
# `validate_proposal` function), and does not flag a benign mention.
# ---------------------------------------------------------------------------------


def _scan_source(src: str) -> tuple[list[int], list[int], list[int], bool]:
    cleaned, unscannable = _strip_comments_and_strings(src)
    if unscannable:
        return [], [], [], True
    return (
        _interface_call_sites(cleaned, "crates/himinbjorg/src/probe.rs"),
        _evaluate_call_sites(cleaned),
        _load_verified_cohort_call_sites(cleaned),
        False,
    )


def control_check() -> list[str]:
    """Run the negative controls. Returns a list of failure descriptions (empty
    if every control bites)."""
    failures: list[str] = []

    # Group 1 must-catch: a qualified call, and a bare call reached through a
    # genuine himinbjorg import.
    hits, _e, _c, bad = _scan_source(
        'let d = himinbjorg::validate_proposal(&ctx, &surf, &prop);\n'
    )
    if bad or not hits:
        failures.append("group 1 FAILED to catch a qualified himinbjorg::validate_proposal(...) call")

    hits, _e, _c, bad = _scan_source(
        'use himinbjorg::{validate_proposal, build_context};\n'
        'let d = validate_proposal(&ctx, &surf, &prop);\n'
    )
    if bad or not hits:
        failures.append(
            "group 1 FAILED to catch a bare validate_proposal(...) call bound by a "
            "genuine `use himinbjorg::{...}` import"
        )

    # Group 1 must-not-catch: the exact collision this module's docstring names --
    # boundary-gjoll's own, unrelated declaration::validate_proposal, reached bare
    # after importing it from `boundary_gjoll::declaration`, never from
    # `himinbjorg`.
    hits, _e, _c, bad = _scan_source(
        'use boundary_gjoll::declaration::{validate_proposal, SinkRegistry};\n'
        'let outcome = validate_proposal("sink:x", &consumes, &registry, &known_ids);\n'
    )
    if bad:
        failures.append("group 1 reported UNSCANNABLE for a benign, tokenisable source")
    elif hits:
        failures.append(
            "group 1 WRONGLY attributed boundary-gjoll's own, unrelated "
            "declaration::validate_proposal to Himinbjörg (the exact collision this "
            "module's docstring names)"
        )

    # Group 2 must-catch: a fully qualified call, and a bare call bound by a
    # genuine `use ...consequentiality::evaluate;` import.
    hits_i, hits_e, _c, bad = _scan_source(
        'let d = boundary_gjoll::consequentiality::evaluate(&p, &c, &r);\n'
    )
    if bad or not hits_e:
        failures.append("group 2 FAILED to catch a qualified consequentiality::evaluate(...) call")

    hits_i, hits_e, _c, bad = _scan_source(
        'use boundary_gjoll::consequentiality::evaluate;\n'
        'let d = evaluate(&p, &c, &r);\n'
    )
    if bad or not hits_e:
        failures.append(
            "group 2 FAILED to catch a bare evaluate(...) call bound by a genuine "
            "`use ...consequentiality::evaluate;` import"
        )

    # Group 2 must-not-catch: an unrelated bare `evaluate(...)` with no
    # consequentiality import in scope at all.
    hits_i, hits_e, _c, bad = _scan_source(
        'fn evaluate(x: i32) -> i32 { x }\n'
        'let y = evaluate(1);\n'
    )
    if bad:
        failures.append("group 2 reported UNSCANNABLE for a benign, tokenisable source")
    elif hits_e:
        failures.append(
            "group 2 WRONGLY flagged an unrelated bare evaluate(...) call with no "
            "consequentiality import in scope"
        )

    # Group 3 must-catch and must-not-catch: a real call, and a comment-only
    # mention.
    _i, _e, hits_c, bad = _scan_source('let c = hierarchy_vor::load_verified_cohort(&t);\n')
    if bad or not hits_c:
        failures.append("group 3 FAILED to catch a planted load_verified_cohort(...) call")

    _i, _e, hits_c, bad = _scan_source(
        '// load_verified_cohort is called by step five, not here\nlet x = 1;\n'
    )
    if bad:
        failures.append("group 3 reported UNSCANNABLE for a benign, tokenisable source")
    elif hits_c:
        failures.append("group 3 WRONGLY flagged a comment-only mention of load_verified_cohort")

    # Fail-closed control (EC-19): an unterminated block comment must be flagged
    # as unscannable, never silently treated as "no call sites found".
    _i, _e, _c, bad = _scan_source(
        "/* unterminated comment mentioning himinbjorg::validate_proposal(&c);\n"
    )
    if not bad:
        failures.append(
            "detector FAILED to fail-closed on an unterminated block comment "
            "(reported a scan result instead of flagging it unscannable)"
        )

    return failures


# ---------------------------------------------------------------------------------
# The banner (REQ-28's own closing requirement, stated live, not only in a
# comment).
# ---------------------------------------------------------------------------------


def print_invocation_banner(repo_root: "Path | None" = None) -> bool:
    """Print Himinbjörg's invocation-boundary banner and return True unless a
    fatal condition holds: an unscanned file, a non-test interface call site, an
    unallowlisted (or miscounted) non-test gate call site, or a non-test
    `load_verified_cohort` call site inside `crates/himinbjorg/`."""
    result = scan_repo(repo_root)
    ok = True

    if result.unscanned_files:
        ok = False
        print(f"HIMINBJORG INVOCATION BOUNDARY: {len(result.unscanned_files)} file(s) "
              f"could not be tokenised cleanly (fail-closed, not silently skipped):")
        for f in result.unscanned_files:
            print(f"  [CRITICAL] could not tokenise cleanly: {f}")

    # Group 1: the four public interfaces.
    test_files, non_test_files = classify(result.interface_sites)
    print(f"HIMINBJORG INVOCATION BOUNDARY -- the four public interfaces "
          f"({', '.join(sorted(INTERFACE_SYMBOLS))}): {len(test_files)} test call "
          f"site(s), {len(non_test_files)} non-test call site(s) (expected zero: the "
          f"process engine that would call these is step five, not yet built).")
    for f in test_files:
        print(f"  + test call site: {f}")
    if non_test_files:
        ok = False
        for f in non_test_files:
            print(f"  [CRITICAL] non-test call site (no allowlist exists for this "
                  f"symbol group): {f}")

    # Group 2: the gate call, with the explicit allowlisted-count check.
    test_files_e, non_test_files_e = classify(result.evaluate_sites)
    total_non_test_evaluate_sites = sum(
        len(result.evaluate_sites[f]) for f in non_test_files_e
    )
    allowed_paths = {e.path for e in GATE_CALL_ALLOWLIST}
    unallowlisted = [f for f in non_test_files_e if f not in allowed_paths]
    print()
    print(f"HIMINBJORG INVOCATION BOUNDARY -- boundary_gjoll::consequentiality::evaluate: "
          f"{len(test_files_e)} test call site(s) (file(s)), "
          f"{total_non_test_evaluate_sites} non-test call site(s) total, expected "
          f"EXACTLY ONE (REQ-28, EC-18).")
    for f in test_files_e:
        print(f"  + test call site: {f}")
    for f in non_test_files_e:
        if f in allowed_paths:
            entry = next(e for e in GATE_CALL_ALLOWLIST if e.path == f)
            print(f"  + allowlisted non-test call site: {f} "
                  f"({entry.decision_ref}: {entry.justification})")
    if unallowlisted:
        ok = False
        for f in unallowlisted:
            print(f"  [CRITICAL] unallowlisted non-test call site: {f}")
    if total_non_test_evaluate_sites != 1:
        ok = False
        print(f"  [CRITICAL] expected exactly one non-test call site of "
              f"consequentiality::evaluate, found {total_non_test_evaluate_sites} "
              f"(EC-18: a count other than one is fatal, whether that is a second, "
              f"unlisted site or the allowlisted site vanishing).")
    elif not unallowlisted:
        print("  [PASS] exactly one non-test call site of consequentiality::evaluate, "
              "and it is the allowlisted one.")
    print()
    print("  STATED PLAINLY (REQ-28, section 10 of the step-three spec): one non-test")
    print("  Rust caller of the gate inside a crate that ITSELF has zero non-test")
    print("  callers does NOT advance invariant 3.6. \"The gate now has one non-test")
    print("  caller in Rust, in a crate nothing calls\" is not \"the gate is invoked")
    print("  live against a real action\"; a caller of the caller does not exist yet.")

    # Group 3: load_verified_cohort, scoped to crates/himinbjorg/ only.
    test_files_c, non_test_files_c = classify(result.cohort_sites)
    print()
    print(f"HIMINBJORG INVOCATION BOUNDARY -- hierarchy_vor::load_verified_cohort, "
          f"scoped to crates/himinbjorg/ only: {len(test_files_c)} test call "
          f"site(s), {len(non_test_files_c)} non-test call site(s) (expected zero: "
          f"this crate takes an already-verified cohort by reference and never "
          f"loads one itself).")
    for f in test_files_c:
        print(f"  + test call site: {f}")
    if non_test_files_c:
        ok = False
        for f in non_test_files_c:
            print(f"  [CRITICAL] non-test call site (no allowlist exists for this "
                  f"symbol group): {f}")

    return ok


def main() -> int:
    control_failures = control_check()
    if control_failures:
        print("HIMINBJORG INVOCATION BOUNDARY negative control FAILED:")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    ok = print_invocation_banner()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
