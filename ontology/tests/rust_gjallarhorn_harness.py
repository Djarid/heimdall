# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Jason Huxley and the Heimdall authors.

"""Gjallarhorn crate posture detector (`.opencode/plans/gjallarhorn-build-spec.md`
REQ-55): is `crates/gjallarhorn/` dependency-clean, free of every forbidden
import REQ-6 names, honest about `EventType` never being forgeable through a
public constructor (REQ-11), isolated between test and implementation code
(REQ-52), honest about the DD's own untestable first-named load-bearing
property (REQ-47), and passing its own Rust suite, on
`rust_promotion_gate_harness.py`'s and `rust_cohort_harness.py`'s exact
shape (standalone sub-harness, mandatory negative controls first, then each
check in a fixed order, the Rust suite last, skipping LOUDLY only when no
toolchain is present).

Run from the repo root:

    python -m ontology.tests.rust_gjallarhorn_harness

REQ-55's six checks, in this fixed order, each with its own mandatory
negative control that runs first (`control_check`, following
`promotion_invocation_harness.py`'s and `rust_promotion_gate_harness.py`'s
own "every control runs before any real check is trusted" discipline):

  a. Dependency posture by import (REQ-2). REUSES (never reimplements)
     `ontology.tests.rust_gate_harness.check_dependency_posture`, called with
     the STRICT EMPTY default (no `permitted_path_dependencies` argument),
     against `crates/gjallarhorn/Cargo.toml`. `crates/gjallarhorn/` carries no
     path dependency of any kind (OR-3, GJ-B-3), so it is one of the crates
     that keeps the function's own original, strict behaviour byte for byte,
     on the same footing `rust_actuator_harness.check_ac51_cross_harness_regression`
     already documents for `hierarchy-vor` and `actuator-git`.
  b. The forbidden-import text scan (REQ-6). No file under
     `crates/gjallarhorn/src/` may name `std::net`, `TcpStream`,
     `TcpListener`, `UdpSocket`, `std::process`, `Command`, `std::env`,
     `var(`, `std::fs`, `File::`, `read_to_string`, `std::time`,
     `SystemTime`, `Instant` or `UNIX_EPOCH`. Comments are stripped first
     (`_strip_line_comments`, on `rust_gateway_harness.check_no_std_process`'s
     own precedent), because `delivery.rs`'s own module doc comment names
     `std::net` in PROSE, stating that a real outward transport is a named
     follow-on and explicitly out of scope for this build (OR-4): that
     sentence is not a violation and must not be flagged as one.
  c. The `EventType`-not-an-input public-surface scan (REQ-11). See this
     module's own docstring section below, "A judgement call on REQ-11's
     scope, stated rather than guessed", for what this check actually
     covers and why.
  d. The test/code isolation grep (REQ-52). The ONLY test construct
     permitted anywhere under `crates/gjallarhorn/src/` is the
     `#[cfg(test)] #[path = "../unit_tests/<name>.rs"] mod <name>;`
     declaration in `lib.rs`. No `#[test]`, no `mod tests`, no fixture and
     no double anywhere else in `src/`.
  e. The REQ-47 absent-counterparty marker. Printed LIVE by scanning this
     workspace's own `crates/` directory for the absence of any crate named
     `fenrir` or `huginn` (by directory name or by manifest `package.name`),
     never a hardcoded print statement. Names both counterparties
     explicitly and states that the design document's own first-named
     load-bearing test (containment fires without alert delivery) is NOT
     RUN, because neither counterparty exists in this workspace. Stops
     printing the moment both counterparties exist (AC-47's own control:
     a scratch tree carrying both crates must NOT print the marker).
  f. The Rust suite (`cargo test -p gjallarhorn`), invoked LAST, on
     `rust_promotion_gate_harness.py`'s own precedent: skips LOUDLY only
     when no Rust toolchain is present (checks a to e above already ran and
     already passed by that point); a present toolchain whose test run
     returns non-zero is always FATAL, never laundered into a skip.

A judgement call on REQ-11's scope, stated rather than guessed. REQ-11's own
text reads, literally, "`EventType` must not appear as an input parameter...
on ANY public function, method or associated function in the crate." Read
with maximum literalism, that would also flag `crate::routing::route_for`,
`crate::channel::admission_for` and `crate::aggregate::correlation_key_for`,
all three of which are genuinely `pub fn`, all three of which genuinely take
an `EventType` parameter, and all three of which REQ-14, REQ-18, REQ-25 and
REQ-31 separately REQUIRE to exist with exactly that shape: `route_for`
resolves a route from a type alone, `admission_for` decides a channel from a
type and a provenance, and `correlation_key_for` derives a collapsing key
from a type and a provenance. None of those three can construct a
`GjallarhornEvent`; none of them touches `GjallarhornEvent::new` (which stays
`pub(crate)`, confirmed separately below); and none of them lets an outside
caller mint an event of a chosen type, which is GJ-B-1's and REQ-11's own
stated purpose ("no public constructor of `GjallarhornEvent` that takes an
event type... which route an event obtains is fixed by which minting
function the caller called"). `crates/gjallarhorn/tests/public_surface.rs`'s
own module doc comment explicitly defers "AC-11's mechanical scan half" to
this module, without itself resolving the scope question either. Taking
REQ-11 at its most literal would therefore fail a crate that is otherwise
fully compliant with REQ-14, REQ-18, REQ-25 and REQ-31, which cannot be the
intended reading: a requirement cannot coherently forbid what three sibling
requirements separately mandate. This module resolves the tension by scoping
the mechanical scan to the construction surface REQ-11's own second sentence
names: (1) `GjallarhornEvent::new` must be `pub(crate)`, never `pub`, checked
directly against `types.rs`'s own `impl GjallarhornEvent` block; and (2) no
public function anywhere in the crate whose return type mentions
`GjallarhornEvent` (bare, or wrapped in `Result`/`Option`/`Vec`) may take
`EventType` as an input parameter. This is the narrower, purpose-consistent
reading that closes GJ-B-1's actual residual (an outside caller choosing an
arbitrary type and route combination by constructing an event directly)
without contradicting REQ-14/REQ-18/REQ-25/REQ-31's own separate mandates.
Flagged here for review rather than resolved silently.

What this harness does NOT prove. It says nothing about invariant 3.6's
live-invocation status, which `ontology.tests.gjallarhorn_invocation_harness`
governs separately (REQ-44 to REQ-46), and it is not a functional test of
`raise`'s own sequencing (the Rust suite it invokes in its own step f covers
that).
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from . import rust_gate_harness

REPO_ROOT = Path(__file__).resolve().parents[2]

CRATE_DIR = REPO_ROOT / "crates" / "gjallarhorn"
CRATE_MANIFEST = CRATE_DIR / "Cargo.toml"
SRC_DIR = CRATE_DIR / "src"
TYPES_RS = SRC_DIR / "types.rs"

CRATES_DIR = REPO_ROOT / "crates"

# REQ-6's own token list, verbatim and in the spec's own order.
_FORBIDDEN_IMPORT_TOKENS: tuple[str, ...] = (
    "std::net", "TcpStream", "TcpListener", "UdpSocket",
    "std::process", "Command", "std::env", "var(",
    "std::fs", "File::", "read_to_string",
    "std::time", "SystemTime", "Instant", "UNIX_EPOCH",
)

# REQ-47's two absent counterparties, named explicitly (never abbreviated,
# so a future session reading only the printed banner still learns which
# two components are missing).
_ABSENT_COUNTERPARTY_NAMES: tuple[str, ...] = ("fenrir", "huginn")

MARKER_ABSENT_COUNTERPARTY = "GJALLARHORN-REAL-COUNTERPARTY-NOT-EXERCISED"
MARKER_COUNTERPARTY_PRESENT = "GJALLARHORN-REAL-COUNTERPARTY-PRESENT"


def _strip_line_comments(src: str) -> str:
    """Mirrors `rust_gateway_harness._strip_line_comments`'s own reasoning
    (duplicated, not imported, on this repository's own convention of
    duplicating a short, test-only helper across sibling harnesses): a `//`
    also blanks a `//!` doc comment, since `//!` begins with the same two
    characters, which is exactly what check (b) needs to avoid flagging
    `delivery.rs`'s own prose mention of `std::net`."""
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


