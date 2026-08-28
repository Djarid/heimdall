"""Process-engine posture detector (`.opencode/plans/process-engine-step-five-spec.md`
section 4.12, REQ-51; section 5.12, AC-55, AC-56): is `crates/process-engine/`
dependency-clean (against the ACTUAL, disclosed dependency table, not the
spec's original assumption), test-and-code isolated (including `main.rs`),
mechanically sound at both crate roots, closed at exactly five sequence
steps, and passing, on `ontology/tests/rust_actuator_harness.py`'s exact
shape (REQ-51).

Run from the repo root:

    python -m ontology.tests.rust_process_engine_harness

What this proves, and what it does not. A green result here means the crate
at `crates/process-engine/` carries a `[dependencies]` table matching the
ACTUAL, disclosed allowlist (see "Two disclosed discrepancies" below, not
REQ-51's own text), keeps every test construct out of `src/` including
`main.rs` (REQ-51), carries `#![forbid(unsafe_code)]` at file scope in BOTH
crate roots with no `unsafe` keyword anywhere in `src/` (REQ-51), declares
exactly one `[[bin]]` target (REQ-51), references neither `std::process` nor
`std::net` anywhere in `src/` EXCEPT the one disclosed, file-scoped exception
documented below (REQ-51), closes `EngineStep` at exactly five variants with
`STEP_SEQUENCE`'s own compile-time length assertion present (REQ-51), keeps
`actuator-git` absent from the dependency table (REQ-51), and passes its own
Rust suite (or loudly skips that one step alone, if no toolchain is present,
following `rust_gate_harness.py`'s skip-if-absent precedent). It says
NOTHING about invariant 3.6's live-invocation status or about whether the
engine's own callers (`himinbjorg::broker_authorised_action`,
`hierarchy_vor::load_verified_cohort`) are exercised outside a test; that is
a different harness's job, not this module's.

Two disclosed discrepancies between REQ-51's own text and this crate's
actual, committed, approved state, resolved here rather than either silently
enforcing the spec's stale assumption or silently dropping the check
(both read directly off `crates/process-engine/Cargo.toml` and
`crates/process-engine/src/main.rs` before this module was written):

  A. REQ-51 says "a two-name allowlist" (`himinbjorg`, `hierarchy-vor`) and
     "the absence of `boundary-gjoll` and `actuator-git` from the dependency
     table". `crates/process-engine/Cargo.toml` carries a THIRD dependency,
     `boundary-gjoll`, with its own multi-paragraph disclosure comment
     recorded directly above the `[dependencies]` table: `himinbjorg`'s
     `ProposalParameter` fields (`consume_mode`, `trust_level`) name
     `boundary_gjoll::types::*` directly, and Rust's extern-prelude
     resolution does not make a transitive dependency's items nameable
     without a direct dependency declaration on the crate that names them
     -- confirmed empirically (per that comment) with a minimal three-crate
     reproduction, not assumed. `src/lib.rs`'s own doc comment repeats the
     same disclosure. This module therefore checks dependency posture with a
     THREE-name allowlist (`himinbjorg`, `hierarchy-vor`, `boundary-gjoll`),
     reflecting the REAL, approved dependency table, and reports this
     discrepancy by name in `check_dependency_posture`'s own detail string
     rather than silently passing a two-name allowlist that would fail
     against the real manifest, or silently widening it without saying so.
     `actuator-git` stays absent and stays fatal if it ever appears: nothing
     in the disclosure touches that half of REQ-51. `check_boundary_gjoll_and_
     actuator_git_absence` below (REQ-51's fifth-from-last named check)
     is narrowed accordingly: `actuator-git`'s absence is still fatal;
     `boundary-gjoll`'s presence is reported as the disclosed, expected
     state, never as a violation.
  B. REQ-51 says the harness checks "the absence of `std::process` and
     `std::net` anywhere in the crate". `crates/process-engine/src/main.rs`
     carries `std::process::exit`, twice, with its own doc comment
     disclosing exactly this: Rust has no route to set a real process exit
     code other than through `std::process` somewhere, and this is
     categorically different from `std::process::Command` (subprocess
     spawning, D112's own concern, which stays inside
     `crates/actuator-git/src/execute.rs` alone). This module resolves the
     tension by scoping the exception narrowly and mechanically: the ONLY
     permitted `std::process` occurrence anywhere in `src/` is the exact
     substring `std::process::exit` inside `main.rs`; `std::process::Command`
     (or any other `std::process::*` path), `std::process` in any file other
     than `main.rs`, and `std::net` anywhere at all (no disclosed exception
     exists for that module) all remain fatal. This is a reasoned narrowing
     of REQ-51's own wording to match a disclosed, spec-acknowledged
     necessity, not a silent pass and not a silent failure; it is recorded
     here, in this docstring, rather than only in a chat transcript.

Checks, run in this fixed order (REQ-51), each fatal regardless of whether a
Rust toolchain is even present, because dependency posture, test isolation
and the mechanical surface properties are all facts about the committed
source, not about the toolchain:

  1. Dependency posture (discrepancy A above). Reuses (never reimplements)
     `ontology.tests.rust_gate_harness.check_dependency_posture` with the
     three-name allowlist, REQ-51's own instruction ("reusing
     rust_gate_harness.check_dependency_posture by import, never by copy")
     honoured; `check_dependency_posture`'s own empty default is untouched,
     so `boundary-gjoll`'s and `hierarchy-vor`'s own manifests keep their
     strict, no-allowlist behaviour byte for byte (AC-55).
  2. Test and code isolation, including `main.rs`. The only test-related
     lines anywhere under `crates/process-engine/src/` are `lib.rs`'s own
     `#[cfg(test)] #[path = "../unit_tests/..."] mod ...;` module
     declarations AND `lib.rs`'s own `#[cfg(test)] pub(crate) use ...;`
     alias declarations (both are this crate's own committed, documented
     convention; see `src/lib.rs`'s own doc comment for why the alias form
     exists alongside the module-declaration form `rust_actuator_harness.py`
     alone anticipates). No file name appears under both `src/` and a test
     directory. `main.rs` carries zero test-related lines at all (it is not
     exempted the way `lib.rs` is).
  3. Mechanical surface properties: `#![forbid(unsafe_code)]` present at
     file scope in BOTH `src/lib.rs` AND `src/main.rs` (a binary target's
     attributes are not inherited from the library), the literal `unsafe`
     keyword appearing nowhere in the crate's `src/`; exactly one `[[bin]]`
     target in `Cargo.toml`; `std::net` absent everywhere in `src/` and
     `std::process` absent everywhere in `src/` except the one disclosed
     `std::process::exit` occurrence in `main.rs` (discrepancy B above);
     `EngineStep` declaring exactly five variants; `STEP_SEQUENCE`'s own
     compile-time length assertion present and asserting `== 5`.
  4. Boundary-gjoll/actuator-git absence (discrepancy A above, narrowed):
     `actuator-git` is fatal if present anywhere in `[dependencies]`;
     `boundary-gjoll`'s presence is reported, not flagged, as the disclosed
     expected state.
  5. The Rust suite, invoked via the REUSED `toolchain_present` and
     `run_rust_suite` helpers, scoped to this crate's own manifest. Skip
     discipline follows `rust_gate_harness.py`'s own precedent: skip
     detection keys on the toolchain-presence probe alone, never on whether
     the test run itself would have succeeded.

REQ-51's own instruction, honoured: this module imports
`check_dependency_posture`, `toolchain_present` and `run_rust_suite` from
`rust_gate_harness`; it adds no second copy of any of the three. The
test-isolation and mechanical-surface checks below have no existing reusable
counterpart (each existing sub-harness's own version is hardcoded to a
different crate's field, module and type names), so they are written fresh
here, on the same mechanical-proxy, not-a-full-parser discipline
`rust_gateway_harness.py`'s own checks already establish and document.
"""

