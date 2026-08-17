"""Two-dimensional classification: a speech-act type plus a separate consequence axis.

The structural defect this fixes. Nornir's classification collapses two orthogonal questions
into ONE label:

  - the SPEECH ACT: does this content tell, or ask? (informational statement, request)
  - the SUBJECT MATTER: what is it about? (a payment, an access grant, a newsletter)

and the speech act wins the tier contest. "For your information, the standing order goes out
on the usual date" earns `comms:informational_statement`, an INERT type, because the speech
act is genuinely informational. The fact that the subject is a payment is then DISCARDED: it
is nowhere in the outcome, so nothing downstream can act on it. That is the mechanism of the
false-inert break (D67, measured at about 43 percent in D77), stated structurally rather than
as a vocabulary problem.

What this module changes, and why it is a real fix rather than another content pattern. It
keeps the speech-act type exactly as Nornir produces it, and records consequence on a SECOND,
independent axis that the inert type CANNOT SUPPRESS. The rule for effective inertness becomes
a conjunction over both axes: a value is inert IN EFFECT only if its speech act is inert AND
its consequence axis is empty. So no inert signal can ever erase a co-present consequence
signal again. That property holds regardless of how good any particular consequence detector
is, which is the point: the defect being fixed is the OVERRIDE, not the detector.

Where consequence signals come from. The axis is a collection point, deliberately open to
several sources of differing strength:

  - STRUCTURAL (strong, not content-derived, an attacker cannot phrase around it): a
    state-delta on a declared consequential slot (`state_delta.py`, D79); a flow edge to a
    declared consequential sink; an action-critical reachability result.
  - CONTENT (weak, and honestly treadmill-vulnerable per invariant 3.5): a recognised
    consequential subject in the extracted text.

The content-derived signals are the weakest members and are marked as such. They are worth
having because a weak signal on an axis that cannot be suppressed is strictly better than the
current arrangement, where a co-present consequence signal is discarded entirely. But they are
NOT the fix, and this module does not claim they are: the fix is the removal of the override,
and the strong signals are the structural ones.

Fail-closed direction: a consequence signal can only ever DENY effective inertness. An empty
axis does not GRANT inertness by itself, because the speech-act term still has to be an inert
type earned by the existing positive-signal discipline (`earns_inert`). So this composes with
what is already there and can only add caution.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class SignalStrength(Enum):
    """How much the source of a consequence signal can be trusted not to be evadable.

    STRUCTURAL signals derive from declarations and state, which an attacker does not author,
    so they are not evadable by rephrasing. CONTENT signals derive from the untrusted text and
    are evadable by rephrasing (invariant 3.5); they are recorded as weak on purpose, so a
    reader of an audit trail can see which kind of evidence denied inertness."""

    STRUCTURAL = "structural"
    CONTENT = "content"


@dataclass(frozen=True)
class ConsequenceSignal:
    """One reason to believe this value concerns something with an effect. `source` names the
    mechanism that produced it (for example `state_delta`, `flow_to_sink`, `subject_match`),
    `detail` is the audit string, and `strength` records whether it is evadable."""

    source: str
    detail: str
    strength: SignalStrength = SignalStrength.CONTENT


@dataclass
class ConsequenceAxis:
    """The second dimension. A collection of signals from any source, which the speech-act
    type cannot suppress."""

    signals: list[ConsequenceSignal] = field(default_factory=list)

    def add(self, signal: ConsequenceSignal) -> None:
        self.signals.append(signal)

    @property
    def occupied(self) -> bool:
        return bool(self.signals)

    @property
    def structural(self) -> list[ConsequenceSignal]:
        return [s for s in self.signals if s.strength is SignalStrength.STRUCTURAL]

    @property
    def has_structural(self) -> bool:
        return bool(self.structural)

    def reasons(self) -> list[str]:
        return [f"{s.source}: {s.detail}" for s in self.signals]


@dataclass
class TwoDimensionalOutcome:
    """A classification on both axes.

    `speech_act_type` is the type Nornir already produces, unchanged. `speech_act_is_inert`
    records whether that type is one of the ontology's inert types. `consequence` is the
    second axis. `effective_inert` is the conjunction that replaces the single-label
    judgement, and it is the only thing downstream should read when deciding whether a value
    may be treated as inert."""

    speech_act_type: str
    speech_act_is_inert: bool
    consequence: ConsequenceAxis = field(default_factory=ConsequenceAxis)

    @property
    def effective_inert(self) -> bool:
        """Inert IN EFFECT only if the speech act is inert AND nothing occupies the
        consequence axis. This is where the override is removed: an inert speech act is no
        longer sufficient on its own."""
        return self.speech_act_is_inert and not self.consequence.occupied

    @property
    def suppressed_consequence(self) -> bool:
        """True when the OLD single-label design would have typed this inert while a
        consequence signal was present, that is exactly a false-inert the collapse would have
        produced. Reported so the harness can measure how many cases the two-dimensional
        model rescues."""
        return self.speech_act_is_inert and self.consequence.occupied

    def disposition(self) -> str:
        """The routing decision, for the audit trail."""
        if self.effective_inert:
            return "inert"
        if self.speech_act_is_inert and self.consequence.has_structural:
            return "gate: inert speech act with a structural consequence signal"
        if self.speech_act_is_inert:
            return "review: inert speech act with a content consequence signal"
        return "not inert by speech act; existing high-risk or review path applies"


def classify_two_dimensional(
    speech_act_type: str,
    speech_act_is_inert: bool,
    signals: "list[ConsequenceSignal] | None" = None,
) -> TwoDimensionalOutcome:
    """Compose a Nornir speech-act classification with a consequence axis."""
    axis = ConsequenceAxis(signals=list(signals or []))
    return TwoDimensionalOutcome(
        speech_act_type=speech_act_type,
        speech_act_is_inert=speech_act_is_inert,
        consequence=axis,
    )


# Convenience constructors for the signal sources that exist today, so callers do not hand-roll
# the strength and mislabel a structural signal as content or vice versa.


def state_delta_signal(detail: str) -> ConsequenceSignal:
    """A state-delta on a declared consequential slot (D79). Structural: derived from the slot
    declaration and stored state, not from the untrusted text, so it is not evadable by
    rephrasing."""
    return ConsequenceSignal(
        source="state_delta", detail=detail, strength=SignalStrength.STRUCTURAL
    )


def flow_to_sink_signal(detail: str) -> ConsequenceSignal:
    """The value can reach a declared consequential sink (the action-critical determination).
    Structural: graph reachability over declared flow edges."""
    return ConsequenceSignal(
        source="flow_to_sink", detail=detail, strength=SignalStrength.STRUCTURAL
    )


def subject_match_signal(detail: str) -> ConsequenceSignal:
    """A consequential subject recognised in the extracted text. CONTENT-derived, therefore
    weak and evadable by rephrasing (invariant 3.5). Recorded as weak on purpose."""
    return ConsequenceSignal(
        source="subject_match", detail=detail, strength=SignalStrength.CONTENT
    )
