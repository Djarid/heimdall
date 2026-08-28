"""Target-loop structural detector (`.opencode/plans/build-order-step-six-spec.md`
section 4.6, REQ-36 to REQ-45; section 5.6, AC-41 to AC-50), on
`ontology/tests/rust_process_engine_harness.py`'s exact shape: a module
docstring stating what green proves and does not, a `main()` returning 0
clean or 1 on failure, a `control_check()` negative control run first, and
the checks run in a fixed, documented order.

Run from the repo root:

    python3 -m ontology.tests.rust_target_loop_harness

What this proves, and what it does not. A green result here means:
`crates/process-engine/src/main.rs` carries the five task constant-sets
REQ-6's table fixes, in one array closed at exactly five members by its own
compile-time length assertion, with every member's constants carrying their
own non-emptiness assertions and the five selector names asserted pairwise
distinct at compile time (REQ-38); `HEIMDALL_ENGINE_TASK` and
`TASK_SELECTOR_ENV_VAR` appear in `startup.rs` and nowhere else under
`crates/process-engine/src/`, the selector's own resolution carries no
default, fallback, case-folding, trimming-before-comparison, prefix or
numeric-index branch, and the selector's value reaches nothing but an index
lookup (REQ-39); the postures already checked for step five still hold
without regression -- one `[[bin]]` target, `#![forbid(unsafe_code)]` at
file scope in both crate roots with the `unsafe` keyword absent, no
`std::process` reference beyond the one disclosed `std::process::exit` in
`main.rs`, no `std::net`, no filesystem write entry point anywhere in
`src/`, and the disclosed three-name dependency table with `actuator-git`
still fatal if it appears (REQ-40); `ontology/tools/run_target_loop.py`
contains no `git commit`, no `git push` and no `git merge` invocation in any
recognisable form (REQ-41); and `TARGET_LOOP_EVIDENCE.md`, if present,
matches its own pinned SHA-256 digest, with an honest, non-silent printed
marker either way (REQ-42, REQ-43). It also means this crate's own Rust
suite passes, or is loudly skipped if no toolchain is present, on
`rust_process_engine_harness.py`'s own skip-if-absent precedent (REQ-37).

It says NOTHING about invariant 3.6's live-invocation status, about whether
the target loop was ever actually run, about the real commit-reachable-in-a-
remote claim (AC-1, AC-2, which are confirmed by hand, never by an automated
test, per the spec's own convention), and about whether `Decision::Allow`
was ever reached for real. This module never runs the loop: it spawns no
git process, creates no repository, reads no secret, sets no environment
variable that reaches a spawned process, and invokes
`ontology/tools/run_target_loop.py` nowhere (REQ-37). It is a STRUCTURAL
detector over committed source and committed evidence alone, exactly as
`rust_process_engine_harness.py` is for step five's own postures.

This module is deliberately NOT wired into `ontology/tests/harness.py` yet:
that wiring (one new `Report` counter, one `run_rust_target_loop(rep)`
obligation registered immediately after `run_rust_process_engine(rep)`) is
REQ-44's own, separate obligation, left for a later code change. Running
this module directly, as shown above, is the only way to invoke it for now.

Checks, run in this fixed order (REQ-36), each preceded by its own negative
control, and the negative controls run first as a block, refusing to trust
every check below if any control fails:

  1. The closed task set (REQ-38): the array's compile-time length
     assertion is present and asserts exactly five; the array carries
     exactly REQ-6's table's five members, verbatim; every member's five
     named constants (`task_id`, `action_name`, `target`, `sink`, the
     selector name) carry their own non-emptiness assertions; and the five
     selector names carry a compile-time pairwise-distinctness assertion.
     A source scan proxy, not a full parser, on this repository's own
     established discipline (see `rust_process_engine_harness.py`'s own
     docstring for the same disclosure): literal-string presence and
     `assert!` occurrence counting, never full AST parsing.
  2. The selector's containment (REQ-39): `TASK_SELECTOR_ENV_VAR` and the
     literal `HEIMDALL_ENGINE_TASK` appear in `startup.rs` and nowhere else
     under `crates/process-engine/src/`; the resolution carries no default,
     fallback, case-folding, trimming, prefix or numeric-index pattern; and
     no `EngineTask` field assignment anywhere in the crate is fed directly
     from an identifier that names the selector. Also: `derive_selector_name`
     (REQ-11's own positive derivation rule) is applied to every
     `(action_name, target, selector_name)` triple extracted, by
     textual/regex scan, from the REAL `main.rs` constants, never merely
     self-tested in isolation, so an edit to a member's `action_name` or
     `target` without the matching `selector_name` edit is caught here.
  2b. The two independently hand-maintained, position-aligned arrays --
      `main.rs`'s `TASK_MEMBERS` and `startup.rs`'s `ACCEPTED_SELECTOR_NAMES`
      -- are asserted to list the same five selector names in the same
      order (REQ-39), since the selector resolves one shared index into
      both; a reordering of one without the other would otherwise silently
      route a selector name to the wrong member.
  3. The postures already checked for step five, restated (REQ-40),
     DUPLICATED here rather than imported from `rust_process_engine_harness`
     (a target-loop regression and an engine-crate posture regression are
     different reasons to change, exactly as REQ-40 itself requires): one
     `[[bin]]` target; `#![forbid(unsafe_code)]` in both crate roots with no
     `unsafe` keyword; `std::process`/`std::net` absence with the one
     disclosed `std::process::exit` exception; no filesystem write entry
     point anywhere in `src/`; and the three-name dependency table with
     `actuator-git` fatal if present. The dependency-posture HALF of this
     check reuses (never reimplements) `rust_gate_harness.check_dependency_posture`,
     honouring REQ-36's own instruction to import a helper where one exists.
  4. The driver's own restraint (REQ-41): `ontology/tools/run_target_loop.py`
     contains no `git commit`, `git push` or `git merge` invocation in any
     recognisable argument-list or string form.
  5. Evidence digest drift (REQ-42, REQ-43): `TARGET_LOOP_EVIDENCE.md`'s
     SHA-256 digest, if the file exists, is compared against a pinned value
     in this module; a mismatch is fatal; absence prints
     `TARGET-LOOP-EVIDENCE-ABSENT` and is not fatal (the document is a later
     obligation, REQ-55, not yet landed); this module never recomputes and
     rewrites the pinned digest itself. **The pinned digest below is a
     placeholder** (64 zero characters), deliberately chosen so it can never
     accidentally match real content; updating it to the real digest, once
     `TARGET_LOOP_EVIDENCE.md` is committed, is REQ-55's and REQ-42's own
     later, deliberate, reviewed edit -- not this module's.
  6. This crate's own Rust suite (REQ-37), via the REUSED `toolchain_present`
     and `run_rust_suite` helpers, skip-if-absent on `rust_process_engine_harness.py`'s
     own precedent.

REQ-36's own instruction, honoured: this module imports `check_dependency_posture`,
`toolchain_present` and `run_rust_suite` from `rust_gate_harness`; it adds no
second copy of any of the three. Every other check below has no existing
reusable counterpart scoped to this crate's own new task-shape and selector
properties, so each is written fresh here, on the same mechanical-proxy,
not-a-full-parser discipline this repository's sibling harnesses already
establish and document.
"""

from __future__ import annotations

import hashlib
import re
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import rust_gate_harness

REPO_ROOT = Path(__file__).resolve().parents[2]
CRATE_DIR = REPO_ROOT / "crates" / "process-engine"
CRATE_MANIFEST = CRATE_DIR / "Cargo.toml"
SRC_DIR = CRATE_DIR / "src"
MAIN_RS = SRC_DIR / "main.rs"
STARTUP_RS = SRC_DIR / "startup.rs"
LIB_RS = SRC_DIR / "lib.rs"
RUN_TARGET_LOOP_PY = REPO_ROOT / "ontology" / "tools" / "run_target_loop.py"
EVIDENCE_MD = REPO_ROOT / "TARGET_LOOP_EVIDENCE.md"

# The selector's own named constant and its value (REQ-14, REQ-39, AC-45).
TASK_SELECTOR_ENV_VAR_NAME = "TASK_SELECTOR_ENV_VAR"
TASK_SELECTOR_ENV_VAR_VALUE = "HEIMDALL_ENGINE_TASK"

# Duplicated (never imported from rust_process_engine_harness.py, REQ-40's
# own instruction): the disclosed three-name dependency allowlist and the
# one forbidden name.
PERMITTED_DEPENDENCIES: frozenset[str] = frozenset(
    {"himinbjorg", "hierarchy-vor", "boundary-gjoll"}
)
FORBIDDEN_DEPENDENCIES: frozenset[str] = frozenset({"actuator-git"})