# ---------------------------------------------------------------------------------
# Check a: dependency posture by import (REQ-2). REUSED, never reimplemented.
# ---------------------------------------------------------------------------------


def check_dependency_posture(manifest_path: Path = CRATE_MANIFEST):
    """REQ-2, REQ-55 step a: `crates/gjallarhorn/`'s manifest carries no path
    dependency, no registry dependency, no git dependency and no optional
    dependency of any kind, checked with `rust_gate_harness.check_dependency_posture`'s
    own STRICT EMPTY default (no `permitted_path_dependencies` argument): this
    crate never widens that function's default, on the same footing
    `hierarchy-vor` and `actuator-git` already keep it strict (REQ-2, GJ-B-3)."""
    return rust_gate_harness.check_dependency_posture(manifest_path)


# ---------------------------------------------------------------------------------
# Check b: the forbidden-import text scan (REQ-6).
# ---------------------------------------------------------------------------------

_FORBIDDEN_IMPORT_RE = re.compile(
    "|".join(re.escape(tok) for tok in _FORBIDDEN_IMPORT_TOKENS)
)


def _check_forbidden_imports_over_files(files: dict[str, str]) -> list[str]:
    violations: list[str] = []
    for fname, raw_src in files.items():
        src = _strip_line_comments(raw_src)
        for m in _FORBIDDEN_IMPORT_RE.finditer(src):
            lineno = src.count("\n", 0, m.start()) + 1
            violations.append(
                f"{fname}:{lineno}: found forbidden token {m.group(0)!r} (REQ-6: "
                f"the crate reads no network, spawns no process, reads no "
                f"environment variable, reads no file and reads no clock)"
            )
    return violations


