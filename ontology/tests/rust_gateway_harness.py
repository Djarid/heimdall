"""Himinbjörg gateway posture detector (D111, `.opencode/plans/himinbjorg-step-three.md`
REQ-27): is `crates/himinbjorg/` dependency-clean, test-and-code isolated, sufficient on
its public surface, and passing, following `ontology/tests/rust_cohort_harness.py`'s
exact shape (REQ-30).

Run from the repo root:

    python -m ontology.tests.rust_gateway_harness

What this proves, and what it does not. A green result here means the crate at
`crates/himinbjorg/` carries no dependency beyond its permitted in-workspace path
dependencies (widened by `.opencode/plans/git-actuator-step-four.md` REQ-6 from two
names to three: `boundary-gjoll`, `hierarchy-vor`, `actuator-git`), keeps every test
construct out of `src/`, re-exports exactly its public interfaces (the original four
plus step four's fifth, `broker_authorised_action`) plus their refusal and decision
types with an `AgentContext` carrying no raw-content-shaped field, never constructs
`Decision::Queue` or `Decision::Escalate` outside a test path, and passes its own Rust
suite (or loudly skips that one step alone, if no toolchain is present). It says
NOTHING about invariant 3.6's live-invocation status: whether the gate this crate calls
is itself called by anything outside this crate's own tests is a DIFFERENT and
separately governed claim, reported live by `ontology.tests.himinbjorg_invocation_harness`
and `ontology.tests.actuator_invocation_harness`, not by this module.

Four checks, run in this fixed order (REQ-27), the first three fatal regardless of
whether a Rust toolchain is even present, because dependency posture, test isolation and
public-surface sufficiency are all facts about the committed source, not about the
toolchain:

  1. Dependency posture. REUSES (never reimplements) the WIDENED
     `ontology.tests.rust_gate_harness.check_dependency_posture` (REQ-30), called with
     an allowlist permitting exactly the two in-workspace path dependencies HB3-3
     names. Fatal on any external, unlisted or non-path dependency, with the exemption
     stated in this check's own output, never hidden.
  2. Test and code isolation (REQ-5). A scan over `crates/himinbjorg/src/` confirming
     the only test-related lines anywhere under it are `lib.rs`'s own
     `#[cfg(test)] #[path = "../unit_tests/..."] mod ...;` declarations, and that no
     file name appears under both `src/` and either `unit_tests/` or `tests/`.
  3. Public-surface checks. `AgentContext`'s field set matches the enumerated names
     (REQ-8) and contains no raw-content-shaped field (`content`, `payload`, `raw`,
     `body`, `text`, `window`); the crate re-exports exactly its public interfaces
     (the original four plus step four's `broker_authorised_action`) plus their
     refusal and decision types (`ContextRefusal`, `DefinitionRefusal`,
     `BrokerRefusal`, `ProposalDecision`); `Decision::Queue` and `Decision::Escalate`
     appear in no construction position outside a test path (REQ-21).
  4. The Rust suite, invoked via the REUSED `toolchain_present` and `run_rust_suite`
     helpers (REQ-30), scoped to this crate's own manifest. Skip discipline follows
     `memgraph_integration_harness.py`'s precedent (also `rust_gate_harness.py`'s own):
     skip detection keys on the toolchain-presence probe alone, never on whether the
     test run itself would have succeeded. A present toolchain whose test run returns
     non-zero is always fatal, never laundered into a skip (EC-16, EC-17).

REQ-30's own instruction: this module imports `check_dependency_posture`,
`toolchain_present` and `run_rust_suite` from `rust_gate_harness`; it adds no second
copy of any of the three. The test-isolation and public-surface checks below have no
existing reusable counterpart (each existing sub-harness's own version is hardcoded to
a different crate's field and type names), so they are written fresh here, on the same
mechanical-proxy, not-a-full-parser discipline `rust_cohort_harness.py`'s own six
surface checks already establish and document.
"""

from __future__ import annotations

import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import rust_gate_harness

