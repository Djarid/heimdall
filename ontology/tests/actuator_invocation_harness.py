"""The git actuator's invocation boundary
(`.opencode/plans/git-actuator-step-four.md` REQ-44): who actually calls
`actuator_git::execute`, and who actually calls `himinbjorg`'s witness-carrying
entry point, `broker_authorised_action`, on `vor_invocation_harness.py`'s and
`himinbjorg_invocation_harness.py`'s token-scan precedent (D96's, itself
`gjoll_invocation_harness.py`'s AST-based original).

Run from the repo root:

    python -m ontology.tests.actuator_invocation_harness

Why this exists, on the same footing as D96's and D111's own caveats.
`crates/actuator-git/` proves the actuator's own mechanical posture
(`ontology.tests.rust_actuator_harness`); it says NOTHING about whether
anything, anywhere, actually CALLS `execute` outside `himinbjorg`'s one
deliberate wiring, or about whether `broker_authorised_action` -- the sibling
entry point authorisation reaches through (GA-1) -- is itself called by
anything beyond this crate's own tests. Both are DIFFERENT and separately
governed claims from "the actuator is built and wired": the process engine
that would call `broker_authorised_action` is build-order step five, not yet
built (REQ-40, section 13 item one of the spec). This module is the mechanised
form of that fact, on the exact pattern `vor_invocation_harness.py` and
`himinbjorg_invocation_harness.py` already established, so a future session
does not have to remember it in prose.

**Section 13 item one's own sentence, stated here live, not only in a
comment:** an actuator that can execute, inside a crate whose one witness-
carrying entry point nothing calls, is not "Heimdall has taken a real gated
action". That is build-order step six.

Two symbol groups tracked, each answering a different question:

  1. `actuator_git::execute`, scanned across the WHOLE repo. Expected EXACTLY
     ONE non-test call site, inside `crates/himinbjorg/src/broker.rs` (REQ-36).
     This is an EXPLICIT ALLOWLISTED COUNT CHECK
     (`ACTUATOR_CALL_ALLOWLIST`), on `gjoll_invocation_harness.NonTestAllowlistEntry`'s
     and `himinbjorg_invocation_harness.GATE_CALL_ALLOWLIST`'s own polarity
     (inverted in degree from `ALLOWED_IMPORT_ROOTS`/D71: this allowlist
     requires EXACTLY the one entry it names, so both a second unlisted call
     site AND the allowlisted site disappearing or duplicating are equally
     fatal, EC-18).

     Resolved through the crate boundary, exactly as
     `himinbjorg_invocation_harness.py`'s own group 2 resolves
     `consequentiality::evaluate`: a fully or partially qualified call
     (`actuator_git::execute(` or `execute(` reached through any prefix
     ending in that path) always counts when the prefix is
     `actuator_git::` or `crate::` from within `crates/actuator-git/` itself;
     a bare `execute(...)` counts only when this file's own scope bound that
     name from a `use actuator_git::execute [as alias];` import, because
     `execute` alone is far too common a bare name to scan for unresolved.
  2. `broker_authorised_action`, scanned across the WHOLE repo. Expected ZERO
     non-test call sites (REQ-40): no allowlist mechanism exists for this
     symbol, following `vor_invocation_harness.py`'s own no-allowlist
     precedent for Vor's cohort entry point. This crate's own test suite
     (`crates/himinbjorg/unit_tests/witness_and_audit.rs` and
     `crates/himinbjorg/tests/public_surface.rs`) is expected to call it
     directly; those are TEST call sites, reported but never fatal.

What it detects, and the honest limit of how, on
`himinbjorg_invocation_harness.py`'s own disclosed weakness. This is a TOKEN
scan, not an AST scan: Python has no built-in Rust parser, so this module
strips `//` and `/* */` comments (nesting-aware) and string/byte-string/
raw-string literals with the same hand-written state machine
`vor_invocation_harness.py` and `himinbjorg_invocation_harness.py` use
(duplicated here, not imported, following this repository's own convention of
duplicating a short, test-only helper across sibling harnesses). The
import-resolution added for group 1 is a regex-based approximation of Rust's
`use` grammar, handling only the two `use` shapes this repository's own code
actually uses today (a single-item `use path::name [as alias];` and a braced
group `use path::{a, b as c, ...};`); a `use path::*;` glob import is not
resolved by it, named here rather than silently assumed away.

Test-side only, by design. This module lives under `ontology/tests/`, exactly
as its siblings do, so it never touches invariant 3.1's authorisation-path
scan scope and arms nothing.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({".git", "target", ".venv", "__pycache__"})

_ACTUATOR_GIT_CRATE_DIR: tuple[str, ...] = ("crates", "actuator-git")
_HIMINBJORG_CRATE_DIR: tuple[str, ...] = ("crates", "himinbjorg")


@dataclass(frozen=True)
class NonTestAllowlistEntry:
    """A designated non-test call site of `actuator_git::execute` permitted to
    exist, on `gjoll_invocation_harness.NonTestAllowlistEntry`'s own shape.
    `ACTUATOR_CALL_ALLOWLIST` below requires EXACTLY the one entry it names
    (REQ-36, REQ-44): the check this module runs fails if the live count of
    non-test call sites is anything other than one."""

    path: str
    justification: str
    decision_ref: str


ACTUATOR_CALL_ALLOWLIST: tuple[NonTestAllowlistEntry, ...] = (
    NonTestAllowlistEntry(
        path="crates/himinbjorg/src/broker.rs",
        justification=(
            "broker_authorised_action's own single actuator call site (REQ-36, REQ-38 "
            "of the git-actuator step-four spec): the crate's one, deliberately "
            "singular, non-test call site of the actuator's own entry point"
        ),
        decision_ref="D112",
    ),
)

for _entry in ACTUATOR_CALL_ALLOWLIST:
    # A real `raise`, not a bare `assert` (following
    # gjoll_invocation_harness.py's own Minor-4 fix): this is meant to be an
    # enforced control on a reviewed trust-boundary decision, not a
    # debug-only check.
    if not (_entry.justification and _entry.decision_ref):
        raise ValueError(
            "an ACTUATOR_CALL_ALLOWLIST entry must carry both a justification and a "
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


def _is_within_actuator_git_crate(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return parts[: len(_ACTUATOR_GIT_CRATE_DIR)] == _ACTUATOR_GIT_CRATE_DIR


def _is_within_himinbjorg_crate(rel_path: str) -> bool:
    parts = Path(rel_path).parts
    return parts[: len(_HIMINBJORG_CRATE_DIR)] == _HIMINBJORG_CRATE_DIR


# ---------------------------------------------------------------------------------
# The tokeniser (duplicated from vor_invocation_harness.py /
# himinbjorg_invocation_harness.py; see their headers and this module's own
# for why duplication, not import, is this repository's convention here).
# ---------------------------------------------------------------------------------


def _strip_comments_and_strings(src: str) -> tuple[str, bool]:
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
# Group 1: actuator_git::execute (REQ-36, REQ-44, EC-18).
# ---------------------------------------------------------------------------------

_QUALIFIED_EXECUTE_CALL_RE = re.compile(r"\bactuator_git::execute\s*\(")
_CRATE_EXECUTE_CALL_RE = re.compile(r"\bcrate::execute\s*\(")
_USE_EXECUTE_SINGLE_RE = re.compile(r"use\s+actuator_git::execute(?:\s+as\s+(\w+))?\s*;")
_USE_EXECUTE_GROUP_RE = re.compile(r"use\s+actuator_git::\{([^}]*)\}\s*;")


def _execute_bound_names(cleaned: str) -> set[str]:
    bound: set[str] = set()
    for alias in _USE_EXECUTE_SINGLE_RE.findall(cleaned):
        bound.add(alias or "execute")
    for group_body in _USE_EXECUTE_GROUP_RE.findall(cleaned):
        for item in group_body.split(","):
            item = item.strip()
            if not item:
                continue
            parts = [p.strip() for p in item.split(" as ")]
            name = parts[0]
            alias = parts[1] if len(parts) > 1 else None
            if name == "execute":
                bound.add(alias or "execute")
    return bound


def _execute_call_sites(cleaned: str, rel_path: str) -> list[int]:
    hits: set[int] = set()
    for m in _QUALIFIED_EXECUTE_CALL_RE.finditer(cleaned):
        hits.add(cleaned.count("\n", 0, m.start()) + 1)
    if _is_within_actuator_git_crate(rel_path):
        for m in _CRATE_EXECUTE_CALL_RE.finditer(cleaned):
            hits.add(cleaned.count("\n", 0, m.start()) + 1)
    for bound_name in _execute_bound_names(cleaned):
        for m in re.finditer(rf"(?<!::){re.escape(bound_name)}\s*\(", cleaned):
            hits.add(cleaned.count("\n", 0, m.start()) + 1)
    return sorted(hits)


# ---------------------------------------------------------------------------------
# Group 2: broker_authorised_action, scanned across the whole repo, no
# allowlist (REQ-40). This symbol has no other definition anywhere in the
# crates tree, so a simple qualified/crate::/use-bound scan (identical shape
# to group 1's) is sufficient.
# ---------------------------------------------------------------------------------

_QUALIFIED_BAA_CALL_RE = re.compile(r"\bhiminbjorg::broker_authorised_action\s*\(")
_CRATE_BAA_CALL_RE = re.compile(r"\bcrate::broker_authorised_action\s*\(")
_USE_BAA_SINGLE_RE = re.compile(
    r"use\s+himinbjorg::broker_authorised_action(?:\s+as\s+(\w+))?\s*;"
)
_USE_BAA_GROUP_RE = re.compile(r"use\s+himinbjorg::\{([^}]*)\}\s*;")


def _baa_bound_names(cleaned: str) -> set[str]:
    bound: set[str] = set()
    for alias in _USE_BAA_SINGLE_RE.findall(cleaned):
        bound.add(alias or "broker_authorised_action")
    for group_body in _USE_BAA_GROUP_RE.findall(cleaned):
        for item in group_body.split(","):
            item = item.strip()
            if not item:
                continue
            parts = [p.strip() for p in item.split(" as ")]
            name = parts[0]
            alias = parts[1] if len(parts) > 1 else None
            if name == "broker_authorised_action":
                bound.add(alias or "broker_authorised_action")
    return bound


def _baa_call_sites(cleaned: str, rel_path: str) -> list[int]:
    hits: set[int] = set()
    for m in _QUALIFIED_BAA_CALL_RE.finditer(cleaned):
        hits.add(cleaned.count("\n", 0, m.start()) + 1)
    if _is_within_himinbjorg_crate(rel_path):
        for m in _CRATE_BAA_CALL_RE.finditer(cleaned):
            hits.add(cleaned.count("\n", 0, m.start()) + 1)
    for bound_name in _baa_bound_names(cleaned):
        for m in re.finditer(rf"(?<!::){re.escape(bound_name)}\s*\(", cleaned):
            hits.add(cleaned.count("\n", 0, m.start()) + 1)
    return sorted(hits)


# ---------------------------------------------------------------------------------
# The unified scan.
# ---------------------------------------------------------------------------------


@dataclass
class ScanResult:
    execute_sites: dict[str, list[int]] = field(default_factory=dict)
    baa_sites: dict[str, list[int]] = field(default_factory=dict)
    unscanned_files: list[str] = field(default_factory=list)


def scan_repo(repo_root: "Path | None" = None) -> ScanResult:
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
        execute_hits = _execute_call_sites(cleaned, rel)
        if execute_hits:
            result.execute_sites[rel] = execute_hits
        baa_hits = _baa_call_sites(cleaned, rel)
        if baa_hits:
            result.baa_sites[rel] = baa_hits
    result.unscanned_files.sort()
    return result


def classify(sites: dict[str, list[int]]) -> tuple[list[str], list[str]]:
    test_files = sorted(p for p in sites if _is_test_path(p))
    non_test_files = sorted(p for p in sites if not _is_test_path(p))
    return test_files, non_test_files


# ---------------------------------------------------------------------------------
# Negative-control probes (invariant 3.10, D10).
# ---------------------------------------------------------------------------------


def _scan_source(src: str, rel_path: str = "crates/himinbjorg/src/probe.rs") -> tuple[list[int], list[int], bool]:
    cleaned, unscannable = _strip_comments_and_strings(src)
    if unscannable:
        return [], [], True
    return (
        _execute_call_sites(cleaned, rel_path),
        _baa_call_sites(cleaned, rel_path),
        False,
    )


def control_check() -> list[str]:
    failures: list[str] = []

    hits, _b, bad = _scan_source('let o = actuator_git::execute(&op);\n')
    if bad or not hits:
        failures.append("group 1 FAILED to catch a qualified actuator_git::execute(...) call")

    hits, _b, bad = _scan_source(
        'use actuator_git::execute;\nlet o = execute(&op);\n'
    )
    if bad or not hits:
        failures.append(
            "group 1 FAILED to catch a bare execute(...) call bound by a genuine "
            "`use actuator_git::execute;` import"
        )

    hits, _b, bad = _scan_source('fn execute(x: i32) -> i32 { x }\nlet y = execute(1);\n')
    if bad:
        failures.append("group 1 reported UNSCANNABLE for a benign, tokenisable source")
    elif hits:
        failures.append(
            "group 1 WRONGLY flagged an unrelated bare execute(...) call with no "
            "actuator_git::execute import in scope"
        )

    _e, hits_b, bad = _scan_source('let r = himinbjorg::broker_authorised_action(&c, &a, &s, &w, &mut rec);\n')
    if bad or not hits_b:
        failures.append("group 2 FAILED to catch a qualified himinbjorg::broker_authorised_action(...) call")

    _e, hits_b, bad = _scan_source(
        'use himinbjorg::{broker_authorised_action, broker_action};\n'
        'let r = broker_authorised_action(&c, &a, &s, &w, &mut rec);\n'
    )
    if bad or not hits_b:
        failures.append(
            "group 2 FAILED to catch a bare broker_authorised_action(...) call bound by "
            "a genuine `use himinbjorg::{...}` import"
        )

    _e, hits_b, bad = _scan_source(
        '// broker_authorised_action is called by step five, not here\nlet x = 1;\n'
    )
    if bad:
        failures.append("group 2 reported UNSCANNABLE for a benign, tokenisable source")
    elif hits_b:
        failures.append("group 2 WRONGLY flagged a comment-only mention of broker_authorised_action")

    _e, _b, bad = _scan_source("/* unterminated comment mentioning actuator_git::execute(&op);\n")
    if not bad:
        failures.append(
            "detector FAILED to fail-closed on an unterminated block comment (reported "
            "a scan result instead of flagging it unscannable)"
        )

    return failures


# ---------------------------------------------------------------------------------
# The banner (REQ-44's own closing requirement, stated live).
# ---------------------------------------------------------------------------------


def print_invocation_banner(repo_root: "Path | None" = None) -> bool:
    result = scan_repo(repo_root)
    ok = True

    if result.unscanned_files:
        ok = False
        print(f"ACTUATOR INVOCATION BOUNDARY: {len(result.unscanned_files)} file(s) could "
              f"not be tokenised cleanly (fail-closed, not silently skipped):")
        for f in result.unscanned_files:
            print(f"  [CRITICAL] could not tokenise cleanly: {f}")

    # Group 1: actuator_git::execute, with the explicit allowlisted-count check.
    test_files, non_test_files = classify(result.execute_sites)
    total_non_test_execute_sites = sum(len(result.execute_sites[f]) for f in non_test_files)
    allowed_paths = {e.path for e in ACTUATOR_CALL_ALLOWLIST}
    unallowlisted = [f for f in non_test_files if f not in allowed_paths]
    print(f"ACTUATOR INVOCATION BOUNDARY -- actuator_git::execute: {len(test_files)} test "
          f"call site(s) (file(s)), {total_non_test_execute_sites} non-test call site(s) "
          f"total, expected EXACTLY ONE (REQ-36, REQ-44, EC-18).")
    for f in test_files:
        print(f"  + test call site: {f}")
    for f in non_test_files:
        if f in allowed_paths:
            entry = next(e for e in ACTUATOR_CALL_ALLOWLIST if e.path == f)
            print(f"  + allowlisted non-test call site: {f} ({entry.decision_ref}: "
                  f"{entry.justification})")
    if unallowlisted:
        ok = False
        for f in unallowlisted:
            print(f"  [CRITICAL] unallowlisted non-test call site: {f}")
    if total_non_test_execute_sites != 1:
        ok = False
        print(f"  [CRITICAL] expected exactly one non-test call site of actuator_git::execute, "
              f"found {total_non_test_execute_sites} (EC-18).")
    elif not unallowlisted:
        print("  [PASS] exactly one non-test call site of actuator_git::execute, and it is "
              "the allowlisted one.")
    print()

    # Group 2: broker_authorised_action, no allowlist (REQ-40).
    test_files_b, non_test_files_b = classify(result.baa_sites)
    print(f"ACTUATOR INVOCATION BOUNDARY -- broker_authorised_action: {len(test_files_b)} "
          f"test call site(s), {len(non_test_files_b)} non-test call site(s) (expected "
          f"zero: this step does not advance invariant 3.6, REQ-40; the process engine "
          f"that will call this is build-order step five, not yet built).")
    for f in test_files_b:
        print(f"  + test call site: {f}")
    if non_test_files_b:
        ok = False
        for f in non_test_files_b:
            print(f"  [CRITICAL] non-test call site (no allowlist exists for this symbol): {f}")
    else:
        print("  [PASS] zero non-test call sites of broker_authorised_action.")
    print()
    print("  STATED PLAINLY (REQ-40, section 13 item one of the spec): an actuator that can")
    print("  execute, inside a crate whose one witness-carrying entry point nothing calls,")
    print("  is not \"the gate is invoked live against a real action\". A caller of the")
    print("  caller does not exist yet.")

    return ok


def main() -> int:
    control_failures = control_check()
    if control_failures:
        print("ACTUATOR INVOCATION BOUNDARY negative control FAILED:")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    ok = print_invocation_banner()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
