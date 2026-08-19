"""Direction D: verify a sink's declared effect primitive against its ACTUAL behaviour.

The place this sits in the seam. `ADVERSARIAL_REVIEW.md` 5.1 is the root: sink and flow
declarations are trusted input and nothing attests them. D81 proved a declaration only
WELL-FORMED. D89 direction B then stopped trusting the per-sink `consequential_by_default`
boolean and DERIVED consequentiality from a declared `effect_primitive` over the small attested
`EFFECT_PRODUCING_PRIMITIVES` table, which defeats a dishonest FLAG. But B only RELOCATED the
trust, from a per-sink boolean to a per-sink primitive string: a sink that dishonestly declares
the WRONG primitive (a money mover declaring itself `display_only`) still slips the gate,
because the derivation reads the string it was handed and the string is a lie. That residual is
named in `plans/declaration_attestation_scoping.md` as the C/D follow-on and in
`ADVERSARIAL_REVIEW.md` section 8 finding 2 (a declaration/behaviour divergence).

What direction D does about it, and where it stops. D is the only direction that attacks "the
declaration diverges from behaviour" head-on rather than relocating the trust again. It does not
ask the author what the sink does; it OBSERVES what the sink does and compares that against the
declaration. Concretely: a sink is exercised under a controlled probe, an observer records which
effect primitive the sink actually produced (money moved, code run, data destroyed, or nothing
but a display/store), and this module cross-checks the OBSERVED primitive against the DECLARED
one. A divergence, a sink that declares `display_only` but is observed to move money, is a
verification failure and FAILS CLOSED: the sink is treated as consequential (its worst observed
effect), never as its dishonest declaration.

The honest limit, stated rather than smoothed. D needs the sink to be OBSERVABLE. Where the sink
is instrumentable (which every in-repo sink is, because the sinks here are the mock `Actuator`
and any real sink we own), D catches the wrong-primitive lie with EVIDENCE, not with an
assertion we relocated. Where the sink is an opaque external tool we cannot instrument, D has no
observation to check and degrades to B (derive from the declared primitive) plus C (attest who
may declare it). So D closes the wrong-primitive seam for observable sinks and names the opaque
sink as the residual, which is the honest scope: the trust is not relocated, it is DISCHARGED by
observation for every sink we can watch.

Why this is not a model, and not a blacklist (the two load-bearing rules). The cross-check is a
comparison of two symbols: the primitive the observer recorded and the primitive the author
declared. There is no model on this path (invariant 3.1): the observer counts effects a probe
actuator recorded, and the verdict is set equality/membership over the same attested table B
uses. And it is fail-closed, not a blacklist (invariant 3.5, D54/D55): a sink earns its declared
non-consequential status only by POSITIVELY being observed to produce no effect-producing
primitive; silence (an unobserved sink, or a probe that produced no observation) does not earn
inert, it fails closed to consequential, exactly as an omitted primitive does under B. We never
enumerate "dangerous" sinks; we require every inert claim to be earned by a clean observation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .sink_declaration import (
    EFFECT_PRODUCING_PRIMITIVES,
    INERT_PRIMITIVES,
    SinkDeclaration,
)


# The primitive we record when a probe observed a sink do nothing effect-producing at all: it
# only displayed or stored. This is the OBSERVED analogue of an honest inert declaration. It is
# NOT the same as "no observation": no observation fails closed (see below), a clean observation
# of display/store-only behaviour is a positive earning of inert.
OBSERVED_INERT = "observed_inert"


@dataclass
class EffectObservation:
    """What a probe run of a sink actually did.

    `sink` is the sink id under probe. `observed_primitives` is the set of effect primitives the
    probe's observer recorded the sink producing (drawn from the same taxonomy the declaration
    uses: `move_money`, `run_or_change_code`, etc., or `OBSERVED_INERT` for a display/store-only
    run). `observed` records whether the probe actually ran and produced an observation at all; a
    probe that could not run (an opaque, non-instrumentable sink) leaves this False, which is the
    signal to fail closed rather than to read an empty set as "no effect"."""

    sink: str
    observed_primitives: frozenset = field(default_factory=frozenset)
    observed: bool = False


@dataclass
class VerificationResult:
    """The outcome of cross-checking one declaration against one observation.

    `sink` names the sink. `agrees` is True only when the declaration is verified honest by the
    observation. `verified_consequential` is the fail-closed instruction for the gate: the sink's
    consequentiality AS OBSERVED, which overrides the declared primitive whenever they diverge.
    `reasons` records why a divergence was found, for the audit trail and review queue."""

    sink: str
    agrees: bool
    verified_consequential: bool
    reasons: list = field(default_factory=list)

    @property
    def divergence(self) -> bool:
        """A declaration/behaviour divergence was detected (the section 8 finding 2 catch)."""
        return not self.agrees


def _observation_is_effect_producing(observation: EffectObservation) -> bool:
    """Whether the observed behaviour includes ANY effect-producing primitive. Fails closed.

    - the probe did not run (opaque/uninstrumentable sink): TRUE. No observation never earns
      inert; an unwatched sink is treated as consequential, the same fail-closed rule an omitted
      declared primitive follows under B. This is what keeps D from reading "I saw nothing"
      as "it does nothing".
    - the probe ran and recorded at least one primitive in EFFECT_PRODUCING_PRIMITIVES: TRUE.
    - the probe ran and recorded only OBSERVED_INERT (or nothing effect-producing): FALSE. This
      is the ONLY way a sink is observed non-consequential: a positive clean observation.
    """
    if not observation.observed:
        return True  # no observation fails closed
    return any(p in EFFECT_PRODUCING_PRIMITIVES for p in observation.observed_primitives)


def verify_declaration(
    declaration: "SinkDeclaration | None",
    observation: EffectObservation,
) -> VerificationResult:
    """Cross-check a declared effect primitive against an observed one (direction D). Fail closed.

    The verdict is the OBSERVED consequentiality, and the declaration is honest only when it
    agrees with the observation:

      - no declaration at all: fail closed to consequential; agreement is judged against the
        observation alone (an undeclared sink cannot be honest, it can only be observed).
      - the observation is effect-producing (or absent) but the declaration claims an inert
        primitive: DIVERGENCE. The declaration is a lie (or unverifiable); the sink is treated
        as consequential by observation, and the gate must not trust the inert claim. This is
        the wrong-primitive seam, closed with evidence.
      - the observation is effect-producing and the declaration also declares an
        effect-producing primitive: agreement; consequential either way.
      - the observation is clean (display/store only) and the declaration claims inert:
        agreement; legitimately non-consequential, no friction.
      - the observation is clean but the declaration claims an effect-producing primitive:
        DIVERGENCE in the SAFE direction. We still fail closed to consequential (the declaration
        says it can produce an effect and a single clean probe does not prove it never will), but
        we flag the divergence so a reviewer can reconcile the over-declaration. Safety is
        preserved; only the audit trail is enriched.

    No model is on this path: the whole function is set membership and equality over the attested
    primitive taxonomy (invariant 3.1)."""
    sink = observation.sink
    observed_effect = _observation_is_effect_producing(observation)

    declared_prim = declaration.effect_primitive if declaration is not None else None
    declared_effect_producing = declared_prim in EFFECT_PRODUCING_PRIMITIVES
    declared_inert = declared_prim in INERT_PRIMITIVES

    reasons: list[str] = []

    # The dangerous divergence: observed to produce an effect, declared inert. This is the
    # wrong-primitive lie D exists to catch.
    if observed_effect and declared_inert:
        producing = sorted(
            p for p in observation.observed_primitives if p in EFFECT_PRODUCING_PRIMITIVES
        )
        if observation.observed:
            reasons.append(
                f"sink {sink!r} declares inert primitive {declared_prim!r} but was OBSERVED to "
                f"produce effect-producing primitive(s) {producing}; the declaration diverges "
                f"from behaviour and is not trusted (fail closed, D93 direction D)"
            )
        else:
            reasons.append(
                f"sink {sink!r} declares inert primitive {declared_prim!r} but could not be "
                f"observed (opaque/uninstrumentable); an unverified inert claim fails closed to "
                f"consequential (D93 direction D degrades to B/C for opaque sinks)"
            )
        return VerificationResult(sink=sink, agrees=False, verified_consequential=True,
                                  reasons=reasons)

    # The safe-direction divergence: observed clean, declared effect-producing. Over-declaration.
    if (not observed_effect) and declared_effect_producing:
        reasons.append(
            f"sink {sink!r} declares effect-producing primitive {declared_prim!r} but was "
            f"observed to produce no effect; treated as consequential (a single clean probe does "
            f"not disprove the declaration), divergence flagged for review (D93 direction D)"
        )
        return VerificationResult(sink=sink, agrees=False, verified_consequential=True,
                                  reasons=reasons)

    # No declaration at all: the observation stands alone, fail closed on an unobserved sink.
    if declaration is None:
        if observed_effect:
            reasons.append(
                f"sink {sink!r} is undeclared; treated as consequential by observation "
                f"(fail closed, D93 direction D)"
            )
        return VerificationResult(sink=sink, agrees=(not observed_effect),
                                  verified_consequential=observed_effect, reasons=reasons)

    # Agreement: declared and observed consequentiality match.
    return VerificationResult(sink=sink, agrees=True, verified_consequential=observed_effect,
                              reasons=reasons)
