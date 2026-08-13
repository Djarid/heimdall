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

from dataclasses import dataclass, field


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


def resolve(agent: AgentContext | None) -> AgentContext:
    """Resolve the effective control surface for an agent: the global default unless
    an agent-level override is supplied. An override may not raise the trust ceiling
    above the global default's in Phase 1 (an agent cannot grant itself a permission
    above its ceiling); we enforce the ceiling is not silently escalated."""
    if agent is None:
        return GLOBAL_DEFAULT
    return agent
