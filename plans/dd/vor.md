# Detailed Design: Vör (the hierarchy plane's minimal single-cohort attestation)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 3 (hierarchy plane, D106/D107)
**Status of the component today:** built, to the minimal single-cohort scope D108
names as build-order step two. `crates/hierarchy-vor/` is real: six modules under
`src/` (1,182 lines), a committed golden-vector file, 26 in-crate unit tests and
three external-crate integration tests, all passing (`cargo test -p hierarchy-vor`).
The general four-tier cohort catalogue this document's section 7 lists is
deliberately not built.

---

## 1. Purpose

Vör answers a narrower question than the general hierarchy plane eventually will:
given a caller who can produce a trusted authoriser's secret, is this the real,
unaltered `heimdall-dev` cohort. It exists because build-order step three
(Himinbjörg's minimal four-interface slice, D108) needs a cohort to bind to before
it can propose anything, and D108 deliberately scoped that need down to "one
hardcoded attested cohort rather than the general four-tier lattice" rather than
building the cohort catalogue first.

Vör's contribution is exactly D103's identity/integrity move, re-expressed in Rust
and narrowed to one record: there is no code path in `crates/hierarchy-vor/` by
which the `heimdall-dev` cohort can be obtained without its attestation having
verified. It closes D103's limit one for this record type in this crate only. It
does not close D103's limit two (identity is not honesty, section 4), does not
advance invariant 3.6, and does not touch `AgentContext`, `resolve()` or
`ontology/nornir/gjoll.py`. This document preserves that framing throughout,
matching `gjoll.md`'s own discipline of stating a component's honest scope rather
than a flattering one.

## 2. Responsibilities and boundaries

In scope for Vör, at this build's depth:

- Re-express D103's attested-record substrate (`ontology/nornir/authorisation_record.py`)
  in Rust, generically over any record type, knowing no concrete one (section 3).
- Define exactly one hardcoded, attested cohort, `heimdall-dev`, and hand out a
  verified handle or a typed refusal through exactly one entry point (section 3).
- Source the trusted authoriser's secret from outside the repository working
  tree, fail closed on every malformed or missing provenance (section 4).

Out of scope, named rather than silently absent:

- Everything section 7 lists as deferred: `permitted_targets` and the
  protected-branch case, the load-time manifest format, the writer taxonomy, the
  review-gated promotion pipeline, the cohort catalogue's general form, the
  four-tier trust lattice, public-key signing, secret zeroisation and registering
  the two `action:git.*`/`sink:git.*` names in the loaded ontology.
- Any dependency on `crates/boundary-gjoll/`. The crate has no dependency, no
  `use`, no re-export and no shared type with it (REQ-26), and `CONSEQUENTIAL_SINKS`
  is never routed into `consequentiality::evaluate`, whose signature deliberately
  excludes an agent sink set. Step three reads the sink set from
  `CohortSurface::consequential_sinks` for its own `action_critical`
  determination instead (EC-16, section 4).

## 3. The record schema and the substrate re-expression

`CohortDefinition` (`src/types.rs`) carries exactly six fields, mirroring Python's
`AgentContext` field for field and adding nothing: four content fields
(`cohort_id`, `permitted_actions`, `trust_ceiling`, `consequential_sinks`) plus the
attested pair (`authoriser`, `attestation`). There is no `permitted_targets` field
and no protected-branch list.

The substrate is split into three modules that see it from three narrow angles,
following `plans/rust-workspace-baseline.md` section 5's Single Responsibility
discipline:

- **`src/record.rs`** defines `AttestedRecord`, a trait of exactly two required
  methods (`record_type() -> &'static str`, `canonical_fields() -> Vec<(&'static
  str, String)>`), and knows no concrete record: it does not name, import or match
  on `CohortDefinition` anywhere. `canonical_record_bytes` builds the same layout
  as Python's `canonical_record_bytes`: the domain separator
  `heimdall.authorisation_record.v1`, a single `0x00` byte, then a newline-joined
  body whose first line is `record_type=<tag>` and whose remaining lines are the
  record's own fields in the order it returned them. Collection fields are sorted
  ascending and comma-joined, an empty collection encoding as the empty string;
  Rust's `String` ordering over valid UTF-8 is the same code-point order Python's
  `sorted()` uses, pinned by a non-ASCII golden vector rather than merely
  asserted. `constant_time_equals` is the crate's one digest-comparison function,
  comparing lengths first then accumulating differences without an early exit,
  mirroring `sink_attestation._constant_time_equals`.
- **`src/verify.rs`** reproduces `verify_record_attestation`'s four branches in the
  same order: no authoriser or no attestation (refused, `RecordRefusal::Unattested`);
  an authoriser absent from the trusted set (`UnknownAuthoriser`); a digest
  mismatch (`DigestMismatch`); and only then, `Ok(())`. There is no fifth outcome
  and no warning path.
- **`src/types.rs`** implements `AttestedRecord for CohortDefinition`, and defines
  `CohortSurface<'a>`, the borrowed, read-only projection a verified handle hands
  back: `cohort_id()`, `permitted_actions()`, `trust_ceiling()`,
  `consequential_sinks()` and `may_perform(&str) -> bool`. No setter, no owned
  copy, no interior mutability.

`RECORD_TYPE_COHORT_DEFINITION` (Rust, `src/record.rs`) equals
`RECORD_TYPE_COHORT_DEFINITION = "cohort_definition"` (Python,
`ontology/nornir/authorisation_record.py`), a fifth reservation on that module's
existing namespace, added as a string constant and one `__all__` entry only, with
no class, field or machinery. Cross-type separation (a differing record-type tag
yields a differing digest for otherwise identical fields) and cross-substrate
separation (the same content attested through `sink_attestation`'s own domain
separator yields a differing digest) are both demonstrated by golden vector
(section 6), not asserted in prose.

**SHA-256, hand-written in `src/sha256.rs`.** The Rust standard library has no
SHA-256, and the workspace's dependency posture (`plans/rust-workspace-baseline.md`
section 4) keeps `[dependencies]` empty. SHA-256 is implemented inside the crate,
in its own module, as a pure function (`digest_hex`, the module's only public
item) with no input or output beyond its signature and no panic on any input.
This is a hand-written hash implementation on an authorisation path: it is
verified against published known-answer vectors and against every golden vector,
and it is not side-channel hardened, because SHA-256 over a fixed-length record
with a fixed-length key has no secret-dependent control flow to leak. The one
timing-sensitive operation, comparing two hex digests, is the separate,
explicit `constant_time_equals` above, mirroring
`sink_attestation._constant_time_equals`. See
`plans/rust-workspace-baseline.md` section 4 for the ruling this extends and its
reopening trigger (a future step needing HMAC proper, a real KDF or asymmetric
signatures).

