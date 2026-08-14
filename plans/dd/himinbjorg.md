# Detailed Design: Himinbjörg (gateway process and control surface)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 3
**Status of the component today:** specified-only, plus a dormant `AgentContext` stub with 4 fields (`ontology/yggdrasil/control_surface.py`), per `plans/hld.md` section 3. This is the single largest unbuilt piece and the Phase-3 critical path.

---

## 1. Purpose

Himinbjörg is the gateway process. It owns the control channel exclusively, and nothing executes without passing through it. It has four jobs: build agent context from the world model, enforce each agent's control surface, validate every proposal before execution and broker credentialled actions so agents never see plaintext secrets. It also applies the Gjöll gate at action time (see `gjoll.md`) and routes Gjallarhorn alerts (see `gjallarhorn.md`).

This is the component that makes the whole architecture's central claim real in operation: the LLM proposes, the harness acts. Every other component feeds Himinbjörg or is fed by it; it is where the deterministic decision that content cannot make is actually made.

This document takes Himinbjörg to implementation fidelity for Phase 3, binding it to the OpenCode/Gleipnir reference primitives set out in `index.md` section 3.

## 2. Responsibilities and boundaries

In scope for Himinbjörg:

- Construct a normal agent's context from Mímisbrunnr, never from raw external content.
- Resolve and enforce each agent's symbolic definition (the control surface) under its trust-level ceiling.
- Validate every proposal against the six checks before execution.
- Broker credentialled actions without exposing credentials to the agent.
- Apply the Gjöll gate to any action-critical value a proposal consumes.
- Own the canonical control channel (index.md section 4.4); no other component writes to it.

Out of scope for Himinbjörg:

- Reading tainted content. That is Fenrir (`fenrir.md`). Himinbjörg constructs the canary wrap Fenrir runs under, but it does not itself read the payload.
- Holding world state. That is Mímisbrunnr (`mimisbrunnr.md`). Himinbjörg reads it to build context; it does not own it.
- Deciding a value's action-critical status. That is Mímisbrunnr's maintained flow-to-sink label, which Gjöll reads. Himinbjörg invokes the gate; it does not compute the label.

## 3. Context construction

A normal agent never receives a raw content window. Himinbjörg builds its context from Mímisbrunnr, so the only content an agent reasons over is typed, classified, provenanced world state. What a normal agent receives (from `HEIMDALL.md` 302 to 308):

- its identity summary (the symbolic-definition summary),
- a typed relevant subgraph of the world model,
- its standing constraints (applicable global and agent-specific rules),
- the task context,
- the canonical control channel (canonical instructions from authorised sources only).

There is deliberately no content window. Reintroducing one would reopen the injection surface Fenrir exists to close, so the absence is a binding rule, not a default. A task that needs an LLM to read tainted content directly is routed to Fenrir, whose output returns to Mímisbrunnr as tainted assertions and reaches a normal agent only after classification.

### 3.1 Interface

```
build_context(agent_id: AgentId, task: TaskContext) -> AgentContext
```

`AgentContext` carries the five elements above and no raw payload field. The dormant stub at `ontology/yggdrasil/control_surface.py` models an early four-field form of this (`agent_id`, `permitted_actions`, `trust_ceiling`, `consequential_sinks`); the Phase-3 build extends it to the full context and adds the world-model subgraph query.

The subgraph is scoped to the agent's world-model read scope (section 4), so context construction and control-surface enforcement share one scope definition rather than two that could drift.

## 4. The control surface

