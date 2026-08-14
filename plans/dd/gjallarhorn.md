# Detailed Design: Gjallarhorn (alert and escalation)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 3
**Status of the component today:** specified-only, per `plans/hld.md` section 3. Only the naming exists: `ontology/nornir/rules.py` calls a constraint violation a Gjallarhorn event. No routing, aggregation, containment decoupling or protected escalation channel is built.

---

## 1. Purpose

Gjallarhorn is Heimdall's alert and escalation layer. Its job is to take a typed security event raised by any component and route it to the correct response, from a log-only note to a full system halt, while guaranteeing two things a naive alerting layer does not. The offending run is contained whether or not a human ever sees the alert, and a genuine escalation reaches an operator on a channel a flood cannot bury.

This document takes Gjallarhorn to implementation fidelity for Phase 3: the per-event-type routing contract, the two load-bearing properties (containment decoupled from alerting, and alert aggregation), the protected escalation channel and its sampled prioritised triage queue, and the fail-closed behaviour of an unroutable event. It is the component that turns Heimdall's assumed-breach posture into an operational one: alerts are the human-visible edge of a defence whose containing actions have already fired.

## 2. Responsibilities and boundaries

In scope for Gjallarhorn:

- Accept a typed event from any component that can raise one, and route it per event type: log-only, human notification, agent halt or full system halt (HLD section 5.5, `HEIMDALL.md` 407 to 417).
- Aggregate correlated events into a single incident, so responders see incidents rather than event floods.
- Treat a spike in attempt-introspection or canary events as itself a single high-priority signal that triggers source quarantine.
- Deliver genuine security escalations on the protected channel, kept separate from the bulk unclassified-triage queue.
- Prioritise and sample the triage queue on provenance and source-reputation signals the attacker does not control, and age unreviewed items upward monotonically.
- Detect a queue flood as a condition in its own right and quarantine the flooding source.

Out of scope for Gjallarhorn:

- **Containment.** This is the boundary that matters most. Gjallarhorn does not halt Fenrir, discard poisoned output or quarantine a source-of-record by reaching into other components. Containment is performed automatically and per instance by the components that hold the risk (Fenrir halts itself on an attempt-introspection or canary fire; Himinbjörg blocks a failed proposal; Hliðskjálf refuses a broken chain). Gjallarhorn alerts; the containing components halt themselves. The `contain()` interface in section 3 records and coordinates a containment that has already been decided, it does not originate the decision to halt a run.
- Classification against the ontology (Nornir, document 4) and value gating (Gjöll, document 8). Gjallarhorn receives a constraint violation or a failed gate as an event; it does not re-run the check.
- Any language-model call. Routing, aggregation and prioritisation are deterministic code over typed events and provenance signals. A model here would be an injectable surface on the escalation path, which is precisely the path an attacker most wants to bend, so the layer contains no model.

## 3. The core contracts

### 3.1 raise(event) with per-event-type routing

`raise` is the single entry point. It accepts a typed event and routes it deterministically by event type. The signature:

```
raise(event: GjallarhornEvent) -> None
```

A `GjallarhornEvent` carries at least: `type` (one of the enumerated trigger types below), `source` (the raising component and the concrete origin, for example a mailbox id or a Fenrir instance id), `provenance` (the origin class and taint of any assertion involved, reusing the cross-cutting contract in `index.md` section 4.1), `severity`, a `correlation_key` (section 3.3) and the audit reference for the Hliðskjálf entry that already records the underlying decision.

The trigger types and their routing (`HEIMDALL.md` 407 to 417):