from __future__ import annotations

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
UNIT_TESTS_DIR = CRATE_DIR / "unit_tests"
TESTS_DIR = CRATE_DIR / "tests"
LIB_RS = SRC_DIR / "lib.rs"
MAIN_RS = SRC_DIR / "main.rs"
SEQUENCE_RS = SRC_DIR / "sequence.rs"

# Discrepancy A (see module docstring): REQ-51's own text says two names;
# the real, disclosed and approved manifest carries three. This allowlist
# reflects the REAL current dependency table, not REQ-51's original
# assumption.
PERMITTED_DEPENDENCIES: frozenset[str] = frozenset(
    {"himinbjorg", "hierarchy-vor", "boundary-gjoll"}
)

FORBIDDEN_DEPENDENCIES: frozenset[str] = frozenset({"actuator-git"})

# Discrepancy B (see module docstring): the one disclosed, file-scoped
# exception to the std::process/std::net absence check.
_PERMITTED_STD_PROCESS_OCCURRENCE = "std::process::exit"
_PERMITTED_STD_PROCESS_FILE = "main.rs"


def _load_rust_files(src_dir: Path) -> dict[str, str]:
    if not src_dir.exists():
        return {}
    return {
        str(p.relative_to(src_dir)): p.read_text(encoding="utf-8")
        for p in sorted(src_dir.rglob("*.rs"))
    }