def check_forbidden_imports(src_dir: Path = SRC_DIR) -> CheckResult:
    """REQ-6, REQ-55 step b. A text scan, comments stripped first (see the
    module docstring for why: `delivery.rs`'s own doc comment names
    `std::net` in prose, as a named, out-of-scope follow-on, and that
    sentence is not a violation)."""
    files = _load_rust_files(src_dir)
    if not files:
        return CheckResult(ok=False, detail=f"no .rs files found under {src_dir}")
    violations = _check_forbidden_imports_over_files(files)
    if violations:
        return CheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return CheckResult(
        ok=True,
        detail="none of REQ-6's forbidden tokens appear outside a comment under "
               "crates/gjallarhorn/src/.",
    )


# ---------------------------------------------------------------------------------
# Check c: the EventType-not-an-input public-surface scan (REQ-11). See the
# module docstring's "A judgement call on REQ-11's scope" section for the
# scoping decision this check implements.
# ---------------------------------------------------------------------------------

_PUB_FN_HEADER_RE = re.compile(
    r"pub fn (\w+)\s*\(([^)]*)\)\s*(?:->\s*([^{;]+))?\s*[{;]"
)


def _impl_block_body(src: str, type_name: str) -> "str | None":
    """The body text of the first `impl (<...>)? TypeName { ... }` block
    (never a trait impl), found by brace-depth matching, on
    `rust_cohort_harness._impl_blocks`'s own technique (duplicated here, not
    imported, following this repository's own convention for a short,
    test-only helper)."""
    pattern = re.compile(rf"impl(?:<[^>]*>)?\s+{re.escape(type_name)}\b(?:<[^>]*>)?\s*\{{")
    m = pattern.search(src)
    if not m:
        return None
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
    return src[start + 1 : i]


