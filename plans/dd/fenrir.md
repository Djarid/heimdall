# Detailed Design: Fenrir (sandbox reading agent)

**Author:** Jason Huxley
**Date:** August 2026
**Version:** 0.1 (draft)
**Phase:** 2
**Status of the component today:** the detection layer is now BUILT under the scoped R-1 exception (D74), at `phase2/` (canary wrap, `extract`, the six hard canary signals and the attempt-introspection tripwire), with a green deterministic logic suite and an optional real-model demonstration. The proof-of-concept neural layer (`poc/neural.py`) proves the tool-less, egress-free, fresh-context extraction shape. STRUCTURAL slot extraction is now also built (D86, `phase2/slot_extraction.py`): a fixed authored `SlotExtractionSchema` the model fills with bounded values only, a deterministic `bind_slots` that maps them to typed `ProposedFact`s, and a `marshal_fenrir_run` bridge into `MarshalledAssertion.proposed_facts`, proven end to end against the live Nornir engine (phase2 harness obligation 6) so the wired state-delta layer (D79) catches consequence on content the classifier types inert. It was first demonstrated against a deterministic mock and then against a REAL model via a bounded per-field generation stand-in (D87): a `MlxSlotProducer` reused the PoC's proven bounded generation to fill the schema values, and on Qwen2.5-7B it bound `salary_destination` from an inertly-phrased payroll redirect the classifier still typed inert. True token-level grammar-constrained decoding into the schema is now also BUILT (D90, `phase2/grammar_slot_extraction.py` + `phase2/grammar_slot_demo.py`): the model emits the whole schema object under a logits mask that permits only grammar-valid tokens, proven deterministically without a model and demonstrated on Qwen2.5-7B; D87's now-superseded stand-in files are retired (D98). Still unbuilt: the segmented-sandbox network deployment. Honest finding from the build (D75): the attempt-introspection catch does not close the false-inert gap for a robust model, because such a model is not steered by the payloads and so emits no action to catch; it is an injection-success detector, not a false-inert fix. See `phase2/OUTCOME.md`.

---

## 1. Purpose

Fenrir is the only agent permitted to read tainted content directly. Every other agent reasons over the typed world model that Himinbjörg constructs, never over a raw content window. Fenrir exists because some language tasks (extracting a sender, summarising a body, listing entities) genuinely need to read the untrusted text, and the architecture chooses to make that reading structurally safe rather than to forbid it.

The point Fenrir makes is that reading is not acting. A payload that reaches Fenrir can influence text; it cannot cause an action, because Fenrir has no surface on which an action can occur. This document takes Fenrir to implementation fidelity for Phase 2: the `extract()` interface under grammar-constrained decoding, the canary mechanism Himinbjörg wraps around every invocation, the attempt-introspection tripwire and the egress-restricted deployment that makes exfiltration a network-policy guarantee rather than a discipline.

## 2. Responsibilities and boundaries

In scope for Fenrir:

- Read a canary-wrapped tainted-content window and emit typed tainted assertions, or a single `INTERPRETIVE_SUMMARY` assertion where the task cannot be grammar-constrained.
- Run under grammar-constrained decoding, so output is valid within the assertion schema by construction and there is no free-text intermediate to re-parse.
- Emit every field as tainted and inert: no field Fenrir produces is wired to any sink or is actionable without downstream promotion.
- Present its full emission (the reasoning trace and the output) to Huginn for canary checking and attempt introspection.

Out of scope for Fenrir, and structurally absent rather than merely denied:

- Any tool, MCP server, shell or filesystem access. The capability set is empty, so injection can only influence text, never cause action. This is a structural property of the sandbox, held by the empty capability set itself rather than by a permission default that could be overridden.
- Any egress path off the trust boundary. Fenrir sits on an egress-restricted segment (section 4) and cannot reach an external endpoint even if fully injected.
- Any state carried between invocations. Each run meets a clean slate.
- The canary wrap and the monitoring. Constructing the signed canary pair is Himinbjörg's job; checking the output against it is Huginn's. Fenrir's own surface is deliberately just extraction, so nothing inside Fenrir can weaken the checks that judge it.
- Trust decisions. Fenrir output is always TAINTED; Fenrir never promotes.

