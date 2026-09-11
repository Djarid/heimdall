# Detailed Design: the cognition client (`crates/cognition-client/`)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 3 (build-order step seven of `plans/synthesis-bootstrap.md`, D108)
**Status of the component today:** built and tested at the fidelity this document
records. This is the repository's sixth Rust crate, and the first to reach a
language model from any non-test code path in this project's history.

---

## 1. Purpose

The cognition client obtains one validated commit message from a Python MLX
sidecar, or refuses. It exists because build-order step seven (D108) needs a
genuine model call on the process engine's own non-test path, replacing the
hardcoded stub `DefaultCognitionStep` had supplied since build-order step five
(D113), without putting the model, or any knowledge of proposals, parameters,
trust levels or consume modes, inside the engine crate itself.

It adjudicates nothing. Everything the sidecar produces still passes through
`himinbjorg::validate_proposal`'s six checks and the witness match regardless
of what it produced, and no branch anywhere in this crate, or in the engine
crate that calls it, derives a permission, a scope, a target-scope membership
or a check outcome from the model's own output. This is the same posture
`crates/actuator-git/` holds one layer down (D112): it executes only what has
already been authorised; this crate proposes only what the caller declares
honestly, and the caller's own honest declaration is what makes the block at
Gjöll's check five the designed outcome of this step, not a defect.

## 2. Responsibilities and boundaries

In scope:

- Spawn the Python MLX sidecar (`cognition.sidecar`, a new top-level Python
  package outside `crates/`) with a fixed argv and no shell, wait under a
  bounded, named wall-clock limit, and hand back either a validated message
  or a typed refusal.
- Read exactly two environment values, both path-shaped (the interpreter to
  spawn, and the directory the `cognition` package imports from), and read
  them nowhere else and on no other path.
- Validate whatever the sidecar returns through a single positive-match
  validator before any caller can see it.
- Refuse fail closed on every one of eleven named conditions (section 6), with
  no default, no cache, no retry and no partial acceptance on any of them.

Out of scope, named rather than smoothed:

- **It knows nothing of trust, consumption, proposals, sinks or actions.**
  Its `[dependencies]` table is empty (REQ-7), so it cannot even name
  `himinbjorg` or `boundary-gjoll`, let alone construct a
  `himinbjorg::ProposalParameter` or declare a trust level. The honest
  `TrustLevel::Tainted`/`ConsumeMode::Action` declaration for the model's
  output is made by `crates/process-engine/src/cognition.rs`, the crate that
  calls this one, never here (ST7-7).
- **It is not a general model-calling interface.** The public surface is
  exactly one function, one value type and one refusal type (REQ-10): no
  streaming, no cancellation, no retry, no token accounting and no model
  identity is exposed, on `himinbjorg::DecisionRecorder`'s own Interface
  Segregation precedent.
- **It does not adjudicate the message's content.** The validator checks the
  received value's *shape*, never its *meaning*; nothing in this crate reads
  what the message says.
- **It is not the audit log.** The decision that will eventually consume this
  crate's output is written to Himinbjörg's own minimal audit seam inside
  `broker_authorised_action`, downstream of this crate entirely.
- **It does not touch the argument vector.** `himinbjorg::ProposalParameter`
  has no value field and the actuator's own commit message is a hardcoded
  constant (`broker::FIXED_COMMIT_MESSAGE`); the model's text reaches no
  argument vector today (section 2.2 finding five of
  `.opencode/plans/build-order-step-seven-spec.md`), and no requirement, doc
  comment or evidence document produced alongside this crate may claim
  otherwise.

## 3. Public surface

```rust
pub fn obtain_message(prompt: &str) -> Result<CognitionMessage, SidecarRefusal>;

pub struct CognitionMessage { /* private */ }
impl CognitionMessage {
    pub fn as_str(&self) -> &str;
}

pub struct SidecarRefusal {
    pub diagnostic: String,
}
```

