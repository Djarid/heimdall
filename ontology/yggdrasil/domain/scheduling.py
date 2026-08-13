"""The scheduling seed domain, medium-neutral. The second domain (attach test D29).

This domain exists to prove the domain attach test for real: a second subject-matter
domain must attach under the shared spine WITHOUT editing the communications domain or
the spine (`ONTOLOGY_CONSTRUCTION.md` 4.2, D29). Nothing in `communications.py`,
`spine/`, `core.py` or `unclassified.py` changes to add scheduling; this module and a
sibling rule module are the whole of it.

Subject-matter: a scheduling item is something that concerns time and commitment, a
meeting, a task, a deadline, a reminder. It is a domain, not a medium: a meeting
invitation types identically whether it arrived by email, web calendar or tool output.

The BFO anchoring (D23, never redefining a BFO class):

- A `scheduling_item` is information content about a temporal commitment: a BFO
  `generically dependent continuant`, the same root as a communication, so the two
  domains relate through their shared ancestor. This is what the shared upper layer
  buys: a scheduling item and a communication are both GDCs and can be reasoned about
  together (a message that schedules a meeting links the two domains through BFO).
- A `scheduled_action` is what a scheduling item asks to happen at a time: a BFO
  `realizable entity`, a disposition to act that is realised at its due time. This is
  the high-risk branch, for the same reason as communications' requested_action: a
  scheduled action can stage a consequential effect (a task that runs a command, a
  reminder that triggers a payment) and its value must be action-critical if it can
  reach a consequential sink.

The high-risk subtype is `scheduled_task`: a scheduling item that will cause an action
to run. It is the cross-domain staging hinge, a communications value can flow into a
scheduled_task field that reaches an execution sink (obligation 8.4, D30).
"""

from __future__ import annotations

from ..core import NodeKind, Ontology, Relation, RelationKind, TypeNode


def _domain_type(name: str, label: str, anchor: str | None, parent: str | None,
                 onto: Ontology, **attrs: object) -> None:
    onto.add_node(
        TypeNode(
            name=name,
            kind=NodeKind.DOMAIN_TYPE,
            label=label,
            attrs=dict(domain="scheduling", medium_neutral=True, **attrs),
        )
    )
    if parent is not None:
        onto.add_relation(Relation(name, RelationKind.IS_A, parent))
    if anchor is not None:
        onto.add_relation(Relation(name, RelationKind.ANCHORS_TO, anchor))


def register(onto: Ontology) -> None:
    # The domain root: a scheduling item is information content about a commitment.
    _domain_type(
        "sched:scheduling_item",
        "scheduling item",
        anchor="bfo:generically_dependent_continuant",
        parent=None,
        onto=onto,
        description="information content about a temporal commitment: a meeting, task, "
        "deadline or reminder; medium-neutral",
    )

    # A scheduled_action: what the item asks to happen at a time. Realizable entity.
    _domain_type(
        "sched:scheduled_action",
        "scheduled action",
        anchor="bfo:realizable_entity",
        parent="sched:scheduling_item",
        onto=onto,
        description="what a scheduling item asks to happen at a time; inert content here, "
        "never realised by Heimdall",
    )
    onto.add_relation(
        Relation("sched:scheduling_item", RelationKind.HAS_FIELD, "sched:scheduled_action")
    )

    # Low-risk subtype: a calendar entry that asks nothing consequential.
    _domain_type(
        "sched:calendar_entry",
        "calendar entry",
        anchor=None,  # inherits scheduled_action's anchor
        parent="sched:scheduled_action",
        onto=onto,
        risk="low",
        description="a meeting, reminder or deadline that carries no consequential action",
    )
    # High-risk subtype: a scheduled task that will cause an action to run. The
    # cross-domain staging hinge.
    _domain_type(
        "sched:scheduled_task",
        "scheduled task",
        anchor=None,
        parent="sched:scheduled_action",
        onto=onto,
        risk="high",
        description="a scheduling item that will cause an action to run at its due time; "
        "can stage a consequential effect and must be gated if it can reach a sink",
    )