REPO_ROOT = Path(__file__).resolve().parents[2]
CRATE_DIR = REPO_ROOT / "crates" / "himinbjorg"
CRATE_MANIFEST = CRATE_DIR / "Cargo.toml"
SRC_DIR = CRATE_DIR / "src"
UNIT_TESTS_DIR = CRATE_DIR / "unit_tests"
TESTS_DIR = CRATE_DIR / "tests"
LIB_RS = SRC_DIR / "lib.rs"
TYPES_RS = SRC_DIR / "types.rs"

# HB3-3, widened by `.opencode/plans/git-actuator-step-four.md` REQ-6 (AC-3, AC-51):
# the exact THREE in-workspace path dependencies this crate is permitted, and no
# other entry of any kind (REQ-3, REQ-30). Widening this set from two names to three
# is itself AC-51's own claim; `rust_gate_harness.check_dependency_posture`'s default
# (no allowlist argument, used by `boundary-gjoll` and `hierarchy-vor` directly) is
# UNCHANGED by this widening, so those two crates keep their strict, zero-dependency
# behaviour byte for byte (AC-51, section 9.2 of that spec).
PERMITTED_PATH_DEPENDENCIES: frozenset[str] = frozenset(
    {"boundary-gjoll", "hierarchy-vor", "actuator-git"}
)

# REQ-8: the AgentContext field set, fixed and enumerable, and the four public
# interfaces plus the refusal/decision types their signatures name (section 6.1 and
# section 7 of the step-three spec).
EXPECTED_AGENT_CONTEXT_FIELDS: frozenset[str] = frozenset(
    {
        "agent_id",
        "identity",
        "standing_constraints",
        "task",
        "control_channel",
        "target_scope",
        "blast_radius_bound",
        "resource_ceiling",
    }
)
EXPECTED_TASK_CONTEXT_FIELDS: frozenset[str] = frozenset({"task_id", "target", "declared_cost"})
RAW_CONTENT_TRIGGER_WORDS: frozenset[str] = frozenset(
    {"content", "payload", "raw", "body", "text", "window"}
)
EXPECTED_INTERFACE_FUNCTIONS: frozenset[str] = frozenset(
    {
        "build_context",
        "enforce_definition",
        "validate_proposal",
        "broker_action",
        # Widened by `.opencode/plans/git-actuator-step-four.md` (REQ-31,
        # section 5.2, section 10 file 18): the witness-carrying entry
        # point is a genuine fifth public interface, re-exported at the
        # crate root alongside the original four. Its own zero-non-test-
        # caller claim (REQ-40, AC-47) is reported live by
        # `ontology.tests.himinbjorg_invocation_harness` and
        # `ontology.tests.actuator_invocation_harness`, not by this
        # module: this check only confirms the crate's public surface is
        # sufficient, exactly as it already does for the original four.
        "broker_authorised_action",
    }
)
EXPECTED_REFUSAL_DECISION_TYPES: frozenset[str] = frozenset(
    {"ContextRefusal", "DefinitionRefusal", "BrokerRefusal", "ProposalDecision"}
)


# ---------------------------------------------------------------------------------
# Check 1: dependency posture (REQ-27 step 1, REQ-30). A thin call-through to the
# WIDENED rust_gate_harness.check_dependency_posture, never a second implementation.
# ---------------------------------------------------------------------------------


def check_dependency_posture(manifest_path: Path = CRATE_MANIFEST):
    """REQ-27 step 1, REQ-30. Calls the widened
    `rust_gate_harness.check_dependency_posture` with the allowlist HB3-3 names, so
    the two in-workspace path dependencies are permitted and anything else -- an
    external dependency, an unlisted path dependency, or a listed name shaped as
    something other than a path dependency -- is fatal."""
    return rust_gate_harness.check_dependency_posture(
        manifest_path, PERMITTED_PATH_DEPENDENCIES
    )


# ---------------------------------------------------------------------------------
# Check 2: test and code isolation (REQ-27 step 2, REQ-5). Text-level, mechanical,
# following rust_cohort_harness.py's own test-isolation discipline (never a full
# Rust parse), but written fresh for this crate's own file set.
# ---------------------------------------------------------------------------------

_TEST_MARKER_RE = re.compile(r"#\[test\]|mod tests|#\[cfg\(test\)\]")


