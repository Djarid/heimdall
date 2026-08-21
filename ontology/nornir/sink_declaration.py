"""The sink-declaration schema and its fail-closed validation.

Why this is the highest-value remaining mitigation. `ADVERSARIAL_REVIEW.md` 5.1 ranks sink and
flow declarations as THE root seam: they are trusted input and nothing attests them. D78 then
showed the containment for the false-inert break rests on exactly these declarations, because
the action-critical determination and the gate are declaration-driven rather than
classification-driven. So the declarations carry the guarantee, and until now they were an
unchecked dict.

Three concrete FAIL-OPEN paths existed in the gate, each triggered by a declaration ERROR
rather than by an attack, and each silently authorising:

  1. An UNKNOWN OR MISTYPED SINK. The gate computed `sink_is_consequential = proposal.sink in
     agent_consequential_sinks`. A typo, a rename or a drifted id makes that False, which makes
     the whole block condition False, which AUTHORISES. A declaration error therefore disabled
     the gate silently. This is the worst of the three.
  2. A SILENTLY OMITTED PARAMETER. The gate iterated only the entries present in `consumes`. A
     parameter the sink really uses, but which the declaration does not mention, was never
     checked at all.
  3. AN INVALID CONSUME MODE. The gate skipped anything that was not exactly `CONSUME_ACTION`,
     so a typo such as "action" or "ACTIION" was treated as inert consumption.

The fix, and the one distinction that makes it correct. It would be wrong to simply treat every
unknown sink as consequential, because agent-scoped action-criticality (D24) legitimately means
a sink can be non-consequential FOR THIS AGENT, and gating it then would be friction without
safety. The right distinction is between:

  - a sink that IS DECLARED and is known not to be consequential for this agent: legitimately
    ungated, no error; and
  - a sink that IS NOT DECLARED AT ALL: a declaration error, which must FAIL CLOSED.

So this module adds a registry of declared sinks with their parameter contracts, and a
validator that refuses a proposal referencing an undeclared sink, an unknown parameter, a
missing required parameter or an invalid mode. Validation runs BEFORE the gate, and a
validation failure is a block, not a warning.

What D81 did not do, and what D89 (direction B) now adds. D81 proved a declaration WELL-FORMED,
not HONEST. Two well-formed but dishonest declarations still defeated the gate: a genuinely
consequential sink flagged `consequential_by_default=False`, and (the A half, in gjoll.py) an
action parameter flagged inert. Direction B, built here, stops trusting the per-sink boolean.
Each sink declares the EFFECT PRIMITIVE it performs (move money, grant or use access, run or
change code or config, exfiltrate data, destroy data, make a binding commitment, change
security state), drawn from a small, fixed, attested set of effect-producing primitives, and
consequentiality is DERIVED from that primitive, not read from the flag. So an author cannot
mark a money-moving sink non-consequential: `effect_primitive="move_money"` is in the
effect-producing set, so the sink is consequential however the boolean is set.

The honest limit of B, stated rather than hidden. This RELOCATES the trust, it does not remove
it. The effect-primitive set (`EFFECT_PRODUCING_PRIMITIVES`) is itself authored input, so the
trust moves from a boolean on every sink to one small, stable, auditable base table. That is a
real gain (a mis-declaration is now an attack on a rarely-changing shared table rather than a
one-line per-sink edit, and a sink that declares NO primitive fails closed to consequential),
but a sink that dishonestly declares the WRONG primitive (a money sink declaring itself
`display_only`) is still defeated. Closing that last step needs C (attest who may declare) or D
(verify the primitive against behaviour), which stay named follow-ons (see
`plans/declaration_attestation_scoping.md`). A model is never on this path: the derivation is a
set membership test over an authored table (invariant 3.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field


# The attested effect-primitive taxonomy (D89, direction B). This is the small, fixed base of
# real-world EFFECTS, mirroring the external consequence test the false-inert corpora use. A
# sink whose declared primitive is in this set is consequential BY DERIVATION, regardless of its
# `consequential_by_default` boolean, so a dishonest flag cannot disarm the gate. The set is the
# relocated trust: it is authored, but it is one auditable table rather than a per-sink flag.
MOVE_MONEY = "move_money"
GRANT_OR_USE_ACCESS = "grant_or_use_access"
RUN_OR_CHANGE_CODE = "run_or_change_code"
EXFILTRATE_DATA = "exfiltrate_data"
DESTROY_DATA = "destroy_data"
BINDING_COMMITMENT = "binding_commitment"
CHANGE_SECURITY_STATE = "change_security_state"

EFFECT_PRODUCING_PRIMITIVES = frozenset({
    MOVE_MONEY,
    GRANT_OR_USE_ACCESS,
    RUN_OR_CHANGE_CODE,
    EXFILTRATE_DATA,
    DESTROY_DATA,
    BINDING_COMMITMENT,
    CHANGE_SECURITY_STATE,
})

# A non-effect-producing primitive a sink may honestly declare. `None` (no primitive declared)
# is NOT this: an undeclared primitive fails closed to consequential, exactly as an undeclared
# sink does, so silence never earns inert.
DISPLAY_ONLY = "display_only"
STORE_ONLY = "store_only"
INERT_PRIMITIVES = frozenset({DISPLAY_ONLY, STORE_ONLY})


# The two consumption modes, mirrored from gjoll to keep this module independent of import
# order. A mode outside this set is a validation error, never a silently-inert default.
CONSUME_INERT = "INERT"
CONSUME_ACTION = "ACTION"
VALID_MODES = frozenset({CONSUME_INERT, CONSUME_ACTION})


@dataclass(frozen=True)
class SinkDeclaration:
    """The declared contract of one sink.

    `name` is the sink node id. `parameters` is the full set of parameter names the sink
    consumes; a proposal must account for every one of them, which is what closes the
    silent-omission path.

    `effect_primitive` (D89, direction B) is the real-world effect this sink performs, drawn
    from the attested taxonomy above. Consequentiality is DERIVED from it: a primitive in
    `EFFECT_PRODUCING_PRIMITIVES` makes the sink consequential regardless of any boolean, so a
    dishonest flag cannot disarm the gate. `None` means no primitive was declared, which FAILS
    CLOSED to consequential (silence never earns inert), the same inversion as an undeclared
    sink. An explicitly inert primitive (display/store only) is the only way to earn
    non-consequential, and even then the AGENT's set still applies (D24).

    `consequential_by_default` is retained for backward compatibility and reporting only; it is
    NO LONGER the source of truth for consequentiality. When an `effect_primitive` is declared,
    the derivation uses it; the flag is ignored. It is kept so existing declarations and the
    D81 tests still construct, and so a reviewer can see a divergence between a stated flag and a
    derived primitive (a divergence is itself a signal worth surfacing)."""

    name: str
    parameters: frozenset[str]
    consequential_by_default: bool = True
    effect_primitive: "str | None" = None
    # Provenance (D94, direction C). `authoriser` is the identity that declared this sink;
    # `attestation` is the keyed digest over the declaration's canonical bytes (see
    # `sink_attestation.py`). Both default to None so existing and test declarations still
    # construct; verification is only enforced where a caller supplies a trusted authoriser set,
    # exactly as effect-primitive derivation (B) and behaviour verification (D) are opt-in on the
    # gate. When enforced, an absent authoriser or digest is REFUSED (fail closed): silence never
    # earns trust. Attestation binds WHO declared it and that it is UNALTERED, never that it is
    # TRUE (the malicious-authoriser limit, addressed by B and D, not C).
    authoriser: "str | None" = None
    attestation: "str | None" = None


@dataclass
class SinkRegistry:
    """The declared sinks. A sink absent from the registry is an ERROR, not a
    non-consequential sink: that inversion is the point of this module."""

    declarations: dict = field(default_factory=dict)

    def declare(self, declaration: SinkDeclaration) -> None:
        self.declarations[declaration.name] = declaration

    def declare_attested(self, declaration: SinkDeclaration, trusted) -> None:
        """Register a declaration ONLY if its provenance verifies against the trusted authoriser
        set (D94, direction C). An unattested, unknown-authoriser or tampered declaration is
        REFUSED with a ValueError, never silently admitted: this is the fail-closed load gate.
        `trusted` is a `TrustedAuthoriserSet`. Import is local to avoid a module-level cycle and
        to keep this module usable without attestation for the existing callers."""
        from .sink_attestation import verify_attestation
        result = verify_attestation(declaration, trusted)
        if not result.verified:
            raise ValueError(result.reason)
        self.declarations[declaration.name] = declaration

    def get(self, name: str) -> "SinkDeclaration | None":
        return self.declarations.get(name)

    def is_declared(self, name: str) -> bool:
        return name in self.declarations


@dataclass
class ValidationResult:
    """The outcome of validating one proposal against the registry. `errors` being non-empty
    means the proposal must be BLOCKED before the gate runs. `treat_as_consequential` is the
    fail-closed instruction for the gate: when a sink is undeclared we cannot know it is safe,
    so it is treated as consequential regardless of the agent's set."""

    errors: list = field(default_factory=list)
    treat_as_consequential: bool = False

    @property
    def valid(self) -> bool:
        return not self.errors


