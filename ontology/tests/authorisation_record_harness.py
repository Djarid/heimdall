"""Test harness for D103's shared attested-record substrate (REQ-1 to REQ-7).

Run from the repo root:

    python -m ontology.tests.authorisation_record_harness

What this substrate is, and why it is not a second copy of D94. `ontology/nornir/
sink_attestation.py` (D94, direction C) attests WHO declared a sink and that a
declaration has not been altered since. This module extends exactly that pattern to
ANY authorisation-path record, generically, by reading only two methods
(`record_type()`, `canonical_fields()`) and two attributes (`authoriser`,
`attestation`) off a record, so the same verifier can attest an `AgentContext`
binding (this build's own record type) and, later, the attendance spec's four
reserved record types, without a second trusted-authoriser type or a second
constant-time comparison (C-b, REQ-1, REQ-4).

Why this harness uses ITS OWN synthetic record types rather than `AgentContext`.
Per the spec's section 10.2 build order, this harness (and the substrate it tests)
lands BEFORE `AgentContext` gains its `record_type()`/`canonical_fields()`/
`authoriser`/`attestation` additions. Testing the substrate against a record type it
does not yet know about would entangle two separate decisions' failures into one
harness. So this file defines `_AgentLikeRecord`, a record shaped exactly like
`AgentContext`'s future attested content (agent_id, permitted_actions,
trust_ceiling, consequential_sinks, authoriser), and a `_SyntheticSecondTypeRecord`
whose non-tag fields are DELIBERATELY IDENTICAL to it, so obligation five's cross-
type control proves the record-type TAG is what separates them, not an incidental
field difference (REQ-3, D101's synthetic-ontology negative-control precedent).

The seven obligations (REQ-22), each traced to its requirement:

  1. MANDATORY CONTROL: an honest attested record verifies, with no friction (AC-1).
  2. A record altered after attestation is REFUSED, independently for each covered
     field (AC-2, AC-10's five sub-checks, restated generically here).
  3. An unknown or forged authoriser is REFUSED (AC-3).
  4. An unattested record is REFUSED in all three shapes: no authoriser, no digest,
     neither (AC-4).
  5. Cross-type replay is REFUSED in both directions, via the contrived-identical
     synthetic second type (AC-5).
  6. Cross-substrate replay is REFUSED in both directions against D94's own
     `sink_attestation.verify_attestation`, under the SAME authoriser and secret
     (AC-6, REQ-5).
  7. Determinism and non-mutation (AC-7); and no second trust primitive, no early
     exit, no new import root (AC-8, REQ-1, REQ-4).

This module imports from `ontology.nornir.authorisation_record`, which DOES NOT
EXIST YET at the time this harness is written (TDD). Running this file before that
module lands is EXPECTED to fail at import time; that failure, tracing to the
missing substrate rather than to a bug in this harness, is itself evidence the test
was written against the contract and not against an assumed implementation.
"""

from __future__ import annotations

import inspect
from dataclasses import dataclass, field

from ..nornir.authorisation_record import (
    RECORD_TYPE_AGENT_CONTEXT,
    RECORD_TYPE_ATTENDANCE,
    RECORD_TYPE_STANDING_GRANT,
    RECORD_TYPE_GATE_POLICY,
    RECORD_TYPE_PROMOTION,
    canonical_record_bytes,
    compute_record_attestation,
    verify_record_attestation,
)
from ..nornir.sink_attestation import (
    TrustedAuthoriser,
    TrustedAuthoriserSet,
    compute_attestation as sink_compute_attestation,
    verify_attestation as sink_verify_attestation,
)
from ..nornir.sink_declaration import SinkDeclaration, MOVE_MONEY
from ..nornir import symbolic_guard


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failures = 0

    def line(self, s: str = "") -> None:
        self.lines.append(s)

    def check(self, ok: bool, label: str) -> None:
        if ok:
            self.line(f"  [PASS] {label}")
        else:
            self.failures += 1
            self.line(f"  [FAIL] {label}")

    def dump(self) -> None:
        print("\n".join(self.lines))


PLATFORM_SECRET = b"authorisation-record-platform-secret-not-in-any-record"
TRUSTED_AUTHORISER_ID = "ops-authoriser"


def build_trusted() -> TrustedAuthoriserSet:
    t = TrustedAuthoriserSet()
    t.trust(TrustedAuthoriser(authoriser_id=TRUSTED_AUTHORISER_ID, secret=PLATFORM_SECRET))
    return t


