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

**The third-path-dependency ruling (D112), extending HB3-3 rather than
replacing it.** `crates/himinbjorg/` needed a third in-workspace path
dependency, `crates/actuator-git/`, so `himinbjorg`'s own `[dependencies]`
table now carries exactly three entries rather than two. This is the same
ruling as HB3-3 above, applied a second time: the new dependency is on a crate
whose own `[dependencies]` table is empty and which carries
`#![forbid(unsafe_code)]`, so it introduces no new reachability to a model
call or a network call, and duplicating `actuator-git`'s logic inside
`himinbjorg` to keep the table at two entries would mean maintaining a second
process-spawning module, worse on every axis than a named, reviewed
dependency. `ontology/tests/rust_gateway_harness.py`'s own
`PERMITTED_PATH_DEPENDENCIES` widens from two names to three
(`boundary-gjoll`, `hierarchy-vor`, `actuator-git`) by the same mechanism HB3-3
already established: `rust_gate_harness.check_dependency_posture`'s own
default allowlist stays an empty `frozenset`, so `boundary-gjoll` and
`hierarchy-vor` keep their strict, zero-dependency behaviour byte for byte,
unaffected by the widening. Adding a **fourth** kind of dependency to any
future crate's gate-adjacent path remains a deliberate trust-boundary decision
requiring its own `DECISIONS.md` row, exactly as HB3-3 already required for
the third.

**The `std::process`-in-one-crate ruling (D112).** Before this step, no crate
in the workspace touched `std::process` at all; the git actuator is the first
to need it, to spawn the system `git` binary. The ruling is to isolate every
line that touches `std::process` inside `crates/actuator-git/src/execute.rs`,
the one module in the whole workspace permitted to reference it, rather than
spawning a process directly from `himinbjorg`'s own `broker` module. This
keeps the load-bearing property section 4's opening rule protects, that there
is no crate through which a model call or a network call could be reached,
stated as a mechanically checkable fact about a named module rather than
about the workspace's dependency graph alone: `ontology/tests/rust_actuator_harness.py`
scans `crates/actuator-git/src/` for `std::process` and expects to find it
only in `execute.rs`, and the widened `ontology/tests/rust_gateway_harness.py`
scans `crates/himinbjorg/src/` and expects to find no reference to it at all,
so `himinbjorg` calling the actuator's own `execute` function is not confused
with `himinbjorg` spawning a process itself. A future crate needing to touch
`std::process` for a second, unrelated reason reopens this ruling with its own
`DECISIONS.md` row rather than being pre-permitted by this one.

