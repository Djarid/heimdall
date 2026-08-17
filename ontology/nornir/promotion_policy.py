"""Promotion policy: corroboration for consequential facts, and graded review priority.

Two mitigations for the false-inert break that act at the PROMOTION and REVIEW boundaries
rather than at classification, so neither depends on the classifier being right.

MITIGATION 4, corroboration for promotion. D76 records that Heimdall will adopt Gleipnir's
tiered memory, in which a value only becomes a premise a downstream agent may treat as fact by
crossing a human-gated promotion boundary. This module adds the policy that boundary enforces
for consequential facts: a value that would set a consequential slot is not promotable on the
word of a SINGLE source. It requires either corroboration from independent sources that agree,
or explicit human approval. This is the standard out-of-band-confirmation defence against
business-email-compromise, expressed structurally: an attacker who controls one channel cannot
satisfy a rule that requires two independent ones, and rephrasing does not help, because the
requirement is about PROVENANCE COUNT, not wording.

The rules, all fail-closed:

  - a non-consequential slot promotes on a single source, as now (no new friction);
  - a consequential slot requires `required_corroborations` DISTINCT sources agreeing, or a
    human approval;
  - the same source repeating itself is not corroboration (distinctness is enforced);
  - sources that DISAGREE never promote, whatever the count, and escalate instead, because a
    conflict on a consequential fact is a stronger signal than either value.

MITIGATION 5, graded review priority. Today the classification outcome is effectively binary:
either a value routes to review, or it does not. That makes the false-inert break costly,
because an inert-typed value gets NO review at all. This module grades it instead: a value that
is inert in effect but touches a consequential entity is queued for LOW-priority review rather
than no review, which restores some review coverage at bounded friction. Note that the routing
half of this is already implemented by the consequence axis (D80), whose `disposition` sends an
inert speech act with a weak content signal to review; what is added here is the PRIORITY, so
the queue can be worked in a sensible order rather than treating every routed item alike.

Neither mitigation grants trust. Both only ever withhold promotion or add review, so they
compose with the existing fail-closed discipline and cannot introduce a silent downgrade.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .state_delta import CONSEQUENTIAL_SLOTS, SlotRef


@dataclass(frozen=True)
class SourcedValue:
    """A value for a slot, together with the concrete source that asserted it. `source` is a
    provenance identifier (a mailbox, a feed, a document id), not a trust level: two values
    from the same source are one source, however many times they arrive."""

    slot: SlotRef
    value: str
    source: str


@dataclass
class PromotionDecision:
    """The outcome of a promotion request. `promoted` is True only when the policy is
    satisfied. `requires_human` marks the cases that must go to the human promotion gate
    rather than being refused outright, which is the normal path for a consequential fact
    with insufficient corroboration."""

    promoted: bool
    requires_human: bool = False
    conflict: bool = False
    reasons: list = field(default_factory=list)


def _normalise(value: str) -> str:
    return " ".join(value.split()).casefold()


def evaluate_promotion(
    candidates: list,
    required_corroborations: int = 2,
    human_approved: bool = False,
) -> PromotionDecision:
    """Decide whether a set of `SourcedValue`s for ONE slot may be promoted to a trusted fact.

    `candidates` must all concern the same slot. `human_approved` records that the human
    promotion gate has already approved this exact value, which satisfies the policy on its
    own (a human is the corroboration of last resort, and D76's gate is where that happens)."""
    if not candidates:
        return PromotionDecision(
            promoted=False, reasons=["no candidate values to promote"]
        )

    slot = candidates[0].slot
    consequential = slot.slot in CONSEQUENTIAL_SLOTS

    # A conflict on a consequential fact is decisive: never promote, escalate.
    distinct_values = {_normalise(c.value) for c in candidates}
    if len(distinct_values) > 1:
        return PromotionDecision(
            promoted=False,
            requires_human=True,
            conflict=True,
            reasons=[
                f"sources disagree on {slot.key()!r} ({len(distinct_values)} distinct values); "
                f"a conflict on a consequential fact is escalated, never resolved by count"
            ] if consequential else [
                f"sources disagree on {slot.key()!r}; escalated for human resolution"
            ],
        )

    if not consequential:
        return PromotionDecision(
            promoted=True,
            reasons=[f"slot {slot.slot!r} is not consequential-critical; single source suffices"],
        )

    if human_approved:
        return PromotionDecision(
            promoted=True,
            reasons=[f"consequential slot {slot.key()!r} promoted on human approval"],
        )

    distinct_sources = {c.source for c in candidates}
    if len(distinct_sources) >= required_corroborations:
        return PromotionDecision(
            promoted=True,
            reasons=[
                f"consequential slot {slot.key()!r} corroborated by "
                f"{len(distinct_sources)} independent sources"
            ],
        )

    return PromotionDecision(
        promoted=False,
        requires_human=True,
        reasons=[
            f"consequential slot {slot.key()!r} has {len(distinct_sources)} distinct source(s), "
            f"below the required {required_corroborations}; not promotable on a single "
            f"source's word, routed to the human promotion gate"
        ],
    )


class ReviewPriority(Enum):
    """How urgently a routed item should be worked. NONE means not queued at all."""

    NONE = "none"
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


def review_priority(
    effective_inert: bool,
    touches_consequential_slot: bool,
    has_structural_signal: bool = False,
) -> ReviewPriority:
    """Grade a value for the review queue (mitigation 5).

    The case this exists for is the middle row: a value that is inert IN EFFECT but touches a
    consequential slot would previously have received no review at all. It now gets LOW
    priority, which restores coverage at bounded friction, and the queue can be worked in a
    sensible order rather than treating every routed item alike."""
    if not effective_inert:
        # Denied inertness: the strength of the evidence sets the urgency.
        return ReviewPriority.HIGH if has_structural_signal else ReviewPriority.NORMAL
    if touches_consequential_slot:
        return ReviewPriority.LOW
    return ReviewPriority.NONE
