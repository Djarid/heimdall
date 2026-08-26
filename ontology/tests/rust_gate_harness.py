"""Rust gate drift detector (D109, spec section 3.6): is the Rust re-expression of
Gjoll's gate current, dependency-clean and passing.

Run from the repo root:

    python -m ontology.tests.rust_gate_harness

What this proves, and what it does not. A green result here means the Rust crate at
`crates/boundary-gjoll/` reproduces the Python gate's decisions on the 22 committed
golden vectors (`ontology/tools/export_gate_vectors.py`), that its manifest carries no
runtime dependency, and that the two source files the vectors were captured against
have not drifted underneath them. It says nothing about invariant 3.6's live-invocation
status, which `ontology.tests.gjoll_invocation_harness` still governs at zero non-test
call sites (D96): a passing translation-fidelity check is not a claim that anything
calls the gate in production.

Three checks, run in this fixed order (REQ-28), each of the first two fatal regardless
of whether a Rust toolchain is even present, because drift and a runtime dependency are
both facts about repository state, not about the toolchain:

  1. Digest drift. Recompute the SHA-256 of `ontology/nornir/gjoll.py` and
     `ontology/nornir/sink_declaration.py` and compare against the values recorded in
     the committed vector file. A mismatch names which file moved and instructs
     regeneration (`python -m ontology.tools.export_gate_vectors`) plus a review of the
     Rust re-expression, because a vector file regenerated without updating the Rust
     would still be caught by the replay itself failing (EC-3), and a cosmetic edit
     (a docstring, a comment) moves the digest deliberately, cheaply and unfoolably
     (EC-4): an AST-scoped digest would be a second parser to trust.
  2. Dependency posture. The crate manifest's `[dependencies]` table must be empty
     (REQ-6); `[dev-dependencies]` is exempt, and that exemption is stated in this
     check's own output, never silently assumed. A future runtime dependency is a
     deliberate trust-boundary decision requiring its own `DECISIONS.md` row (EC-13),
     on the same footing as a new `ALLOWED_IMPORT_ROOTS` entry (D71).
  3. The Rust suite. Invoke `cargo test` for the crate. A present toolchain whose test
     run returns non-zero is fatal, never laundered into a skip (REQ-29): skip
     detection keys on the toolchain-presence probe alone (`toolchain_present`,
     following `memgraph_integration_harness.py`'s skip-if-absent precedent), never on
     whether the test run itself succeeded.

One addition beyond the spec's assumed build order, stated here so it is not mistaken
for spec behaviour. The spec's build order (section 10.3) builds the crate skeleton
(files 1 to 5) before this sub-harness ever runs, so `check_dependency_posture` and
`run_rust_suite` always have a real manifest to read. This module is deliberately
authored and runnable BEFORE that skeleton lands (issue #16's scope, not this one's),
so `main()` treats an absent crate manifest as a distinct, non-fatal "not yet built"
state, reported with its own banner, separate from EC-1's toolchain-absent skip. Once
the workspace files exist, this path never fires again and the three checks run in
full exactly as the spec describes. Flagged for review before that build begins.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GJOLL_PY = REPO_ROOT / "ontology" / "nornir" / "gjoll.py"
SINK_DECLARATION_PY = REPO_ROOT / "ontology" / "nornir" / "sink_declaration.py"
VECTOR_FILE = REPO_ROOT / "crates" / "boundary-gjoll" / "vectors" / "gate_vectors.json"
CRATE_DIR = REPO_ROOT / "crates" / "boundary-gjoll"
CRATE_MANIFEST = CRATE_DIR / "Cargo.toml"


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@dataclass
class DigestCheckResult:
    ok: bool
    drifted_files: list[str] = field(default_factory=list)
    detail: str = ""


def check_digests(vector_file: Path = VECTOR_FILE) -> DigestCheckResult:
    """REQ-28 step 1. See the module docstring. An absent or unparseable vector file
    is a failure, never a skip (EC-11): a missing oracle is not a passing oracle."""
    if not vector_file.exists():
        return DigestCheckResult(
            ok=False,
            detail=(
                f"{vector_file} does not exist (EC-11: an absent oracle is not a "
                f"passing oracle). Run `python -m ontology.tools.export_gate_vectors` "
                f"first."
            ),
        )
    try:
        recorded = json.loads(vector_file.read_text())["generated_from"]
    except Exception as exc:  # noqa: BLE001 - fail closed on any parse problem
        return DigestCheckResult(ok=False, detail=f"{vector_file} could not be read: {exc}")

    drifted: list[str] = []
    for label, path, key in (
        ("gjoll.py", GJOLL_PY, "gjoll_py_sha256"),
        ("sink_declaration.py", SINK_DECLARATION_PY, "sink_declaration_py_sha256"),
    ):
        if recorded.get(key) != _sha256_of(path):
            drifted.append(label)

    if drifted:
        return DigestCheckResult(
            ok=False,
            drifted_files=drifted,
            detail=(
                f"source drift in {', '.join(drifted)}: the recorded digest no longer "
                f"matches the file's current bytes. Regenerate the vectors (`python -m "
                f"ontology.tools.export_gate_vectors`) and review the Rust "
                f"re-expression for the same change (EC-3, EC-4)."
            ),
        )
    return DigestCheckResult(ok=True, detail="both source digests match the committed vectors.")


@dataclass
class DependencyPostureResult:
    ok: bool
    manifest_found: bool
    violations: list[str] = field(default_factory=list)
    dev_dependencies_exempted: list[str] = field(default_factory=list)
    detail: str = ""


def _is_path_dependency(spec: object) -> bool:
    """True when a `[dependencies]` entry's TOML value is shaped as an
    in-workspace path dependency: a table carrying a `path` key and neither a
    `git` nor a `registry` key. A bare version string (`"1.0"`) or a table
    carrying `git`/`registry` is never a path dependency, whatever name it is
    filed under (REQ-30, HB3-3)."""
    return (
        isinstance(spec, dict)
        and "path" in spec
        and "git" not in spec
        and "registry" not in spec
    )


def check_dependency_posture(
    manifest_path: Path = CRATE_MANIFEST,
    permitted_path_dependencies: frozenset[str] = frozenset(),
) -> DependencyPostureResult:
    """REQ-6, REQ-28 step 2. See the module docstring for the manifest-absent case.

    Widened by REQ-30 (`.opencode/plans/himinbjorg-step-three.md`) to take an
    optional allowlist of permitted in-workspace PATH dependencies, defaulting
    to an empty `frozenset`. This exists because HB3-3 (that spec's section 4)
    settles that a crate is allowed exactly two named path dependencies on
    other in-workspace crates, each carrying an empty `[dependencies]` table
    of its own and `#![forbid(unsafe_code)]`, without that crate being read as
    carrying an external, reachability-widening dependency: the mechanical
    check must express the REAL rule (no external dependency) rather than the
    PROXY for it (an empty table).

    The default keeps BOTH of today's callers byte-for-byte identical to this
    function's behaviour before this widening (REQ-30, AC-47): this module's
    own use for `boundary-gjoll` and `rust_cohort_harness.py`'s use for
    `hierarchy-vor` both call this function with no allowlist argument, so
    `permitted_path_dependencies` is empty for both, and the branch below
    reproduces the original, strict logic verbatim -- any `[dependencies]`
    entry at all is a violation, with the exact original detail text. Only a
    caller that explicitly passes a non-empty allowlist (`himinbjorg`'s own
    two in-workspace path dependencies, via `rust_gateway_harness.py`) reaches
    the widened branch below it."""
    if not manifest_path.exists():
        return DependencyPostureResult(
            ok=True, manifest_found=False,
            detail=f"{manifest_path} does not exist yet; nothing to check.",
        )
    data = tomllib.loads(manifest_path.read_text())
    deps = data.get("dependencies", {}) or {}
    dev_deps = data.get("dev-dependencies", {}) or {}

    if not permitted_path_dependencies:
        # The original, strict behaviour, reproduced verbatim (REQ-30, AC-47):
        # any [dependencies] entry at all is a violation, regardless of shape.
        if deps:
            return DependencyPostureResult(
                ok=False, manifest_found=True, violations=sorted(deps),
                detail=(
                    f"[dependencies] is not empty: {sorted(deps)}. A runtime dependency on "
                    f"the gate path is a deliberate trust-boundary decision requiring its "
                    f"own DECISIONS.md row, never a silent addition (EC-13)."
                ),
            )
        exempt = sorted(dev_deps)
        detail = "[dependencies] is empty."
        if exempt:
            detail += (
                f" [dev-dependencies] is exempt from this check and is populated: "
                f"{exempt} (the exemption is stated, not hidden)."
            )
        return DependencyPostureResult(
            ok=True, manifest_found=True, dev_dependencies_exempted=exempt, detail=detail,
        )

    # The widened path (REQ-30, HB3-3): permit exactly the named in-workspace
    # PATH dependencies and fail on anything else -- an unlisted name, a
    # registry dependency, a git dependency, or a listed name whose spec is
    # not actually shaped as a path dependency.
    violations: list[str] = []
    permitted_present: list[str] = []
    for name, spec in deps.items():
        if name in permitted_path_dependencies and _is_path_dependency(spec):
            permitted_present.append(name)
        else:
            violations.append(name)

    if violations:
        return DependencyPostureResult(
            ok=False, manifest_found=True, violations=sorted(violations),
            detail=(
                f"[dependencies] carries an entry outside the permitted in-workspace "
                f"path-dependency allowlist ({sorted(permitted_path_dependencies)}): "
                f"{sorted(violations)}. An external, unlisted or non-path dependency is "
                f"a deliberate trust-boundary decision requiring its own DECISIONS.md "
                f"row, never a silent addition (EC-13)."
            ),
        )
    exempt = sorted(dev_deps)
    detail = (
        f"[dependencies] carries only the permitted in-workspace path dependencies "
        f"{sorted(permitted_present)} (the exemption is stated, not hidden): zero "
        f"external, unlisted or non-path dependencies."
    )
    if exempt:
        detail += (
            f" [dev-dependencies] is exempt from this check and is populated: "
            f"{exempt} (the exemption is stated, not hidden)."
        )
    return DependencyPostureResult(
        ok=True, manifest_found=True, dev_dependencies_exempted=exempt, detail=detail,
    )


def toolchain_present() -> bool:
    """REQ-29. Presence probe for the skip decision, keyed on the binary alone, never
    on whether a test run succeeds (`memgraph_integration_harness.py`'s
    skip-if-absent precedent)."""
    return shutil.which("cargo") is not None


def run_rust_suite(crate_dir: Path = CRATE_DIR) -> tuple[bool, str]:
    """REQ-28 step 3. Invoke the crate's test run. Only meaningful once
    `toolchain_present()` is True and the crate manifest exists; a non-zero result is
    always fatal here (REQ-29), never laundered into a skip.

    EC-2 requires a hang to return non-zero as fatal, never raise: a run that
    exceeds the timeout must be reported the same way as any other failing
    obligation, not propagate an exception up through `main()` (this module's
    own, and `run_rust_gjoll`'s in `ontology.tests.harness`, neither of which
    wraps this call in a try/except) and crash the whole suite run over one
    failing check. `subprocess.TimeoutExpired` is NOT a subclass of `OSError`,
    so it is caught explicitly and separately, not folded into the `OSError`
    branch above it."""
    try:
        result = subprocess.run(
            ["cargo", "test", "--manifest-path", str(crate_dir / "Cargo.toml")],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired as exc:
        return False, (
            f"cargo test did not complete within {exc.timeout:.0f}s and was killed "
            f"(EC-2: a hang is fatal and non-zero, never a skip and never an "
            f"unhandled exception). Acquiring or running the pinned toolchain "
            f"(rust-toolchain.toml) hung; this is a fatal result for this "
            f"obligation, not a crash of the whole suite run."
        )
    except OSError as exc:
        return False, f"could not invoke cargo test: {exc}"
    if result.returncode != 0:
        tail = (result.stdout[-2000:] + "\n" + result.stderr[-2000:]).strip()
        return False, (
            f"cargo test returned {result.returncode}. Acquiring the pinned toolchain "
            f"(rust-toolchain.toml) is a prerequisite, not an optional extra (EC-2).\n{tail}"
        )
    return True, "cargo test passed."


def control_check() -> list[str]:
    """REQ-31. Prove each fatal check can actually fail before it is trusted,
    following `gjoll_invocation_harness.py`'s `control_check` naming convention
    rather than inventing a second mechanism. Returns a list of failure descriptions
    (empty if both controls bite)."""
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as d:
        # Digest control: a vector file recording a deliberately wrong gjoll.py
        # digest must be reported as drift.
        bad_vectors = Path(d) / "gate_vectors.json"
        bad_vectors.write_text(json.dumps({
            "generated_from": {
                "gjoll_py_sha256": "0" * 64,
                "sink_declaration_py_sha256": _sha256_of(SINK_DECLARATION_PY),
            },
        }))
        digest_result = check_digests(bad_vectors)
        if digest_result.ok or "gjoll.py" not in digest_result.drifted_files:
            failures.append(
                "digest control did NOT report drift for a deliberately wrong "
                "gjoll.py digest"
            )

        # Dependency control: a manifest with a populated [dependencies] table must
        # be reported as a violation naming the offending crate.
        bad_manifest = Path(d) / "Cargo.toml"
        bad_manifest.write_text(
            '[package]\nname = "boundary-gjoll"\n\n[dependencies]\nserde = "1"\n'
        )
        dep_result = check_dependency_posture(bad_manifest)
        if dep_result.ok or "serde" not in dep_result.violations:
            failures.append(
                "dependency control did NOT report a violation for a manifest with a "
                "populated [dependencies] table"
            )

        # Control the dev-dependency exemption itself: a manifest with ONLY
        # dev-dependencies populated must report clean and name the exemption.
        exempt_manifest = Path(d) / "Cargo-exempt.toml"
        exempt_manifest.write_text(
            '[package]\nname = "boundary-gjoll"\n\n'
            '[dependencies]\n\n[dev-dependencies]\nserde_json = "1"\n'
        )
        exempt_result = check_dependency_posture(exempt_manifest)
        if not exempt_result.ok or "serde_json" not in exempt_result.dev_dependencies_exempted:
            failures.append(
                "dependency control did NOT report clean-with-exemption for a "
                "manifest with only [dev-dependencies] populated"
            )

    return failures


def main() -> int:
    print("Rust gate drift detector (D109): translation fidelity against the Python")
    print("reference, not invariant 3.6's live-invocation status (D96 still governs")
    print("that; see ontology.tests.gjoll_invocation_harness).")
    print()

    control_failures = control_check()
    if control_failures:
        print("NEGATIVE CONTROL FAILED (refusing to trust the checks below):")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    print("  [PASS] negative controls: a wrong digest is reported as drift, a "
          "populated [dependencies] table is reported as a violation, and a "
          "dev-dependency-only manifest reports clean with the exemption stated.")
    print()

    digest_result = check_digests()
    print(f"  [{'PASS' if digest_result.ok else 'CRITICAL'}] digest check: {digest_result.detail}")
    if not digest_result.ok:
        return 1  # fatal regardless of toolchain presence (REQ-28)

    dep_result = check_dependency_posture()
    print(f"  [{'PASS' if dep_result.ok else 'CRITICAL'}] dependency posture: {dep_result.detail}")
    if not dep_result.ok:
        return 1  # fatal regardless of toolchain presence (REQ-28)

    if not dep_result.manifest_found:
        print()
        print("  [SKIP] crates/boundary-gjoll/Cargo.toml does not exist yet: the crate")
        print("  workspace has not been built (see the module docstring). The digest and")
        print("  dependency checks above already ran against what does exist; only the")
        print("  test-run step is skipped. This is not a failure.")
        return 0

    if not toolchain_present():
        print()
        print("  [SKIP] no Rust toolchain found on this machine (cargo not on PATH).")
        print("  The digest and dependency checks above already ran and passed; only")
        print("  the test-run step is skipped (EC-1). This is not a failure.")
        return 0

    ok, detail = run_rust_suite()
    print(f"  [{'PASS' if ok else 'CRITICAL'}] Rust suite: {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