`CognitionMessage` has no public constructor and no public `From` conversion
anywhere in this crate: the only way to mint one is `CognitionMessage::new`,
`pub(crate)` and callable only from `validation::validate_received_message`,
on `boundary_gjoll::rule::ConsequentialityVerdict`'s own containment
precedent for the identical property. A downstream caller depending on this
crate as a library has no path to a value of this type except through
`obtain_message`, and therefore through the single validator.

The crate's own module split (REQ-9), each with one reason to change:

- **`types`**: the value shapes (`CognitionMessage`, `SidecarRefusal`). No
  logic.
- **`validation`**: the single positive-match validator,
  `validate_received_message`, and its own maximum-length constant. Answers
  whether a received value affirmatively matches the one permitted shape, and
  refuses if not. Never repairs.
- **`invocation`**: the only module in this crate, and the second module in
  the whole workspace, alongside `crates/actuator-git/src/execute.rs` and
  `main.rs`'s one disclosed `std::process::exit`, permitted to touch
  `std::process`, and the only module that reads the process environment.
  Spawns the sidecar with a fixed argv, waits within the bounded deadline,
  and hands back what it received or a refusal. Decides nothing about the
  value's meaning.
- **`lib.rs`** (crate root): carries `#![forbid(unsafe_code)]` at file scope
  and the public surface above.

## 4. Fail-closed refusal set

Every one of the following refuses, never defaults, never caches, never
retries and never substitutes any other value:

1. the interpreter-path environment value unset, empty, whitespace only,
   naming a path that does not exist, or naming a path that is not an
   executable regular file;
2. the package-root environment value unset, empty, whitespace only, or
   naming a path that does not exist or is not a directory;
3. the spawn itself failing;
4. the sidecar module absent or failing to import, including a missing
   `mlx_lm`;
5. the model weights absent or failing to load;
6. a non-zero exit status from the child;
7. output that is empty or whitespace only;
8. output whose fixed line-oriented shape does not parse, including a
   missing key, an unexpected key or an out-of-order key;
9. output failing the positive-match validator (section 5);
10. output exceeding the declared maximum length;
11. the timeout expiring.

On none of these is a default value produced, a previous value cached or
reused, a retry attempted, a partial output accepted, or `DefaultCognitionStep`'s
output substituted for the failed call. `crates/process-engine/src/cognition.rs`'s
own `RealCognitionStep`, the crate's one caller, never names, imports or
references `DefaultCognitionStep` at all, and contains no `unwrap_or`,
`unwrap_or_default` or `unwrap_or_else` producing a `CognitionOutput`: this is
a property of the code's shape, checked by the new sub-harness, not left to
review (section 8, check 6).

## 5. Validator policy

`validation::validate_received_message` is the only place in the crate a
value received from the child is checked, on `crates/actuator-git/src/argv.rs`'s
own single-validator precedent. Every check is a permitted-shape check, never
a forbidden-shape check: this is invariant 3.5's discipline applied at a new
boundary, and enumerating forbidden shapes would be that invariant's
blacklist mistake one layer over. The policy is at least as strict as
`argv.rs`'s `ValueKind::Message` policy, which the value must survive
downstream anyway, though no line of `argv.rs` or any other file in
`crates/actuator-git/` changes to accommodate it:

- non-empty after any trailing line ending is stripped;
- not whitespace only;
- at most `MAX_RECEIVED_VALUE_LEN` bytes (4,096, this crate's own constant,
  never read from `actuator_git::argv::MAX_VALUE_LEN`, which this crate
  cannot see because it does not depend on `actuator-git`: the two are an
  agreement between independently owned constants, never a derivation, on
  `context::TARGET_SCOPE`'s PE-4 precedent, and no test asserts the two
  agree);
- no leading hyphen;
- no NUL byte;
- no newline;
- no carriage return;
- every character matching `is_ascii_graphic() || c == ' '`.