def _strip_line_comments(src: str) -> str:
    """Mirrors `rust_gateway_harness._strip_line_comments`'s own reasoning;
    duplicated, not imported, following this repository's own convention of
    duplicating a short, test-only helper across sibling harnesses."""
    out_lines = []
    for line in src.split("\n"):
        idx = line.find("//")
        if idx == -1:
            out_lines.append(line)
        else:
            out_lines.append(line[:idx] + " " * (len(line) - idx))
    return "\n".join(out_lines)


# ---------------------------------------------------------------------------------
# Check 1: dependency posture (discrepancy A). The [dependencies] half
# reuses rust_gate_harness.check_dependency_posture directly, with the
# three-name allowlist, and this function's own detail string states the
# discrepancy against REQ-51's original two-name text rather than hiding it.
# ---------------------------------------------------------------------------------


@dataclass
class DependencyPostureReport:
    ok: bool
    detail: str = ""
    violations: list[str] = field(default_factory=list)


def check_dependency_posture(manifest_path: Path = CRATE_MANIFEST) -> DependencyPostureReport:
    """Reuses `rust_gate_harness.check_dependency_posture` (never
    reimplemented), passing the THREE-name allowlist that reflects this
    crate's real, disclosed manifest (discrepancy A). `boundary-gjoll` and
    `hierarchy-vor`'s own manifests are untouched: `check_dependency_posture`
    is called here with an explicit allowlist argument, and its own empty
    default (used by every OTHER existing caller) is never edited."""
    result = rust_gate_harness.check_dependency_posture(manifest_path, PERMITTED_DEPENDENCIES)
    if not result.manifest_found:
        return DependencyPostureReport(ok=True, detail=result.detail)
    if not result.ok:
        return DependencyPostureReport(ok=False, violations=result.violations, detail=result.detail)
    return DependencyPostureReport(
        ok=True,
        detail=(
            f"{result.detail} NOTE (discrepancy A, disclosed): REQ-51's own text names a "
            f"two-name allowlist (himinbjorg, hierarchy-vor); this check uses the REAL, "
            f"disclosed three-name allowlist {sorted(PERMITTED_DEPENDENCIES)} because "
            f"Cargo.toml's own comment and src/lib.rs's own doc comment both disclose an "
            f"approved, empirically-confirmed third path dependency on boundary-gjoll for "
            f"ProposalParameter value construction only."
        ),
    )


# ---------------------------------------------------------------------------------
# Check 2: test and code isolation (REQ-51), including main.rs, on
# rust_actuator_harness.py's own discipline, widened to recognise this
# crate's OWN second permitted lib.rs shape (the `pub(crate) use` alias
# declarations), which no existing sibling harness anticipates.
# ---------------------------------------------------------------------------------

_TEST_MARKER_RE = re.compile(r"#\[test\]|mod tests|#\[cfg\(test\)\]")

_LIB_RS_PATH_MOD_RE = re.compile(
    r'\s*\n\s*#\[path\s*=\s*"\.\./unit_tests/[^"]+"\]\s*\n\s*mod\s+\w+\s*;'
)
_LIB_RS_ALIAS_USE_RE = re.compile(r"\s*\n\s*pub\(crate\)\s+use\s+[\w:]+\s*;")


@dataclass
class IsolationCheckResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    detail: str = ""


def _check_test_markers(files: dict[str, str]) -> list[str]:
    violations: list[str] = []
    for fname, raw_src in files.items():
        src = _strip_line_comments(raw_src)
        for m in _TEST_MARKER_RE.finditer(src):
            lineno = src.count("\n", 0, m.start()) + 1
            if fname != "lib.rs":
                violations.append(
                    f"{fname}:{lineno}: found `{m.group(0)}` outside lib.rs (REQ-51 "
                    f"permits test-related constructs under src/ only as lib.rs's own "
                    f"declarations, and main.rs is explicitly in scope for this check)"
                )
                continue
            if m.group(0) != "#[cfg(test)]":
                violations.append(
                    f"{fname}:{lineno}: found `{m.group(0)}` in lib.rs (only "
                    f"`#[cfg(test)]` declaration lines are permitted here)"
                )
                continue
            rest = src[m.end():]
            if _LIB_RS_PATH_MOD_RE.match(rest) or _LIB_RS_ALIAS_USE_RE.match(rest):
                continue
            violations.append(
                f"{fname}:{lineno}: found `#[cfg(test)]` in lib.rs not immediately "
                f"followed by either a `#[path = \"../unit_tests/...\"] mod ...;` "
                f"declaration or a `pub(crate) use ...;` alias declaration (this "
                f"crate's own two permitted lib.rs shapes)"
            )
    return violations


