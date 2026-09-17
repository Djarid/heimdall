# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Jason Huxley and the Heimdall authors.

"""Gjallarhorn's invocation boundary
(`.opencode/plans/gjallarhorn-build-spec.md` REQ-44 to REQ-46): who actually
calls `gjallarhorn::raise`, on D96's own pattern and on
`promotion_invocation_harness.py`'s own function shapes (`_scan_repo`,
`classify_call_sites`, `control_check`, `print_invocation_banner`,
`synthetic_widening_control`).

Run from the repo root:

    python -m ontology.tests.gjallarhorn_invocation_harness

**The polarity is the opposite of `promotion_invocation_harness.py`'s, and
that is deliberate (REQ-44, OR-5, EC-22, EC-23).** Every sibling invocation
detector this repository has built before Gjallarhorn (`vor_invocation_harness`,
`promotion_invocation_harness`) reports its own symbol's non-test call-site
count as zero-required: the live path those detectors watch is genuinely
unbuilt, so any non-test caller at all is a reviewed trust-boundary event and
the correct number is zero. Gjallarhorn's `raise` is different: OR-5 requires
the component to be "honestly useful rather than dormant", and REQ-39
committed to exactly one genuine non-test raise site inside
`crates/process-engine/src/sequence.rs`'s `GateBlocked` branch, built in the
same change series as this detector. So THIS detector's polarity is
EXACTLY ONE REQUIRED, on `actuator_invocation_harness.ACTUATOR_CALL_ALLOWLIST`'s
own exactly-one-required shape, not `promotion_invocation_harness`'s
zero-required shape:

  - **Zero** non-test call sites is a FAILURE here (EC-23): the component
    would have been built and then quietly made dormant, which is the exact
    outcome OR-5 refuses.
  - **A second, unlisted** non-test call site is ALSO a failure (EC-22): a
    future second raise site must be a reviewed act, never a silent one.
  - **Exactly the one allowlisted site**, and nothing else, is the only
    passing state.

`GJALLARHORN_RAISE_ALLOWLIST` below carries exactly the one entry REQ-39 and
REQ-44 both name: `crates/process-engine/src/sequence.rs`, with a
justification and a `DECISIONS.md` reference, exactly as
`ACTUATOR_CALL_ALLOWLIST` and `BAA_CALL_ALLOWLIST` already do for their own
one-entry allowlists (see `actuator_invocation_harness.py`).

What it detects, and the honest limit of how, on
`promotion_invocation_harness.py`'s own disclosed weakness. This is a TOKEN
scan, not an AST scan: Python has no built-in Rust parser, so this module
strips `//` and `/* */` comments (nesting-aware) and string/byte-string/
raw-string literals with the same hand-written state machine
`promotion_invocation_harness.py` and its own siblings use (duplicated here,
not imported, following this repository's own convention of duplicating a
short, test-only helper across sibling harnesses). A qualified call
(`gjallarhorn::raise(`) and a bare call reached through a genuine
`use gjallarhorn::raise [as alias];` import both count; a bare `raise(...)`
with no such import in scope does not (word-boundary control, so an
unrelated function that merely shares the name `raise` is never mistaken for
this one).

Fail-closed on the unscannable (REQ-45, following `vor_invocation_harness.py`'s
EC-19 discipline): a file this tokeniser cannot parse cleanly (an unterminated
comment or string literal) is reported as UNSCANNED and counted as a failure
to verify, never as silent evidence of a clean boundary.

Test-side only, by design. This module lives under `ontology/tests/`, exactly
as its siblings do, so it never touches invariant 3.1's authorisation-path
scan scope and arms nothing.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({".git", "target", ".venv", "__pycache__"})

# `raise`'s own definition site: gjallarhorn's own src/ tree. Excluded for the
# same reason `promotion_invocation_harness.py` excludes each symbol's own
# definition directory: the definition, its doc comments and any purely
# internal mention are not wiring call sites, and counting them would report
# a spurious "non-test call site" inside the crate's own source on every run.
_GJALLARHORN_DEFINITION_DIR: tuple[str, ...] = ("crates", "gjallarhorn", "src")


def _is_definition_file(rel_parts: tuple[str, ...]) -> bool:
    return rel_parts[: len(_GJALLARHORN_DEFINITION_DIR)] == _GJALLARHORN_DEFINITION_DIR


@dataclass(frozen=True)
class NonTestAllowlistEntry:
    """A designated non-test call site of `gjallarhorn::raise` permitted to
    exist, on `actuator_invocation_harness.NonTestAllowlistEntry`'s own
    shape. `GJALLARHORN_RAISE_ALLOWLIST` below requires EXACTLY the one
    entry it names (REQ-39, REQ-44): the check this module runs fails if the
    live count of non-test call sites is anything other than one, in either
    direction (EC-22, EC-23)."""

    path: str
    justification: str
    decision_ref: str


# THE ALLOWLIST (REQ-39, REQ-44, OR-5, OR-7): exactly one entry. Widening this
# tuple to a second entry is how a future session would record a genuinely
# new raise site as a reviewed decision, never as a change that happens to
# make this obligation pass by accident (EC-22).
GJALLARHORN_RAISE_ALLOWLIST: tuple[NonTestAllowlistEntry, ...] = (
    NonTestAllowlistEntry(
        path="crates/process-engine/src/sequence.rs",
        justification=(
            "the process engine's own GateBlocked branch (REQ-39, spec section "
            "3.8 of .opencode/plans/gjallarhorn-build-spec.md, issue #118): the "
            "one, deliberately singular, non-test call site of "
            "gjallarhorn::raise, reached only after a Gjoll gate decision is "
            "already known and after the EngineOutcome's own value is already "
            "determined, so the raise call can never change what the engine "
            "already decided (REQ-40)"
        ),
        decision_ref="D126",
    ),
)

for _entry in GJALLARHORN_RAISE_ALLOWLIST:
    # A real `raise`, not a bare `assert` (on `gjoll_invocation_harness.py`'s
    # own Minor-4 fix): this is an enforced control on a reviewed
    # trust-boundary decision, not a debug-only check.
    if not (_entry.justification and _entry.decision_ref):
        raise ValueError(
            "a GJALLARHORN_RAISE_ALLOWLIST entry must carry both a justification "
            "and a decision reference; see NonTestAllowlistEntry's docstring")

if len(GJALLARHORN_RAISE_ALLOWLIST) != 1:
    raise ValueError(
        "GJALLARHORN_RAISE_ALLOWLIST must carry EXACTLY one entry (REQ-44, "
        "OR-5's exactly-one-required polarity, the opposite of "
        "promotion_invocation_harness.py's zero-required polarity): found "
        f"{len(GJALLARHORN_RAISE_ALLOWLIST)}")


def _default_repo_root() -> Path:
    return REPO_ROOT


def _iter_repo_rust_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for p in repo_root.rglob("*.rs"):
        if any(part in _EXCLUDED_DIR_NAMES for part in p.parts):
            continue
        rel_parts = p.relative_to(repo_root).parts
        if _is_definition_file(rel_parts):
            continue
        files.append(p)
    return files


# ---------------------------------------------------------------------------------
# The tokeniser (duplicated from promotion_invocation_harness.py; see its own
# header, and this module's, for why duplication, not import, is this
# repository's convention here).
# ---------------------------------------------------------------------------------


def _strip_comments_and_strings(src: str) -> tuple[str, bool]:
    """Returns `(cleaned, unscannable)`. Strips `//` line comments, `/* */`
    block comments (nesting-aware) and string/byte-string/raw-string
    literals, replacing every stripped character with a space (preserving
    real newlines), so line numbers computed against `cleaned` still match
    the original file exactly. `unscannable` is True when a comment or
    string was never terminated before end of file (REQ-45): that file must
    be reported as unscanned, never silently scanned as empty."""
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
# gjallarhorn::raise call-site resolution: a qualified call
# (`gjallarhorn::raise(`) always counts; a bare `raise(...)` counts only when
# this file's own scope bound that name from a genuine
# `use gjallarhorn::raise [as alias];` import (word-boundary control, on
# `actuator_invocation_harness.py`'s own `execute`/`broker_authorised_action`
# resolution shape).
# ---------------------------------------------------------------------------------

_QUALIFIED_RAISE_CALL_RE = re.compile(r"\bgjallarhorn::raise\s*\(")
_USE_RAISE_SINGLE_RE = re.compile(r"use\s+gjallarhorn::raise(?:\s+as\s+(\w+))?\s*;")
_USE_RAISE_GROUP_RE = re.compile(r"use\s+gjallarhorn::\{([^}]*)\}\s*;")


def _raise_bound_names(cleaned: str) -> set[str]:
    bound: set[str] = set()
    for alias in _USE_RAISE_SINGLE_RE.findall(cleaned):
        bound.add(alias or "raise")
    for group_body in _USE_RAISE_GROUP_RE.findall(cleaned):
        for item in group_body.split(","):
            item = item.strip()
            if not item:
                continue
            parts = [p.strip() for p in item.split(" as ")]
            name = parts[0]
            alias = parts[1] if len(parts) > 1 else None
            if name == "raise":
                bound.add(alias or "raise")
    return bound


def _raise_call_sites(cleaned: str) -> list[int]:
    hits: set[int] = set()
    for m in _QUALIFIED_RAISE_CALL_RE.finditer(cleaned):
        hits.add(cleaned.count("\n", 0, m.start()) + 1)
    for bound_name in _raise_bound_names(cleaned):
        for m in re.finditer(rf"(?<!::){re.escape(bound_name)}\s*\(", cleaned):
            hits.add(cleaned.count("\n", 0, m.start()) + 1)
    return sorted(hits)


def _scan_file(path: Path) -> tuple[list[int], bool]:
    """Return `(sorted hit line numbers, unscannable)` for one file."""
    src = path.read_text(encoding="utf-8", errors="replace")
    cleaned, unscannable = _strip_comments_and_strings(src)
    if unscannable:
        return [], True
    return _raise_call_sites(cleaned), False


def _scan_repo(repo_root: Path) -> tuple[dict[str, list[int]], list[str]]:
    """Scan every repo `.rs` file (outside `gjallarhorn`'s own `src/`, its
    definition site) for `raise` call sites. Returns `(sites, unscanned)`:
    `sites` maps repo-relative path to sorted hit line numbers; `unscanned`
    lists repo-relative paths that could not be tokenised cleanly (REQ-45),
    never folded silently into an empty `sites` entry."""
    sites: dict[str, list[int]] = {}
    unscanned: list[str] = []
    for f in _iter_repo_rust_files(repo_root):
        hits, bad = _scan_file(f)
        rel = str(f.relative_to(repo_root))
        if bad:
            unscanned.append(rel)
            continue
        if hits:
            sites[rel] = hits
    return sites, sorted(unscanned)


def raise_call_sites(repo_root: "Path | None" = None) -> dict[str, list[int]]:
    """Detect every textual, non-comment, non-string mention of
    `gjallarhorn::raise` (qualified, or bare through a genuine `use`
    import) in the repo's `.rs` files, outside `gjallarhorn`'s own `src/`.
    Returns a mapping of repo-relative file path to the sorted line numbers
    where a call site was found. Does not distinguish test from non-test
    (`classify_call_sites` does that) and does not surface unscanned files
    (this function's return type has no room for them)."""
    if repo_root is None:
        repo_root = _default_repo_root()
    sites, _unscanned = _scan_repo(repo_root)
    return sites


def _is_test_path(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return "unit_tests" in parts or "tests" in parts


def classify_call_sites(repo_root: "Path | None" = None) -> dict:
    """Classify every detected call site as test (`unit_tests/` or `tests/`)
    or non-test. Returns a dict with `sites` (the raw file-to-lines map),
    `test_files`, `non_test_files` (sorted lists of repo-relative paths) and
    `unscanned_files` (sorted repo-relative paths that could not be
    tokenised cleanly, REQ-45)."""
    if repo_root is None:
        repo_root = _default_repo_root()
    sites, unscanned = _scan_repo(repo_root)
    test_files = sorted(p for p in sites if _is_test_path(p))
    non_test_files = sorted(p for p in sites if not _is_test_path(p))
    return {
        "sites": sites,
        "test_files": test_files,
        "non_test_files": non_test_files,
        "unscanned_files": unscanned,
    }


# ---------------------------------------------------------------------------------
# REQ-46: the mandatory negative control, ordered BEFORE every positive
# assertion, on `promotion_invocation_harness.control_check`'s own shape.
# ---------------------------------------------------------------------------------

_MUST_CATCH = (
    ("a direct, qualified call to gjallarhorn::raise",
     'let _ = gjallarhorn::raise(event, &mut recorder, &mut protected, &mut triage, &mut delivery);\n'),
    ("a qualified call to raise through the crate path with an unrelated import present",
     'use gjallarhorn::GjallarhornEvent;\n'
     'let _ = gjallarhorn::raise(event, &mut recorder, &mut protected, &mut triage, &mut delivery);\n'),
    ("a bare call bound by a genuine use gjallarhorn::raise; import",
     'use gjallarhorn::raise;\n'
     'let _ = raise(event, &mut recorder, &mut protected, &mut triage, &mut delivery);\n'),
    ("a bare call bound by a genuine use gjallarhorn::{raise, ...}; group import",
     'use gjallarhorn::{raise, GjallarhornEvent};\n'
     'let _ = raise(event, &mut recorder, &mut protected, &mut triage, &mut delivery);\n'),
)

_MUST_NOT_CATCH = (
    ("a mention only inside a line comment",
     '// gjallarhorn::raise is called by sequence.rs, not here\n'
     'let x = 1;\n'),
    ("a mention only inside a block comment",
     '/* gjallarhorn::raise(event, &mut r, &mut p, &mut t, &mut d) -- not a real call */\n'
     'let x = 1;\n'),
    ("a mention only inside a string literal",
     'let s = "gjallarhorn::raise";\n'),
    ("a mention only inside a raw string literal",
     'let s = r#"raise"#;\n'),
    ("an unrelated function whose name only shares a prefix (word-boundary control)",
     'fn raise_awareness() {}\n'
     'raise_awareness();\n'),
    ("a bare raise(...) call with NO gjallarhorn::raise import in scope",
     'fn raise(x: i32) -> i32 { x }\n'
     'let y = raise(1);\n'),
)


def control_check() -> list[str]:
    """Run the negative control. Returns a list of failure descriptions
    (empty if the detector behaves): each `_MUST_CATCH` source must produce
    at least one hit, each `_MUST_NOT_CATCH` source must produce none, and a
    genuinely untokenisable file (an unterminated block comment) must be
    reported as unscanned rather than silently scanning clean (REQ-45)."""
    failures: list[str] = []
    d = Path(tempfile.mkdtemp())

    for label, src in _MUST_CATCH:
        f = d / "probe.rs"
        f.write_text(src)
        hits, bad = _scan_file(f)
        if bad or not hits:
            failures.append(f"detector FAILED to catch a planted {label}")

    for label, src in _MUST_NOT_CATCH:
        f = d / "probe.rs"
        f.write_text(src)
        hits, bad = _scan_file(f)
        if bad:
            failures.append(
                f"detector reported UNSCANNABLE for a benign source it should have "
                f"tokenised cleanly ({label})"
            )
        elif hits:
            failures.append(f"detector WRONGLY flagged a benign source ({label})")

    # Fail-closed control (REQ-45): an unterminated block comment must be
    # flagged as unscanned, never silently treated as "no call sites found".
    bad_f = d / "probe.rs"
    bad_f.write_text("/* unterminated comment mentioning gjallarhorn::raise(event, &mut r);\n")
    hits, bad = _scan_file(bad_f)
    if not bad:
        failures.append(
            "detector FAILED to fail-closed on an unterminated block comment "
            "(reported a scan result instead of flagging it unscannable)"
        )

    shutil.rmtree(d, ignore_errors=True)
    return failures


def print_invocation_banner(repo_root: "Path | None" = None) -> bool:
    """Print the Gjallarhorn invocation-boundary banner and return True only
    when exactly one non-test call site exists and it is the allowlisted
    one, and no file is unscanned.

    **The polarity is exactly-one-required (REQ-44, OR-5), the opposite of
    `promotion_invocation_harness.print_invocation_banner`'s zero-required
    polarity.** Zero non-test call sites is a FAILURE here (EC-23), and a
    second, unlisted non-test call site is ALSO a failure (EC-22)."""
    status = classify_call_sites(repo_root)
    n_test = len(status["test_files"])
    non_test_files = status["non_test_files"]
    total_non_test_sites = sum(len(status["sites"][f]) for f in non_test_files)
    n_unscanned = len(status["unscanned_files"])
    ok = True

    allowed_paths = {e.path for e in GJALLARHORN_RAISE_ALLOWLIST}
    unallowlisted = [f for f in non_test_files if f not in allowed_paths]

    print(f"GJALLARHORN INVOCATION BOUNDARY (detected live by a TOKEN scan, weaker "
          f"than an AST scan): {n_test} test call site(s) (file(s)), "
          f"{total_non_test_sites} non-test call site(s) total, expected EXACTLY "
          f"ONE (REQ-44, OR-5's exactly-one-required polarity, the opposite of "
          f"promotion_invocation_harness's zero-required polarity).")
    for f in status["test_files"]:
        print(f"  + test call site: {f}")
    for f in non_test_files:
        if f in allowed_paths:
            entry = next(e for e in GJALLARHORN_RAISE_ALLOWLIST if e.path == f)
            print(f"  + allowlisted non-test call site: {f} ({entry.decision_ref}: "
                  f"{entry.justification})")
    if unallowlisted:
        ok = False
        for f in unallowlisted:
            print(f"  [CRITICAL] unallowlisted non-test call site: {f}")
    if total_non_test_sites == 0:
        ok = False
        print("  [CRITICAL] zero non-test call sites of gjallarhorn::raise (EC-23): "
              "this build requires exactly one, on OR-5's own polarity, because a "
              "zero count here would mean the component was built and then made "
              "dormant.")
    elif total_non_test_sites > 1 and not unallowlisted:
        # Every non-test site is individually allowlisted, yet the total
        # count still exceeds one (a second call landing at the SAME
        # allowlisted path, or the allowlist itself carrying more than one
        # entry, which the module-level check above already forbids). Named
        # explicitly rather than folded into the unallowlisted branch, so a
        # reviewer sees why a seemingly "clean" allowlist match still fails.
        ok = False
        print(f"  [CRITICAL] {total_non_test_sites} non-test call sites found, "
              f"expected exactly one, even though every site matches an "
              f"allowlisted path (EC-22): a second call landing at an already-"
              f"allowlisted file is still a second call site.")
    elif not unallowlisted:
        print("  [PASS] exactly one non-test call site of gjallarhorn::raise, and "
              "it is the allowlisted one.")
    if n_unscanned:
        ok = False
        for f in status["unscanned_files"]:
            print(f"  [CRITICAL] could not tokenise cleanly (fail-closed, not "
                  f"silently skipped): {f}")
    return ok


# ---------------------------------------------------------------------------------
# REQ-46: a negative-control extension proving the detector still bites in
# both directions, against SYNTHETIC temporary trees (never this
# repository's own working tree), on
# `promotion_invocation_harness.synthetic_widening_control`'s own shape.
# ---------------------------------------------------------------------------------


def _write_synthetic_tree(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp(prefix="gjallarhorn-invocation-boundary-synthetic-"))
    for rel, src in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src, encoding="utf-8")
    return root


def synthetic_widening_control() -> list[str]:
    failures: list[str] = []

    allowlisted_sequence_rs = (
        "fn f() {\n"
        "    let _ = gjallarhorn::raise(event, &mut recorder, &mut protected, "
        "&mut triage, &mut delivery);\n"
        "}\n"
    )

    # Direction 1 (AC-44's own passing case): exactly the one allowlisted
    # non-test call site, and nothing else, must PASS.
    root = _write_synthetic_tree({
        "crates/process-engine/src/sequence.rs": allowlisted_sequence_rs,
    })
    try:
        if not print_invocation_banner(root):
            failures.append(
                "synthetic control FAILED: exactly the one allowlisted non-test "
                "call site of gjallarhorn::raise was WRONGLY reported as a "
                "violation"
            )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # Direction 2 (EC-23, AC-44's second case): ZERO non-test call sites of
    # raise must FAIL, because zero-required is the wrong polarity for this
    # build (the opposite of promotion_invocation_harness's own polarity).
    root = _write_synthetic_tree({
        "crates/process-engine/src/sequence.rs": "fn f() {}\n",
    })
    try:
        if print_invocation_banner(root):
            failures.append(
                "synthetic control FAILED: ZERO non-test call sites of "
                "gjallarhorn::raise was WRONGLY reported as passing (EC-23: this "
                "build's polarity requires exactly one, never zero)"
            )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # Direction 3 (EC-22, AC-44's third case): a SECOND, unlisted non-test
    # call site alongside the genuine allowlisted one must FAIL.
    root = _write_synthetic_tree({
        "crates/process-engine/src/sequence.rs": allowlisted_sequence_rs,
        "crates/process-engine/src/other_module.rs": (
            "fn g() {\n"
            "    let _ = gjallarhorn::raise(event2, &mut recorder2, &mut protected2, "
            "&mut triage2, &mut delivery2);\n"
            "}\n"
        ),
    })
    try:
        if print_invocation_banner(root):
            failures.append(
                "synthetic control FAILED: a second, unlisted non-test call site "
                "of gjallarhorn::raise alongside the allowlisted one was NOT "
                "reported as critical (EC-22)"
            )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # Direction 4 (test-path classification, AC-44's own "must NOT be
    # flagged" case): a call site under unit_tests/ must NOT be treated as a
    # violation. Paired with the one allowlisted site so this tree's own
    # non-test count is still exactly one and the tree passes overall.
    root = _write_synthetic_tree({
        "crates/process-engine/src/sequence.rs": allowlisted_sequence_rs,
        "crates/gjallarhorn/unit_tests/raise_failclosed.rs": (
            "fn t() {\n"
            "    let _ = raise(event, &mut recorder, &mut protected, &mut triage, "
            "&mut delivery);\n"
            "}\n"
        ),
    })
    try:
        if not print_invocation_banner(root):
            failures.append(
                "synthetic control FAILED: a call site under unit_tests/ was "
                "WRONGLY treated as a violation"
            )
    finally:
        shutil.rmtree(root, ignore_errors=True)

    return failures


def main() -> int:
    control_failures = control_check()
    control_failures += synthetic_widening_control()
    if control_failures:
        print("GJALLARHORN INVOCATION BOUNDARY negative control FAILED:")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    ok = print_invocation_banner()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
