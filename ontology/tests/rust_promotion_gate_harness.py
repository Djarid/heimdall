# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Jason Huxley and the Heimdall authors.

"""Rust promotion-gate drift, posture, no-clock and isolation detector
(`.opencode/plans/rust-promotion-gate-spec.md` REQ-43), on `rust_gate_harness.py`'s
and `rust_cohort_harness.py`'s own shape.

Run from the repo root:

    python -m ontology.tests.rust_promotion_gate_harness

Written from the spec alone, before the promotion-gate implementation exists. Every
check below is expected to report a CRITICAL or a not-yet-applicable state at this
stage of the build, which is correct: this harness exists so a future session can
watch the checks turn green one at a time as REQ-1 to REQ-32 land, never so it
reports a clean bill of health today.

REQ-43's five checks, in this fixed order, each with a mandatory negative control
that runs first:

  1. Digest drift. `crates/boundary-gjoll/vectors/gate_vectors.json`'s own
     `generated_from` digests (reused verbatim from `rust_gate_harness.check_digests`,
     never reimplemented) plus, once it exists,
     `crates/hierarchy-vor/vectors/promotion_vectors.json`'s own recorded source
     digest against `ontology/nornir/authorisation_record.py`.
  2. Dependency posture. `boundary-gjoll`'s manifest must carry EXACTLY the
     one-name allowlist `{"hierarchy-vor"}` (REQ-4); `hierarchy-vor`'s own manifest
     must keep its strict, zero-dependency default, checked via
     `rust_cohort_harness.check_dependency_posture` (never reimplemented).
  3. The no-clock text scan (REQ-22). No module under `crates/boundary-gjoll/src/`
     or `crates/hierarchy-vor/src/` may name `std::time`, `SystemTime`, `Instant`,
     `UNIX_EPOCH` or `chrono`.
  4. The test/code isolation grep (REQ-39). A grep for `#[test]`, `mod tests` or
     `#[cfg(test)]` over both crates' `src/` trees must return only the `#[cfg(test)]
     #[path = ...] mod ...;` declaration lines in each crate's `lib.rs`.
  5. The Rust suite (`cargo test --workspace`). Skips LOUDLY only when no Rust
     toolchain is present; a present toolchain whose test run fails is always fatal,
     never laundered into a skip.

What this harness does NOT prove. It says nothing about invariant 3.6's
live-invocation status (`ontology.tests.gjoll_invocation_harness` and the sibling
`ontology.tests.promotion_invocation_harness` govern that separately), and it is not
a functional test of the gate's own decisions (the Rust suite it invokes in step 5
covers that).
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from . import rust_gate_harness

REPO_ROOT = Path(__file__).resolve().parents[2]

GJOLL_CRATE_DIR = REPO_ROOT / "crates" / "boundary-gjoll"
GJOLL_MANIFEST = GJOLL_CRATE_DIR / "Cargo.toml"
GJOLL_SRC_DIR = GJOLL_CRATE_DIR / "src"
GATE_VECTOR_FILE = GJOLL_CRATE_DIR / "vectors" / "gate_vectors.json"

VOR_CRATE_DIR = REPO_ROOT / "crates" / "hierarchy-vor"
VOR_MANIFEST = VOR_CRATE_DIR / "Cargo.toml"
VOR_SRC_DIR = VOR_CRATE_DIR / "src"
PROMOTION_VECTOR_FILE = VOR_CRATE_DIR / "vectors" / "promotion_vectors.json"

AUTHORISATION_RECORD_PY = REPO_ROOT / "ontology" / "nornir" / "authorisation_record.py"

REQUIRED_PATH_DEPENDENCY = "hierarchy-vor"

_CLOCK_NAMES = ("std::time", "SystemTime", "Instant", "UNIX_EPOCH", "chrono")
_CLOCK_RE = re.compile("|".join(re.escape(n) for n in _CLOCK_NAMES))

_TEST_MARKER_RE = re.compile(r"#\[test\]|mod tests|#\[cfg\(test\)\]")
_UNIT_TEST_PATH_ATTR = re.compile(r'#\[path\s*=\s*"\.\./unit_tests/[^"]+"\]')


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _strip_line_comments(src: str) -> str:
    out_lines = []
    for line in src.split("\n"):
        idx = line.find("//")
        if idx == -1:
            out_lines.append(line)
        else:
            out_lines.append(line[:idx] + " " * (len(line) - idx))
    return "\n".join(out_lines)


# ---------------------------------------------------------------------------------
# Check 1: digest drift.
# ---------------------------------------------------------------------------------


@dataclass
class DigestCheckResult:
    ok: bool
    drifted_files: list[str] = field(default_factory=list)
    detail: str = ""


def check_gate_vector_digests(vector_file: Path = GATE_VECTOR_FILE) -> DigestCheckResult:
    """REQ-43 step 1, half one: reuse `rust_gate_harness.check_digests` verbatim
    against `boundary-gjoll`'s own vector file, never a second implementation."""
    result = rust_gate_harness.check_digests(vector_file)
    return DigestCheckResult(ok=result.ok, drifted_files=result.drifted_files, detail=result.detail)


