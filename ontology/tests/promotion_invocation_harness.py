# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Jason Huxley and the Heimdall authors.

"""The promotion gate's invocation boundary: who actually calls the
promotion-verification entry point and the promotion-gate policy evaluator
(`.opencode/plans/rust-promotion-gate-spec.md` REQ-34 to REQ-36), on
`ontology.tests.vor_invocation_harness`'s exact function shapes (D96's
precedent, inherited a fourth time).

Run from the repo root:

    python -m ontology.tests.promotion_invocation_harness

Why this exists, on the same footing as D96's caveat for Gjoll and Vor's own
`vor_invocation_harness.py` caveat for the cohort. This build's job is to prove a
promotion cannot be OBTAINED without its attestation having verified
(`hierarchy_vor::load_verified_promotion`), and that a gate policy cannot be
satisfied without a verified promotion witness
(`boundary_gjoll::gate_policy::evaluate_policy`). It says nothing about whether
anything, anywhere, actually CALLS either symbol outside a test file. **At this
build, nothing does, and nothing CAN, because the live minting path (human
promotion on Gjallarhorn's protected channel) is unbuilt** (OR-3, section 10 items
1 and 2). This module is the mechanised form of that fact, so a future session does
not have to remember it in prose.

**Written and run BEFORE the promotion-gate implementation exists.** At this stage
of the build, neither `load_verified_promotion` nor `evaluate_policy` is defined
anywhere in the repository's `.rs` files at all: this detector is deliberately
authored so it can be run today and report the truthful, pre-implementation state
honestly -- zero test call sites and zero non-test call sites of either symbol --
rather than being written only once the Rust exists. Reporting "zero test call
sites" here is NOT the same claim as AC-34's eventual "a non-zero count of test
call sites, and zero non-test call sites": AC-34 describes the POST-build state,
which this module's own `main()` distinguishes explicitly (see its own printed
banner) from today's PRE-build state, so a genuinely zero-everywhere scan is never
read as satisfying AC-34's positive half by accident.

What it detects, and the honest limit of how (following `vor_invocation_harness.py`
verbatim in mechanism). Every textual mention, outside a comment or a string
literal, of `load_verified_promotion` or `evaluate_policy` in a `.rs` file under the
repository. A TOKEN scan, not an AST scan (Python has no built-in Rust parser): see
`vor_invocation_harness.py`'s own module docstring for the full list of what a token
scan can miss (it cannot tell a real call from a mere mention, cannot resolve a
symbol through a module alias, and reports a file it cannot tokenise cleanly as
UNSCANNED rather than silently treating it as zero call sites, EC-19's own
discipline, REQ-35).

Test-side only, by design. This module lives under `ontology/tests/`, exactly as
`vor_invocation_harness.py` and `gjoll_invocation_harness.py` do, so it never
touches invariant 3.1's authorisation scan scope and arms nothing.

What it reports and what is fatal (REQ-34, REQ-36). The COUNT of test call sites is
reporting-only, never a failure. A NON-TEST call site is fatal unless it matches
`PROMOTION_CALL_ALLOWLIST` below, which is **empty at this build** (REQ-34's own
instruction): the moment anything, anywhere, calls either symbol from outside
`unit_tests/` or `tests/`, this obligation must fail loudly, because nothing in the
live path is meant to be able to mint or consult a promotion witness yet.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

# The two symbols this detector tracks: the crate's one promotion-verification
# entry point (hierarchy-vor) and the promotion-gate policy evaluator
# (boundary-gjoll).
PROMOTION_SYMBOLS: frozenset[str] = frozenset({"load_verified_promotion", "evaluate_policy"})

_SYMBOL_RE = re.compile(r"\b(?:" + "|".join(sorted(PROMOTION_SYMBOLS)) + r")\b")

# Directories never scanned: build output and caches carry no repo-authored call
# site, and scanning them would slow this down for no signal.
_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({".git", "target", ".venv", "__pycache__"})

# The two crates' own definition locations. Excluded for the same reason
# `vor_invocation_harness.py` excludes `crates/hierarchy-vor/src`: a symbol's own
# definition site, its doc comments, and any internal call from one half of the
# gate to the other are not wiring call sites, and counting them would report a
# spurious "non-test call site" inside the crate's own source on every run.
_VOR_DEFINITION_DIR: tuple[str, ...] = ("crates", "hierarchy-vor", "src")
_GJOLL_DEFINITION_DIR: tuple[str, ...] = ("crates", "boundary-gjoll", "src")


def _is_definition_file(rel_parts: tuple[str, ...]) -> bool:
    return (
        rel_parts[: len(_VOR_DEFINITION_DIR)] == _VOR_DEFINITION_DIR
        or rel_parts[: len(_GJOLL_DEFINITION_DIR)] == _GJOLL_DEFINITION_DIR
    )


@dataclass(frozen=True)
class NonTestAllowlistEntry:
    """A designated non-test call site of one of `PROMOTION_SYMBOLS` permitted to
    exist, on `vor_invocation_harness.NonTestAllowlistEntry`'s own shape. Widening
    this tuple is how a future session records the live minting path (or the gate's
    live wiring) as a reviewed decision, never as a change that happens to make this
    obligation pass by accident."""

    path: str
    justification: str
    decision_ref: str


# THE ALLOWLIST (REQ-34): EMPTY at this build. Nothing outside `unit_tests/` or
# `tests/` may call either symbol, because the live minting path (human promotion on
# Gjallarhorn's protected channel) is unbuilt (OR-3) and the gate's own pass path is
# harness-and-test-invocation only (section 10, items 1 and 2). Widening this tuple
# is a deliberate, reviewed trust-boundary decision, never a silent addition.
PROMOTION_CALL_ALLOWLIST: tuple[NonTestAllowlistEntry, ...] = ()

for _entry in PROMOTION_CALL_ALLOWLIST:
    if not (_entry.justification and _entry.decision_ref):
        raise ValueError(
            "a PROMOTION_CALL_ALLOWLIST entry must carry both a justification and "
            "a decision reference; see NonTestAllowlistEntry's docstring")


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


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


def _strip_comments_and_strings(src: str) -> tuple[str, bool]:
    """Returns `(cleaned, unscannable)`. Identical mechanism to
    `vor_invocation_harness._strip_comments_and_strings`: strips `//` line
    comments, `/* */` block comments (nesting-aware) and
    string/byte-string/raw-string literals, replacing every stripped character
    with a space (preserving real newlines), so line numbers computed against
    `cleaned` still match the original file exactly. `unscannable` is True when a
    comment or string was never terminated before end of file (REQ-35, EC-19):
    that file must be reported as unscanned, never silently scanned as empty."""
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


def _scan_file(path: Path) -> tuple[list[int], bool]:
    """Return `(sorted hit line numbers, unscannable)` for one file."""
    src = path.read_text(encoding="utf-8", errors="replace")
    cleaned, unscannable = _strip_comments_and_strings(src)
    if unscannable:
        return [], True
    hits = sorted(
        {cleaned.count("\n", 0, m.start()) + 1 for m in _SYMBOL_RE.finditer(cleaned)}
    )
    return hits, False


def _scan_repo(repo_root: Path) -> tuple[dict[str, list[int]], list[str]]:
    """Scan every repo `.rs` file for promotion call sites. Returns `(sites,
    unscanned)`: `sites` maps repo-relative path to sorted hit line numbers;
    `unscanned` lists repo-relative paths that could not be tokenised cleanly
    (REQ-35, EC-19), never folded silently into an empty `sites` entry."""
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


def promotion_call_sites(repo_root: "Path | None" = None) -> dict[str, list[int]]:
    """Detect every textual, non-comment, non-string mention of
    `load_verified_promotion` or `evaluate_policy` in the repo's `.rs` files.
    Returns a mapping of repo-relative file path to the sorted line numbers where a
    mention was found. Does not distinguish test from non-test
    (`classify_call_sites` does that) and does not surface unscanned files (this
    function's return type has no room for them)."""
    if repo_root is None:
        repo_root = _default_repo_root()
    sites, _unscanned = _scan_repo(repo_root)
    return sites


def _is_test_path(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return "unit_tests" in parts or "tests" in parts


def classify_call_sites(repo_root: "Path | None" = None) -> dict:
    """Classify every detected call site as test (`unit_tests/` or `tests/`) or
    non-test. Returns a dict with `sites` (the raw file-to-lines map),
    `test_files`, `non_test_files` (sorted lists of repo-relative paths) and
    `unscanned_files` (sorted repo-relative paths that could not be tokenised
    cleanly, REQ-35, EC-19)."""
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
# REQ-36: the mandatory negative control, ordered BEFORE every positive assertion,
# on `vor_invocation_harness.control_check`'s own shape.
# ---------------------------------------------------------------------------------

_MUST_CATCH = (
    ("a direct call to the promotion-verification entry point",
     'let w = load_verified_promotion(&id, &digest, &level, from, until, &auth, &att, &trusted, now);\n'),
    ("a qualified call to the promotion-verification entry point through the crate path",
     'let w = hierarchy_vor::load_verified_promotion(&id, &digest, &level, from, until, &auth, &att, &trusted, now);\n'),
    ("a call to the promotion-gate policy evaluator",
     'let results = evaluate_policy(&policy, &param, &digest, witness.as_ref());\n'),
    ("a qualified call to the promotion-gate policy evaluator through the crate path",
     'let results = boundary_gjoll::gate_policy::evaluate_policy(&policy, &param, &digest, None);\n'),
)

_MUST_NOT_CATCH = (
    ("a mention only inside a line comment",
     '// load_verified_promotion is called by step three, not here\n'
     'let x = 1;\n'),
    ("a mention only inside a block comment",
     '/* evaluate_policy(&policy, &param, &digest, None) -- not a real call */\n'
     'let x = 1;\n'),
    ("a mention only inside a string literal",
     'let s = "load_verified_promotion";\n'),
    ("a mention only inside a raw string literal",
     'let s = r#"evaluate_policy"#;\n'),
    ("an unrelated function whose name only shares a prefix (word-boundary control)",
     'fn evaluate_policy_v2() {}\n'
     'evaluate_policy_v2();\n'),
)


def control_check() -> list[str]:
    """Run the negative control. Returns a list of failure descriptions (empty if
    the detector behaves): each `_MUST_CATCH` source must produce at least one
    hit, each `_MUST_NOT_CATCH` source must produce none, and a genuinely
    untokenisable file (an unterminated block comment) must be reported as
    unscanned rather than silently scanning clean (REQ-35, EC-19)."""
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

    # Fail-closed control (REQ-35, EC-19): an unterminated block comment must be
    # flagged as unscanned, never silently treated as "no call sites found".
    bad_f = d / "probe.rs"
    bad_f.write_text("/* unterminated comment mentioning evaluate_policy(&p, &q, &r, None);\n")
    hits, bad = _scan_file(bad_f)
    if not bad:
        failures.append(
            "detector FAILED to fail-closed on an unterminated block comment "
            "(reported a scan result instead of flagging it unscannable)"
        )

    return failures


def print_invocation_banner(repo_root: "Path | None" = None) -> bool:
    """Print the promotion-gate invocation-boundary banner and return True unless
    an unallowlisted non-test call site or an unscanned file exists.

    On `vor_invocation_harness.print_invocation_banner`'s own pattern: this states
    the count live so a future session does not have to remember, in prose, who
    calls the promotion-verification entry point or the promotion-gate policy
    evaluator, and it stops stating a clean boundary the moment that changes
    without a reviewed allowlist entry to explain it (REQ-34, REQ-36).

    At this build (pre-implementation, see the module docstring), zero test call
    sites and zero non-test call sites is the TRUTHFUL, correctly-computed state:
    neither symbol is defined anywhere in the repository's Rust source yet, so
    there is genuinely nothing to call. This function reports that state
    accurately (it is not a fabricated pass: the scan genuinely found zero
    matches), and `main()` labels it explicitly as the pre-build state rather than
    as AC-34's own eventual "non-zero test, zero non-test" claim."""
    status = classify_call_sites(repo_root)
    n_test = len(status["test_files"])
    non_test_files = status["non_test_files"]
    total_non_test_sites = len(non_test_files)
    n_unscanned = len(status["unscanned_files"])
    ok = True

    allowed_paths = {e.path for e in PROMOTION_CALL_ALLOWLIST}
    unallowlisted = [f for f in non_test_files if f not in allowed_paths]

    print(f"PROMOTION GATE INVOCATION BOUNDARY (detected live by a TOKEN scan, "
          f"weaker than an AST scan): {n_test} test call site(s) (file(s)), "
          f"{total_non_test_sites} non-test call site(s) (file(s)), expected ZERO "
          f"(REQ-34, empty allowlist at this build).")
    for f in status["test_files"]:
        print(f"  + test call site: {f}")
    for f in non_test_files:
        if f in allowed_paths:
            entry = next(e for e in PROMOTION_CALL_ALLOWLIST if e.path == f)
            print(f"  + allowlisted non-test call site: {f} ({entry.decision_ref}: "
                  f"{entry.justification})")
    if unallowlisted:
        ok = False
        for f in unallowlisted:
            print(f"  [CRITICAL] unallowlisted non-test call site: {f}")
    elif total_non_test_sites == 0:
        print("  [PASS] zero non-test call sites of a promotion-gate symbol; the "
              "empty allowlist is satisfied.")
    if n_unscanned:
        ok = False
        for f in status["unscanned_files"]:
            print(f"  [CRITICAL] could not tokenise cleanly (fail-closed, not "
                  f"silently skipped): {f}")
    return ok


# ---------------------------------------------------------------------------------
# REQ-36: a negative-control extension proving the detector still bites in both
# directions, against SYNTHETIC temporary trees (never this repository's own
# working tree), on `vor_invocation_harness.synthetic_widening_control`'s own shape.
# ---------------------------------------------------------------------------------


def _write_synthetic_tree(files: dict[str, str]) -> Path:
    root = Path(tempfile.mkdtemp(prefix="promotion-invocation-boundary-synthetic-"))
    for rel, src in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src, encoding="utf-8")
    return root


def synthetic_widening_control() -> list[str]:
    failures: list[str] = []

    # Direction 1: an UNLISTED non-test call site must be reported as critical
    # (the empty-allowlist polarity: any non-test call site at all is fatal).
    root = _write_synthetic_tree({
        "crates/process-engine/src/startup.rs": (
            "fn run() {\n    let w = hierarchy_vor::load_verified_promotion(&a, &b, &c, 0, 1, &d, &e, &t, 0);\n}\n"
        ),
    })
    try:
        if not print_invocation_banner(root):
            pass  # correctly detected as critical
        else:
            failures.append(
                "synthetic control FAILED: a non-test call site of "
                "load_verified_promotion was NOT reported as critical (REQ-34's "
                "empty-allowlist polarity)"
            )
    finally:
        import shutil as _shutil
        _shutil.rmtree(root, ignore_errors=True)

    # Direction 2: a test-path call site (unit_tests/ or tests/) must NOT be
    # treated as a violation.
    root = _write_synthetic_tree({
        "crates/boundary-gjoll/unit_tests/gate_policy_failclosed.rs": (
            "fn t() {\n    let r = evaluate_policy(&policy, &param, &digest, None);\n}\n"
        ),
    })
    try:
        if not print_invocation_banner(root):
            failures.append(
                "synthetic control FAILED: a test-path call site of evaluate_policy "
                "under unit_tests/ was WRONGLY reported as a violation"
            )
    finally:
        import shutil as _shutil
        _shutil.rmtree(root, ignore_errors=True)

    # Sanity companion: a synthetic tree with no promotion-symbol mention at all
    # must be reported as satisfying the (empty) allowlist.
    root = _write_synthetic_tree({
        "crates/process-engine/src/startup.rs": "fn run() {}\n",
    })
    try:
        if not print_invocation_banner(root):
            failures.append(
                "synthetic control FAILED: a synthetic tree with zero promotion "
                "call sites at all was wrongly reported as violating the "
                "empty-allowlist check"
            )
    finally:
        import shutil as _shutil
        _shutil.rmtree(root, ignore_errors=True)

    return failures


def main() -> int:
    control_failures = control_check()
    control_failures += synthetic_widening_control()
    if control_failures:
        print("PROMOTION GATE INVOCATION BOUNDARY negative control FAILED:")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1

    ok = print_invocation_banner()

    status = classify_call_sites()
    if len(status["test_files"]) == 0:
        print()
        print("  [PRE-BUILD STATE] zero TEST call sites of load_verified_promotion "
              "or evaluate_policy were found anywhere in the repository. This is "
              "the correct, truthful state BEFORE the promotion-gate implementation "
              "lands (neither symbol is defined in any .rs file yet): it is NOT the "
              "same claim as AC-34's own eventual 'a non-zero count of test call "
              "sites', which only becomes meaningful once REQ-10 to REQ-24's Rust "
              "surface and its own unit_tests/ and tests/ replays exist. Reported "
              "as a distinct, honest pre-build marker, never fabricated as a pass "
              "of AC-34 itself.")

    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