Every agent is a first-class object with two inseparable halves: a symbolic definition (deterministic, enforced by Himinbjörg) and a neural persona (probabilistic, shaping the LLM's reasoning). Neither half is sufficient alone. Himinbjörg enforces the symbolic half; the persona is passed to the model but carries no authority.

### 4.1 The symbolic definition

The full schema is `HEIMDALL.md` 331 to 384. At the interface level, an agent's symbolic definition carries: an id and type, a trust level (0 to 5), a world-model read and write scope, and 10 control groups: tools, filesystem, network, resources, credentials, subagents, inter-agent, exfiltration, temporal and escalation. This document does not restate the schema field by field; the schema in `HEIMDALL.md` is authoritative. It specifies how Himinbjörg enforces it.

### 4.2 Enforcement: deny-by-default, ceiling-bounded

Enforcement uses the OpenCode/Gleipnir deny-by-default pattern (index.md section 3). Three binding rules:

- A capability an agent's definition does not grant is absent, not merely denied. The enforcement is an allowlist of exact capabilities, never a denylist of patterns. This is the lesson Gleipnir already paid for: a pattern deny (for example a `git*` string deny) is evadable by a compound command (`sh -c "git push"`), whereas an allowlist of exact capabilities has no such gap. Himinbjörg grants named capabilities; anything unnamed cannot be invoked.
- Global defaults apply to every agent. An agent definition may override a control within its trust-level ceiling and never above it. An agent cannot grant itself a capability its definition does not carry, and cannot raise its own ceiling.
- The trust level is a ceiling on what the definition may grant, not a grant in itself. An agent at level 4 may be defined far more narrowly. Elevating an agent's trust level is a human-authorised action logged to Hliðskjálf.

### 4.3 Interface

```
enforce_definition(agent_id: AgentId) -> ControlSurface
```

Resolves global defaults with the agent's overrides under its trust ceiling, and returns the effective control surface applied at agent start through the Harness Boundary Interface's agent-start-enforcement group (index.md section 3). Applied before the first token, so the agent operates within its definition from the start.

## 5. Proposal validation

Every agent proposal returns to Himinbjörg before any execution. This is the operational form of "the LLM proposes, the harness acts": the proposal is a request, not an instruction, and Himinbjörg is the sole arbiter of whether it becomes an action.

### 5.1 The six checks

From `HEIMDALL.md` 314 to 323, in order:

1. the action type exists in the agent's permitted action space,
2. the target is in scope per the world model,
3. no constraint axiom is violated,
4. the blast radius is within authorised bounds,
5. the taint level of the inputs is compatible with the action,
6. the resource budget is not exceeded.

Check 5 is where Gjöll enters: if the proposal consumes an action-critical value as an action instruction, the Gjöll gate (see `gjoll.md`) runs as part of the taint-compatibility check, and a value that passes no gate blocks the proposal. Check 3 covers the constraint axioms Nornir also enforces on assertion; here they are enforced on the proposed action.

### 5.2 Interface

```
validate_proposal(agent_id: AgentId, proposal: Proposal) -> Decision
```

where `Decision` is one of `ALLOW`, `BLOCK`, `QUEUE` (for human authorisation) or `ESCALATE` (a Gjallarhorn event). A proposal failing any check is blocked, logged to Hliðskjálf with the failing check, and optionally escalated. The decision and its check results are written to Hliðskjálf before any allowed action fires, so the audit trail records the authorisation, not just the outcome.

This is the OpenCode/Gleipnir tool-call-interception binding (index.md section 3): the `tool.execute.before` gate inspects the proposal's typed arguments against the control surface and the world state and refuses out of policy. The reference implementation reuses Gleipnir's proven gate shape.

## 6. Credential brokering

Agents never see plaintext credentials. When an action needs a credential, Himinbjörg performs the authenticated action on the agent's behalf within a permitted credential scope, and the agent receives only the result. This is the single-holder pattern from Gleipnir (index.md section 3): the credential is held in one place the agent cannot reach, and every credentialled action is brokered, not delegated.

### 6.1 Interface

```
broker_action(agent_id: AgentId, action: Action, credential_scope: Scope) -> Result
```

The credential store is a trust root (section 8): Himinbjörg brokers access to it, but the store's own security is a prerequisite, not a product, of the architecture. The broker refuses a scope the agent's definition does not permit, deny-by-default as in section 4.2.

## 7. Fail-closed behaviour

- A proposal that fails any of the six checks is blocked, never allowed through on a partial pass.
- A proposal consuming an action-critical value that passes no Gjöll gate is blocked and routed to human authorisation on the protected channel (not the bulk review queue), per `gjoll.md`.
- A capability not explicitly granted is absent; an agent cannot invoke it, and an attempt is a control-surface violation raised to Gjallarhorn.
- An override that would exceed the trust ceiling is refused; the effective control surface is the intersection of the definition and the ceiling, never the union.
- If context construction cannot resolve a clean typed subgraph (for example a required node is missing or unclassified), the agent receives less scope, never a raw-content fallback. There is no code path from a context-construction failure to a raw content window.
- A decision that cannot be written to Hliðskjálf blocks rather than proceeding unlogged (see `hlidskjalf.md` section 5).

## 8. Data owned

- The agent definitions (the symbolic halves).
- The global default control surface.
- The live authorisation state and the active credential-broker sessions.

Himinbjörg reads Mímisbrunnr and does not own it. The credential store and the canonical control channel are trust roots Himinbjörg mediates access to but does not itself secure (section 8.2 of the HLD).

## 9. Dependencies

- Upstream: Mímisbrunnr (context source), the agent runtime via the Harness Boundary Interface (proposals arrive through tool-call interception).
- Downstream: Gjöll (action-critical value gating, invoked in check 5), Gjallarhorn (escalation), Hliðskjálf (every decision logged), the credential store (brokering), Fenrir (Himinbjörg constructs the canary wrap for a tainted-content task).
- The Harness Boundary Interface is the seam to the host harness; the reference binding is OpenCode/Gleipnir (index.md section 3).

## 10. Build delta from today

Himinbjörg is essentially unbuilt. The dormant `AgentContext` in `ontology/yggdrasil/control_surface.py` models about 4 of roughly 20 control fields and holds no behaviour. The Phase-3 build must deliver:

- the gateway process itself, as the sole owner of the control channel,
- context construction from Mímisbrunnr (the `build_context` interface and the scoped subgraph query),
- full control-surface resolution and enforcement (the 10 control groups, global-default-plus-override, ceiling-bounded, deny-by-default),
- the six-check proposal-validation pipeline with the Gjöll gate wired into check 5,
- credential brokering,
- the Harness Boundary Interface binding to OpenCode/Gleipnir (tool-call interception, agent-start enforcement, provider-request interception, trust ownership, episode capture).

This is the largest single build in Phases 1 to 3 and the phase's critical path. The reference binding reuses Gleipnir's proven deny-by-default permission map, trust-tier ladder, deterministic proposal-then-act sequencing and single-holder credential broker, so the control-surface work builds on a running precedent rather than inventing one. The novel work is the Heimdall-specific parts: context construction from a typed world model, the six-check pipeline and the Gjöll integration, none of which have an OpenCode analogue.

## 11. Test plan

The security properties are tested by their failure modes, not only their happy paths (index.md section 5):

- Context isolation: assert a constructed `AgentContext` contains no raw-payload field for any agent, and that an agent's subgraph is bounded to its read scope. Plant a tainted node outside scope and assert it is absent from the context.
- Deny-by-default: assert a capability not granted in a definition cannot be invoked, and that the attempt raises a control-surface violation. Assert the enforcement is allowlist-based by testing a compound-command form that a pattern deny would miss (the Gleipnir enumerable-bypass lesson) and confirming it is absent-by-capability, not merely denied.
- Ceiling enforcement: an agent definition requesting an override above its trust ceiling resolves to the ceiling, never the requested value. The effective surface is the intersection.
- Proposal validation: for each of the six checks, a proposal that fails only that check is blocked with the failing check recorded to Hliðskjálf; a proposal passing all six is allowed and logged.
- The Gjöll integration (check 5): a proposal consuming an action-critical untrusted-derived value as an action is blocked; the same value consumed as inert data is allowed. This inherits the proven gate behaviour in `ontology/nornir/gjoll.py` and is specified fully in `gjoll.md`.
- Credential non-exposure: assert an agent never receives a plaintext credential, and that a brokered action outside the agent's permitted scope is refused.
- Fail-closed: a context-construction failure yields less scope, never a raw-content fallback; a decision that cannot be logged blocks.

Coverage is reported line and branch, with the fail-closed and ceiling-intersection branches covered explicitly, since they are the point of the gateway.

## 12. Decisions (index)

| # | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| HB-1 | Enforcement model | Deny-by-default allowlist of exact capabilities, ceiling-bounded | Denylist of forbidden patterns | A pattern deny is evadable by a compound command; an exact-capability allowlist has no such gap. The Gleipnir enumerable-bypass lesson (index.md section 3). |
| HB-2 | Context source | Always Mímisbrunnr, never a raw content window for a normal agent | A content window for convenience on some agent types | A content window is the injection surface Fenrir exists to close. The absence is a binding rule; there is no code path to a raw-content fallback. |
| HB-3 | Effective control surface | The intersection of the definition and the trust ceiling | The union, or the definition as requested | An agent must not raise its own authority. The intersection guarantees an override never exceeds the ceiling. |
| HB-4 | Gjöll placement | Inside proposal-validation check 5 (taint compatibility), at action time | A separate pre-check, or on assertion rather than action | Gjöll gates the action, not the assertion (a value can be correctly typed and provenanced and still poisoned). Placing it in the action-time check is where the action-critical determination is meaningful. See `gjoll.md`. |
| HB-5 | Harness binding | OpenCode/Gleipnir reference via the HBI (index.md section 3) | A pi.dev-only binding hard-coded here | HLD D-1. The reference reuses Gleipnir's proven control-surface pattern where Heimdall needs it most; the HBI keeps the architecture portable. |
| HB-6 | Logging order | Write the decision and its check results to Hliðskjálf before an allowed action fires | Log after execution | The audit trail must record the authorisation, not just the outcome, so a decision cannot fire unlogged (`hlidskjalf.md` section 5). |

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