def check_promotion_vector_digest(
    vector_file: Path = PROMOTION_VECTOR_FILE,
    source_file: Path = AUTHORISATION_RECORD_PY,
) -> DigestCheckResult:
    """REQ-43 step 1, half two: `crates/hierarchy-vor/vectors/promotion_vectors.json`'s
    own recorded source digest against `authorisation_record.py`. An absent vector
    file, or a vector file that has not yet been generated by the (not-yet-built)
    additive exporter section (REQ-42), is reported as a distinct, non-fatal
    "not yet built" state at this stage, on `rust_gate_harness.py`'s own precedent
    for the pre-skeleton state."""
    if not vector_file.exists():
        return DigestCheckResult(
            ok=True,
            detail=(
                f"{vector_file} does not exist yet (REQ-42's additive exporter "
                f"section has not run). Nothing to check yet at this stage; this is "
                f"the expected pre-build state, not a failure."
            ),
        )
    try:
        recorded = json.loads(vector_file.read_text()).get("generated_from", {})
    except Exception as exc:  # noqa: BLE001 - fail closed on any parse problem
        return DigestCheckResult(ok=False, detail=f"{vector_file} could not be read: {exc}")

    key = "authorisation_record_py_sha256"
    recorded_digest = recorded.get(key)
    if recorded_digest is None:
        return DigestCheckResult(
            ok=False,
            detail=f"{vector_file}'s generated_from carries no {key!r} key at all.",
        )
    actual_digest = _sha256_of(source_file)
    if recorded_digest != actual_digest:
        return DigestCheckResult(
            ok=False,
            drifted_files=["authorisation_record.py"],
            detail=(
                f"source drift in authorisation_record.py: recorded digest "
                f"{recorded_digest!r} does not match the file's current bytes "
                f"({actual_digest!r}). Regenerate the promotion vectors."
            ),
        )
    return DigestCheckResult(ok=True, detail="promotion vector source digest matches.")


# ---------------------------------------------------------------------------------
# Check 2: dependency posture (REQ-4).
# ---------------------------------------------------------------------------------


def check_gjoll_dependency_posture(manifest_path: Path = GJOLL_MANIFEST):
    """REQ-43 step 2, half one: `boundary-gjoll` must carry EXACTLY the one-name
    allowlist `{"hierarchy-vor"}` (REQ-4). Reuses
    `rust_gate_harness.check_dependency_posture` verbatim, passing the allowlist."""
    return rust_gate_harness.check_dependency_posture(
        manifest_path, permitted_path_dependencies=frozenset({REQUIRED_PATH_DEPENDENCY})
    )


def check_vor_dependency_posture(manifest_path: Path = VOR_MANIFEST):
    """REQ-43 step 2, half two: `hierarchy-vor` keeps its strict, zero-dependency
    default byte for byte, unchanged (REQ-3, REQ-4). Reuses the same function with
    NO allowlist, which is `rust_cohort_harness.check_dependency_posture`'s own
    default call shape, never reimplemented."""
    return rust_gate_harness.check_dependency_posture(manifest_path)


# ---------------------------------------------------------------------------------
# Check 3: the no-clock text scan (REQ-22).
# ---------------------------------------------------------------------------------


@dataclass
class NoClockCheckResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    detail: str = ""


