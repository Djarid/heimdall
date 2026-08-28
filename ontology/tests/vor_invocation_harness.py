"""Vor's invocation boundary: who actually calls the cohort entry point and the
secret loaders (REQ-45), on `ontology.tests.gjoll_invocation_harness`'s exact
function shapes (D96's precedent).

Run from the repo root:

    python -m ontology.tests.vor_invocation_harness

Why this exists, on the same footing as D96's caveat for Gjoll. This build's job is
to prove `crates/hierarchy-vor/`'s cohort cannot be OBTAINED without its attestation
having verified (D110). It says nothing about whether anything, anywhere, actually
CALLS `load_verified_cohort` or the secret loaders outside a test file. Nothing does,
today: step three (a later issue) is the intended caller, and it is not built yet.
This module is the mechanised form of that fact, so a future session does not have to
remember it in prose, on exactly the pattern `gjoll_invocation_harness.py` already
established for the Gjoll gate and `pipeline_score_harness.py` established before
that.

What it detects, and the honest limit of how (REQ-45). Every textual mention, outside
a comment or a string literal, of `load_verified_cohort`, `load_trusted_set_from_env`
or `load_trusted_set_from_path` in a `.rs` file under the repository. Unlike
`gjoll_invocation_harness.py`, THIS is a TOKEN scan, not an AST scan: Python has no
built-in Rust parser, so this module strips `//` and `/* */` comments (nesting-aware)
and string/byte-string/raw-string literals with a small hand-written state machine,
then matches the three symbol names as whole words in what remains. This is
DELIBERATELY WEAKER than `gjoll_invocation_harness.py`'s AST-resolved import tracking,
and the weakness is named, not hidden:

  - It cannot tell a real function CALL from a mere MENTION: a `use` import, a
    `fn load_verified_cohort_elsewhere` definition with a coincidentally similar
    name that survives the `\\b` word boundary, or a doc comment the stripper failed
    to remove would all count identically to an actual call. (`\\b` word boundaries
    do at least rule out a partial match like `load_verified_cohort_v2`.)
  - It cannot resolve the symbol through a module alias or a re-export the way
    `gjoll_invocation_harness.py`'s `_gjoll_module_aliases` does; every mention of
    the bare name counts, wherever it is bound from.
  - A file it cannot tokenise cleanly (an unterminated block comment, most notably)
    is reported as UNSCANNED rather than silently treated as zero call sites
    (EC-19): a file this detector cannot verify is a failure to verify, never
    silent evidence of a clean boundary, on the same fail-closed discipline
    `gjoll_invocation_harness.py`'s own `_ParseFailure` handling uses for a genuine
    Python `SyntaxError`.

Test-side only, by design. This module lives under `ontology/tests/`, exactly as
`gjoll_invocation_harness.py` does, so it never touches invariant 3.1's authorisation
scan scope and arms nothing.

What it reports and what is fatal. The COUNT of test call sites (a path under
`unit_tests/` or `tests/`, matching REQ-38's own directory split) is reporting-only,
never a failure. A NON-TEST call site is fatal unless it matches
`VOR_CALL_ALLOWLIST` below.

**Build-order step five widening
(`.opencode/plans/process-engine-step-five-spec.md` REQ-40, AC-44).** Before this
step, REQ-45 carried no allowlist mechanism for Vor at all and every non-test call
site was unconditionally fatal, following `gjoll_invocation_harness.py`'s
`NON_TEST_ALLOWLIST`/`ALLOWED_IMPORT_ROOTS` polarity only in spirit, not in
mechanism. Step five's engine crate is the first genuine non-test caller of
`load_verified_cohort`, so this module now carries `VOR_CALL_ALLOWLIST`, an
exactly-one-required allowlist on `himinbjorg_invocation_harness.GATE_CALL_ALLOWLIST`'s
and `actuator_invocation_harness.ACTUATOR_CALL_ALLOWLIST`'s own shape: the named entry
disappearing and an unlisted entry appearing are equally fatal.

**A correction against the spec's own literal text, recorded here rather than
silently reconciled.** REQ-40's own wording names
`crates/process-engine/src/main.rs` as the permitted call site. Reading the built
crate live shows this is not where the call happens: `crates/process-engine/src/main.rs`
never mentions `load_verified_cohort` at all; the real call is in
`crates/process-engine/src/startup.rs`, the delegate module REQ-26 has `main.rs`
hand every environment read to (`main.rs` calls `process_engine::startup::run()`,
which calls `hierarchy_vor::load_trusted_set_from_path` and then
`hierarchy_vor::load_verified_cohort`). `VOR_CALL_ALLOWLIST` below names the file
verified live, `startup.rs`, not the path the spec's own prose assumed.
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

# The three symbols this detector tracks: the crate's one entry point and its two
# secret loaders (section 2.2, REQ-13, REQ-23).
COHORT_SYMBOLS: frozenset[str] = frozenset(
    {"load_verified_cohort", "load_trusted_set_from_env", "load_trusted_set_from_path"}
)

_SYMBOL_RE = re.compile(r"\b(?:" + "|".join(sorted(COHORT_SYMBOLS)) + r")\b")

# Directories never scanned: build output and caches carry no repo-authored call
# site, and scanning them would slow this down for no signal.
_EXCLUDED_DIR_NAMES: frozenset[str] = frozenset({".git", "target", ".venv", "__pycache__"})

# The crate's own definition location. Excluded for the same reason
# `gjoll_invocation_harness.py` excludes `gjoll.py` itself: `load_trusted_set_from_env`'s
# internal call to `load_trusted_set_from_path` (`authoriser.rs`) is one loader
# calling its own sibling, not a wiring call site, and the doc comments and the
# `pub use` re-export line in `lib.rs` mention every symbol by name without calling
# any of them. Counting any of that would report a spurious "non-test call site"
# inside the crate's own source on every run.
_VOR_DEFINITION_DIR: tuple[str, ...] = ("crates", "hierarchy-vor", "src")


def _is_definition_file(rel_parts: tuple[str, ...]) -> bool:
    return rel_parts[: len(_VOR_DEFINITION_DIR)] == _VOR_DEFINITION_DIR


from dataclasses import dataclass


@dataclass(frozen=True)
class NonTestAllowlistEntry:
    """A designated non-test call site of one of `COHORT_SYMBOLS` permitted to
    exist, on `himinbjorg_invocation_harness.NonTestAllowlistEntry`'s and
    `actuator_invocation_harness.NonTestAllowlistEntry`'s own shape.
    `VOR_CALL_ALLOWLIST` below requires EXACTLY the one entry it names
    (REQ-40): the check this module runs fails if the live count of non-test
    call sites is anything other than one, whether that is because a second,
    unlisted site appeared, or because the one allowlisted site vanished."""

    path: str
    justification: str
    decision_ref: str


# THE ALLOWLIST (REQ-40, AC-44, `.opencode/plans/process-engine-step-five-spec.md`):
# exactly one entry, naming the real, empirically-verified non-test call site of
# `hierarchy_vor::load_verified_cohort`, `crates/process-engine/src/startup.rs`
# (not `src/main.rs`, which REQ-40's own literal text assumed -- see the module
# docstring's correction). Widening this tuple to a second entry is how a future
# session would record a genuinely new call site as a reviewed decision, never
# as a change that happens to make this obligation pass by accident.
VOR_CALL_ALLOWLIST: tuple[NonTestAllowlistEntry, ...] = (
    NonTestAllowlistEntry(
        path="crates/process-engine/src/startup.rs",
        justification=(
            "the binary's fail-closed startup contract (REQ-26, REQ-27 of the "
            "process-engine step-five spec): the one module in the crate that reads "
            "the environment, resolving the cohort precondition by loading the "
            "trusted authoriser set and then calling load_verified_cohort exactly "
            "once, before any step of the sequence runs"
        ),
        decision_ref="D113",
    ),
)

for _entry in VOR_CALL_ALLOWLIST:
    # A real `raise`, not a bare `assert` (following
    # gjoll_invocation_harness.py's own Minor-4 fix): this is meant to be an
    # enforced control on a reviewed trust-boundary decision, not a debug-only
    # check.
    if not (_entry.justification and _entry.decision_ref):
        raise ValueError(
            "a VOR_CALL_ALLOWLIST entry must carry both a justification and a "
            "decision reference; see NonTestAllowlistEntry's docstring")


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
    """Returns `(cleaned, unscannable)`. Strips `//` line comments, `/* */` block
    comments (nesting-aware) and string/byte-string/raw-string literals, replacing
    every stripped character with a space (and preserving every real newline as a
    newline), so line numbers computed against `cleaned` still match the original
    file exactly. `unscannable` is True when a comment or string was never
    terminated before end of file (EC-19): that file must be reported as unscanned,
    never silently scanned as empty.

    This is a hand-written token scan, not a lexer: it does not attempt to
    distinguish a character literal (`'x'`) from a lifetime (`&'a str`), because
    both use a single quote and disambiguating them needs more context than a
    token scan carries. See the module docstring for the full list of what this
    approach can miss."""
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
    """Scan every repo `.rs` file for cohort call sites. Returns `(sites,
    unscanned)`: `sites` maps repo-relative path to sorted hit line numbers;
    `unscanned` lists repo-relative paths that could not be tokenised cleanly
    (EC-19), never folded silently into an empty `sites` entry."""
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


def cohort_call_sites(repo_root: "Path | None" = None) -> dict[str, list[int]]:
    """Detect every textual, non-comment, non-string mention of
    `load_verified_cohort`, `load_trusted_set_from_env` or
    `load_trusted_set_from_path` in the repo's `.rs` files. Returns a mapping of
    repo-relative file path to the sorted line numbers where a mention was found.
    Does not distinguish test from non-test (`classify_call_sites` does that) and
    does not surface unscanned files (this function's return type has no room for
    them); callers that must not silently drop an untokenisable file should use
    `classify_call_sites`, whose `unscanned_files` key exists for exactly that
    reason."""
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
    cleanly, EC-19; callers should treat a non-empty `unscanned_files` as fatal,
    the same as a non-test call site, because an unscanned file is a failure to
    verify, not evidence of a clean one)."""
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
# Negative-control probes (REQ-45): before trusting a clean scan, confirm the
# detector actually catches a planted call site and does not flag a source that
# merely mentions the names inside a comment or a string literal.
# ---------------------------------------------------------------------------------

