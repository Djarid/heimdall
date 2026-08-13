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
