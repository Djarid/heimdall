# Detailed Design: the process engine (`crates/process-engine/`)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 3 (build-order step five of `plans/synthesis-bootstrap.md`, D108)
**Status of the component today:** built and tested at the fidelity this document
records. This is the repository's fifth Rust crate and the first genuine non-test
caller of `himinbjorg::validate_proposal`, `himinbjorg::broker_authorised_action`,
Himinbjörg's other three interfaces, and `hierarchy_vor::load_verified_cohort`.

---

## 1. Purpose

The process engine sequences a fixed, five-step run: accept a task, obtain
cognition's advisory content, turn the two into a proposal, gate the proposal
through Himinbjörg's own `validate_proposal`, and, only on `Decision::Allow`,
execute through `himinbjorg::broker_authorised_action`. It is the piece
`STATUS.md` section 0 named as load bearing before this step landed: four crates
already held a complete authorisation path from a proposal to a git process, and
nothing in the repository called that path outside a test.

The engine adjudicates nothing. It sequences. Every authorisation decision in the
run is `validate_proposal`'s, and every execution decision is
`broker_authorised_action`'s; the only refusal the engine originates itself is a
structural well-formedness refusal on the task, before cognition ever runs, and
that refusal is never described as an authorisation decision. This mirrors
`crates/actuator-git/`'s own posture one layer up: the actuator executes what has
already been authorised and adjudicates nothing about whether it should; the
engine calls what has already been built and decides nothing about whether a
proposal should pass.

## 2. Responsibilities and boundaries

In scope:

- Run the fixed five-step sequence exactly once per call to the crate's one
  public entry point, in order, with no back edge.
- Turn a task and the cognition step's advisory output into exactly one
  `himinbjorg::Proposal`, inventing no permission of its own.
- Call `himinbjorg::validate_proposal` exactly once, genuinely, and carry every
  one of its six `CheckRecord`s through verbatim on a block.
- Call `himinbjorg::broker_authorised_action` exactly once, and only when a
  witness minted by an `Allow` decision is already held, supplying a fresh
  `himinbjorg::MinimalDecisionRecorder` per run.
- Carry a `BrokerRefusal` or an `ActuationReceipt` through to the caller
  verbatim, dropping nothing two differing upstream refusals need to stay
  distinguishable.
- Own a binary target whose only job is to resolve two environment-named
  preconditions, call the library's one entry point once, and map the outcome to
  a documented exit code.

Out of scope, named rather than smoothed:

