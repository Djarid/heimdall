"""State-delta consequence detection: consequence by what a value would CHANGE.

The false-inert break (D67, measured at about 43 percent in D77) is that inertness is
earned by a CONTENT pattern, and an attacker controls content. Every attempt to fix it by
refining the content pattern has been re-opened by a fresh phrasing (D69, D72), because
that is invariant 3.5's treadmill.

This module judges consequence on a different basis entirely: not how the content reads,
but WHAT IT WOULD CHANGE in the world model. A value that would set a new bank account for
a supplier, a new destination for a salary, a new member of a privileged group, or turn off
a second-factor requirement is consequential BY ITS EFFECT, whatever wording carried it.

Why this is not a blacklist (invariant 3.5). It never enumerates malicious phrasings or
consequential topics in content. It keys on two things an attacker does not author:

  1. WHICH SLOT the value targets, against a set of consequential-critical slots DECLARED
     in the ontology (an authored, reviewed declaration, the same kind of thing as the
     consequential-sink set, not a keyword list); and
  2. WHETHER the value DIFFERS from the currently-stored value for that slot (a state
     comparison, not a text match).

The load-bearing property: the attacker cannot phrase around it. To redirect a payroll they
must actually assert a new salary destination, and that assertion IS the state delta. If the
euphemism is so oblique that no slot value is extracted, then nothing is written to the world
model, so nothing is redirected: the attack fails on its own terms. Harm potential and
detectability therefore rise TOGETHER, which is the opposite of the treadmill, where evasion
reduces detectability while preserving harm.

Honest limit, stated plainly. This bites only where extraction is STRUCTURAL, that is where
the reading layer binds a value to a typed slot (`salary_destination = X`). Where extraction
is an interpretive free-text summary with no slot binding, there is no delta to detect. That
is not a silent hole: an unbound summary is also not an actionable premise, so the same
condition that hides it from this detector also denies it the slot it would need to cause the
effect. It does mean this mitigation's reach is bounded by how much of the pipeline uses
structural extraction, which `plans/dd/fenrir.md` already prefers for exactly this reason.

Fail-closed direction: a detected delta on a consequential slot DENIES the inert label and
routes to gating or review. An undetected delta never grants inertness by itself; inertness
still has to be earned by the existing positive-signal discipline (`earns_inert`). So this
can only ever add caution, never remove it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping


# The consequential-critical SLOT declaration. Authored in the ontology layer, reviewed like
# the consequential-sink set, and deliberately about SLOTS (what kind of fact is being set),
# never about content wording. A slot here means: writing a new value to this slot has a
# real-world effect (money moves, access changes, execution changes, security state changes).
#
# This is a seed set for the four Phase 1 domains. A new domain contributes its own slots the
# same way it contributes types and rules (the D29/D50 attach pattern), so growing coverage
# never edits another domain's declaration.
CONSEQUENTIAL_SLOTS: frozenset[str] = frozenset({
    # money destination and commitment
    "bank_details",
    "salary_destination",
    "payment_destination",
    "standing_order",
    "billing_tier",
    "signing_authority",
    "spend_limit",
    # access and identity
    "group_members",
    "role_grants",
    "permission_scope",
    "credential",
    "mfa_required",
    "session_lifetime",
    # execution and configuration
    "scheduled_job",
    "deployment_target",
    "feature_flag",
    "firewall_rule",
    "webhook_endpoint",
    # data lifecycle
    "retention_policy",
    "backup_enabled",
    # contractual
    "contract_term",
    "supplier_of_record",
})


@dataclass(frozen=True)
class SlotRef:
    """A concrete fact slot on a concrete entity, for example the bank details of a named
    supplier. `entity` scopes the slot so two suppliers' bank details are distinct facts."""

    entity: str
    slot: str

    def key(self) -> str:
        return f"{self.entity}::{self.slot}"


@dataclass(frozen=True)
class ProposedFact:
    """A value an assertion would write to a slot. Produced by structural extraction; the
    reading layer binds an extracted value to a slot, and this is that binding."""

    slot: SlotRef
    value: str


@dataclass(frozen=True)
class DeltaFinding:
    """The outcome for one proposed fact. `is_delta` is True only when the slot is
    consequential-critical AND the proposed value differs from the stored value. `reason`
    carries the audit string; `is_new_fact` distinguishes setting a slot that had no prior
    value (also a delta) from overwriting an existing one, since the first is how an attacker
    establishes a fact rather than changing one."""

    fact: ProposedFact
    is_delta: bool
    is_new_fact: bool = False
    reason: str = ""


# A StateOracle answers "what value is currently stored for this slot?", returning None when
# the slot is unset. In the live system this reads Mímisbrunnr; here it is injected, so the
# detector is testable before the store exists and carries no store dependency.
StateOracle = Callable[[SlotRef], "str | None"]


def dict_oracle(state: Mapping[str, str]) -> StateOracle:
    """A StateOracle over a plain mapping keyed by `SlotRef.key()`. For tests and for the
    in-memory reference path."""

    def _oracle(ref: SlotRef) -> "str | None":
        return state.get(ref.key())

    return _oracle


def _normalise(value: str) -> str:
    """Compare values on a conservative normalisation (case and surrounding whitespace).
    Deliberately NOT a semantic comparison: any difference beyond case and whitespace counts
    as a change, so an attacker cannot dodge the comparison with formatting noise, and the
    detector never has to judge whether two different values 'mean the same thing'."""
    return " ".join(value.split()).casefold()


def evaluate_fact(fact: ProposedFact, oracle: StateOracle) -> DeltaFinding:
    """Decide whether one proposed fact is a consequential state delta."""
    if fact.slot.slot not in CONSEQUENTIAL_SLOTS:
        return DeltaFinding(
            fact=fact,
            is_delta=False,
            reason=f"slot {fact.slot.slot!r} is not consequential-critical",
        )

    current = oracle(fact.slot)
    if current is None:
        return DeltaFinding(
            fact=fact,
            is_delta=True,
            is_new_fact=True,
            reason=(
                f"establishes a first value for consequential slot "
                f"{fact.slot.key()!r}; a new consequential fact is a delta"
            ),
        )
    if _normalise(current) != _normalise(fact.value):
        return DeltaFinding(
            fact=fact,
            is_delta=True,
            reason=(
                f"changes consequential slot {fact.slot.key()!r} from a stored value to a "
                f"different one"
            ),
        )
    return DeltaFinding(
        fact=fact,
        is_delta=False,
        reason=f"restates the stored value for {fact.slot.key()!r}; no change, no delta",
    )


@dataclass
class DeltaVerdict:
    """The outcome over all facts an assertion proposes. `deny_inert` is the fail-closed
    signal the classifier consumes: True when any proposed fact is a consequential delta."""

    findings: list[DeltaFinding] = field(default_factory=list)

    @property
    def deltas(self) -> list[DeltaFinding]:
        return [f for f in self.findings if f.is_delta]

    @property
    def deny_inert(self) -> bool:
        return bool(self.deltas)

    def reasons(self) -> list[str]:
        return [f.reason for f in self.deltas]


def evaluate(facts: list[ProposedFact], oracle: StateOracle) -> DeltaVerdict:
    """Evaluate every proposed fact and return the verdict. An assertion proposing no facts
    (interpretive extraction with no slot binding) yields no deltas and therefore does not
    deny inert: this detector only ever ADDS caution, and inertness must still be earned by
    the existing positive-signal discipline."""
    return DeltaVerdict(findings=[evaluate_fact(f, oracle) for f in facts])