def _strip_line_comments(src: str) -> str:
    """Truncates every line at its first `//`, replacing the removed tail with
    spaces so line numbers and byte offsets are preserved exactly. A mechanical
    proxy only (no string-literal awareness, no block-comment handling), which is
    safe here because none of this crate's `src/` files hold a `//` sequence
    inside a string literal or a `/* */` block comment (confirmed directly).
    Mirrors `rust_cohort_harness._strip_line_comments`'s own reasoning; not
    imported from it because that function is private to that module and this
    repository's own convention (`gjoll_invocation_harness.py`'s duplicated
    `_call_target`) is to duplicate a short, test-only helper across sibling
    harnesses rather than add a cross-module dependency on another harness's
    private implementation detail."""
    out_lines = []
    for line in src.split("\n"):
        idx = line.find("//")
        if idx == -1:
            out_lines.append(line)
        else:
            out_lines.append(line[:idx] + " " * (len(line) - idx))
    return "\n".join(out_lines)


@dataclass
class IsolationCheckResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    detail: str = ""


def _load_rust_files(src_dir: Path) -> dict[str, str]:
    if not src_dir.exists():
        return {}
    return {
        str(p.relative_to(src_dir)): p.read_text(encoding="utf-8")
        for p in sorted(src_dir.rglob("*.rs"))
    }


def _check_test_markers(files: dict[str, str]) -> list[str]:
    """Every match of `#[test]|mod tests|#[cfg(test)]` anywhere under `src/`,
    comments stripped first, must be one of `lib.rs`'s own permitted
    `#[cfg(test)] #[path = "../unit_tests/..."] mod ...;` declaration lines. A
    match in any other file, or a match in `lib.rs` that is not part of that exact
    permitted block shape, is a violation (REQ-5, REQ-27 step 2)."""
    violations: list[str] = []
    for fname, raw_src in files.items():
        src = _strip_line_comments(raw_src)
        for m in _TEST_MARKER_RE.finditer(src):
            lineno = src.count("\n", 0, m.start()) + 1
            if fname != "lib.rs":
                violations.append(
                    f"{fname}:{lineno}: found `{m.group(0)}` outside lib.rs (REQ-5 "
                    f"permits test-related constructs under src/ only as lib.rs's "
                    f"own #[cfg(test)] #[path] declarations)"
                )
                continue
            if m.group(0) != "#[cfg(test)]":
                violations.append(
                    f"{fname}:{lineno}: found `{m.group(0)}` in lib.rs (only "
                    f"`#[cfg(test)]` declaration lines are permitted here, never a "
                    f"bare `#[test]` fn or `mod tests` block)"
                )
                continue
            rest = src[m.end():]
            if not re.match(
                r'\s*\n\s*#\[path\s*=\s*"\.\./unit_tests/[^"]+"\]\s*\n\s*mod\s+\w+\s*;',
                rest,
            ):
                violations.append(
                    f"{fname}:{lineno}: found `#[cfg(test)]` in lib.rs not "
                    f"immediately followed by a `#[path = \"../unit_tests/...\"] "
                    f"mod ...;` declaration (only that fixed block shape is "
                    f"permitted here)"
                )
    return violations


def _check_no_cross_directory_file_names(
    src_dir: Path, unit_tests_dir: Path, tests_dir: Path
) -> list[str]:
    """No file name may appear under both `src/` and either `unit_tests/` or
    `tests/` (REQ-5, REQ-27 step 2)."""
    violations: list[str] = []
    src_names = {p.name for p in src_dir.rglob("*.rs")} if src_dir.exists() else set()
    for other_dir, label in ((unit_tests_dir, "unit_tests/"), (tests_dir, "tests/")):
        if not other_dir.exists():
            continue
        other_names = {p.name for p in other_dir.rglob("*.rs")}
        overlap = sorted(src_names & other_names)
        if overlap:
            violations.append(
                f"file name(s) {overlap} appear under both src/ and {label} "
                f"(REQ-5 requires test code and implementation code to live in "
                f"separate files in separate directories)"
            )
    return violations


