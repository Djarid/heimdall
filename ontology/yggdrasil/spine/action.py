"""The action vocabulary: the action types that can exist.

System-wide vocabulary, not per-agent binding (D20): which agent may perform which
action is control-surface state in Himinbjorg (`control_surface.py`), not here. An
action type is a BFO `process`: an action is something that unfolds in time and has
participants (the value it acts on, the agent that performs it).

Phase 1 actions are small and read-only or human-gated (`ONTOLOGY_CONSTRUCTION.md`
section 4.1): classify, triage, summarise, draft-for-review. None is consequential,
so the Phase 1 action-critical SET is empty. The machinery to declare an action
consequential is present and dormant: an action type carries a `consequential`
attribute and a consequential action registers a SINK node, but no Phase 1 action
sets `consequential=True`. This is deliberate: Gjoll is dormant in Phase 1
(invariant 3.6, HEIMDALL.md Phase 1), and we prove the machinery exists without
arming it.

A consequential sink is what flow-to-sink reachability propagates back from (D24,
D30). A value that can reach a SINK is action-critical. To exercise that machinery
in tests without arming Phase 1, the test corpus supplies its own agent context
with its own sinks (agent-scoped, D24); the loaded ontology ships none.
"""

from __future__ import annotations

from ..core import NodeKind, Ontology, Relation, RelationKind, TypeNode


# name -> (label, human_gated, consequential, description)
_ACTIONS = {
    "action:classify": (
        "classify",
        False,
        False,
        "assign a marshalled assertion its ontology type; internal, not consequential",
    ),
    "action:triage": (
        "triage",
        False,
        False,
        "route an assertion to a queue; internal, not consequential",
    ),
    "action:summarise": (
        "summarise",
        False,
        False,
        "produce an inert INTERPRETIVE_SUMMARY assertion; not consequential",
    ),
    "action:draft_for_review": (
        "draft-for-review",
        True,
        False,
        "prepare a draft a human must approve before anything leaves; human-gated, "
        "so not consequential on its own",
    ),
}


def register(onto: Ontology) -> None:
    for name, (label, human_gated, consequential, desc) in _ACTIONS.items():
        onto.add_node(
            TypeNode(
                name=name,
                kind=NodeKind.ACTION_TYPE,
                label=label,
                attrs={
                    "human_gated": human_gated,
                    "consequential": consequential,
                    "description": desc,
                },
            )
        )
        onto.add_relation(Relation(name, RelationKind.ANCHORS_TO, "bfo:process"))

    # The Phase 1 action-critical set is empty: assert it, so a future edit that
    # arms a consequential action without updating the phase is caught by a test.
    assert not any(a[2] for a in _ACTIONS.values()), (
        "Phase 1 action-critical set must be empty (ONTOLOGY_CONSTRUCTION.md 4.1); "
        "no action may set consequential=True until Gjoll is armed in a later phase"
    )