_PERMITTED_STD_PROCESS_OCCURRENCE = "std::process::exit"
_PERMITTED_STD_PROCESS_FILE = "main.rs"

_FORBIDDEN_FS_WRITE_PATTERNS: tuple[str, ...] = (
    "fs::write(",
    "fs::File::create(",
    "File::create(",
    "OpenOptions::new(",
    "fs::create_dir(",
    "fs::create_dir_all(",
    "fs::remove_file(",
    "fs::remove_dir(",
    "fs::remove_dir_all(",
    "fs::copy(",
    "fs::rename(",
)

# The selector's own resolution must carry none of these (REQ-17, REQ-39):
# no default, no fallback, no case folding, no trimming-before-comparison,
# no prefix match, no numeric-index acceptance.
_DEFAULTING_OR_FUZZY_PATTERNS: tuple[str, ...] = (
    "unwrap_or(",
    "unwrap_or_else(",
    "unwrap_or_default(",
    "to_lowercase(",
    "to_ascii_lowercase(",
    "to_uppercase(",
    "to_ascii_uppercase(",
    "starts_with(",
    "parse::<usize>",
    "parse::<u32>",
    "parse::<i32>",
    "trim_start_matches(",
    "trim_end_matches(",
)

# REQ-6's table, fixed exactly: (selector, task_id, action_name, target,
# sink, declared_cost). Never derived from any of Himinbjörg's, Vör's or
# the actuator's own constants (REQ-4), and never read by this harness from
# any other list either: this is this harness's own, independent copy of
# the spec's fixed table, exactly as REQ-6 itself requires of `main.rs`.
TASK_TABLE: tuple[tuple[str, str, str, str, str, int], ...] = (
    ("commit-fixture-target", "target-loop-commit-fixture-target", "action:git.commit", "fixture-target", "sink:git.commit", 0),
    ("push-fixture-integration-branch", "target-loop-push-fixture-integration-branch", "action:git.push", "fixture-integration-branch", "sink:git.push", 0),
    ("merge-fixture-target", "target-loop-merge-fixture-target", "action:git.merge", "fixture-target", "sink:git.commit", 0),
    ("push-main", "target-loop-push-main", "action:git.push", "main", "sink:git.push", 0),
    ("push-fixture-target", "target-loop-push-fixture-target", "action:git.push", "fixture-target", "sink:git.push", 0),
)

# The real SHA-256 digest of the committed TARGET_LOOP_EVIDENCE.md (REQ-42),
# computed by hand with `shasum -a 256 TARGET_LOOP_EVIDENCE.md` after the file
# was written and reviewed, and pinned here as a deliberate, reviewed edit --
# never something this module computes and rewrites itself. A later edit to
# the recorded proof is detected as digest drift rather than silently
# absorbed.
PINNED_EVIDENCE_SHA256 = "cf91d0383793abc6b1c428caeb8299c170df72078fd2b6e19ba116d295a3f394"


def derive_selector_name(action_name: str, target: str) -> str:
    """REQ-11's own positive derivation rule: the action name's leaf (the
    substring after the `action:git.` prefix) joined to the target by a
    single hyphen. A pure function, so a mismatch is provable independent
    of any file scan."""
    prefix = "action:git."
    leaf = action_name[len(prefix):] if action_name.startswith(prefix) else action_name
    return f"{leaf}-{target}"


# `derive_selector_name`'s own isolated self-test inside `control_check()`
# proves the FUNCTION is correct; it proves nothing about whether the REAL,
# committed `P1_SELECTOR_NAME` .. `N3_SELECTOR_NAME` constants in main.rs
# actually satisfy it. `extract_member_selector_triples` below closes that
# gap: a genuine textual/regex extraction (this repository's own source
# scan proxy discipline, never a full parser and never a hardcoded copy of
# the expected values, which would drift silently the same way) of each
# member's own `(action_name, target, selector_name)` triple, so
# `check_selector_containment` can apply `derive_selector_name` to the
# REAL extracted pair and assert the result against the REAL extracted
# selector name.
_SELECTOR_NAME_CONST_RE = re.compile(r'const\s+(\w+)_SELECTOR_NAME\s*:\s*&str\s*=\s*"([^"]*)"')


def extract_member_selector_triples(src: str) -> list[tuple[str, str, str, str]]:
    """Extracts every `(prefix, action_name, target, selector_name)`
    quadruple this source text's own `const <PREFIX>_SELECTOR_NAME`,
    `const <PREFIX>_ACTION_NAME` and `const <PREFIX>_TARGET` constants
    carry, by textual/regex extraction alone. A prefix whose companion
    `_ACTION_NAME` or `_TARGET` constant is missing is silently skipped
    here rather than raising; this stays a pure extraction step, and the
    caller decides what an empty or partial result means."""
    triples: list[tuple[str, str, str, str]] = []
    for prefix, selector_name in _SELECTOR_NAME_CONST_RE.findall(src):
        action_match = re.search(
            rf'const\s+{re.escape(prefix)}_ACTION_NAME\s*:\s*&str\s*=\s*"([^"]*)"', src
        )
        target_match = re.search(
            rf'const\s+{re.escape(prefix)}_TARGET\s*:\s*&str\s*=\s*"([^"]*)"', src
        )
        if action_match and target_match:
            triples.append((prefix, action_match.group(1), target_match.group(1), selector_name))
    return triples


def _strip_line_comments(src: str) -> str:
    """Mirrors `rust_process_engine_harness._strip_line_comments`'s own
    reasoning; duplicated, not imported, following this repository's own
    convention of duplicating a short, test-only helper across sibling
    harnesses."""
    out_lines = []
    for line in src.split("\n"):
        idx = line.find("//")
        if idx == -1:
            out_lines.append(line)
        else:
            out_lines.append(line[:idx] + " " * (len(line) - idx))
    return "\n".join(out_lines)


def _load_rust_files(src_dir: Path) -> dict[str, str]:
    if not src_dir.exists():
        return {}
    return {
        str(p.relative_to(src_dir)): p.read_text(encoding="utf-8")
        for p in sorted(src_dir.rglob("*.rs"))
    }


@dataclass
class CheckResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    detail: str = ""
    marker: str = ""


# ---------------------------------------------------------------------------------
# Check 1: the closed task set (REQ-38, AC-44).
# ---------------------------------------------------------------------------------


def _count_len_n_assertions(src: str, n: int) -> int:
    return len(re.findall(rf"assert!\s*\(\s*[\w:]+\.len\(\)\s*==\s*{n}\b", src))


def _count_non_emptiness_assertions(src: str) -> int:
    return len(re.findall(r"const\s+_\s*:\s*\(\)\s*=\s*assert!", src))


def _has_pairwise_distinctness_assertion(src: str) -> bool:
    """Mechanical proxy, not a full parser (this repository's own
    established discipline): a compile-time assertion asserting five
    values pairwise distinct needs at least four `!=` comparisons (a
    chained a != b && b != c && c != d && d != e shape, or equivalent);
    fewer than that cannot possibly cover all five members, so this
    threshold is a necessary, not sufficient, mechanical signal."""
    for m in re.finditer(r"const\s+_\s*:\s*\(\)\s*=\s*assert!\(.*?\)\s*;", src, re.DOTALL):
        if m.group(0).count("!=") >= 4:
            return True
    return False


def check_closed_task_set(main_rs_path: Path = MAIN_RS, table: tuple = TASK_TABLE) -> CheckResult:
    if not main_rs_path.exists():
        return CheckResult(ok=False, detail=f"{main_rs_path} does not exist")
    src = _strip_line_comments(main_rs_path.read_text(encoding="utf-8"))
    violations: list[str] = []

    for row in table:
        selector, task_id, action_name, target, sink, _cost = row
        for label, value in (
            ("selector name", selector),
            ("task_id", task_id),
            ("action_name", action_name),
            ("target", target),
            ("sink", sink),
        ):
            literal = f'"{value}"'
            if literal not in src:
                violations.append(
                    f"member {selector!r}: missing literal {literal} ({label}) -- REQ-6's "
                    f"table requires this value verbatim"
                )

    if _count_len_n_assertions(src, 5) == 0:
        violations.append(
            "no compile-time `assert!(<array>.len() == 5)` found in main.rs (REQ-9): an "
            "edit that adds or removes a member must fail the build, not a later test run"
        )

    assertion_count = _count_non_emptiness_assertions(src)
    expected_minimum = 5 * 5 + 1  # five fields per member, five members, plus the length assertion
    if assertion_count < expected_minimum:
        violations.append(
            f"found only {assertion_count} `const _: () = assert!` occurrence(s) in "
            f"main.rs; expected at least {expected_minimum} (REQ-8: one non-emptiness "
            f"assertion per task_id/action_name/target/sink/selector-name, for each of "
            f"the five members, plus the array's own length assertion)"
        )

    if not _has_pairwise_distinctness_assertion(src):
        violations.append(
            "no compile-time assertion found asserting the five selector names are "
            "pairwise distinct (REQ-11): expected an `assert!` containing at least four "
            "`!=` comparisons"
        )

    if violations:
        return CheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return CheckResult(
        ok=True,
        detail="all thirty of REQ-6's literal values are present verbatim, the array's "
               "compile-time length assertion asserts exactly five, at least 26 "
               "non-emptiness assertions are present, and a pairwise-distinctness "
               "assertion over the five selector names is present.",
    )