_MUST_CATCH = (
    ("a direct call to the entry point",
     'let c = load_verified_cohort(&trusted);\n'),
    ("a qualified call to the entry point through the crate path",
     'let c = hierarchy_vor::load_verified_cohort(&trusted);\n'),
    ("a call to the env-var secret loader",
     'let t = load_trusted_set_from_env("heimdall-dev-authoriser")?;\n'),
    ("a call to the path secret loader",
     'let t = load_trusted_set_from_path("heimdall-dev-authoriser", &path)?;\n'),
)

_MUST_NOT_CATCH = (
    ("a mention only inside a line comment",
     '// load_verified_cohort(&trusted) is called by step three, not here\n'
     'let x = 1;\n'),
    ("a mention only inside a block comment",
     '/* load_verified_cohort(&trusted) -- not a real call */\n'
     'let x = 1;\n'),
    ("a mention only inside a string literal",
     'let s = "load_verified_cohort";\n'),
    ("a mention only inside a raw string literal",
     'let s = r#"load_trusted_set_from_env"#;\n'),
    ("an unrelated function whose name only shares a prefix (word-boundary control)",
     'fn load_verified_cohort_v2() {}\n'
     'load_verified_cohort_v2();\n'),
)


def control_check() -> list[str]:
    """Run the negative control. Returns a list of failure descriptions (empty if
    the detector behaves): each `_MUST_CATCH` source must produce at least one
    hit, each `_MUST_NOT_CATCH` source must produce none, and a genuinely
    untokenisable file (an unterminated block comment) must be reported as
    unscanned rather than silently scanning clean (EC-19)."""
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

    # Fail-closed control (EC-19): an unterminated block comment must be flagged as
    # unscanned, never silently treated as "no call sites found".
    bad_f = d / "probe.rs"
    bad_f.write_text("/* unterminated comment mentioning load_verified_cohort(&t);\n")
    hits, bad = _scan_file(bad_f)
    if not bad:
        failures.append(
            "detector FAILED to fail-closed on an unterminated block comment "
            "(reported a scan result instead of flagging it unscannable)"
        )

    return failures


