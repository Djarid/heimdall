# Rust workspace baseline

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Status:** the standing baseline the repository's first Rust crate established

---

## 1. Purpose

`crates/boundary-gjoll/` (D109) is the repository's first Rust crate, built as build-order
step one of `plans/synthesis-bootstrap.md` (D108). This document records the workspace
layout, the toolchain pin, the minimum supported Rust version (MSRV), the dependency
posture, the module-layering pattern, the test-isolation pattern and the vector-parity
mechanism it established, so steps two to seven of D108's build order inherit one set of
conventions rather than each re-deciding them. It is a cross-cutting document, not a
per-component one: see `plans/dd/index.md` section 1's cross-reference note.

## 2. Workspace layout

A single Cargo workspace at the repository root:

- `Cargo.toml`: the workspace manifest. `resolver = "3"`, one member
  (`crates/boundary-gjoll`), and a `[workspace.package]` table setting
  `edition = "2024"` and `rust-version = "1.85"`. A future crate joins this workspace as a
  new member rather than starting its own.
- `rust-toolchain.toml`: pins the toolchain (section 3). Applies repository-wide.
- `Cargo.lock`: committed, covering the dev-dependency graph of every workspace member.
- `crates/<name>/`: one directory per crate, each with its own `Cargo.toml` inheriting
  `edition` and `rust-version` from the workspace.

Rust build output is ignored by `.gitignore`; nothing under `target/` is tracked.

## 3. Toolchain pin and MSRV

`rust-toolchain.toml` pins `channel = "1.98.0"`, with `rustfmt` and `clippy` as components
and `profile = "minimal"`. This is the toolchain verified present on the build machine
(`cargo 1.98.0`, `rustc 1.98.0`), observed rather than assumed.

The workspace's `rust-version` is `1.85`, the edition-2024 floor, and is distinct from the
pinned channel: `rust-version` states the minimum a crate is written to compile against,
while the pinned channel is the version this repository's own builds and tests actually
run on. A future crate may rely on a language feature newer than 1.85 only if the workspace
`rust-version` is raised deliberately, which is a decision worth its own `DECISIONS.md` row
if it narrows what can build this repository.

## 4. Dependency posture

`boundary-gjoll`'s `[dependencies]` table is empty, and carries no `license` field (the
licence question is OPEN; see section 7). Dev-dependencies are permitted for test-only
concerns (in this crate, JSON vector parsing) and must be version-pinned exactly, not
range-pinned, so a dependency upgrade is a deliberate, reviewed edit rather than a silent
drift on the next build.

This is the Rust analogue of `ontology/nornir/symbolic_guard.py`'s structural enforcement
of invariant 3.1, and of D105 row H5: with no runtime dependency present, there is no crate
through which a model call or a network call could be reached. A mechanical check
(`ontology/tests/rust_gate_harness.py::check_dependency_posture`) asserts the
`[dependencies]` table stays empty, failing loudly if a runtime dependency is added, and
stating the dev-dependency exemption in its own output. Adding a runtime dependency to a
future crate's gate-adjacent path is a deliberate trust-boundary decision requiring its own
`DECISIONS.md` row, exactly as `ALLOWED_IMPORT_ROOTS` treats a new Python import root (D71).

Every crate root carries `#![forbid(unsafe_code)]`.

**The SHA-256-in-crate ruling (D110).** `crates/hierarchy-vor/` needed a keyed
digest over a fixed-length record and the Rust standard library carries no
SHA-256, so the empty `[dependencies]` table above forced a choice: add a
runtime dependency for the hash, or write it. The ruling is to write it, inside
the crate, in its own module, as a pure function with mandatory published
known-answer vectors (`crates/hierarchy-vor/src/sha256.rs`). The reasoning, in
descending weight: first, adding a runtime dependency to the hierarchy plane's
attestation path for a fixed, roughly 90-line, publicly specified algorithm
would itself be a trust-boundary decision needing its own `DECISIONS.md` row,
for a function whose correctness a test can answer directly; second, the risk
is bounded and mechanically checkable in a way a supply-chain risk is not,
because SHA-256 is a fixed, published function with authoritative test vectors;
third, the usual and correct warning against writing your own cryptography
applies to protocols, key handling and constant-time work, none of which a
bare hash is, and the one timing-sensitive operation this pattern needs,
comparing two hex digests, is re-expressed separately and explicitly as a
constant-time comparison, never folded into the hash module itself.

**The caveat, which must travel with the ruling and not be dropped by a future
crate that copies the pattern.** This is a hand-written hash implementation on
an authorisation path. It is verified against published vectors and against
every golden vector the re-expression it serves carries, and it is not
side-channel hardened, because a hash over a fixed-length record with a
fixed-length key has no secret-dependent control flow to leak. This ceases to
apply, and the dependency question must be reopened with its own decision row,
the moment a future crate needs HMAC proper, a real KDF or asymmetric
signatures rather than a bare fixed hash: those are exactly the protocol,
key-handling and constant-time concerns the "do not write your own crypto"
warning is actually about, and this ruling does not extend to them.