def check_no_clock(src_dirs: tuple[Path, ...] = (GJOLL_SRC_DIR, VOR_SRC_DIR)) -> NoClockCheckResult:
    """REQ-22, REQ-43 step 3: no module under either crate's `src/` may name
    `std::time`, `SystemTime`, `Instant`, `UNIX_EPOCH` or `chrono`. A text scan, not
    an AST parse (this module has no Rust parser): comments and string literals are
    NOT stripped first, so this is a strictly conservative (over-inclusive) check --
    a mention inside a comment would also be flagged, which is the correct
    fail-closed direction for a control that must never silently pass a real clock
    read hidden behind a comment-stripping bug."""
    violations: list[str] = []
    for src_dir in src_dirs:
        if not src_dir.exists():
            continue
        for path in sorted(src_dir.rglob("*.rs")):
            src = path.read_text(encoding="utf-8", errors="replace")
            for m in _CLOCK_RE.finditer(src):
                lineno = src.count("\n", 0, m.start()) + 1
                try:
                    display_path = path.relative_to(REPO_ROOT)
                except ValueError:
                    display_path = path
                violations.append(
                    f"{display_path}:{lineno}: found clock-related "
                    f"name {m.group(0)!r} (REQ-22 forbids any clock source in "
                    f"either crate's src/)"
                )
    if violations:
        return NoClockCheckResult(
            ok=False, violations=violations, detail=f"{len(violations)} violation(s)"
        )
    return NoClockCheckResult(ok=True, detail="no clock-related name found in either crate's src/.")


# ---------------------------------------------------------------------------------
# Check 4: the test/code isolation grep (REQ-39).
# ---------------------------------------------------------------------------------


@dataclass
class IsolationCheckResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    detail: str = ""


def _check_isolation_over_files(files: dict[str, str]) -> list[str]:
    violations: list[str] = []
    for fname, raw_src in files.items():
        src = _strip_line_comments(raw_src)
        for m in _TEST_MARKER_RE.finditer(src):
            lineno = src.count("\n", 0, m.start()) + 1
            if fname != "lib.rs":
                violations.append(
                    f"{fname}:{lineno}: found `{m.group(0)}` outside lib.rs (REQ-39 "
                    f"requires the grep over src/ to return only lib.rs's own "
                    f"declaration lines)"
                )
                continue
            if m.group(0) != "#[cfg(test)]":
                violations.append(
                    f"{fname}:{lineno}: found `{m.group(0)}` in lib.rs (REQ-39 "
                    f"permits only `#[cfg(test)]` declaration lines here)"
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
                    f"mod ...;` declaration (REQ-39)"
                )
    return violations


def _load_rust_files(src_dir: Path) -> dict[str, str]:
    if not src_dir.exists():
        return {}
    return {
        str(p.relative_to(src_dir)): p.read_text(encoding="utf-8")
        for p in sorted(src_dir.rglob("*.rs"))
    }


def check_test_isolation(
    src_dirs: tuple[Path, ...] = (GJOLL_SRC_DIR, VOR_SRC_DIR)
) -> IsolationCheckResult:
    """REQ-39, REQ-43 step 4: the only test construct permitted anywhere under
    `src/` is the `#[cfg(test)] #[path = "../unit_tests/<name>.rs"] mod <name>;`
    declaration in each crate's `lib.rs`."""
    violations: list[str] = []
    for src_dir in src_dirs:
        files = _load_rust_files(src_dir)
        violations += [
            f"{src_dir.parent.name}/src/{v}" for v in _check_isolation_over_files(files)
        ]
    if violations:
        return IsolationCheckResult(
            ok=False, violations=violations, detail=f"{len(violations)} violation(s)"
        )
    return IsolationCheckResult(
        ok=True, detail="only the permitted #[cfg(test)] declaration lines found."
    )


# ---------------------------------------------------------------------------------
# Check 5: the Rust suite.
# ---------------------------------------------------------------------------------


def toolchain_present() -> bool:
    return shutil.which("cargo") is not None