def _check_no_cross_directory_file_names(
    src_dir: Path, unit_tests_dir: Path, tests_dir: Path
) -> list[str]:
    violations: list[str] = []
    src_names = {p.name for p in src_dir.rglob("*.rs")} if src_dir.exists() else set()
    for other_dir, label in ((unit_tests_dir, "unit_tests/"), (tests_dir, "tests/")):
        if not other_dir.exists():
            continue
        other_names = {p.name for p in other_dir.rglob("*.rs")}
        overlap = sorted(src_names & other_names)
        if overlap:
            violations.append(
                f"file name(s) {overlap} appear under both src/ and {label} (REQ-51)"
            )
    return violations


def check_test_isolation(
    src_dir: Path = SRC_DIR,
    unit_tests_dir: Path = UNIT_TESTS_DIR,
    tests_dir: Path = TESTS_DIR,
) -> IsolationCheckResult:
    files = _load_rust_files(src_dir)
    if not files:
        return IsolationCheckResult(
            ok=True,
            detail=f"{src_dir} does not exist yet; nothing to check.",
        )
    violations = _check_test_markers(files)
    violations += _check_no_cross_directory_file_names(src_dir, unit_tests_dir, tests_dir)
    if violations:
        return IsolationCheckResult(
            ok=False, violations=violations, detail=f"{len(violations)} violation(s)"
        )
    return IsolationCheckResult(
        ok=True,
        detail="the only test-related lines under src/ are lib.rs's own #[cfg(test)] "
               "#[path] module declarations and pub(crate) use alias declarations; "
               "main.rs and every other file under src/ carry zero test-related lines; "
               "no file name is shared between src/ and unit_tests/ or tests/.",
    )


# ---------------------------------------------------------------------------------
# Check 3: mechanical surface properties (REQ-51): forbid(unsafe_code) in
# BOTH crate roots, no unsafe keyword, exactly one [[bin]] target,
# std::process/std::net absence (discrepancy B narrowing), EngineStep's
# five variants, STEP_SEQUENCE's length assertion.
# ---------------------------------------------------------------------------------


@dataclass
class SurfaceCheckResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    detail: str = ""


def check_forbid_unsafe_in_both_roots_and_no_unsafe_keyword(
    lib_rs_path: Path = LIB_RS, main_rs_path: Path = MAIN_RS, src_dir: Path = SRC_DIR
) -> SurfaceCheckResult:
    """`#![forbid(unsafe_code)]` at file scope in BOTH src/lib.rs and
    src/main.rs (a binary target's attributes are not inherited from the
    library it links against), and no `unsafe` keyword anywhere in the
    crate's src/ (proving the attribute is not merely present but
    unviolated)."""
    violations: list[str] = []
    for label, path in (("src/lib.rs", lib_rs_path), ("src/main.rs", main_rs_path)):
        if not path.exists():
            violations.append(f"{label} does not exist")
            continue
        stripped = path.read_text(encoding="utf-8").lstrip()
        if not stripped.startswith("#![forbid(unsafe_code)]"):
            violations.append(
                f"{label} does not begin with `#![forbid(unsafe_code)]` at file scope: "
                f"either it is absent, it is `deny`/`warn` instead of `forbid`, or it is "
                f"not the first item in the file"
            )
    files = _load_rust_files(src_dir)
    unsafe_re = re.compile(r"\bunsafe\b")
    for fname, raw_src in files.items():
        cleaned = _strip_line_comments(raw_src)
        for m in unsafe_re.finditer(cleaned):
            lineno = cleaned.count("\n", 0, m.start()) + 1
            violations.append(
                f"{fname}:{lineno}: the `unsafe` keyword appears in this crate's src/, "
                f"which would violate #![forbid(unsafe_code)] at compile time"
            )
    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(
        ok=True,
        detail="src/lib.rs and src/main.rs both begin with #![forbid(unsafe_code)], and "
               "the `unsafe` keyword appears nowhere in this crate's src/.",
    )


