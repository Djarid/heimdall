"""The control surface: per-agent binding. NOT part of the ontology (D20).

This is deliberately separate from Yggdrasil. The ontology holds action and
constraint VOCABULARY; the control surface holds the per-agent BINDING that selects
from that vocabulary (D20, `ONTOLOGY_CONSTRUCTION.md` 2.3). Which actions an agent
may perform, which constraints bind it and its trust ceiling are per-agent and do
not belong in the type tree. Keeping them here, in the same package but a distinct
module, makes the ontology-versus-control-surface line physical.

Two orthogonal axes (D21): by-domain lives in the ontology, by-agent lives here. An
agent spans domains; a domain is touched by many agents. This module is per-agent.

Phase 1 grants no consequential capability: the action-critical set is empty and
the machinery is dormant (`ONTOLOGY_CONSTRUCTION.md` 4.1). The point of building it
now is the attach discipline: the schema to declare and gate consequential actions
exists and is exercised by tests (which supply their own agent contexts with their
own sinks, agent-scoped per D24), so arming it later is a config change, not a
build. An agent can never grant itself a permission above its trust ceiling.

Action-critical status is agent-scoped (D24): a value is action-critical for an
agent iff it can reach a sink in THAT agent's reachable sink set. So the sinks live
on the agent context, not globally. The loaded ontology ships no armed sinks; a
test or a later phase supplies them per agent.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .spine.trust import TRUST_ORDER


@dataclass(frozen=True)
class AgentContext:
    """One agent's control-surface binding.

    `permitted_actions` are action-type names (from the ontology's action
    vocabulary) this agent may perform. `trust_ceiling` is the highest trust level
    this agent may assign or hold; it can never exceed it. `consequential_sinks` are
    the sink node names that are consequential FOR THIS AGENT: the target set
    flow-to-sink reachability propagates back from (D24). An empty set is the Phase 1
    default, and means nothing is action-critical for this agent.
    """

    agent_id: str
    permitted_actions: frozenset[str] = frozenset()
    trust_ceiling: str = "TAINTED"
    consequential_sinks: frozenset[str] = frozenset()

    def may_perform(self, action_name: str) -> bool:
        return action_name in self.permitted_actions


# The global default control surface (HEIMDALL.md design principle 5). Agent-level
# overrides take precedence for that agent only, bounded by the agent's trust
# ceiling. The Phase 1 default grants only the read-only, human-gated actions and no
# consequential sinks: the action-critical set is empty.
GLOBAL_DEFAULT = AgentContext(
    agent_id="__global_default__",
    permitted_actions=frozenset(
        {"action:classify", "action:triage", "action:summarise", "action:draft_for_review"}
    ),
    trust_ceiling="TAINTED",
    consequential_sinks=frozenset(),
)


def _trust_rank(level: str) -> int:
    """Rank a `trust_ceiling` string against the trust lattice ordering (`TRUST_ORDER`,
    `spine/trust.py`), low to high. This is the ONLY ordering defined anywhere in the
    codebase today, and `trust_ceiling` values already use its literal names
    ("TAINTED" and so on), so this fix uses it without resolving the separate, still-open
    question of whether `AgentContext.trust_ceiling` should instead draw from a distinct
    agent-authority scale (recorded as an open question elsewhere, not decided here; see
    D97's note). An unrecognised level is not on the lattice at all, so it cannot be
    ranked as low: it is treated as maximally escalated, fail closed, so a string this
    module cannot place never earns a bypass by being unrankable."""
    try:
        return TRUST_ORDER.index(level)
    except ValueError:
        return len(TRUST_ORDER)


def resolve(agent: AgentContext | None) -> AgentContext:
    """Resolve the effective control surface for an agent: the global default unless
    an agent-level override is supplied. An override may not raise the trust ceiling
    above the global default's in Phase 1 (an agent cannot grant itself a permission
    above its ceiling); we enforce the ceiling is not silently escalated (D97: this
    enforcement was previously undocumented in name only, `resolve` returned `agent`
    unmodified and performed no check at all).

    Fails closed: an override whose `trust_ceiling` ranks ABOVE the global default's is
    refused, not silently honoured. Refusal here means CLAMPING the effective ceiling
    down to the global default's, not raising, so a caller that already validated
    everything else about the agent still gets a usable context back, one that can no
    longer exceed what the docstring already promised. An override at or below the
    global default's ceiling passes through untouched: this must never be friction on a
    legitimately-scoped agent narrowing itself.

    This closes the CEILING check only. It does not attest the `AgentContext` object
    itself (who constructed it, whether it was tampered with in transit): that is a
    materially larger change, named as a follow-on in D97 rather than built here."""
    if agent is None:
        return GLOBAL_DEFAULT
    if _trust_rank(agent.trust_ceiling) > _trust_rank(GLOBAL_DEFAULT.trust_ceiling):
        return replace(agent, trust_ceiling=GLOBAL_DEFAULT.trust_ceiling)
    return agent