## 4. The interface contract build-order step three consumes

The crate's one door is:

```rust
pub fn load_verified_cohort(
    trusted: &authoriser::TrustedAuthoriserSet,
) -> Result<cohort::VerifiedCohort, cohort::CohortRefusal>;
```

`trusted` is a plain reference, never an `Option` and never defaulted, so there is
no unverified path through this function for a later step to design around.
`VerifiedCohort` (`src/cohort.rs`) is constructible only from inside the crate: no
public constructor, no public `From`/`TryFrom`, no `Deref` to the unverified
definition, no `cfg` escape hatch, and no derived `Clone`, `Copy` or `Default`.
Its one read surface is `VerifiedCohort::surface() -> CohortSurface<'_>`.

For step three to obtain a cohort, it must independently obtain a
`TrustedAuthoriserSet` for the authoriser id
`cohort::AUTHORISER_ID` (`"heimdall-dev-authoriser"`), through one of exactly two
public functions:

```rust
pub fn load_trusted_set_from_env(authoriser_id: &str)
    -> Result<TrustedAuthoriserSet, SecretRefusal>;
pub fn load_trusted_set_from_path(authoriser_id: &str, path: &Path)
    -> Result<TrustedAuthoriserSet, SecretRefusal>;
```

Step three must treat every `CohortRefusal` and `SecretRefusal` as fail closed:
there is no degraded, narrowed or empty cohort to substitute on refusal, because
hollowing `consequential_sinks` is the disarming direction, not a safe one
(REQ-23). Step three must read the sink set for its own `action_critical`
determination from `CohortSurface::consequential_sinks()`; there is no path by
which it reaches `boundary-gjoll::consequentiality::evaluate`, whose signature
excludes an agent sink set by construction, and no path is being added here
(EC-16). This must not be rediscovered by whoever builds step three; it is stated
here so it does not need to be.