**The fifth crate's path-dependency ruling (D113), extending HB3-3 and D112 rather
than replacing them, plus a disclosed exception neither anticipated.** Build-order
step five's `crates/process-engine/` needed real, callable access to
`himinbjorg::validate_proposal` and `himinbjorg::broker_authorised_action`, so its
own `[dependencies]` table was scoped, in the build spec, to exactly two
in-workspace path entries, `himinbjorg` and `hierarchy-vor`. The crate as built
carries a **third**, `boundary-gjoll`, disclosed in the crate's own `Cargo.toml`
comment and `src/lib.rs` doc comment rather than left for a reader to discover: it
exists because `himinbjorg::ProposalParameter`'s own fields
(`consume_mode: boundary_gjoll::types::ConsumeMode`, `trust_level:
boundary_gjoll::types::TrustLevel`) are unmodifiable, out-of-scope `himinbjorg`
content, and Rust's extern-prelude resolution does not make a transitive
dependency's items nameable without a direct dependency declaration on the crate
that defines them, a claim confirmed empirically with a minimal three-crate
reproduction before it was relied on, not assumed from first principles. Both the
crate's own `DefaultCognitionStep`, which must build a genuinely non-empty
`Vec<ProposalParameter>`, and its own already-committed
`unit_tests/cognition_and_proposal.rs` construct `ProposalParameter` values
directly and so need `ConsumeMode`/`TrustLevel` resolvable by name. This is the
same shape of ruling as HB3-3 and D112's own third-dependency extension of it,
applied a third time to a different crate: the new dependency is on a crate whose
own `[dependencies]` table is empty and which carries `#![forbid(unsafe_code)]`,
so it introduces no new reachability to a model call or a network call, and it is
for **value construction only**. The load-bearing property this section exists to
protect is untouched: `crates/process-engine/` still never depends on
`actuator-git`, never names `actuator_git::` anywhere in its own source, and never
calls `boundary_gjoll::consequentiality::evaluate` or any other Gjöll gate function
directly, so the gate is still reached only through
`himinbjorg::validate_proposal`, never bypassed. `ontology/tests/rust_process_engine_harness.py`
checks this against the **real, disclosed three-name** table
(`boundary-gjoll`, `hierarchy-vor`, `himinbjorg`), not the build spec's literal
two-name text, and states the discrepancy in its own output rather than silently
reconciling it; `rust_gate_harness.check_dependency_posture`'s own empty default
stays untouched, so `boundary-gjoll` and `hierarchy-vor` keep their strict,
zero-dependency behaviour byte for byte. Adding a **fourth** kind of dependency to
any future crate's gate-adjacent path remains a deliberate trust-boundary decision
requiring its own `DECISIONS.md` row, exactly as HB3-3 and D112 already required
for the second and third.

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
  **A second genuinely-new-component case confirms the ruling generalises rather than being
  a one-off (D112).** `crates/actuator-git/` has no Python analogue at any fidelity, not even
  a dormant stub: nothing under `ontology/` models a git actuator, because the whole point of
  building one in Rust is that no Python equivalent was ever written or intended (D105 rules
  the actuator, like the rest of the hierarchy and process planes, is Rust). Correctness is
  established the same way D111's own resolution names: Rust-native unit and integration
  tests written directly against `.opencode/plans/git-actuator-step-four.md`'s own
  requirements and acceptance criteria, with no golden-vector replay step, while the four
  mechanical obligations carry forward unchanged in shape: dependency posture (widened again,
  reusing `check_dependency_posture` by import), test-and-code isolation, public-surface
  sufficiency (`crates/actuator-git/tests/public_surface.rs`, mirroring `hierarchy-vor`'s own),
  and live invocation-boundary detection (`ontology/tests/actuator_invocation_harness.py`, on
  the same precedent, reporting both the actuator's own single non-test call site and the
  witness-carrying entry point's zero).   Both new checks fold into a new standalone sub-harness,
  `ontology/tests/rust_actuator_harness.py`, on `rust_gateway_harness.py`'s exact shape. No
  further case remains open that this bullet's own wording leaves unresolved: a third
  genuinely-new Rust component inherits the same choice between D110's replay-what-exists
  case and D111's and D112's native-test case, decided by whether a Python reference exists
  to replay, not by anything left undecided here.
  **A third genuinely-new-component case confirms the ruling generalises to a fifth crate
  (D113).** `crates/process-engine/` has no Python analogue at any fidelity either, not even a
  dormant stub: nothing under `ontology/` models a fixed sequencing engine, because the whole
  point of building one in Rust is that Gleipnir's own state-machine mechanism is re-expressed
  natively rather than ported from a Python original that never existed here (D105, D108).
  Correctness is established the same way D111's and D112's own resolutions name: Rust-native
  unit and integration tests written directly against
  `.opencode/plans/process-engine-step-five-spec.md`'s own requirements and acceptance
  criteria, with no golden-vector replay step, while the four mechanical obligations carry
  forward unchanged in shape: dependency posture (widened again, reusing
  `check_dependency_posture` by import, against the real, disclosed three-name table section 4
  above records), test-and-code isolation (including the workspace's first binary target,
  `src/main.rs`, section 9 below), public-surface sufficiency
  (`crates/process-engine/tests/public_surface.rs`, mirroring `hierarchy-vor`'s and
  `actuator-git`'s own), and live invocation-boundary detection, this time across three
  existing detectors widened with a reviewed allowlist entry each
  (`ontology/tests/actuator_invocation_harness.py`, `ontology/tests/himinbjorg_invocation_harness.py`,
  `ontology/tests/vor_invocation_harness.py`) rather than one new one. The new mechanical
  obligations fold into a new standalone sub-harness, `ontology/tests/rust_process_engine_harness.py`,
  on `rust_actuator_harness.py`'s exact shape. This is the third instance of the same choice
  the bullet above already named as inherited, not a new rule: a fourth genuinely-new Rust
  component decides the same way, by whether a Python reference exists to replay.

## 9. Binary-target posture (D113, the workspace's first binary)

`crates/process-engine/` is the workspace's first crate to carry a `[[bin]]` target
alongside its library. Every ruling above this point governs a library crate root
(`src/lib.rs`); a binary crate root (`src/main.rs`) is a separate compilation unit
with its own attributes, and a future crate adding one inherits this section rather
than the library rules above by analogy. The load-bearing property section 4 exists
to protect, that there is no crate through which a model call or a network call
could be reached, is unaffected by a binary target as such: what changes is that the
workspace stops being auditable purely by static posture checks over libraries and
gains a runnable surface, so the following properties are stated once here rather
than assumed.

- **What a binary may read.** A binary owns every environment read for its own
  crate, or delegates that reading to exactly one named startup module its `main.rs`
  calls; no other module under that crate's `src/` may read an environment variable,
  read a file or resolve a path. The library half of the crate takes its
  preconditions as already-resolved parameters and reads none of them itself,
  mirroring how `himinbjorg::build_context` and `enforce_definition` already take an
  already-verified `&hierarchy_vor::VerifiedCohort` rather than loading one.
- **What a binary may not do.** No step logic, no proposal or decision shaping, no
  cognition and no outcome interpretation beyond mapping a result to a documented
  exit code and printing it. No argument parsing and no configuration-file read: a
  binary's task, if it has one, is a hardcoded named constant carrying a
  compile-time non-emptiness assertion, on the same no-configuration-surface
  reasoning the cognition seam and the gating constants elsewhere in a crate already
  follow, so there is no surface through which the guarded population could change
  what the binary does. No loop, no daemon mode, no retry, no signal handler and no
  scheduler: a binary runs its crate's own sequence at most once per process.
- **`#![forbid(unsafe_code)]` is not inherited.** A binary crate root is a separate
  compilation unit from the library, so its own attributes must be stated
  explicitly at the top of `src/main.rs` rather than assumed to follow from the
  library's own `#![forbid(unsafe_code)]` at the top of `src/lib.rs`. Both files
  carry the attribute independently.
- **Exit codes are a small, closed, documented set.** Every outcome a binary can
  reach maps to a named exit-code constant with its own doc comment, all distinct,
  the whole set documented in one place. Zero is reserved for the fully successful
  case; every other outcome, including a startup refusal, maps to its own
  non-zero, never-reused code. No outcome maps to an undocumented code and no
  failing outcome maps to zero.
- **The one disclosed, narrow exception to the empty-`std::process`-outside-`execute.rs`
  rule.** Section 4's `std::process`-in-one-crate ruling (D112) forbids a second
  crate from spawning a subprocess; it says nothing about a binary terminating its
  own. Mapping an outcome to the process's own real exit code needs
  `std::process::exit`, and Rust has no other route to it. A binary's `main.rs` may
  therefore reference `std::process::exit` alone, confined to that one file, never
  `std::process::Command` or any other subprocess-spawning item, and this must be
  disclosed in the binary's own doc comment rather than left for a scanner to
  discover unexplained. A mechanical check distinguishes the two: it is a violation
  for `std::process::Command`, or for `std::process` of any kind, to appear
  anywhere outside `crates/actuator-git/src/execute.rs` and the one disclosed
  `std::process::exit` call site named above.
- **How the invocation detectors classify `src/main.rs`.** All three of this
  repository's live invocation-boundary detectors (`ontology/tests/actuator_invocation_harness.py`,
  `ontology/tests/himinbjorg_invocation_harness.py`, `ontology/tests/vor_invocation_harness.py`)
  share one `_is_test_path` implementation, keyed on whether `"unit_tests"` or
  `"tests"` appears among a path's own directory components. `src/main.rs` contains
  neither, so it classifies as **non-test** under all three, exactly like any other
  file under `src/`. A binary target does not need, and must not be given, a special
  case in any detector: it is scanned, and if it calls an allowlist-governed symbol
  it needs its own reviewed entry naming it, on the same exactly-one-required
  polarity as every other non-test call site.

Realised first by `crates/process-engine/src/main.rs` (D113): it delegates every
environment read to `src/startup.rs`, carries its own `#![forbid(unsafe_code)]`,
parses no arguments, reads its one hardcoded task from named constants, maps its
outcome to one of a small documented set of exit-code constants, and carries the
one disclosed `std::process::exit` exception stated above, confined to that file.

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