def print_invocation_banner(repo_root: "Path | None" = None) -> bool:
    """Print the Vor invocation-boundary banner and return True unless an
    unallowlisted non-test call site, a miscounted allowlist or an unscanned
    file exists.

    On the same pattern `gjoll_invocation_harness.print_invocation_banner`
    established for the Gjoll gate: this states the count live so a future
    session does not have to remember, in prose, who calls the cohort entry
    point or the secret loaders, and it stops stating a clean boundary the
    moment that changes without a reviewed allowlist entry to explain it
    (REQ-40, EC-10, EC-11)."""
    status = classify_call_sites(repo_root)
    n_test = len(status["test_files"])
    non_test_files = status["non_test_files"]
    # Counted by FILE, not by line: `COHORT_SYMBOLS` merges three related
    # symbols (the entry point and its two secret loaders) into one detector,
    # and a single legitimate call site (startup.rs's own precondition
    # resolution, REQ-27) genuinely calls more than one of them from the same
    # file. "Exactly one non-test call site" therefore means exactly one
    # non-test FILE, on REQ-40's own plain-language reading of "the one
    # permitted non-test call site", not exactly one textual hit.
    total_non_test_sites = len(non_test_files)
    n_unscanned = len(status["unscanned_files"])
    ok = True

    allowed_paths = {e.path for e in VOR_CALL_ALLOWLIST}
    unallowlisted = [f for f in non_test_files if f not in allowed_paths]

    print(f"VOR INVOCATION BOUNDARY (detected live by a TOKEN scan, weaker than an "
          f"AST scan -- see the module docstring for what that can miss): {n_test} "
          f"test call site(s) (file(s)), {total_non_test_sites} non-test call "
          f"site(s) (file(s)) total, expected EXACTLY ONE (REQ-40, EC-10, EC-11).")
    for f in status["test_files"]:
        print(f"  + test call site: {f}")
    for f in non_test_files:
        if f in allowed_paths:
            entry = next(e for e in VOR_CALL_ALLOWLIST if e.path == f)
            print(f"  + allowlisted non-test call site: {f} ({entry.decision_ref}: "
                  f"{entry.justification})")
    if unallowlisted:
        ok = False
        for f in unallowlisted:
            print(f"  [CRITICAL] unallowlisted non-test call site: {f}")
    if total_non_test_sites != 1:
        ok = False
        print(f"  [CRITICAL] expected exactly one non-test call site (file) of a "
              f"cohort symbol, found {total_non_test_sites} (EC-10, EC-11).")
    elif not unallowlisted:
        print("  [PASS] exactly one non-test call site of a cohort symbol, and it "
              "is the allowlisted one.")
    if n_unscanned:
        ok = False
        for f in status["unscanned_files"]:
            print(f"  [CRITICAL] could not tokenise cleanly (fail-closed, not "
                  f"silently skipped): {f}")
    return ok


