"""Per-domain Nornir rule modules.

Each subject-matter domain contributes its own classification and derivation rules
here, as a sibling module. This is what makes the domain attach test (D29) hold for
Nornir's rules, not just for the ontology types: a new domain adds a module and a
line in `register_all`; it never edits another domain's rules. The shared,
authored-once rules (the derivation rule, the constraint checks, flow-to-sink) stay
in `nornir/rules.py`; only the domain-specific classification predicates and the
domain's high-risk type declarations live here.

`register_all` is idempotent: `register_classification_rule` and
`register_high_risk_types` replace or union rather than duplicate, so constructing
Nornir more than once (as tests do) is safe.
"""

from __future__ import annotations


def register_all() -> None:
    from . import communications, scheduling, finance

    communications.register_rules()
    scheduling.register_rules()
    finance.register_rules()