def check_exactly_one_binary_target(manifest_path: Path = CRATE_MANIFEST) -> SurfaceCheckResult:
    """Exactly one `[[bin]]` target in Cargo.toml."""
    if not manifest_path.exists():
        return SurfaceCheckResult(ok=False, detail=f"{manifest_path} does not exist")
    data = tomllib.loads(manifest_path.read_text())
    bins = data.get("bin", []) or []
    if len(bins) != 1:
        return SurfaceCheckResult(
            ok=False,
            violations=[f"Cargo.toml declares {len(bins)} [[bin]] target(s), expected exactly 1"],
            detail=f"{len(bins)} != 1",
        )
    return SurfaceCheckResult(ok=True, detail="Cargo.toml declares exactly one [[bin]] target.")


def check_std_process_and_std_net_absence(src_dir: Path = SRC_DIR) -> SurfaceCheckResult:
    """`std::net` absent everywhere in src/; `std::process` absent
    everywhere in src/ EXCEPT the one disclosed `std::process::exit`
    occurrence in main.rs (discrepancy B, see module docstring). Any other
    `std::process::*` path (e.g. `std::process::Command`), `std::process`
    in any file other than main.rs, or `std::net` anywhere at all, is
    fatal."""
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
            if (
                fname == _PERMITTED_STD_PROCESS_FILE
                and occurrence == _PERMITTED_STD_PROCESS_OCCURRENCE
            ):
                continue
            violations.append(
                f"{fname}:{lineno}: found `{occurrence}`, which is not the one disclosed "
                f"exception (`{_PERMITTED_STD_PROCESS_OCCURRENCE}` in "
                f"`{_PERMITTED_STD_PROCESS_FILE}` alone, discrepancy B)"
            )
    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(
        ok=True,
        detail="std::net is absent everywhere in src/, and the only std::process "
               f"occurrence anywhere in src/ is `{_PERMITTED_STD_PROCESS_OCCURRENCE}` in "
               f"{_PERMITTED_STD_PROCESS_FILE} (the one disclosed exception, discrepancy B).",
    )


_ENUM_BODY_RE_TEMPLATE = r"pub enum {name}\s*\{{"


def _enum_variant_count(src: str, enum_name: str) -> "int | None":
    m = re.search(_ENUM_BODY_RE_TEMPLATE.format(name=re.escape(enum_name)), src)
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
    body = src[start : i - 1]
    # Top-level commas separate variants; a variant carrying a struct-shaped
    # payload nests its own braces, so only commas at brace-depth zero are
    # counted. This is a mechanical proxy, not a full parser (matching this
    # repository's own established discipline).
    variant_count = 0
    d = 0
    saw_any_non_whitespace_since_comma = False
    for ch in body:
        if ch == "{":
            d += 1
        elif ch == "}":
            d -= 1
        elif ch == "," and d == 0:
            if saw_any_non_whitespace_since_comma:
                variant_count += 1
            saw_any_non_whitespace_since_comma = False
            continue
        if not ch.isspace():
            saw_any_non_whitespace_since_comma = True
    if saw_any_non_whitespace_since_comma:
        variant_count += 1
    return variant_count


def check_step_enum_and_sequence_array(sequence_rs_path: Path = SEQUENCE_RS) -> SurfaceCheckResult:
    """REQ-51: `EngineStep` declares exactly five variants, and
    `STEP_SEQUENCE`'s own compile-time length assertion is present and
    asserts `== 5`."""
    if not sequence_rs_path.exists():
        return SurfaceCheckResult(ok=False, detail=f"{sequence_rs_path} does not exist")
    src = _strip_line_comments(sequence_rs_path.read_text(encoding="utf-8"))
    violations: list[str] = []
    count = _enum_variant_count(src, "EngineStep")
    if count is None:
        violations.append("could not find `pub enum EngineStep` in sequence.rs")
    elif count != 5:
        violations.append(f"EngineStep declares {count} variant(s), expected exactly 5")
    if not re.search(r"pub\s+const\s+STEP_SEQUENCE\s*:\s*\[\s*EngineStep\s*;\s*5\s*\]", src):
        violations.append(
            "could not find `pub const STEP_SEQUENCE: [EngineStep; 5]` in sequence.rs "
            "(the array's own declared, fixed length must be 5)"
        )
    if not re.search(r"assert!\s*\(\s*STEP_SEQUENCE\.len\(\)\s*==\s*5", src):
        violations.append(
            "could not find a compile-time `assert!(STEP_SEQUENCE.len() == 5 ...)` in "
            "sequence.rs: an edit that adds or removes a step must fail the build, not "
            "a later test run"
        )
    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(
        ok=True,
        detail="EngineStep declares exactly five variants, STEP_SEQUENCE is declared as "
               "[EngineStep; 5], and a compile-time assert!(STEP_SEQUENCE.len() == 5) is "
               "present.",
    )