@dataclass(frozen=True)
class _AgentLikeRecord:
    """A minimal stand-in for `AgentContext`'s future attested-record shape (REQ-9's
    field selection), defined HERE so this harness can prove the SUBSTRATE's own
    obligations independently of any edit to `control_surface.py`. Implements the
    narrow interface the substrate reads (`record_type()`, `canonical_fields()`) and
    nothing else."""

    agent_id: str
    permitted_actions: frozenset[str] = frozenset()
    trust_ceiling: str = "TAINTED"
    consequential_sinks: frozenset[str] = frozenset()
    authoriser: "str | None" = None
    attestation: "str | None" = None

    def record_type(self) -> str:
        return RECORD_TYPE_AGENT_CONTEXT

    def canonical_fields(self) -> tuple:
        return (
            ("agent_id", self.agent_id),
            ("permitted_actions", ",".join(sorted(self.permitted_actions))),
            ("trust_ceiling", self.trust_ceiling),
            ("consequential_sinks", ",".join(sorted(self.consequential_sinks))),
            ("authoriser", self.authoriser or ""),
        )


@dataclass(frozen=True)
class _SyntheticSecondTypeRecord:
    """A synthetic second record type (REQ-3, AC-5), CONTRIVED so its
    `canonical_fields()` tuple is identical to `_AgentLikeRecord`'s for the same
    field values, and whose `record_type()` differs. A pass on the cross-type
    control below, using this type, proves the record-type TAG (not an incidental
    field difference) is what the digest depends on."""

    agent_id: str
    permitted_actions: frozenset[str] = frozenset()
    trust_ceiling: str = "TAINTED"
    consequential_sinks: frozenset[str] = frozenset()
    authoriser: "str | None" = None
    attestation: "str | None" = None

    def record_type(self) -> str:
        return RECORD_TYPE_ATTENDANCE

    def canonical_fields(self) -> tuple:
        return (
            ("agent_id", self.agent_id),
            ("permitted_actions", ",".join(sorted(self.permitted_actions))),
            ("trust_ceiling", self.trust_ceiling),
            ("consequential_sinks", ",".join(sorted(self.consequential_sinks))),
            ("authoriser", self.authoriser or ""),
        )


def _attested(record_cls, secret: bytes = PLATFORM_SECRET,
              authoriser: "str | None" = TRUSTED_AUTHORISER_ID, **overrides):
    """Build an instance of `record_cls` and attach a real attestation computed
    under `secret`. Records are frozen, so the honest pipeline this models is:
    build the draft, compute the digest, rebuild with the digest set."""
    fields = dict(
        agent_id="treasury",
        permitted_actions=frozenset({"action:classify"}),
        trust_ceiling="TAINTED",
        consequential_sinks=frozenset({"sink:payments.execute"}),
    )
    fields.update(overrides)
    draft = record_cls(authoriser=authoriser, **fields)
    digest = compute_record_attestation(draft, secret)
    return record_cls(attestation=digest, authoriser=authoriser, **fields)


def test_honest_record_verifies_no_friction(rep: Report) -> None:
    """AC-1. MANDATORY CONTROL. A substrate that refuses an honest record is
    friction without safety and fails here before any refusal criterion is
    credited."""
    rep.line("=== 1. MANDATORY CONTROL: an honest attested record verifies, no friction ===")
    trusted = build_trusted()
    rec = _attested(_AgentLikeRecord)
    res = verify_record_attestation(rec, trusted)
    rep.check(res.verified, "a record honestly attested by a trusted authoriser verifies")
    rep.check(res.reason == "", "and the reason is empty on a clean verify")
    rep.line()


def test_altered_field_refused(rep: Report) -> None:
    """AC-2 / AC-10 restated generically. Each covered field, altered independently
    with the ORIGINAL (now-stale) digest retained, must break verification. Five
    sub-checks, one per covered field."""
    rep.line("=== 2. A record altered after attestation is REFUSED, per covered field ===")
    trusted = build_trusted()
    honest = _attested(_AgentLikeRecord)

    def _tamper(**overrides) -> _AgentLikeRecord:
        fields = dict(
            agent_id=honest.agent_id,
            permitted_actions=honest.permitted_actions,
            trust_ceiling=honest.trust_ceiling,
            consequential_sinks=honest.consequential_sinks,
            authoriser=honest.authoriser,
            attestation=honest.attestation,  # the STALE digest, deliberately retained
        )
        fields.update(overrides)
        return _AgentLikeRecord(**fields)

    cases = [
        ("agent_id", _tamper(agent_id="attacker")),
        ("permitted_actions", _tamper(permitted_actions=frozenset({"action:admin"}))),
        ("trust_ceiling", _tamper(trust_ceiling="CANONICAL")),
        ("consequential_sinks", _tamper(consequential_sinks=frozenset())),
        ("authoriser", _tamper(authoriser="someone-else")),
    ]
    for field_name, tampered in cases:
        res = verify_record_attestation(tampered, trusted)
        rep.check(not res.verified, f"altering {field_name!r} after attestation is refused")
    rep.line()