**The in-workspace path-dependency ruling (D111, HB3-3).** `crates/himinbjorg/`
needed to call both `crates/boundary-gjoll/` and `crates/hierarchy-vor/` for
real, not re-implement or vendor either, so its own `[dependencies]` table
carries exactly two entries, both path dependencies on those two in-workspace
crates, rather than staying literally empty. This does not weaken section 4's
opening rule; it makes the rule's own justification explicit rather than
leaving an empty table read as the load-bearing property when it never was
one. The load-bearing property this section exists to protect is "there is no
crate through which a model call or a network call could be reached", and an
in-workspace path dependency on a crate whose own `[dependencies]` table is
empty and which carries `#![forbid(unsafe_code)]` introduces no such
reachability: the two crates `himinbjorg` depends on are exactly as auditable
as `himinbjorg` itself, and duplicating either (to keep the referencing
crate's table literally empty) would mean maintaining a second gate or a
second cohort loader, worse on every axis than a named, reviewed dependency.
The mechanical check (`ontology/tests/rust_gate_harness.py::check_dependency_posture`)
is widened accordingly, not bypassed: it now takes an optional allowlist of
permitted in-workspace path dependency names, defaulting to an empty
`frozenset`, so the two existing strict callers (`boundary-gjoll`, checked
directly by this module; `hierarchy-vor`, checked by `rust_cohort_harness.py`)
keep their original, byte-for-byte behaviour, any `[dependencies]` entry at
all is still a violation for them, and only a caller that explicitly passes a
non-empty allowlist (`himinbjorg`'s own two names, via
`ontology/tests/rust_gateway_harness.py`) reaches the widened branch. An
unlisted name, a registry dependency, a git dependency, or a listed name whose
manifest entry is not actually shaped as a path dependency all still fail the
check. Adding a **third** kind of dependency, external or in-workspace, to any
future crate's gate-adjacent path remains a deliberate trust-boundary decision
requiring its own `DECISIONS.md` row, exactly as before this widening; only
the shape of "an in-workspace path dependency on an already-empty-table,
`unsafe`-forbidding crate" is pre-permitted, and only by explicit allowlist,
never by default.

**The out-of-tree secret convention (D110), recorded as the standing pattern for
a future crate needing similar provenance.** Where a crate's correctness
depends on a secret the source tree itself must not contain (an attestation
key, a signing key), the pattern established at `crates/hierarchy-vor/src/authoriser.rs`
is: name a **path** by an environment variable, never the secret itself, so
the secret is not inherited by every child process a later step shells out to
and does not appear in process listings or crash dumps; provide exactly two
public entry points, one reading the variable and delegating and one taking a
path directly, so a test needs no process-global mutation; refuse, fail
closed, rather than default, on every one of: the variable absent or empty,
the path missing or not a regular file, the path resolving inside the
repository working tree (a development-time guard, not a deployment control,
and stated as such in the check's own doc comment), the file readable by group
or other on a Unix target, the target providing no Unix permission metadata at
all (refused, not silently skipped), and the secret too short or entirely
whitespace after stripping exactly one trailing line ending. A future crate
adopting this pattern inherits its named residuals rather than needing to
rediscover them: it does not defend against a compromised build (the deployed
binary is not the source tree), the in-tree check is compile-time-derived and
vacuous across machines, it stays a keyed digest rather than a signature unless
paired with real asymmetric signing, and it performs no zeroisation, because
zeroisation a compiler cannot elide needs either `unsafe` or a dependency, both
forbidden by this baseline.

## 5. The two-layer module pattern

`boundary-gjoll` splits into four modules, following a Single Responsibility discipline
worth reusing:

- **`types`**: shared value shapes, no logic.
- **`rule`**: a pure, total core carrying the load-bearing decision logic. It receives the
  narrowest input that can express the decision, denied anything that would let it be
  fooled (in this crate, the registry, the agent sink set, a self-asserted safety flag and
  effect observations are all structurally unreachable from the rule).
- **`declaration`**: contracts and validation, separated out so the module that validates
  input has one reason to change (a new validation condition) distinct from the module that
  derives a verdict (a new derivation source).
- **`consequentiality`** (or the equivalent shell for a future crate): the mandatory,
  registry-backed entry point that validates, derives and then delegates to the rule.

The rule core exposes a verdict or decision type constructible only from inside the crate
(`pub(crate)`, no public constructor, no public `From` conversion, no `cfg` escape hatch a
downstream caller could enable). This turns a "the rule does not trust a self-asserted
input" claim into a property of the type system rather than of review, and it is why the
crate's public surface can stay narrow: a caller reaches the decision logic only through
the mandatory shell, never around it.

## 6. Test-isolation pattern

Test code and implementation code live in separate files in separate directories, so the
implementing agent and the test-writing agent never edit the same file:

- **Unit tests** (needing access to `pub(crate)` items) live in `unit_tests/`, a sibling of
  `src/` and of `tests/`. They are attached to the crate by exactly one declaration in
  `lib.rs`, of the form
  `#[cfg(test)] #[path = "../unit_tests/<name>.rs"] mod <name>;`. That declaration is the
  only test-related construct permitted anywhere under `src/`: no `#[test]`, no
  `mod tests`, no fixture and no double may appear in an implementation file. Because
  `cfg(test)` is set only when Cargo compiles the crate's own test harness, this does not
  widen the visibility a downstream consumer of the crate sees.
- **Integration tests** (proving the public API alone is sufficient) live under `tests/`,
  compiled as an external crate, importing only public items.

The ownership boundary this creates is directory-level and mechanically checkable: a grep
for `#[test]`, `mod tests` or `#[cfg(test)]` over `src/` should return exactly the `lib.rs`
declaration lines and nothing else, and no file should appear under both `src/` and either
test directory.

## 7. The vector-parity mechanism

Where a Rust crate re-expresses existing Python behaviour, correctness is checked from day
one by replaying golden vectors captured from the Python reference, not by writing Rust
tests against an assumed specification:

- A Python exporter (`ontology/tools/export_gate_vectors.py` for this crate) wraps the
  Python reference's own public entry point, captures every real call the existing test
  harnesses make, and derives each vector's expected result by calling the Python's own
  functions rather than reimplementing them.
- The emitted vector file is committed (small, textual and diffable, inspectable without a
  working Rust toolchain), carries a schema version and SHA-256 digests of every Python
  source file the re-expression's correctness depends on.
- A standalone sub-harness (`ontology/tests/rust_gate_harness.py` for this crate) checks
  digest drift first, dependency posture second and the Rust test run third, skipping
  loudly only when no Rust toolchain is present, following
  `ontology/tests/memgraph_integration_harness.py`'s skip-if-absent precedent. A present
  toolchain whose test run fails is always fatal, never laundered into a skip.
- The sub-harness folds into the main Python suite (`ontology/tests/harness.py`) as an
  additive obligation, following the exact shape of an existing fatal-gated obligation
  (`run_effect_probe`), so a Rust re-expression's drift or failure is visible in the same
  report as every other obligation.

A digest mismatch is fatal regardless of whether a Rust toolchain is present, because drift
is a fact about repository state, not about the toolchain: a reviewer without Rust installed
must still be able to tell that the vectors are stale.

## 8. What this baseline does not decide

This document records conventions a crate should follow; it does not itself authorise or
build anything. In particular it does not:

- Decide which future step of D108's build order builds next, or what that crate does.
- Settle the code licence (section 4), which stays OPEN.
- Extend the vector-parity mechanism to a component with no existing Python reference to
  replay against; a genuinely new Rust component needs its own test strategy. **Resolved by
  D110, not left open, for the "existing substrate, no existing concrete Python type" case:**
  `crates/hierarchy-vor/` re-expresses an existing Python substrate
  (`ontology/nornir/authorisation_record.py`), so a Python reference does exist, but no
  Python type shaped like the crate's own hardcoded cohort exists or ever will, because
  D105 rules the hierarchy plane is Rust. The resolution is to export vectors from a shim
  record, defined once, in the exporter file, and nowhere else, honouring the substrate's
  own two-method interface without pretending to replay a real call history that was
  never made. The vector file states this narrower claim in its own text (a `claim` field
  reading "substrate mechanism parity over a shim record... NOT a real Python cohort's
  call history"), so a reader of the committed vectors does not have to infer the scope
  from a spec that may since have been removed. **The fully novel case, a genuinely new
  Rust component with no Python reference to replay against at all, not even a substrate,
  is now also resolved, by D111 (HB3-10), not left open.** Himinbjörg's Rust gateway has no
  Python analogue at any fidelity: the dormant `ontology/yggdrasil/control_surface.py` stub
  models about four fields and holds no behaviour to export vectors from, and D111 leaves it
  untouched rather than inventing a Python Himinbjörg purely to have something to replay.
  The resolution here is different in kind from D110's, not merely narrower: correctness is
  established by Rust-native unit and integration tests written directly against this
  document's own requirements and acceptance criteria, with no golden-vector replay step at
  all, while the **mechanical** obligations the vector-parity precedent established for
  steps one and two are still carried forward for step three, so a genuinely new component
  does not lose them merely for lacking a Python reference: dependency posture (widened per
  the HB3-3 ruling above, reusing `check_dependency_posture` by import rather than copying
  it), test-and-code isolation (REQ-5), public-surface sufficiency (an external-crate
  integration test proving the public surface alone suffices, `tests/public_surface.rs`),
  and live invocation-boundary detection (`ontology/tests/himinbjorg_invocation_harness.py`
  on `vor_invocation_harness.py`'s precedent). Both new checks fold into the same standalone
  sub-harness shape as `rust_cohort_harness.py` (`ontology/tests/rust_gateway_harness.py`),
  additively registered in `ontology/tests/harness.py` on `run_rust_cohort`'s exact pattern.
  A future genuinely new Rust component with no Python reference of any kind inherits this
  ruling rather than needing to rediscover it: replay what exists to replay (D110's case),
  and where nothing exists to replay, still carry the four mechanical obligations named
  above, native Rust tests standing in for vector parity, not for the mechanical posture
  checks. This closes the bullet as it was originally scoped; no case it named is left open.

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