- **It adjudicates nothing.** No step reads Himinbjörg's own gating constants
  (`TARGET_SCOPE`, `PERMITTED_CREDENTIAL_SCOPES`, `BLAST_RADIUS_BOUND`,
  `RESOURCE_CEILING`, the sink registry, the cohort's permitted-action set) to
  decide whether to proceed. The engine's own hardcoded cognition constants
  answer a different question, what is proposed, never what is permitted.
- **It stages nothing.** The stub cognition step produces a proposal only, no
  file content, and the engine performs no filesystem write on any path (section
  4 below).
- **It cannot name Gjöll's gate or the actuator's entry point at all.** The
  gate is reached only through `validate_proposal`'s check five; the actuator is
  reached only through `broker_authorised_action`. The crate's own dependency
  table does not carry `boundary-gjoll` for gate access or `actuator-git` at all
  (section 8 states the one disclosed exception).
- **It does not own a loop cap or a human-question gate.** Both are named,
  typed and deliberately unconstructible this step (section 4 below), because
  the chosen task is low-stakes enough not to need them for this first proof
  (D108).
- **It is not the audit log.** The decision the engine's run authorises is
  written to Himinbjörg's own minimal audit seam
  (`crates/himinbjorg/src/audit.rs`) inside `broker_authorised_action` itself;
  the engine supplies a real recorder and does nothing else with the write.

## 3. The fixed five-step sequence

The step vocabulary is a closed, five-variant enum, `EngineStep`, in this fixed
order: `AcceptTask`, `Cognition`, `ProposeAction`, `Gate`, `Execute`. The
sequence itself is a fixed array of exactly those five variants in that order,
`STEP_SEQUENCE: [EngineStep; 5]`, carrying a `const _: () = assert!(...)`
compile-time length assertion, so an edit that adds or removes a step fails the
build rather than a later test run. "Result out" is the entry point's own return
value, `EngineOutcome`, never a sixth step.

No back edge is expressible. `run_sequence_with_cognition` (`sequence.rs`) is a
straight-line function: accept task, obtain cognition, propose, gate, and,
conditionally, execute, returning at the first refusal it meets and otherwise
falling through to the end. There is no `loop`, no `while`, no recursive call
and no branch that returns control to an earlier step; each step runs at most
once, in array order, per call. The crate exposes exactly one public entry
point, `run_sequence`, that runs the sequence with the crate's one stub
cognition implementation; every step's own implementation
(`accept_task`, `run_gate`, `run_execute`) is `pub(crate)`, reachable only
through it, following `boundary-gjoll`'s registry-mandatory shell and
`actuator-git`'s single-`execute`-surface pattern.

The gate step calls `himinbjorg::validate_proposal` exactly once, never
bypassed and never re-implemented locally; no branch anywhere in the crate
copies, approximates or short-circuits any of the six checks. The execute step
is reachable only from a point that already holds `Decision::Allow` and the
`Authorisation` witness `ProposalDecision::authorisation()` returned as `Some`;
the witness is passed straight through, never reconstructed, never cloned (it
implements no `Clone`) and never synthesised. Execution goes through
`broker_authorised_action` and nothing else: the engine never calls
`broker_action`, never calls `actuator_git::execute`, and cannot name the
latter at all, so `broker_action` keeps its exact zero non-test callers after
this step.

## 4. The cognition seam

Cognition sits behind a one-method trait, `CognitionStep`, on
`himinbjorg::DecisionRecorder`'s Interface Segregation precedent applied a
second time: nothing about verification, retry, streaming, cancellation, token
accounting or model identity is declared on it, so a future implementor is not
forced to satisfy an operation it has no use for. Exactly one implementation
exists in this step, `DefaultCognitionStep`, whose output is built from
hardcoded named constants declared in `cognition.rs`, each carrying its own
`const _: () = assert!(...)` non-emptiness assertion, on
`context::TARGET_SCOPE`'s own precedent. The stub reads no file, reads no
environment variable, opens no socket and consults no configuration surface on
the process path: there is no configuration file, no environment override and
no manifest through which the guarded population could change what cognition
proposes (D105 row H5).

Cognition is advisory and never adjudicative, which is why a substitutable trait
here does not repeat `crates/actuator-git/`'s own rejection of a trait at the
actuator invocation (D112, GA-1's declined alternative). Everything cognition
produces still passes through `validate_proposal`'s six checks and the witness
match regardless of which implementation supplied it; no branch anywhere derives
a permission, a scope, a target-scope membership or a check outcome from
cognition's output. A substitutable **execution** path would create exactly the
seam an attacker wants, which is why `broker_authorised_action` stays a concrete
call and the sequence itself is not behind a trait at all. A substitute
implementation that proposes a deliberately disallowed action is still blocked
at the gate, attributable to a named `CheckRecord`, which is the property that
makes the trait acceptable here where it was rejected one layer down.

One function, `proposal::build_proposal`, and only one, turns a task plus a
cognition output into a `himinbjorg::Proposal`; it is the only `Proposal`
construction site in the crate, and every field it sets comes from the task,
from the cognition stub's constants or from a named engine constant, never from
reading Himinbjörg's own gating constants.

## 5. The binary's startup contract

`crates/process-engine/src/main.rs` is the crate's one binary target. Its only
job is to call `startup::run()` to resolve three environment-named
preconditions, call the library's one entry point once on the task the third
precondition selects, and map the outcome to a documented exit code. It
contains no step logic, no proposal shaping, no cognition and no outcome
interpretation beyond that mapping. It parses no arguments and reads no
configuration file: the five task constant-sets it selects among (build-order
step six, D114) come from named constants carrying their own compile-time
non-emptiness assertions and a compile-time length assertion fixing the array
at five members, on the cognition seam's own no-configuration-surface
reasoning applied to the binary's own input.

`startup.rs` is the one module in the crate that reads the environment; every
other module, including `main.rs` itself, reads none. It resolves three
preconditions independently, always attempting all three so a caller sees
which one failed, or which two, or all three, never only the first:

- **The cohort precondition**, from `HEIMDALL_COHORT_SECRET_FILE`: loads a
  `hierarchy_vor::TrustedAuthoriserSet` via
  `hierarchy_vor::load_trusted_set_from_path` and verifies it into a real
  `hierarchy_vor::VerifiedCohort` via `hierarchy_vor::load_verified_cohort`, the
  crate's one non-test call site of that entry point (this is REQ-26's own
  split: the binary loads the cohort; the library takes an already-verified
  `&VerifiedCohort` and never loads one itself, mirroring
  `himinbjorg::build_context`'s and `enforce_definition`'s own posture).
- **The working-repository precondition**, from
  `HEIMDALL_ACTUATOR_GIT_WORKING_REPO`: checks only that the named path exists
  and is a directory, deliberately not duplicating the actuator's own five,
  deeper refusal conditions.
- **The task-selector precondition, added at build-order step six**, from
  `TASK_SELECTOR_ENV_VAR = "HEIMDALL_ENGINE_TASK"`: resolves the supplied value
  against a closed, compile-time set of five accepted selector names, one per
  member of the fixed task array `main.rs` carries, and yields an index into
  that array only. Absent, empty, whitespace-only or a value outside the closed
  set refuses fail closed, naming the variable, with no default, no fallback,
  no case folding, no whitespace trimming, no prefix or substring match and no
  numeric-index acceptance. The selector supplies no action name, no target, no
  sink, no declared cost and no task identifier: its only product is which of
  five already-compiled proposals is submitted for adjudication, never how any
  of them is adjudicated.

All three refuse fail closed and never default: an absent or empty variable,
an unverifiable secret, an unusable working-repository path, or an unresolved
selector all refuse, naming the failing environment variable and the refusal
class, never a secret byte, a digest or any portion of key material. Where a
path is printed it is the path only. No step of the sequence runs until all
three preconditions resolve.

**The REQ-21 amendment to REQ-31, stated here rather than left to the decision
row alone.** REQ-31 (this document's own numbering) bars the binary from
parsing arguments or reading a configuration file, on the ground that the
binary should carry no configuration surface at all. Three things are true
together about the task-selector precondition just added, and none of them
may be read in isolation from the other two:

1. REQ-31's two literal prohibitions both remain intact. The binary parses no
   arguments and reads no configuration file; `HEIMDALL_ENGINE_TASK` is an
   environment variable, exactly like the two preconditions that already
   existed, never a flag and never a file path naming a document to load.
2. REQ-31's underlying concern, that the binary should carry no configuration
   surface, is **amended**, not honoured by a technicality: a variable that
   selects which of several compiled behaviours runs is a configuration
   surface by any honest reading of the word, and this document says so rather
   than describing the selector as compliant with the original no-surface
   reading.
3. The load-bearing property REQ-31 exists to protect is nonetheless preserved
   and mechanically checked: the selector cannot widen what is authorised,
   because every member of the five-item array is a compile-time constant in
   the engine's own source, the selector chooses an index only, and every
   member passes through the identical five-step sequence, the identical six
   checks, the identical witness match and the identical actuator allowlist.
   This is the same argument section 4 already makes for why `cognition.rs`'s
   substitutable trait does not repeat D112's rejection of a trait at the
   actuator invocation: a seam that decides nothing about authorisation cannot
   widen authorisation, whether that seam is a trait implementation or an
   environment-selected array index.

This amendment is also recorded as a new row in section 11's decisions table
(PE-11) and in `DECISIONS.md` D114.

## 6. Fail-closed behaviour

Inside the engine, every one of the following refuses rather than proceeding
with a degraded or default value:

- a task that is not structurally well formed (empty or whitespace-only task
  identifier): the engine's own `RefusedBeforeCognition` outcome, documented as
  a structural well-formedness refusal and never an authorisation decision;
- any of the three environment-named startup preconditions unresolved (section 5);
- `validate_proposal`'s decision not being `Allow`: the gate-blocked outcome,
  carrying all six `CheckRecord`s verbatim;
- any `broker_authorised_action` refusal: carried through verbatim, including
  the `ActuationRefusal` variant recoverable from an `ActuatorRefused` payload.

Before build-order step six (D114), a commit proposal that passed all six
checks reached the actuator and refused with `ActuationRefusal::ExitStatus`,
because nothing in this crate or the workspace could stage a change (`argv.rs`'s
fixed `["commit", "-m", <message>]` shape forbids `add`, and step four's own
EC-4 already records that "nothing staged" is a non-zero exit). **That refusal
is no longer the terminal state of the positive path.** Build-order step six
stages content out of band: `ontology/tools/run_target_loop.py`, a standalone
Python driver living outside `crates/`, performs the one `git add` the commit
needs, in a throwaway clone, before the engine binary is ever invoked, never by
the engine itself. Against that out-of-band staged content the commit path now
succeeds, and the push that follows it makes the commit reachable in a real
remote's history (`TARGET_LOOP_EVIDENCE.md`). This is EC-1's stated boundary,
discharged exactly that far and no further: the commit succeeds because the
operator staged the change outside the pipeline, not because anything inside
`crates/process-engine/` or the workspace learned to stage one. The engine
still writes no file on any path, and no staging call is added anywhere to
make the old refusal disappear; doing so would still breach REQ-8 (no
filesystem write) and would still put a second `std::process` site in the
workspace, reopening D112's one-crate ruling. Governed staging, a real
`GitOperation::Stage` variant reached through a gated action rather than an
ungoverned fixture step, is deferred to build-order step seven as a named
obligation (section 12).

## 7. Data owned

The engine itself owns no persistent state, no world model and no audit
record. What it owns is entirely in-memory and compiled in:

- `cognition.rs`'s hardcoded task-shape constants the stub's output is built
  from.
- `sequence.rs`'s `ENGINE_CREDENTIAL_SCOPE`, the one credential scope the
  engine presents to `broker_authorised_action`, an agreement with
  `himinbjorg::broker`'s own permitted-scope allowlist, never a derivation from
  it (that allowlist is `pub(crate)` to `himinbjorg` and this crate cannot see
  it at all).
- `main.rs`'s five task constant-sets (build-order step six, D114), its
  compile-time-length-asserted array of them, and its named exit-code
  constants.
- `startup.rs`'s `TASK_SELECTOR_ENV_VAR` and the closed, compile-time set of
  five accepted selector names it resolves against (build-order step six).

The decision record HB-6 requires is owned by `himinbjorg`, not by this crate:
the engine supplies a fresh `himinbjorg::MinimalDecisionRecorder` per run and
nothing else. `startup.rs`'s three environment variable **names**
(`HEIMDALL_COHORT_SECRET_FILE`, `HEIMDALL_ACTUATOR_GIT_WORKING_REPO` and, since
build-order step six, `TASK_SELECTOR_ENV_VAR`) are its own named constants,
restated rather than imported, because `hierarchy_vor::SECRET_PATH_ENV_VAR` is
not exposed to this crate at the same visibility and
`actuator_git::repo::WORKING_REPO_ENV_VAR` is `pub(crate)` to that crate alone
and this crate does not depend on `actuator-git` in any case; the third name is
this crate's own, never restated from elsewhere.

## 8. Dependencies

- **Upstream (the crate's own non-test callers):** none inside the repository.
  `crates/process-engine/` is not depended on by any other crate; its own
  library entry point and its binary are both terminal in the workspace's
  dependency graph.
- **Downstream (what this crate itself depends on):** `himinbjorg` (for
  `validate_proposal`, `broker_authorised_action`, the other three interfaces
  and their value shapes) and `hierarchy-vor` (for `VerifiedCohort`,
  `load_verified_cohort`, `load_trusted_set_from_path`), both required by the
  build spec's own REQ-2. **A disclosed, empirically-confirmed third
  dependency, `boundary-gjoll`, is also present**, for value construction only:
  `himinbjorg::ProposalParameter`'s own fields
  (`consume_mode: boundary_gjoll::types::ConsumeMode`,
  `trust_level: boundary_gjoll::types::TrustLevel`) are unmodifiable existing
  `himinbjorg` content, and Rust's extern-prelude resolution does not make a
  transitive dependency's items nameable without a direct declaration, confirmed
  with a minimal three-crate reproduction before this dependency was added, not
  assumed. `crates/process-engine/` still never depends on `actuator-git`, never
  names `actuator_git::` anywhere in its own source, and never calls
  `boundary_gjoll::consequentiality::evaluate` or any other Gjöll gate function
  directly: the load-bearing property (the gate is reached only through
  `validate_proposal`) is intact. See `plans/rust-workspace-baseline.md` section
  4 for the full ruling, extending HB3-3 and D112 a third time.
- The dependency direction is one way: the engine depends on Himinbjörg, never
  the reverse. `crates/himinbjorg/Cargo.toml`'s own `[dependencies]` table is
  unchanged at exactly three entries after this step, and no crate names
  `process-engine` as a dependency (PE-1).

## 9. Build delta from today

Before this step, `himinbjorg::broker_authorised_action`, Himinbjörg's other
four interfaces and `hierarchy_vor::load_verified_cohort` each had zero
non-test callers, so a complete authorisation path from a proposal to a git
process existed and nothing in the repository called it outside a test. This
step builds the caller:

- **`crates/process-engine/`, the repository's fifth Rust crate.** A library
  (`lib.rs`, `sequence.rs`, `task.rs`, `cognition.rs`, `proposal.rs`,
  `outcome.rs`, `startup.rs`) plus one binary (`main.rs`), both carrying their
  own `#![forbid(unsafe_code)]`. `[dependencies]` carries the disclosed
  three-name table (section 8).
- **`crates/himinbjorg/src/context.rs`'s `TARGET_SCOPE`** gains
  `"fixture-integration-branch"` additively, keeping `"fixture-target"`
  unchanged, recorded in the constant's own doc comment as an agreement between
  two independently owned lists (matching `targets::PERMITTED_TARGETS`), never
  a derivation, on `sinks.rs`'s own EC-7 precedent. This is the only line of any
  existing crate this step changes; the existing `ac57` case in
  `crates/himinbjorg/unit_tests/witness_and_audit.rs` continues to pass
  unmodified, because it targets `"fixture-target"`, which stays in scope here
  while still failing at `actuator_git::targets::PERMITTED_TARGETS`'s own
  allowlist.
- **Three existing live invocation detectors are widened, not repurposed.**
  `ontology/tests/actuator_invocation_harness.py` gains an allowlist mechanism
  for `broker_authorised_action` it previously lacked entirely, naming
  `crates/process-engine/src/sequence.rs`.
  `ontology/tests/himinbjorg_invocation_harness.py`'s group one gains
  allowlist entries, keyed by symbol and path together, naming the engine's own
  non-test call sites of `build_context`, `enforce_definition`,
  `validate_proposal` and `broker_authorised_action` (all four, not only
  `validate_proposal`/`broker_authorised_action`, because the engine's own
  accept-task step resolves context and the effective surface for itself before
  cognition ever runs). `ontology/tests/vor_invocation_harness.py` gains one
  entry naming `crates/process-engine/src/startup.rs` as the permitted non-test
  call site of `load_verified_cohort`. Group three of
  `himinbjorg_invocation_harness.py` is unaffected, scoped to
  `crates/himinbjorg/` only, which the engine sits outside of.
- **A new standalone Python sub-harness**,
  `ontology/tests/rust_process_engine_harness.py`, on
  `rust_actuator_harness.py`'s exact shape, folded additively into
  `ontology/tests/harness.py` as `run_rust_process_engine`.

`crates/actuator-git/`, `crates/boundary-gjoll/`, `crates/hierarchy-vor/` and
every file inside `crates/himinbjorg/src/broker.rs`, `validation.rs`,
`types.rs`, `audit.rs`, `gate_bridge.rs`, `sinks.rs` are all unchanged,
confirmed by direct inspection.

## 10. Test plan

Following `plans/dd/index.md` section 5's convention (a security property is
tested by its failure mode, not only its happy path):

- **The structural half, executable without a provisioned secret.**
  `unit_tests/sequence_shape.rs`: the step enum's exactly-five variants and the
  sequence array's own content; the single `validate_proposal` call site; no
  local copy of any of the six checks; the human-question outcome variant
  declared and never constructed anywhere in `src/`; no read of Himinbjörg's
  own gating constants in a branch that decides whether to proceed.
- **The cognition and proposal-shaping half.**
  `unit_tests/cognition_and_proposal.rs`: the trait's exactly one method; a
  substitute cognition implementation proposing a disallowed action still
  blocked at the gate; no branch deriving a permission from cognition's
  output; the one `Proposal` construction site and the origin of every field
  it sets.
- **The binary's startup contract, tested by refusal.**
  `unit_tests/startup_failclosed.rs`: the secret path unset, set to an
  unverifiable path; the working-repository path unset or unusable; and,
  since build-order step six, the task selector unset, empty, whitespace-only
  or unrecognised; each refusing fail closed and naming the failing variable;
  all three conditions failing together naming all three; no secret byte
  appearing in any refusal description across any of the three.
- **The public surface and both directions of PE-9, gated on a provisioned
  secret where a cohort is genuinely needed.** `tests/public_surface.rs`,
  compiled as an external crate: a task naming a permitted action reaching
  `Decision::Allow` and the execute step; a task naming a disallowed action
  blocked at a named `CheckRecord`; the `PROCESS-ENGINE-REAL-COHORT-VERIFIED`
  or `PROCESS-ENGINE-REAL-COHORT-NOT-EXERCISED` marker printed rather than a
  silent skip when the secret is absent.
- **A new Python sub-harness, folded into the main suite.**
  `ontology/tests/rust_process_engine_harness.py` checks dependency posture
  (against the real, disclosed three-name table), test-and-code isolation
  including `main.rs`, `#![forbid(unsafe_code)]` in both crate roots with no
  `unsafe` keyword, exactly one binary target, the absence of `std::process`
  and `std::net` beyond the one disclosed `std::process::exit` exception, the
  step enum's five variants and the sequence array's length assertion, the
  absence of `boundary-gjoll` and `actuator-git` from a literal two-name
  reading (narrowed by the disclosed exception), and the Rust suite.

**Observed at the time of writing** (the verification set run in the same
session this document was completed in): `cargo test --workspace` passes 174
tests across all five crates, zero failures (137 pre-existing plus 37 new: 35
unit tests in `crates/process-engine/unit_tests/` and two integration tests in
`crates/process-engine/tests/public_surface.rs`); `python3 -m
ontology.tests.harness` reports exactly 22 critical findings, all false-inert,
with the new obligation passing; the invariant 3.1 guard reports 34 scanned
files, unaffected, because `crates/` sits outside its scan roots;
`ontology.tests.pipeline_score_harness` reports 48 percent layer one and 33 of
33 (100 percent) pipeline containment, unchanged;
`ontology.tests.gjoll_invocation_harness` reports six test call sites and zero
non-test call sites, unchanged; `ontology.tests.actuator_invocation_harness`,
`ontology.tests.himinbjorg_invocation_harness` and
`ontology.tests.vor_invocation_harness` all report exactly one non-test call
site of their respective widened symbols, and it is the allowlisted one in
every case. See `DECISIONS.md` D113 for the full figures and the line-budget
outcome.

## 11. Decisions (index)

| # | Ruling | Chosen | Declined alternative |
|---|---|---|---|
| PE-1 | Where the engine lives and which way the dependency arrow runs | A new fifth crate, `crates/process-engine/`, depending on `himinbjorg`, never the reverse; corrects `plans/synthesis-architecture.md`'s "resident inside Himinbjörg" and "hosts process-engine" language | A module inside `crates/himinbjorg/`, which would have given that crate two reasons to change and made the actuator call intra-crate |
| PE-2 | The stubbed cognition step's output | Hardcoded named constants in the engine crate, with compile-time non-emptiness assertions | A fixture file, or an environment-named task path |
| PE-3 | Staging | Nothing in this step stages a change; the commit path reaches the actuator and refuses with `ActuationRefusal::ExitStatus`, the designed outcome | A third actuator operation; the engine staging for itself, putting a second `std::process` site in the workspace |
| PE-4 | The target-scope collision `crates/himinbjorg/src/context.rs`'s `TARGET_SCOPE` had with the actuator's own allowlist | `"fixture-integration-branch"` added additively, keeping `"fixture-target"`, recorded as an agreement between two independently owned lists, never a derivation | Leaving the collision (no reachable push for step six); widening the actuator's own allowlist instead |
| PE-5 | The engine's own surface | One public library entry point plus a binary that calls it, so the binary becomes a genuine non-test caller | A library with no binary; a test-only driver |
| PE-6 | How the three detectors that would go red against this step are resolved | Each widened with an explicit allowlist entry naming the engine's one call site, carrying a justification and a `DECISIONS.md` reference | Raising each expected count without an allowlist |
| PE-7 | The two deferrals (the human-question gate, the loop cap) | Typed but unconstructible forms, plus a structural fixed-five sequence with a compile-time length assertion | Doc comments alone; `unimplemented!()` branches |
| PE-8 | EC-12 (witness replay) and EC-13 (a lying recorder) | EC-12 narrowed at the engine, not closed; EC-13 untouched | Closing EC-12 properly by changing `broker_authorised_action`'s signature; re-deferring both without narrowing either |
| PE-9 | Which directions the engine's own suite exercises | Both: a task naming a permitted action and one naming a disallowed action, the block attributable to a named `CheckRecord` | The allowed path only |
| PE-10 | The cognition seam's shape | A narrow one-method trait with one stub implementation | A concrete stub function replaced wholesale at step seven |
| PE-11 | How `HEIMDALL_ENGINE_TASK` is amended into REQ-31's no-configuration-surface concern (build-order step six, D114) | A third fail-closed startup precondition selecting an index into a compile-time-closed, length-asserted five-member array; REQ-31's two literal prohibitions stay intact and the load-bearing property (the selector cannot widen what is authorised) is mechanically checked | A single-process outer loop over all five members, which would amend REQ-25 in plain words (no longer at most once per process) and break REQ-30's one-outcome-to-one-exit-code contract |

## 12. Deferred, named, not built

Carried on `plans/dd/vor.md` section 7's precedent, so build-order step six
inherits these as written obligations rather than rediscovering them.

| # | Item | Where it goes |
|---|---|---|
| 1 | Staging a real change so the commit path can succeed end to end | **Discharged out of band at build-order step six (D114), not delivered by a governed path.** `ontology/tools/run_target_loop.py`, a standalone Python driver living outside `crates/`, performs the one `git add` the commit needs, before the engine binary is ever invoked. No gate adjudicated what was staged, so this is not marked simply delivered: item 12 below is the still-open, governed form this deferral becomes at build-order step seven |
| 2 | The human-question gate | Needs Gjallarhorn's protected channel and an operator-answer path, neither built. Named and typed (`EngineOutcome`'s unconstructible variant), not delivered |
| 3 | The loop cap | Needs a general transition table with more than one path to cap, which this step deliberately does not have (Gleipnir's code-enforced loop caps, D108). Named and typed (a constructorless type), not delivered |
| 4 | EC-12's open half: `broker_authorised_action` is not single use | Needs the witness taken by value, or a nonce in the audit record, both changes to `crates/himinbjorg/`, out of this step's scope. **Confirmed still narrowed at the engine only after build-order step six (D114):** each of the five separate processes that step six runs obtains at most one witness and passes it exactly once, so replay stays unreachable **through** the engine; still reachable by any other caller holding a witness |
| 5 | EC-13: a recorder reporting success while retaining nothing defeats the audit obligation | Untouched. The same class of limit as D103's limit two and D100's in-process label rewrite; nothing built here or in any prior step detects it |
| 6 | `cohort::COMMITTED_ATTESTATION`'s development-time placeholder secret (D110) | **Unchanged in kind at build-order step six (D114).** The secret was regenerated under a fresh development-time placeholder matching D110's own pattern (REQ-31 to REQ-33 of that step's spec), and the engine producing a real commit and a real push against a real remote does not upgrade that trust root. Still open |
| 7 | Concurrency safety across processes (EC-16) | **Still unaddressed at build-order step six (D114).** The out-of-band driver's five invocations run strictly sequentially, a property of the driver, not the engine, so it demonstrates nothing about safety under concurrency. The actuator still holds no lock and `MinimalDecisionRecorder` is still not concurrency hardened |
| 8 | `ActuationRefusal::PartialEffect` becoming reachable | **Still unreachable after build-order step six (D114).** Five separate processes, one operation each, so no run ever holds both a commit outcome and a push outcome to combine. Stays with whichever later step first chains two operations behind one witness |
| 9 | The credential broker's general form, the Harness Boundary Interface binding, the canary wrap for a Fenrir task | Unchanged from D111 and D112 |
| 10 | The trust-ceiling ordering and clamp (D97's open question) | Unchanged. This step adds no ranking, parsing or clamping of `trust_ceiling` anywhere |
| 11 | Flow-to-sink transitive reachability for `action_critical` | Unchanged. `gate_bridge::action_critical_for` stays the D24 agent-scoped membership test |
| 12 | Staging becomes a governed action, most likely `GitOperation::Stage { path }` with `action:git.stage` and `sink:git.stage` | Build-order step seven, triggered the moment cognition genuinely authors file content, because at that point what to stage is a consequential choice about the scope of a change rather than a fixture the operator provided. Approach B of `.opencode/plans/build-order-step-six-brainstorm.md` is the design to reach for, and merge becomes the fourth `GitOperation` variant rather than the third |

Also carried forward, stated so a reviewer can check it directly rather than
infer it: build-order step six (D114) advances invariant 3.6 only in the
narrow sense `NEUROSYMBOLIC_FILTER_INVARIANTS.md` invariant 3.6 now states,
DEMONSTRATED once, on one fixture, never PROVEN. That is not observed
end-to-end containment, which stays delegated externally (D91, D92). D108's
own definition of done is now satisfied on that one fixture run
(`TARGET_LOOP_EVIDENCE.md`): a real commit was made reachable in the git
remote's history by a real push, and three deliberately disallowed actions
were blocked by the same pipeline at three structurally distinct depths.
Staging that made the commit possible was discharged out of band, by an
ungoverned fixture step outside `crates/` (item 1 above), never by this crate
or by anything the actuator gates; governed staging is item 12's own
obligation, owed to build-order step seven.

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