def _check_new_is_pub_crate_only(files: dict[str, str]) -> list[str]:
    """REQ-11's second sentence: `GjallarhornEvent::new` must be `pub(crate)`,
    never `pub`. Scoped to `impl GjallarhornEvent`'s own body so an unrelated
    `pub fn new` on some other type is never mistaken for this one."""
    violations: list[str] = []
    for fname, raw_src in files.items():
        src = _strip_line_comments(raw_src)
        body = _impl_block_body(src, "GjallarhornEvent")
        if body is None:
            continue
        if re.search(r"\bpub fn new\s*\(", body):
            violations.append(
                f"{fname}: `impl GjallarhornEvent` declares `pub fn new(...)` "
                f"(REQ-11 requires GjallarhornEvent::new to be pub(crate), never pub)"
            )
        if not re.search(r"pub\(crate\)\s+fn new\s*\(", body):
            violations.append(
                f"{fname}: `impl GjallarhornEvent` does not declare a "
                f"`pub(crate) fn new(...)` (REQ-11's one construction site "
                f"must exist and must be pub(crate))"
            )
    return violations


def _check_no_public_gjallarhornevent_constructor_taking_event_type(
    files: dict[str, str],
) -> list[str]:
    """REQ-11's own stated purpose: no public function anywhere in the crate
    whose return type mentions `GjallarhornEvent` (bare, or wrapped in
    `Result`/`Option`/`Vec`) may take `EventType` as an input parameter.
    Scoped this way (rather than to every `pub fn` in the crate, full stop)
    for the reason stated at length in the module docstring: `route_for`,
    `admission_for` and `correlation_key_for` are all genuinely `pub fn`,
    all genuinely take an `EventType`, and none of them can construct a
    `GjallarhornEvent`, so none of them is a REQ-11 violation."""
    violations: list[str] = []
    for fname, raw_src in files.items():
        src = _strip_line_comments(raw_src)
        for m in _PUB_FN_HEADER_RE.finditer(src):
            fn_name, params, ret = m.group(1), m.group(2), (m.group(3) or "")
            if "GjallarhornEvent" in ret and re.search(r"\bEventType\b", params):
                lineno = src.count("\n", 0, m.start()) + 1
                violations.append(
                    f"{fname}:{lineno}: `pub fn {fn_name}` returns a type "
                    f"mentioning GjallarhornEvent and takes EventType as an "
                    f"input parameter (REQ-11 forbids a public constructor of "
                    f"GjallarhornEvent that takes an event type)"
                )
    return violations


def check_event_type_not_an_input(src_dir: Path = SRC_DIR) -> CheckResult:
    """REQ-11, REQ-55 step c."""
    files = _load_rust_files(src_dir)
    if not files:
        return CheckResult(ok=False, detail=f"no .rs files found under {src_dir}")
    violations = _check_new_is_pub_crate_only(files)
    violations += _check_no_public_gjallarhornevent_constructor_taking_event_type(files)
    if violations:
        return CheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return CheckResult(
        ok=True,
        detail="GjallarhornEvent::new is pub(crate) only, and no public function "
               "returning a type mentioning GjallarhornEvent takes EventType as an "
               "input parameter anywhere under crates/gjallarhorn/src/.",
    )


# ---------------------------------------------------------------------------------
# Check d: the test/code isolation grep (REQ-52).
# ---------------------------------------------------------------------------------

_TEST_MARKER_RE = re.compile(r"#\[test\]|mod tests|#\[cfg\(test\)\]")


def _check_test_isolation_over_files(files: dict[str, str]) -> list[str]:
    violations: list[str] = []
    for fname, raw_src in files.items():
        src = _strip_line_comments(raw_src)
        for m in _TEST_MARKER_RE.finditer(src):
            lineno = src.count("\n", 0, m.start()) + 1
            if fname != "lib.rs":
                violations.append(
                    f"{fname}:{lineno}: found `{m.group(0)}` outside lib.rs (REQ-52 "
                    f"permits a test-related construct under src/ only as lib.rs's own "
                    f"#[cfg(test)] #[path = ...] mod ...; declaration)"
                )
                continue
            if m.group(0) != "#[cfg(test)]":
                violations.append(
                    f"{fname}:{lineno}: found `{m.group(0)}` in lib.rs (REQ-52 "
                    f"permits only `#[cfg(test)]` declaration lines here)"
                )
                continue
            rest = src[m.end():]
            if not re.match(
                r'\s*\n\s*#\[path\s*=\s*"\.\./unit_tests/[^"]+"\]\s*\n\s*mod\s+\w+\s*;',
                rest,
            ):
                violations.append(
                    f"{fname}:{lineno}: found `#[cfg(test)]` in lib.rs not immediately "
                    f"followed by a `#[path = \"../unit_tests/...\"] mod ...;` declaration "
                    f"(REQ-52)"
                )
    return violations


