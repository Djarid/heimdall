# Scoping: attesting the sink and flow declarations (the root seam, 5.1)

**Author:** scoping pass for STATUS section 0 task 2
**Status:** A and B built (D89); D built for observable sinks (D93). C is the one direction not yet built.
**Reads with:** `ADVERSARIAL_REVIEW.md` 5.1, `DECISIONS.md` D78, D81, `ontology/nornir/sink_declaration.py`, `ontology/nornir/gjoll.py`

This note scopes the open root seam so the fix direction can be chosen from an
informed position. It takes no decision. It states the seam precisely against
the real code, then lays out the honest directions with their costs and what
each does and does not close.

---

## 1. The seam, stated precisely

Gjoll's action-time gate (`ontology/nornir/gjoll.py`) blocks a consequential
action only when a conjunction holds: the sink is consequential for this agent
AND the proposal consumes, as an ACTION, a parameter that is an untrusted-derived
action-critical value. Two of the conjunction's terms are trusted DECLARATIONS,
not derived facts:

1. **Sink consequentiality.** `effective_consequential(sink, registry,
   agent_consequential_sinks)` decides whether the sink can cause a real-world
   effect. It rests on `SinkDeclaration.consequential_by_default` and the agent's
   `consequential_sinks` set.
2. **Per-parameter consume mode.** `proposal.consumes[param] in {CONSUME_ACTION,
   CONSUME_INERT}` decides whether the sink ACTS on a given parameter. Only a
   parameter consumed as `CONSUME_ACTION` is gated.

D81 (`sink_declaration.py`) closed the class where an ERROR or DRIFT in these
declarations silently disabled the gate: an undeclared sink now fails closed
(treated as consequential), an invalid mode is a validation error not a silent
inert, a phantom parameter is caught, and an omitted declared parameter is
caught. Six obligations, green.

**What D81 does NOT close, and this note is about.** Validation proves a
declaration is well-FORMED, not HONEST. Two dishonest-but-well-formed declarations
still defeat the gate with no error:

- **Dishonest sink flag.** An author declares a genuinely consequential sink with
  `consequential_by_default=False` (and it is not in the agent's consequential
  set). `effective_consequential` returns False, the conjunction is False, the
  action is authorised. The sink then acts.
- **Dishonest consume mode.** An author declares a parameter the sink actually
  acts on as `CONSUME_INERT`. The gate's loop skips every non-`CONSUME_ACTION`
  parameter, so the action-critical untrusted value is never checked, and the
  action is authorised.

Either one is a single well-formed line that passes `validate_proposal` and
turns the gate off for that path. This is 5.1's "a sink that declares it consumes
an action-critical value as inert, but actually acts on it, passes the gate", and
it is the single most load-bearing unverified assumption in the design. The flow
graph's EDGES are the same shape of trusted declaration (a missing edge is a
silent hole), so this note treats sink declarations and flow edges together as
one seam.

**Threat model, stated honestly.** The adversary here is NOT untrusted external
content (that is the whole rest of the design). It is the authoring and
configuration path (5.8): whoever writes or can modify a sink declaration, a
flow edge, the ontology or the agent's sink set. This is a real adversary
(a malicious or coerced insider, a compromised config pipeline, a supply-chain
edit to the ontology, or simply an honest author's mistake that behaves
identically to malice) but it is a DIFFERENT adversary from the content attacker,
and any fix should say which one it addresses.

---

## 2. The honest fix directions

Four directions, roughly increasing in strength and cost. They are not mutually
exclusive; the strongest posture combines B and D.

### A. Fail-closed on the consume mode (cheap, partial)

Invert the per-parameter default. Today an absent or non-`CONSUME_ACTION` mode is
treated as inert (not gated). Instead, treat any parameter carrying an
untrusted-derived action-critical value as gated UNLESS the declaration positively
and verifiably earns inert. This is the D54/D55 fail-closed discipline applied to
the consume mode: inert must be earned, not defaulted.

