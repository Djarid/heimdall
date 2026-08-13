"""The trust lattice: TAINTED, VOUCHED, TRUSTED, CANONICAL.

The system-wide trust levels and the promotion relations between them (D20, and
`ONTOLOGY_CONSTRUCTION.md` section 2.2). A level is a BFO `role`: it is a role an
assertion bears, realised in the classification and promotion processes, not an
intrinsic quality of the content. This matters because trust is assigned by origin
and can be promoted by a deliberate event, which is what a role captures and a
quality would not.

The lattice is ordered by increasing trust. Promotion only ever moves upward and
only by a logged promotion event (the Odin/human ratification discipline lives in
`ONTOLOGY_CONSTRUCTION.md` section 7; here we define the levels and the legal
promotion edges). Untrusted-derived content enters as TAINTED and stays TAINTED
unless something promotes it; nothing in the loaded ontology promotes it
automatically.
"""

from __future__ import annotations

from ..core import NodeKind, Ontology, Relation, RelationKind, TypeNode


# Ordered low to high. The order is the lattice; an index lets a rule compare two
# levels without hard-coding pairs.
TRUST_ORDER = ("TAINTED", "VOUCHED", "TRUSTED", "CANONICAL")

_DESCRIPTIONS = {
    "TAINTED": "untrusted-derived; the default for anything read from external content",
    "VOUCHED": "attested by a bounded source but not yet fully trusted",
    "TRUSTED": "promoted to trusted by a logged promotion event",
    "CANONICAL": "system-authored ground truth; the highest level",
}


def register(onto: Ontology) -> None:
    for level in TRUST_ORDER:
        onto.add_node(
            TypeNode(
                name=f"trust:{level}",
                kind=NodeKind.TRUST_LEVEL,
                label=level,
                attrs={
                    "rank": TRUST_ORDER.index(level),
                    "description": _DESCRIPTIONS[level],
                },
            )
        )
        # Each level is a BFO role.
        onto.add_relation(
            Relation(f"trust:{level}", RelationKind.ANCHORS_TO, "bfo:role")
        )
    # Legal promotion edges: strictly upward, one step at a time. A rule that wants
    # to promote must follow an existing PROMOTES_TO edge; there is no edge back
    # down, and no edge that skips a level, so promotion is monotone and auditable.
    for lower, higher in zip(TRUST_ORDER, TRUST_ORDER[1:]):
        onto.add_relation(
            Relation(f"trust:{lower}", RelationKind.PROMOTES_TO, f"trust:{higher}")
        )