def check_mechanical_surface() -> SurfaceCheckResult:
    violations: list[str] = []
    details: list[str] = []
    for result in (
        check_forbid_unsafe_in_both_roots_and_no_unsafe_keyword(),
        check_exactly_one_binary_target(),
        check_std_process_and_std_net_absence(),
        check_step_enum_and_sequence_array(),
    ):
        if not result.ok:
            violations += result.violations or [result.detail]
        else:
            details.append(result.detail)
    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(ok=True, detail=" ".join(details))


# ---------------------------------------------------------------------------------
# Check 4: boundary-gjoll/actuator-git absence, narrowed by discrepancy A
# (see module docstring). actuator-git's absence is still fatal;
# boundary-gjoll's presence is reported, not flagged.
# ---------------------------------------------------------------------------------


def check_boundary_gjoll_and_actuator_git_absence(
    manifest_path: Path = CRATE_MANIFEST,
) -> SurfaceCheckResult:
    """REQ-51's own text asks for BOTH `boundary-gjoll` and `actuator-git`
    to be absent from `[dependencies]`. Discrepancy A (see module
    docstring) discloses that `boundary-gjoll` is now a real, approved
    dependency of this crate; this check is narrowed to what is actually
    true and disclosed: `actuator-git` absence is still fatal if violated;
    `boundary-gjoll`'s presence is reported in the detail string, never
    treated as a violation."""
    if not manifest_path.exists():
        return SurfaceCheckResult(ok=False, detail=f"{manifest_path} does not exist")
    data = tomllib.loads(manifest_path.read_text())
    deps = data.get("dependencies", {}) or {}
    violations: list[str] = []
    for forbidden in sorted(FORBIDDEN_DEPENDENCIES):
        if forbidden in deps:
            violations.append(
                f"[dependencies] carries {forbidden!r}, which must remain absent"
            )
    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    boundary_gjoll_note = (
        "boundary-gjoll IS present, which is the disclosed, approved discrepancy A state "
        "(see module docstring), not a violation."
        if "boundary-gjoll" in deps
        else "boundary-gjoll is also absent."
    )
    return SurfaceCheckResult(
        ok=True,
        detail=f"actuator-git is absent from [dependencies]. {boundary_gjoll_note}",
    )


# ---------------------------------------------------------------------------------
# Check 5: the Rust suite (REUSED, never reimplemented).
# ---------------------------------------------------------------------------------


def toolchain_present() -> bool:
    return rust_gate_harness.toolchain_present()


def run_rust_suite(crate_dir: Path = CRATE_DIR) -> tuple[bool, str]:
    return rust_gate_harness.run_rust_suite(crate_dir)


# ---------------------------------------------------------------------------------
# Negative controls (invariant 3.10, D10; REQ-51, AC-56). One synthetic
# violation per check, each proving the scan bites.
# ---------------------------------------------------------------------------------


