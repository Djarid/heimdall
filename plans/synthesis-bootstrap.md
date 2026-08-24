# Heimdall synthesis: the self-hosting bootstrap

**Author:** Jason Huxley (recorded by AETOS orchestrator session)
**Date:** August 2026
**Version:** 1.0
**Status:** Bootstrap strategy. Defines the smallest buildable slice across the four planes, not a Detailed Design document for any one component.

## 1. Purpose

Every prior synthesis document, `plans/synthesis-capability-matrix.md` (D105), `plans/synthesis-architecture.md` (D106), and `plans/synthesis-resolutions.md` (D107), settled what to build and where it lives. None of them settled what to build first. This document answers that question directly, in service of a stated goal: reaching a point where Heimdall can be used to build Heimdall.

## 2. The dogfooding thesis

AETOS and Gleipnir each already self-host: AETOS uses its own workflow to develop itself, and Gleipnir does the same while it hardens AETOS's own weaknesses. Heimdall's version of this claim is stronger than either. If a heimdall-shaped development cohort proposes a commit, a push, or a merge, that proposal is exactly the shape of consequential action Gjöll's gate already exists to catch: an action-critical value, driving an action, that must not proceed without authorisation. Making Heimdall's own build pipeline the first real domain its safety architecture protects is not a side effect of self-hosting. It is the deepest available proof of the architecture, because the same gate that would stop a poisoned world-model value from triggering a wire transfer would gate a force-push to the main branch, on the same terms, with no special-casing for its own maintainers.

## 3. Strategy: a walking skeleton, cognition stubbed last

The four planes named in D105 and D106 each carry real uncertainty, but not the same kind. The process plane's sequencing logic and the output plane's gate logic are deterministic and can be proven correct by inspection and test. The cognition plane, an external model called for judgment, is the one plane whose behaviour cannot be fully specified in advance. Building the whole system by starting with cognition risks discovering integration problems in the deterministic layers only after the hardest, least controllable layer is already in place.

This document takes the opposite order. The first target is a walking skeleton: the thinnest possible slice that runs end to end, from a task through the process engine, through a proposed action, through Gjöll's gate, to an executed actuator call, and back. Cognition is stubbed first, a fixed or templated response standing in for a real model call, so the skeleton proves the wiring, specifically that the gate genuinely sits in the path and genuinely can block, before any model-integration complexity is introduced. A real model call is the first stub replaced once the skeleton is proven, precisely because it is the highest-uncertainty piece, not the lowest.

## 4. The single target loop

One concrete loop is the definition of done for this bootstrap phase: a heimdall-dev cohort, given a trivial, real coding task, produces a code change, proposes committing and pushing that change as an action, has that action evaluated by Gjöll's gate inside Himinbjörg's proposal-validation pipeline, and, if authorised, executes a real commit and push against a real git remote. The task is real. The cognition step that produces the code change is stubbed. The gate is real. The actuator's effect on the git remote is real and checkable by inspecting the resulting commit history, not by reading a log line asserting that it would have happened.

This loop is chosen because it touches every plane at least once, output (Gjöll's gate), process (the engine sequencing task through proposal through execution), hierarchy (one cohort definition, attested), and cognition (stubbed, but present as a named step in the sequence), while remaining small enough that a single session's build effort can plausibly close it.

## 5. Minimal slice per component

Each of the following is scoped to the smallest form that makes the target loop in section four possible, explicitly deferring generality to later.

**Himinbjörg, minimal slice.** Only enough of its four interfaces to gate one action for one hardcoded agent. `build_context` returns a fixed context for the one heimdall-dev agent, no world-model subgraph query. `enforce_definition` checks a single, hardcoded control surface rather than the full ten-group schema `HEIMDALL.md` specifies. `validate_proposal` is real, and must genuinely call Gjöll's gate at its check five, per `plans/dd/himinbjorg.md`'s own existing design. `broker_action` dispatches to exactly one actuator, the git actuator, with no general credential-scoping logic yet.

**Vör, minimal slice.** Not the general four-tier lattice for an arbitrary agent registry and cohort catalogue. One hardcoded cohort definition, attested with a keyed digest extending D103's `AgentContext` pattern, verified once at process start. No load-time manifest format, no writer taxonomy, no review-gated promotion pipeline. Those arrive when a second cohort needs to exist.

**The process engine, minimal slice.** A fixed sequence, not Gleipnir's general transition table: task in, cognition step (stubbed), propose-action step, gate step, execute step, result out. No loop caps, because there is exactly one path and nothing to loop. No human-question gate, because the target loop's action is deliberately chosen to be low-stakes enough not to need one for this first proof. Both are named explicitly as deferred, not silently dropped.

**Gjöll, re-expressed in Rust.** The existing `evaluate`/`enforce` logic and the three-condition rule, already demonstrated in `ontology/nornir/gjoll.py`, re-expressed natively per D105's ruling that nothing ports, everything is re-expressed. This is the smallest re-expression job of the six, because the existing logic is compact and already proven; the risk here is translation fidelity, not design.

**The git actuator.** A Rust component that shells out to the system `git` binary for exactly two operations, commit and push, against one preconfigured remote and branch. This is not a violation of the compiled-boundary principle: the boundary principle governs what adjudicates an action, never mutable and never interpreted, not every process a compiled binary is permitted to invoke. `git` itself is a compiled, externally audited tool, invoked deterministically with fixed arguments; the actuator does not interpret or evaluate anything, it executes only what Gjöll has already authorised.

**The cognition client, stubbed.** For this phase, a fixed or templated response, standing in for the real client interface D105 and D106 already named. Its replacement with a real model call is the first piece of Phase two work, not part of this phase.

**Explicitly out of scope for this phase, named so it is not silently assumed away:** the credential broker's general form, the generalised actuator sandbox for arbitrary tool or command execution, notify's real transport, coordinator memory, the cohort catalogue's general form, and anything belonging to the master-control tier. Every one of these remains exactly where D105, D106 and D107 already left it.

## 6. Build order

1. Re-express Gjöll in Rust, tested against the same cases the existing Python suite already proves, so the ported logic has an independent correctness check from day one.
2. Build Vör's minimal, single-cohort form, extending D103's attestation pattern rather than inventing a new one.
3. Build Himinbjörg's minimal four-interface slice, wiring `validate_proposal`'s check five to the Rust Gjöll from step one.
4. Build the git actuator and wire it behind `broker_action`.
5. Build the process engine's fixed five-step sequence, with the cognition step calling a stub.
6. Run the target loop end to end. This is the walking skeleton's completion, and the first point at which Heimdall has taken one real, gated, executed action.
7. Replace the cognition stub with a real model call behind the Rust client interface D105 and D106 already named, and re-run the target loop, now with a real model producing the proposed code change.

## 7. Definition of done

The target loop in section four runs, produces a real commit reachable in the git remote's history, and a deliberately introduced disallowed action, for example proposing a push directly to a protected branch or an action outside the hardcoded cohort's control surface, is blocked by the same pipeline rather than by a special case written for the test. The second half of that sentence matters as much as the first: a loop that only ever proves the authorised path proves nothing about the gate.

## 8. What this document does not settle

This is a build-order document, not a Detailed Design. Every component named in section five earns its own Detailed Design document once its own build begins, following `plans/dd/index.md`'s one-document-per-component convention, and none of the minimal-slice descriptions above should be read as a substitute for that fidelity. The exact manifest format for Vör's later, general form, the process engine's eventual loop-cap and human-question-gate design, and the cognition client's eventual grammar-constrained interface are all left for those later documents.