def check_test_isolation(
    src_dir: Path = SRC_DIR,
    unit_tests_dir: Path = UNIT_TESTS_DIR,
    tests_dir: Path = TESTS_DIR,
) -> IsolationCheckResult:
    """REQ-27 step 2, REQ-5. Fatal regardless of toolchain presence: a test
    construct leaking into `src/`, or a file name shared across a test and a
    non-test directory, is a fact about the committed source."""
    files = _load_rust_files(src_dir)
    if not files:
        return IsolationCheckResult(ok=False, detail=f"no .rs files found under {src_dir}")
    violations = _check_test_markers(files)
    violations += _check_no_cross_directory_file_names(src_dir, unit_tests_dir, tests_dir)
    if violations:
        return IsolationCheckResult(
            ok=False, violations=violations, detail=f"{len(violations)} violation(s)"
        )
    return IsolationCheckResult(
        ok=True,
        detail=(
            "the only test-related lines under src/ are lib.rs's own "
            "#[cfg(test)] #[path] declarations, and no file name is shared "
            "between src/ and unit_tests/ or tests/."
        ),
    )


# ---------------------------------------------------------------------------------
# Check 3: public-surface checks (REQ-27 step 3, REQ-8, REQ-21). Text-level,
# mechanical, written fresh for this crate (see the module docstring).
# ---------------------------------------------------------------------------------

_STRUCT_FIELD_RE = re.compile(r"pub(?:\(crate\))?\s+(\w+)\s*:")


def _struct_body(src: str, type_name: str) -> "str | None":
    """The body text between a `pub struct <type_name>...{` and its closing brace,
    found by naive brace-depth matching (no nested braces are expected in any
    field type this crate declares, confirmed directly against the real
    source). `type_name` is the bare name (no generic parameter list); an
    optional `<...>` after it is matched but not required, so a caller passes
    `"AgentContext"`, not `"AgentContext<'a>"`."""
    m = re.search(rf"pub struct {re.escape(type_name)}\b(?:<[^{{]*>)?\s*\{{", src)
    if not m:
        return None
    depth = 1
    i = m.end()
    start = i
    while i < len(src) and depth > 0:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
        i += 1
    return src[start : i - 1]


def _field_names(body: str) -> list[str]:
    return _STRUCT_FIELD_RE.findall(body)


def _raw_content_violations(type_name: str, field_names: list[str]) -> list[str]:
    violations: list[str] = []
    for name in field_names:
        tokens = name.split("_")
        if any(tok in RAW_CONTENT_TRIGGER_WORDS for tok in tokens):
            violations.append(
                f"{type_name}.{name}: field name contains a raw-content-shaped "
                f"token ({RAW_CONTENT_TRIGGER_WORDS & set(tokens)}) (REQ-8 forbids "
                f"a raw-content field of any kind, transitively)"
            )
    return violations


@dataclass
class SurfaceCheckResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    detail: str = ""


def check_agent_context_fields(types_src_path: Path = TYPES_RS) -> SurfaceCheckResult:
    """REQ-8, REQ-27 step 3 item 1: `AgentContext`'s field set matches the
    enumerated names exactly, and no field name (on `AgentContext` itself or on
    the `TaskContext` it embeds) contains a raw-content-shaped token."""
    if not types_src_path.exists():
        return SurfaceCheckResult(ok=False, detail=f"{types_src_path} does not exist")
    src = types_src_path.read_text(encoding="utf-8")
    violations: list[str] = []

    agent_context_body = _struct_body(src, "AgentContext")
    if agent_context_body is None:
        return SurfaceCheckResult(ok=False, detail="could not find `pub struct AgentContext` in types.rs")
    agent_context_fields = set(_field_names(agent_context_body))
    if agent_context_fields != EXPECTED_AGENT_CONTEXT_FIELDS:
        violations.append(
            f"AgentContext's field set is {sorted(agent_context_fields)}, expected "
            f"exactly {sorted(EXPECTED_AGENT_CONTEXT_FIELDS)} (REQ-8: the field set "
            f"must be fixed and enumerable, and this is the check that enumerates it)"
        )
    violations += _raw_content_violations("AgentContext", sorted(agent_context_fields))

    task_context_body = _struct_body(src, "TaskContext")
    if task_context_body is not None:
        task_context_fields = set(_field_names(task_context_body))
        violations += _raw_content_violations("TaskContext", sorted(task_context_fields))
        if task_context_fields != EXPECTED_TASK_CONTEXT_FIELDS:
            violations.append(
                f"TaskContext's field set is {sorted(task_context_fields)}, expected "
                f"exactly {sorted(EXPECTED_TASK_CONTEXT_FIELDS)} (REQ-8: no free-form "
                f"external text field, checked at the nested level too)"
            )

    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(
        ok=True,
        detail=(
            f"AgentContext's field set is exactly {sorted(EXPECTED_AGENT_CONTEXT_FIELDS)}, "
            f"TaskContext's is exactly {sorted(EXPECTED_TASK_CONTEXT_FIELDS)}, and no field "
            f"name on either contains a raw-content-shaped token."
        ),
    )


