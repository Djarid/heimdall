# Detailed Design: the process engine (`crates/process-engine/`)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 3 (build-order step five of `plans/synthesis-bootstrap.md`, D108;
amended by build-order step seven, D115 to D117)
**Status of the component today:** built and tested at the fidelity this document
records. This is the repository's fifth Rust crate and the first genuine non-test
caller of `himinbjorg::validate_proposal`, `himinbjorg::broker_authorised_action`,
Himinbjörg's other three interfaces, and `hierarchy_vor::load_verified_cohort`.
**Build-order step six (D114) then ran the target loop through this crate end to
end, once, on a fixture; build-order step seven (D115 to D117) then gave the
cognition seam a second, real implementation, calling `crates/cognition-client/`
(the sixth crate) on this crate's own non-test path for the first time, and the
sections below are updated in place rather than duplicated for it.**

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
once, in array order, per call. It stays `pub(crate)`, unchanged in signature,
reachable only from `run_sequence` and from in-crate unit tests, following
`boundary-gjoll`'s registry-mandatory shell and `actuator-git`'s
single-`execute`-surface pattern.

**Build-order step seven (D115, REQ-40): the entry point's third parameter.**
`run_sequence` gains a third parameter, `CognitionBinding`, a new closed public
enum with exactly two variants (`Stub`, `Real`), and stays the crate's **one**
public library entry point: no second entry point is added, and
`run_sequence_with_cognition` keeps its exact `&impl CognitionStep` signature.
`run_sequence` resolves the binding to a concrete implementation and makes
exactly one call to `run_sequence_with_cognition`; the match on the binding is
the only place in the crate that reads it, and no code downstream of the
cognition step branches on it. Every step after cognition is byte for byte
identical for both bindings: one `validate_proposal` call, the witness passed
straight through, one `broker_authorised_action` call where reached, and the
refusal carried through verbatim. This is an addition to the entry point's
signature, not a widening of what any step decides; every step's own
implementation (`accept_task`, `run_gate`, `run_execute`) stays `pub(crate)`,
unchanged.

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
forced to satisfy an operation it has no use for. At build-order step five,
exactly one implementation existed, `DefaultCognitionStep`, whose output is
built from hardcoded named constants declared in `cognition.rs`, each carrying
its own `const _: () = assert!(...)` non-emptiness assertion, on
`context::TARGET_SCOPE`'s own precedent. The stub reads no file, reads no
environment variable, opens no socket and consults no configuration surface on
the process path: there is no configuration file, no environment override and
no manifest through which the guarded population could change what cognition
proposes (D105 row H5).

**Build-order step seven (D115, REQ-28, REQ-36 to REQ-39): the trait's `Result`
contract, and a second, real implementation.** `CognitionStep::propose` now
returns `Result<CognitionOutput, CognitionRefusal>` rather than
`CognitionOutput` directly. This is a change to the trait's contract, recorded
here as one rather than glossed as an addition: the change is required, not
merely preferred, because with no error channel an implementation that cannot
reach the model must return SOME `CognitionOutput`, and the natural degraded
value, an empty `parameters` vector, produces a proposal the rule core
authorises (`gate_bridge` builds an empty `consumes` map, `rule::apply`'s
per-parameter loop body never runs, `reasons` stays empty, `authorised` is
`true`, and check five records `Pass`). A model-call failure that degraded
this way would have turned a designed block into a real, executed commit
attributed to a model that was never reached; making refusal expressible in
the trait's own return type is what keeps that unreachable (section 2.2
finding one of `.opencode/plans/build-order-step-seven-spec.md`). `CognitionRefusal`
is a new type carrying a bounded diagnostic, never described as an
authorisation decision; `EngineOutcome::CognitionRefused` carries it through
verbatim (section 3 above and `outcome.rs`).