def run_rust_workspace_suite() -> tuple[bool, str]:
    """REQ-43 step 5: `cargo test --workspace`. A non-zero result is always fatal,
    never laundered into a skip (mirrors `rust_gate_harness.run_rust_suite`'s own
    `TimeoutExpired` handling exactly)."""
    try:
        result = subprocess.run(
            ["cargo", "test", "--workspace"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=900,
        )
    except subprocess.TimeoutExpired as exc:
        return False, (
            f"cargo test --workspace did not complete within {exc.timeout:.0f}s and "
            f"was killed (a hang is fatal and non-zero, never a skip)."
        )
    except OSError as exc:
        return False, f"could not invoke cargo test --workspace: {exc}"
    if result.returncode != 0:
        tail = (result.stdout[-2000:] + "\n" + result.stderr[-2000:]).strip()
        return False, f"cargo test --workspace returned {result.returncode}.\n{tail}"
    return True, "cargo test --workspace passed."


# ---------------------------------------------------------------------------------
# Mandatory negative controls, run first, following gjoll_invocation_harness.py's
# and rust_gate_harness.py's own control_check naming and shape.
# ---------------------------------------------------------------------------------


def control_check() -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as d:
        # Digest control (gate vectors): a deliberately wrong gjoll.py digest
        # must be reported as drift.
        bad_gate_vectors = Path(d) / "gate_vectors.json"
        bad_gate_vectors.write_text(json.dumps({
            "generated_from": {
                "gjoll_py_sha256": "0" * 64,
                "sink_declaration_py_sha256": _sha256_of(
                    REPO_ROOT / "ontology" / "nornir" / "sink_declaration.py"
                ),
            },
        }))
        gate_digest_result = check_gate_vector_digests(bad_gate_vectors)
        if gate_digest_result.ok or "gjoll.py" not in gate_digest_result.drifted_files:
            failures.append(
                "gate-vector digest control did NOT report drift for a "
                "deliberately wrong gjoll.py digest"
            )

        # Digest control (promotion vectors): a deliberately wrong
        # authorisation_record.py digest, with a PRESENT promotion vector file,
        # must be reported as drift.
        bad_promotion_vectors = Path(d) / "promotion_vectors.json"
        bad_promotion_vectors.write_text(json.dumps({
            "generated_from": {"authorisation_record_py_sha256": "0" * 64},
        }))
        promo_digest_result = check_promotion_vector_digest(bad_promotion_vectors)
        if promo_digest_result.ok or "authorisation_record.py" not in promo_digest_result.drifted_files:
            failures.append(
                "promotion-vector digest control did NOT report drift for a "
                "deliberately wrong authorisation_record.py digest"
            )

        # Dependency control (gjoll): a manifest naming an UNLISTED path
        # dependency (not hierarchy-vor) must fail even under the one-name
        # allowlist.
        bad_gjoll_manifest = Path(d) / "boundary-gjoll-Cargo.toml"
        bad_gjoll_manifest.write_text(
            '[package]\nname = "boundary-gjoll"\n\n'
            '[dependencies]\nsome-other-crate = { path = "../some-other-crate" }\n'
        )
        gjoll_dep_result = check_gjoll_dependency_posture(bad_gjoll_manifest)
        if gjoll_dep_result.ok or "some-other-crate" not in gjoll_dep_result.violations:
            failures.append(
                "boundary-gjoll dependency-posture control did NOT report a "
                "violation for a manifest naming an unlisted path dependency"
            )

        # Dependency control (gjoll): a registry dependency named "hierarchy-vor"
        # (not path-shaped) must ALSO fail, because the allowlist requires a
        # path-shaped entry, not merely the right name.
        registry_gjoll_manifest = Path(d) / "boundary-gjoll-registry-Cargo.toml"
        registry_gjoll_manifest.write_text(
            '[package]\nname = "boundary-gjoll"\n\n'
            '[dependencies]\nhierarchy-vor = "1.0"\n'
        )
        registry_dep_result = check_gjoll_dependency_posture(registry_gjoll_manifest)
        if registry_dep_result.ok or "hierarchy-vor" not in registry_dep_result.violations:
            failures.append(
                "boundary-gjoll dependency-posture control did NOT report a "
                "violation for a registry-shaped entry named hierarchy-vor "
                "(REQ-4 requires a genuine path dependency, not merely the name)"
            )

        # Dependency control (vor): a manifest with a populated [dependencies]
        # table must be reported as a violation under the strict, zero-allowlist
        # default (REQ-3 must stay untouched).
        bad_vor_manifest = Path(d) / "hierarchy-vor-Cargo.toml"
        bad_vor_manifest.write_text(
            '[package]\nname = "hierarchy-vor"\n\n[dependencies]\nserde = "1"\n'
        )
        vor_dep_result = check_vor_dependency_posture(bad_vor_manifest)
        if vor_dep_result.ok or "serde" not in vor_dep_result.violations:
            failures.append(
                "hierarchy-vor dependency-posture control did NOT report a "
                "violation for a manifest with a populated [dependencies] table "
                "(REQ-3's strict default must stay untouched)"
            )

        # No-clock control: a fixture file naming SystemTime must be caught.
        clock_dir = Path(d) / "clock-fixture-src"
        clock_dir.mkdir()
        (clock_dir / "fixture.rs").write_text(
            "use std::time::{SystemTime, UNIX_EPOCH};\nfn now() -> u64 { 0 }\n"
        )
        clock_result = check_no_clock((clock_dir,))
        if clock_result.ok:
            failures.append(
                "no-clock control did NOT catch a fixture file naming "
                "SystemTime/UNIX_EPOCH"
            )

        # No-clock control (negative-negative): a clean fixture file must NOT be
        # flagged.
        clean_clock_dir = Path(d) / "clean-clock-fixture-src"
        clean_clock_dir.mkdir()
        (clean_clock_dir / "fixture.rs").write_text("fn now(caller_supplied: u64) -> u64 { caller_supplied }\n")
        clean_clock_result = check_no_clock((clean_clock_dir,))
        if not clean_clock_result.ok:
            failures.append(
                "no-clock control WRONGLY flagged a clean fixture file with no "
                "clock-related name at all"
            )

        # Isolation control: a stray #[test] fn directly in a fixture src/ file
        # (not lib.rs) must be caught.
        iso_dir = Path(d) / "isolation-fixture-src"
        iso_dir.mkdir()
        (iso_dir / "leaky.rs").write_text(
            "fn helper() {}\n\n#[test]\nfn a_stray_unit_test_in_src() {\n    assert!(true);\n}\n"
        )
        iso_result = check_test_isolation((iso_dir,))
        if iso_result.ok:
            failures.append(
                "test-isolation control did NOT catch a stray #[test] function "
                "landing directly in a src/ file outside lib.rs"
            )

        # Isolation control (negative-negative): a clean lib.rs's own permitted
        # declaration block must NOT be flagged.
        clean_iso_dir = Path(d) / "clean-isolation-fixture-src"
        clean_iso_dir.mkdir()
        (clean_iso_dir / "lib.rs").write_text(
            '#[cfg(test)]\n#[path = "../unit_tests/whatever.rs"]\nmod whatever;\n'
        )
        clean_iso_result = check_test_isolation((clean_iso_dir,))
        if not clean_iso_result.ok:
            failures.append(
                "test-isolation control WRONGLY flagged a clean lib.rs's own "
                "permitted #[cfg(test)] #[path = ...] mod ...; declaration block"
            )

    return failures


def main() -> int:
    print("Rust promotion-gate drift/posture/no-clock/isolation detector (REQ-43):")
    print("five checks, in fixed order, each preceded by its own negative control.")
    print()

    control_failures = control_check()
    if control_failures:
        print("NEGATIVE CONTROL FAILED (refusing to trust the checks below):")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    print("  [PASS] negative controls: every planted violation was caught and no "
          "clean fixture was wrongly flagged.")
    print()

    # Step 1: digest drift.
    gate_digest = check_gate_vector_digests()
    print(f"  [{'PASS' if gate_digest.ok else 'CRITICAL'}] gate vector digests: {gate_digest.detail}")
    promo_digest = check_promotion_vector_digest()
    print(f"  [{'PASS' if promo_digest.ok else 'CRITICAL'}] promotion vector digest: {promo_digest.detail}")
    if not (gate_digest.ok and promo_digest.ok):
        return 1  # fatal regardless of toolchain presence

    # Step 2: dependency posture.
    gjoll_dep = check_gjoll_dependency_posture()
    print(f"  [{'PASS' if gjoll_dep.ok else 'CRITICAL'}] boundary-gjoll dependency posture: {gjoll_dep.detail}")
    vor_dep = check_vor_dependency_posture()
    print(f"  [{'PASS' if vor_dep.ok else 'CRITICAL'}] hierarchy-vor dependency posture: {vor_dep.detail}")
    if not (gjoll_dep.ok and vor_dep.ok):
        return 1  # fatal regardless of toolchain presence

    # Step 3: the no-clock text scan.
    clock_result = check_no_clock()
    if clock_result.ok:
        print(f"  [PASS] no-clock scan: {clock_result.detail}")
    else:
        print(f"  [CRITICAL] no-clock scan: {clock_result.detail}")
        for v in clock_result.violations:
            print(f"    - {v}")
        return 1

    # Step 4: the test/code isolation grep.
    iso_result = check_test_isolation()
    if iso_result.ok:
        print(f"  [PASS] test/code isolation: {iso_result.detail}")
    else:
        print(f"  [CRITICAL] test/code isolation: {iso_result.detail}")
        for v in iso_result.violations:
            print(f"    - {v}")
        return 1

    # Step 5: the Rust suite, skipping LOUDLY only when no toolchain is present.
    print()
    if not toolchain_present():
        print("  [SKIP] no Rust toolchain found on this machine (cargo not on PATH).")
        print("  Steps 1 to 4 above already ran; only the Rust suite is skipped.")
        return 0

    ok, detail = run_rust_workspace_suite()
    print(f"  [{'PASS' if ok else 'CRITICAL'}] Rust suite (cargo test --workspace): {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