_PUB_USE_GROUP_RE = re.compile(r"pub use (\w+)::\{([^}]*)\};")
_PUB_USE_SINGLE_RE = re.compile(r"pub use (\w+)::(\w+);")


def _reexported_names(lib_src: str) -> set[str]:
    names: set[str] = set()
    for _module, body in _PUB_USE_GROUP_RE.findall(lib_src):
        names.update(n.strip() for n in body.split(",") if n.strip())
    for _module, name in _PUB_USE_SINGLE_RE.findall(lib_src):
        names.add(name)
    return names


def check_public_reexports(lib_rs_path: Path = LIB_RS) -> SurfaceCheckResult:
    """REQ-27 step 3 item 2: the crate re-exports exactly its public
    interfaces (`build_context`, `enforce_definition`, `validate_proposal`,
    `broker_action`, and, widened by `.opencode/plans/git-actuator-step-four.md`
    REQ-31/section 5.2, `broker_authorised_action`), no more and no fewer,
    plus their refusal and decision types (`ContextRefusal`,
    `DefinitionRefusal`, `BrokerRefusal`, `ProposalDecision`)."""
    if not lib_rs_path.exists():
        return SurfaceCheckResult(ok=False, detail=f"{lib_rs_path} does not exist")
    src = lib_rs_path.read_text(encoding="utf-8")
    reexported = _reexported_names(src)
    violations: list[str] = []

    functions_present = reexported & EXPECTED_INTERFACE_FUNCTIONS
    if functions_present != EXPECTED_INTERFACE_FUNCTIONS:
        missing = EXPECTED_INTERFACE_FUNCTIONS - functions_present
        violations.append(
            f"missing re-exported interface function(s): {sorted(missing)} (REQ-27 "
            f"expects the crate to re-export exactly its public interfaces, "
            f"{sorted(EXPECTED_INTERFACE_FUNCTIONS)})"
        )
    unexpected_function_like = {
        n for n in reexported
        if n.endswith("_action") or n.startswith("build_") or n.startswith("enforce_")
        or n.startswith("validate_")
    } - EXPECTED_INTERFACE_FUNCTIONS
    if unexpected_function_like:
        violations.append(
            f"unexpected additional function-shaped re-export(s): "
            f"{sorted(unexpected_function_like)} (REQ-27 expects exactly the named "
            f"interfaces, {sorted(EXPECTED_INTERFACE_FUNCTIONS)}, no more)"
        )

    missing_types = EXPECTED_REFUSAL_DECISION_TYPES - reexported
    if missing_types:
        violations.append(
            f"missing re-exported refusal/decision type(s): {sorted(missing_types)} "
            f"(REQ-27 expects the four interfaces' refusal and decision types to be "
            f"re-exported alongside them)"
        )

    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(
        ok=True,
        detail=(
            f"exactly the four interfaces {sorted(EXPECTED_INTERFACE_FUNCTIONS)} are "
            f"re-exported, alongside their refusal/decision types "
            f"{sorted(EXPECTED_REFUSAL_DECISION_TYPES)}."
        ),
    )


_DECISION_CONSTRUCTION_RE = re.compile(r"Decision::(Queue|Escalate)\b")


