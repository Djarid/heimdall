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
never a failure. A NON-TEST call site is fatal, full stop: unlike
`gjoll_invocation_harness.py`'s `NON_TEST_ALLOWLIST` (D96, following the
`ALLOWED_IMPORT_ROOTS`/D71 polarity for Gjoll's gate specifically), REQ-45 carries no
allowlist mechanism for Vor. It reads zero non-test call sites on the day this lands
(REQ-45's own closing sentence) and stops reporting a clean boundary the moment a real
caller (step five) is wired in; widening this module with an allowlist, if one is ever
needed, is that future session's own reviewed decision to make, not this one's to
anticipate.
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
    """Print the Vor invocation-boundary banner and return True unless a non-test
    call site or an unscanned file exists.

    On the same pattern `gjoll_invocation_harness.print_invocation_banner`
    established for the Gjoll gate: this states the count live so a future
    session does not have to remember, in prose, that nothing outside a test
    calls the cohort entry point or the secret loaders, and it stops stating a
    clean boundary the moment that changes."""
    status = classify_call_sites(repo_root)
    n_test = len(status["test_files"])
    n_non_test = len(status["non_test_files"])
    n_unscanned = len(status["unscanned_files"])

    print(f"VOR INVOCATION BOUNDARY (detected live by a TOKEN scan, weaker than an "
          f"AST scan -- see the module docstring for what that can miss): {n_test} "
          f"test call site(s), {n_non_test} non-test call site(s).")
    for f in status["test_files"]:
        print(f"  + test call site: {f}")
    if n_non_test:
        for f in status["non_test_files"]:
            print(f"  [CRITICAL] non-test call site (no allowlist exists for this "
                  f"detector): {f}")
    if n_unscanned:
        for f in status["unscanned_files"]:
            print(f"  [CRITICAL] could not tokenise cleanly (fail-closed, not "
                  f"silently skipped): {f}")
    if n_non_test or n_unscanned:
        return False
    return True


# ---------------------------------------------------------------------------------
# REQ-43/AC-47 (build-order step five, process-engine-step-five-spec.md): a
# forward-looking negative-control extension, anticipating REQ-40's own
# widening of this detector with an allowlist naming
# `crates/process-engine/src/main.rs` as the one permitted non-test call
# site of `load_verified_cohort`. This detector carries NO allowlist
# mechanism at all today (REQ-45's own closing sentence), so the meaningful
# thing to prove ahead of that widening is that a synthetic non-test call
# site -- including one at exactly the path the future allowlist will name
# -- is still reported as critical now, against a SYNTHETIC temporary tree
# (never this repository's own working tree). "The allowlisted site
# disappearing" has no meaning yet, because no allowlist exists; that half
# of REQ-43 becomes exercisable only once REQ-40 lands, and is named here as
# a limit rather than faked.
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

    # A non-test call site at exactly the path REQ-40's own future allowlist
    # will name. Today, with no allowlist mechanism at all, this must still
    # be reported as a critical non-test call site.
    root = _write_synthetic_tree({
        "crates/process-engine/src/main.rs": (
            "fn main() {\n    let c = hierarchy_vor::load_verified_cohort(&t);\n}\n"
        ),
    })
    try:
        if print_invocation_banner(root):
            failures.append(
                "synthetic control FAILED: a non-test call site of load_verified_cohort "
                "at crates/process-engine/src/main.rs on a synthetic tree was not "
                "reported as critical (no allowlist mechanism exists for this detector "
                "today, REQ-45; REQ-40 widens this deliberately with exactly one named "
                "entry at this exact path, never silently)")
    finally:
        shutil.rmtree(root, ignore_errors=True)

    # Sanity companion: a synthetic tree with no cohort mention at all must
    # still report a clean boundary, so the detector is not simply always
    # failing.
    root = _write_synthetic_tree({
        "crates/process-engine/src/main.rs": "fn main() {}\n",
    })
    try:
        if not print_invocation_banner(root):
            failures.append(
                "synthetic control FAILED: a synthetic tree with no mention of any "
                "cohort symbol was wrongly reported as having a non-test call site")
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