def validate_proposal(
    sink: str,
    consumes: dict,
    registry: SinkRegistry,
    known_assertion_ids: frozenset,
) -> ValidationResult:
    """Validate a proposal's declarations before the gate evaluates it. Fails closed.

    `sink` is the proposed sink id, `consumes` the declared parameter-to-mode mapping,
    `known_assertion_ids` the ids the classifier actually produced for this batch."""
    result = ValidationResult()

    # 1. The sink must be declared. An undeclared sink is a declaration error AND is treated
    #    as consequential, so a typo or a rename can no longer silently disable the gate.
    declaration = registry.get(sink)
    if declaration is None:
        result.errors.append(
            f"sink {sink!r} is not declared in the sink registry; a proposal cannot be "
            f"authorised against an undeclared sink (fail closed: treated as consequential)"
        )
        result.treat_as_consequential = True
        # Without a declaration there is no parameter contract to check against, so the
        # remaining structural checks that do not need it still run below.

    # 2. Every consume mode must be valid. A typo must not read as inert consumption.
    for param_id, mode in consumes.items():
        if mode not in VALID_MODES:
            result.errors.append(
                f"parameter {param_id!r} declares consume mode {mode!r}, which is not one of "
                f"{sorted(VALID_MODES)}; an unrecognised mode is not treated as inert"
            )

    # 3. No phantom parameters: every declared parameter must be an assertion that exists.
    for param_id in consumes:
        if param_id not in known_assertion_ids:
            result.errors.append(
                f"parameter {param_id!r} is declared in consumes but is not a known classified "
                f"assertion; the declaration has drifted from the batch"
            )

    # 4. No silent omissions: every parameter the sink declares must be accounted for.
    if declaration is not None:
        missing = sorted(declaration.parameters - set(consumes))
        if missing:
            result.errors.append(
                f"sink {sink!r} declares parameters {missing} that the proposal does not "
                f"account for; an unaccounted parameter would never be gated"
            )
        extra = sorted(set(consumes) - declaration.parameters)
        if extra:
            result.errors.append(
                f"proposal declares parameters {extra} that sink {sink!r} does not accept; "
                f"the declaration does not match the sink contract"
            )

    return result