def check_no_queue_or_escalate_construction(src_dir: Path = SRC_DIR) -> SurfaceCheckResult:
    """REQ-21, REQ-27 step 3 item 3: `Decision::Queue` and `Decision::Escalate`
    must appear in no construction position anywhere under `src/` (their own
    bare, unqualified declaration in the `Decision` enum and any doc comment
    mentioning them by their qualified name are both permitted; comments are
    stripped first so a doc comment's own mention is never mistaken for a
    construction)."""
    files = _load_rust_files(src_dir)
    if not files:
        return SurfaceCheckResult(ok=False, detail=f"no .rs files found under {src_dir}")
    violations: list[str] = []
    for fname, raw_src in files.items():
        src = _strip_line_comments(raw_src)
        for m in _DECISION_CONSTRUCTION_RE.finditer(src):
            lineno = src.count("\n", 0, m.start()) + 1
            violations.append(
                f"{fname}:{lineno}: found `Decision::{m.group(1)}` outside a comment "
                f"under src/ (REQ-21 permits Queue and Escalate to be declared, "
                f"never constructed, in step three)"
            )
    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(
        ok=True,
        detail="Decision::Queue and Decision::Escalate appear in no construction position under src/.",
    )


_STD_PROCESS_RE = re.compile(r"std::process\b")


def check_no_std_process(src_dir: Path = SRC_DIR) -> SurfaceCheckResult:
    """AC-4, added by `.opencode/plans/git-actuator-step-four.md` REQ-7: no
    `.rs` file under `crates/himinbjorg/src/` references `std::process`.
    `crates/actuator-git/` is now the only crate in the workspace permitted to
    touch it (REQ-7); this check is `himinbjorg`'s own half of that claim.
    Comments are stripped first, mirroring
    `check_no_queue_or_escalate_construction`'s own discipline, so a doc
    comment mentioning `std::process` in prose is never mistaken for a real
    reference."""
    files = _load_rust_files(src_dir)
    if not files:
        return SurfaceCheckResult(ok=False, detail=f"no .rs files found under {src_dir}")
    violations: list[str] = []
    for fname, raw_src in files.items():
        src = _strip_line_comments(raw_src)
        for m in _STD_PROCESS_RE.finditer(src):
            lineno = src.count("\n", 0, m.start()) + 1
            violations.append(
                f"{fname}:{lineno}: found `std::process` outside a comment under src/ "
                f"(REQ-7: actuator-git is now the only crate in the workspace permitted "
                f"to touch std::process)"
            )
    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(
        ok=True,
        detail="std::process appears nowhere under crates/himinbjorg/src/ (AC-4, REQ-7).",
    )


def check_public_surface() -> SurfaceCheckResult:
    """Runs all four public-surface checks (REQ-27 step 3, widened by AC-4)
    and aggregates."""
    violations: list[str] = []
    details: list[str] = []
    for result in (
        check_agent_context_fields(),
        check_public_reexports(),
        check_no_queue_or_escalate_construction(),
        check_no_std_process(),
    ):
        if not result.ok:
            violations += result.violations or [result.detail]
        else:
            details.append(result.detail)
    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(ok=True, detail=" ".join(details))


# ---------------------------------------------------------------------------------
# Check 4: the Rust suite (REQ-27 step 4). REUSED, never reimplemented (REQ-30):
# toolchain_present and run_rust_suite are imported from rust_gate_harness.
# ---------------------------------------------------------------------------------


def toolchain_present() -> bool:
    """REQ-30: reused directly from `rust_gate_harness`, exposed here under the
    same name so a caller of this module does not need to know it is a
    call-through."""
    return rust_gate_harness.toolchain_present()


def run_rust_suite(crate_dir: Path = CRATE_DIR) -> tuple[bool, str]:
    """REQ-30: reused directly from `rust_gate_harness.run_rust_suite`, scoped to
    this crate's own manifest path via `crate_dir`."""
    return rust_gate_harness.run_rust_suite(crate_dir)


# ---------------------------------------------------------------------------------
# Negative controls (invariant 3.10, D10): before trusting a clean scan, confirm
# each check actually bites a planted violation.
# ---------------------------------------------------------------------------------