def check_test_isolation(src_dir: Path = SRC_DIR) -> CheckResult:
    """REQ-52, REQ-55 step d."""
    files = _load_rust_files(src_dir)
    if not files:
        return CheckResult(ok=False, detail=f"no .rs files found under {src_dir}")
    violations = _check_test_isolation_over_files(files)
    if violations:
        return CheckResult(ok=False, violations=violations, detail=f"{len(violations)} violation(s)")
    return CheckResult(
        ok=True,
        detail="the only test-related lines under crates/gjallarhorn/src/ are lib.rs's "
               "own #[cfg(test)] #[path = ...] declarations.",
    )


# ---------------------------------------------------------------------------------
# Check e: the REQ-47 absent-counterparty marker. A LIVE detection, never a
# hardcoded print statement: scans the workspace's own crates/ directory for
# the absence of any crate named fenrir or huginn, by directory name or by
# manifest package.name.
# ---------------------------------------------------------------------------------


def _crate_names_present(crates_dir: Path) -> set[str]:
    """Every crate name found under `crates_dir`: the directory's own leaf
    name and, when a manifest exists and can be parsed, its
    `[package].name` value too, so a rename that keeps the old directory
    name (or vice versa) is still caught either way. Lower-cased, since a
    crate name is checked case-insensitively here (REQ-47 names Fenrir and
    Huginn with their natural capitalisation; a Rust crate name convention
    would use lower-case-with-hyphens)."""
    names: set[str] = set()
    if not crates_dir.exists():
        return names
    for entry in sorted(crates_dir.iterdir()):
        if not entry.is_dir():
            continue
        names.add(entry.name.lower())
        manifest = entry / "Cargo.toml"
        if manifest.exists():
            try:
                data = tomllib.loads(manifest.read_text(encoding="utf-8"))
                pkg_name = (data.get("package", {}) or {}).get("name")
                if isinstance(pkg_name, str):
                    names.add(pkg_name.lower())
            except Exception:  # noqa: BLE001 - a malformed manifest names nothing extra
                pass
    return names


def absent_counterparties(crates_dir: Path = CRATES_DIR) -> list[str]:
    """The subset of `_ABSENT_COUNTERPARTY_NAMES` that is genuinely absent
    from `crates_dir`, live, never hardcoded. An empty return means every
    named counterparty now exists somewhere under `crates_dir`."""
    present = _crate_names_present(crates_dir)
    return [name for name in _ABSENT_COUNTERPARTY_NAMES if name not in present]


def print_absent_counterparty_marker(crates_dir: Path = CRATES_DIR) -> None:
    """REQ-47, REQ-55 step e. Prints, LIVE, whether Fenrir and/or Huginn
    exist anywhere under `crates_dir`. When both are absent (today's real
    state), prints `MARKER_ABSENT_COUNTERPARTY` naming both explicitly and
    stating that the design document's own first-named load-bearing test
    (containment fires without alert delivery) is NOT RUN. When both exist,
    prints `MARKER_COUNTERPARTY_PRESENT` instead and prints NOTHING
    resembling the absent marker, which is what AC-47's own control checks:
    the detection must be live, not hardcoded, so it must stop printing the
    absent marker the moment both counterparties exist."""
    missing = absent_counterparties(crates_dir)
    if missing:
        missing_titled = [name.title() for name in missing]
        print(
            f"  [GAP] {MARKER_ABSENT_COUNTERPARTY}: {' and '.join(missing_titled)} "
            f"{'does' if len(missing_titled) == 1 else 'do'} not exist anywhere under "
            f"{crates_dir}. The design document's own first-named load-bearing test "
            f"(containment fires without alert delivery) is NOT RUN, because it needs "
            f"a real Fenrir and a real Huginn as counterparties and this workspace has "
            f"neither. This is a named gap, never a silent pass, and it is detected "
            f"live: it stops printing the moment both counterparties exist."
        )
    else:
        print(
            f"  [PASS] {MARKER_COUNTERPARTY_PRESENT}: both Fenrir and Huginn now exist "
            f"under {crates_dir}. The absent-counterparty gap above no longer applies "
            f"(this branch is exercised today only by the negative control, on a "
            f"synthetic scratch tree, never against this repository's own working tree)."
        )