| Event type | Raised by | Default route |
|---|---|---|
| Instruction pattern detected at Bifröst | Bifröst | log-only (belt-and-braces signal; the boundary already quarantined the content) |
| Constraint axiom violated by an agent proposal | Nornir, Himinbjörg | human-notify; the proposal is already blocked |
| Taint-boundary breach attempt | Bifröst, Himinbjörg | human-notify |
| Anomaly surfaced by Huginn | Huginn | human-notify; a hard canary or attempt-introspection signal is halt-agent |
| Attempt introspection or canary fire (Fenrir) | Huginn over Fenrir | halt-agent, and the Fenrir instance is already halted per instance (section 3.2) |
| Resource-limit approach or breach | Himinbjörg | human-notify on approach, halt-agent on breach |
| Promotion request above the automated threshold | Himinbjörg | human-notify on the protected channel |
| Audit-log integrity failure | Hliðskjálf | halt-system; a broken signature chain is a trust-root failure |

Routing is data, not code branches: a routing table keyed by event type, resolvable per deployment, with a global default. An event type absent from the table does not fall through to log-only; it escalates (section 5). The four routes are ordered by force: log-only, human-notify, halt-agent, halt-system. `raise` writes every event to Hliðskjálf before routing, so the audit record does not depend on the route taken.

### 3.2 The two load-bearing properties

**Property one: containment is decoupled from alerting.** This is the anti-alert-exhaustion mechanism and the property to represent precisely. When attempt introspection or a canary check fires, the Fenrir instance is halted and its output discarded automatically, per instance, by the containing component itself, without waiting for any human to see an alert and without waiting on Gjallarhorn's delivery. The containment does not depend on the alert being seen, delivered, aggregated or even raised successfully. An attacker who buries the corresponding alert in a flood of noise gains nothing on the integrity axis, because the offending run is already contained regardless of whether the alert is ever read. Gjallarhorn's `raise` for such an event is therefore a notification of a containment that has happened, not a request for one. The alert can be dropped, delayed or aggregated with no effect on whether the poisoned run was stopped.

This is the split the whole design rests on. Alert-attention exhaustion is defeated on the integrity axis entirely, because containment is automatic and independent, and only mitigated on the attention axis, because a determined flooder can still cost operators triage effort (HLD section 9 and risk R-4). The honest boundary: burying alerts cannot blind operators to a real escalation, but it can still waste their triage time. Gjallarhorn closes the first and taxes the second; it does not claim to close the second.

**Property two: alert aggregation.** Human-facing alerting is aggregated. Correlated events, from a single source or matching a single pattern, collapse into one incident rather than paging per event. A storm of attempt-introspection or canary events across many Fenrir instances is not thousands of pages; it is a single high-priority signal, and that spike is itself the trigger for source quarantine. Aggregation is what makes the attention axis defensible at all: a responder sees incidents, weighted and prioritised, not an undifferentiated event flood. Aggregation never suppresses containment, because containment already happened per instance before aggregation runs. Collapsing 10000 canary fires into one incident does not un-halt any of the 10000 runs.

### 3.3 The protected escalation channel

Genuine security escalations travel on a protected channel that is separate, by construction, from the bulk unclassified-triage queue. Flooding the triage queue with edge-case-unclassifiable content cannot bury a real escalation, because the escalation was never in that queue (HLD section 9, `HEIMDALL.md` 988). The two are different data structures with different admission rules, not one queue with a priority field an attacker can contend for.

Three properties defend the protected channel and the triage queue that sits beside it:

- **Channel separation.** A promotion-above-threshold request, a Gjöll block routed to human authorisation, an audit-integrity failure and an attempt-introspection spike admit to the protected channel directly. Bulk `UNCLASSIFIED_DATA_ASSERTION` review admits to the triage queue. An attacker who controls external content can flood the triage queue; the content the attacker controls does not admit to the protected channel, because admission is by event type and source provenance, not by content the attacker writes.
- **Sampled and prioritised, not FIFO.** The triage queue is sampled and prioritised, weighting provenance and source-reputation signals the attacker does not control (the origin class, the source's clean-run history via the Fenrir corroboration track, whether the source is a known-critical inbound type). A flood of low-reputation edge cases does not push a high-reputation item down, because ordering is by signal, not by arrival time.
- **Monotonic age-up.** An unreviewed item ages upward monotonically. A legitimate but unclassifiable message from a critical source cannot be held down indefinitely by a continuous flood, because its priority only ever rises with age; it cannot be reset by newer arrivals. This closes the forced-misclassification suppression path (HLD risk R-5, `HEIMDALL.md` 989) for provenance-protected sources: UNCLASSIFIED content from a high-trust or safety-relevant source is routed to the protected channel rather than the bulk triage queue, so a failure to classify a message from a critical source is itself escalation-worthy rather than a silent suppression.

### 3.4 contain() and aggregate() at signature level

```
contain(instance_ref: InstanceRef, reason: ContainmentReason) -> None
aggregate(events: list[GjallarhornEvent]) -> Incident
```

`contain` records and coordinates a containment that the holding component has already performed (it does not decide to halt; see section 2). `instance_ref` identifies the halted Fenrir instance or blocked proposal; `reason` is the typed cause. Its effects are downstream of the halt: mark the source for quarantine assessment, anchor the containment to its Hliðskjálf entry and feed the aggregation state. Calling `contain` after the fact never un-does or re-does the halt; the halt is the containing component's, and it is idempotent from Gjallarhorn's side.

`aggregate` collapses a list of correlated events into a single `Incident` keyed by `correlation_key`. Correlation is deterministic over source and pattern: same source, same event type or same matched pattern collapse. An `Incident` carries the event count, the time window, the highest severity seen and the set of contained instances, so a responder reads one incident and sees the full scope. `aggregate` is pure over its inputs; it owns no side effect on containment.

## 4. Correlation and prioritisation

Aggregation and triage ordering both turn on signals the attacker cannot supply. This section fixes how each is computed, since a weak correlation key or a contendable priority would reopen the flooding path section 3 closes.

**Correlation.** An event's `correlation_key` is derived deterministically from its source and its pattern, never from attacker-supplied content. Two events collapse into one incident when they share a source (the same mailbox, feed or Fenrir instance family) or the same matched pattern class. A storm from many instances driven by one source collapses on the source term; a storm of one pattern across sources collapses on the pattern term. The key is computed by Gjallarhorn from typed event fields, so an attacker cannot forge distinct keys to defeat collapsing (which would turn one incident back into a page-per-event flood). This is why correlation reads the origin, not the body.

**Triage priority.** The triage queue orders items by a priority derived from provenance and reputation, not by arrival time. The inputs: the origin class (an `EXTERNAL_COMMS` edge case ranks below a known-critical inbound type), the source's clean-run history from the Fenrir corroboration track (read from Muninn), whether the source is a provenance-protected critical type and the item's age. Age enters as a monotonically rising term, so no newer arrival can lower an older item's priority. An attacker who floods with low-reputation content raises the queue's depth but cannot raise the priority of the content they control, because the reputation and provenance terms that dominate the ordering are outside their reach.

**The flood threshold.** A flood is a rate condition. Gjallarhorn watches the triage-admission rate per source; a source crossing the threshold is quarantined (section 5) rather than admitted further. Measuring the rate per source means a single flooding source is contained without penalising legitimate load from other sources.

## 5. Fail-closed behaviour

Gjallarhorn fails closed toward escalation. An alerting layer that fails by dropping is the one an attacker wants, so every failure mode routes upward, never to silence.

- An event whose type is absent from the routing table does not fall through to log-only. It escalates to human-notify on the protected channel as an unknown-event, so a new or malformed event type surfaces rather than vanishing.
- An event that cannot be routed at all (a malformed event, a routing-table read that raises) escalates rather than being dropped, and is written to Hliðskjálf first, so the failure to route is itself an audited event.
- A queue flood is a quarantine trigger, not an enqueue. When the triage-admission rate crosses the flood threshold, Gjallarhorn quarantines the flooding source and raises a single high-priority incident, rather than admitting unbounded content. The pull paradigm (HLD Design Principle 11) means the source cannot force proportional processing; quarantine is the enforcement of that at the alerting layer.
- Aggregation failure fails toward paging: if the aggregation state is unavailable, events are delivered individually rather than dropped in the name of collapsing them. Over-paging is a cost; a missed page is a failure.
- Containment never depends on Gjallarhorn being up. Because containment is performed by the holding component per instance (section 3.2), a Gjallarhorn outage cannot leave a poisoned run active. It can only delay the human-facing alert, which the aggregation and protected-channel design already tolerate.

## 6. Data owned

- **The routing configuration.** The per-event-type routing table (event type to route), the global default and the flood threshold. Data, resolvable per deployment, not code branches.
- **Incident-aggregation state.** The open incidents keyed by `correlation_key`, each with its event count, time window, highest severity and contained-instance set. This is the state `aggregate` reads and updates; it is derived from events and rebuildable from the Hliðskjálf record, so a loss fails toward per-event paging (section 5).
- **The protected-channel queue and the triage queue.** Two separate structures. The protected channel holds admitted escalations; the triage queue holds bulk unclassified-review items with their priority (provenance and reputation signals) and their age counter. The admission rule (which structure an item enters) is owned here and is by event type and source provenance, never by attacker-supplied content.
- **The source-reputation signals** used for triage prioritisation: origin class, clean-run history and known-critical-source membership. These are read from Muninn and the world model; Gjallarhorn owns the weighting, not the underlying history.

No persistent decision authority: the authoritative record of every event is in Hliðskjálf. Gjallarhorn's state is routing configuration plus derived queues and incidents.

## 7. Dependencies

- Upstream: every component that can raise an event. Bifröst (instruction pattern at the boundary), Nornir (constraint violation), Himinbjörg (proposal block, resource limit, promotion-above-threshold, taint-boundary breach), Huginn (canary and attempt-introspection signals, anomalies) and Hliðskjálf (audit-integrity failure). Gjallarhorn does not poll them; they call `raise`.
- Downstream: the protected escalation channel (delivery to the operator), source quarantine (the pull-loop deprioritisation and quarantine that Bifröst's ingestion cadence honours) and Hliðskjálf (every event is written before routing).
- Lateral: Muninn and the world model, read for the source-reputation signals that prioritise the triage queue (section 6). Read-only; Gjallarhorn does not write agent history.

Gjallarhorn holds no credentials and no git or platform access. It is a routing and queueing layer over typed events, and its only authority is over its own routing configuration and derived queues.

## 8. Build delta from today

Per HLD section 3, Gjallarhorn is specified-only, and the delta is nearly the whole component.

- Only the naming exists: `ontology/nornir/rules.py` calls a constraint violation a Gjallarhorn event, and `ontology/nornir/engine.py` treats an `action_critical_must_gate` divergence as one. There is no `raise`, no routing table, no `contain`, no `aggregate` and no queue.
- The per-event-type routing table and the four routes (log-only, human-notify, halt-agent, halt-system) are new, Phase 3.
- The containment-decoupling property is a design contract to hold, not code to add here: containment lives in the holding components (Fenrir's self-halt, Himinbjörg's block, Hliðskjálf's chain refusal). Phase 3 builds `contain` as the record-and-coordinate side of that already-decided halt (section 3.4), and the test that proves the decoupling (section 9).
- Alert aggregation, the protected escalation channel, the sampled prioritised triage queue and the monotonic age-up are all Phase 3 and all new.
- Queue-flood detection and source quarantine are Phase 3, wired to the pull-loop deprioritisation that Bifröst's ingestion cadence already assumes.

The dependency order: Gjallarhorn's containment-decoupling test cannot be meaningful until Fenrir's attempt-introspection self-halt exists (Phase 2), so this component's tests inherit the Phase-2 Fenrir and Huginn behaviour and add the routing, aggregation and channel behaviour on top.

## 9. Test plan

Each security property is tested by its failure mode, per `index.md` section 5, not only its happy path.

- **Event routing per type.** For each enumerated event type, assert `raise` routes to the expected route in the table (log-only, human-notify, halt-agent, halt-system), and that every event is written to Hliðskjálf before routing regardless of route. An audit-integrity-failure event routes to halt-system; an instruction-pattern-at-Bifröst event routes to log-only.
- **Containment fires without alert delivery.** The load-bearing test. Simulate an attempt-introspection fire with the alert-delivery path disabled or flooded, and assert the Fenrir instance is halted and its output discarded regardless. This proves containment does not depend on the alert being seen: with `raise` dropping every event, the run is still contained. A green here is the whole anti-alert-exhaustion claim.
- **Aggregation collapses a correlated storm.** Feed a storm of correlated canary fires from one source and assert `aggregate` collapses them into one `Incident` with the correct count, window and contained-instance set, and that exactly one high-priority signal is delivered, not one per event. Assert separately that every underlying run was still contained per instance (aggregation did not suppress containment).
- **Protected channel survives a triage flood.** Enqueue a genuine escalation on the protected channel, then flood the triage queue with edge-case-unclassifiable content, and assert the escalation is still delivered and still reachable. The escalation must not be buried, because it was never in the flooded queue.
- **Queue flood triggers quarantine.** Drive triage admission past the flood threshold and assert the flooding source is quarantined and a single incident is raised, rather than unbounded enqueuing. Assert the pull loop honours the quarantine (the source is deprioritised, not force-consumed).
- **Forced-misclassification from a critical source routes to the protected channel.** An `UNCLASSIFIED_DATA_ASSERTION` from a known-critical source (recognised by source and channel provenance, not content) routes to the protected channel, not bulk triage, and ages upward monotonically. This tests HLD risk R-5: obscuring the body of a legitimate high-priority signal does not suppress it, because the source provenance the attacker does not control routes it to escalation.
- **Fail-closed unknown event.** An event whose type is absent from the routing table escalates to human-notify on the protected channel, never falls through to log-only, and is audited.

Coverage is reported line and branch. The fail-closed branches (unknown-event escalation, unroutable-event escalation, flood-to-quarantine, aggregation-unavailable-pages-individually) are covered explicitly, because a green count over low branch coverage on the failure paths is not evidence for an alerting layer whose failure paths are the point.

## 10. Decisions (index)

| # | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| GJ-1 | Containment origin | Containment lives in the holding component (Fenrir self-halt, Himinbjörg block, Hliðskjálf refusal); Gjallarhorn records and coordinates via `contain`, it does not decide to halt | Gjallarhorn reaches into components and halts them on alert | Decoupling containment from alerting is the anti-alert-exhaustion property. If Gjallarhorn had to act for containment to happen, burying its alert would benefit an attacker. Per-instance self-halt makes containment independent of alert delivery. |
| GJ-2 | Alert delivery model | Aggregated incidents keyed by correlation, delivered to responders | Per-event paging | Aggregation is the attention-axis mitigation: responders see incidents, not floods. A correlated storm is one high-priority signal. Containment already happened per instance, so aggregation never suppresses it. |
| GJ-3 | Escalation vs triage separation | Two separate structures with admission by event type and source provenance | One queue with a priority field | Flooding the triage queue must not be able to bury a real escalation. Separate structures with attacker-uncontrolled admission make burying structurally impossible, not merely unlikely. |
| GJ-4 | Triage ordering | Sampled and prioritised on provenance and reputation, with monotonic age-up | FIFO | FIFO lets a flood push legitimate items down indefinitely. Prioritising on signals the attacker does not control, plus monotonic age-up, closes the forced-misclassification suppression path (R-5) for provenance-protected sources. |
| GJ-5 | Queue-flood handling | Flood is a quarantine trigger, not an enqueue | Unbounded enqueue with backpressure | The pull paradigm means a source cannot force proportional processing. Quarantine enforces that at the alerting layer; unbounded enqueue is the DoS the pull paradigm exists to refuse. |
| GJ-6 | Unroutable event | Escalate to the protected channel and audit | Drop or log-only | An alerting layer that fails silent is the one an attacker wants. Fail closed means fail toward escalation, so a new or malformed event surfaces rather than vanishing. |

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
