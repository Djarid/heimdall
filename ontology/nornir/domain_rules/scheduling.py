"""Scheduling-domain classification rules. A sibling of communications (D29).

Adding this module and its line in `register_all` is the whole of the scheduling
domain on the rules side. It edits no other domain's rules and no shared rule
function; it only registers its own. That is the attach test for rules.

The predicates are broad and err toward the higher-risk type, the same discipline as
communications (D48): a scheduled_task (something that will run) beats the low-risk
calendar_entry, so a task that stages an action is not typed as an inert calendar
note. The high-risk band ensures a scheduled_task also beats another domain's
catch-all.
"""

from __future__ import annotations

import re

from ..assertions import MarshalledAssertion
from ..rules import (
    ClassificationRule,
    RiskTier,
    carries_imperative_or_consequence,
    register_classification_rule,
    register_high_risk_types,
    text_of,
)


# A scheduled TASK: something that will cause an action to run at a time. High-risk.
_TASK = re.compile(
    r"\b(task|job|cron|schedule[ds]? (a|the|to)|automation|trigger|run at|"
    r"at \d{1,2}(:\d{2})?\s?(am|pm)?|every (day|week|hour|morning|night)|"
    r"deploy|batch|pipeline run|workflow)\b"
)
# A calendar-type item: a meeting, reminder, deadline. Low-risk.
_CALENDAR = re.compile(
    r"\b(meeting|meet|call|invite|invitation|calendar|appointment|reminder|"
    r"deadline|due (date|on)|rsvp|agenda|reschedul|availability)\b"
)


def _is_scheduled_task(a: MarshalledAssertion) -> bool:
    return bool(_TASK.search(text_of(a)))


def _is_calendar_entry(a: MarshalledAssertion) -> bool:
    # Inert only if it looks like a calendar item AND carries no imperative or
    # consequence signal (D69). A "reminder" that also says "add the new starter to
    # the important-buttons room" is not an inert calendar entry; it falls through to
    # the fail-closed default. This applies the same discipline the communications
    # inert rule always had, which the false-inert measurement (D67) found missing here.
    return bool(_CALENDAR.search(text_of(a))) and not carries_imperative_or_consequence(a)


def register_rules() -> None:
    # High-risk: a scheduled task that will run. Risk tier HIGH, and specificity 2:
    # HIGHER than the communications instruction rule (specificity 0), because a
    # scheduling signal (cron, scheduled to, run at 2am, every night) is a narrower,
    # stronger indicator than a bare action verb. Under the D31 principle this means a
    # genuine scheduled task wins the tier over the broad comms instruction rule,
    # resolving the D51 masking: the task is typed as sched:scheduled_task, not
    # comms:instruction_to_act. Where the text is genuinely ambiguous and BOTH match
    # at the same specificity, the tie routes to review; that cannot happen here
    # because the specificities differ, which is the point of ranking them.
    register_classification_rule(
        ClassificationRule("scheduled_task", "sched:scheduled_task", _is_scheduled_task,
                           risk_tier=RiskTier.HIGH, specificity=2)
    )
    # Domain-specific low-risk catch: a calendar entry. Inert tier.
    register_classification_rule(
        ClassificationRule("calendar_entry", "sched:calendar_entry", _is_calendar_entry,
                           risk_tier=RiskTier.INERT, specificity=1)
    )
    register_high_risk_types("sched:scheduled_task")