A value failing any check is refused, with a diagnostic naming which check
failed, built only from this module's own fixed strings. No function in this
crate removes, replaces, strips, filters or maps characters of a received
value; none truncates it to a permitted length; none wraps, escapes or
quote-wraps it. The received value is either returned unchanged inside
`CognitionMessage`, byte for byte, or the call refuses.

## 6. Spawn contract

The child is spawned with a fixed argv and no shell on any path, on
`execute.rs`'s own pattern: the resolved interpreter path, the `-m` flag, and
the compile-time constant module name `cognition.sidecar`. No argument is
derived from any input, any environment value's contents beyond the two
resolved paths, or any prior output. No shell, no `sh -c`, no
`Command::new("sh")` and no shell metacharacter interpretation anywhere.

The child's environment is cleared (`env_clear`) and then repopulated from a
named, closed forwarding set, each member carrying its own reason: `PATH` (so
the interpreter can resolve its own shared libraries and helper binaries) and
`HOME` (so it finds whatever per-user configuration the host already
carries; neither is a secret), both forwarded explicitly from this process's
own environment; and `PYTHONPATH`, set explicitly by this module itself from
the already-validated package-root path, never forwarded from any
pre-existing `PYTHONPATH` this process might have inherited. No other
variable crosses.

A named constant, `SIDECAR_TIMEOUT_SECS = 300`, bounds the wait: a bounded
poll on `Child::try_wait`, never an unbounded `Child::wait`, chosen so a cold
model load on Apple silicon (tens of seconds for a 4-bit 7B model) cannot
false-fire while the bound stays real. On expiry the child is killed and
reaped, no partial output is read or used, and the call refuses with its own
named reason. No retry exists on any path, because a retry would double the
window and falsify the one-invocation-per-run claim the evidence transcript
makes. Both the child's standard output and standard error are piped and
drained continuously on their own threads for the whole lifetime of the wait,
so a verbose sidecar cannot deadlock the bounded wait against a full, unread
pipe buffer.

The prompt, an untrusted task description the caller (`RealCognitionStep`)
assembles from the task's own `action_name`, `target` and `sink`, is written
to the child's standard input; this is the only handle this crate writes to,
and it performs no filesystem write on any path (no file creation, no
directory creation, no temporary file).

## 7. Data owned

The crate owns no persistent state, no world model and no audit record. What
it owns is entirely compile-time constant:

- `PYTHON_INTERPRETER_ENV_VAR`, `COGNITION_PACKAGE_ROOT_ENV_VAR`, the two
  environment variable names, never the values themselves;
- `SIDECAR_TIMEOUT_SECS`, the wall-clock bound;
- `SIDECAR_MODULE_NAME`, the compile-time module name spawned;
- `MESSAGE_KEY_PREFIX`, the fixed line-oriented output's one key;
- `MAX_RECEIVED_VALUE_LEN`, the validator's own maximum-length constant.

## 8. Dependencies

- **Upstream (the crate's only non-test caller):**
  `crates/process-engine/src/cognition.rs`'s `RealCognitionStep`, which calls
  `obtain_message` and constructs the one `Tainted`/`Action`
  `himinbjorg::ProposalParameter` from the validated message it returns. This
  crate itself never constructs a `ProposalParameter`, never names
  `himinbjorg` or `boundary-gjoll`, and has no view on trust or consumption at
  all.
- **Downstream (what this crate itself depends on):** nothing inside the
  repository. `[dependencies]` is empty and so is `[dev-dependencies]`
  (REQ-7); the crate depends only on the Rust standard library, and, at run
  time rather than as a Cargo dependency, on whatever the resolved
  interpreter path names and whatever the `cognition` Python package (outside
  `crates/`) does at the other end of the pipe.
- The dependency direction between the two crates is one way:
  `crates/process-engine/` depends on `crates/cognition-client/`, never the
  reverse; a reverse dependency would be a cycle Cargo refuses to build,
  since the trait this crate would need to implement is declared in the
  crate that already depends on it.

## 9. Test plan

Following `plans/dd/index.md` section 5's convention (a security property is
tested by its failure mode, not only its happy path):

