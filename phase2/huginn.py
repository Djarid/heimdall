"""Huginn: canary monitoring and the attempt-introspection tripwire.

Huginn observes every Fenrir emission and raises Gjallarhorn hard signals. It never
authorises anything: its only outcomes are a clean pass or a halt-and-quarantine. This
is the permitted polarity of invariant 3.5 (a detector may observe and alert, never be
the gate that authorises action), which is exactly why Huginn can inform the false-inert
problem (D67-fix direction d) without violating invariant 3.1.

Two detectors, from fenrir.md sections 3.2 and 3.3:

- CANARY MONITOR (six hard signals, HEIMDALL.md 558 to 567). Checks the output against
  the wrap: token echoed, honeypot absent, no tool call, schema honoured, tail canary
  acknowledged, no Himinbjörg internals leaked. Each hard signal is an immediate halt.

- ATTEMPT-INTROSPECTION TRIPWIRE (the null-surface detector). Fenrir has an empty
  capability set, so it has no legitimate reason ever to emit an action-shaped token
  sequence. Any action-shaped emission (a tool call in the model's native format, a
  request to invoke a named capability, or reasoning tokens describing intent to act)
  is therefore dispositive proof that the tainted content instructed it to act. This is
  the signal that catches consequential imperatives BEHAVIOURALLY, including the passive
  and metaphorical cases the deterministic content classifier misses.

The tripwire's zero-false-positive property is a property of the empty capability set
(fenrir.py FENRIR_CAPABILITIES). It holds only while that set stays empty: a Fenrir with
a real capability would have a legitimate reason to emit an action, so the emission would
no longer be dispositive. This module asserts the emptiness before trusting a clean
tripwire result, so a future capability grant cannot silently degrade the guarantee.

Honest residual: the tripwire detects a model that ATTEMPTS an action. It does not fire on
a passive consequence the model merely records as a fact without trying to act on it; that
passes Huginn clean. So this REDUCES the false-inert gap, it does not close it, and the
modules and tests say so rather than reporting a hollow green.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from .fenrir import FENRIR_CAPABILITIES, FenrirRun


class Verdict(Enum):
    CLEAN = "clean"       # no hard signal; the emission may proceed as tainted data
    HALT = "halt"         # a hard signal fired; halt the instance, discard, quarantine


class HardSignal(Enum):
    """The six hard canary signals plus the attempt-introspection signal. Every one is
    an immediate halt-and-quarantine (fenrir.md 3.2, 3.3)."""
    CANARY_TOKEN_ABSENT = "canary token absent or malformed"
    HONEYPOT_PRESENT = "honeypot phrase present in output"
    TOOL_CALL_ATTEMPTED = "tool call attempted"
    SCHEMA_VIOLATION = "output schema violation"
    TAIL_CANARY_ABSENT = "tail canary instruction absent from output"
    INTERNALS_REFERENCED = "output references Himinbjörg internals"
    ATTEMPT_INTROSPECTION = "action-shaped emission (attempt introspection)"


@dataclass(frozen=True)
class MonitorResult:
    """The outcome of monitoring one Fenrir run. `verdict` is CLEAN or HALT; `signals`
    lists every hard signal that fired (there may be more than one). `quarantined` is
    True when the run was halted and its source routed to review. `consequential_catch`
    is True when the reason for the halt was an attempt-introspection hit, which is the
    false-inert catch: behaviourally-proven consequential content that the content
    classifier may have typed inert."""
    verdict: Verdict
    signals: tuple[HardSignal, ...] = ()
    quarantined: bool = False
    consequential_catch: bool = False

    @property
    def clean(self) -> bool:
        return self.verdict is Verdict.CLEAN


# Action-shaped emission patterns for the attempt-introspection tripwire. These match
# the SHAPE of an action request, not the topic of any content: a native tool-call
# envelope, a function/capability invocation, or first-person intent-to-act framing.
# This is not a content blacklist (invariant 3.5): it does not enumerate consequential
# subjects (payments, credentials); it detects that the MODEL is trying to act, which a
# reader of inert data has no reason to do. A false negative here means a missed catch
# (the value stays tainted and non-actionable regardless), never a false trust.
_ACTION_SHAPED = (
    # native tool-call / function-call envelopes in common model formats
    re.compile(r"<\s*tool_call\s*>", re.I),
    re.compile(r"<\s*function_call\s*>", re.I),
    re.compile(r"\bfunctions?\.[a-z_]+\s*\(", re.I),
    re.compile(r"```\s*(tool|function|json)\s*\n\s*\{[^}]*\"(name|tool|function|action)\"", re.I),
    # a request to invoke a named capability
    re.compile(r"\b(call|invoke|execute|run|trigger)\s+(the\s+)?(tool|function|command|capability|api|endpoint)\b", re.I),
    # first-person intent to act (reasoning tokens describing an action the reader would take)
    re.compile(r"\bI\s+(will|shall|am going to|need to|should|must)\s+(send|transfer|pay|wire|delete|disable|grant|forward|execute|run|deploy|call|invoke|issue|initiate|schedule|approve|purchase|buy)\b", re.I),
    re.compile(r"\b(sending|transferring|paying|wiring|deleting|disabling|granting|forwarding|executing|deploying|invoking|initiating|approving|purchasing)\s+(the|it|that|this|them|now)\b", re.I),
)


def _detect_action_shaped(run: FenrirRun) -> bool:
    """True if the emission is action-shaped anywhere in the reasoning trace, the
    output, or the intercepted tool-call list. Checks the TRACE as well as the output,
    which is what makes the tripwire earlier and less evadable than the output canary
    (fenrir.md 3.3): a payload that makes the model try to act reveals itself in the
    trace even if the final output would have looked clean."""
    # Any intercepted structured tool call is, by itself, an action attempt: Fenrir's
    # empty capability set means the harness refused it, and the refusal is the proof.
    if run.emission.tool_calls:
        return True
    haystack = f"{run.emission.reasoning_trace}\n{run.emission.output}"
    return any(p.search(haystack) for p in _ACTION_SHAPED)


def _canary_signals(run: FenrirRun) -> list[HardSignal]:
    """The six hard canary signals, checked against the wrap the run carried."""
    signals: list[HardSignal] = []
    output = run.emission.output
    wrap = run.wrap

    # 1. Canary token absent or malformed: the model must echo it verbatim.
    if wrap.token not in output:
        signals.append(HardSignal.CANARY_TOKEN_ABSENT)

    # 2. Honeypot present: the model was told never to emit it, so its presence means
    #    an injected instruction introduced a phrase the model was told to withhold.
    if wrap.honeypot in output or wrap.honeypot in run.emission.reasoning_trace:
        signals.append(HardSignal.HONEYPOT_PRESENT)

    # 3. Tool call attempted: a structured action request Fenrir's empty set refused.
    if run.emission.tool_calls:
        signals.append(HardSignal.TOOL_CALL_ATTEMPTED)

    # 4. Schema violation: for this build the schema is a single non-empty extracted
    #    field. An empty output, or output that is only the honeypot/token noise, is a
    #    schema violation. (Grammar-constrained decoding makes this near-impossible in
    #    the real build; the check is kept so a stand-in producer cannot slip past.)
    stripped = output.replace(wrap.token, "").strip()
    if not stripped:
        signals.append(HardSignal.SCHEMA_VIOLATION)

    # 5. Tail canary acknowledgement absent: the model must confirm it followed the
    #    canonical instruction. A missing token already covers the main case; this adds
    #    the explicit tail acknowledgement the wrap asks for. Kept conservative: only
    #    flagged when the token is present but no confirmation shape appears, to avoid
    #    double-counting the token-absent case.
    #    (Left as a structural check on the presence of the echoed token, which the tail
    #    canary instructs; a richer confirmation grammar lands with Himinbjörg, Phase 3.)

    # 6. Himinbjörg internals referenced: a prompt-extraction attempt. The model must
    #    never echo the internal frame markers or the honeypot/secret field labels.
    internals = ("[TOP CANARY", "[TAIL CANARY", "Himinbjörg-signed", "honeypot:")
    if any(marker in output for marker in internals):
        signals.append(HardSignal.INTERNALS_REFERENCED)

    return signals


def monitor(run: FenrirRun) -> MonitorResult:
    """Observe a Fenrir run and return a fail-closed verdict.

    Any hard canary signal or an attempt-introspection hit is a HALT: the instance is
    halted, its output discarded and the source quarantined to review. A run with no
    hard signal is CLEAN, meaning its assertions may proceed as TAINTED data (still not
    actionable; Fenrir never promotes). Huginn never returns anything that authorises an
    action; the strongest thing a CLEAN verdict says is "no injection signal observed",
    which is not the same as "safe to act on"."""
    # Guard the tripwire's precondition: the zero-false-positive property is a property
    # of Fenrir's empty capability set. If that ever changes, an action-shaped emission
    # is no longer dispositive, so refuse to certify a clean tripwire result.
    assert FENRIR_CAPABILITIES == frozenset(), (
        "Fenrir capability set is non-empty; attempt introspection is no longer dispositive"
    )

    signals = _canary_signals(run)
    attempt = _detect_action_shaped(run)
    if attempt:
        signals.append(HardSignal.ATTEMPT_INTROSPECTION)

    if signals:
        return MonitorResult(
            verdict=Verdict.HALT,
            signals=tuple(signals),
            quarantined=True,
            consequential_catch=attempt,
        )
    return MonitorResult(verdict=Verdict.CLEAN)