def control_check() -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as d:
        # Check 1 control: dependency posture. An unlisted name must be caught.
        bad_manifest = Path(d) / "Cargo.toml"
        bad_manifest.write_text(
            '[package]\nname = "process-engine"\n\n[dependencies]\n'
            'himinbjorg = { path = "../himinbjorg" }\n'
            'hierarchy-vor = { path = "../hierarchy-vor" }\n'
            'boundary-gjoll = { path = "../boundary-gjoll" }\n'
            'actuator-git = { path = "../actuator-git" }\n'
        )
        dep_result = check_dependency_posture(bad_manifest)
        if dep_result.ok:
            failures.append(
                "dependency-posture control did NOT catch an unlisted (actuator-git) "
                "entry in [dependencies]"
            )

        clean_manifest = Path(d) / "Cargo-clean.toml"
        clean_manifest.write_text(
            '[package]\nname = "process-engine"\n\n[dependencies]\n'
            'himinbjorg = { path = "../himinbjorg" }\n'
            'hierarchy-vor = { path = "../hierarchy-vor" }\n'
            'boundary-gjoll = { path = "../boundary-gjoll" }\n'
        )
        clean_result = check_dependency_posture(clean_manifest)
        if not clean_result.ok:
            failures.append(
                "dependency-posture control WRONGLY flagged a manifest carrying only "
                "the three disclosed, permitted dependencies"
            )

        # Check 2 control: test isolation. A stray #[test] fn outside lib.rs
        # must be caught, including in a file named main.rs.
        bad_src = Path(d) / "src_bad"
        bad_src.mkdir()
        (bad_src / "lib.rs").write_text(
            '#![forbid(unsafe_code)]\n#[cfg(test)]\n#[path = "../unit_tests/x.rs"]\nmod x;\n'
            '#[cfg(test)]\npub(crate) use proposal::build_proposal;\n'
        )
        (bad_src / "main.rs").write_text("#[test]\nfn sneaky() {}\n")
        isolation_result = check_test_isolation(bad_src, Path(d) / "ut_absent", Path(d) / "t_absent")
        if isolation_result.ok:
            failures.append(
                "test-isolation control did NOT catch a stray #[test] fn in main.rs"
            )

        good_src = Path(d) / "src_good"
        good_src.mkdir()
        (good_src / "lib.rs").write_text(
            '#![forbid(unsafe_code)]\n#[cfg(test)]\n#[path = "../unit_tests/x.rs"]\nmod x;\n'
            '#[cfg(test)]\npub(crate) use proposal::build_proposal;\n'
        )
        (good_src / "main.rs").write_text("#![forbid(unsafe_code)]\nfn main() {}\n")
        good_isolation_result = check_test_isolation(good_src, Path(d) / "ut_absent2", Path(d) / "t_absent2")
        if not good_isolation_result.ok:
            failures.append(
                "test-isolation control WRONGLY flagged this crate's own two permitted "
                "lib.rs shapes (path-mod declaration and pub(crate) use alias)"
            )

        # Check 3a control: forbid(unsafe_code) in both roots, no unsafe keyword.
        bad_unsafe_dir = Path(d) / "src_unsafe"
        bad_unsafe_dir.mkdir()
        (bad_unsafe_dir / "lib.rs").write_text("#![forbid(unsafe_code)]\n")
        (bad_unsafe_dir / "main.rs").write_text("fn main() {}\n")  # missing forbid
        (bad_unsafe_dir / "execute.rs").write_text("fn f() { unsafe { std::ptr::null::<u8>(); } }\n")
        unsafe_result = check_forbid_unsafe_in_both_roots_and_no_unsafe_keyword(
            bad_unsafe_dir / "lib.rs", bad_unsafe_dir / "main.rs", bad_unsafe_dir
        )
        if unsafe_result.ok:
            failures.append(
                "forbid(unsafe_code)/unsafe-keyword control did NOT catch a missing "
                "attribute in main.rs and a planted unsafe keyword"
            )

        # Check 3b control: exactly one [[bin]] target.
        bad_bin_manifest = Path(d) / "Cargo-twobins.toml"
        bad_bin_manifest.write_text(
            '[package]\nname = "process-engine"\n\n'
            '[[bin]]\nname = "process-engine"\npath = "src/main.rs"\n\n'
            '[[bin]]\nname = "process-engine-second"\npath = "src/second.rs"\n'
        )
        bin_result = check_exactly_one_binary_target(bad_bin_manifest)
        if bin_result.ok:
            failures.append("binary-target control did NOT catch a manifest with two [[bin]] targets")

        # Check 3c control: std::process/std::net absence, with the
        # disclosed exception scoped correctly.
        bad_proc_dir = Path(d) / "src_proc"
        bad_proc_dir.mkdir()
        (bad_proc_dir / "main.rs").write_text(
            "fn main() { std::process::exit(0); std::process::Command::new(\"x\"); }\n"
        )
        (bad_proc_dir / "other.rs").write_text("fn f() { let _ = std::net::TcpStream::connect(\"x\"); }\n")
        proc_result = check_std_process_and_std_net_absence(bad_proc_dir)
        if proc_result.ok or len(proc_result.violations) < 2:
            failures.append(
                "std::process/std::net control did NOT catch a planted std::process::"
                "Command call and a planted std::net call, while permitting the one "
                "disclosed std::process::exit exception in main.rs"
            )

        # Check 3d control: EngineStep's five variants, STEP_SEQUENCE's
        # length assertion.
        bad_sequence_rs = Path(d) / "sequence_bad.rs"
        bad_sequence_rs.write_text(
            "pub enum EngineStep {\n"
            "    AcceptTask,\n"
            "    Cognition,\n"
            "    ProposeAction,\n"
            "    Gate,\n"
            "    Execute,\n"
            "    ResultOut,\n"
            "}\n"
            "pub const STEP_SEQUENCE: [EngineStep; 6] = [];\n"
        )
        sequence_result = check_step_enum_and_sequence_array(bad_sequence_rs)
        if sequence_result.ok:
            failures.append(
                "step-enum/sequence-array control did NOT catch a six-variant EngineStep "
                "with no compile-time length assertion"
            )

        # Check 4 control: actuator-git absence, boundary-gjoll narrowing.
        bad_actuator_manifest = Path(d) / "Cargo-actuator.toml"
        bad_actuator_manifest.write_text(
            '[package]\nname = "process-engine"\n\n[dependencies]\n'
            'himinbjorg = { path = "../himinbjorg" }\n'
            'hierarchy-vor = { path = "../hierarchy-vor" }\n'
            'boundary-gjoll = { path = "../boundary-gjoll" }\n'
            'actuator-git = { path = "../actuator-git" }\n'
        )
        actuator_result = check_boundary_gjoll_and_actuator_git_absence(bad_actuator_manifest)
        if actuator_result.ok:
            failures.append(
                "boundary-gjoll/actuator-git-absence control did NOT catch a planted "
                "actuator-git dependency"
            )

        clean_actuator_manifest = Path(d) / "Cargo-actuator-clean.toml"
        clean_actuator_manifest.write_text(
            '[package]\nname = "process-engine"\n\n[dependencies]\n'
            'himinbjorg = { path = "../himinbjorg" }\n'
            'hierarchy-vor = { path = "../hierarchy-vor" }\n'
            'boundary-gjoll = { path = "../boundary-gjoll" }\n'
        )
        clean_actuator_result = check_boundary_gjoll_and_actuator_git_absence(clean_actuator_manifest)
        if not clean_actuator_result.ok:
            failures.append(
                "boundary-gjoll/actuator-git-absence control WRONGLY flagged a manifest "
                "carrying the disclosed boundary-gjoll dependency without actuator-git"
            )

    return failures