`RealCognitionStep` is the new, named, real implementation: its `propose`
calls `cognition_client::obtain_message` (`crates/cognition-client/`, the
sixth crate, section 8 below), receives the validated message, and constructs
exactly one `himinbjorg::ProposalParameter` carrying it, declared
`ConsumeMode::Action` and `TrustLevel::Tainted` from two named constants in
this crate's own `cognition.rs`, `REAL_CONSUME_MODE` and `REAL_TRUST_LEVEL`.
It constructs no other parameter and returns no other output shape, and its
`Ok` value never carries an empty `parameters` vector: every path either
returns exactly one parameter or returns `Err`. **REQ-35's load-bearing
property, stated in the type's own shape rather than left to review:** this
implementation never names, imports or references `DefaultCognitionStep`,
holds no `Option<&dyn CognitionStep>` fallback field, and contains no
`unwrap_or`, `unwrap_or_default` or `unwrap_or_else` producing a
`CognitionOutput`. Every one of `cognition_client::obtain_message`'s own
eleven refusal conditions (`plans/dd/cognition-client.md` section 4) maps to
`Err` here, never to a default, cached or partial `CognitionOutput`.

**The trust declaration, verified against the lattice's own terms rather than
asserted.** `ontology/yggdrasil/spine/trust.py`'s own module docstring states
the entry rule without ambiguity: "Untrusted-derived content enters as TAINTED
and stays TAINTED unless something promotes it; nothing in the loaded ontology
promotes it automatically". `Vouched` is reached only by traversing a
`PROMOTES_TO` edge after a logged promotion event, and no promotion mechanism
exists anywhere in this repository today: `STATUS.md` section 6 names Gjöll's
own promotion and re-validation gate as queued and not started. Declaring
anything above `Tainted` for model output would therefore assert the outcome
of a promotion event that never happened, so `TrustLevel::Tainted` is the
honest entry level, and every proposal carrying this parameter blocking at
check five (`boundary_gjoll::rule::apply` tests `c.trust_level ==
TrustLevel::Tainted` in both arms) is the designed outcome of this step, not a
defect.

**A named residual this verification surfaced, not closed, narrowed or
mitigated by this step.** `rule::apply` tests untrusted-derivation by equality
against `TrustLevel::Tainted` alone, not by a rank comparison against
`spine.trust.TRUST_ORDER`'s own `rank` attribute. A parameter declared
`Vouched`, one step up and still explicitly "not yet fully trusted", would
pass check five silently under both the `Action` arm and the `Inert` arm.
Nothing in the workspace exercises this today, because every parameter
constructed anywhere in `crates/` is `Canonical` before this step and
`Tainted` after it, so this is a latent gap rather than a live hole. No line
of `crates/boundary-gjoll/` changes to address it: widening the equality test
to a rank comparison is an authorisation-path edit to the rule core that would
re-baseline `crates/hierarchy-vor/vectors/cohort_vectors.json`'s golden gate
vectors if their expectations moved, and it belongs with the promotion gate
that gives the intermediate trust levels a meaning, not inside a cognition
build. The mitigation this step supplies instead is detection, not closure:
`REAL_TRUST_LEVEL`'s and `REAL_CONSUME_MODE`'s values are pinned by
`ontology/tests/rust_cognition_client_harness.py`, so a later softening to
`Vouched` is a build-visible, reviewed edit rather than a silent one. See
section 12, item 13, below.

**The consume mode, and the honest counter-argument stated alongside the
ruling.** `ConsumeMode::Action` is chosen because the parameter is declared at
a sink whose declared effect primitive is `EffectPrimitive::RunOrChangeCode`,
and a commit message is part of the commit object that effect produces, not a
log entry recorded beside it; declaring `Inert` on a value D24 agent-scoped
derivation has already marked action-critical is precisely the claim D89-A
exists to distrust. The honest counter-argument: the message does not itself
determine whether a commit occurs, and in the system as built it reaches no
argument vector at all (`himinbjorg::ProposalParameter` has no value field,
and `broker::operation_for` maps `action:git.commit` to its own hardcoded
`FIXED_COMMIT_MESSAGE`, never to anything carried on a proposal parameter),
so a reader can reasonably read the message as a payload rather than an
instruction. That reading is real and it is outweighed, not dismissed, by the
grounds above. **No requirement, doc comment, harness message, transcript,
evidence document, decision row or passage of this document states or implies
that a model-authored value reaches an argument vector, the actuator or any
git process in the system as built.** This is a named observation for a later
step to inherit, restated in section 12, item 14, below: the risk this
counter-argument names is a *future* risk, live only once the broker takes a
commit message from the proposal rather than from `FIXED_COMMIT_MESSAGE`.

