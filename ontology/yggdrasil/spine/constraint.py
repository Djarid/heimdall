"""The constraint vocabulary: the axioms that can be expressed.

A constraint states what must not hold. A violation triggers Gjallarhorn
(`ONTOLOGY_CONSTRUCTION.md` sections 4.1 and 6). These are the axioms the Phase 1
seed needs; they are checked by Nornir's constraint rules over asserted and derived
facts, deterministically, with no model.

A constraint is authored here as a named node with a `predicate` key that Nornir's
constraint checker knows how to evaluate. The predicate is a plain identifier, not
code: `nornir/rules.py` maps each predicate name to a deterministic Python check.
Keeping the axiom (what must not hold) in the ontology and its evaluation in Nornir
keeps the trust-boundary rule change and the code change reviewable together, but
separable.

The Phase 1 constraints encode the load-bearing invariants of the boundary as
checkable axioms:

- no-tainted-actionable: a TAINTED assertion may never be marked actionable. This
  is the fail-safe of invariant 3.11 expressed as a constraint.
- no-auto-promotion: a promotion that is not backed by a logged promotion event is
  a violation (the D27 discipline).
- action-critical-must-gate: any value classified as reaching a consequential sink
  must be action-critical; a value that reaches a sink but is not marked is the
  critical misclassification of obligation 8.2 and must be caught.
"""

from __future__ import annotations

from ..core import NodeKind, Ontology, TypeNode


# name -> (predicate, label, description)
_CONSTRAINTS = {
    "constraint:no_tainted_actionable": (
        "no_tainted_actionable",
        "no tainted actionable",
        "a TAINTED assertion must never carry actionable: true",
    ),
    "constraint:no_auto_promotion": (
        "no_auto_promotion",
        "no auto promotion",
        "a trust promotion must cite a logged promotion event; none is automatic",
    ),
    "constraint:action_critical_must_gate": (
        "action_critical_must_gate",
        "action-critical must gate",
        "any value that can reach a consequential sink must be marked action-critical",
    ),
}


def register(onto: Ontology) -> None:
    for name, (predicate, label, desc) in _CONSTRAINTS.items():
        onto.add_node(
            TypeNode(
                name=name,
                kind=NodeKind.CONSTRAINT,
                label=label,
                attrs={"predicate": predicate, "description": desc},
            )
        )
