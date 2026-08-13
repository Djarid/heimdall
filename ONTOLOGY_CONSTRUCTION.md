# Heimdall: Ontology Construction (Yggdrasil)

**Author:** Jason Huxley
**Version:** 1.0
**Date:** August 2026
**Status:** construction methodology for the ontology framework; Phase 1 seed only is built
**Reads with:** `HEIMDALL.md` (the architecture), `NEUROSYMBOLIC_FILTER_INVARIANTS.md` (the invariants, especially 3.11), `GLOSSARY.md` (component names)

---

## 1. Purpose

The premise PoC proved the neurosymbolic filter's structural half: untrusted content cannot become an instruction. It left the load-bearing other half untested, because it had no ontology (see `NEUROSYMBOLIC_FILTER_INVARIANTS.md`, invariant 3.11). The guarantee the whole filter offers is exactly as strong as the ontology's coverage, and gaps in the ontology are gaps in the boundary (HEIMDALL.md design principle 10).

This document defines how that ontology is built, grown and tested. It is the "how" behind invariant 3.11. It is a methodology, not an implementation: it composes the layers, recommends a substrate, defines the Phase 1 seed, states the marshalling contract, sets out how rules are authored and how coverage grows, and specifies the test obligations. It answers the three ontology-related open questions in HEIMDALL.md (substrate, bootstrapping, marshalling) as decisions, and names what remains open.

The ontology framework takes the name **Yggdrasil**, reserved in the glossary for exactly this: the connecting structure of types and relations within which all of Heimdall's knowledge is arranged. The glossary marks it "(future)", and that is honest: this document builds only the Phase 1 seed. The full framework is later-phase.

Yggdrasil is not a component that acts. It is the type structure that two components consume. Nornir reasons over it. Mímisbrunnr stores typed nodes whose types come from it. Neither is the ontology itself.

The tree lives on disk under `ontology/`, with each layer as a directory and its own README. The sources are already fetched: BFO 2020 (loaded, CC BY 4.0) under `ontology/upper/bfo`, and SUMO (reference only, GPL, never loaded) under `ontology/reference/sumo`. See `ontology/README.md` for the map and the loaded-versus-reference split, which is also the licence boundary (decisions D39 and D40).

---

## 2. What Yggdrasil holds, and what it does not

The most common way an ontology programme fails is by conflating things that vary along different axes, so the type structure fragments into unmaintainable silos. Heimdall's composition avoids this by keeping two variations strictly apart.

### 2.1 Two orthogonal axes of variation

There are two independent axes along which the system varies, and only one of them lives in the ontology:

- **By domain (in Yggdrasil).** Subject-matter types: communications, scheduling, finance, infrastructure. This is the layer that multiplies as the system takes on new domains.
- **By agent (in Himinbjörg's control surface, not Yggdrasil).** Which actions a given agent may perform, which constraints bind it, and its trust ceiling. This is per-agent and does not belong in the ontology.

The axes are orthogonal. A single agent may operate across several domains. A single domain may be touched by several agents with different permissions. Building the ontology per-agent, or the control surface per-domain, would couple two things that must move independently.

### 2.2 The composed ontology, by scope

Yggdrasil composes five layers. Only one multiplies by domain. Two of them define shared vocabulary but must not be confused with the per-agent binding that selects from that vocabulary.

| Layer | Source | What it is | Scope |
|-------|--------|-----------|-------|
| Upper | SUMO / BFO | General types and relations | System-wide, shared |
| Domain | Extensible per deployment | Subject-matter types | One layer per subject-matter domain |
| Action vocabulary | Heimdall-defined | The action types that can exist | System-wide vocabulary; binding to agents is not here (see 2.3) |
| Constraint vocabulary | Heimdall-defined | The constraint axioms that can be expressed | System-wide vocabulary; binding to agents is not here (see 2.3) |
| Trust | Heimdall-defined | Taint and promotion types (TAINTED, VOUCHED, TRUSTED, CANONICAL) | System-wide, shared |

Domain layers extend the upper ontology. They add subject-matter types beneath the general types; they never redefine a general type. This is what lets a fact expressed in one domain relate to a fact in another through their common ancestors, and it is what keeps the domains from drifting into mutually unintelligible dialects.

### 2.3 Vocabulary is in the ontology; binding is in the control surface

The action and constraint layers define vocabulary only: the set of action types that can exist and the set of constraint axioms that can be written. They do not record which agent may do what. That binding is per-agent and lives in Himinbjörg's control surface (HEIMDALL.md design principle 5 and the agent-definition schema): a global default control surface, with agent-level overrides that take precedence for that agent only, bounded by the agent's trust-level ceiling. An agent cannot grant itself a permission above its ceiling.

So the honest correction to a naive "one ontology per domain" picture is this. Yggdrasil holds the shared spine (upper, trust, action and constraint vocabulary) plus a per-domain type layer. The per-agent selection from the action and constraint vocabulary is not in Yggdrasil at all; it is control-surface state enforced by Himinbjörg. Proposal validation checks the agent's permitted action space (control surface) against actions whose types are defined in the ontology.

### 2.4 Domains are subject-matter, not medium

A domain is a subject-matter area, not a source medium. Email is only one ingestion source, and not the main one. The real threat surface is any external content an LLM agent reads: web pages, social-media content, documents, transcribed audio, tool output. An agent browsing the open web or reading a social feed is consuming attacker-controllable content of exactly the same trust class as an email body, and often less structured and higher volume. Web content and social media that express the same fact as an email must land as the same typed assertion; this is the medium-blindness the architecture requires (HEIMDALL.md Phase 4). The parser at Bifröst sets the taint class (`EXTERNAL_WEB`, `EXTERNAL_COMMS`, `EXTERNAL_DOCUMENT` and so on); the domain layer sets the type. A "payment request" is a finance-domain concept regardless of whether it arrived by email, in a web page or in a social-media message.

The anti-pattern to avoid by name: an "email ontology", a "web ontology", a "social-media ontology", a "PDF ontology". Per-medium ontologies make medium-blindness impossible and give the same real-world fact incompatible types depending on how it arrived. Worse, they invite the assumption that email is the domain and web or social content is a special case, when both are just untrusted media feeding the same subject-matter types. Organise the domain layer around what the content is about, never around how it was parsed or where it came from.

### 2.5 Consequence for action-critical status

Because the per-agent binding lives in the control surface, action-critical status is agent-scoped. Whether a value is action-critical depends on whether it can reach a consequential sink, and which sinks are reachable depends on a given agent's permitted action space. A value can be action-critical for a high-trust agent that can reach a consequential sink and inert for a constrained agent that cannot. The flow-to-sink analysis (section 8) is therefore computed against an agent's reachable sink set, not against a domain-global set. This is developed under testing, because it changes what a test fixture must carry.

---

## 3. Substrate

**Recommendation: a property graph, Memgraph, as both the world-model store (Mímisbrunnr) and the substrate the reasoner (Nornir) operates over.** The recommendation is firm but ratified by a spike with the pass criteria in 3.3, so it is falsifiable rather than assumed.

### 3.1 Why a property graph

The deciding criterion is Gjöll's flow-to-sink action-critical propagation. Action-critical status must propagate backward from consequential sinks to every value that can reach them, transitively, and it must be available at action-authorisation time without an expensive query. This is maintained most efficiently as an incremental, backward-propagated label written at the moment an edge is added, which a property graph supports naturally. The alternative, an RDF triple store answering SPARQL property-path queries at authorisation time, pays the reachability cost on the hot path, at authorisation, which is exactly where latency is least affordable.

A property graph also holds the composed structure cleanly: one global node space, per-domain type labels on nodes, a single global write/read dependency graph for reachability, and the trust lattice as node properties. The ontology-versus-control-surface line (2.3) is preserved: Yggdrasil types label the nodes; the per-agent control surface stays in Himinbjörg and is consulted at proposal-validation and reachability time. Agent permissions are not modelled as graph state.

### 3.2 The honest trade-off

A property graph is less expressive than OWL for classical description-logic inference, and its constraint checking is less standardised than an OWL reasoner's. For Heimdall this is an acceptable loss: the reasoning Heimdall needs (forward-chaining derivation, constraint-axiom checking, transitive reachability) is served well by a property graph with a rule engine, and the reachability requirement dominates. If a future domain needs heavy description-logic inference the decision can be revisited, but the flow-to-sink hot path is the load-bearing case and it points at a property graph.

### 3.3 The ratification spike (Phase 2)

Before committing, run a spike with these pass criteria:

1. **Write-time label maintenance.** Adding an edge that creates a path from a value to a consequential sink marks that value action-critical at write time, in bounded time, without a full-graph traversal.
2. **Authorisation-time read.** Querying whether a value is action-critical at action time is a property read, not a traversal.
3. **Edge-deletion retraction.** Removing an edge correctly retracts action-critical labels from values that no longer have a path to any sink. This is the known hard case (see 10). The spike must demonstrate correct retraction or a sound conservative over-approximation (never retract a label that should stay), and measure its cost.
4. **Scale.** The above hold at a node and edge count representative of a realistic Mímisbrunnr, not a toy graph.

If criterion 3 cannot be met soundly at acceptable cost, that is the signal to reconsider a Datalog engine (for example Soufflé) for the reasoning layer while keeping the property graph for state, and the spike report should say so.

### 3.4 Upper ontology and the question of breadth

The upper layer's source (the `SUMO / BFO` choice in HEIMDALL.md) interacts with the substrate, so it is decided here. The two candidates differ by roughly three orders of magnitude: BFO is about 35 classes, a minimal rigorous spine designed to be extended; SUMO with its domain ontologies is about 25,000 terms and 80,000 axioms, broad and richly axiomatised, with ready-made communications, finance, government, law and media domain ontologies.

The decision hinges on breadth, and the naive reading is the wrong way round. With LLM agents reading open web and social-media content, the subject-matter surface is effectively unbounded, so more coverage sounds like exactly what is wanted, and SUMO's breadth sounds like an asset. It is not, for three reasons specific to this system.

First, coverage that is not tested is not trusted. Under invariant 3.11 every classification rule is part of the trust boundary and must be validated against a ground-truth corpus. Adopting SUMO wholesale means either testing 25,000 terms' worth of classification behaviour to that standard, or carrying most of the ontology as unaudited surface. Untested breadth in a trust boundary is a liability, not an asset. BFO's 35 classes are auditable; the whole of SUMO is not.

Second, the filter needs typed inertness, not semantic richness. Its job is to classify untrusted content into typed, provenance-stamped, mostly-inert assertions, not to reason deeply about the world. A web page about a political event needs to type as an untrusted document with extracted entities; it does not need SUMO's axioms about politics. SUMO's breadth is depth-of-meaning, which is largely orthogonal to what a taint-typing classifier uses.

Third, coverage should grow demand-driven, not be front-loaded. The growth model (section 7) is that `UNCLASSIFIED` accumulates and coverage is extended where real traffic demands it. Loading all of SUMO front-loads coverage speculatively, most of which the actual traffic never exercises, while still owing the full test burden on all of it.

So the answer to "why not use SUMO's breadth" is: not because breadth is unwanted, but because loaded breadth is untested trust-boundary surface, semantic richness the classifier does not use, and speculative coverage the growth model does not want. The decision is **BFO as the loaded spine**, confirmed by a Phase 2 spike.

SUMO's breadth is kept as a reference library, not loaded. When coverage is extended for a newly-common `UNCLASSIFIED` pattern (section 7), SUMO's relevant domain ontology is a source to import and prune from rather than authoring types from nothing. That captures the value of the breadth (a head start on domain types) without its cost (untested surface, speculative loading). If it is ever used this way, note that SUMO already publishes a Neo4j translation, so importing a pruned subset into a property-graph substrate needs no triple-store conversion.

---

## 4. The minimum viable Phase 1 ontology

Phase 1 starts with a single ingestion medium for staging reasons (the architecture names email, HEIMDALL.md Phase 1), with read-only, human-gated autonomy and an empty action-critical set. This is a starting point chosen to make the first build tractable, not a statement that email is the threat. The threat is external content read by an LLM agent, of which web and social-media content are the larger and less structured part, and the seed ontology must be built so those media attach as further ingestion sources feeding the same subject-matter types, not as new domains. The Phase 1 ontology is correspondingly small, and deliberately built so both a second medium and a second subject-matter domain attach later without disturbing it.

### 4.1 What Phase 1 builds

- **The shared spine.** A minimal upper layer (enough BFO or SUMO types to anchor the domain layer; the upper-ontology choice is a tracked decision, see the decision log), the trust lattice (TAINTED, VOUCHED, TRUSTED, CANONICAL), and the action and constraint vocabularies. The action vocabulary in Phase 1 is small and read-only or human-gated (classify, triage, summarise, draft-for-review). The constraint vocabulary carries the axioms Phase 1 needs.
- **One subject-matter domain: communications.** The subject-matter types for a message from a person or organisation, whatever medium carried it. The PoC's flat four-field schema (`sender_extracted`, `subject_extracted`, `requested_action_summary`, `entities`) is the seed. It becomes typed nodes under the communications domain, with a type hierarchy rather than a flat list, and each type carries the machinery for an `action_critical` declaration even though the Phase 1 action-critical set is empty. These types are deliberately medium-neutral, so that a web page or social-media post expressing a communication types identically to an email.
- **The `UNCLASSIFIED` path.** Content that does not map to a known type is classified `UNCLASSIFIED_DATA_ASSERTION`, `actionable: false`, routed to human review, never trusted or actionable by default (HEIMDALL.md Nornir). This is the coverage-fail-safe and it must exist from the first day. It matters more for web and social content than for email, because those are higher-volume and less structured, so early coverage will be lower and the fail-safe will carry more traffic.
- **The control-surface binding machinery.** Global defaults and the agent-definition schema (HEIMDALL.md agent definitions), so the per-agent binding exists even though Phase 1 grants no consequential capability. The action-critical set stays empty, as Phase 1 specifies; the machinery to declare and gate it is present and dormant.

### 4.2 The attach test, for a second medium and a second domain

The Phase 1 ontology is correct only if two kinds of extension attach cleanly. A second **medium** (web, social media, documents) must attach by adding a Bifröst parser and taint class that feed the existing communications types, without adding new types for the new medium. A second **subject-matter domain** (scheduling, finance) must attach by adding a domain-type layer under the shared upper ontology, without editing the communications types and without touching the shared spine. If either extension forces a change to what is already there, the layering is wrong and the seed must be refactored before Phase 4. Building the seed with both attach tests in mind is cheaper than discovering the coupling later. The medium attach test is the one most easily forgotten, because email arrives first and it is tempting to bake email structure into the communications types.

---

## 5. The marshalling contract

Marshalling is the seam between Fenrir's output and Yggdrasil's types: how grammar-constrained extraction becomes typed assertions that slot into the ontology. The architecture largely resolves this (HEIMDALL.md open question 6); this section states the contract.

- **The grammar is derived from the ontology.** Fenrir's grammar-constrained decoding is constrained by the domain types it is extracting into, so the model can only emit shapes that correspond to known ontology nodes. There is no free-text intermediate that a second pass must interpret.
- **Interpretive tasks that resist grammar constraint** become a single opaque `INTERPRETIVE_SUMMARY` assertion. They are never decomposed by a second LLM pass, because a second model reading the first model's output would reopen the injection surface one layer over. Whether some interpretive tasks warrant a constrained decomposition grammar is left open (see 10).
- **Every marshalled assertion is TAINTED by origin.** Fenrir reads untrusted content, so everything it emits is untrusted-derived, regardless of how cleanly it typed. Provenance is set at marshalling and is immutable thereafter.
- **Marshalling is where the PoC's `neural.py` meets Nornir.** The PoC assembled a fixed schema envelope in Python; the live system assembles a typed assertion whose type is an ontology node and whose grammar was derived from that node. The discipline is the same: the model fills values, the structure is not the model's to emit.

---

## 6. Authoring the rules

Nornir's rules are deterministic and human-authored. No model authors them and no model runs them. There are four kinds:

- **Classification rules** map a marshalled assertion to its ontology type. An assertion that matches no rule is `UNCLASSIFIED`, not guessed.
- **Derivation rules** are the forward-chaining inferences Nornir runs after each assertion batch. Every derived fact is marked `inferred: true` and carries the assertion chain that produced it, so any derived fact is traceable to its premises.
- **Constraint axioms** state what must not hold. A violation triggers Gjallarhorn immediately.
- **Flow-to-sink propagation** is the rule that assigns action-critical status transitively (section 8). It is authored once, over the shared structure, not per domain.

Rules are versioned, reviewed and tested like code. A change to a classification or constraint rule is a change to the trust boundary and is treated with the same seriousness as a change to Bifröst.

---

## 7. How coverage grows

Coverage growth is hand-authored now, and Odin-proposed later, with a hard provenance discipline on the automated path.

### 7.1 Phase 1 to 2: hand-authored, human-curated

Humans author the domain types, the classification rules and the constraint axioms. Content that does not classify accumulates as `UNCLASSIFIED_DATA_ASSERTION` in the review queue. A human periodically inspects the queue and extends coverage: new types, new rules, ratified deliberately. This is slow and sound, and it is the only mode in early phases.

### 7.2 Later phase: Odin-proposed, human-approved, provenance-gated

The roster agent Odin observes repeated `UNCLASSIFIED` patterns (via Huginn and Muninn) and proposes new ontology types and rules. This is how coverage scales, and it is also the most dangerous path in the whole design, because Odin's proposals derive from tainted content, and the ontology is the classifier, which is the trust boundary. An unguarded proposal path would let tainted content influence the classifier, reintroducing the injectable-classifier problem one level up.

The provenance gate on the proposal path is therefore mandatory and non-negotiable:

- An Odin proposal is itself untrusted until a human ratifies it. It carries the provenance of the tainted content it was derived from.
- A proposed type or rule can never auto-apply. It sits as a proposal, outside the live ontology, until explicit human approval promotes it.
- Approval is a promotion event, logged to Hliðskjálf, subject to the same trust-lattice discipline as any other promotion.
- Odin cannot approve its own proposals, and (per HEIMDALL.md open question 3) cannot propose changes to its own definition.

The rule in one line: Odin may propose coverage, a human ratifies it, and nothing tainted-derived ever becomes classifier logic without that ratification.

---

## 8. Testing the ontology

Building the ontology and testing it are the same activity. Coverage cannot be claimed without being measured, and correctness cannot be assumed. These are the acceptance obligations named in invariant 3.11, stated here as methodology. All are Phase 2 or later, because the ontology does not exist before then.

### 8.1 Coverage measurement

Against a representative corpus, measure the fraction of assertions that classify to a known type versus `UNCLASSIFIED`. Coverage is a tracked, reported number, not a pass or fail. The only hard invariant is that uncovered content fails safe: to review, never to a trusted or actionable type. The guarantee the filter offers is always reported alongside its coverage figure, never stated unqualified.

### 8.2 Classification correctness

A labelled corpus maps each assertion to its expected type, including adversarial cases engineered to force misclassification. The critical class is any case that tries to get an action-critical value typed as an inert label, so it skips Gjöll. This corpus needs ground-truth labels, which the injection corpus does not have, so it is a new corpus. A misclassification that downgrades an action-critical value is a critical finding, not a quality metric.

### 8.3 Reasoner soundness

For a set of asserted facts, every derived fact must be entailed by the ontology's rules. A derived fact that does not follow, above all one that confers trust or in-scope status, fails the suite. Because every derived fact carries its assertion chain, a soundness failure is traceable to the rule and premises that produced it.

### 8.4 Flow-to-sink reachability, agent-scoped and cross-domain

Any value that can reach a consequential sink by any path, however many reversible hops intervene, must inherit action-critical status at the moment it is written. Two properties make this test harder than a single-graph check:

- **Agent-scoped.** Reachability is computed against a given agent's permitted action space (control surface), not a domain-global sink set. A test fixture therefore carries an agent context (permitted actions and trust ceiling), not just a value and a graph. The same value may be action-critical for one agent and inert for another, and both must be asserted.
- **Cross-domain.** A value extracted in one domain can flow to a sink in another; the reachability graph is global across domains even though types are per-domain. The mandatory cross-domain case: a value marshalled in the communications domain that flows to a consequential sink reachable only through another domain must still be caught.

The mandatory adversarial case is state staging (HEIMDALL.md action-critical set sizing): a chain of individually-reversible, individually-non-consequential writes that composes into a consequential action must be caught at the staging write, not missed. The test must include a staging chain that crosses a domain boundary, exercising both properties at once.

---

## 9. Mapping to build phases

- **Phase 1 (prove the separation).** The seed ontology of section 4: the shared spine, the communications domain, the `UNCLASSIFIED` fail-safe path and the dormant control-surface binding machinery. Action-critical set empty.
- **Phase 2 (world model, reasoner, Fenrir).** The substrate spike and decision (section 3), Nornir operating over the seed ontology, the marshalling contract (section 5) wired to Fenrir, hand-authored coverage growth (section 7.1), and the first three test obligations (8.1 to 8.3). The coverage bound in invariant 3.9 becomes measurable for the first time here.
- **Phase 3 (control surface, Gjöll).** Flow-to-sink action-critical propagation (section 8.4), tested agent-scoped and cross-domain against a real state-staging attempt.
- **Later phase (introspection and roster).** The Odin-proposed coverage-growth path with its provenance gate (section 7.2).
- **Phase 4 (ingestion expansion).** The attach test (4.2) is exercised for real as a second domain and further media arrive, and the domain-governance decision (section 10) is forced and must be taken.

---

## 10. Deferred decisions and carried-forward open questions

Stated so they are not mistaken for settled.

### 10.1 Domain ontology governance (settled: single-curated, with a cross-domain priority principle)

**Governance model: single-curated now, federated deferred to a second owning team** (decision D31). One owning author holds one repository of truth with namespaced domain modules (`comms:`, `sched:`), all extending the shared BFO spine, composed by one loader. This is coherent and collision-free, and it matches the current reality: one author, one repository. Federated ownership, where each domain has a separate owner and a conformance harness catches collisions and drift, is more machinery than a single team needs. The trigger for federated is not merely a second domain (two now exist) but a second owning **team**. Until then, single-curated stands.

**Cross-domain classification priority principle.** A second domain surfaced a concrete question single-curated governance must answer (D51): when two domains share vocabulary and more than one classification rule matches, which wins? Priority by registration order was an accident. The principle, in order:

1. **Risk tier.** The highest-risk matching type wins. A value is never masked down to a lower-risk or inert type. This is the load-bearing safety property: a high-risk value always beats an inert one, so nothing is laundered by a broad rule matching first.
2. **Specificity.** Within the top risk tier, a rule matching a narrower, stronger signal beats a broad one. A scheduling signal (`cron`, `scheduled to`, `run at 2am`) is more specific than a bare action verb, so a genuine scheduled task types as `sched:scheduled_task` rather than being masked as a communications instruction.
3. **Tie to human review.** If two rules sit in the top tier with equal specificity and name different types, that is a genuine tie. Nornir does not silently pick one; it routes the assertion to `HIGH_RISK_UNRESOLVED`, a distinct high-risk fail-safe that stays gated (action-critical if it can reach a sink) and goes to a human. Never guess on a true tie.

This replaces registration order, which is no longer load-bearing. It is realised in `ontology/nornir/rules.py` (the `classify_assertion` function and `RiskTier`), the per-domain rule modules (which declare `risk_tier` and `specificity`), and `ontology/yggdrasil/unclassified.py` (the `HIGH_RISK_UNRESOLVED` tie outcome). The test corpus exercises both the resolved masking case and a genuine tie.

### 10.2 Carried-forward open questions

These are open in HEIMDALL.md and bear on this methodology. They are named here and cross-referenced, not re-opened.

- **Edge-deletion label retraction** in the flow-to-sink reachability graph (HEIMDALL.md open question 1). The known hard case for incremental backward-propagated action-critical labels, and a pass criterion for the substrate spike (3.3).
- **Constrained decomposition grammar for interpretive tasks** (HEIMDALL.md open question 6 residual). Whether some interpretive Fenrir tasks warrant a decomposition grammar, or all remain single opaque `INTERPRETIVE_SUMMARY` assertions (section 5).
- **Huginn's discriminating features** for telling honest small-model extraction errors from injection-induced ones (HEIMDALL.md open question 7). Bears directly on the classification-correctness corpus (8.2): a forced-misclassification attack and an honest extraction error can look alike, and the test corpus needs labelled examples of both to be meaningful.
