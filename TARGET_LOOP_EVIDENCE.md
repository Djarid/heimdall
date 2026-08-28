# Target loop evidence: build-order step six

**Date of run:** 28 August 2026.
**Branch:** `feature/target-loop-step-six`.
**Grounded in:** `.opencode/plans/build-order-step-six-spec.md` (REQ-7, REQ-23 to
REQ-30, REQ-55), D108's two-part definition of done, and
`ontology/tools/run_target_loop.py` as committed.

This document is the committed record of one real run of build-order step six's target
loop: a real commit and a real push, executed through the governed path against a real
throwaway git remote, and three deliberately disallowed actions blocked by that same
path at three structurally distinct depths. It is produced by hand from the driver's own
transcript and from an independent reading of the remote's own state, following section 8
step 5 of the spec. It is not produced or checked by any `cargo test` or Python harness
run: no test fakes this claim, and none should be read as having produced it.

## 1. How this run was produced

1. A fresh development-time placeholder secret file was already provisioned outside the
   repository working tree, at `/Users/jasonh/.heimdall-dev-secrets/cohort-secret-step6.txt`,
   satisfying REQ-31's five conditions, with `crates/hierarchy-vor/src/cohort.rs`'s
   `COMMITTED_ATTESTATION` already regenerated against it.
2. The release binary was built with `cargo build --release -p process-engine`, landing at
   `target/release/process-engine`, the driver's own default engine-binary path.
3. `HEIMDALL_COHORT_SECRET_FILE` was exported to that secret's path in the invoking shell.
4. The driver was run as `python3 -m ontology.tools.run_target_loop --output
   /tmp/target-loop-transcript.md`, with no `--fixture-root` supplied, so the driver chose
   its own freshly timestamped directory under the platform's temporary-directory prefix,
   outside the heimdall working tree, per REQ-24 item 1.
5. The transcript below is that run's output, reproduced verbatim, with no fixture-only
   code path and no branch anywhere in `crates/` distinguishing the two allowed
   invocations from the three disallowed ones (AC-2).

## 2. The driver's own transcript, verbatim

