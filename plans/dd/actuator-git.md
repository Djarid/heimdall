# Detailed Design: the git actuator (`crates/actuator-git/`)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 3 (build-order step four of `plans/synthesis-bootstrap.md`, D108)
**Status of the component today:** built and tested at the fidelity this document
records. This is the repository's fourth Rust crate and, wired behind Himinbjörg's
witness-carrying entry point, the first crate in this project's history able to
perform a real, gated, executed action.

---

## 1. Purpose

The git actuator executes exactly two operations, a local commit and a push, by
shelling out to the system `git` binary with a fixed, validated argument vector. It
is the fill for the one actuator slot `plans/dd/himinbjorg.md` section 6.1 named and
left unimplemented at D111: `broker_action`'s dispatch seam. This document takes that
slot, and the crate that fills it, to implementation fidelity.

It executes only what has already been authorised. It adjudicates nothing: every
decision about whether an action is permitted is made upstream, by
`validate_proposal`'s six checks (including the real `boundary_gjoll::consequentiality::evaluate`
call at check five), and by the witness that decision mints. The actuator's own job
is narrower than that decision and comes after it: turn an already-authorised
operation into a git process, run it under a controlled environment, and report
honestly what happened.

Shelling out to `git` is not a boundary violation. D108's own text settles this: the
boundary principle governs what adjudicates an action, never mutable and never
interpreted, not every process a compiled binary may invoke, and `git` is a
compiled, externally audited tool invoked deterministically with fixed arguments.
The actuator interprets nothing and evaluates nothing.

## 2. Responsibilities and boundaries

In scope:

- Turn one of two closed operations, a commit or a push, into one fixed,
  positive-match-validated argument vector, and spawn `git` directly with it.
- Own a hardcoded, non-empty, positive-match allowlist of permitted push targets.
- Resolve and validate the working repository the actuator operates on, from an
  environment-named path, never from the inherited working directory or a path
  baked into the binary.
- Spawn the process under a controlled environment, a bounded wall-clock limit,
  and honest exit-status mapping, and report a success or a refusal distinctly.
  The refusal vocabulary also names the partial-effect case (a commit that
  succeeded followed by a push that refused) as a category distinct from a
  success or nothing having happened, but no call this crate makes can produce
  it at this fidelity (section 13, deferred item 13): naming the category is
  in scope for this step; making it reachable is not.

Out of scope, named rather than smoothed:

- **It adjudicates nothing.** No cohort, no sink registry, no scope and no gate
  logic reaches this crate: its `[dependencies]` table is empty, so it cannot even
  name `himinbjorg`, `hierarchy-vor` or `boundary-gjoll`, let alone call into any
  of them (REQ-2). Authorisation is entirely `himinbjorg`'s concern, upstream of
  this crate.
- **It is not a general command-execution sandbox.** `execute` is a fixed,
  two-operation entry point, not an actuator for arbitrary tools or commands
  (deferred item 2, section 13).
- **It does not verify the identity of the resolved `git` binary.** It trusts
  whatever `git` resolves to on `PATH`, the same class of trust root as
  Hliðskjálf's signing key (EC-2).
- **It is not the audit log.** The decision that authorised its invocation is
  written to Himinbjörg's own minimal audit seam (`crates/himinbjorg/src/audit.rs`,
  section 6 below) before the actuator is ever called; this crate itself records
  nothing.

## 3. The two operations