# ---------------------------------------------------------------------------------
# Check f: the Rust suite (REUSED helpers, never reimplemented).
# ---------------------------------------------------------------------------------


def toolchain_present() -> bool:
    return rust_gate_harness.toolchain_present()


def run_rust_suite(crate_dir: Path = CRATE_DIR) -> tuple[bool, str]:
    return rust_gate_harness.run_rust_suite(crate_dir)


# ---------------------------------------------------------------------------------
# Mandatory negative controls (REQ-55, invariant 3.10, D10), run FIRST, on
# `rust_promotion_gate_harness.py`'s own control_check shape: one function
# covering every check above, each control proven to bite on a disposable
# scratch fixture before any real check's result is trusted.
# ---------------------------------------------------------------------------------


def control_check() -> list[str]:
    failures: list[str] = []

    with tempfile.TemporaryDirectory() as d:
        # Control a (REQ-2): a manifest with a populated [dependencies]
        # table must be reported as a violation under the strict default.
        bad_manifest = Path(d) / "Cargo.toml"
        bad_manifest.write_text(
            '[package]\nname = "gjallarhorn"\n\n[dependencies]\nserde = "1"\n'
        )
        dep_result = check_dependency_posture(bad_manifest)
        if dep_result.ok or "serde" not in dep_result.violations:
            failures.append(
                "check a control did NOT report a violation for a manifest with a "
                "populated [dependencies] table"
            )

        clean_manifest = Path(d) / "Cargo-clean.toml"
        clean_manifest.write_text('[package]\nname = "gjallarhorn"\n\n[dependencies]\n')
        clean_dep_result = check_dependency_posture(clean_manifest)
        if not clean_dep_result.ok:
            failures.append(
                "check a control WRONGLY flagged a clean manifest with an empty "
                "[dependencies] table"
            )

        # Control b (REQ-6): each forbidden token in turn, planted into a
        # disposable scratch copy, must be caught; a comment-only mention
        # must NOT be caught.
        for token in _FORBIDDEN_IMPORT_TOKENS:
            fixture_dir = Path(d) / f"src_forbidden_{abs(hash(token))}"
            fixture_dir.mkdir()
            (fixture_dir / "probe.rs").write_text(f"fn f() {{ let _ = {token}; }}\n")
            result = check_forbidden_imports(fixture_dir)
            if result.ok:
                failures.append(
                    f"check b control did NOT catch a planted occurrence of "
                    f"{token!r}"
                )

        clean_forbidden_dir = Path(d) / "src_forbidden_clean"
        clean_forbidden_dir.mkdir()
        (clean_forbidden_dir / "probe.rs").write_text(
            "// this module never touches std::net (REQ-6, prose only)\n"
            "fn f() {}\n"
        )
        clean_forbidden_result = check_forbidden_imports(clean_forbidden_dir)
        if not clean_forbidden_result.ok:
            failures.append(
                "check b control WRONGLY flagged a comment-only mention of a "
                "forbidden token"
            )

        # Control c (REQ-11): a violating public constructor (returns a type
        # mentioning GjallarhornEvent, takes EventType) must be caught; a
        # clean fixture on route_for's own shape (pub fn taking EventType,
        # returning something OTHER than GjallarhornEvent) must NOT be
        # caught; and a pub fn new that is NOT pub(crate) must be caught.
        bad_ctor_dir = Path(d) / "src_bad_ctor"
        bad_ctor_dir.mkdir()
        (bad_ctor_dir / "probe.rs").write_text(
            "pub fn mint_arbitrary(\n"
            "    event_type: EventType,\n"
            "    source: SourceProvenance,\n"
            ") -> Result<GjallarhornEvent, MintRefusal> {\n"
            "    unimplemented!()\n"
            "}\n"
        )
        bad_ctor_result = check_event_type_not_an_input(bad_ctor_dir)
        if bad_ctor_result.ok:
            failures.append(
                "check c control did NOT catch a planted public function returning "
                "a GjallarhornEvent-mentioning type while taking EventType as an "
                "input parameter"
            )

        bad_new_dir = Path(d) / "src_bad_new"
        bad_new_dir.mkdir()
        (bad_new_dir / "probe.rs").write_text(
            "impl GjallarhornEvent {\n"
            "    pub fn new(event_type: EventType) -> Self {\n"
            "        unimplemented!()\n"
            "    }\n"
            "}\n"
        )
        bad_new_result = check_event_type_not_an_input(bad_new_dir)
        if bad_new_result.ok:
            failures.append(
                "check c control did NOT catch a planted `pub fn new` on "
                "GjallarhornEvent (REQ-11 requires pub(crate), never pub)"
            )

        clean_ctor_dir = Path(d) / "src_clean_ctor"
        clean_ctor_dir.mkdir()
        (clean_ctor_dir / "probe.rs").write_text(
            "pub fn route_for(event_type: EventType) -> Route {\n"
            "    unimplemented!()\n"
            "}\n\n"
            "impl GjallarhornEvent {\n"
            "    pub(crate) fn new(event_type: EventType) -> Self {\n"
            "        unimplemented!()\n"
            "    }\n"
            "}\n"
        )
        clean_ctor_result = check_event_type_not_an_input(clean_ctor_dir)
        if not clean_ctor_result.ok:
            failures.append(
                "check c control WRONGLY flagged a route_for-shaped pub fn (takes "
                "EventType, returns something other than GjallarhornEvent) and a "
                "clean pub(crate) fn new: "
                f"{clean_ctor_result.violations}"
            )

        # Control d (REQ-52): a stray #[test] in a non-lib.rs file must be
        # caught; a clean lib.rs declaration block must NOT be caught.
        bad_iso_dir = Path(d) / "src_bad_iso"
        bad_iso_dir.mkdir()
        (bad_iso_dir / "sneaky.rs").write_text("#[test]\nfn a() {}\n")
        bad_iso_result = check_test_isolation(bad_iso_dir)
        if bad_iso_result.ok:
            failures.append("check d control did NOT catch a stray #[test] fn in src/")

        clean_iso_dir = Path(d) / "src_clean_iso"
        clean_iso_dir.mkdir()
        (clean_iso_dir / "lib.rs").write_text(
            '#[cfg(test)]\n#[path = "../unit_tests/event_and_mint.rs"]\nmod event_and_mint;\n'
        )
        clean_iso_result = check_test_isolation(clean_iso_dir)
        if not clean_iso_result.ok:
            failures.append(
                "check d control WRONGLY flagged lib.rs's own permitted #[cfg(test)] "
                "#[path = ...] mod ...; declaration block"
            )

        # Control e (REQ-47): a scratch crates/ tree carrying BOTH
        # counterparties must report zero absent counterparties, proving the
        # detection is live rather than hardcoded (AC-47's own control).
        present_crates_dir = Path(d) / "crates_both_present"
        present_crates_dir.mkdir()
        for name in _ABSENT_COUNTERPARTY_NAMES:
            crate_dir = present_crates_dir / name
            crate_dir.mkdir()
            (crate_dir / "Cargo.toml").write_text(f'[package]\nname = "{name}"\n')
        if absent_counterparties(present_crates_dir):
            failures.append(
                "check e control did NOT clear both counterparties from a scratch "
                "crates/ tree that genuinely carries a fenrir/ and a huginn/ crate "
                "(AC-47's own live-detection control)"
            )

        # Control e, second half: a scratch crates/ tree carrying NEITHER
        # counterparty must report both as absent (today's real state,
        # reproduced on a scratch tree so the control is self-contained).
        absent_crates_dir = Path(d) / "crates_both_absent"
        absent_crates_dir.mkdir()
        (absent_crates_dir / "some-other-crate").mkdir()
        (absent_crates_dir / "some-other-crate" / "Cargo.toml").write_text(
            '[package]\nname = "some-other-crate"\n'
        )
        missing = absent_counterparties(absent_crates_dir)
        if set(missing) != set(_ABSENT_COUNTERPARTY_NAMES):
            failures.append(
                "check e control did NOT report both fenrir and huginn as absent "
                "from a scratch crates/ tree carrying neither"
            )

    return failures