def sink_is_intrinsically_consequential(declaration: "SinkDeclaration | None") -> bool:
    """Derive a sink's INTRINSIC consequentiality from its declared effect primitive (D89,
    direction B), never from the `consequential_by_default` boolean. Fails closed.

      - no declaration at all: TRUE (an undeclared sink is an error, treated consequential).
      - a declared effect primitive in EFFECT_PRODUCING_PRIMITIVES: TRUE, by derivation. A
        dishonest `consequential_by_default=False` cannot change this.
      - a declared inert primitive (display/store only): FALSE. This is the only honest way to
        earn non-consequential.
      - no primitive declared (`effect_primitive is None`): TRUE. Silence fails closed to
        consequential, exactly like an undeclared sink; it never earns inert by omission.
      - an UNRECOGNISED primitive string: TRUE. An unknown primitive is not read as inert,
        the same fail-closed rule the consume-mode validation uses.

    This is a set-membership test over the attested table, not a model call (invariant 3.1)."""
    if declaration is None:
        return True
    prim = declaration.effect_primitive
    if prim is None:
        return True
    if prim in EFFECT_PRODUCING_PRIMITIVES:
        return True
    if prim in INERT_PRIMITIVES:
        return False
    # Unrecognised primitive: fail closed.
    return True


def effective_consequential(
    sink: str,
    registry: SinkRegistry,
    agent_consequential_sinks: frozenset,
) -> bool:
    """Whether the gate should treat this sink as consequential, with the fail-closed
    inversion (D81) AND the derive-from-effect-primitive rule (D89, direction B) applied.

    The order matters. Intrinsic consequentiality is DERIVED first (from the effect primitive,
    not the flag); agent scoping (D24) then applies ONLY to narrow a sink that is intrinsically
    consequential down to out-of-scope for this agent. A sink that is intrinsically
    consequential and NOT in the agent's set is still consequential, because the whole point of
    B is that a real money-mover is gated whatever any per-agent or per-sink declaration claims.

      - undeclared sink: TRUE (fail closed, D81).
      - declared, intrinsically consequential by its effect primitive: TRUE. The
        `consequential_by_default` flag and the agent set can no longer switch this off, which
        is what closes the dishonest-flag seam.
      - declared, intrinsically NON-consequential (an honest display/store-only primitive):
        FALSE. Legitimately ungated, no friction. The agent set is irrelevant, because a sink
        with no real-world effect cannot be made consequential by scoping.

    Note the deliberate change from D81 behaviour: consequentiality no longer rests on
    `sink in agent_consequential_sinks`. The agent set is retained by callers for
    reporting/scoping of WHICH consequential sinks this agent may target, but it can no longer
    make an intrinsically consequential sink non-consequential. That was the dishonest-flag
    hole. Agent scoping that legitimately ungates a NON-consequential sink still works, because
    such a sink is intrinsically non-consequential and returns FALSE here regardless."""
    if not registry.is_declared(sink):
        return True
    declaration = registry.get(sink)
    return sink_is_intrinsically_consequential(declaration)