def test_unknown_authoriser_refused(rep: Report) -> None:
    """AC-3. Refused because the authoriser is UNTRUSTED, not because the digest
    happens to mismatch: the reason must name the untrusted authoriser."""
    rep.line("=== 3. An unknown or forged authoriser is REFUSED ===")
    trusted = build_trusted()
    rogue = _attested(_AgentLikeRecord, secret=b"rogue-secret", authoriser="attacker")
    res = verify_record_attestation(rogue, trusted)
    rep.check(not res.verified, "an attestation from an untrusted authoriser does not verify")
    rep.check(
        "not in the trusted" in res.reason or "unknown" in res.reason.lower()
        or "untrusted" in res.reason.lower(),
        "and the reason names the untrusted authoriser, not a digest mismatch",
    )
    rep.line()


def test_unattested_refused_three_shapes(rep: Report) -> None:
    """AC-4. Silence never earns trust: no authoriser, no digest, or neither must
    all be REFUSED on the unattested path."""
    rep.line("=== 4. An unattested record is REFUSED, in all three shapes ===")
    trusted = build_trusted()
    base = dict(
        agent_id="treasury", permitted_actions=frozenset(), trust_ceiling="TAINTED",
        consequential_sinks=frozenset(),
    )
    no_authoriser = _AgentLikeRecord(**base, authoriser=None, attestation="deadbeef" * 8)
    no_digest = _AgentLikeRecord(**base, authoriser=TRUSTED_AUTHORISER_ID, attestation=None)
    neither = _AgentLikeRecord(**base, authoriser=None, attestation=None)
    for label, rec in (
        ("no authoriser", no_authoriser),
        ("no digest", no_digest),
        ("neither", neither),
    ):
        res = verify_record_attestation(rec, trusted)
        rep.check(not res.verified, f"a record with {label} is refused (unattested)")
    rep.line()


def test_cross_type_replay_refused(rep: Report) -> None:
    """AC-5. MANDATORY CONTROL for the tag. Because the two synthetic types' non-tag
    canonical fields are contrived identical, a pass here proves the record-type
    tag, not an incidental field difference, is what separates them. Checked in
    both directions."""
    rep.line("=== 5. MANDATORY CONTROL for the tag: cross-type replay REFUSED both ways ===")
    trusted = build_trusted()

    tags = {
        RECORD_TYPE_AGENT_CONTEXT,
        RECORD_TYPE_ATTENDANCE,
        RECORD_TYPE_STANDING_GRANT,
        RECORD_TYPE_GATE_POLICY,
        RECORD_TYPE_PROMOTION,
    }
    rep.check(len(tags) == 5, "all five reserved record-type tag constants are distinct (EC-16)")

    shared_fields = dict(
        agent_id="treasury",
        permitted_actions=frozenset({"action:classify"}),
        trust_ceiling="TAINTED",
        consequential_sinks=frozenset({"sink:x"}),
    )
    agent_rec = _attested(_AgentLikeRecord, **shared_fields)
    synth_rec = _attested(_SyntheticSecondTypeRecord, **shared_fields)

    rep.check(
        agent_rec.canonical_fields() == synth_rec.canonical_fields(),
        "the two synthetic record types' non-tag canonical fields are contrived "
        "IDENTICAL for these inputs (so a refusal below is provably the tag's doing)",
    )
    rep.check(
        agent_rec.record_type() != synth_rec.record_type(),
        "and their record_type() tags differ",
    )

    replayed_on_synth = _SyntheticSecondTypeRecord(
        agent_id=agent_rec.agent_id, permitted_actions=agent_rec.permitted_actions,
        trust_ceiling=agent_rec.trust_ceiling, consequential_sinks=agent_rec.consequential_sinks,
        authoriser=agent_rec.authoriser, attestation=agent_rec.attestation,
    )
    res_a = verify_record_attestation(replayed_on_synth, trusted)
    rep.check(
        not res_a.verified,
        "an AgentContext-tagged attestation does not verify when presented as the "
        "synthetic second type",
    )

    replayed_on_agent = _AgentLikeRecord(
        agent_id=synth_rec.agent_id, permitted_actions=synth_rec.permitted_actions,
        trust_ceiling=synth_rec.trust_ceiling, consequential_sinks=synth_rec.consequential_sinks,
        authoriser=synth_rec.authoriser, attestation=synth_rec.attestation,
    )
    res_b = verify_record_attestation(replayed_on_agent, trusted)
    rep.check(
        not res_b.verified,
        "and the synthetic type's attestation does not verify when presented as an "
        "AgentContext-shaped record (both directions refused)",
    )
    rep.line()