# ---------------------------------------------------------------------------------
# Check 2: the selector's containment (REQ-39, AC-45).
# ---------------------------------------------------------------------------------

_FIELD_FED_BY_SELECTOR_RE = re.compile(
    r"\b(action_name|target|sink|declared_cost|task_id)\s*:\s*[^,\n}]*\bselector\w*"
)


def check_selector_containment(
    src_dir: Path = SRC_DIR, startup_filename: str = "startup.rs"
) -> CheckResult:
    files = _load_rust_files(src_dir)
    if not files:
        return CheckResult(ok=False, detail=f"{src_dir} does not exist")

    violations: list[str] = []
    startup_raw = files.get(startup_filename)
    if startup_raw is None:
        violations.append(f"{startup_filename} does not exist under {src_dir}")
        startup_raw = ""

    for fname, raw_src in files.items():
        cleaned = _strip_line_comments(raw_src)
        if fname == startup_filename:
            continue
        if TASK_SELECTOR_ENV_VAR_VALUE in cleaned or TASK_SELECTOR_ENV_VAR_NAME in cleaned:
            violations.append(
                f"{fname}: the selector's own name ({TASK_SELECTOR_ENV_VAR_NAME!r}) or "
                f"literal ({TASK_SELECTOR_ENV_VAR_VALUE!r}) must appear in {startup_filename} "
                f"alone (REQ-39); found it here too"
            )

    startup_cleaned = _strip_line_comments(startup_raw)
    if TASK_SELECTOR_ENV_VAR_VALUE not in startup_cleaned:
        violations.append(
            f"{startup_filename} does not carry the literal {TASK_SELECTOR_ENV_VAR_VALUE!r} "
            f"(REQ-14, REQ-39)"
        )

    for pattern in _DEFAULTING_OR_FUZZY_PATTERNS:
        if pattern in startup_cleaned:
            violations.append(
                f"{startup_filename} contains {pattern!r}, a defaulting/fallback/"
                f"case-folding/trimming/prefix/numeric-index pattern forbidden on the "
                f"selector's own resolution path (REQ-17, REQ-39)"
            )

    whole_crate = "\n".join(_strip_line_comments(v) for v in files.values())
    field_hits = _FIELD_FED_BY_SELECTOR_RE.findall(whole_crate)
    if field_hits:
        violations.append(
            f"found an EngineTask field fed directly from an identifier naming the "
            f"selector ({sorted(set(field_hits))}); the selector's only product must be "
            f"an index into the closed array (REQ-18, REQ-39)"
        )

    # REQ-11's derivation rule, applied to the REAL, extracted constants
    # (finding I1's own fix): a member whose `action_name` or `target`
    # changed without its own `selector_name` following would otherwise
    # pass this harness undetected, since `derive_selector_name`'s own
    # self-test in `control_check()` exercises the function alone, never
    # the committed constants.
    main_raw = files.get("main.rs")
    if main_raw is not None:
        main_cleaned = _strip_line_comments(main_raw)
        extracted_triples = extract_member_selector_triples(main_cleaned)
        # This assertion, not the derivation loop below, is what closes the
        # gap `extract_member_selector_triples`'s own docstring discloses: a
        # prefix whose companion `_ACTION_NAME` or `_TARGET` constant fails
        # to match is silently dropped BY THE EXTRACTOR, so a for-loop over
        # its result alone can report a clean pass having checked fewer than
        # five members, or none. This is an EXTRACTION-SHAPE problem --
        # the regex scan could not find all five members' own constants,
        # e.g. because a future edit to main.rs's constant-declaration shape
        # inlined values directly into the struct literal instead of
        # declaring them via named `const <PREFIX>_ACTION_NAME`/`_TARGET`
        # constants -- and is reported distinctly from a REQ-11 derivation
        # mismatch (checked in the loop below), so a reader is never left
        # unsure which of the two failed.
        if len(extracted_triples) != 5:
            violations.append(
                f"main.rs: extract_member_selector_triples found only "
                f"{len(extracted_triples)} member (action_name, target, selector_name) "
                f"triple(s) by regex scan, but exactly 5 are expected -- this is an "
                f"EXTRACTION-SHAPE problem (the scan could not locate all five members' "
                f"own companion `_ACTION_NAME`/`_TARGET` constants), not a REQ-11 "
                f"derivation mismatch; a change to main.rs's constant-declaration shape "
                f"(for example inlining a member's values directly into the struct "
                f"literal instead of via named constants) would otherwise silently "
                f"reduce how many members this check actually examines, down to zero, "
                f"while still reporting a clean pass"
            )
        for prefix, action_name, target, selector_name in extracted_triples:
            derived = derive_selector_name(action_name, target)
            if derived != selector_name:
                violations.append(
                    f"main.rs: {prefix}_SELECTOR_NAME is {selector_name!r}, but REQ-11's "
                    f"derivation rule applied to {prefix}_ACTION_NAME={action_name!r} and "
                    f"{prefix}_TARGET={target!r} derives {derived!r} instead -- an edit to "
                    f"the action name or target without the matching selector-name edit "
                    f"would otherwise pass undetected"
                )

    if violations:
        return CheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return CheckResult(
        ok=True,
        detail=f"{TASK_SELECTOR_ENV_VAR_NAME}/{TASK_SELECTOR_ENV_VAR_VALUE} appear in "
               f"{startup_filename} alone; the resolution carries no default, fallback, "
               f"case-folding, trimming, prefix or numeric-index pattern; no EngineTask "
               f"field is fed directly from a selector-named identifier; and every "
               f"extracted (action_name, target, selector_name) triple found in main.rs "
               f"satisfies REQ-11's derivation rule.",
    )


# ---------------------------------------------------------------------------------
# Check 2b: main.rs's `TASK_MEMBERS` and startup.rs's own
# `ACCEPTED_SELECTOR_NAMES` agree, position for position (REQ-39, finding
# I2). The two arrays are independently hand-maintained (startup.rs's own
# doc comment says so directly: "The two arrays are independent,
# hand-maintained agreements... an edit to either array without the
# matching edit to the other is a silent divergence neither compiler nor
# this module can detect by itself"); nothing mechanical checked that
# claim until now. Extraction only, on this file's own established
# discipline: never a hardcoded copy of either array's expected order,
# which would drift silently the same way finding I2 itself describes.
# ---------------------------------------------------------------------------------

_TASK_MEMBERS_ARRAY_RE = re.compile(
    r"const\s+TASK_MEMBERS\s*:\s*\[EngineTaskMember;\s*5\]\s*=\s*\[(.*?)\];", re.DOTALL
)
_MEMBER_SELECTOR_FIELD_RE = re.compile(r"selector_name\s*:\s*(\w+)_SELECTOR_NAME")
_ACCEPTED_SELECTOR_NAMES_ARRAY_RE = re.compile(
    r"const\s+ACCEPTED_SELECTOR_NAMES\s*:\s*\[&str;\s*5\]\s*=\s*\[(.*?)\];", re.DOTALL
)
_QUOTED_STRING_RE = re.compile(r'"([^"]*)"')