def main() -> int:
    print("Gjallarhorn posture detector (REQ-55): dependency posture, forbidden-import")
    print("scan, EventType-not-an-input scan, test/code isolation, the absent-")
    print("counterparty marker and the Rust suite. Not invariant 3.6's live-invocation")
    print("status (see ontology.tests.gjallarhorn_invocation_harness for that).")
    print()

    control_failures = control_check()
    if control_failures:
        print("NEGATIVE CONTROL FAILED (refusing to trust the checks below):")
        for cf in control_failures:
            print(f"  [CRITICAL] {cf}")
        return 1
    print("  [PASS] negative controls: a populated [dependencies] table, each of "
          "REQ-6's forbidden tokens, a REQ-11-violating public constructor and a "
          "non-pub(crate) `new`, a stray #[test] in src/, and both directions of "
          "the absent-counterparty marker are all caught or correctly cleared, "
          "and no clean fixture is wrongly flagged.")
    print()

    # Check a: dependency posture.
    dep_result = check_dependency_posture()
    print(f"  [{'PASS' if dep_result.ok else 'CRITICAL'}] (a) dependency posture: {dep_result.detail}")
    if not dep_result.ok:
        for v in dep_result.violations:
            print(f"    - {v}")
        return 1

    # Check b: forbidden-import text scan.
    forbidden_result = check_forbidden_imports()
    print(f"  [{'PASS' if forbidden_result.ok else 'CRITICAL'}] (b) forbidden-import scan: "
          f"{forbidden_result.detail}")
    if not forbidden_result.ok:
        for v in forbidden_result.violations:
            print(f"    - {v}")
        return 1

    # Check c: EventType-not-an-input public-surface scan.
    ctor_result = check_event_type_not_an_input()
    print(f"  [{'PASS' if ctor_result.ok else 'CRITICAL'}] (c) EventType-not-an-input scan: "
          f"{ctor_result.detail}")
    if not ctor_result.ok:
        for v in ctor_result.violations:
            print(f"    - {v}")
        return 1

    # Check d: test/code isolation.
    iso_result = check_test_isolation()
    print(f"  [{'PASS' if iso_result.ok else 'CRITICAL'}] (d) test/code isolation: "
          f"{iso_result.detail}")
    if not iso_result.ok:
        for v in iso_result.violations:
            print(f"    - {v}")
        return 1

    # Check e: the absent-counterparty marker. Always a [GAP] or a [PASS],
    # never fatal on its own: REQ-47 requires it to be printed honestly, not
    # to be treated as a suite failure.
    print("  (e) absent-counterparty marker:")
    print_absent_counterparty_marker()

    print()
    if not toolchain_present():
        print("  [SKIP] no Rust toolchain found on this machine (cargo not on PATH).")
        print("  Checks (a) to (e) above already ran and passed; only the Rust suite")
        print("  is skipped. This is not a failure.")
        return 0

    ok, detail = run_rust_suite()
    print(f"  [{'PASS' if ok else 'CRITICAL'}] (f) Rust suite: {detail}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