Cognition is advisory and never adjudicative, which is why a substitutable trait
here does not repeat `crates/actuator-git/`'s own rejection of a trait at the
actuator invocation (D112, GA-1's declined alternative), and this holds for
both implementations equally: whichever one supplies the proposal, it still
passes through `validate_proposal`'s six checks and the witness match, and no
branch anywhere derives a permission, a scope, a target-scope membership or a
check outcome from cognition's output. A substitutable **execution** path
would create exactly the seam an attacker wants, which is why
`broker_authorised_action` stays a concrete call and the sequence itself is
not behind a trait at all. A substitute implementation that proposes a
deliberately disallowed action is still blocked at the gate, attributable to
a named `CheckRecord`, which is the property that makes the trait acceptable
here where it was rejected one layer down, and build-order step seven
exercises this for real for the first time: `RealCognitionStep`'s own
proposal is genuinely blocked, attributable to check five's own
`ActionOnActionCriticalTainted` reason.

`DefaultCognitionStep` is retained, byte for byte unchanged in logic from
build-order step five, with a doc comment gaining its current function and
its expiry trigger, stated together rather than left implicit: it exists to
supply the one positive control the real implementation cannot supply while
an honest declaration blocks every model-authored proposal, and it becomes
redundant once Gjöll's own promotion and re-validation gate lands, at which
point deleting it is a single, clean edit rather than a load-bearing change.
This is D116's own subject, an amendment to D108's literal word "replace"
rather than a claim of compliance with it: the stub is joined, not replaced,
precisely so step six's own executed commit and push stay live and
re-runnable on a machine with no model at all (section 12, item 15, below).

One function, `proposal::build_proposal`, and only one, turns a task plus a
cognition output into a `himinbjorg::Proposal`; it is the only `Proposal`
construction site in the crate, and every field it sets comes from the task,
from either cognition implementation's own output or from a named engine
constant, never from reading Himinbjörg's own gating constants. No line of
this function changes for build-order step seven: it already copies the whole
`parameters` vector verbatim, so a second implementation producing a
differently-declared parameter needed no change here.

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

**Build-order step seven (D115, REQ-38): this section is restated as still
holding, unamended.** `startup.rs` remains the one module in
`crates/process-engine/` that reads the process environment, and it still
reads exactly three variables. The two path-shaped environment values the
sidecar needs (the interpreter path, the package root) are read inside
`crates/cognition-client/`'s own invocation module, at cognition time, never
in `startup.rs`, and never as a fourth startup precondition. This placement
is load bearing, not stylistic: a fourth startup precondition would refuse
*before* any member runs, so on a machine without `poc/.venv` and the model
weights the binary could no longer run the two stub-bound positive-control
members either, and build-order step six's own demonstrated commit and push
would stop being reproducible. `CognitionBinding` itself (section 3 above) is
a compile-time field of each task member, never something `HEIMDALL_ENGINE_TASK`
carries or varies: the selector still supplies no action name, no target, no
sink, no declared cost, no task identifier and no cognition binding, exactly
as PE-11 and REQ-44 already required, restated here rather than left to
imply that the new binding might have widened what the selector expresses.

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
  the `ActuationRefusal` variant recoverable from an `ActuatorRefused` payload;
- **build-order step seven (D115): the cognition step's own refusal.** When
  `CognitionStep::propose` returns `Err`, the sequence never reaches the gate
  this run at all: it maps to `EngineOutcome::CognitionRefused`, a new,
  distinct outcome (section 3 above), never described as an authorisation
  decision and never merged with `RefusedBeforeCognition` (a model-call
  failure and an empty task identifier are different failure classes,
  genuinely warranted as separate outcomes rather than convenient ones,
  because conflating them would make a model-call failure indistinguishable
  from a structural well-formedness defect in both the outcome and the exit
  code).

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
- `main.rs`'s seven task constant-sets (widened from five at build-order step
  seven, D115: the two existing allowed members, the three existing
  disallowed members, plus the two new model-bound members, M1 a commit and
  M2 a merge, section 3 above), its compile-time-length-asserted array of
  them, and its named exit-code constants, now six rather than five
  (`EXIT_COGNITION_REFUSAL = 5` added, every existing constant's name,
  meaning and value unchanged).