def main() -> int:
    print("Process-engine posture detector (REQ-51): dependency posture (against the")
    print("REAL, disclosed three-name dependency table, discrepancy A), test and code")
    print("isolation including main.rs, mechanical surface properties (forbid(unsafe_code)")
    print("in both crate roots, one binary target, std::process/std::net absence with the")
    print("one disclosed std::process::exit exception, discrepancy B), EngineStep's five")
    print("variants and STEP_SEQUENCE's length assertion, boundary-gjoll/actuator-git")
    print("absence (narrowed by discrepancy A), and the Rust suite for")
    print("crates/process-engine/. See this module's own docstring for the full,")
    print("evidence-backed resolution of both disclosed discrepancies.")
    print()

    control_failures = control_check()
    if control_failures:
        print("NEGATIVE CONTROL FAILED (refusing to trust the checks below):")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    print("  [PASS] negative controls: a disallowed manifest, a stray test construct in "
          "src/ (including main.rs), a missing forbid(unsafe_code)/planted unsafe "
          "keyword, a two-binary-target manifest, planted std::process::Command/"
          "std::net calls, a six-variant step enum with no length assertion, and a "
          "planted actuator-git dependency are all caught, while this crate's own "
          "legitimate shapes (the pub(crate) use alias, the disclosed "
          "std::process::exit, the disclosed boundary-gjoll dependency) are all "
          "correctly permitted.")
    print()

    dep_result = check_dependency_posture()
    print(f"  [{'PASS' if dep_result.ok else 'CRITICAL'}] dependency posture: {dep_result.detail}")
    if not dep_result.ok:
        for v in dep_result.violations:
            print(f"    - {v}")
        return 1

    isolation_result = check_test_isolation()
    print(f"  [{'PASS' if isolation_result.ok else 'CRITICAL'}] test and code isolation "
          f"(including main.rs): {isolation_result.detail}")
    if not isolation_result.ok:
        for v in isolation_result.violations:
            print(f"    - {v}")
        return 1

    surface_result = check_mechanical_surface()
    print(f"  [{'PASS' if surface_result.ok else 'CRITICAL'}] mechanical surface properties: "
          f"{surface_result.detail}")
    if not surface_result.ok:
        for v in surface_result.violations:
            print(f"    - {v}")
        return 1

    absence_result = check_boundary_gjoll_and_actuator_git_absence()
    print(f"  [{'PASS' if absence_result.ok else 'CRITICAL'}] boundary-gjoll/actuator-git "
          f"absence: {absence_result.detail}")
    if not absence_result.ok:
        for v in absence_result.violations:
            print(f"    - {v}")
        return 1

    print()
    if not toolchain_present():
        print("  [SKIP] no Rust toolchain found on this machine (cargo not on PATH).")
        print("  The checks above already ran and passed; only the Rust suite is")
        print("  skipped. This is not a failure.")
        return 0

    ok, detail = run_rust_suite()
    print(f"  [{'PASS' if ok else 'CRITICAL'}] Rust suite: {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