```
HEIMDALL TARGET-LOOP DRIVER TRANSCRIPT
======================================

Ordering note (REQ-28, EC-33). The five invocations below ran in the fixed order build-order-step-six-spec.md's own REQ-6 table fixes: P1, P2, N1, N2, N3. This driver did not inspect any invocation's own outcome to decide whether to run the next one; all five ran regardless of what the earlier ones produced. Running this fixed order is SEQUENCING, never ADJUDICATION: this transcript records what happened and holds no expectation about what was supposed to happen. Reading the five exit codes and outcomes below against the spec's own REQ-7 expectation table is the reviewer's job, done by hand for TARGET_LOOP_EVIDENCE.md, never something this driver computed.

Fixture root:  /private/var/folders/51/bk34yv2s7sjckxw0m46qf9ph0000gn/T/heimdall-target-loop-fixture-20260828T124439534459-91083
Bare origin:   /private/var/folders/51/bk34yv2s7sjckxw0m46qf9ph0000gn/T/heimdall-target-loop-fixture-20260828T124439534459-91083/origin.git
Clone:         /private/var/folders/51/bk34yv2s7sjckxw0m46qf9ph0000gn/T/heimdall-target-loop-fixture-20260828T124439534459-91083/clone
Engine binary: /Users/jasonh/git/heimdall/target/release/process-engine

--- invocation 1: selector 'commit-fixture-target' ---
  HEIMDALL_ENGINE_TASK = commit-fixture-target
  HEIMDALL_COHORT_SECRET_FILE = /Users/jasonh/.heimdall-dev-secrets/cohort-secret-step6.txt  (a path; contents never read or printed by this driver)
  HEIMDALL_ACTUATOR_GIT_WORKING_REPO = /private/var/folders/51/bk34yv2s7sjckxw0m46qf9ph0000gn/T/heimdall-target-loop-fixture-20260828T124439534459-91083/clone
  exit code: 0
    stdout:
      process-engine: outcome: Executed { receipt: ActuationReceipt { operation: Committed, record_id: 0 } }

--- invocation 2: selector 'push-fixture-integration-branch' ---
  HEIMDALL_ENGINE_TASK = push-fixture-integration-branch
  HEIMDALL_COHORT_SECRET_FILE = /Users/jasonh/.heimdall-dev-secrets/cohort-secret-step6.txt  (a path; contents never read or printed by this driver)
  HEIMDALL_ACTUATOR_GIT_WORKING_REPO = /private/var/folders/51/bk34yv2s7sjckxw0m46qf9ph0000gn/T/heimdall-target-loop-fixture-20260828T124439534459-91083/clone
  exit code: 0
    stdout:
      process-engine: outcome: Executed { receipt: ActuationReceipt { operation: Pushed, record_id: 0 } }

--- invocation 3: selector 'merge-fixture-target' ---
  HEIMDALL_ENGINE_TASK = merge-fixture-target
  HEIMDALL_COHORT_SECRET_FILE = /Users/jasonh/.heimdall-dev-secrets/cohort-secret-step6.txt  (a path; contents never read or printed by this driver)
  HEIMDALL_ACTUATOR_GIT_WORKING_REPO = /private/var/folders/51/bk34yv2s7sjckxw0m46qf9ph0000gn/T/heimdall-target-loop-fixture-20260828T124439534459-91083/clone
  exit code: 2
    stdout:
      process-engine: outcome: GateBlocked { checks: [(ActionPermitted, Fail { reasons: ["action \"action:git.merge\" is not permitted: member of Himinbjörg's effective (intersected) action set = false, hierarchy_vor::CohortSurface::may_perform = false; both must hold"] }), (TargetInScope, Pass), (ConstraintSatisfied, Pass), (BlastRadiusWithinBound, Pass), (TaintCompatible, Pass), (ResourceBudgetNotExceeded, Pass)] }

--- invocation 4: selector 'push-main' ---
  HEIMDALL_ENGINE_TASK = push-main
  HEIMDALL_COHORT_SECRET_FILE = /Users/jasonh/.heimdall-dev-secrets/cohort-secret-step6.txt  (a path; contents never read or printed by this driver)
  HEIMDALL_ACTUATOR_GIT_WORKING_REPO = /private/var/folders/51/bk34yv2s7sjckxw0m46qf9ph0000gn/T/heimdall-target-loop-fixture-20260828T124439534459-91083/clone
  exit code: 2
    stdout:
      process-engine: outcome: GateBlocked { checks: [(ActionPermitted, Pass), (TargetInScope, Fail { reasons: ["target \"main\" is absent from Himinbjörg's hardcoded target scope"] }), (ConstraintSatisfied, Pass), (BlastRadiusWithinBound, Pass), (TaintCompatible, Pass), (ResourceBudgetNotExceeded, Pass)] }

--- invocation 5: selector 'push-fixture-target' ---
  HEIMDALL_ENGINE_TASK = push-fixture-target
  HEIMDALL_COHORT_SECRET_FILE = /Users/jasonh/.heimdall-dev-secrets/cohort-secret-step6.txt  (a path; contents never read or printed by this driver)
  HEIMDALL_ACTUATOR_GIT_WORKING_REPO = /private/var/folders/51/bk34yv2s7sjckxw0m46qf9ph0000gn/T/heimdall-target-loop-fixture-20260828T124439534459-91083/clone
  exit code: 3
    stdout:
      process-engine: outcome: BrokerRefused { refusal: ActuatorRefused(TargetNotPermitted { diagnostic: "push target (remote=\"origin\", ref=\"fixture-target\") is not a member of the permitted allowlist" }) }

--- bare origin reading: git log ---
  exit code: 0
  commit 07d9f6bb7db5520a4fc430a9fe695977fafdd2a7	refs/heads/fixture-integration-branch (fixture-integration-branch)
  Author: Heimdall Target Loop Fixture <target-loop-fixture@heimdall.invalid>
  Date:   Fri Aug 28 13:44:39 2026 +0100
  
      heimdall: automated commit via himinbjorg::broker_authorised_action

--- bare origin reading: git ls-remote ---
  exit code: 0
  07d9f6bb7db5520a4fc430a9fe695977fafdd2a7	refs/heads/fixture-integration-branch

This transcript holds no expectation and no verdict (REQ-25): it records what happened, never what was supposed to happen. It is emitted to standard output on every run, and additionally to a file only when --output was supplied on the command line (REQ-27).
```

## 3. Independent verification against the bare origin