def extract_task_members_selector_order(main_rs_src: str) -> list[str] | None:
    """Extracts the ordered list of selector names as `TASK_MEMBERS`
    itself lists its members, from main.rs's own committed source text:
    finds the `TASK_MEMBERS` array literal, reads each member's own
    `selector_name: <PREFIX>_SELECTOR_NAME` field in the order the
    members appear, and resolves each prefix to that prefix's own `const
    <PREFIX>_SELECTOR_NAME: &str = "..."` literal. Returns `None` if the
    array literal, or a field it references, cannot be found -- never
    raises -- so a caller can report absence as its own violation rather
    than crashing."""
    array_match = _TASK_MEMBERS_ARRAY_RE.search(main_rs_src)
    if array_match is None:
        return None
    prefixes = _MEMBER_SELECTOR_FIELD_RE.findall(array_match.group(1))
    if not prefixes:
        return None
    const_map = dict(_SELECTOR_NAME_CONST_RE.findall(main_rs_src))
    names: list[str] = []
    for prefix in prefixes:
        name = const_map.get(prefix)
        if name is None:
            return None
        names.append(name)
    return names


def extract_accepted_selector_names_order(startup_rs_src: str) -> list[str] | None:
    """Extracts the ordered list of selector names as
    `ACCEPTED_SELECTOR_NAMES` itself lists them, from startup.rs's own
    committed source text, by the same textual/regex extraction
    discipline. Returns `None` if the array literal cannot be found."""
    array_match = _ACCEPTED_SELECTOR_NAMES_ARRAY_RE.search(startup_rs_src)
    if array_match is None:
        return None
    names = _QUOTED_STRING_RE.findall(array_match.group(1))
    if not names:
        return None
    return names


def check_task_members_and_accepted_selector_order_agree(
    main_rs_path: Path = MAIN_RS, startup_rs_path: Path = STARTUP_RS
) -> CheckResult:
    """Extracts, from both committed files' source text, the ordered list
    of the five selector names as they actually appear -- from main.rs's
    `TASK_MEMBERS` and from startup.rs's `ACCEPTED_SELECTOR_NAMES` -- and
    asserts the two ordered lists are identical, position for position
    (REQ-39, finding I2). A reordering of one array without the matching
    reordering of the other would otherwise silently route a selector
    name to the wrong member; nothing else in this crate or this harness
    checks that the two independently hand-maintained arrays agree."""
    if not main_rs_path.exists():
        return CheckResult(ok=False, detail=f"{main_rs_path} does not exist")
    if not startup_rs_path.exists():
        return CheckResult(ok=False, detail=f"{startup_rs_path} does not exist")

    main_src = _strip_line_comments(main_rs_path.read_text(encoding="utf-8"))
    startup_src = _strip_line_comments(startup_rs_path.read_text(encoding="utf-8"))

    main_order = extract_task_members_selector_order(main_src)
    startup_order = extract_accepted_selector_names_order(startup_src)

    if main_order is None:
        return CheckResult(
            ok=False,
            detail=f"could not extract TASK_MEMBERS's own selector-name order from "
                   f"{main_rs_path}",
        )
    if startup_order is None:
        return CheckResult(
            ok=False,
            detail=f"could not extract ACCEPTED_SELECTOR_NAMES's own order from "
                   f"{startup_rs_path}",
        )

    violations: list[str] = []
    if len(main_order) != len(startup_order):
        violations.append(
            f"TASK_MEMBERS lists {len(main_order)} selector name(s) but "
            f"ACCEPTED_SELECTOR_NAMES lists {len(startup_order)}; the two arrays must be "
            f"the same length to share one index space"
        )
    else:
        for i, (m_name, s_name) in enumerate(zip(main_order, startup_order)):
            if m_name != s_name:
                violations.append(
                    f"position {i}: TASK_MEMBERS names {m_name!r} but "
                    f"ACCEPTED_SELECTOR_NAMES names {s_name!r} -- the selector resolves "
                    f"one shared index into both arrays (REQ-39), so a reordering of one "
                    f"without the other would route a selector name to the wrong member"
                )

    if violations:
        return CheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return CheckResult(
        ok=True,
        detail=f"TASK_MEMBERS and ACCEPTED_SELECTOR_NAMES list the same "
               f"{len(main_order)} selector names in the same order.",
    )


# ---------------------------------------------------------------------------------
# Check 3: the postures already checked for step five, restated (REQ-40,
# AC-46). Duplicated, never imported from rust_process_engine_harness.py,
# because a target-loop regression and an engine-crate posture regression
# are different reasons to change (REQ-40's own wording).
# ---------------------------------------------------------------------------------


def check_exactly_one_binary_target(manifest_path: Path = CRATE_MANIFEST) -> CheckResult:
    if not manifest_path.exists():
        return CheckResult(ok=False, detail=f"{manifest_path} does not exist")
    data = tomllib.loads(manifest_path.read_text())
    bins = data.get("bin", []) or []
    if len(bins) != 1:
        return CheckResult(
            ok=False,
            violations=[f"Cargo.toml declares {len(bins)} [[bin]] target(s), expected exactly 1"],
            detail=f"{len(bins)} != 1",
        )
    return CheckResult(ok=True, detail="Cargo.toml declares exactly one [[bin]] target.")


def check_forbid_unsafe_in_both_roots_and_no_unsafe_keyword(
    lib_rs_path: Path = LIB_RS, main_rs_path: Path = MAIN_RS, src_dir: Path = SRC_DIR
) -> CheckResult:
    violations: list[str] = []
    for label, path in (("src/lib.rs", lib_rs_path), ("src/main.rs", main_rs_path)):
        if not path.exists():
            violations.append(f"{label} does not exist")
            continue
        stripped = path.read_text(encoding="utf-8").lstrip()
        if not stripped.startswith("#![forbid(unsafe_code)]"):
            violations.append(
                f"{label} does not begin with `#![forbid(unsafe_code)]` at file scope"
            )
    files = _load_rust_files(src_dir)
    unsafe_re = re.compile(r"\bunsafe\b")
    for fname, raw_src in files.items():
        cleaned = _strip_line_comments(raw_src)
        for m in unsafe_re.finditer(cleaned):
            lineno = cleaned.count("\n", 0, m.start()) + 1
            violations.append(f"{fname}:{lineno}: the `unsafe` keyword appears in this crate's src/")
    if violations:
        return CheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return CheckResult(
        ok=True,
        detail="src/lib.rs and src/main.rs both begin with #![forbid(unsafe_code)], and "
               "the `unsafe` keyword appears nowhere in this crate's src/.",
    )


def check_std_process_and_std_net_absence(src_dir: Path = SRC_DIR) -> CheckResult:
    files = _load_rust_files(src_dir)
    violations: list[str] = []
    net_re = re.compile(r"std::net\b")
    process_re = re.compile(r"std::process(?:::\w+)?")
    for fname, raw_src in files.items():
        cleaned = _strip_line_comments(raw_src)
        for m in net_re.finditer(cleaned):
            lineno = cleaned.count("\n", 0, m.start()) + 1
            violations.append(f"{fname}:{lineno}: found `std::net` (no disclosed exception exists)")
        for m in process_re.finditer(cleaned):
            lineno = cleaned.count("\n", 0, m.start()) + 1
            occurrence = m.group(0)
            if fname == _PERMITTED_STD_PROCESS_FILE and occurrence == _PERMITTED_STD_PROCESS_OCCURRENCE:
                continue
            violations.append(
                f"{fname}:{lineno}: found `{occurrence}`, not the one disclosed exception "
                f"(`{_PERMITTED_STD_PROCESS_OCCURRENCE}` in `{_PERMITTED_STD_PROCESS_FILE}` alone)"
            )
    if violations:
        return CheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return CheckResult(
        ok=True,
        detail="std::net is absent everywhere in src/, and the only std::process "
               f"occurrence is `{_PERMITTED_STD_PROCESS_OCCURRENCE}` in "
               f"{_PERMITTED_STD_PROCESS_FILE}.",
    )


def check_no_filesystem_write_entry_point(src_dir: Path = SRC_DIR) -> CheckResult:
    files = _load_rust_files(src_dir)
    violations: list[str] = []
    for fname, raw_src in files.items():
        cleaned = _strip_line_comments(raw_src)
        for pattern in _FORBIDDEN_FS_WRITE_PATTERNS:
            if pattern in cleaned:
                violations.append(f"{fname}: found {pattern!r}, a filesystem write entry point")
    if violations:
        return CheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return CheckResult(ok=True, detail="no filesystem write entry point found anywhere in src/.")