The four structural properties, each closing a class of attack (from `HEIMDALL.md` 519 to 530 and HLD section 5.6):

| Property | Closes |
|---|---|
| Fresh context per invocation | Cross-invocation conditioning. No payload can condition Fenrir across runs; the attack surface collapses to what a single payload achieves in a single isolated pass. |
| Local egress-restricted model | Exfiltration. A fully injected Fenrir has no route out of the trust boundary to leak tainted content to. |
| Zero execution surface | Action. "Injection succeeded" can only ever mean "Fenrir's text was influenced", never "Fenrir did something". |
| Full mandatory introspection | Silent compromise. Every emission is observed by Huginn, including any attempt to act. |

The combination leaves one residual attack, value poisoning (section 5 and 9), which Fenrir does not close and which is contained by Gjöll, not here.

## 3. The core contracts

### 3.1 The extract interface

Fenrir's own surface is a single entry point. It receives a canary-wrapped context and returns typed tainted assertions under grammar-constrained decoding:

```
extract(canary_wrapped_content: CanaryContext) -> list[TaintedAssertion]
```

The `TaintedAssertion` is the cross-cutting type from `index.md` section 4.1. Fenrir populates it with `taint == TAINTED` always (there is no code path to a higher taint level in this component), the provenance carried through from the Bifröst-parsed content, and `payload`/`parsed_fields` holding the extracted values. Every field Fenrir emits is inert: it is not wired to any sink and is not actionable without human or cryptographic promotion downstream.

**Grammar-constrained decoding.** Because Fenrir runs a local model, decoding is constrained at the token level to emit directly into the typed assertion schema. The model can only produce tokens that are valid within the grammar, so there is no natural-language output to re-parse and therefore no second parsing pass to reintroduce an injection surface (`HEIMDALL.md` 657 to 659). The marshalling problem (turning free-text model output into typed assertions) largely dissolves, because the structure is not the model's to emit: the envelope is fixed by the grammar and the model fills bounded values. The proof-of-concept neural layer proves this shape by a simpler mechanism (a per-field bounded sub-generation with a newline hard-stop and the JSON envelope assembled in Python, `poc/neural.py` lines 121 to 163 and 316 to 328). D90 replaces that stand-in with true token-level grammar-constrained decoding into the schema: `phase2/grammar_slot_extraction.py` is a pure-Python `GrammarState` over the schema's JSON grammar, and `phase2/grammar_slot_demo.py` turns it into an mlx_lm logits mask so the model emits the whole object under the grammar, keeping the guarantee that the model cannot emit a field the pipeline treats as actionable and cannot emit malformed structure. It is native (no outlines/xgrammar dependency) and the grammar is proven deterministically without a model (`phase2/tests/harness.py` obligation 7). The honest residual is value poisoning: the grammar constrains structure and well-formedness, not value truth, so a schema-valid wrong value is contained by Gjöll at action time, not here (section 9, FR-6).

**The interpretive fallback.** A task that genuinely requires interpretive output that cannot be fully grammar-constrained (a summary, for instance) becomes a single `INTERPRETIVE_SUMMARY` tainted assertion. It is never decomposed into further typed assertions by a second LLM pass, and it is never actionable without human promotion (`HEIMDALL.md` 661). This keeps the no-second-parse guarantee intact for the one case grammar constraint cannot cover: the interpretive text is quarantined as one opaque tainted value, not re-fed to a model that could be injected by it.

### 3.2 The canary mechanism

Himinbjörg wraps every Fenrir context with a signed top and tail canary (`HEIMDALL.md` 532 to 556). The wrap carries the task, the output schema, a per-invocation canary token and a honeypot phrase. Fenrir reads the wrap as its only instruction source; the tainted content sits between the two canaries and cannot instruct it.

- **The canary token** is a per-invocation UUID generated by Himinbjörg from a cryptographically secure entropy source, never reused, and the model is instructed to include it verbatim in its output. A missing or malformed token means the canonical instruction was not followed.
- **The honeypot phrase** is a secret unknown to the tainted content, which the model is instructed never to include. Its presence in the output means the injection succeeded in steering the model, because only injected instruction could introduce a phrase the model was told to withhold.