## 5. The secret-provenance ruling and its residuals

**The ruling.** The trusted authoriser's secret is read at process start from a
file outside the repository working tree, named by an environment variable,
`HEIMDALL_COHORT_SECRET_FILE` (`SECRET_PATH_ENV_VAR`). There is no secret literal
anywhere under `crates/hierarchy-vor/src/`, and no public way to build a
`TrustedAuthoriserSet` from bytes a caller supplies inline. The loader refuses,
fail closed, on every one of seven conditions: the variable absent or empty; the
path missing or not a regular file; the path resolving inside the repository
working tree; the file readable by group or other; the target providing no Unix
permission metadata; the secret shorter than 32 bytes after stripping one trailing
line ending, or entirely whitespace; and the file being unreadable. None of these
falls back to a default or a warning.

Two public functions exist because a secret held directly in an environment
variable is inherited by every child process a later build-order step shells out
to (the git actuator, `plans/synthesis-bootstrap.md` section 5), and would appear
in process listings and crash dumps on the way: `load_trusted_set_from_env` reads
the variable and delegates; `load_trusted_set_from_path` takes a path directly, so
an integration test needs no process-global mutation.

**What this closes.** An attacker with write access to the repository source tree
cannot mint an attestation matching `cohort::COMMITTED_ATTESTATION`, because the
secret is not in the tree. This is the config-tamper property the whole step is
built on.

**What this does not close, stated rather than smoothed, four residuals carried
verbatim from `.opencode/plans/vor-minimal-cohort-spec.md` section 2.2:**

1. An attacker with source-write access before build time can delete the
   verification call, widen the hardcoded cohort and rebuild. No in-tree check
   stops that; the deployed binary is not the source tree (D105). This step
   protects against post-build configuration tamper, not against a compromised
   build.
2. The in-tree rejection (`authoriser::repo_root`) is derived from
   `CARGO_MANIFEST_DIR` at compile time, so on a binary built on one machine and
   run on another the rejected prefix is a path that may not exist locally, and
   the check is then vacuous. This is a development-time guard against the
   source-tree-constant failure mode, stated in the module's own doc comment, and
   it is not a deployment security control.
3. It stays a keyed digest, not a signature. D94's deployment residual
   (asymmetric keys and real non-repudiation) is inherited verbatim and is not
   narrowed here.
4. Secret bytes are not zeroised on drop, because zeroisation a compiler cannot
   elide needs either `unsafe` or a crate dependency, and both are forbidden
   (`#![forbid(unsafe_code)]`, an empty `[dependencies]` table). A memory-scraping
   adversary is out of scope for this step and is named as such in the module's
   own doc comment.

**A fifth honest note this document adds, not in the spec's own list, found by
reading the built code rather than assumed from the plan.** `cohort::COMMITTED_ATTESTATION`
carries its own doc comment stating plainly that the constant currently committed
was produced by `export_cohort_vectors.py`'s authoring mode under a
development-time placeholder secret, not a real, separately-provisioned
production secret. Any deployment relying on this constant today is relying on a
development-time value, and this must be replaced once a real secret is actually
provisioned for a real `heimdall-dev` deployment. This is distinct from, and does
not narrow, the fixture-secret-versus-real-secret separation the vector file
already states (section 6): the vectors were always fixture-secret by design; the
committed constant was meant to be the real thing and, honestly, is not yet.