def check_dependency_posture_restated(manifest_path: Path = CRATE_MANIFEST) -> CheckResult:
    """The [dependencies] half reuses (never reimplements)
    `rust_gate_harness.check_dependency_posture`, honouring REQ-36's own
    instruction. The allowlist and the forbidden-name re-check are this
    module's own duplicated data (REQ-40)."""
    result = rust_gate_harness.check_dependency_posture(manifest_path, PERMITTED_DEPENDENCIES)
    if not result.manifest_found:
        return CheckResult(ok=True, detail=result.detail)
    if not result.ok:
        return CheckResult(ok=False, violations=result.violations, detail=result.detail)
    data = tomllib.loads(manifest_path.read_text())
    deps = data.get("dependencies", {}) or {}
    violations = [
        f"[dependencies] carries {forbidden!r}, which must remain absent"
        for forbidden in sorted(FORBIDDEN_DEPENDENCIES)
        if forbidden in deps
    ]
    if violations:
        return CheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return CheckResult(ok=True, detail=result.detail)


def check_restated_postures() -> CheckResult:
    violations: list[str] = []
    details: list[str] = []
    for result in (
        check_exactly_one_binary_target(),
        check_forbid_unsafe_in_both_roots_and_no_unsafe_keyword(),
        check_std_process_and_std_net_absence(),
        check_no_filesystem_write_entry_point(),
        check_dependency_posture_restated(),
    ):
        if not result.ok:
            violations += result.violations or [result.detail]
        else:
            details.append(result.detail)
    if violations:
        return CheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return CheckResult(ok=True, detail=" ".join(details))


# ---------------------------------------------------------------------------------
# Check 4: the driver's own restraint (REQ-41, AC-47).
# ---------------------------------------------------------------------------------

_GIT_INVOCATION_PATTERNS: dict[str, tuple[str, ...]] = {
    "commit": (r'"git"\s*,\s*"commit"', r"'git'\s*,\s*'commit'", r'"git\s+commit', r"'git\s+commit"),
    "push": (r'"git"\s*,\s*"push"', r"'git'\s*,\s*'push'", r'"git\s+push', r"'git\s+push"),
    "merge": (r'"git"\s*,\s*"merge"', r"'git'\s*,\s*'merge'", r'"git\s+merge', r"'git\s+merge"),
}


def check_driver_restraint(driver_path: Path = RUN_TARGET_LOOP_PY) -> CheckResult:
    if not driver_path.exists():
        return CheckResult(
            ok=False,
            detail=f"{driver_path} does not exist yet (REQ-23 has not landed)",
        )
    src = driver_path.read_text(encoding="utf-8")
    violations: list[str] = []
    for operation, patterns in _GIT_INVOCATION_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, src):
                violations.append(f"found a git {operation} invocation matching {pattern!r}")
    if violations:
        return CheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return CheckResult(
        ok=True,
        detail="no git commit, git push or git merge invocation found in any recognisable form.",
    )


# ---------------------------------------------------------------------------------
# Check 5: evidence digest drift (REQ-42, REQ-43, AC-48).
# ---------------------------------------------------------------------------------


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_evidence_digest(
    evidence_path: Path = EVIDENCE_MD, pinned: str = PINNED_EVIDENCE_SHA256
) -> CheckResult:
    if not evidence_path.exists():
        return CheckResult(
            ok=True,
            marker="TARGET-LOOP-EVIDENCE-ABSENT",
            detail=f"{evidence_path} does not exist yet (REQ-55 has not landed); this is "
                   f"reported, never a silent pass.",
        )
    digest = _sha256_of(evidence_path)
    if digest != pinned:
        return CheckResult(
            ok=False,
            marker="TARGET-LOOP-EVIDENCE-PRESENT",
            violations=[f"pinned digest {pinned} does not match computed digest {digest}"],
            detail="digest drift detected",
        )
    return CheckResult(
        ok=True,
        marker="TARGET-LOOP-EVIDENCE-PRESENT",
        detail="the pinned SHA-256 digest matches the committed evidence file.",
    )


# ---------------------------------------------------------------------------------
# Check 6: this crate's own Rust suite (REQ-37), REUSED helpers only.
# ---------------------------------------------------------------------------------


def toolchain_present() -> bool:
    return rust_gate_harness.toolchain_present()


def run_rust_suite(crate_dir: Path = CRATE_DIR) -> tuple[bool, str]:
    return rust_gate_harness.run_rust_suite(crate_dir)


# ---------------------------------------------------------------------------------
# Negative controls (REQ-36, AC-42). At least one synthetic violation and
# one synthetic legitimate case per check, proving each scan bites in both
# directions.
# ---------------------------------------------------------------------------------


def _synthetic_main_rs_all_five(extra_asserts: int = 0, distinct_assert: bool = True) -> str:
    lines = ["#![forbid(unsafe_code)]", "fn main() {}", ""]
    asserts = 0
    for row in TASK_TABLE:
        selector, task_id, action_name, target, sink, _cost = row
        for value in (task_id, action_name, target, sink, selector):
            lines.append(f'const _: () = assert!(!"{value}".is_empty());')
            asserts += 1
    for i in range(extra_asserts):
        lines.append(f'const _: () = assert!(!"filler-{i}".is_empty());')
        asserts += 1
    lines.append('const _: () = assert!(TASK_MEMBERS.len() == 5);')
    if distinct_assert:
        names = [row[0] for row in TASK_TABLE]
        chain = " && ".join(f'"{names[i]}" != "{names[i+1]}"' for i in range(len(names) - 1))
        lines.append(f"const _: () = assert!({chain});")
    return "\n".join(lines)


_MEMBER_PREFIXES: tuple[str, ...] = ("P1", "P2", "N1", "N2", "N3")


def _synthetic_full_main_rs(
    selector_overrides: dict[str, str] | None = None,
    member_order: list[int] | None = None,
) -> str:
    """Builds a synthetic main.rs carrying the REAL file's own shape (one
    `const <PREFIX>_SELECTOR_NAME`/`_ACTION_NAME`/`_TARGET` triple per
    member, and one `TASK_MEMBERS` array literal referencing them by
    name, in `EngineTaskMember { selector_name: <PREFIX>_SELECTOR_NAME,
    ... }` form), on `TASK_TABLE`'s own five rows. Used by both the
    finding-I1 derivation-application controls and the finding-I2
    order-agreement controls below, so a single fixture generator proves
    both checks bite against a realistic, committed-shaped file rather
    than only against `derive_selector_name`'s or the array-order
    extraction's own isolated inputs.

    `selector_overrides` maps a prefix to a replacement selector-name
    literal (used to plant a REQ-11 derivation mismatch without touching
    the real file). `member_order` reorders which row occupies which
    `TASK_MEMBERS` array position (used to plant an order-agreement
    mismatch against a startup.rs fixture)."""
    selector_overrides = selector_overrides or {}
    indices = member_order if member_order is not None else list(range(len(TASK_TABLE)))
    lines = ["#![forbid(unsafe_code)]", "fn main() {}", ""]
    for i, row in enumerate(TASK_TABLE):
        prefix = _MEMBER_PREFIXES[i]
        selector, task_id, action_name, target, sink, _cost = row
        selector = selector_overrides.get(prefix, selector)
        lines.append(f'const {prefix}_SELECTOR_NAME: &str = "{selector}";')
        lines.append(f'const {prefix}_TASK_ID: &str = "{task_id}";')
        lines.append(f'const {prefix}_ACTION_NAME: &str = "{action_name}";')
        lines.append(f'const {prefix}_TARGET: &str = "{target}";')
        lines.append(f'const {prefix}_SINK: &str = "{sink}";')
    lines.append("const TASK_MEMBERS: [EngineTaskMember; 5] = [")
    for i in indices:
        prefix = _MEMBER_PREFIXES[i]
        lines.append("    EngineTaskMember {")
        lines.append(f"        selector_name: {prefix}_SELECTOR_NAME,")
        lines.append(f"        task_id: {prefix}_TASK_ID,")
        lines.append(f"        action_name: {prefix}_ACTION_NAME,")
        lines.append(f"        target: {prefix}_TARGET,")
        lines.append(f"        sink: {prefix}_SINK,")
        lines.append("    },")
    lines.append("];")
    return "\n".join(lines)


def _synthetic_startup_rs(selector_order: list[str] | None = None) -> str:
    """Builds a synthetic startup.rs carrying only the shape the
    order-agreement extraction needs: `TASK_SELECTOR_ENV_VAR`'s own
    literal (so `check_selector_containment`'s other sub-checks do not
    misfire on a fixture reused across both), and `ACCEPTED_SELECTOR_NAMES`
    in the given order (`TASK_TABLE`'s own order by default)."""
    order = selector_order if selector_order is not None else [row[0] for row in TASK_TABLE]
    lines = [f'pub const {TASK_SELECTOR_ENV_VAR_NAME}: &str = "{TASK_SELECTOR_ENV_VAR_VALUE}";']
    lines.append("const ACCEPTED_SELECTOR_NAMES: [&str; 5] = [")
    for name in order:
        lines.append(f'    "{name}",')
    lines.append("];")
    return "\n".join(lines)