- **The validator, tested by refusal and by acceptance.**
  `unit_tests/validator.rs`: an empty value, a whitespace-only value, a
  leading hyphen, a NUL byte, a newline, a carriage return, a character
  outside the allowlist, and an overlong value all refuse with a diagnostic
  naming the failing check; a value satisfying every check is returned
  unchanged, byte for byte.
- **The refusal set, tested against a stand-in interpreter.**
  `unit_tests/refusal_set.rs`: every one of section 4's eleven conditions
  exercisable without a real model or the venv (an unset, empty or
  non-existent interpreter path; an unset, empty or non-directory
  package-root path; a spawn failure; a non-zero exit; empty or
  whitespace-only output; an unparseable line shape) is induced and confirmed
  to return `Err`, never `Ok`, never a default and never a cached value.
- **No sanitising path.** `unit_tests/no_sanitising.rs`: confirms no
  function in the crate removes, replaces, strips, truncates, escapes or
  quote-wraps a received value; a validated value is either returned
  unchanged or the call refuses.
- **Structural posture.** `unit_tests/structural_posture.rs`: `#![forbid(unsafe_code)]`
  present, `unsafe` absent, no `[[bin]]` target, `std::net` absent everywhere,
  `std::process` present only in `invocation.rs`, no filesystem write entry
  point anywhere in `src/`.
- **Public-surface sufficiency.** `tests/public_surface.rs`, compiled as an
  external crate: the one function, the one value type and the one refusal
  type are reachable and sufficient for a caller outside this crate; the
  value type cannot be minted without going through `obtain_message`.
- **A new Python sub-harness, folded into the main suite.**
  `ontology/tests/rust_cognition_client_harness.py` checks committed
  structure, committed constants and committed evidence (never the model,
  the loop or git): dependency posture, the forbid attribute and the absence
  of `unsafe`, `std::process`/`std::net` confinement, the absence of a
  filesystem write, the pinned `REAL_TRUST_LEVEL`/`REAL_CONSUME_MODE`
  constants, the absence of any fallback to `DefaultCognitionStep`, the
  absence of a sanitising path, the absence of a shell spawn, the absence of
  an unbounded wait or retry, the invariant 3.1 guard's own unaffected
  reading (34 scanned files, 13 allowed roots) plus a negative-control probe
  proving the guard would catch a `cognition` import on a scanned-path
  stand-in, the absence of any authorisation-path import of the new package,
  and a digest pin over `COGNITION_EVIDENCE.md`.

**Observed at the time of writing:** `cargo test -p cognition-client` passes
50 unit tests plus three integration tests (53 total), zero failures;
`cargo test --workspace` passes 258 tests across all six crates (180
pre-existing plus 78 new: 53 in this crate, 25 in `crates/process-engine/`'s
own widened suite), zero failures; `python3 -m ontology.tests.harness`
reports exactly 22 critical findings, all false-inert, with the new
`run_rust_cognition_client` obligation passing; the invariant 3.1 guard
reports 34 scanned files, 13 allowed import roots and zero violations,
unaffected because `crates/` and `cognition/` both sit outside its scan
roots; `ontology.tests.pipeline_score_harness` reports 48 percent layer one
and 33 of 33 (100 percent) pipeline containment, unchanged;
`ontology.tests.gjoll_invocation_harness` reports six test call sites and
zero non-test call sites, unchanged. See `DECISIONS.md` D115 for the full
figures and the line-budget breakdown, and `COGNITION_EVIDENCE.md` for the
committed transcript of the real model run.

## 10. Decisions (index)

