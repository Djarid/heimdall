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
    register_classification_rule,
    register_high_risk_types,
    text_of,
)
from . import priorities


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
    return bool(_CALENDAR.search(text_of(a)))


def register_rules() -> None:
    # High-risk: a scheduled task that will run. In the HIGH_RISK band.
    register_classification_rule(
        ClassificationRule("scheduled_task", "sched:scheduled_task", _is_scheduled_task),
        priorities.HIGH_RISK,
    )
    # Domain-specific low-risk catch: a calendar entry. In the DOMAIN_SPECIFIC band,
    # so it runs after all high-risk rules but before any catch-all.
    register_classification_rule(
        ClassificationRule("calendar_entry", "sched:calendar_entry", _is_calendar_entry),
        priorities.DOMAIN_SPECIFIC,
    )
    register_high_risk_types("sched:scheduled_task")