def control_check() -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as d:
        base = Path(d)

        # -------------------------------------------------------------
        # Check 1 controls: closed task set.
        # -------------------------------------------------------------

        # Legitimate: all five members, length assertion == 5, plenty of
        # non-emptiness assertions, a pairwise-distinctness assertion.
        legit_main = base / "main_legit.rs"
        legit_main.write_text(_synthetic_main_rs_all_five())
        legit_result = check_closed_task_set(legit_main)
        if not legit_result.ok:
            failures.append(
                f"closed-task-set control WRONGLY flagged a fully compliant synthetic "
                f"main.rs: {legit_result.violations}"
            )

        # Violation: four members (N3 dropped), length assertion == 4.
        four_member = base / "main_four.rs"
        four_lines = _synthetic_main_rs_all_five().replace(
            'const _: () = assert!(TASK_MEMBERS.len() == 5);',
            'const _: () = assert!(TASK_MEMBERS.len() == 4);',
        )
        # Remove N3's literals to genuinely simulate a four-member array.
        for value in TASK_TABLE[-1][:5]:
            four_lines = four_lines.replace(f'const _: () = assert!(!"{value}".is_empty());\n', "")
        four_member.write_text(four_lines)
        four_result = check_closed_task_set(four_member)
        if four_result.ok:
            failures.append("closed-task-set control did NOT catch a four-member array")

        # Violation: six members (an extra, unlisted sixth), length
        # assertion == 6.
        six_member = base / "main_six.rs"
        six_lines = _synthetic_main_rs_all_five().replace(
            'const _: () = assert!(TASK_MEMBERS.len() == 5);',
            'const _: () = assert!(TASK_MEMBERS.len() == 6);\n'
            'const _: () = assert!(!"sixth-member-unlisted".is_empty());',
        )
        six_member.write_text(six_lines)
        six_result = check_closed_task_set(six_member)
        if six_result.ok:
            failures.append("closed-task-set control did NOT catch a six-member array")

        # Violation: missing length assertion entirely.
        missing_len = base / "main_missing_len.rs"
        missing_len_src = _synthetic_main_rs_all_five().replace(
            'const _: () = assert!(TASK_MEMBERS.len() == 5);', ""
        )
        missing_len.write_text(missing_len_src)
        missing_len_result = check_closed_task_set(missing_len)
        if missing_len_result.ok:
            failures.append("closed-task-set control did NOT catch a missing length assertion")

        # Violation: too few non-emptiness assertions (strip most of them).
        few_asserts = base / "main_few_asserts.rs"
        few_lines = "\n".join(
            _synthetic_main_rs_all_five().split("\n")[:6]
            + ['const _: () = assert!(TASK_MEMBERS.len() == 5);']
        )
        few_asserts.write_text(few_lines)
        few_asserts_result = check_closed_task_set(few_asserts)
        if few_asserts_result.ok:
            failures.append(
                "closed-task-set control did NOT catch main.rs carrying too few "
                "non-emptiness assertions"
            )

        # Violation: no pairwise-distinctness assertion.
        no_distinct = base / "main_no_distinct.rs"
        no_distinct.write_text(_synthetic_main_rs_all_five(distinct_assert=False))
        no_distinct_result = check_closed_task_set(no_distinct)
        if no_distinct_result.ok:
            failures.append(
                "closed-task-set control did NOT catch a missing pairwise-distinctness "
                "assertion over the five selector names"
            )

        # Violation: a selector name that does not match REQ-11's
        # derivation rule (pure-function control, independent of any file).
        if derive_selector_name("action:git.push", "main") != "push-main":
            failures.append(
                "derive_selector_name control: the legitimate case (push, main) did not "
                "derive to 'push-main'"
            )
        mismatched_selector = "delete-everything"
        if derive_selector_name("action:git.push", "main") == mismatched_selector:
            failures.append(
                "derive_selector_name control did NOT distinguish a mismatched selector "
                "name from the correctly derived one"
            )

        # -------------------------------------------------------------
        # Check 2 controls: selector containment.
        # -------------------------------------------------------------

        legit_src = base / "src_selector_legit"
        legit_src.mkdir()
        (legit_src / "startup.rs").write_text(
            f'pub const {TASK_SELECTOR_ENV_VAR_NAME}: &str = "{TASK_SELECTOR_ENV_VAR_VALUE}";\n'
            "fn resolve(v: Option<&str>) -> Result<usize, String> {\n"
            "    match v { Some(x) if x == \"commit-fixture-target\" => Ok(0), _ => Err(\"refused\".to_string()) }\n"
            "}\n"
        )
        # Real-shaped (all five members' own constants present), so this
        # fixture also satisfies the extraction-count assertion below,
        # rather than incidentally tripping it while testing something else.
        (legit_src / "main.rs").write_text(_synthetic_full_main_rs())
        legit_containment = check_selector_containment(legit_src)
        if not legit_containment.ok:
            failures.append(
                f"selector-containment control WRONGLY flagged a compliant synthetic "
                f"crate: {legit_containment.violations}"
            )

        # Violation: the selector read outside startup.rs.
        leaked_src = base / "src_selector_leaked"
        leaked_src.mkdir()
        (leaked_src / "startup.rs").write_text(
            f'pub const {TASK_SELECTOR_ENV_VAR_NAME}: &str = "{TASK_SELECTOR_ENV_VAR_VALUE}";\n'
        )
        (leaked_src / "main.rs").write_text(
            f'fn main() {{ let _ = std::env::var("{TASK_SELECTOR_ENV_VAR_VALUE}"); }}\n'
        )
        leaked_result = check_selector_containment(leaked_src)
        if leaked_result.ok:
            failures.append(
                "selector-containment control did NOT catch the selector literal leaking "
                "outside startup.rs"
            )

        # Violation: a defaulting selector resolution.
        defaulting_src = base / "src_selector_default"
        defaulting_src.mkdir()
        (defaulting_src / "startup.rs").write_text(
            f'pub const {TASK_SELECTOR_ENV_VAR_NAME}: &str = "{TASK_SELECTOR_ENV_VAR_VALUE}";\n'
            "fn resolve(v: Option<&str>) -> usize {\n"
            "    v.map(|s| 0).unwrap_or(0)\n"
            "}\n"
        )
        (defaulting_src / "main.rs").write_text("fn main() {}\n")
        defaulting_result = check_selector_containment(defaulting_src)
        if defaulting_result.ok:
            failures.append(
                "selector-containment control did NOT catch a defaulting selector "
                "resolution (unwrap_or)"
            )

        # Violation: an EngineTask field fed directly from the selector.
        field_fed_src = base / "src_selector_field_fed"
        field_fed_src.mkdir()
        (field_fed_src / "startup.rs").write_text(
            f'pub const {TASK_SELECTOR_ENV_VAR_NAME}: &str = "{TASK_SELECTOR_ENV_VAR_VALUE}";\n'
        )
        (field_fed_src / "main.rs").write_text(
            "fn main() { let t = EngineTask { action_name: selector_value.clone(), .. }; }\n"
        )
        field_fed_result = check_selector_containment(field_fed_src)
        if field_fed_result.ok:
            failures.append(
                "selector-containment control did NOT catch an EngineTask field fed "
                "directly from a selector-named identifier"
            )

        # Violation (finding I1): a real-shaped main.rs whose P1_SELECTOR_NAME
        # has been mutated so it no longer matches REQ-11's derivation rule
        # applied to its own P1_ACTION_NAME/P1_TARGET. Proves the extraction
        # added to check_selector_containment actually bites against a
        # realistic, committed-shaped file -- not merely against
        # derive_selector_name's own isolated self-test above.
        mismatched_derivation_src = base / "src_selector_mismatched_derivation"
        mismatched_derivation_src.mkdir()
        (mismatched_derivation_src / "startup.rs").write_text(
            f'pub const {TASK_SELECTOR_ENV_VAR_NAME}: &str = "{TASK_SELECTOR_ENV_VAR_VALUE}";\n'
        )
        (mismatched_derivation_src / "main.rs").write_text(
            _synthetic_full_main_rs(selector_overrides={"P1": "delete-everything"})
        )
        mismatched_derivation_result = check_selector_containment(mismatched_derivation_src)
        if mismatched_derivation_result.ok:
            failures.append(
                "selector-containment control did NOT catch a main.rs whose "
                "P1_SELECTOR_NAME does not match REQ-11's derivation rule applied to "
                "its own P1_ACTION_NAME/P1_TARGET"
            )

        # Legitimate (finding I1): the same real-shaped main.rs, unmutated,
        # proving the extraction does not over-fire against a genuinely
        # compliant set of constants.
        correct_derivation_src = base / "src_selector_correct_derivation"
        correct_derivation_src.mkdir()
        (correct_derivation_src / "startup.rs").write_text(
            f'pub const {TASK_SELECTOR_ENV_VAR_NAME}: &str = "{TASK_SELECTOR_ENV_VAR_VALUE}";\n'
        )
        (correct_derivation_src / "main.rs").write_text(_synthetic_full_main_rs())
        correct_derivation_result = check_selector_containment(correct_derivation_src)
        if not correct_derivation_result.ok:
            failures.append(
                f"selector-containment control WRONGLY flagged a main.rs whose selector "
                f"names all match REQ-11's derivation rule: "
                f"{correct_derivation_result.violations}"
            )
        # Explicit, not merely incidental: proves extraction over the same
        # unmutated fixture actually found all five triples (the exactly-5
        # case this module's new extraction-count assertion must permit),
        # rather than the check above passing for some unrelated reason.
        correct_derivation_extracted = extract_member_selector_triples(
            _strip_line_comments(_synthetic_full_main_rs())
        )
        if len(correct_derivation_extracted) != 5:
            failures.append(
                f"extraction-count control: extract_member_selector_triples found "
                f"{len(correct_derivation_extracted)} triple(s) over a fully compliant "
                f"synthetic main.rs, expected exactly 5"
            )

        # Violation (extraction-shape gap, one layer below finding I1): a
        # real-shaped main.rs where P1's own companion `_ACTION_NAME`
        # constant has been renamed, so `extract_member_selector_triples`
        # itself -- by its own documented, silent-skip behaviour -- returns
        # only 4 triples rather than 5. Proves `check_selector_containment`
        # treats this as a genuine, named failure (an extraction-shape
        # problem) rather than silently checking fewer than five members
        # and reporting a clean pass.
        missing_companion_src = base / "src_selector_missing_companion"
        missing_companion_src.mkdir()
        (missing_companion_src / "startup.rs").write_text(
            f'pub const {TASK_SELECTOR_ENV_VAR_NAME}: &str = "{TASK_SELECTOR_ENV_VAR_VALUE}";\n'
        )
        broken_main_src = _synthetic_full_main_rs().replace(
            "P1_ACTION_NAME", "P1_ACTION_NAME_RENAMED"
        )
        (missing_companion_src / "main.rs").write_text(broken_main_src)
        missing_companion_result = check_selector_containment(missing_companion_src)
        if missing_companion_result.ok:
            failures.append(
                "selector-containment control did NOT catch main.rs's P1 member losing "
                "its own extractable _ACTION_NAME companion constant (extraction found "
                "fewer than 5 triples, but the check reported a clean pass)"
            )
        elif not any("found only 4" in v for v in missing_companion_result.violations):
            failures.append(
                f"selector-containment control caught the missing companion constant "
                f"but did not name the actual extracted count (4) as an "
                f"extraction-shape problem: {missing_companion_result.violations}"
            )

        # -------------------------------------------------------------
        # Check 2b controls: TASK_MEMBERS/ACCEPTED_SELECTOR_NAMES order
        # agreement (finding I2).
        # -------------------------------------------------------------

        # Legitimate: the two arrays list the same five names in the same
        # order, proving the order-agreement check does not over-fire.
        order_legit_main = base / "order_legit_main.rs"
        order_legit_main.write_text(_synthetic_full_main_rs())
        order_legit_startup = base / "order_legit_startup.rs"
        order_legit_startup.write_text(_synthetic_startup_rs())
        order_legit_result = check_task_members_and_accepted_selector_order_agree(
            order_legit_main, order_legit_startup
        )
        if not order_legit_result.ok:
            failures.append(
                f"order-agreement control WRONGLY flagged a matching TASK_MEMBERS/"
                f"ACCEPTED_SELECTOR_NAMES order: {order_legit_result.violations}"
            )

        # Violation: startup.rs's own ACCEPTED_SELECTOR_NAMES has its first
        # two entries swapped relative to main.rs's own TASK_MEMBERS, with
        # no matching edit to main.rs -- exactly the silent divergence
        # finding I2 describes. Proves the check catches it and reports the
        # disagreeing position by name.
        order_bad_main = base / "order_bad_main.rs"
        order_bad_main.write_text(_synthetic_full_main_rs())
        order_bad_startup = base / "order_bad_startup.rs"
        swapped_order = [row[0] for row in TASK_TABLE]
        swapped_order[0], swapped_order[1] = swapped_order[1], swapped_order[0]
        order_bad_startup.write_text(_synthetic_startup_rs(swapped_order))
        order_bad_result = check_task_members_and_accepted_selector_order_agree(
            order_bad_main, order_bad_startup
        )
        if order_bad_result.ok:
            failures.append(
                "order-agreement control did NOT catch startup.rs's ACCEPTED_SELECTOR_NAMES "
                "being reordered relative to main.rs's own TASK_MEMBERS"
            )
        elif not any("position 0" in v for v in order_bad_result.violations):
            failures.append(
                f"order-agreement control caught the reordering but did not report the "
                f"disagreeing position by name: {order_bad_result.violations}"
            )

        # -------------------------------------------------------------
        # Check 3 controls: restated postures.
        # -------------------------------------------------------------

        # 3a: one [[bin]] target.
        two_bins = base / "Cargo-twobins.toml"
        two_bins.write_text(
            '[package]\nname = "process-engine"\n\n'
            '[[bin]]\nname = "process-engine"\npath = "src/main.rs"\n\n'
            '[[bin]]\nname = "second"\npath = "src/second.rs"\n'
        )
        if check_exactly_one_binary_target(two_bins).ok:
            failures.append("binary-target control did NOT catch a manifest with two [[bin]] targets")

        # 3b: forbid(unsafe_code) both roots, no unsafe keyword.
        unsafe_dir = base / "src_unsafe"
        unsafe_dir.mkdir()
        (unsafe_dir / "lib.rs").write_text("#![forbid(unsafe_code)]\n")
        (unsafe_dir / "main.rs").write_text("fn main() {}\n")  # missing forbid
        (unsafe_dir / "execute.rs").write_text("fn f() { unsafe { std::ptr::null::<u8>(); } }\n")
        unsafe_result = check_forbid_unsafe_in_both_roots_and_no_unsafe_keyword(
            unsafe_dir / "lib.rs", unsafe_dir / "main.rs", unsafe_dir
        )
        if unsafe_result.ok:
            failures.append(
                "forbid(unsafe_code)/unsafe-keyword control did NOT catch a missing "
                "attribute and a planted unsafe keyword"
            )
        good_unsafe_dir = base / "src_unsafe_good"
        good_unsafe_dir.mkdir()
        (good_unsafe_dir / "lib.rs").write_text("#![forbid(unsafe_code)]\nfn f() {}\n")
        (good_unsafe_dir / "main.rs").write_text("#![forbid(unsafe_code)]\nfn main() {}\n")
        good_unsafe_result = check_forbid_unsafe_in_both_roots_and_no_unsafe_keyword(
            good_unsafe_dir / "lib.rs", good_unsafe_dir / "main.rs", good_unsafe_dir
        )
        if not good_unsafe_result.ok:
            failures.append(
                f"forbid(unsafe_code)/unsafe-keyword control WRONGLY flagged a compliant "
                f"synthetic crate: {good_unsafe_result.violations}"
            )

        # 3c: std::process::Command and std::net planted.
        proc_dir = base / "src_proc"
        proc_dir.mkdir()
        (proc_dir / "main.rs").write_text(
            'fn main() { std::process::exit(0); std::process::Command::new("x"); }\n'
        )
        (proc_dir / "other.rs").write_text('fn f() { let _ = std::net::TcpStream::connect("x"); }\n')
        proc_result = check_std_process_and_std_net_absence(proc_dir)
        if proc_result.ok or len(proc_result.violations) < 2:
            failures.append(
                "std::process/std::net control did NOT catch a planted std::process::"
                "Command call and a planted std::net call"
            )
        clean_proc_dir = base / "src_proc_clean"
        clean_proc_dir.mkdir()
        (clean_proc_dir / "main.rs").write_text("fn main() { std::process::exit(0); }\n")
        clean_proc_result = check_std_process_and_std_net_absence(clean_proc_dir)
        if not clean_proc_result.ok:
            failures.append(
                "std::process/std::net control WRONGLY flagged the one disclosed "
                "std::process::exit exception in main.rs"
            )

        # 3d: filesystem write entry point planted.
        fs_dir = base / "src_fs"
        fs_dir.mkdir()
        (fs_dir / "sneaky.rs").write_text('fn f() { std::fs::write("x", b"y").unwrap(); }\n')
        fs_result = check_no_filesystem_write_entry_point(fs_dir)
        if fs_result.ok:
            failures.append("filesystem-write control did NOT catch a planted fs::write call")
        clean_fs_dir = base / "src_fs_clean"
        clean_fs_dir.mkdir()
        (clean_fs_dir / "clean.rs").write_text("fn f() {}\n")
        clean_fs_result = check_no_filesystem_write_entry_point(clean_fs_dir)
        if not clean_fs_result.ok:
            failures.append("filesystem-write control WRONGLY flagged a clean synthetic file")

        # 3e: actuator-git dependency planted.
        bad_dep_manifest = base / "Cargo-actuator.toml"
        bad_dep_manifest.write_text(
            '[package]\nname = "process-engine"\n\n[dependencies]\n'
            'himinbjorg = { path = "../himinbjorg" }\n'
            'hierarchy-vor = { path = "../hierarchy-vor" }\n'
            'boundary-gjoll = { path = "../boundary-gjoll" }\n'
            'actuator-git = { path = "../actuator-git" }\n'
        )
        if check_dependency_posture_restated(bad_dep_manifest).ok:
            failures.append("dependency-posture control did NOT catch a planted actuator-git dependency")
        clean_dep_manifest = base / "Cargo-clean.toml"
        clean_dep_manifest.write_text(
            '[package]\nname = "process-engine"\n\n[dependencies]\n'
            'himinbjorg = { path = "../himinbjorg" }\n'
            'hierarchy-vor = { path = "../hierarchy-vor" }\n'
            'boundary-gjoll = { path = "../boundary-gjoll" }\n'
        )
        if not check_dependency_posture_restated(clean_dep_manifest).ok:
            failures.append(
                "dependency-posture control WRONGLY flagged a manifest carrying only the "
                "three disclosed, permitted dependencies"
            )

        # -------------------------------------------------------------
        # Check 4 controls: driver restraint.
        # -------------------------------------------------------------

        bad_driver = base / "run_target_loop_bad.py"
        bad_driver.write_text(
            "import subprocess\n"
            'subprocess.run(["git", "commit", "-m", "x"])\n'
            'subprocess.run(["git", "push", "origin", "x"])\n'
            'subprocess.run(["git", "merge", "x"])\n'
        )
        bad_driver_result = check_driver_restraint(bad_driver)
        if bad_driver_result.ok or len(bad_driver_result.violations) < 3:
            failures.append(
                "driver-restraint control did NOT catch a planted git commit, a planted "
                "git push and a planted git merge"
            )
        good_driver = base / "run_target_loop_good.py"
        good_driver.write_text(
            "import subprocess\n"
            'subprocess.run(["git", "add", "."])\n'
            'subprocess.run(["git", "checkout", "fixture-integration-branch"])\n'
        )
        good_driver_result = check_driver_restraint(good_driver)
        if not good_driver_result.ok:
            failures.append(
                f"driver-restraint control WRONGLY flagged a compliant synthetic driver: "
                f"{good_driver_result.violations}"
            )

        # -------------------------------------------------------------
        # Check 5 controls: evidence digest drift.
        # -------------------------------------------------------------

        evidence_file = base / "TARGET_LOOP_EVIDENCE.md"
        evidence_file.write_text("# Target loop evidence\n\nsome content\n")
        real_digest = _sha256_of(evidence_file)
        matching_result = check_evidence_digest(evidence_file, pinned=real_digest)
        if not matching_result.ok:
            failures.append("evidence-digest control WRONGLY flagged a matching digest")

        evidence_file.write_text("# Target loop evidence\n\nSOME CONTENT WAS EDITED\n")
        mutated_result = check_evidence_digest(evidence_file, pinned=real_digest)
        if mutated_result.ok:
            failures.append("evidence-digest control did NOT catch a mutated evidence file")

        absent_result = check_evidence_digest(base / "does-not-exist.md", pinned=real_digest)
        if absent_result.marker != "TARGET-LOOP-EVIDENCE-ABSENT" or not absent_result.ok:
            failures.append(
                "evidence-digest control did NOT print TARGET-LOOP-EVIDENCE-ABSENT for a "
                "genuinely absent file, or wrongly treated absence as fatal"
            )

    return failures