def control_check() -> list[str]:
    """Prove each fatal check can actually fail before it is trusted, following
    `rust_cohort_harness.control_check`'s naming and shape. Returns a list of
    failure descriptions (empty if every control bites)."""
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as d:
        # Dependency control: a manifest carrying a dependency outside the
        # allowlist must be reported as a violation naming it.
        bad_manifest = Path(d) / "Cargo.toml"
        bad_manifest.write_text(
            '[package]\nname = "himinbjorg"\n\n[dependencies]\n'
            'boundary-gjoll = { path = "../boundary-gjoll" }\n'
            'hierarchy-vor = { path = "../hierarchy-vor" }\n'
            'serde = "1"\n'
        )
        dep_result = check_dependency_posture(bad_manifest)
        if dep_result.ok or "serde" not in dep_result.violations:
            failures.append(
                "dependency control did NOT report a violation for a manifest with "
                "a dependency outside the permitted in-workspace path allowlist"
            )

        # Control the control: a manifest carrying ONLY the two permitted path
        # dependencies must report clean.
        clean_manifest = Path(d) / "Cargo-clean.toml"
        clean_manifest.write_text(
            '[package]\nname = "himinbjorg"\n\n[dependencies]\n'
            'boundary-gjoll = { path = "../boundary-gjoll" }\n'
            'hierarchy-vor = { path = "../hierarchy-vor" }\n'
        )
        clean_result = check_dependency_posture(clean_manifest)
        if not clean_result.ok:
            failures.append(
                "dependency control WRONGLY flagged a manifest carrying only the "
                "two permitted in-workspace path dependencies"
            )

        # Test-isolation control: a stray #[test] fn in a src/ file must be caught.
        fixture_dir = Path(d) / "src"
        fixture_dir.mkdir()
        (fixture_dir / "lib.rs").write_text(
            '#[cfg(test)]\n#[path = "../unit_tests/six_checks.rs"]\nmod six_checks;\n'
        )
        (fixture_dir / "sneaky.rs").write_text(
            "fn helper() {}\n\n#[test]\nfn a_stray_unit_test_in_src() {\n    assert!(true);\n}\n"
        )
        isolation_result = check_test_isolation(
            fixture_dir, Path(d) / "unit_tests_absent", Path(d) / "tests_absent"
        )
        if isolation_result.ok:
            failures.append(
                "test-isolation control did NOT catch a stray #[test] fn landing "
                "directly in a src/ file"
            )

        # Control the control: the real crate's own permitted lib.rs declaration
        # block must not be flagged on its own.
        clean_fixture_dir = Path(d) / "src_clean"
        clean_fixture_dir.mkdir()
        (clean_fixture_dir / "lib.rs").write_text(
            '#[cfg(test)]\n#[path = "../unit_tests/six_checks.rs"]\nmod six_checks;\n'
        )
        clean_isolation_result = check_test_isolation(
            clean_fixture_dir, Path(d) / "unit_tests_absent2", Path(d) / "tests_absent2"
        )
        if not clean_isolation_result.ok:
            failures.append(
                "test-isolation control WRONGLY flagged lib.rs's own permitted "
                "#[cfg(test)] #[path = ...] mod ...; declaration"
            )

        # Public-surface field control: a fixture AgentContext carrying a
        # raw-content-shaped field must be caught.
        bad_types = Path(d) / "types_bad.rs"
        bad_types.write_text(
            "pub struct AgentContext<'a> {\n"
            "    pub(crate) agent_id: AgentId,\n"
            "    pub(crate) payload: &'a str,\n"
            "}\n"
        )
        field_result = check_agent_context_fields(bad_types)
        if field_result.ok:
            failures.append(
                "public-surface field control did NOT catch an AgentContext "
                "carrying a raw-content-shaped field (payload)"
            )

        # Public-surface re-export control: a lib.rs missing one interface must
        # be caught.
        bad_lib = Path(d) / "lib_bad.rs"
        bad_lib.write_text(
            "pub use types::{ContextRefusal, DefinitionRefusal, BrokerRefusal, ProposalDecision};\n"
            "pub use broker::broker_action;\n"
            "pub use context::build_context;\n"
            "pub use definition::enforce_definition;\n"
        )
        reexport_result = check_public_reexports(bad_lib)
        if reexport_result.ok:
            failures.append(
                "public-surface re-export control did NOT catch a lib.rs missing "
                "one of the four interface re-exports (validate_proposal)"
            )

        # Queue/Escalate construction control: a planted construction outside a
        # comment must be caught.
        bad_construction_dir = Path(d) / "src_construct"
        bad_construction_dir.mkdir()
        (bad_construction_dir / "leaky.rs").write_text(
            "fn f() -> Decision {\n    Decision::Queue\n}\n"
        )
        construction_result = check_no_queue_or_escalate_construction(bad_construction_dir)
        if construction_result.ok:
            failures.append(
                "Queue/Escalate construction control did NOT catch a planted "
                "`Decision::Queue` construction outside a comment"
            )

        # Control the control: a doc-comment-only mention must not be flagged.
        clean_construction_dir = Path(d) / "src_construct_clean"
        clean_construction_dir.mkdir()
        (clean_construction_dir / "leaky.rs").write_text(
            "/// never constructs Decision::Queue or Decision::Escalate\nfn f() {}\n"
        )
        clean_construction_result = check_no_queue_or_escalate_construction(clean_construction_dir)
        if not clean_construction_result.ok:
            failures.append(
                "Queue/Escalate construction control WRONGLY flagged a doc-comment-"
                "only mention of Decision::Queue"
            )

        # AC-4 control: a planted std::process reference must be caught.
        bad_process_dir = Path(d) / "src_process"
        bad_process_dir.mkdir()
        (bad_process_dir / "leaky.rs").write_text(
            "fn f() {\n    let _ = std::process::Command::new(\"git\");\n}\n"
        )
        process_result = check_no_std_process(bad_process_dir)
        if process_result.ok:
            failures.append("AC-4 control did NOT catch a planted std::process reference")

        # Control the control: a doc-comment-only mention must not be flagged.
        clean_process_dir = Path(d) / "src_process_clean"
        clean_process_dir.mkdir()
        (clean_process_dir / "leaky.rs").write_text(
            "// this module never touches std::process (REQ-7)\nfn f() {}\n"
        )
        clean_process_result = check_no_std_process(clean_process_dir)
        if not clean_process_result.ok:
            failures.append(
                "AC-4 control WRONGLY flagged a doc-comment-only mention of std::process"
            )

    return failures