Injection must defeat both tokens independently. The two are complementary: the token proves the canonical instruction was honoured, the honeypot proves no adversarial instruction was.

**Both tokens are set on the canonical control channel only.** This is load-bearing security, not a convenience (`HEIMDALL.md` 700 to 706, `index.md` section 4.4). The canary token must be generated per invocation from a secure entropy source, never reused, and never logged to any surface reachable from the ingestion pipeline. The honeypot phrase must come from an entropy source outside the ingestion surface and the Heimdall codebase, must not be derivable from any content Fenrir has ever received or any public documentation, is rotated on a schedule and is known only to Himinbjörg at runtime: never persisted in plaintext, never transmitted off the canonical channel, never logged in recoverable form. Any implementation path that derives, stores or transmits either token through a tainted-reachable surface voids the canary guarantee entirely. The DD treats this as an interface constraint on Himinbjörg's wrap construction (document 7) and on Hliðskjálf's logging (document 6): the audit log records that a canary check ran and its verdict, never the token or phrase values themselves.

Huginn checks the output against the wrap. The hard signals (each an immediate Gjallarhorn event, `HEIMDALL.md` 558 to 567):

| Hard signal | Meaning |
|---|---|
| Canary token absent or malformed | The canonical instruction was not followed. |
| Honeypot phrase present in output | Injection influenced the output. |
| Tool call attempted | Sandbox boundary violation (also an attempt-introspection hit, section 3.3). |
| Output schema violation | The model produced unsolicited content outside the grammar. |
| Tail canary instruction absent from output | The canonical instruction was overridden. |
| Output references Himinbjörg internals | Possible prompt-extraction attempt. |

The soft signals feed pattern analysis rather than an immediate halt (`HEIMDALL.md` 569 to 577): semantic drift from the declared task, output length outside the baseline, confidence-score outliers, latency outliers and repeated `UNCLASSIFIED` assertion types (an ontology gap surfacing through Fenrir runs). Soft signals are Huginn evidence for baselining and correlation; they do not by themselves discard a run.

### 3.3 Attempt introspection: the null-surface tripwire

Fenrir's empty capability set makes it evidential as well as preventive. Because it has no tools, MCP, shell or filesystem, it has no legitimate reason ever to emit an action-shaped token sequence. Its legitimate behaviour space contains no actions at all. Any action-shaped emission (a tool call in the model's native format, reasoning tokens describing intent to act, a malformed output that is structurally an invocation rather than the requested schema, or an attempt to invoke a named capability that does not exist) therefore has exactly one explanation: something in the context instructed it to act, and the only thing in the context that could is the tainted content (`HEIMDALL.md` 579 to 591).

This is dispositive proof of injection rather than a heuristic, and it has three properties the output canary does not:

- **Earlier than the canary.** It fires at the attempt, before any manipulated final output is produced. A payload that tries to make Fenrir act reveals itself even if the eventual text would have looked clean.
- **Less evadable than the canary.** The canary checks the final output; the tripwire checks the reasoning trace. An attacker would have to steer Fenrir without producing any action-shaped intermediate emission at all.
- **Zero false positives by construction.** Because the legitimate behaviour space contains no actions, an action-shaped emission is not merely suspicious; it is proof. The zero-false-positive property is a property of the empty capability set, so it holds only as long as the set stays empty, which is why any capability grant to Fenrir is a change to this contract, not a configuration tweak.

Attempt introspection is a hard signal. Any action-shaped emission triggers immediate Gjallarhorn, halts the Fenrir instance, discards its output and quarantines the source content for human review. Combined with the output canary and the zero-execution surface, Fenrir has three independent detection layers: preventive (no surface, so the attempt cannot succeed), attempt introspection (the act of trying is caught at emission, independent of output) and the output canary (manipulated final output is caught by the token, honeypot and schema checks).

## 4. The egress-restricted deployment

The taint boundary and the network-egress boundary coincide (HLD section 10, Design Principle 13). Tainted content is processed only by a component that has no egress path out of the trust boundary, and Fenrir is that component. This is egress control, not air-gapping: Fenrir has the internal connectivity it needs and nothing more.

The reference agent definition (`HEIMDALL.md` 618 to 655) fixes the segment policy:

- `egress_policy: default-deny`. Nothing leaves the segment unless a peer is on the allowlist.
- `permitted_peers: [bifrost, mimisbrunnr]`. The internal allowlist is exactly the two peers Fenrir needs: Bifröst hands it parsed tainted content, and it writes typed tainted assertions toward Mímisbrunnr. No other internal peer, and no external endpoint.
- `external_egress: none`. There is no route to any internet or external endpoint from the segment.

This makes exfiltration a network-policy guarantee rather than a discipline. A compromised Fenrir cannot phone home, because its segment denies egress to anything outside its permitted peers. The rule "never send tainted content to an external API" is enforced by segmentation, because the component holding tainted content has no route to an external API in the first place. The consequence for the model inventory is a hard partition: local egress-restricted models process tainted content (Fenrir), networked API models reason only over untainted typed state (normal agents) and are reachable only from the untainted side, and no model occupies both roles.

**The local dense model (reference, not requirement).** Fenrir's guarantees derive from its structural properties, not from any specific model (`HEIMDALL.md` 714 to 721, HLD section 9). The reference deployment is a DGX-Spark-class local machine (unified memory around 128GB) running a dense 30B to 80B model on the egress-restricted segment, paired with a same-family small draft model (an 80B target with a 7B draft, for example) for speculative decoding. Dense is preferred over sparse MoE as a security property: MoE routing is an input-dependent variance surface, undesirable in a component whose job is resisting adversarial input, whereas a dense model behaves more uniformly and is more analysable under adversarial conditions. Grammar-constrained decoding and low-entropy extraction workloads both raise speculative-draft acceptance, and because every token is target-verified the draft cannot introduce a poisoned value the target would not have produced, so it does not widen the attack surface.

## 5. Fail-closed behaviour

- Any hard canary signal (token absent or malformed, honeypot present, tool call attempted, schema violation, tail canary absent, internals referenced) halts the Fenrir instance, discards its output and quarantines the source, independent of alert delivery.
- Any attempt-introspection hit (any action-shaped emission) does the same, and does it earlier, at the attempt.
- Containment is decoupled from alerting (HLD section 5.5). The halt-and-discard is automatic and per instance; it does not wait for a human to read a Gjallarhorn alert. Burying an alert in volume does not help an attacker, because the poisoned run is already contained before the alert is triaged. A spike in canary or attempt-introspection events is itself a single high-priority signal that triggers source quarantine.
- A low-confidence extraction is treated as `UNCLASSIFIED` and routed to human review rather than trusted (`HEIMDALL.md` 611 to 614), consistent with the fail-closed default in `index.md` section 4.2.
- Fenrir never emits anything other than TAINTED. There is no code path to a higher taint level in this component, so a clean run still produces only tainted assertions that require downstream promotion before any action.

**What fail-closed does not cover.** A schema-valid, canary-valid, honeypot-clean output whose field values are corrupted passes every check above, because every check is structural and the corruption is semantic. That residual is value poisoning, named in section 9 and contained by Gjöll, not by any fail-closed branch here.

## 6. Data owned

None persistent. Fenrir holds no state between invocations: fresh context every run, no carryover, no conditioning across runs (`poc/neural.py` line 25, `HEIMDALL.md` 645 to 646). The canary token and honeypot phrase are Himinbjörg's, held only for the duration of the wrap and never persisted by Fenrir. The output assertions are handed downstream and not retained. This absence of owned state is what makes the fresh-context property real rather than aspirational: there is no store for a payload to condition.

## 7. Dependencies

- Upstream: Himinbjörg constructs and signs the canary wrap and hands Fenrir the wrapped context; Bifröst-parsed tainted content fills the content window. Fenrir does not parse raw content itself; it reads what Bifröst has already turned into tainted assertions.
- Downstream: Mímisbrunnr only, and only via Nornir classification. Fenrir returns typed tainted assertions that Nornir classifies and Mímisbrunnr stores as TAINTED. Fenrir never returns anything to the control channel directly (`HEIMDALL.md` 652, `index.md` section 4.4). A document that specified any Fenrir path to the control channel would be a defect.
- Lateral: Huginn monitors Fenrir throughout, running the attempt-introspection checks during emission and the canary checks on output, then raising Gjallarhorn hard signals. Gjallarhorn routes the alert and triggers source quarantine; the per-instance halt-and-discard runs regardless.
- Scaling: multiple Fenrir instances run in parallel over different content streams, independently monitored, sharing no state and coordinating only through Mímisbrunnr via Himinbjörg (`HEIMDALL.md` 710 to 712). Instances cannot communicate with each other or with normal agents directly.