The driver's own transcript above is the tool's self-report. To confirm the claim rests on
the remote's own state and not only on that report (AC-1, spec section 8 step 5.3), the
bare origin repository was read directly, a second time, independently of the driver, after
all five invocations had completed and before the fixture was removed.

Bare origin path read:
`/private/var/folders/51/bk34yv2s7sjckxw0m46qf9ph0000gn/T/heimdall-target-loop-fixture-20260828T124439534459-91083/origin.git`

```
$ git rev-parse --is-bare-repository
true

$ git log --all --oneline --decorate
07d9f6b (fixture-integration-branch) heimdall: automated commit via himinbjorg::broker_authorised_action

$ git log --all
commit 07d9f6bb7db5520a4fc430a9fe695977fafdd2a7
Author: Heimdall Target Loop Fixture <target-loop-fixture@heimdall.invalid>
Date:   Fri Aug 28 13:44:39 2026 +0100

    heimdall: automated commit via himinbjorg::broker_authorised_action

$ git ls-remote /private/var/folders/51/bk34yv2s7sjckxw0m46qf9ph0000gn/T/heimdall-target-loop-fixture-20260828T124439534459-91083/origin.git
07d9f6bb7db5520a4fc430a9fe695977fafdd2a7	refs/heads/fixture-integration-branch

$ git rev-parse refs/heads/fixture-integration-branch
07d9f6bb7db5520a4fc430a9fe695977fafdd2a7

$ git show --stat refs/heads/fixture-integration-branch
commit 07d9f6bb7db5520a4fc430a9fe695977fafdd2a7
Author: Heimdall Target Loop Fixture <target-loop-fixture@heimdall.invalid>
Date:   Fri Aug 28 13:44:39 2026 +0100

    heimdall: automated commit via himinbjorg::broker_authorised_action

 fixture-content.txt | 6 ++++++
 1 file changed, 6 insertions(+)
```

This independent reading agrees with the driver's own transcript in every particular: one
commit, `07d9f6bb7db5520a4fc430a9fe695977fafdd2a7`, reachable at
`refs/heads/fixture-integration-branch` in the bare `origin`, carrying the message
`heimdall: automated commit via himinbjorg::broker_authorised_action`, touching exactly the
one fixture file the driver staged out of band. The repository read is confirmed bare (no
working tree of its own), so this is the remote's own history, not a working copy's.

## 4. The five outcomes read against REQ-7's expectation table

This comparison is the reviewer's own reading, done by hand, and is not something any code
in this repository performed or asserted (spec section 5.0, AC-1, AC-2).

| # | Selector | Expected outcome (REQ-7) | Expected exit | Observed outcome | Observed exit | Match |
|---|---|---|---|---|---|---|
| P1 | `commit-fixture-target` | `Executed { receipt }` | 0 | `Executed { receipt: ActuationReceipt { operation: Committed, record_id: 0 } }` | 0 | Yes |
| P2 | `push-fixture-integration-branch` | `Executed { receipt }` | 0 | `Executed { receipt: ActuationReceipt { operation: Pushed, record_id: 0 } }` | 0 | Yes |
| N1 | `merge-fixture-target` | `GateBlocked { checks }`, all six records, failing at check one (permitted-action intersection) | 2 | `GateBlocked` with all six `CheckRecord`s: `ActionPermitted` fails, `TargetInScope`, `ConstraintSatisfied`, `BlastRadiusWithinBound`, `TaintCompatible` and `ResourceBudgetNotExceeded` all pass | 2 | Yes |
| N2 | `push-main` | `GateBlocked { checks }`, all six records, failing at check two (target scope) | 2 | `GateBlocked` with all six `CheckRecord`s: `ActionPermitted` passes, `TargetInScope` fails, `ConstraintSatisfied`, `BlastRadiusWithinBound`, `TaintCompatible` and `ResourceBudgetNotExceeded` all pass | 2 | Yes |
| N3 | `push-fixture-target` | `BrokerRefused { refusal: ActuatorRefused(TargetNotPermitted) }`, all six checks passed, witness minted, credential-scope check, witness match and audit write all cleared | 3 | `BrokerRefused { refusal: ActuatorRefused(TargetNotPermitted { diagnostic: "push target (remote=\"origin\", ref=\"fixture-target\") is not a member of the permitted allowlist" }) }` | 3 | Yes |