def main() -> int:
    print("Himinbjörg gateway posture detector (D111, REQ-27): dependency posture, test")
    print("and code isolation, public-surface sufficiency and the Rust suite for")
    print("crates/himinbjorg/. Not invariant 3.6's live-invocation status (see")
    print("ontology.tests.himinbjorg_invocation_harness for that, separately governed).")
    print()

    control_failures = control_check()
    if control_failures:
        print("NEGATIVE CONTROL FAILED (refusing to trust the checks below):")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    print("  [PASS] negative controls: a disallowed dependency, a stray test construct "
          "in src/, a raw-content-shaped AgentContext field, a missing interface "
          "re-export, a planted Decision::Queue construction and a planted std::process "
          "reference (AC-4) are all caught, and none of their clean counterparts is "
          "wrongly flagged.")
    print()

    dep_result = check_dependency_posture()
    print(f"  [{'PASS' if dep_result.ok else 'CRITICAL'}] dependency posture "
          f"(permitted in-workspace path dependencies: "
          f"{sorted(PERMITTED_PATH_DEPENDENCIES)}): {dep_result.detail}")
    if not dep_result.ok:
        return 1  # fatal regardless of toolchain presence (REQ-27)

    isolation_result = check_test_isolation()
    print(f"  [{'PASS' if isolation_result.ok else 'CRITICAL'}] test and code isolation: "
          f"{isolation_result.detail}")
    if not isolation_result.ok:
        for v in isolation_result.violations:
            print(f"    - {v}")
        return 1  # fatal regardless of toolchain presence (REQ-27)

    surface_result = check_public_surface()
    if surface_result.ok:
        print(f"  [PASS] public-surface checks: {surface_result.detail}")
    else:
        print(f"  [CRITICAL] public-surface checks: {surface_result.detail}")
        for v in surface_result.violations:
            print(f"    - {v}")
        return 1  # fatal regardless of toolchain presence (REQ-27)

    print()
    if not toolchain_present():
        print("  [SKIP] no Rust toolchain found on this machine (cargo not on PATH).")
        print("  The dependency, isolation and surface checks above already ran and")
        print("  passed; only the Rust suite is skipped (EC-16). This is not a failure.")
        return 0

    ok, detail = run_rust_suite()
    print(f"  [{'PASS' if ok else 'CRITICAL'}] Rust suite: {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