def test_cross_substrate_replay_refused(rep: Report) -> None:
    """AC-6, REQ-5. Cross-substrate separation must hold WITHOUT relying on the two
    records' fields happening to differ: same authoriser, same secret, both
    directions refused, against D94's own `sink_attestation.verify_attestation`."""
    rep.line(
        "=== 6. Cross-substrate replay REFUSED both ways (same authoriser, same secret) ==="
    )
    record_trusted = build_trusted()
    sink_trusted = TrustedAuthoriserSet()
    sink_trusted.trust(TrustedAuthoriser(authoriser_id=TRUSTED_AUTHORISER_ID, secret=PLATFORM_SECRET))

    agent_rec = _attested(_AgentLikeRecord)

    sink_decl = SinkDeclaration(
        name="sink:payments.execute", parameters=frozenset({"amount"}),
        consequential_by_default=True, effect_primitive=MOVE_MONEY,
        authoriser=TRUSTED_AUTHORISER_ID,
    )
    sink_digest = sink_compute_attestation(sink_decl, PLATFORM_SECRET)
    attested_sink_decl = SinkDeclaration(
        name=sink_decl.name, parameters=sink_decl.parameters,
        consequential_by_default=sink_decl.consequential_by_default,
        effect_primitive=sink_decl.effect_primitive, authoriser=sink_decl.authoriser,
        attestation=sink_digest,
    )

    # Direction 1: an AgentContext-record digest presented on a SinkDeclaration.
    replayed_sink = SinkDeclaration(
        name=attested_sink_decl.name, parameters=attested_sink_decl.parameters,
        consequential_by_default=attested_sink_decl.consequential_by_default,
        effect_primitive=attested_sink_decl.effect_primitive,
        authoriser=agent_rec.authoriser, attestation=agent_rec.attestation,
    )
    res1 = sink_verify_attestation(replayed_sink, sink_trusted)
    rep.check(
        not res1.verified,
        "an AgentContext-record attestation does not verify as a SinkDeclaration "
        "through D94's own verify_attestation, under the SAME authoriser and secret",
    )

    # Direction 2: a SinkDeclaration digest presented on the record substrate.
    replayed_record = _AgentLikeRecord(
        agent_id=agent_rec.agent_id, permitted_actions=agent_rec.permitted_actions,
        trust_ceiling=agent_rec.trust_ceiling, consequential_sinks=agent_rec.consequential_sinks,
        authoriser=attested_sink_decl.authoriser, attestation=attested_sink_decl.attestation,
    )
    res2 = verify_record_attestation(replayed_record, record_trusted)
    rep.check(
        not res2.verified,
        "and a SinkDeclaration attestation does not verify through this substrate's "
        "verify_record_attestation, under the SAME authoriser and secret",
    )
    rep.line()