# ---------------------------------------------------------------------------------
# REQ-43/AC-47 (build-order step five, process-engine-step-five-spec.md): a
# negative-control extension proving the widened detector still bites in both
# directions, against SYNTHETIC temporary trees (never this repository's own
# working tree):
#
#   1. A synthetic UNLISTED non-test call site appearing alongside the genuine
#      allowlisted one must still be reported as critical.
#   2. The allowlisted call site synthetically DISAPPEARING (the count falling
#      to zero) must still be reported as critical.
# ---------------------------------------------------------------------------------


def _write_synthetic_tree(files: dict[str, str]) -> Path:
    """Builds a temporary directory tree from a `{relative_path: source}`
    mapping and returns its root. Caller must remove it; never touches this
    repository's own working tree."""
    root = Path(tempfile.mkdtemp(prefix="vor-invocation-boundary-synthetic-"))
    for rel, src in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(src, encoding="utf-8")
    return root


def synthetic_widening_control() -> list[str]:
    failures: list[str] = []

    allowlisted_startup_rs = (
        "fn run() {\n    let c = hierarchy_vor::load_verified_cohort(&t);\n}\n"
    )

    # Direction 1: an extra, UNLISTED non-test call site alongside the
    # genuine allowlisted one.
    root = _write_synthetic_tree({
        "crates/process-engine/src/startup.rs": allowlisted_startup_rs,
        "crates/process-engine/src/other_module.rs": (
            "fn f() {\n    let c2 = hierarchy_vor::load_verified_cohort(&t2);\n}\n"
        ),
    })
    try:
        if print_invocation_banner(root):
            failures.append(
                "synthetic control FAILED: a second, unlisted non-test call site of "
                "load_verified_cohort alongside the allowlisted one was not reported "
                "as critical (REQ-40's own exactly-one-required polarity, EC-10, "
                "EC-11)")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # Direction 2: the allowlisted call site DISAPPEARS (the file exists but
    # no longer calls a cohort symbol at all; the count falls to zero, EC-10).
    root = _write_synthetic_tree({
        "crates/process-engine/src/startup.rs": "fn run() {}\n",
    })
    try:
        if print_invocation_banner(root):
            failures.append(
                "synthetic control FAILED: the allowlisted call site of "
                "load_verified_cohort vanishing (count falls to zero) was not "
                "reported as critical (EC-10's own disappearance-is-fatal polarity)")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # Sanity companion: a synthetic tree with no cohort mention at all must
    # still be reported as fatal (zero is not one), never silently accepted
    # as a clean boundary.
    root = _write_synthetic_tree({
        "crates/process-engine/src/startup.rs": "fn run() {}\n",
        "crates/process-engine/src/main.rs": "fn main() {}\n",
    })
    try:
        if print_invocation_banner(root):
            failures.append(
                "synthetic control FAILED: a synthetic tree with zero cohort call "
                "sites at all was wrongly reported as satisfying the "
                "exactly-one-required allowlist check")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    return failures


def main() -> int:
    control_failures = control_check()
    control_failures += synthetic_widening_control()
    if control_failures:
        print("VOR INVOCATION BOUNDARY negative control FAILED:")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    ok = print_invocation_banner()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