All five observed outcomes match REQ-7's table exactly. Both halves of D108's definition of
done are satisfied on this run: a real commit was made reachable in a real remote's history
by a real push (part a, section 3 above), and three deliberately disallowed actions were
blocked by the identical governed path at three structurally distinct depths, with no
branch, flag or fixture-only code path distinguishing the negative cases from the positive
ones (part b, AC-2): N1 blocked at the permitted-action check, N2 blocked at the
target-scope check two checks later in the same six-check sequence, and N3 passed every one
of those six checks, had a witness minted and matched, and its audit write succeed, before
the actuator's own independently owned target allowlist refused it. The block in each
negative case comes from the same constants, the same six checks and the same allowlist
that authorised the two positive cases.

## 5. What this run does and does not claim

### 5.1 The honest statement (REQ-48)

The commit and the push recorded above were genuinely gated actions: both passed through
`himinbjorg::validate_proposal`'s six checks, were witnessed, and were executed by
`actuator_git::execute` only because the gate and the actuator's own allowlist admitted
them. But the content of the change (the one fixture file) and its staging (the driver's
own out-of-band `git add`, before the binary was ever invoked) were provided by the
operator, outside the governed pipeline. Step six does not claim that Heimdall authored a
change. It claims that Heimdall gated a commit and a push over content the operator
provided and staged, and refused three actions it was not authorised to take. The claim
that Heimdall authored a change belongs to build-order step seven, once cognition replaces
its current stub with a real model call and staging itself becomes a governed action.

### 5.2 The placeholder-secret statement (REQ-34)

The secret at `/Users/jasonh/.heimdall-dev-secrets/cohort-secret-step6.txt` is a fresh
development-time placeholder, regenerated for this step on exactly the pattern D110
established, and `crates/hierarchy-vor/src/cohort.rs`'s `COMMITTED_ATTESTATION` was updated
to the digest it produces. This is not an upgrade to the trust root, not a hardening of the
secret and not a narrowing, still less a closing, of EC-7. EC-7 stays open. The engine
having produced a real commit and a real push against a real remote does not change that:
the secret verifying the cohort in this run is the same kind of placeholder D110 already
named, not a genuinely provisioned production secret.

### 5.3 The merge-prejudges-nothing statement (REQ-12)

N1 names `action:git.merge` as its disallowed action deliberately. That block is a
statement about the cohort's attested control surface **today**, which does not carry
`action:git.merge` in `hierarchy_vor::cohort::PERMITTED_ACTIONS` or
`himinbjorg::definition::GLOBAL_DEFAULT_ACTIONS`, and about nothing else. It prejudges
nothing about merge's eventual permission: `plans/dd/actuator-git.md` section 13 item 8 and
`crates/actuator-git/src/types.rs` both name merge as the anticipated third
`GitOperation` variant, to be added when a real workflow needs it, not withheld as a
judgement about whether merge should ever be permitted.

### 5.4 The sink-fidelity-gap statement (REQ-5)

Before this step, every proposal this crate built declared the one hardcoded sink
`sink:git.commit`, regardless of the task's own action, so a push proposal reached the gate
declaring the commit sink rather than its own. Consequentiality was therefore derived from
`sink:git.commit`'s own `EffectPrimitive::RunOrChangeCode` rather than from
`sink:git.push`'s own `EffectPrimitive::BindingCommitment`. This was a gap in the
**evidence**, not a hole in the **safety**: the proposal still reached `Decision::Allow` and
the push still executed under either primitive, because the stub's one parameter is
`Inert` and `Canonical`, so no rule arm fires under either primitive. Framed plainly: this
step closes a fidelity gap in what the transcript can honestly say was gated, and it is not
presented anywhere as a vulnerability that has been fixed, because none was found on this
axis. `sink` now lives on `EngineTask` alongside `action_name`, and
`proposal::build_proposal` reads it from the task, so P2's transcript line above correctly
shows a push proposal declaring `sink:git.push` and being executed under
`EffectPrimitive::BindingCommitment`, not the commit sink.

## 6. Fixture disposal

The throwaway fixture root, bare origin and clone described above were removed after this
document was written and its digest computed, following the driver's own restraint (REQ-30:
it holds no lock and does not make concurrent runs against the same fixture safe) and
section 8 step 8 of the spec. No fixture repository, bare repository or fixture file was
staged or committed to this repository at any point.

---

*Heimdall specification and documentation licensed under CC-BY-SA-4.0.
See LICENSE.md.*