def test_deterministic_and_non_mutating(rep: Report) -> None:
    """AC-7, REQ-6. Two records equal in content but built with frozensets in
    different insertion orders must encode identically; two calls over the same
    record must agree; and neither call may mutate the record."""
    rep.line("=== 7. Deterministic, and mutates nothing ===")
    a = _AgentLikeRecord(
        agent_id="treasury",
        permitted_actions=frozenset({"action:b", "action:a"}),
        trust_ceiling="TAINTED",
        consequential_sinks=frozenset({"sink:b", "sink:a"}),
        authoriser=TRUSTED_AUTHORISER_ID,
    )
    b = _AgentLikeRecord(
        agent_id="treasury",
        permitted_actions=frozenset({"action:a", "action:b"}),
        trust_ceiling="TAINTED",
        consequential_sinks=frozenset({"sink:a", "sink:b"}),
        authoriser=TRUSTED_AUTHORISER_ID,
    )
    bytes_a = canonical_record_bytes(a)
    bytes_b = canonical_record_bytes(b)
    rep.check(
        bytes_a == bytes_b,
        "canonical_record_bytes is identical for equal content built with different "
        "frozenset insertion orders",
    )

    digest1 = compute_record_attestation(a, PLATFORM_SECRET)
    digest2 = compute_record_attestation(a, PLATFORM_SECRET)
    rep.check(digest1 == digest2, "compute_record_attestation is deterministic on repeat calls")

    before = (
        a.agent_id, a.permitted_actions, a.trust_ceiling, a.consequential_sinks,
        a.authoriser, a.attestation,
    )
    canonical_record_bytes(a)
    compute_record_attestation(a, PLATFORM_SECRET)
    after = (
        a.agent_id, a.permitted_actions, a.trust_ceiling, a.consequential_sinks,
        a.authoriser, a.attestation,
    )
    rep.check(before == after, "neither call mutates the record")
    rep.line()


def test_no_second_primitive_no_new_root(rep: Report) -> None:
    """AC-8, REQ-1, REQ-4. No second `TrustedAuthoriser`/`TrustedAuthoriserSet`, no
    second constant-time comparison, and `ALLOWED_IMPORT_ROOTS` unchanged at 13
    roots (no new root added by this substrate)."""
    rep.line("=== 8. No second trust primitive, no early exit, no new import root ===")
    from ..nornir import authorisation_record as substrate
    from ..nornir.sink_attestation import _constant_time_equals

    source = inspect.getsource(substrate)
    rep.check(
        "class TrustedAuthoriser" not in source.replace("class TrustedAuthoriserSet", ""),
        "authorisation_record.py does not redefine TrustedAuthoriser",
    )
    rep.check(
        "class TrustedAuthoriserSet" not in source,
        "authorisation_record.py does not redefine TrustedAuthoriserSet",
    )
    rep.check(
        substrate.TrustedAuthoriser is TrustedAuthoriser,
        "and imports TrustedAuthoriser from .sink_attestation by identity",
    )
    rep.check(
        substrate.TrustedAuthoriserSet is TrustedAuthoriserSet,
        "and imports TrustedAuthoriserSet from .sink_attestation by identity",
    )
    rep.check(
        substrate._constant_time_equals is _constant_time_equals,
        "digest comparison delegates to sink_attestation._constant_time_equals, not "
        "a second comparison loop",
    )
    rep.check(
        len(symbolic_guard.ALLOWED_IMPORT_ROOTS) == 13,
        "ALLOWED_IMPORT_ROOTS is unchanged at 13 roots (no new root added)",
    )
    rep.line()


def main() -> int:
    rep = Report()
    rep.line("D103: the shared attested-record substrate (REQ-1 to REQ-7)")
    rep.line("Extends D94's authoriser-plus-keyed-digest pattern to a generic attested-record")
    rep.line("facility, reused (never duplicated) by any record type implementing")
    rep.line("record_type() and canonical_fields(). Occupies the attendance spec's harness slot")
    rep.line("for AC-8 and the REQ-2 refusal paths.")
    rep.line("")

    test_honest_record_verifies_no_friction(rep)
    test_altered_field_refused(rep)
    test_unknown_authoriser_refused(rep)
    test_unattested_refused_three_shapes(rep)
    test_cross_type_replay_refused(rep)
    test_cross_substrate_replay_refused(rep)
    test_deterministic_and_non_mutating(rep)
    test_no_second_primitive_no_new_root(rep)

    rep.dump()
    print()
    if rep.failures:
        print(f"SUITE FAIL: {rep.failures} failing check(s).")
        return 1
    print("SUITE PASS: an honest attested record verifies with no friction; a record altered")
    print("after attestation, an unknown/forged authoriser and an unattested record (in all")
    print("three shapes) are all REFUSED; cross-type replay is refused in both directions with")
    print("the tag proven load-bearing by a contrived-identical synthetic second type; cross-")
    print("substrate replay is refused in both directions against D94's own verifier under the")
    print("SAME authoriser and secret; and the substrate is deterministic, non-mutating, adds no")
    print("second trust primitive and no new import root (D103, REQ-1 to REQ-7).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