def main() -> int:
    print("Target-loop structural detector (REQ-36 to REQ-45): the closed five-member")
    print("task set, the selector's containment, the postures restated from step five,")
    print("the driver's own restraint, and evidence digest drift, for")
    print("crates/process-engine/ and ontology/tools/run_target_loop.py. This module")
    print("never runs the target loop itself (REQ-37). See this module's own docstring")
    print("for what a green result proves and does not, and note that it is NOT yet")
    print("wired into ontology/tests/harness.py (REQ-44 is a separate, later obligation).")
    print()

    control_failures = control_check()
    if control_failures:
        print("NEGATIVE CONTROL FAILED (refusing to trust the checks below):")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    print(
        "  [PASS] negative controls: every planted violation (a four-member array, a "
        "six-member array, a missing length assertion, too few non-emptiness "
        "assertions, a missing pairwise-distinctness assertion, a mismatched "
        "selector-derivation name, a selector leaked outside startup.rs, a "
        "defaulting selector resolution, a selector-fed EngineTask field, a "
        "real-shaped main.rs whose selector name does not match REQ-11's derivation "
        "rule applied to its own extracted action_name/target, a "
        "TASK_MEMBERS/ACCEPTED_SELECTOR_NAMES ordering disagreement, a "
        "two-binary-target manifest, a missing forbid(unsafe_code)/planted unsafe "
        "keyword, a planted std::process::Command call, a planted std::net call, a "
        "planted filesystem write, a planted actuator-git dependency, planted git "
        "commit/push/merge invocations, and a mutated evidence digest) is caught, "
        "while every corresponding legitimate synthetic case is correctly permitted."
    )
    print()

    task_set_result = check_closed_task_set()
    print(f"  [{'PASS' if task_set_result.ok else 'CRITICAL'}] closed task set (REQ-38): {task_set_result.detail}")
    if not task_set_result.ok:
        for v in task_set_result.violations:
            print(f"    - {v}")
        return 1

    containment_result = check_selector_containment()
    print(f"  [{'PASS' if containment_result.ok else 'CRITICAL'}] selector containment (REQ-39): {containment_result.detail}")
    if not containment_result.ok:
        for v in containment_result.violations:
            print(f"    - {v}")
        return 1

    order_agreement_result = check_task_members_and_accepted_selector_order_agree()
    print(
        f"  [{'PASS' if order_agreement_result.ok else 'CRITICAL'}] TASK_MEMBERS/"
        f"ACCEPTED_SELECTOR_NAMES order agreement (REQ-39): {order_agreement_result.detail}"
    )
    if not order_agreement_result.ok:
        for v in order_agreement_result.violations:
            print(f"    - {v}")
        return 1

    postures_result = check_restated_postures()
    print(f"  [{'PASS' if postures_result.ok else 'CRITICAL'}] restated postures (REQ-40): {postures_result.detail}")
    if not postures_result.ok:
        for v in postures_result.violations:
            print(f"    - {v}")
        return 1

    driver_result = check_driver_restraint()
    print(f"  [{'PASS' if driver_result.ok else 'CRITICAL'}] driver restraint (REQ-41): {driver_result.detail}")
    if not driver_result.ok:
        for v in driver_result.violations:
            print(f"    - {v}")
        return 1

    evidence_result = check_evidence_digest()
    marker_line = f"  [{'PASS' if evidence_result.ok else 'CRITICAL'}] evidence digest (REQ-42, REQ-43): {evidence_result.detail}"
    print(marker_line)
    print(f"  {evidence_result.marker}")
    if not evidence_result.ok:
        for v in evidence_result.violations:
            print(f"    - {v}")
        return 1

    print()
    if not toolchain_present():
        print("  [SKIP] no Rust toolchain found on this machine (cargo not on PATH).")
        print("  The checks above already ran; only the Rust suite is skipped. This is")
        print("  not a failure.")
        return 0

    ok, detail = run_rust_suite()
    print(f"  [{'PASS' if ok else 'CRITICAL'}] Rust suite: {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