**On this build machine, the real-cohort check reports its own gap rather than a
pass.** No secret is provisioned via `HEIMDALL_COHORT_SECRET_FILE` here, so
`cargo test -p hierarchy-vor -- --nocapture` prints
`VOR-REAL-COHORT-NOT-EXERCISED`, and `ontology.tests.rust_cohort_harness` reports
the same condition as a named `[GAP]`, not a pass. Mechanism parity is still
proven by the vector replay under the committed fixture secret; only the real
cohort's own attestation is unexercised here. This is the designed behaviour of
edge case three (a secret not provisioned on the machine running the suite), not
a failure.

## 6. Golden vectors

`ontology/tools/export_cohort_vectors.py` derives every vector by calling
`canonical_record_bytes` and `compute_record_attestation`, imported from
`ontology.nornir.authorisation_record`, and the cross-substrate comparison by
calling `ontology.nornir.sink_attestation`'s own functions; it reimplements no
encoding, sort, join or digest. The shim record honouring the two-method
interface, `_ShimCohortRecord`, is defined in that file and nowhere else, because
no Python `CohortDefinition` exists or ever will (D105 rules the hierarchy plane
is Rust). The parity claim is correspondingly narrower than a normal Python
re-expression: it covers the substrate *mechanism* over a shim, not a real
Python cohort's call history.