- `startup.rs`'s `TASK_SELECTOR_ENV_VAR` and the closed, compile-time set of,
  now, seven accepted selector names it resolves against (widened from five
  at build-order step seven).
- `cognition.rs`'s two named declaring constants for the real implementation,
  `REAL_TRUST_LEVEL` and `REAL_CONSUME_MODE` (build-order step seven), each
  with its own doc comment stating the ruling and, for the consume mode, the
  honest counter-argument (section 4 above).

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
- **Build-order step seven (D115, D117): a fourth in-workspace path
  dependency, `cognition-client`, added to the disclosed three.**
  `crates/cognition-client/` (the sixth crate, `plans/dd/cognition-client.md`)
  knows nothing of proposals, parameters, trust levels or consume modes: it
  exposes one plain function (`obtain_message`) plus one validated value type
  plus one refusal type, and this crate's own `cognition.rs` is the one place
  that calls it, receives the validated message, and constructs the one
  `Tainted`/`Action` `ProposalParameter` carrying it. The arrow runs one way,
  this crate to `cognition-client`; that crate's own `[dependencies]` table
  stays empty. `crates/process-engine/` still never depends on `actuator-git`,
  never names `actuator_git::` anywhere in its own source, and never calls
  `boundary_gjoll::consequentiality::evaluate` or any other Gjöll gate
  function directly: the load-bearing property that the gate is reached only
  through `validate_proposal` is intact. See `plans/rust-workspace-baseline.md`
  section 4 for the sixth-crate dependency ruling this extends, and D117 for
  the separate `std::process` reopening this new dependency's own crate makes.

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

