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

What this does not do. It does not attest that a declaration is HONEST. A sink author who
declares a consequential sink as non-consequential, or declares an action parameter as inert,
still defeats the gate, and that remains the open root seam (5.1) which only attestation or
derivation from real data flow can close. What this closes is the narrower and entirely
avoidable class where an ERROR or DRIFT in a declaration silently disables the gate.
"""

from __future__ import annotations

from dataclasses import dataclass, field


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
    silent-omission path. `consequential_by_default` records the ontology's view of whether
    this sink can cause a real-world effect at all; the AGENT's consequential-sink set still
    decides whether it is consequential for a given agent (D24 agent scoping), and this flag
    does not override that."""

    name: str
    parameters: frozenset[str]
    consequential_by_default: bool = True


@dataclass
class SinkRegistry:
    """The declared sinks. A sink absent from the registry is an ERROR, not a
    non-consequential sink: that inversion is the point of this module."""

    declarations: dict = field(default_factory=dict)

    def declare(self, declaration: SinkDeclaration) -> None:
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


def effective_consequential(
    sink: str,
    registry: SinkRegistry,
    agent_consequential_sinks: frozenset,
) -> bool:
    """Whether the gate should treat this sink as consequential, with the fail-closed
    inversion applied.

    The distinction that keeps agent scoping (D24) intact while closing the fail-open path:

      - undeclared sink: TRUE. We cannot know it is safe, so it is consequential.
      - declared, and in the agent's consequential set: TRUE, as before.
      - declared, not in the agent's set, and the ontology says it is not consequential at
        all: FALSE. Legitimately ungated, no error, no friction.
      - declared, not in the agent's set, but the ontology says it IS consequential by
        default: FALSE for this agent, which is the agent-scoped answer, but the caller is
        expected to have validated the declaration first so this is a deliberate scoping
        decision rather than a typo.
    """
    if not registry.is_declared(sink):
        return True
    return sink in agent_consequential_sinks