The actuator's whole public operation vocabulary is a closed, two-variant enum,
`GitOperation`: a commit, carrying its message, and a push, carrying its remote and
ref (REQ-8). No third operation exists and none is reserved for one. In particular
the crate never invokes `add`, `checkout`, `fetch`, `rev-parse`, `config`, `remote`,
`status` or `reset`, and it never chains a second git process to discover the
result of the first, so `execute` neither stages a file to make a commit possible
nor fetches to reconcile a rejected push. A future third operation (a merge, per
D108's own dogfooding text) is added as a new variant with its own fixed argument
shape when a real workflow needs it (section 9.1 of the build spec's Open/Closed
analysis), never by widening one of the two that exist.

`execute(operation: &GitOperation) -> Result<ActuationOutcome, ActuationRefusal>` is
the crate's single public entry point. Everything else the crate exposes,
`GitOperation`, `ActuationOutcome` and `ActuationRefusal`, is a value shape or a
refusal vocabulary; the argument-vector construction (`argv`), the permitted-ref
allowlist (`targets`), the working-repository resolution (`repo`) and the process
spawn (`execute`'s own internals) are all `pub(crate)`, reachable only through
`execute`.

A success (`ActuationOutcome`) names only which operation ran, `Committed` or
`Pushed`, and nothing it did not observe: no commit identifier, because obtaining
one would need a third git operation the closed set forbids, and no field derived
from parsing git's own output. The refusal vocabulary names the partial-effect
case, a commit that succeeded followed by a push that refused
(`ActuationRefusal::PartialEffect`), as a category that must be reported neither
as a success nor as nothing having happened, because a local commit is a real
effect that happened. That variant is named and typed today but currently
unreachable: `execute` performs exactly one operation per call (REQ-8), so no
call ever holds both a commit outcome and a push outcome to combine, and the
crate's one non-test caller authorises and executes exactly one operation per
witness on the same grounds. See section 13, deferred item 13.

## 4. The argument-safety contract

Every caller-supplied string that reaches an argument vector is validated by one
function, `argv::validate_value`, before any process is spawned, and a string
failing validation refuses fail closed with `ActuationRefusal::InvalidArgument`
(REQ-11). The validation is a positive-match allowlist, never a denylist: a string
is refused unless every character in it is explicitly permitted, so no enumeration
of forbidden shapes is needed or present anywhere in the crate. This is the
argument-safety ruling this document's own decisions table (section 12, GA-6)
records: the corpus sources `.opencode/plans/git-actuator-step-four.md` section 15
cites (the `ultralytics/actions` compromise, `tj-actions/branch-names` CVE-2023-49291,
the Home Assistant branch-name review) each show a real incident in which a git ref
or branch name, itself restricted to git's own legal character set, achieved
command execution once concatenated into a shell command; enumerating the
metacharacter shapes those incidents used would be exactly the blacklist trap
invariant 3.5 names, one layer over, so validation grants nothing by default and
denies everything not named.

The shared structural rule, applied to every value position regardless of kind:
non-empty, no leading hyphen, no NUL byte, no newline, no carriage return and at
most 4,096 bytes. What differs by position is the per-character allowlist:

- A ref or remote name is restricted to git's own conventional character set
  (alphanumeric, hyphen, underscore, dot, slash).
- A commit message is permitted the whole printable ASCII range plus the space,
  because it never reaches a shell (no shell is invoked on any path, REQ-10) and
  never occupies the target allowlist's position, so the shared structural checks
  (no leading hyphen chief among them) remain its load-bearing defence.

No shell is invoked anywhere: `git` is spawned directly with a constructed
argument vector (`Command::new("git").args(argv)`), never via `sh -c`, `bash -c`,
`cmd /c`, or a string built up and handed to an interpreter (REQ-10). No
caller-supplied string can occupy an option position: a value beginning with a
hyphen is refused by the shared structural check rather than escaped, and for
`git push`, which supports an end-of-options separator, the fixed argument shape
places `--` before the first value position (`["push", "--", <remote>,
<ref_name>]`), so neither `remote` nor `ref_name` can be read as an option even in
principle. `git commit`'s `-m` has no comparable second value position to guard
this way, so the load-bearing defence for the commit message is the leading-hyphen
refusal itself (REQ-12).

The commit message is never written to a file the actuator creates, never
templated into a larger string, and reaches exactly one value position of one
fixed shape (`["commit", "-m", <message>]`); taken with the no-shell property
above, this closes REQ-13's three clauses together.

## 5. The target allowlist

The actuator owns a hardcoded, non-empty, positive-match allowlist of permitted
push targets, as `(remote, ref)` pairs (`targets::PERMITTED_TARGETS`, REQ-14).
Membership is checked as a pair: a remote and a ref individually present in the
list, but not together, is not a match. The list's non-emptiness is asserted at
compile time, so an edit emptying it fails the build rather than making every push
refuse silently at run time.

`main` and `master` are absent from the allowlist. That absence is the whole
mechanism that blocks a push to either branch (REQ-15): a target earns membership
by a positive match, and neither name ever earns one. A second, explicit refusal on
a named protected-ref list (`targets::PROTECTED_REFS`) exists as defence in depth
only, structurally unreachable given the allowlist's own construction, following
`DefinitionRefusal::EmptyIntersection`'s precedent of naming a defence-in-depth arm
honestly rather than presenting it as the protection (REQ-16). It must never be
described anywhere as the mechanism.

`hierarchy_vor::CohortDefinition`'s shape is untouched by this allowlist: no
`permitted_targets` field, no protected-branch list and no fifth content field is
added to it, so `COMMITTED_ATTESTATION` and its ten committed golden vectors all
stay valid (REQ-17). The cohort's own `permitted_targets` field, and the load-time
manifest that would let a second cohort choose a different allowlist, both stay
deferred (section 13, item 1).

## 6. The working-repository contract

The working repository the actuator operates on is resolved from a path named by
one environment variable (`HEIMDALL_ACTUATOR_GIT_WORKING_REPO`), never from the
inherited current working directory and never from a path baked into the binary,
following D110's out-of-tree convention that an environment variable names a
**path**, never a secret (REQ-18). Resolution refuses fail closed, never defaults,
on each of five conditions, checked in this order (REQ-19):

1. the variable is absent or set to the empty string;
2. the named path does not exist, or its metadata cannot be read;
3. the path exists but is not a directory;
4. the directory carries no git repository marker (no `.git` entry); and
5. the path resolves, after canonicalisation on both sides, inside this
   repository's own working tree.

The fifth condition is a development-time guard against the actuator committing to
the repository that houses it, not a deployment control, and its own documentation
says so rather than presenting it as one; it is derived from `CARGO_MANIFEST_DIR`,
a path baked in at compile time on the machine that built the binary, so it is
vacuous by construction on a binary built here and run elsewhere. This mirrors
`hierarchy_vor::authoriser`'s identical `repo_root` precedent and identical honesty
about the same limit.

Every spawned process is given the resolved working directory explicitly
(`Command::current_dir`); no operation relies on the parent process's own current
directory (REQ-20).

## 7. Fail-closed behaviour

Inside the actuator, every one of the following refuses rather than defaulting to
a success or a partial success:

- a caller-supplied string failing the argument-safety contract (section 4);
- a push target absent from the permitted allowlist, or present individually but
  not as a pair (section 5);
- any one of the five working-repository resolution conditions (section 6);
- a spawn failure (the `git` binary absent from `PATH`, never a fallback to a
  second candidate path);
- the process not exiting within the bounded wall-clock limit (terminated on
  expiry);
- a non-zero exit status, or a status the platform reports as absent (a signalled
  process), never treated as a success or a partial success.

The vocabulary also names the partial-effect case (a commit that succeeded, a
push that then refused) as one that must be reported distinctly rather than as
a success or as nothing having happened, but no path through this crate today
constructs it: `execute` performs exactly one operation per call, so no single
call ever holds both outcomes to distinguish (section 13, deferred item 13).

Upstream, inside `himinbjorg::broker::broker_authorised_action`, three further
gates run before the actuator is ever reached, and a failure at any of them
refuses without invoking the actuator at all: the credential-scope check (real,
run first, identical to `broker_action`'s own), the witness match (byte equality
on action name and target between the brokered action and the supplied
`Authorisation`), and the audit write (section 8). The ordering of the third gate
is structural, not a convention held by comment: the actuator call is reachable
only from a point that already holds the audit write's successful result.

The process's captured standard output and standard error are treated as
untrusted throughout: they may be carried into a size-bounded diagnostic string on
a refusal path only, and no branch anywhere in either crate parses, classifies or
derives a control-flow decision from them.

## 8. Data owned

The actuator itself owns no persistent state, no world model and no audit record.
What it owns is entirely in-memory and compiled in:

- `targets::PERMITTED_TARGETS`, the hardcoded permitted push-target allowlist, and
  `targets::PROTECTED_REFS`, the defence-in-depth list.
- `repo::WORKING_REPO_ENV_VAR`, the name of the environment variable that carries
  the working repository's path (never the path itself, never a secret).
- The named constants governing the argument-safety contract (`argv::MAX_VALUE_LEN`)
  and execution (`execute::EXECUTION_TIMEOUT`, `execute::MAX_DIAGNOSTIC_BYTES`).

The decision record HB-6 requires is owned by `himinbjorg`, not by this crate:
`crates/himinbjorg/src/audit.rs`'s `DecisionRecorder` trait and its one minimal
implementation, `MinimalDecisionRecorder`, append one `RecordedDecision` (the agent
id, the action, the decision, the six `CheckRecord`s) per successful write, in
process only, unsigned, unchained and not durable. `entry_id`, `timestamp`,
`world_model_state_hash` and `signature`, the fields `plans/dd/hlidskjalf.md`
section 3.1 names, are absent from `RecordedDecision`, not merely empty: there is
no Rust Hliðskjálf, no Rust Mímisbrunnr and no signing key at this fidelity for any
of the four to be derived from.

## 9. Dependencies

- **Upstream (the crate's only non-test caller):**
  `himinbjorg::broker::broker_authorised_action`, called at most once per brokered
  action, after the credential-scope check, the witness match and the audit write
  have all already passed (`ontology/tests/actuator_invocation_harness.py` reports
  this live: exactly one non-test call site, the allowlisted one). `broker_action`
  itself never reaches this crate: its three arguments carry no authorisation
  evidence.
- **Downstream (what this crate itself depends on):** nothing inside the
  repository. `[dependencies]` is empty (REQ-2); the crate depends only on the
  Rust standard library, and, at run time rather than as a Cargo dependency, on
  whatever binary the host resolves as `git` on `PATH`.
- The dependency direction between the two crates is one way: `himinbjorg`
  depends on `actuator-git`, never the reverse, so the actuator cannot be tempted
  to re-derive authorisation and knows nothing about the cohort, the sink
  registry or the gate (section 2).

## 10. Build delta from today

Before this step, `himinbjorg::broker_action` dispatched to a single actuator slot
that was unimplemented, so every call refused `NoActuatorAvailable` and nothing
built so far could execute anything (D111). This step fills that slot without
changing `broker_action`'s signature, by building a new crate and a new,
witness-carrying sibling entry point rather than widening `broker_action` itself
(GA-1):

- **`crates/actuator-git/`, the repository's fourth Rust crate.** Five modules,
  each with one reason to change (section 9.3 of the build spec): `types` (the
  operation, outcome and refusal vocabularies), `argv` (the fixed argument shapes
  and the value validator), `targets` (the permitted-ref allowlist), `repo` (the
  working-repository resolver) and `execute` (the process spawn, the only module
  in the whole workspace that touches `std::process`, REQ-7). `[dependencies]` is
  empty; the crate carries `#![forbid(unsafe_code)]` at file scope with no
  `unsafe` keyword anywhere in its source.
- **`himinbjorg` gains a third in-workspace path dependency, `actuator-git`**
  (GA-3), widening `plans/rust-workspace-baseline.md` section 4's HB3-3 passage
  and the dependency-posture allowlist by one name (section 4 of that document,
  updated alongside this row).
- **An opaque `Authorisation` witness** (`crates/himinbjorg/src/types.rs`),
  mintable only by `validation::validate_proposal` and only when its decision is
  `Decision::Allow`, following `hierarchy_vor::VerifiedCohort`'s precedent for a
  type with no public constructor, no `Clone`, no `Copy`, no `Default` and no
  escape hatch (REQ-26 to REQ-28).
- **`himinbjorg::broker_authorised_action`**, the witness-carrying sibling entry
  point (GA-1): the credential-scope check, the witness match, the audit write,
  then the single non-test call site of `actuator_git::execute` in the whole
  repository. `broker_action` itself keeps its exact three-argument signature and
  stays refuse-only forever (REQ-30): its refusal reason is corrected from
  `NoActuatorAvailable`, which would now be a false statement, to
  `NoAuthorisationEvidence`.
- **`crates/himinbjorg/src/audit.rs`**, HB-6's audit seam at minimal fidelity
  (GA-2): the `DecisionRecorder` trait, one method, and `MinimalDecisionRecorder`,
  the one append-only implementation this step provides, with no update and no
  delete operation on the type (REQ-34).
- **`ontology/tests/rust_actuator_harness.py`** and
  **`ontology/tests/actuator_invocation_harness.py`**, two new standalone
  Python sub-harnesses, folded additively into `ontology/tests/harness.py` as
  `run_rust_actuator` and `run_actuator_invocation_boundary`, on
  `run_rust_gateway`'s exact shape (REQ-43 to REQ-45).
- **`ontology/tests/rust_gateway_harness.py`** widened: its permitted
  in-workspace path-dependency allowlist gains `actuator-git`, and it gains a
  check that `std::process` appears nowhere under `crates/himinbjorg/src/` (REQ-6,
  REQ-7).
- **`ontology/tests/himinbjorg_invocation_harness.py`** widened additively: its
  interface symbol set gains `broker_authorised_action`, so its own
  zero-non-test-caller claim is reported by two independent detectors, not one
  (REQ-40).

`hierarchy_vor::CohortDefinition`, `crates/boundary-gjoll/` and the Python
authorisation-path files named in the build spec's section 10 row 34 are all
unchanged, confirmed by the file list this step's own verification set checks
against (section 11 below).

## 11. Test plan

Following `index.md` section 5's convention (a security property is tested by its
failure mode, not only its happy path):

- **Argument safety, tested by injection.** `unit_tests/argv_validation.rs`: a
  leading hyphen, a NUL byte, a newline, a carriage return, an empty value, an
  overlong value and the two named real-incident payload shapes (the
  `tj-actions/branch-names` and Home Assistant branch-name corpus cases, section
  15 of the build spec) all refuse at validation, with no process spawned; a
  validated message containing shell metacharacters the validation nonetheless
  permits is recorded by git literally, byte for byte, proving the value position
  is not interpreted; a static scan confirms no forbidden git subcommand name and
  no shell invocation appears anywhere in the crate.
- **The target allowlist and the working repository, tested by absence and by
  fail-closed refusal.** `unit_tests/target_and_repo_failclosed.rs`: a push to
  `main` refuses via the allowlist-membership variant, never the protected-ref
  variant; an arbitrary unrecognised target, and a remote/ref pair individually
  permitted but not as a pair, both refuse identically; the working-repository
  variable absent, empty, pointing at a missing path, a regular file, a directory
  with no git marker and a path inside this repository's own working tree all
  refuse.
- **Real git behaviour, always exercised, never gated on a secret or a network**
  (GA-5, REQ-46). `tests/public_surface.rs`, compiled as an external crate: a
  throwaway working repository and a throwaway local bare repository acting as
  `origin`, both inside a temporary directory and removed afterwards, prove a
  commit then a push against a permitted target actually lands in the bare
  repository's history; a push to a non-existent remote refuses via the
  exit-status variant; a spawned process exceeding the bounded wall-clock limit
  is terminated and refuses via the timeout variant; the actuator's own public
  surface (`execute` plus its three value types) suffices for a caller that is
  not `himinbjorg`.
- **The witness path and the audit seam, tested end to end.**
  `crates/himinbjorg/unit_tests/witness_and_audit.rs` and the widened
  `crates/himinbjorg/tests/public_surface.rs`: a proposal passing all six checks
  yields `Decision::Allow` and a witness; a proposal failing any one check yields
  `Decision::Block` and no witness, including when check five (the real gate
  call) is the one that fails; a witness minted for one action refuses when
  brokered against a different action or target; a recorder whose write fails
  refuses before the actuator is ever invoked, and the effect's absence in the
  working repository is asserted, not only the returned refusal; a recorder that
  reports success without retaining anything (the honest limit, REQ-35, EC-13)
  still lets the actuator execute, and the test names this as the stated limit
  being demonstrated, not as a defect being caught.
- **Two Python sub-harnesses, folded into the main suite.**
  `ontology/tests/rust_actuator_harness.py` checks dependency posture (importing
  `rust_gate_harness.check_dependency_posture`, never copying it), test and code
  isolation, the mechanical surface properties of section 4.1 to 4.5 of the build
  spec, and runs the Rust suite.
  `ontology/tests/actuator_invocation_harness.py` reports, live, the call sites of
  `actuator_git::execute` and of `broker_authorised_action`, classified test
  versus non-test.

**Observed at the time of writing** (the verification set run in the same session
this document was completed in): `cargo test` passes across all four crates
(`crates/actuator-git`'s own 21 unit tests plus 15 integration tests, all
executing real assertions, no silent no-op); `python3 -m ontology.tests.harness`
reports exactly 22 critical findings, all false-inert, with both new obligations
passing; `ontology.tests.rust_actuator_harness` exits 0, reporting each check by
name; `ontology.tests.actuator_invocation_harness` exits 0, reporting exactly one
non-test call site of `actuator_git::execute` (the allowlisted one, inside
`crates/himinbjorg/src/broker.rs`) and zero non-test call sites of
`broker_authorised_action`; `ontology.tests.rust_gateway_harness` reports three
permitted path dependencies and confirms `std::process` is absent from
`himinbjorg/src/`; `ontology.tests.pipeline_score_harness` reports 48 percent
layer one and 33 of 33 pipeline containment, unchanged; `ontology.tests.gjoll_invocation_harness`
reports six test call sites and zero non-test call sites, unchanged. See
`DECISIONS.md` D112 for the full figures and the line-budget outcome.

## 12. Decisions (index)

| # | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| GA-1 | Authorisation reaches the actuator | Through a witness-carrying sibling entry point, `broker_authorised_action` | Widening `broker_action` to accept an authorisation argument | `broker_action`'s three arguments cannot express authorisation; widening it would make its signature a moving target and risk a second, weaker execution path. The sibling entry point can be gated behind an opaque witness that only `Decision::Allow` mints |
| GA-2 | HB-6 (write before fire) | A minimal, in-crate, append-only audit seam (`DecisionRecorder`, `MinimalDecisionRecorder`), fail closed on a write failure | A signed, chained, durable log; a best-effort or fire-and-forget write | The build spec scopes this step to minimal fidelity: the load-bearing property (an unlogged decision does not fire) is real and structural, while signing, chaining and persistence stay Phase 2 (`plans/dd/hlidskjalf.md`) rather than being stubbed in for shape |
| GA-3 | The actuator's own crate | A new crate, `crates/actuator-git/`, the only one in the workspace permitted to touch `std::process` | Adding the process-spawn logic directly inside `himinbjorg` | Isolating the one module that touches `std::process` to its own crate, with an empty `[dependencies]` table, keeps the mechanical dependency-posture and test-isolation checks that already govern the other three crates applicable to a fourth, and keeps `himinbjorg` itself free of any direct process-spawning code |
| GA-4 | The push-target mechanism | A hardcoded positive-match permitted-ref allowlist at the actuator boundary | Extending `hierarchy_vor::CohortDefinition` with a `permitted_targets` field now | Keeps the cohort's attested record shape, its `COMMITTED_ATTESTATION` and its ten golden vectors untouched (REQ-17); step six inherits a real mechanism to prove a disallowed push blocked, and the cohort's own field stays a named, deferred item until a second cohort or the load-time manifest format arrives |
| GA-5 | Testing real git behaviour | Always exercised, against a throwaway bare repository in a temporary directory, no network and no secret required | Gating the real-behaviour tests behind a provisioned secret, following D111's `six_checks.rs` precedent | D111's own residual (a Rust test that passes having executed zero assertions when a secret is absent) is exactly what this step must not repeat for its own crate (REQ-46, REQ-47); a throwaway local repository needs no external state at all |
| GA-6 | Argument-value validation | A positive-match character allowlist, checked once per value by one function, never a denylist of forbidden shapes | Enumerating known-dangerous shell metacharacters or known attack payload shapes | This is invariant 3.5's discipline (never grow coverage by naming the attack) applied to the actuator boundary: the corpus sources this document's section 4 cites each show a restricted character set still achieving command execution once shell-interpreted, so the actuator refuses everything not explicitly permitted rather than trying to name everything dangerous |

## 13. Deferred, named, not built

Carried from `.opencode/plans/git-actuator-step-four.md` section 14, so build-order
step five inherits these as written obligations rather than rediscovering them,
following `plans/dd/vor.md` section 7's precedent for this table's shape.

| # | Item | Where it goes |
|---|---|---|
| 1 | The cohort's `permitted_targets` field | When a second cohort exists, or when the load-time manifest format arrives (D107 ruling three). Vör deferred item 1 is partially discharged here, at the actuator boundary, not at the cohort record |
| 2 | The generalised actuator sandbox for arbitrary tool or command execution | Explicitly out of scope for this phase, per `plans/synthesis-bootstrap.md` section 5. Do not generalise the actuator to get it early |
| 3 | The credential broker's general form and the single-holder pattern's real implementation | Unchanged from D111. The scope allowlist is still a hardcoded stand-in for a real credential store |
| 4 | A signed, chained, durable Hliðskjálf with `verify_chain` and Gjallarhorn wiring | Phase 2, `plans/dd/hlidskjalf.md`. `DecisionRecorder` is its extension point |
| 5 | `Decision::Queue` and `Decision::Escalate` becoming reachable | Need Gjallarhorn's protected channel and Hliðskjálf's escalation record respectively. Neither is built |
| 6 | Witness single use or replay resistance | Step five's fixed five-step sequence, or a nonce in the audit record. A caller holding a valid witness can drive two identical executions today (EC-12) |
| 7 | Concurrency safety for the actuator and the recorder | Step five owns sequencing. The actuator holds no lock and the minimal recorder is not concurrency hardened (EC-10) |
| 8 | A third operation (merge), which D108's dogfooding text names alongside commit and push | Added as an operation variant when a real workflow needs it, per the Open/Closed analysis in section 9.1 of the build spec |
| 9 | Registering `action:git.commit` and `action:git.push` in the loaded ontology's action vocabulary | Vör deferred item 9, deliberately still not done |
| 10 | The Harness Boundary Interface binding to OpenCode/Gleipnir, and the canary wrap for a Fenrir task | Unchanged from D111 |
| 11 | The process engine's fixed five-step sequence | Build-order step five, and the thing that would give `broker_authorised_action` a non-test caller and start advancing invariant 3.6 |
| 12 | Verification of the resolved `git` binary's identity | EC-2's trust root |
| 13 | `ActuationRefusal::PartialEffect` becoming reachable | Build-order step five, item 11 above: `execute` performs exactly one operation per call and `broker_authorised_action` authorises exactly one operation per witness, so no code path in this build holds both a commit outcome and a subsequent push outcome to combine. The variant is named and typed, not delivered behaviour |

Also carried forward, stated so a reviewer can check it directly rather than
infer it: a caller supplying a recorder whose write always reports success
without retaining anything defeats the audit obligation this step builds
(REQ-35, EC-13), and nothing in this crate or in `himinbjorg` detects, rejects or
distinguishes that recorder from an honest one. This is the same class of limit
as D103's limit two and D100's in-process label rewrite, and it is not closed by
this step.

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