The committed file, `crates/hierarchy-vor/vectors/cohort_vectors.json`, carries a
schema version, SHA-256 digests of both
`ontology/nornir/authorisation_record.py` and `ontology/nornir/sink_attestation.py`
for drift detection, the fixture secret as lowercase hex with an explicit
non-production label, and ten named vectors (V-1 to V-6, a cross-type pair V-7a
and V-7b, and a mutated-field pair V-9a and V-9b) against a single
`expected_count` the exporter checks itself. The cross-substrate demonstration
(the ninth of the nine named cases the build spec required, its own case eight)
is deliberately not one of the ten vectors: `sink_attestation.canonical_bytes`
carries no record-type prefix and shares no domain separator with
`authorisation_record.canonical_record_bytes`, so it is not a record this
substrate's own shape can carry; it is computed directly, once, and recorded in
the file's top-level `cross_substrate_check` field, with its own rationale stated
in the exporter's docstring. Every vector carries both `canonical_bytes_hex` and
the resulting `attestation`, so a byte-level divergence localises to a field
rather than only surfacing as an opaque digest mismatch (verified as observed: all
digests are 64 lowercase hex characters, matching SHA-256's output length).

The exporter's authoring mode (`attest_real_cohort`) computes the real cohort's
attestation under whatever secret `HEIMDALL_COHORT_SECRET_FILE` names, the same
way the Rust loader sources it, and prints it for pasting into
`cohort::COMMITTED_ATTESTATION`; it never writes the secret or the real
attestation into the vector file, and refuses on the same seven conditions the
Rust loader refuses on.

## 7. Deferred, named, not built

Nine items, carried verbatim from `.opencode/plans/vor-minimal-cohort-spec.md`
section 11.2, so build-order step three inherits them as written obligations
rather than rediscovering them:

| # | Item | Where it goes |
|---|---|---|
| 1 | `permitted_targets` and the protected-branch case | Build-order step four, where the branch actually lives |
| 2 | The load-time manifest format | D107 ruling three. Arrives when a second cohort needs to exist; a change to `cohort.rs`'s input source only |
| 3 | The writer taxonomy | D106 and D107. Not begun |
| 4 | The review-gated promotion pipeline | D106 and D107. Not begun |
| 5 | The cohort catalogue's general form | D106. Not begun |
| 6 | The four-tier trust lattice | D106, and D97's open question about whether `trust_ceiling` draws from `TRUST_ORDER` or a distinct scale, which REQ-21 keeps open |
| 7 | Public-key signing instead of the keyed digest | D94's deployment residual, inherited verbatim, not narrowed |
| 8 | Secret zeroisation and a hardened key store | Section 5's fourth residual and edge case eight. Both need either `unsafe`, a dependency or an ancestor-directory-permission policy with no clean stopping point |
| 9 | Registering `action:git.commit` and `action:git.push` in the loaded ontology's action vocabulary | Deliberately not done. If Phase 1's empty action-critical set is ever revisited, this is where the vocabulary lands, not before |

Also explicitly not begun: build-order steps three to seven (Himinbjörg's minimal
four-interface slice, the git actuator, the process engine, the end-to-end target
loop and the replacement of the cognition stub with a real model call).

## 8. What this step does not claim

Carried from `.opencode/plans/vor-minimal-cohort-spec.md` section 11.4, restated
here because a component document, not only a decision row, should say so:

- **D103's limit two is not closed and cannot be.** A trusted authoriser who
  honestly attests a cohort with a hollow `consequential_sinks` set produces a
  perfectly valid attestation of a disarmed cohort. There is no honesty backstop
  on this surface at all, unlike the sink-declaration seam (D89-B, D93-D).
- **Invariant 3.6 is not advanced.** This crate adds no gate call site, and
  Gjöll's gate still has zero non-test callers in either language. This crate's
  own entry point also has zero non-test callers on the day this document is
  written, reported live by `ontology/tests/vor_invocation_harness.py` rather
  than carried in prose.
- **The vector replay is evidence about translation fidelity of an attestation
  mechanism, nothing more.** It does not prove the Python substrate correct, it
  does not prove the cohort's content correct, and it covers no real Python
  cohort call history, because none exists.
- **The 22 RED false-inert findings, the roughly 48 percent layer-one figure and
  the pipeline containment figure are all unaffected.** This step does not touch
  the classifier, and the invariant 3.1 guard stays at 34 scanned files (this
  crate and `ontology/tools/export_cohort_vectors.py` both sit outside its scan
  roots).
- **The SHA-256 implementation is hand-written on an authorisation path,** verified
  against published known-answer vectors and every golden vector, not
  side-channel hardened (section 3).
- **The code licence stays OPEN,** matching `boundary-gjoll` and D109. No source
  file under `crates/` carries an SPDX header, and `hierarchy-vor`'s manifest
  carries no `license` field.

## 9. Test plan

- **Vector replay**, ordered so the negative control runs first, following
  `_bfo_relatedness_control_check`'s precedent (D101) that no check is trusted
  until shown to bite: a mutated-field pair (V-9a base, V-9b mutated) asserts
  verification refuses under the fixture secret before any positive assertion in
  the same file runs.
- **SHA-256 known-answer tests**: the empty input, a single-block input
  (`"abc"`), the NIST two-block vector, and inputs pinned at the 55, 56 and 64
  byte padding boundaries.
- **Loader refusal tests**, one per REQ-14 condition, each fixture file created
  under the system temporary directory outside the repository; exactly one test
  is documented as environment-mutating (the absent-or-empty-variable case).
- **An integration test compiled as an external crate** (`tests/public_surface.rs`)
  proves the public surface alone is sufficient for build-order step three:
  obtain a trusted set through a public loader, obtain the cohort through the
  public entry point, read the permitted actions and the sink set through the
  projection.
- **The real-cohort verification test** prints one of two distinct, greppable
  markers depending on whether the secret is provisioned; a skip is never
  reported as a pass (section 5).
- **A compile-fail confirmation is documented, not yet executed.** `tests/public_surface.rs`
  carries three commented-out blocks proving `VerifiedCohort` cannot be
  constructed, converted into or cloned from outside the crate, with instructions
  to uncomment one, capture rustc's exact error and record it. As of this
  document, that manual confirmation has not been run and its exact compiler
  error has not been captured; this is a named gap in the verification record,
  not a claim that the property is untested (the type-level absence of a public
  constructor, `From`, `Deref` and any derive is real and was read directly from
  `src/cohort.rs`, section 3), only that the specific compiler-error evidence the
  build spec asks for is still outstanding.
- **Standalone Python entry points**: `ontology.tools.export_cohort_vectors`
  (regenerate and self-check the vectors), `ontology.tests.rust_cohort_harness`
  (digest drift, dependency posture, surface checks, the Rust suite, the
  real-cohort gap report) and `ontology.tests.vor_invocation_harness` (the
  live call-site count). All three folded additively into
  `ontology.tests.harness` as `run_rust_cohort` and `run_vor_invocation_boundary`,
  on `run_rust_gjoll`'s exact shape.

Observed at the time of writing (`cargo test -p hierarchy-vor -- --nocapture`):
26 unit tests plus three integration tests, all passing, with
`VOR-REAL-COHORT-NOT-EXERCISED` printed because no secret is provisioned on this
machine. `python -m ontology.tests.harness` reports exactly 22 critical
findings, all false-inert, unchanged; the invariant 3.1 guard reports 34 scanned
files, unchanged; `gjoll_invocation_harness` reports six test call sites and zero
non-test call sites, unchanged; `vor_invocation_harness` reports two test call
sites (`crates/hierarchy-vor/tests/public_surface.rs`,
`crates/hierarchy-vor/unit_tests/loader_failclosed.rs`) and zero non-test call
sites.

## 10. Data owned

- `crates/hierarchy-vor/vectors/cohort_vectors.json`, the committed golden
  vectors and the fixture secret.
- `cohort::COMMITTED_ATTESTATION`, the one hardcoded cohort's attestation
  constant, its provenance stated honestly in section 5.
- No world state, no flow-to-sink label and no gate policy; those remain
  Mímisbrunnr's and Gjöll's.

## 11. Dependencies

- Upstream: none inside the repository. `[dependencies]` is empty (REQ-1); the
  crate depends only on the Rust standard library.
- Downstream: build-order step three (Himinbjörg's minimal slice), the first and
  only intended caller of `load_verified_cohort`, not yet built (section 7).

## 12. Decisions (index)

| # | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| VOR-1 | Secret provenance | Out of the repository working tree, mandatory, refused if absent | A committed demonstration secret with a named deployment residual | A source-tree secret makes the whole step's config-tamper property circular; the ruling is deliberately cheap to reverse (one module, `src/authoriser.rs`) |
| VOR-2 | SHA-256 | Hand-written inside the crate, its own module, mandatory published known-answer vectors | A runtime dependency | The empty `[dependencies]` table is the Rust analogue of `ALLOWED_IMPORT_ROOTS`; a fixed, published, KAT-testable algorithm is a bounded risk a dependency would not reduce, only relocate |
| VOR-3 | `VerifiedCohort`'s clonability | Not `Clone`, not `Copy`, not `Default`, no public constructor | A cloneable handle | Withholding is the cheap reversible direction; a later genuine need for a second owner is a reviewable edit, not a silent one |
| VOR-4 | The exporter's shim record | A real Python class inside `ontology/tools/export_cohort_vectors.py` and nowhere else | Reusing or approximating an existing Python cohort type | No Python `CohortDefinition` exists or ever will (D105); the parity claim is stated as narrower rather than presented as the normal vector-parity mechanism |
| VOR-5 | The sink set's reachability to the gate | Structurally absent: no dependency on `boundary-gjoll`, no shared type | Wiring `CONSEQUENTIAL_SINKS` into `consequentiality::evaluate` | That signature deliberately excludes an agent sink set (D109); step three must use the projection for its own `action_critical` determination instead |
| VOR-6 | The trust ceiling's representation | An opaque `&'static str`, never ranked, parsed or compared for ordering | A local Rust copy of `TRUST_ORDER` or an enum | Keeps D97's and D103 REQ-32's open question (whether `trust_ceiling` draws from `TRUST_ORDER` or a distinct scale) open rather than creating a second copy to drift |

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
