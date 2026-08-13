"""The UNCLASSIFIED fail-safe: the coverage safety net.

Content that matches no classification rule is typed `UNCLASSIFIED_DATA_ASSERTION`,
`actionable: false`, and routed to human review. It never defaults to a trusted or
actionable type (invariant 3.11, `ONTOLOGY_CONSTRUCTION.md` 4.1). This must exist
from the first day, because coverage starts low and the fail-safe carries whatever
the ontology does not yet cover. It carries more traffic for web and social content
than for email, which are higher-volume and less structured.

The fail-safe is the hard invariant behind the coverage-measurement obligation
(8.1): coverage is a reported number, but "uncovered content fails safe" is not
negotiable. A test that finds uncovered content reaching a trusted or actionable
type is a critical failure, not a coverage statistic.

It anchors to BFO `generically dependent continuant`, the same root as a
communication: an unclassified assertion is still information content, we simply do
not yet have a more specific type for it. That keeps it inside the tree rather than
floating outside BFO.
"""

from __future__ import annotations

from .core import NodeKind, Ontology, Relation, RelationKind, TypeNode


UNCLASSIFIED = "unclassified:data_assertion"

# A distinct fail-safe for a genuine cross-domain classification tie (D31): two
# top-tier rules of equal specificity named different high-risk types, so Nornir
# routes to human review rather than guessing. It is NOT the same as UNCLASSIFIED:
# UNCLASSIFIED is "no rule matched" (low information), whereas this is "more than one
# high-risk type matched equally" (high information, high risk). It is high-risk and
# gated, so a value here is still treated as action-critical if it can reach a sink;
# it fails safe to review, never to an inert or trusted type. `risk=high` so the
# harness recognises it as a non-downgrade outcome.
HIGH_RISK_UNRESOLVED = "unclassified:high_risk_unresolved"


def register(onto: Ontology) -> None:
    onto.add_node(
        TypeNode(
            name=UNCLASSIFIED,
            kind=NodeKind.FAILSAFE,
            label="UNCLASSIFIED_DATA_ASSERTION",
            attrs={
                "actionable": False,
                "route": "human_review",
                "description": "content that matched no classification rule; fails safe "
                "to review, never trusted or actionable",
            },
        )
    )
    onto.add_relation(
        Relation(UNCLASSIFIED, RelationKind.ANCHORS_TO, "bfo:generically_dependent_continuant")
    )
    onto.add_node(
        TypeNode(
            name=HIGH_RISK_UNRESOLVED,
            kind=NodeKind.FAILSAFE,
            label="HIGH_RISK_UNRESOLVED",
            attrs={
                "actionable": False,
                "route": "human_review",
                "risk": "high",
                "description": "a genuine cross-domain classification tie between high-risk "
                "types (D31); routed to review, gated, never silently typed or downgraded",
            },
        )
    )
    onto.add_relation(
        Relation(HIGH_RISK_UNRESOLVED, RelationKind.ANCHORS_TO, "bfo:generically_dependent_continuant")
    )
