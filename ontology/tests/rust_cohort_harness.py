"""Rust cohort drift detector (D110, spec section 3.7): is the Rust re-expression of
Vor's minimal single-cohort form at `crates/hierarchy-vor/` current, dependency-clean,
surface-clean and passing, following D109's pattern and `rust_gate_harness.py`'s exact
shape (REQ-41).

Run from the repo root:

    python -m ontology.tests.rust_cohort_harness

What this proves, and what it does not (REQ-48). A green result here means the Rust
crate at `crates/hierarchy-vor/` reproduces the Python substrate's canonical encoding
and attestation byte-faithfully on the committed golden vectors
(`ontology/tools/export_cohort_vectors.py`), that its manifest carries no runtime
dependency, that its public surface still holds the mechanical shape REQ-42 fixes, and
that the two source files the vectors were captured against have not drifted
underneath them. It proves this crate cannot be obtained without its attestation
having verified. It does **not** advance invariant 3.6, does **not** close D103's
limit two (identity is not honesty), and does **not** change `AgentContext`'s opt-in
default in Python: none of those are this crate's job. Whether anything actually
calls `load_verified_cohort` or the secret loaders outside a test harness is a
DIFFERENT and separately governed claim, reported live by
`ontology.tests.vor_invocation_harness`, at zero non-test call sites today.

Four checks, run in this fixed order (REQ-41), the first three fatal regardless of
whether a Rust toolchain is even present, because drift, a runtime dependency and a
surface breach are all facts about repository state, not about the toolchain:

  1. Digest drift. Recompute the SHA-256 of `ontology/nornir/authorisation_record.py`
     and `ontology/nornir/sink_attestation.py` and compare against the values recorded
     in the committed vector file (`crates/hierarchy-vor/vectors/cohort_vectors.json`'s
     `generated_from`). A mismatch names which file moved and instructs regeneration
     (`python -m ontology.tools.export_cohort_vectors`).
  2. Dependency posture (REQ-5). REUSES (never reimplements)
     `ontology.tests.rust_gate_harness.check_dependency_posture`, called against
     `crates/hierarchy-vor/Cargo.toml`, and states the dev-dependency exemption in its
     own output.
  3. Surface checks (REQ-42). Six mechanical, text-level assertions over
     `crates/hierarchy-vor/src/` only -- see `check_surface`'s own docstring for each
     rule and why each is a defensible mechanical proxy rather than a full Rust parse.
  4. The Rust suite, invoked with `-- --nocapture` so REQ-36's two markers
     (`VOR-REAL-COHORT-VERIFIED` / `VOR-REAL-COHORT-NOT-EXERCISED`) are visible in the
     captured output and can be reported, never silently.

Skip discipline (REQ-43), following `memgraph_integration_harness.py`'s
skip-if-absent precedent: a machine with no Rust toolchain skips ONLY step four, and
only after steps one to three have already run and passed; skip detection keys on the
toolchain-presence probe alone (`toolchain_present`), never on whether a test run
itself would have succeeded. A present toolchain whose test run returns non-zero is
always fatal, never laundered into a skip. Separately and distinctly from the
toolchain skip, this harness always states whether REQ-36's real-cohort verification
was exercised (`VOR-REAL-COHORT-VERIFIED`, the secret was provisioned) or skipped
(`VOR-REAL-COHORT-NOT-EXERCISED`, or the whole suite run itself was skipped for lack of
a toolchain); a skip there is printed as a named gap, never as a pass.
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
AUTHORISATION_RECORD_PY = REPO_ROOT / "ontology" / "nornir" / "authorisation_record.py"
SINK_ATTESTATION_PY = REPO_ROOT / "ontology" / "nornir" / "sink_attestation.py"
VECTOR_FILE = REPO_ROOT / "crates" / "hierarchy-vor" / "vectors" / "cohort_vectors.json"
CRATE_DIR = REPO_ROOT / "crates" / "hierarchy-vor"
CRATE_MANIFEST = CRATE_DIR / "Cargo.toml"
SRC_DIR = CRATE_DIR / "src"

MARKER_VERIFIED = "VOR-REAL-COHORT-VERIFIED"
MARKER_NOT_EXERCISED = "VOR-REAL-COHORT-NOT-EXERCISED"


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# ---------------------------------------------------------------------------------
# Check 1: digest drift (REQ-41 step 1). Fatal regardless of toolchain presence:
# drift is a fact about repository state, not about the toolchain.
# ---------------------------------------------------------------------------------


@dataclass
class DigestCheckResult:
    ok: bool
    drifted_files: list[str] = field(default_factory=list)
    detail: str = ""


def check_digests(vector_file: Path = VECTOR_FILE) -> DigestCheckResult:
    """REQ-41 step 1. An absent or unparseable vector file is a failure, never a
    skip: a missing oracle is not a passing oracle (`rust_gate_harness.check_digests`'
    own precedent)."""
    if not vector_file.exists():
        return DigestCheckResult(
            ok=False,
            detail=(
                f"{vector_file} does not exist. Run `python -m "
                f"ontology.tools.export_cohort_vectors` first."
            ),
        )
    try:
        recorded = json.loads(vector_file.read_text())["generated_from"]
    except Exception as exc:  # noqa: BLE001 - fail closed on any parse problem
        return DigestCheckResult(ok=False, detail=f"{vector_file} could not be read: {exc}")

    drifted: list[str] = []
    for label, path, key in (
        ("authorisation_record.py", AUTHORISATION_RECORD_PY, "authorisation_record_py_sha256"),
        ("sink_attestation.py", SINK_ATTESTATION_PY, "sink_attestation_py_sha256"),
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
                f"ontology.tools.export_cohort_vectors`)."
            ),
        )
    return DigestCheckResult(ok=True, detail="both source digests match the committed vectors.")


# ---------------------------------------------------------------------------------
# Check 2: dependency posture (REQ-5). REUSES rust_gate_harness's own function;
# never reimplemented here.
# ---------------------------------------------------------------------------------


def check_dependency_posture(manifest_path: Path = CRATE_MANIFEST):
    """REQ-5, REQ-41 step 2. A thin call-through to
    `rust_gate_harness.check_dependency_posture`, passing this crate's own manifest
    path, so the check is never a second implementation. That function's own
    `detail` already states the dev-dependency exemption when one applies."""
    return rust_gate_harness.check_dependency_posture(manifest_path)


# ---------------------------------------------------------------------------------
# Check 3: the six surface checks (REQ-42). Text-level, mechanical assertions over
# `crates/hierarchy-vor/src/` only. Each rule is a defensible PROXY for its
# requirement, not a full Rust parse (this module has none): every rule is designed
# so it reports clean against the real crate today (verified by running it) and so
# it can be shown to bite against a small, deliberately-breaching fixture
# (REQ-44's control_check). A rule that cannot be shown to bite is not trusted.
# ---------------------------------------------------------------------------------


def _load_rust_files(src_dir: Path) -> dict[str, str]:
    if not src_dir.exists():
        return {}
    return {
        str(p.relative_to(src_dir)): p.read_text(encoding="utf-8")
        for p in sorted(src_dir.rglob("*.rs"))
    }


def _impl_blocks(src: str, type_name: str) -> list[str]:
    """Bodies of every direct `impl (<...>)? TypeName (<...>)? { ... }` block (never
    a trait impl -- `impl Trait for TypeName` -- which callers check separately),
    found by naive brace-depth matching. Good enough for this mechanical proxy;
    a full Rust parser is out of scope for a Python test harness."""
    blocks: list[str] = []
    pattern = re.compile(rf"impl(?:<[^>]*>)?\s+{re.escape(type_name)}\b(?:<[^>]*>)?\s*\{{")
    for m in pattern.finditer(src):
        depth = 0
        i = m.end() - 1
        start = i
        while i < len(src):
            if src[i] == "{":
                depth += 1
            elif src[i] == "}":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        blocks.append(src[start + 1 : i])
    return blocks


# Rule 1 (REQ-42 item 1, REQ-24): no public constructor/From/TryFrom/Clone/Copy/
# Default/Deref on VerifiedCohort, and no cfg(feature = ...) gate anywhere.
_FORBIDDEN_HANDLE_TRAITS = ("Clone", "Copy", "Default", "Deref", "From", "TryFrom")


def _check_handle_construction(files: dict[str, str]) -> list[str]:
    violations: list[str] = []
    all_src = "\n".join(files.values())
    if re.search(r"cfg\s*\(\s*feature\s*=", all_src):
        violations.append(
            "found a cfg(feature = ...) gate somewhere in the crate (REQ-24 forbids "
            "any feature escape hatch a downstream caller could enable)"
        )
    for fname, src in files.items():
        for m in re.finditer(
            r"#\[derive\(([^)]*)\)\]\s*\n(?:\s*#\[[^\]]*\]\s*\n)*\s*pub struct VerifiedCohort\b",
            src,
        ):
            derived = m.group(1)
            for trait in ("Clone", "Copy", "Default"):
                if trait in derived:
                    violations.append(
                        f"{fname}: VerifiedCohort derives {trait} (REQ-24 forbids "
                        f"Clone/Copy/Default on the verified cohort handle)"
                    )
        for m in re.finditer(
            r"impl(?:<[^>]*>)?\s+([\w:]+)(?:<[^>]*>)?\s+for\s+VerifiedCohort\b", src
        ):
            trait = m.group(1).rsplit("::", 1)[-1]
            if trait in _FORBIDDEN_HANDLE_TRAITS:
                violations.append(
                    f"{fname}: found `impl {trait} for VerifiedCohort` (REQ-24 forbids "
                    f"a public From/TryFrom/Clone/Copy/Default/Deref on the handle)"
                )
        for block in _impl_blocks(src, "VerifiedCohort"):
            for fn_m in re.finditer(r"\bpub fn (\w+)\s*\(([^)]*)\)", block):
                params = fn_m.group(2).strip()
                if not re.match(r"&\s*mut\s+self|&\s*self|self\b", params):
                    violations.append(
                        f"{fname}: `impl VerifiedCohort` exposes a public associated "
                        f"function `{fn_m.group(1)}` with no `self` receiver -- a "
                        f"public constructor (REQ-24 forbids one)"
                    )
    return violations


# Rule 2 (REQ-42 item 2, REQ-13, REQ-18): exactly two public functions return a
# trusted authoriser set, no public constructor from bytes, no Debug derive on the
# authoriser types.
def _check_authoriser_set_surface(files: dict[str, str]) -> list[str]:
    violations: list[str] = []
    all_src = "\n".join(files.values())
    returning = set(
        re.findall(r"\bpub fn (\w+)\([^)]*\)\s*->\s*Result<\s*TrustedAuthoriserSet\s*,", all_src)
    ) | set(re.findall(r"\bpub fn (\w+)\([^)]*\)\s*->\s*TrustedAuthoriserSet\b", all_src))
    if len(returning) != 2:
        violations.append(
            f"expected exactly two public functions returning a trusted authoriser "
            f"set (REQ-13), found {len(returning)}: {sorted(returning)}"
        )
    for fname, src in files.items():
        for block in _impl_blocks(src, "TrustedAuthoriserSet"):
            for fn_m in re.finditer(r"(pub(?:\(crate\))?)\s+fn (\w+)\s*\(([^)]*)\)", block):
                visibility, fn_name, params = fn_m.groups()
                if visibility == "pub" and re.search(r"&\s*\[\s*u8\s*\]|Vec\s*<\s*u8\s*>", params):
                    violations.append(
                        f"{fname}: `impl TrustedAuthoriserSet` exposes a PUBLIC "
                        f"function `{fn_name}` taking raw secret bytes (REQ-13 forbids "
                        f"a public constructor from bytes)"
                    )
        for type_name in ("TrustedAuthoriserSet", "SecretRefusal"):
            for m in re.finditer(
                rf"#\[derive\(([^)]*)\)\]\s*\n(?:\s*#\[[^\]]*\]\s*\n)*\s*pub (?:struct|enum) {type_name}\b",
                src,
            ):
                if "Debug" in m.group(1):
                    violations.append(
                        f"{fname}: {type_name} derives Debug (REQ-18 forbids a "
                        f"derived Debug on the authoriser types)"
                    )
    return violations


# Rule 3 (REQ-42 item 3, REQ-13): no identifier matching secret/key/passphrase/token
# bound to a string or byte-string literal. Matched on the identifier's LAST
# underscore-separated word, never a bare substring: `SECRET_PATH_ENV_VAR` (the
# real crate's own constant, naming WHERE a secret lives, never the secret itself)
# ends in `VAR` and is correctly left alone, while `AUTH_TOKEN` or a bare `secret`
# ends in a trigger word and is correctly caught. A substring match would flag the
# real, innocent constant; this is the deliberate, narrower rule that does not.
_SECRET_LITERAL_TRIGGER_WORDS = frozenset({"secret", "key", "passphrase", "token"})
_SECRET_LITERAL_BINDING = re.compile(
    r"\b(?:let(?:\s+mut)?|const|static(?:\s+mut)?)\s+([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"(?::\s*[^=;]+)?=\s*(b?\"(?:[^\"\\]|\\.)*\")"
)


def _check_no_secret_literals(files: dict[str, str]) -> list[str]:
    violations: list[str] = []
    for fname, src in files.items():
        for m in _SECRET_LITERAL_BINDING.finditer(src):
            ident, literal = m.group(1), m.group(2)
            last_word = ident.rsplit("_", 1)[-1].lower()
            if last_word in _SECRET_LITERAL_TRIGGER_WORDS:
                violations.append(
                    f"{fname}: identifier `{ident}` (ends in a secret/key/"
                    f"passphrase/token word) is bound directly to a literal "
                    f"{literal} (REQ-13 forbids a secret literal anywhere under src/)"
                )
    return violations


# Rule 4 (REQ-42 item 4, REQ-21): no ordering comparison or lattice constant applied
# to the trust ceiling.
def _check_no_trust_ordering(files: dict[str, str]) -> list[str]:
    violations: list[str] = []
    lhs_op = re.compile(
        r"([\w.]*trust_ceiling[\w.]*)\s*(<=|>=|<|(?<!-)>)\s*([^\n;]+)", re.IGNORECASE
    )
    rhs_op = re.compile(
        r"([^\n;]+?)\s*(<=|>=|<|(?<!-)>)\s*([\w.]*trust_ceiling[\w.]*)", re.IGNORECASE
    )
    for fname, src in files.items():
        if "TRUST_ORDER" in src:
            violations.append(
                f"{fname}: references TRUST_ORDER (REQ-21 forbids any lattice "
                f"constant applied to the opaque trust ceiling)"
            )
        for m in lhs_op.finditer(src):
            violations.append(
                f"{fname}: ordering comparison against the trust ceiling: "
                f"`{m.group(0).strip()}` (REQ-21)"
            )
        for m in rhs_op.finditer(src):
            violations.append(
                f"{fname}: ordering comparison against the trust ceiling: "
                f"`{m.group(0).strip()}` (REQ-21)"
            )
        if re.search(r"trust_ceiling[\w]*\s*\.\s*cmp\(", src, re.IGNORECASE):
            violations.append(
                f"{fname}: `.cmp(` called on the trust ceiling (REQ-21 forbids "
                f"ordering it)"
            )
    return violations


# Rule 5 (REQ-42 item 5, REQ-10): no comma, newline or `=` in any hardcoded cohort
# field value. Scoped to the five field names REQ-20 fixes.
_SCALAR_FIELD_NAMES = ("COHORT_ID", "TRUST_CEILING", "AUTHORISER_ID")
_LIST_FIELD_NAMES = ("PERMITTED_ACTIONS", "CONSEQUENTIAL_SINKS")
_FORBIDDEN_FIELD_SUBSTRINGS = ((",", "a comma"), ("\\n", "a newline (escaped)"), ("=", "an '='"))


def _check_hardcoded_field_values_clean(files: dict[str, str]) -> list[str]:
    violations: list[str] = []
    for fname, src in files.items():
        for name in _SCALAR_FIELD_NAMES:
            for m in re.finditer(rf'const {name}\s*:\s*&str\s*=\s*"((?:[^"\\]|\\.)*)"', src):
                value = m.group(1)
                for needle, label in _FORBIDDEN_FIELD_SUBSTRINGS:
                    if needle in value:
                        violations.append(
                            f"{fname}: hardcoded field {name} contains {label} "
                            f"(REQ-10 forbids this in the cohort's own field values)"
                        )
        for name in _LIST_FIELD_NAMES:
            for m in re.finditer(rf"const {name}\s*:\s*&\[&str\]\s*=\s*&\[([^\]]*)\]", src):
                for item_m in re.finditer(r'"((?:[^"\\]|\\.)*)"', m.group(1)):
                    value = item_m.group(1)
                    for needle, label in _FORBIDDEN_FIELD_SUBSTRINGS:
                        if needle in value:
                            violations.append(
                                f"{fname}: hardcoded field {name} contains a member "
                                f"with {label} (REQ-10)"
                            )
    return violations


# Rule 6 (REQ-42 item 6, REQ-38): the test-isolation grep returns only lib.rs's own
# declaration lines.
_UNIT_TEST_PATH_ATTR = re.compile(r'#\[path\s*=\s*"\.\./unit_tests/[^"]+"\]')

# AC-38's own, broader literal grep: `grep -rnE '#\[test\]|mod tests|#\[cfg\(test\)\]'
# crates/hierarchy-vor/src/` must return ONLY the `#[cfg(test)]` lines of lib.rs's
# declaration block, nothing else anywhere under src/. This is a strictly broader
# net than the `#[path = ...]` attachment check above (rule 6's original scope): it
# also catches a stray `#[test]` function or a stray `mod tests` block landing
# directly in a `src/` file, neither of which necessarily carries a `#[path = ...]`
# attribute at all, so rule 6 alone would miss them.
_AC38_TEST_MARKER = re.compile(r"#\[test\]|mod tests|#\[cfg\(test\)\]")


def _check_test_isolation(files: dict[str, str]) -> list[str]:
    violations: list[str] = []
    for fname, src in files.items():
        for m in _UNIT_TEST_PATH_ATTR.finditer(src):
            if fname != "lib.rs":
                lineno = src.count("\n", 0, m.start()) + 1
                violations.append(
                    f"{fname}:{lineno}: found a unit-test `#[path = ...]` attachment "
                    f"declaration outside lib.rs (REQ-38 requires exactly one such "
                    f"declaration per file, all of them in lib.rs)"
                )
    violations += _check_test_isolation_ac38_broad(files)
    return violations


def _strip_line_comments(src: str) -> str:
    """Truncates every line at its first `//`, replacing the removed tail with
    spaces so line numbers and byte offsets are preserved exactly. A mechanical
    proxy only (no string-literal awareness), which is safe here because none of
    this crate's `src/` files hold a `//` sequence inside a string literal
    (confirmed directly). Exists solely so AC-38's literal grep pattern is matched
    against CODE, not against the explanatory prose comment directly above lib.rs's
    own permitted declaration block, which otherwise also contains the literal text
    `#[cfg(test)]` and would be a false positive against the real, clean crate."""
    out_lines = []
    for line in src.split("\n"):
        idx = line.find("//")
        if idx == -1:
            out_lines.append(line)
        else:
            out_lines.append(line[:idx] + " " * (len(line) - idx))
    return "\n".join(out_lines)


def _check_test_isolation_ac38_broad(files: dict[str, str]) -> list[str]:
    """AC-38's literal grep, run exactly as its own wording states: every match of
    `#\\[test\\]|mod tests|#\\[cfg\\(test\\)\\]` anywhere under `src/` must be one of
    lib.rs's own declaration lines. A match in ANY other file, or a match in lib.rs
    that is not part of the permitted `#[cfg(test)] #[path = ...] mod ...;` block, is
    a violation. This is deliberately broader than `_check_test_isolation`'s
    `#[path = ...]`-only scan above: it also catches a bare stray `#[test]` fn or a
    bare `mod tests { ... }` block landing directly in a `src/` file, neither of
    which necessarily carries a `#[path = ...]` attribute of its own. Comments are
    stripped first (see `_strip_line_comments`) so a match is always real code."""
    violations: list[str] = []
    for fname, raw_src in files.items():
        src = _strip_line_comments(raw_src)
        for m in _AC38_TEST_MARKER.finditer(src):
            lineno = src.count("\n", 0, m.start()) + 1
            if fname != "lib.rs":
                violations.append(
                    f"{fname}:{lineno}: found `{m.group(0)}` outside lib.rs (AC-38 "
                    f"requires the broader `#[test]|mod tests|#[cfg(test)]` grep "
                    f"over src/ to return only lib.rs's own declaration lines)"
                )
                continue
            # In lib.rs, a `#[cfg(test)]` match is permitted ONLY when it is
            # immediately followed (allowing blank/comment lines) by a `#[path =
            # "../unit_tests/...")]` attribute and then a `mod ...;` declaration --
            # exactly the one permitted construct REQ-38 names. `#[test]` and
            # `mod tests` are never permitted in lib.rs at all.
            if m.group(0) != "#[cfg(test)]":
                violations.append(
                    f"{fname}:{lineno}: found `{m.group(0)}` in lib.rs (AC-38 "
                    f"permits only `#[cfg(test)]` declaration lines here, never a "
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
                    f"mod ...;` declaration (AC-38 permits only the fixed "
                    f"`#[cfg(test)] #[path = ...] mod ...;` block shape here)"
                )
    return violations


@dataclass
class SurfaceCheckResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    detail: str = ""


def _check_surface_over_files(files: dict[str, str]) -> SurfaceCheckResult:
    violations: list[str] = []
    violations += _check_handle_construction(files)
    violations += _check_authoriser_set_surface(files)
    violations += _check_no_secret_literals(files)
    violations += _check_no_trust_ordering(files)
    violations += _check_hardcoded_field_values_clean(files)
    violations += _check_test_isolation(files)
    if violations:
        return SurfaceCheckResult(
            ok=False, violations=violations, detail=f"{len(violations)} violation(s)"
        )
    return SurfaceCheckResult(ok=True, detail="all six surface checks report clean")


def check_surface(src_dir: Path = SRC_DIR) -> SurfaceCheckResult:
    """REQ-42, REQ-41 step 3. The six mechanical surface assertions over
    `crates/hierarchy-vor/src/` only. Fatal regardless of toolchain presence: a
    surface breach is a fact about the committed source, not about whether cargo
    is installed."""
    files = _load_rust_files(src_dir)
    if not files:
        return SurfaceCheckResult(ok=False, detail=f"no .rs files found under {src_dir}")
    return _check_surface_over_files(files)


# ---------------------------------------------------------------------------------
# Check 4: the Rust suite (REQ-41 step 4, REQ-36, REQ-43).
# ---------------------------------------------------------------------------------


def toolchain_present() -> bool:
    """REQ-43. Presence probe for the skip decision, keyed on the binary alone,
    never on whether a test run succeeds (`memgraph_integration_harness.py`'s
    skip-if-absent precedent, and `rust_gate_harness.toolchain_present`'s own
    shape)."""
    return shutil.which("cargo") is not None


def run_rust_suite(crate_dir: Path = CRATE_DIR) -> tuple[bool, str, str]:
    """REQ-41 step 4. Invokes `cargo test -p hierarchy-vor -- --nocapture` (the
    `--nocapture` is required: `tests/public_surface.rs`'s own header states test
    output is otherwise captured, and REQ-36's markers must be visible to this
    harness). Returns `(ok, marker, detail)`: `marker` is one of
    `MARKER_VERIFIED`, `MARKER_NOT_EXERCISED` or `""` if neither printed (which is
    itself reported, never silently treated as a pass). A non-zero return is
    always fatal here, never laundered into a skip (REQ-43); a hang returns non-zero
    fatal rather than raising, mirroring `rust_gate_harness.run_rust_suite`'s own
    `TimeoutExpired` handling exactly."""
    try:
        result = subprocess.run(
            ["cargo", "test", "-p", "hierarchy-vor", "--", "--nocapture"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired as exc:
        return False, "", (
            f"cargo test did not complete within {exc.timeout:.0f}s and was killed "
            f"(a hang is fatal and non-zero, never a skip)."
        )
    except OSError as exc:
        return False, "", f"could not invoke cargo test: {exc}"

    combined = (result.stdout or "") + "\n" + (result.stderr or "")
    if MARKER_VERIFIED in combined:
        marker = MARKER_VERIFIED
    elif MARKER_NOT_EXERCISED in combined:
        marker = MARKER_NOT_EXERCISED
    else:
        marker = ""

    if result.returncode != 0:
        tail = (result.stdout[-2000:] + "\n" + result.stderr[-2000:]).strip()
        return False, marker, f"cargo test returned {result.returncode}.\n{tail}"
    return True, marker, "cargo test passed."


# ---------------------------------------------------------------------------------
# REQ-44: mandatory negative controls, following gjoll_invocation_harness.py's
# control_check naming and shape rather than inventing a second mechanism.
# ---------------------------------------------------------------------------------


def control_check() -> list[str]:
    """Prove each fatal check can actually fail before it is trusted. Returns a
    list of failure descriptions (empty if every control bites)."""
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as d:
        # Digest control: a vector file recording a deliberately wrong
        # authorisation_record.py digest must be reported as drift.
        bad_vectors = Path(d) / "cohort_vectors.json"
        bad_vectors.write_text(json.dumps({
            "generated_from": {
                "authorisation_record_py_sha256": "0" * 64,
                "sink_attestation_py_sha256": _sha256_of(SINK_ATTESTATION_PY),
            },
        }))
        digest_result = check_digests(bad_vectors)
        if digest_result.ok or "authorisation_record.py" not in digest_result.drifted_files:
            failures.append(
                "digest control did NOT report drift for a deliberately wrong "
                "authorisation_record.py digest"
            )

        # Dependency control: a manifest with a populated [dependencies] table
        # must be reported as a violation naming the offending crate. Exercises
        # the REUSED rust_gate_harness function through this module's own
        # wrapper, never a second implementation (REQ-5).
        bad_manifest = Path(d) / "Cargo.toml"
        bad_manifest.write_text(
            '[package]\nname = "hierarchy-vor"\n\n[dependencies]\nserde = "1"\n'
        )
        dep_result = check_dependency_posture(bad_manifest)
        if dep_result.ok or "serde" not in dep_result.violations:
            failures.append(
                "dependency control did NOT report a violation for a manifest with "
                "a populated [dependencies] table"
            )

    # Six surface controls (REQ-44), one deliberately-breaching fixture per rule.
    fixture_1 = {
        "cohort.rs": (
            '#[derive(Clone)]\n'
            'pub struct VerifiedCohort {\n'
            '    definition: String,\n'
            '}\n\n'
            'impl VerifiedCohort {\n'
            '    pub fn new(definition: String) -> Self {\n'
            '        VerifiedCohort { definition }\n'
            '    }\n'
            '}\n'
        )
    }
    if not _check_handle_construction(fixture_1):
        failures.append(
            "surface control 1 (handle construction) did NOT catch a Clone-derived, "
            "publicly-constructible VerifiedCohort fixture"
        )

    fixture_2 = {
        "authoriser.rs": (
            'pub struct TrustedAuthoriserSet {\n'
            '    entries: std::collections::HashMap<String, Vec<u8>>,\n'
            '}\n\n'
            'impl TrustedAuthoriserSet {\n'
            '    pub fn from_bytes(entries: &[(&str, &[u8])]) -> Self {\n'
            '        TrustedAuthoriserSet { entries: Default::default() }\n'
            '    }\n'
            '}\n\n'
            'pub fn only_one_loader(x: &str) -> Result<TrustedAuthoriserSet, String> {\n'
            '    unimplemented!()\n'
            '}\n'
        )
    }
    if not _check_authoriser_set_surface(fixture_2):
        failures.append(
            "surface control 2 (authoriser set surface) did NOT catch a fixture "
            "with a public from-bytes constructor and only one public loader"
        )

    fixture_3 = {
        "authoriser.rs": 'const REAL_SECRET_TOKEN: &str = "0123456789abcdef0123456789ab";\n'
    }
    if not _check_no_secret_literals(fixture_3):
        failures.append(
            "surface control 3 (secret literal) did NOT catch a const identifier "
            "ending in TOKEN bound directly to a string literal"
        )
    # Control the control: the real crate's own SECRET_PATH_ENV_VAR (an env-var
    # NAME, not a secret) must NOT be flagged, or rule 3 is just a blacklist that
    # would also break the real, clean crate.
    clean_fixture_3 = {
        "authoriser.rs": 'pub const SECRET_PATH_ENV_VAR: &str = "HEIMDALL_COHORT_SECRET_FILE";\n'
    }
    if _check_no_secret_literals(clean_fixture_3):
        failures.append(
            "surface control 3 (secret literal) WRONGLY flagged SECRET_PATH_ENV_VAR "
            "(an env-var name, not a secret literal) -- the real crate would fail "
            "this check for no reason"
        )

    fixture_4 = {
        "cohort.rs": (
            'fn rank(ceiling: &str) -> usize {\n'
            '    TRUST_ORDER.iter().position(|c| c == &ceiling).unwrap()\n'
            '}\n'
        )
    }
    if not _check_no_trust_ordering(fixture_4):
        failures.append(
            "surface control 4 (trust ordering) did NOT catch a fixture ranking the "
            "ceiling against TRUST_ORDER"
        )

    fixture_5 = {"cohort.rs": 'pub const COHORT_ID: &str = "heimdall,dev";\n'}
    if not _check_hardcoded_field_values_clean(fixture_5):
        failures.append(
            "surface control 5 (hardcoded field content) did NOT catch a COHORT_ID "
            "value containing a comma"
        )

    fixture_6 = {
        "other.rs": '#[cfg(test)]\n#[path = "../unit_tests/sneaky.rs"]\nmod sneaky;\n'
    }
    if not _check_test_isolation(fixture_6):
        failures.append(
            "surface control 6 (test isolation) did NOT catch a unit-test #[path] "
            "attachment declared outside lib.rs"
        )

    # AC-38's broader grep control: a stray `#[test]` fn (no `#[path = ...]`
    # attribute at all) landing directly in a src/ file must still be caught, since
    # rule 6's original `#[path = ...]`-only scan above would miss it entirely.
    fixture_6b = {
        "authoriser.rs": (
            "fn helper() {}\n\n#[test]\nfn a_stray_unit_test_in_src() {\n    assert!(true);\n}\n"
        )
    }
    if not _check_test_isolation(fixture_6b):
        failures.append(
            "surface control 6b (AC-38 broad test-isolation grep) did NOT catch a "
            "stray #[test] function with no #[path = ...] attribute landing "
            "directly in a src/ file"
        )

    # Control the control: the real, clean lib.rs's own permitted
    # `#[cfg(test)] #[path = "../unit_tests/..."] mod ...;` declaration block must
    # NOT be flagged, or the broader AC-38 check would also break the real crate.
    clean_fixture_6 = {
        "lib.rs": (
            '#[cfg(test)]\n#[path = "../unit_tests/loader_failclosed.rs"]\n'
            "mod loader_failclosed;\n"
        )
    }
    if _check_test_isolation(clean_fixture_6):
        failures.append(
            "surface control 6 (AC-38 broad test-isolation grep) WRONGLY flagged "
            "lib.rs's own permitted #[cfg(test)] #[path = ...] mod ...; "
            "declaration block -- the real crate would fail this check for no "
            "reason"
        )

    return failures


def main() -> int:
    print("Rust cohort drift detector (D110): translation fidelity and surface shape")
    print("against the Python reference and REQ-42's mechanical rules, not invariant")
    print("3.6 and not whether anything actually calls this crate outside a test (see")
    print("ontology.tests.vor_invocation_harness for that, separately governed).")
    print()

    control_failures = control_check()
    if control_failures:
        print("NEGATIVE CONTROL FAILED (refusing to trust the checks below):")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    print("  [PASS] negative controls: a wrong digest is reported as drift, a "
          "populated [dependencies] table is reported as a violation, and each of "
          "the six surface checks bites its own breaching fixture without flagging "
          "the real crate's own clean constructs.")
    print()

    digest_result = check_digests()
    print(f"  [{'PASS' if digest_result.ok else 'CRITICAL'}] digest check: {digest_result.detail}")
    if not digest_result.ok:
        return 1  # fatal regardless of toolchain presence

    dep_result = check_dependency_posture()
    print(f"  [{'PASS' if dep_result.ok else 'CRITICAL'}] dependency posture: {dep_result.detail}")
    if not dep_result.ok:
        return 1  # fatal regardless of toolchain presence

    surface_result = check_surface()
    if surface_result.ok:
        print(f"  [PASS] surface checks: {surface_result.detail}")
    else:
        print(f"  [CRITICAL] surface checks: {surface_result.detail}")
        for v in surface_result.violations:
            print(f"    - {v}")
        return 1  # fatal regardless of toolchain presence

    print()
    if not toolchain_present():
        print("  [SKIP] no Rust toolchain found on this machine (cargo not on PATH).")
        print("  The digest, dependency and surface checks above already ran and")
        print("  passed; only the Rust suite is skipped.")
        print("  [GAP] REQ-36 real-cohort verification marker: SKIPPED (no toolchain, ")
        print("  so the suite that would print it never ran). This is a named gap, ")
        print("  not a pass.")
        return 0

    ok, marker, detail = run_rust_suite()
    print(f"  [{'PASS' if ok else 'CRITICAL'}] Rust suite: {detail}")
    if marker == MARKER_VERIFIED:
        print(f"  [PASS] REQ-36 real-cohort verification marker: {marker} (the "
              f"secret was provisioned and the real, committed attestation "
              f"verified against it).")
    elif marker == MARKER_NOT_EXERCISED:
        print(f"  [GAP] REQ-36 real-cohort verification marker: {marker} (the "
              f"secret was not provisioned on this machine, so the real cohort's "
              f"own attestation was not exercised this run; this is a named gap, "
              f"not a pass -- mechanism parity is still proven by the vector "
              f"replay under the fixture secret).")
    else:
        print("  [GAP] REQ-36 real-cohort verification marker: NEITHER marker was "
              "found in the captured Rust suite output. Reported as a gap, never "
              "as a pass.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