## 8. Build delta from today

- `poc/neural.py` proves the tool-less, egress-free, fresh-context shape (HLD section 3, invariant 3.8). The proof-of-concept is a first-class demonstration of three of the four structural properties: it has no tools, no function calling and no execution surface (line 24); it carries no history between cases (line 25); and it receives only the typed record, never raw input, so it has no egress role. It also proves the out-of-band instruction/data separation the boundary rests on: the trusted instruction is a fixed constant in a system message, the untrusted payload sits alone in a user message, the prompt is assembled as token ids, and encode-time control-marker neutralisation (`split_special_tokens=True`, line 254) forces any `<|im_start|>`-shaped string in the payload to ordinary text so no payload byte becomes a control token. Every extraction field is stamped `UNTRUSTED_DERIVED` and `action_capable: False` (lines 67 to 84), which is the inert-output property in running code.
- What the proof-of-concept does not prove, and what Phase 2 must build:
  - No segmented sandbox deployment. The egress-restricted network segment, the default-deny egress policy and the `[bifrost, mimisbrunnr]` internal allowlist are all unbuilt.
  - No egress-policy test. The network-policy guarantee (a compromised Fenrir has no route off the segment) is asserted in the design but not yet enforced or tested.
  - No canary wrapping. Himinbjörg does not exist yet (Phase 3), so the signed top/tail canary, the per-invocation token and the honeypot phrase are specified but not constructed. Phase 2 builds Fenrir to consume a canary wrap; the wrap's construction and the token secrecy enforcement land with Himinbjörg.
  - No attempt-introspection tripwire. The null-surface detection over the reasoning trace is unbuilt; it depends on Huginn (Phase 2 canary monitoring) observing the emission.
  - The proof-of-concept constraint mechanism (per-field bounded sub-generation with a newline hard-stop) is a stand-in for true grammar-constrained decoding into the assertion schema, which Phase 2 builds.
- Fenrir's guarantees are a Phase-2 obligation, and no Phase-3 consequential capability arms against them until the D67-fix arming gate closes (HLD R-1); until then Fenrir output stays tainted and non-actionable by default, which is the fail-closed posture that makes the gap safe.

## 9. Test plan

Inherits the proof-of-concept neural suite (`poc/`): the extraction runs with no tools and no execution surface, fresh context per case, over an adversarial corpus, at decoding temperatures 0.0 and 0.7. This is the proven baseline for the tool-less, egress-free, fresh-context shape (invariant 3.8).

Adds, before implementation:

- No action-shaped emission crosses: for an adversarial corpus of tainted-content windows carrying injection payloads (imperative instructions, tool-call syntax in the model's native format, capability-invocation attempts), assert that no run produces an action, that every output is either a typed tainted assertion or a halt, and that no emission reaches the control channel. This tests the zero-execution-surface guarantee by its failure mode.
- Canary-violation detection: for each hard signal (token absent, token malformed, honeypot present, tool call attempted, schema violation, tail canary absent, internals referenced), plant an output that exhibits it and assert Huginn raises the correct hard signal, the instance halts, the output is discarded and the source is quarantined. Assert a clean output raises no hard signal.
- Attempt-introspection dispositive signal: plant a payload that induces an action-shaped intermediate emission whose eventual text output would have looked clean, and assert the tripwire fires at the attempt, before the final output, and that it fires independently of the output canary. Assert the zero-false-positive property: a legitimate extraction over a benign corpus produces no attempt-introspection hit across the whole corpus.
- Canary-token secrecy: assert the canary token and honeypot phrase never appear in any ingestion-reachable surface. Grep the Hliðskjálf audit entries produced by a Fenrir run and assert the token and phrase values are absent (the log records that a canary check ran and its verdict, not the values). Assert neither value is derivable from Fenrir input, Fenrir output or any logged artefact.
- Egress-denial network test: from the Fenrir segment, assert a connection to any peer outside the `[bifrost, mimisbrunnr]` allowlist and any external endpoint is refused by the default-deny egress policy, and that connections to the two permitted peers succeed. This tests the network-policy guarantee directly rather than trusting a discipline.
- Fresh-context isolation: run a payload designed to condition a later run, then run a clean case, and assert the clean case is unaffected, confirming no state carries between invocations.

Coverage is reported line and branch; the fail-closed branches (every hard-signal halt, the attempt-introspection halt, the egress denial) are covered explicitly, since they are the point of a sandbox component. A green count over low branch coverage on these paths is not evidence, because the failure paths are the guarantee.

**The value-poisoning residual, named as not closed here.** No test in this plan asserts that Fenrir prevents value poisoning, because Fenrir does not. A payload that produces a schema-compliant, canary-valid, honeypot-clean output whose field values are corrupted passes every check above; grammar-constrained decoding guarantees shape, not value truth, and the taint label answers origin, not safety (`HEIMDALL.md` 599 to 616, HLD section 8.5). If a poisoned action-critical value reaches the world model, a fully legitimate authorised agent will act on it, because the attack corrupts the premises the control channel reasons from rather than crossing the control channel. This residual is contained by Gjöll at action time (moving the decision to a human or a key for action-critical values, HLD section 5.2 and document 8), not by Fenrir. The extraction-layer mitigations Fenrir does carry (preferring structural extraction checkable against source over interpretation, and treating low-confidence extractions as `UNCLASSIFIED`) are necessary but not sufficient, and are tested as such above without any claim that they close the attack. Named here so the boundary of Fenrir's guarantee is explicit and is not overstated.

## 10. Decisions (index)

| # | Decision | Chosen | Rejected | Rationale |
|---|---|---|---|---|
| FR-1 | The reading posture | Make reading structurally safe (zero execution surface, monitored) rather than prevent reading | Forbid direct reading of tainted content entirely | Some language tasks genuinely need to read the untrusted text. An empty capability set makes reading safe and also yields the attempt-introspection tripwire; a ban would push the task elsewhere without the guarantee. |
| FR-2 | Output form | Grammar-constrained decoding into the typed assertion schema, with a single `INTERPRETIVE_SUMMARY` fallback | Free-text output re-parsed into typed assertions by a second pass | A free-text intermediate reintroduces a second-parse injection surface. Emitting directly into the grammar removes it; the one uncoverable case is quarantined as one opaque tainted value, never re-decomposed by a second LLM. |
| FR-3 | Canary token and honeypot placement | Both on the canonical control channel only, never on any ingestion-reachable surface | Derive or cache either token near the ingestion path for convenience | The canary guarantee rests entirely on the unguessability of both tokens. Any path that stores or transmits either through a tainted-reachable surface voids it (`HEIMDALL.md` 706). This is an interface constraint on Himinbjörg's wrap and Hliðskjálf's logging, not a Fenrir preference. |
| FR-4 | Containment timing | Per-instance halt-and-discard on any hard signal, decoupled from alert delivery | Halt only after a human triages the Gjallarhorn alert | Coupling containment to alert delivery lets an attacker bury the alert in volume while the poisoned run completes. Automatic per-instance containment means the run is already contained before triage. |
| FR-5 | Model class | Local dense 30B to 80B on an egress-restricted segment, same-family draft for speculative decoding | Sparse MoE, or a networked API model | Dense behaves uniformly and is analysable under adversarial input; MoE routing is an input-dependent variance surface. A networked model would break the taint/egress coincidence. Reference deployment, not an architectural requirement. |
| FR-6 | Value poisoning ownership | Named as not closed by Fenrir; contained by Gjöll at action time | Claim the sandbox or grammar constraint closes it | Grammar constraint guarantees shape, not value truth; taint answers origin, not safety. Overstating Fenrir here would hide the primary open limitation of the reading path (HLD section 8.5). Honesty over reassurance. |

---

## Licence

Part of the Heimdall specification, licensed under CC-BY-SA-4.0. See `LICENSE.md`.