- **Closes:** the dishonest/omitted `CONSUME_INERT` on an action parameter, when
  the value is already known action-critical by flow reachability.
- **Does not close:** the dishonest sink FLAG (if the sink is declared
  non-consequential the conjunction never reaches the parameter loop). And it
  cannot distinguish an honestly-inert parameter from a dishonestly-inert one; it
  can only make the safe direction the default and push the rest to review.
- **Cost:** review friction. Every action-critical value at a sink that declares
  it inert now routes to review instead of authorising. Needs the D53-style
  friction measurement before adopting.
- **Load-bearing check:** must not become a blacklist; it is a fail-closed
  default, exactly the sanctioned shape (invariant 3.5, D54).

### B. Derive consequentiality from flow, do not trust the flag (strong, structural)

Stop trusting `consequential_by_default`. Derive whether a sink is consequential
from the graph: a sink is consequential if it is reachable as a terminal
effect-producing node, i.e. its OUTPUT crosses a real-world boundary (money,
credential, code/config, data destruction, external send). The action-critical
machinery already computes reachability TO a sink; this extends the same
structural reasoning to classify the sink itself, rather than reading a boolean an
author set.

- **Closes:** the dishonest sink flag, structurally. An author cannot mark a
  money-moving sink non-consequential if consequentiality is derived from what the
  sink does, not from what the author claims.
- **Does not close:** it moves the trust, it does not eliminate it. The derivation
  needs a ground truth about which primitive operations are effect-producing (a
  sink taxonomy). That taxonomy is itself authored input, so the trust relocates
  from a per-sink boolean to a smaller, more stable, more auditable base set of
  effect primitives. That is a real gain (one small attested table versus a flag
  on every sink) but it is not zero-trust.
- **Cost:** the largest design change. Needs a declared effect-primitive taxonomy
  and a derivation pass, and it reshapes how `effective_consequential` is computed.
  Aligns with `plans/dd/gjoll.md` naming this as the Phase-3 gap to close first.

### C. Attest the declaration (strong on integrity, needs infrastructure)

Sign declarations and refuse an unsigned or unverified one at load time. A
declaration becomes a fact with provenance: who declared it, verified against a
key or an attestation the runtime trusts. Extends the D68/D71 posture (integrity
on the authorisation path) from imports to configuration.

- **Closes:** the CONFIGURATION-tampering and supply-chain variants (a declaration
  changed by someone not authorised to change it is rejected). This is the
  literal reading of "attest the declarations".
- **Does not close:** an authorised-but-dishonest author. If the person who may
  legitimately sign declarations declares a consequential sink non-consequential,
  a signature attests that THEY said it, not that it is TRUE. Attestation binds
  identity and integrity, not honesty. So C is necessary for the config-tamper
  adversary and useless against the malicious-authoriser adversary; it pairs with
  B, which addresses honesty structurally.
- **Cost:** key management, a signing step in the authoring pipeline, a verified
  set at load. New infrastructure and a new operational burden. Mirrors the
  verified-tokenizer-set idea (5.7).

### D. Behaviour-derivation / runtime cross-check (strongest evidence, heaviest): BUILT for observable sinks (D93)