**Build-order step seven (D115 to D117) then made this crate the first
non-test caller of a language model.** A new sixth crate,
`crates/cognition-client/`, is added to the workspace (section 8 above,
`plans/dd/cognition-client.md`). Inside this crate: `cognition.rs` gains the
trait's `Result` contract, `CognitionRefusal`, the two declaring constants and
the second, real implementation (section 4 above); `sequence.rs` gains the
`CognitionBinding` third parameter and one new match on it (section 3 above);
`outcome.rs` gains the sixth variant and exit code (section 6 above);
`main.rs` gains the cognition-binding field on `EngineTaskMember`, the two new
members M1 and M2, the length assertion widened to seven, and the
pairwise-distinctness assertion widened to all 21 pairs over seven names;
`startup.rs` gains nothing beyond `ACCEPTED_SELECTOR_NAMES` widening to seven,
restated in its own doc comment as still reading exactly three environment
variables (section 5 above). Three existing live invocation detectors are
widened again, on exactly the axes their own build spec's Finding Three
names, never by a silently raised count: `ontology/tests/rust_process_engine_harness.py`'s
`PERMITTED_DEPENDENCIES` widens from three names to four, naming
`cognition-client`; `ontology/tests/rust_target_loop_harness.py`'s hardcoded
task-array cardinality (the length-assertion expectation, the per-member
assertion-count minimum, and `startup.rs`'s array shape) widens from five to
seven everywhere it is pinned, and its selector-derivation helper is widened
to the amended rule (section 3, REQ-48 of the build spec). A new standalone
Python sub-harness, `ontology/tests/rust_cognition_client_harness.py`, on
`rust_process_engine_harness.py`'s exact shape, folds additively into
`ontology/tests/harness.py` as `run_rust_cognition_client`.
`crates/actuator-git/`, `crates/boundary-gjoll/`, `crates/hierarchy-vor/` and
`crates/himinbjorg/` all remain unchanged by this step too, confirmed by
direct inspection; so does `TARGET_LOOP_EVIDENCE.md` and its own pinned
SHA-256, and so does every file under `ontology/nornir/`, `ontology/yggdrasil/`
and `poc/symbolic.py`.

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

**Build-order step seven (D115) added to this test plan, not replacing it:**
`unit_tests/cognition_and_proposal.rs` gains cases for the `Result` contract
(a substitute cognition step returning `Err` maps to `CognitionRefused`, never
to a degraded `CognitionOutput`), the real implementation's never-empty
`parameters` property, and the parameterless-proposal case that documents why
that property matters (a `Proposal` built from an empty `CognitionOutput`
still authorises at check five, the failure mode REQ-37 exists to make
unreachable). `unit_tests/sequence_shape.rs` and
`unit_tests/startup_failclosed.rs` gain cases for the binding parameter, the
sixth outcome variant, and the seven-name accepted selector set, extending
rather than replacing their existing intent. `tests/public_surface.rs` gains
the sixth exit constant's and the sixth variant's reachability, and confirms
`run_sequence` is still the crate's one public entry point, now taking three
parameters. **No test in this crate or in `crates/cognition-client/` runs a
real model call and asserts a fixed outcome from it:** the definition-of-done
evidence (M1 and M2's own block, P1 and P2's own execution) is confirmed by
hand from a real run and recorded in `COGNITION_EVIDENCE.md`, per the build
spec's own instruction that no test is to be written that fakes a real model
call. **Observed at the time of writing, this step's own session:** `cargo
test --workspace` passes 258 tests across all six crates, zero failures (180
pre-existing plus 78 new: 53 in the wholly new `crates/cognition-client/`, 25
in this crate's own widened suite); `python3 -m ontology.tests.harness`
reports exactly 22 critical findings, all false-inert, with the new
`run_rust_cognition_client` obligation passing; the invariant 3.1 guard
reports 34 scanned files, 13 allowed import roots, zero violations, unchanged
because `crates/` and the new top-level `cognition/` Python package both sit
outside its scan roots; `ontology.tests.pipeline_score_harness` reports 48
percent layer one and 33 of 33 (100 percent) pipeline containment, unchanged;
`ontology.tests.gjoll_invocation_harness` reports six test call sites and zero
non-test call sites, unchanged. See `DECISIONS.md` D115 to D117 for the full
figures and the line-budget outcome.

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
| PE-12 | REQ-10's own "no code is keyed on which member was selected" (build-order step seven, D115) | Amended, not glossed as compliance: the load-bearing property REQ-10 protects (no member is *adjudicated* differently) is preserved and mechanically checked, because every member passes through the identical five steps, six checks, witness match and actuator allowlist, and nothing downstream of cognition reads the binding; what is amended is the literal reading, since one compile-time field of the selected member (`cognition_binding`) is now read, once, to choose between two implementations of a seam that decides nothing about authorisation | Treating the binding field as compliant with the unamended literal wording, which would misstate what changed |
| PE-13 | The trait's error channel (build-order step seven, D115, ST7-8) | `CognitionStep::propose` returns `Result<CognitionOutput, CognitionRefusal>`; a new `EngineOutcome::CognitionRefused` variant and `EXIT_COGNITION_REFUSAL = 5` | Keeping the infallible signature and returning a degraded `CognitionOutput` on failure, which converts the designed block into an executed commit (section 2.2 finding one of the build spec); panicking, which puts a panic on an authorisation-adjacent path |
| PE-14 | D108's own word "replace" for this step (build-order step seven, D116) | Amended: the stub is joined, not replaced, `DefaultCognitionStep` retained byte for byte as a named positive control with a stated expiry trigger (Gjöll's own promotion and re-validation gate landing) | Deleting the stub outright, which would leave nothing anywhere in this build reaching `EngineOutcome::Executed` and no live positive control on a machine with no model |

## 12. Deferred, named, not built

Carried on `plans/dd/vor.md` section 7's precedent, so build-order step six
inherits these as written obligations rather than rediscovering them.

| # | Item | Where it goes |
|---|---|---|
| 1 | Staging a real change so the commit path can succeed end to end | **Discharged out of band at build-order step six (D114), not delivered by a governed path. Still not delivered by a governed path after build-order step seven (D115).** `ontology/tools/run_target_loop.py`, a standalone Python driver living outside `crates/`, performs the one `git add` the commit needs, before the engine binary is ever invoked. No gate adjudicated what was staged, so this is not marked simply delivered: item 12 below is the still-open, governed form this deferral becomes, and its trigger is honestly not met by step seven either, because cognition authors a commit message only, no file content |
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
| 12 | Staging becomes a governed action, most likely `GitOperation::Stage { path }` with `action:git.stage` and `sink:git.stage` | **Still deferred after build-order step seven (D115).** Its own trigger, the moment cognition genuinely authors file content, is honestly not met: build-order step seven's cognition authors a commit message only, no file content, so this item's trigger stays intact and unmet, carried to whichever step first has cognition author file content. Approach B of `.opencode/plans/build-order-step-six-brainstorm.md` is the design to reach for, and merge becomes the fourth `GitOperation` variant rather than the third |
| 13 | The filesystem-write obligation the build-order-step-seven brainstorm's own section 1.2 names, logically preceding item 12 | **Named as its own item here for the first time (build-order step seven, D115), not folded into item 12.** Before any governed write to the working tree can exist, the engine (or whatever component eventually performs one) needs its own fail-closed contract for what may be written and where; item 12's staging obligation presumes content already exists on disk, and this item is the precondition that content genuinely being authored, rather than staged, would need. Neither item's trigger is met by build-order step seven: cognition authors a commit message only |
| 14 | The equality-versus-rank residual in `boundary_gjoll::rule::apply` (`c.trust_level == TrustLevel::Tainted` by equality, never a rank comparison against `TRUST_ORDER`) | **Named, not closed, narrowed or mitigated, by build-order step seven (D115).** A parameter declared `Vouched` would pass check five silently under both arms; nothing exercises this today because every parameter constructed anywhere in `crates/` is `Canonical` before this step and `Tainted` after it. Belongs with Gjöll's own promotion and re-validation gate, which gives the intermediate trust levels a meaning; no line of `crates/boundary-gjoll/` changes to address it here. Detected, not fixed: `REAL_TRUST_LEVEL`'s value is pinned by the new sub-harness, so a later softening is build-visible |
| 15 | Section 2.2 finding five of the build-order-step-seven spec: the model-authored message reaches no argument vector today, so Pre-Mortem risk five (a newline or control character in a model-produced message reaching `argv.rs`'s fixed shape) is a **future** risk, not a present one | **Named as a future-conditional risk (build-order step seven, D115), never described as defended against a live reachability that does not exist.** Becomes live only if a later step changes `broker::operation_for` to take the commit message from the proposal rather than from `FIXED_COMMIT_MESSAGE`; if that step arrives, `crates/cognition-client/`'s own validator (`plans/dd/cognition-client.md` section 5) is already at least as strict as `argv.rs`'s `ValueKind::Message` policy, so this item is a readiness note, not an open vulnerability |

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

**Build-order step seven (D115 to D117) advances invariant 3.6 only in a
different, narrower sense again, stated here rather than left to imply
otherwise.** `boundary_gjoll::rule::apply` raises a reason in the live Rust
path for the first time, at a fourth structurally distinct depth (check
five's `ActionOnActionCriticalTainted`, naming a genuinely model-authored
parameter), but no new containment is observed, no third-party corpus is run
and no flow-to-sink transitive reachability is added, so the
DEMONSTRATED-once status this document already carries is not upgraded and
is never marked PROVEN. Gjöll's own Python gate functions
(`ontology/nornir/gjoll.py`) still have zero non-test callers, unchanged.
This step does not claim Heimdall authored a change (cognition authors a
commit message only) and does not claim Heimdall executed a model-authored
commit (every `Executed` outcome comes from a stub-bound member; both
model-bound members block). The equality-versus-rank residual (item 14 above)
and the `CognitionBinding::Real` end-to-end test-coverage gap (deferred item
4 of `plans/dd/cognition-client.md` section 11) are both named explicitly as
not closed, per this document's own honesty-over-reassurance convention: the
first is a latent gap in the rule core's own trust-level test, and the
second is a stated limit rather than an oversight, because the build spec's
own instruction is that no test is to be written that fakes a real model
call.

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