| # | Decision | Chosen | Declined alternative |
|---|---|---|---|
| CC-1 | The trust declaration for the model's output | `TrustLevel::Tainted`, made by the caller (`crates/process-engine/src/cognition.rs`), never by this crate | Declaring it inside this crate, which would force it to depend on `boundary-gjoll` for `TrustLevel`'s own type and give it a second reason to change (ST7-7, section 3.2 item four of the build spec) |
| CC-2 | The consume mode | `ConsumeMode::Action`, likewise made by the caller | `ConsumeMode::Inert`, which would declare a value D24 agent-scoped derivation has already marked action-critical as inert, the claim D89-A exists to distrust (ST7-5) |
| CC-3 | The substrate | A sixth crate spawning a Python MLX sidecar as a child process, with a fixed argv | A socket to a local model server (needs a hand-written HTTP client, breaches the `std::net` zero-exception posture); Python-owned cognition (contradicts D105) (ST7-2) |
| CC-4 | The sidecar's own preconditions | Read inside this crate's invocation module, at cognition time, never in `startup.rs` | Placing them in `startup.rs` alongside the existing three preconditions, which would make them refuse *before* any member runs, killing step six's positive control on any machine with no model at all (section 2.2 finding four of the build spec) |
| CC-5 | The boundary's own encoding | A fixed, minimal, line-oriented form (`MESSAGE=<content>`), deliberately not JSON | A JSON envelope, which would need a parser or a hand-written JSON implementation neither this crate nor the workspace otherwise needs (REQ-22) |
| CC-6 | The wall-clock bound | Imposed, 300 seconds, no retry | Leaving the refusal set silently incomplete; retrying, which would double the window and falsify the one-invocation-per-run evidence claim (ST7-10) |
| CC-7 | The `std::process` ruling this crate reopens | A second permitted module, alongside `crates/actuator-git/src/execute.rs`, with its own narrower justification rather than D108's reused verbatim (an interpreter loading a model is not a compiled, deterministic, externally audited tool) | Reusing D112's reasoning unchanged, which does not transfer (D117) |

## 11. Deferred, named, not built

| # | Item | Where it goes |
|---|---|---|
| 1 | A second model backend behind the same one-function interface | Whenever a second model substrate is needed; the crate's Open/Closed posture (section 9.1 of the build spec) already supports it without any caller change |
| 2 | Streaming, cancellation, token accounting or verification of the model's own identity | Deliberately not exposed on the public surface (Interface Segregation, section 9.1 of the build spec); no current caller needs any of them |
| 3 | The mixed-provenance parameter case (an operator-authored and a model-authored parameter on the same proposal) | Explicitly optional and dropped at this step (ST7-12, REQ-O3); the EC-10 non-short-circuit property it would have demonstrated is already demonstrable by a Rust unit test over `rule::apply` alone |
| 4 | A test exercising `CognitionBinding::Real` end to end with the real model | Deliberately not built: the build spec's own instruction is that no test is to be written that fakes a real model call, so this is a stated limit, not an oversight. The definition-of-done evidence (`COGNITION_EVIDENCE.md`) is confirmed by hand, once, per run, never by an automated suite |
| 5 | The equality-versus-rank residual in `boundary_gjoll::rule::apply` | Belongs with Gjöll's own promotion and re-validation gate, which gives the intermediate trust levels (`Vouched`) a meaning; not touched by this crate or by this step (EC-40, section 2.1 of the build spec) |
| 6 | Governed staging and the filesystem-write obligation | Unchanged from build-order step six: cognition authors a commit message only, no file content, so neither obligation's trigger is met by this step (`plans/dd/process-engine.md` section 12) |
| 7 | Public-key signing or any stronger transport-integrity guarantee on the sidecar boundary | Not needed at this fidelity: the sidecar is a local child process on a fixed argv, not a network peer, so no signing or integrity mechanism analogous to D94's keyed digest is warranted here |

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