Verify a declaration against the sink's ACTUAL behaviour: instrument the sink so
that if a parameter declared `CONSUME_INERT` in fact influences an effect, that
divergence is detected (at test time against a sink test-harness, or at runtime
via a taint check on the sink's own outputs). This is the only direction that
attacks "the declaration diverges from behaviour" head-on rather than relocating
trust.

- **Closes:** the dishonest consume mode against real behaviour, with evidence
  rather than assertion. Finding 2 in `ADVERSARIAL_REVIEW.md` section 8 (a
  demonstrated declaration/behaviour divergence) is exactly what this would catch.
- **Does not close:** it needs the sink to be observable/instrumentable, which is
  not always possible for an opaque external tool. Where the sink is a black box,
  D degrades to B plus C.
- **Cost:** the heaviest. Per-sink instrumentation or a behavioural test harness,
  and a taint-tracking discipline on sink outputs. Probably a later phase.

**Built (D93), test-harness form.** The test-time form of D is now built:
`ontology/nornir/effect_probe.py` (`EffectObservation`, `verify_declaration`) cross-checks
the effect primitive a behavioural probe OBSERVED a sink producing against the declared
primitive; a divergence (observed effect-producing, declared inert) is caught and the sink
treated as consequential by its observed behaviour, and the verdict enters the gate through
`evaluate`/`enforce`'s new `effect_observations` parameter as a fail-closed OR into
consequentiality (so it composes with B, neither can disarm the other). `ontology/tests/
effect_probe_harness.py` plants the display_only-but-moves-money lie and proves it is caught
and blocked end to end, with the mandatory controls (honest declarations verify clean; an
opaque sink fails closed). No model on the path (set membership and equality over the attested
table, invariant 3.1); fail-closed, not a blacklist (inert earned only by a positive clean
observation). This DISCHARGES the wrong-primitive trust for every OBSERVABLE sink. What stays
unbuilt: the RUNTIME taint form (a live taint check on sink outputs, for a sink whose behaviour
must be watched in production rather than in a test harness), and the OPAQUE sink that cannot
be instrumented at all, where D degrades to B plus C. See D93.

---

## 3. Recommendation for the decision (not taken here)

The honest reading is that "attest the declarations" (the STATUS wording) is
really TWO problems wearing one name, and they need different tools:

- **Integrity of the declaration** (was it changed by someone allowed to change
  it?) is direction C, attestation proper.
- **Honesty of the declaration** (is what it claims TRUE of the sink?) is
  direction B (derive, do not trust) or D (verify against behaviour).

C alone would be the literal task but would leave the malicious-authoriser
adversary open, so it should not be done alone. The highest structural value for
the least new infrastructure is **B**: derive sink consequentiality from a small
attested effect-primitive taxonomy instead of a per-sink boolean, because it turns
the dishonest-flag attack from a one-line config edit into an attack on a small,
auditable, rarely-changing base table. **A** is a cheap complementary default
worth measuring for friction. **C** and **D** are follow-on phases (C when a
config-integrity pipeline exists, D when sinks are instrumentable).

**Update (D89, D93).** B and A were built (D89). D was then built in its test-harness form
(D93): where a sink is instrumentable, its declared primitive is now verified against observed
behaviour, which DISCHARGES the wrong-primitive trust B could only relocate, rather than
deferring it to a later phase. So the recommendation's ordering held, and only C remains
unbuilt (plus the opaque-sink and runtime-taint residuals of D).

A first buildable step that stays inside the repo's current depth and does not
need new infrastructure: implement **B** as a demonstration over the seed sinks
(a declared effect-primitive set, a derivation of `effective_consequential` from
it, and a harness obligation showing a sink dishonestly flagged non-consequential
is still gated because its effect primitive is money-movement), plus **A** as the
fail-closed consume-mode default with a friction measurement. That closes the
dishonest-flag and dishonest-mode variants structurally on the seed, leaves C and
D named as phased follow-ons, and keeps the honest limit explicit: the trust is
relocated to a small attested base, not removed.

---

## 4. What a decision here must preserve

- **Invariant 3.1.** No model on the derivation or gate path. B's derivation is
  deterministic graph reasoning over an authored taxonomy, not a model call.
- **D24 agent scoping.** A sink legitimately non-consequential FOR AN AGENT must
  stay ungated with no friction; only DISHONEST non-consequentiality is the
  target. B must derive the sink's intrinsic consequentiality and still apply
  agent scoping on top, exactly as `effective_consequential` layers the two today.
- **Fail closed, never a blacklist (invariant 3.5, D54/D55).** A's inert-earning
  default must be a positive-signal allowlist shape, not an enumeration of
  dangerous sinks.
- **The honest-limit discipline.** Whatever is built, the residual trust (the
  effect-primitive taxonomy for B, the signing authority for C, the
  instrumentability assumption for D) must be stated as the new bound, not
  presented as closure.
