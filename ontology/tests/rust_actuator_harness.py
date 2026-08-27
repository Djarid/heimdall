"""Git actuator posture detector (`.opencode/plans/git-actuator-step-four.md`
REQ-43): is `crates/actuator-git/` dependency-clean, test-and-code isolated,
mechanically sound at the properties section 4.1 to 4.5 name, and passing,
following `ontology/tests/rust_gateway_harness.py`'s and
`ontology/tests/rust_cohort_harness.py`'s exact shape (REQ-43).

Run from the repo root:

    python -m ontology.tests.rust_actuator_harness

What this proves, and what it does not. A green result here means the crate at
`crates/actuator-git/` carries an empty `[dependencies]` table and no
`[dev-dependencies]` table and no `license` field (REQ-2, REQ-4), keeps every
test construct out of `src/` (REQ-5), carries `#![forbid(unsafe_code)]` at file
scope with no `unsafe` keyword anywhere in its source (REQ-3, AC-54), declares
its operation vocabulary as exactly two variants (REQ-8), carries a non-empty
permitted-target allowlist excluding `main` and `master` (REQ-14, REQ-15), and
passes its own Rust suite (or loudly skips that one step alone, if no
toolchain is present, EC-16). It says NOTHING about invariant 3.6's
live-invocation status: whether `execute` or `broker_authorised_action` is
called by anything outside a test is `ontology.tests.actuator_invocation_harness`'s
job, not this module's (AC-46, AC-47).

Checks, run in this fixed order (REQ-43), the first four fatal regardless of
whether a Rust toolchain is even present, because dependency posture, test
isolation and the mechanical surface properties are all facts about the
committed source, not about the toolchain:

  1. Dependency posture. `[dependencies]` must be empty (REQ-2); UNLIKE
     `boundary-gjoll`'s and `hierarchy-vor`'s own precedent, `[dev-dependencies]`
     is NOT exempt here and must also be empty, and no `license` manifest field
     may exist (REQ-4). Reuses (never reimplements)
     `ontology.tests.rust_gate_harness.check_dependency_posture` for the
     `[dependencies]` half (REQ-43's own instruction: "reusing
     rust_gate_harness.check_dependency_posture by import, never by copy").
  2. Test and code isolation (REQ-5). The only test-related lines anywhere
     under `crates/actuator-git/src/` are `lib.rs`'s own
     `#[cfg(test)] #[path = "../unit_tests/..."] mod ...;` declarations, and no
     file name appears under both `src/` and a test directory.
  3. Mechanical surface properties (section 4.1 to 4.5, AC-54): `#![forbid(unsafe_code)]`
     is present at file scope in `src/lib.rs` (not `deny`, not `warn`, not on an
     inner item), the literal `unsafe` keyword appears nowhere in the crate's
     `src/` (both halves of AC-54); the operation enum (`GitOperation`) declares
     exactly two variants (REQ-8); the permitted-target allowlist is non-empty
     and excludes `main` and `master` (REQ-14, REQ-15).
  4. Cross-harness regression (AC-51): `rust_gateway_harness.PERMITTED_PATH_DEPENDENCIES`
     carries exactly three names, and `rust_gate_harness.check_dependency_posture`'s
     default (no allowlist argument) still reports the ORIGINAL strict behaviour
     -- any `[dependencies]` entry at all is a violation -- for `boundary-gjoll`
     and `hierarchy-vor`'s own manifests, byte for byte unchanged.
  5. The Rust suite, invoked via the REUSED `toolchain_present` and
     `run_rust_suite` helpers, scoped to this crate's own manifest. Skip
     discipline follows `rust_gateway_harness.py`'s own precedent: skip
     detection keys on the toolchain-presence probe alone, never on whether the
     test run itself would have succeeded.

REQ-43's own instruction, honoured: this module imports
`check_dependency_posture`, `toolchain_present` and `run_rust_suite` from
`rust_gate_harness`; it adds no second copy of any of the three. The
test-isolation and mechanical-surface checks below have no existing reusable
counterpart (each existing sub-harness's own version is hardcoded to a
different crate's field and type names), so they are written fresh here, on
the same mechanical-proxy, not-a-full-parser discipline
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
from . import rust_gateway_harness

REPO_ROOT = Path(__file__).resolve().parents[2]
CRATE_DIR = REPO_ROOT / "crates" / "actuator-git"
CRATE_MANIFEST = CRATE_DIR / "Cargo.toml"
SRC_DIR = CRATE_DIR / "src"
UNIT_TESTS_DIR = CRATE_DIR / "unit_tests"
TESTS_DIR = CRATE_DIR / "tests"
LIB_RS = SRC_DIR / "lib.rs"
TYPES_RS = SRC_DIR / "types.rs"
TARGETS_RS = SRC_DIR / "targets.rs"

PROTECTED_REF_NAMES: frozenset[str] = frozenset({"main", "master"})


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
# Check 1: dependency posture (REQ-2, REQ-4). The [dependencies] half reuses
# rust_gate_harness.check_dependency_posture directly; the dev-dependencies and
# license-field halves are this crate's own additional, stricter rules, since
# REQ-2/REQ-4 give it NO exemption boundary-gjoll and hierarchy-vor both have.
# ---------------------------------------------------------------------------------


@dataclass
class ManifestPostureResult:
    ok: bool
    manifest_found: bool
    violations: list[str] = field(default_factory=list)
    detail: str = ""


def check_dependency_posture(manifest_path: Path = CRATE_MANIFEST) -> ManifestPostureResult:
    """REQ-2 (empty [dependencies], reused from rust_gate_harness), REQ-2/REQ-6
    (no [dev-dependencies] at all -- stricter than boundary-gjoll's own
    exemption), REQ-4 (no `license` manifest field)."""
    if not manifest_path.exists():
        return ManifestPostureResult(
            ok=True, manifest_found=False,
            detail=f"{manifest_path} does not exist yet; nothing to check.",
        )
    deps_result = rust_gate_harness.check_dependency_posture(manifest_path)
    violations: list[str] = []
    if not deps_result.ok:
        violations.append(
            f"[dependencies] is not empty (REQ-2): {deps_result.violations}"
        )
    data = tomllib.loads(manifest_path.read_text())
    dev_deps = data.get("dev-dependencies", {}) or {}
    if dev_deps:
        violations.append(
            f"[dev-dependencies] is populated with {sorted(dev_deps)}: REQ-6 forbids a "
            f"dev-dependency for ANY crate in this workspace's git-actuator step, unlike "
            f"boundary-gjoll's/hierarchy-vor's own [dev-dependencies] exemption"
        )
    package = data.get("package", {}) or {}
    if "license" in package:
        violations.append(
            "the [package] table carries a `license` field (REQ-4 forbids this: the code "
            "licence stays OPEN and this step does not settle it)"
        )
    if violations:
        return ManifestPostureResult(
            ok=False, manifest_found=True, violations=violations,
            detail=f"{len(violations)} violation(s)",
        )
    return ManifestPostureResult(
        ok=True, manifest_found=True,
        detail="[dependencies] is empty, [dev-dependencies] is absent, and no `license` "
               "field exists.",
    )


# ---------------------------------------------------------------------------------
# Check 2: test and code isolation (REQ-5), on rust_gateway_harness.py's own
# discipline for this exact obligation, rewritten for this crate's own
# directory names.
# ---------------------------------------------------------------------------------

_TEST_MARKER_RE = re.compile(r"#\[test\]|mod tests|#\[cfg\(test\)\]")


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
                    f"{fname}:{lineno}: found `{m.group(0)}` outside lib.rs (REQ-5 "
                    f"permits test-related constructs under src/ only as lib.rs's own "
                    f"#[cfg(test)] #[path] declaration)"
                )
                continue
            if m.group(0) != "#[cfg(test)]":
                violations.append(
                    f"{fname}:{lineno}: found `{m.group(0)}` in lib.rs (only "
                    f"`#[cfg(test)]` declaration lines are permitted here)"
                )
                continue
            rest = src[m.end():]
            if not re.match(
                r'\s*\n\s*#\[path\s*=\s*"\.\./unit_tests/[^"]+"\]\s*\n\s*mod\s+\w+\s*;',
                rest,
            ):
                violations.append(
                    f"{fname}:{lineno}: found `#[cfg(test)]` in lib.rs not immediately "
                    f"followed by a `#[path = \"../unit_tests/...\"] mod ...;` declaration"
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
                f"file name(s) {overlap} appear under both src/ and {label} (REQ-5)"
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
               "#[path] declarations, and no file name is shared between src/ and "
               "unit_tests/ or tests/.",
    )


# ---------------------------------------------------------------------------------
# Check 3: mechanical surface properties (section 4.1 to 4.5, AC-54, REQ-8,
# REQ-14, REQ-15).
# ---------------------------------------------------------------------------------


@dataclass
class SurfaceCheckResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    detail: str = ""


def check_forbid_unsafe_and_no_unsafe_keyword(
    lib_rs_path: Path = LIB_RS, src_dir: Path = SRC_DIR
) -> SurfaceCheckResult:
    """AC-54: `#![forbid(unsafe_code)]` at file scope in lib.rs (REQ-3), and no
    `unsafe` keyword anywhere in the crate's src/ (proving the attribute is not
    merely present but unviolated)."""
    if not lib_rs_path.exists():
        return SurfaceCheckResult(ok=False, detail=f"{lib_rs_path} does not exist")
    lib_src = lib_rs_path.read_text(encoding="utf-8")
    violations: list[str] = []
    # Must be the file-scope inner attribute, `forbid`, not `deny`/`warn`, and
    # must appear before any item (a simple prefix check on the stripped,
    # leading-whitespace-trimmed content is sufficient here: this repository's
    # own convention, confirmed directly against every existing crate's
    # lib.rs, is to place it as the very first line).
    stripped = lib_src.lstrip()
    if not stripped.startswith("#![forbid(unsafe_code)]"):
        violations.append(
            "src/lib.rs does not begin with `#![forbid(unsafe_code)]` at file scope "
            "(REQ-3): either it is absent, it is `deny`/`warn` instead of `forbid`, or "
            "it is not the first item in the file"
        )
    files = _load_rust_files(src_dir)
    unsafe_re = re.compile(r"\bunsafe\b")
    for fname, raw_src in files.items():
        cleaned = _strip_line_comments(raw_src)
        for m in unsafe_re.finditer(cleaned):
            lineno = cleaned.count("\n", 0, m.start()) + 1
            violations.append(
                f"{fname}:{lineno}: the `unsafe` keyword appears in this crate's src/, "
                f"which would violate #![forbid(unsafe_code)] at compile time (AC-54)"
            )
    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(
        ok=True,
        detail="src/lib.rs begins with #![forbid(unsafe_code)], and the `unsafe` "
               "keyword appears nowhere in this crate's src/.",
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
    # payload (`Commit { message: String }`) nests its own braces, so only
    # commas at brace-depth zero are counted. This is a mechanical proxy, not
    # a full parser (matching this repository's own established discipline).
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


def check_operation_enum_has_exactly_two_variants(types_rs_path: Path = TYPES_RS) -> SurfaceCheckResult:
    """REQ-8: `GitOperation` declares exactly two variants."""
    if not types_rs_path.exists():
        return SurfaceCheckResult(ok=False, detail=f"{types_rs_path} does not exist")
    src = _strip_line_comments(types_rs_path.read_text(encoding="utf-8"))
    count = _enum_variant_count(src, "GitOperation")
    if count is None:
        return SurfaceCheckResult(ok=False, detail="could not find `pub enum GitOperation` in types.rs")
    if count != 2:
        return SurfaceCheckResult(
            ok=False,
            violations=[f"GitOperation declares {count} variant(s), expected exactly 2 (REQ-8)"],
            detail=f"{count} != 2",
        )
    return SurfaceCheckResult(ok=True, detail="GitOperation declares exactly two variants.")


_CONST_ARRAY_RE_TEMPLATE = r"const\s+{name}\s*:[^=]*=\s*&?\["


def _const_array_body(src: str, const_name: str) -> "str | None":
    """The body text of a `const <const_name>: ... = &[...];` array literal,
    found by naive bracket-depth matching from the first `[` after `=` to its
    matching `]`, mirroring `_enum_variant_count`'s brace-matching technique
    above (this file's own established discipline for isolating a single
    item's body rather than searching the whole file). Scoping to this body
    is what lets `check_permitted_target_allowlist` below tell
    `PERMITTED_TARGETS`'s own entries apart from an unrelated, legitimate
    defence-in-depth arm (REQ-16's `PROTECTED_REFS`) that names the same
    forbidden strings elsewhere in this same file."""
    m = re.search(_CONST_ARRAY_RE_TEMPLATE.format(name=re.escape(const_name)), src)
    if not m:
        return None
    depth = 1
    i = m.end()
    start = i
    while i < len(src) and depth > 0:
        if src[i] == "[":
            depth += 1
        elif src[i] == "]":
            depth -= 1
        i += 1
    return src[start : i - 1]


def check_permitted_target_allowlist(targets_rs_path: Path = TARGETS_RS) -> SurfaceCheckResult:
    """REQ-14, REQ-15: the permitted-target allowlist is non-empty and
    excludes `main` and `master`, checked textually against targets.rs's own
    source (a mechanical proxy: this cannot execute the compile-time assertion
    itself, which is `cargo build`'s own job; it looks for the literal
    forbidden ref names appearing as allowlist entries, which is a distinct,
    complementary signal). The absence check is scoped to `PERMITTED_TARGETS`'s
    own body only (via `_const_array_body`), never to the whole file: REQ-16's
    `PROTECTED_REFS` defence-in-depth arm legitimately names `main` and
    `master` elsewhere in this same file, and that is not a REQ-15
    violation."""
    if not targets_rs_path.exists():
        return SurfaceCheckResult(ok=False, detail=f"{targets_rs_path} does not exist")
    src = _strip_line_comments(targets_rs_path.read_text(encoding="utf-8"))
    allowlist_body = _const_array_body(src, "PERMITTED_TARGETS")
    if allowlist_body is None:
        return SurfaceCheckResult(ok=False, detail="could not find PERMITTED_TARGETS in targets.rs")
    violations: list[str] = []
    for protected in sorted(PROTECTED_REF_NAMES):
        if re.search(rf'"{protected}"', allowlist_body):
            violations.append(
                f"PERMITTED_TARGETS contains the literal string {protected!r}: REQ-15 "
                f"requires main and master to be ABSENT from the permitted-target "
                f"allowlist itself"
            )
    if not re.search(r"assert!\s*\(", src):
        violations.append(
            "targets.rs contains no `assert!(...)` at all: REQ-14 requires the "
            "allowlist's non-emptiness to be asserted at COMPILE time"
        )
    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(
        ok=True,
        detail="targets.rs contains a compile-time assertion and PERMITTED_TARGETS itself "
               "contains no literal 'main'/'master' string.",
    )


def check_mechanical_surface() -> SurfaceCheckResult:
    violations: list[str] = []
    details: list[str] = []
    for result in (
        check_forbid_unsafe_and_no_unsafe_keyword(),
        check_operation_enum_has_exactly_two_variants(),
        check_permitted_target_allowlist(),
    ):
        if not result.ok:
            violations += result.violations or [result.detail]
        else:
            details.append(result.detail)
    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(ok=True, detail=" ".join(details))


# ---------------------------------------------------------------------------------
# Check 4: cross-harness regression (AC-51). rust_gateway_harness's allowlist
# carries exactly three names, and rust_gate_harness's own DEFAULT behaviour
# (no allowlist argument) is unchanged for boundary-gjoll and hierarchy-vor.
# ---------------------------------------------------------------------------------


def check_ac51_cross_harness_regression() -> SurfaceCheckResult:
    violations: list[str] = []
    permitted = rust_gateway_harness.PERMITTED_PATH_DEPENDENCIES
    if len(permitted) != 3:
        violations.append(
            f"rust_gateway_harness.PERMITTED_PATH_DEPENDENCIES carries "
            f"{len(permitted)} name(s) ({sorted(permitted)}), expected exactly 3 "
            f"(AC-51, REQ-6)"
        )
    expected_three = {"boundary-gjoll", "hierarchy-vor", "actuator-git"}
    if set(permitted) != expected_three:
        violations.append(
            f"rust_gateway_harness.PERMITTED_PATH_DEPENDENCIES is {sorted(permitted)}, "
            f"expected exactly {sorted(expected_three)}"
        )

    boundary_gjoll_manifest = REPO_ROOT / "crates" / "boundary-gjoll" / "Cargo.toml"
    hierarchy_vor_manifest = REPO_ROOT / "crates" / "hierarchy-vor" / "Cargo.toml"
    for manifest in (boundary_gjoll_manifest, hierarchy_vor_manifest):
        result = rust_gate_harness.check_dependency_posture(manifest)
        if not result.ok:
            violations.append(
                f"rust_gate_harness.check_dependency_posture's DEFAULT (no allowlist "
                f"argument) wrongly reports {manifest} as a violation: {result.detail} "
                f"(AC-51 requires boundary-gjoll and hierarchy-vor to keep their strict "
                f"behaviour byte for byte)"
            )
    if violations:
        return SurfaceCheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return SurfaceCheckResult(
        ok=True,
        detail=f"rust_gateway_harness's allowlist carries exactly {sorted(permitted)}, and "
               f"rust_gate_harness.check_dependency_posture's default remains strict for "
               f"boundary-gjoll and hierarchy-vor.",
    )


# ---------------------------------------------------------------------------------
# Check 5: the Rust suite (REUSED, never reimplemented).
# ---------------------------------------------------------------------------------


def toolchain_present() -> bool:
    return rust_gate_harness.toolchain_present()


def run_rust_suite(crate_dir: Path = CRATE_DIR) -> tuple[bool, str]:
    return rust_gate_harness.run_rust_suite(crate_dir)


# ---------------------------------------------------------------------------------
# Negative controls (invariant 3.10, D10).
# ---------------------------------------------------------------------------------


def control_check() -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as d:
        bad_manifest = Path(d) / "Cargo.toml"
        bad_manifest.write_text(
            '[package]\nname = "actuator-git"\nlicense = "MIT"\n\n'
            '[dependencies]\nserde = "1"\n\n[dev-dependencies]\ntempfile = "3"\n'
        )
        result = check_dependency_posture(bad_manifest)
        if result.ok or len(result.violations) < 3:
            failures.append(
                "dependency-posture control did NOT catch a manifest with a populated "
                "[dependencies] table, a populated [dev-dependencies] table AND a "
                "license field (expected all three violations)"
            )

        clean_manifest = Path(d) / "Cargo-clean.toml"
        clean_manifest.write_text('[package]\nname = "actuator-git"\n\n[dependencies]\n')
        clean_result = check_dependency_posture(clean_manifest)
        if not clean_result.ok:
            failures.append(
                "dependency-posture control WRONGLY flagged a clean manifest with an "
                "empty [dependencies] table, no [dev-dependencies] and no license field"
            )

        bad_src = Path(d) / "src_bad"
        bad_src.mkdir()
        (bad_src / "lib.rs").write_text(
            '#![forbid(unsafe_code)]\n#[cfg(test)]\n#[path = "../unit_tests/x.rs"]\nmod x;\n'
        )
        (bad_src / "sneaky.rs").write_text("#[test]\nfn a() {}\n")
        isolation_result = check_test_isolation(bad_src, Path(d) / "ut_absent", Path(d) / "t_absent")
        if isolation_result.ok:
            failures.append("test-isolation control did NOT catch a stray #[test] fn in src/")

        bad_unsafe_dir = Path(d) / "src_unsafe"
        bad_unsafe_dir.mkdir()
        (bad_unsafe_dir / "lib.rs").write_text("#![forbid(unsafe_code)]\n")
        (bad_unsafe_dir / "execute.rs").write_text("fn f() { unsafe { std::ptr::null::<u8>(); } }\n")
        unsafe_result = check_forbid_unsafe_and_no_unsafe_keyword(
            bad_unsafe_dir / "lib.rs", bad_unsafe_dir
        )
        if unsafe_result.ok:
            failures.append("AC-54 control did NOT catch a planted `unsafe` keyword")

        bad_enum_types = Path(d) / "types_bad.rs"
        bad_enum_types.write_text(
            "pub enum GitOperation {\n"
            "    Commit { message: String },\n"
            "    Push { remote: String, ref_name: String },\n"
            "    Fetch,\n"
            "}\n"
        )
        enum_result = check_operation_enum_has_exactly_two_variants(bad_enum_types)
        if enum_result.ok:
            failures.append("REQ-8 control did NOT catch a three-variant GitOperation")

        bad_targets = Path(d) / "targets_bad.rs"
        bad_targets.write_text(
            'pub(crate) const PERMITTED_TARGETS: &[(&str, &str)] = &[("origin", "main")];\n'
        )
        targets_result = check_permitted_target_allowlist(bad_targets)
        if targets_result.ok:
            failures.append(
                "REQ-15 control did NOT catch a literal 'main' string in targets.rs with "
                "no compile-time assertion present"
            )

    return failures


def main() -> int:
    print("Git actuator posture detector (REQ-43): dependency posture, test and code")
    print("isolation, mechanical surface properties (AC-54, REQ-8, REQ-14, REQ-15), an")
    print("AC-51 cross-harness regression check, and the Rust suite for")
    print("crates/actuator-git/. Not invariant 3.6's live-invocation status (see")
    print("ontology.tests.actuator_invocation_harness for that, separately governed).")
    print()

    control_failures = control_check()
    if control_failures:
        print("NEGATIVE CONTROL FAILED (refusing to trust the checks below):")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    print("  [PASS] negative controls: a disallowed manifest, a stray test construct in "
          "src/, a planted unsafe keyword, a three-variant operation enum and a "
          "protected-ref-containing, unasserted allowlist are all caught.")
    print()

    dep_result = check_dependency_posture()
    print(f"  [{'PASS' if dep_result.ok else 'CRITICAL'}] dependency posture: {dep_result.detail}")
    if not dep_result.ok:
        for v in dep_result.violations:
            print(f"    - {v}")
        return 1

    isolation_result = check_test_isolation()
    print(f"  [{'PASS' if isolation_result.ok else 'CRITICAL'}] test and code isolation: "
          f"{isolation_result.detail}")
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

    regression_result = check_ac51_cross_harness_regression()
    print(f"  [{'PASS' if regression_result.ok else 'CRITICAL'}] AC-51 cross-harness "
          f"regression: {regression_result.detail}")
    if not regression_result.ok:
        for v in regression_result.violations:
            print(f"    - {v}")
        return 1

    print()
    if not toolchain_present():
        print("  [SKIP] no Rust toolchain found on this machine (cargo not on PATH).")
        print("  The checks above already ran and passed; only the Rust suite is")
        print("  skipped (EC-16). This is not a failure.")
        return 0

    ok, detail = run_rust_suite()
    print(f"  [{'PASS' if ok else 'CRITICAL'}] Rust suite: {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
