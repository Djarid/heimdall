"""D103: the shared attested-record substrate, extending D94's authoriser-plus-
keyed-digest pattern to ANY authorisation-path record, generically.

Where this sits, and why it is not a second copy of D94. `sink_attestation.py`
(D94, direction C) attests WHO declared a sink and that a declaration has not
been altered since. That mechanism is specific to one record shape
(`SinkDeclaration`). This module extracts the SAME mechanism -- a keyed digest
over a record's canonical bytes, verified against a `TrustedAuthoriserSet` -- so
it can attest ANY record type without a second trusted-authoriser type or a
second constant-time comparison (C-b, REQ-1, REQ-4). It reads a record through
exactly two methods (`record_type() -> str`, `canonical_fields() -> tuple[tuple[
str, str], ...]`) and two attributes (`authoriser`, `attestation`), and imports
no record type -- specifically not `control_surface` (REQ-7) -- so the
dependency points one way: records depend on this module to be verified; this
module depends on no record.

This build's own record type is `AgentContext` (`RECORD_TYPE_AGENT_CONTEXT`).
Four further record-type tags are RESERVED here, as string constants only, for
`attendance-surface-and-gate-policy-spec.md`'s file 1 (`StandingGrant`,
`GatePolicy`, `PromotionRecord`): no class, field or machinery for any of them
is built in this module (REQ-3). This is deliberate, minimal namespace
reservation, so that spec's file 1 slots straight into this substrate rather
than defining a second one, and so it cannot later pick a colliding or
differently-spelled tag.

A fifth record-type tag, `RECORD_TYPE_COHORT_DEFINITION` (`cohort_definition`),
is RESERVED here on the same terms, for `vor-minimal-cohort-spec.md`'s cohort
definition: no class, field or machinery for it either is built in this
module (REQ-40).

Cross-type and cross-substrate separation (REQ-3, REQ-5). Every record's
canonical bytes are PREFIXED with its own record-type tag, so an attestation
computed for one record type does not verify when presented as another, in
either direction (cross-type replay). Separately, this substrate's domain
separator (`_RECORD_DOMAIN`) is distinct from `sink_attestation.compute_
attestation`'s own domain separator (the `b"\\x00"` byte it hashes between
content and key), so an `AgentContext` attestation cannot verify as a
`SinkDeclaration` attestation, or vice versa, even under the SAME authoriser
and the SAME secret (cross-substrate replay). The tag alone would not be
sufficient for cross-substrate separation if the two substrates ever
happened to compute over identical field sets; the distinct domain separator
is the second, independent barrier that removes that dependency.

The load-bearing honesty limit, restated here for this substrate (D94's own
limit, inherited verbatim). Attestation binds IDENTITY and INTEGRITY, never
HONESTY. A verified attestation proves "authoriser X produced this record and
it has not been altered since", NOT "what X attested is true of the world".
A trusted authoriser who honestly attests a record whose content is a lie
(for `AgentContext`, an emptied `consequential_sinks` set for an agent that is
not really read-only) produces a perfectly valid attestation of that lie.
Nothing in this module, or in any record type built on it, closes that gap;
only an independent honesty backstop (as D89-B/D93-D are for the sink
declaration) could, and none exists here for the agent binding (see D103's own
decision text and REQ-30 limit 2).

Not public-key non-repudiation (D94's own deployment residual, inherited
verbatim). Each record's digest is `hashlib` (stdlib SHA-256) over the
record's canonical bytes, its record-type tag, this substrate's domain
separator and a per-authoriser secret held only in a `TrustedAuthoriserSet`
loaded at startup. This is a keyed integrity check (HMAC-shaped): it proves
the holder of the shared secret produced the record, not a globally
verifiable signature. A real deployment would replace the shared secret with
an asymmetric key and the digest with a signature; that stays a deployment
requirement, exactly as D94 left it.

Invariant 3.1. This module imports only `__future__`, `dataclasses` and
`hashlib` (already allowlisted, D94), plus `.sink_attestation` (relative,
intra-package, exempt from the allowlist). No model, no network. `hashlib` is
a hashing primitive, not a model client or a network module, and reaches
neither.

Fail closed, never a blacklist (invariant 3.5, D54/D55). A record is trusted
only when it POSITIVELY verifies against a trusted authoriser and a matching
digest. Silence never earns trust: an unattested record (no authoriser, no
digest, or neither), an unknown or forged authoriser, or a digest that does
not match is REFUSED, not admitted with a warning or a default. Nothing here
enumerates forbidden authorisers, agent ids or sink names.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from .sink_attestation import (
    TrustedAuthoriser,
    TrustedAuthoriserSet,
    _constant_time_equals,
)

__all__ = [
    "RECORD_TYPE_AGENT_CONTEXT",
    "RECORD_TYPE_ATTENDANCE",
    "RECORD_TYPE_STANDING_GRANT",
    "RECORD_TYPE_GATE_POLICY",
    "RECORD_TYPE_PROMOTION",
    "RECORD_TYPE_COHORT_DEFINITION",
    "canonical_record_bytes",
    "compute_record_attestation",
    "verify_record_attestation",
    "RecordAttestationResult",
    "TrustedAuthoriser",
    "TrustedAuthoriserSet",
]

# This build's own record type (REQ-3).
RECORD_TYPE_AGENT_CONTEXT = "agent_context"

# Reserved namespace only (REQ-3). No record class, field or machinery for
# these four is built here; they belong to attendance-surface-and-gate-
# policy-spec.md's file 1, and they are spelled here, in the one module that
# already knows how to verify a record, so that spec cannot later pick a
# colliding or differently-spelled tag (EC-16, EC-22).
RECORD_TYPE_ATTENDANCE = "attendance_attestation"
RECORD_TYPE_STANDING_GRANT = "standing_grant"
RECORD_TYPE_GATE_POLICY = "gate_policy"
RECORD_TYPE_PROMOTION = "promotion_record"
RECORD_TYPE_COHORT_DEFINITION = "cohort_definition"

# Distinct from sink_attestation.compute_attestation's own domain separator
# (its b"\x00" byte between content and key), so an AgentContext attestation
# cannot verify as a SinkDeclaration attestation, or vice versa, even under
# the SAME authoriser and the SAME secret (REQ-5). The record-type tag,
# prefixed into the canonical bytes below, is the SECOND, independent
# barrier: cross-substrate separation must not depend on the two substrates'
# fields happening to differ.
_RECORD_DOMAIN = b"heimdall.authorisation_record.v1"


def canonical_record_bytes(record) -> bytes:
    """Deterministic encoding of a record's attested content, PREFIXED with
    its record-type tag (REQ-3) so an attestation computed for one record
    type cannot verify when presented as another, in either direction.

    Reads only `record.record_type()` and `record.canonical_fields()`: this
    module imports no record type and cannot depend on `control_surface`
    (REQ-7). `canonical_fields()` is a fixed-order tuple of (name, value)
    pairs; the record itself is responsible for sorting any collection it
    encodes into a value string, so this function need not know a record's
    internal shape beyond that narrow interface. Field order here is exactly
    the order the record returned, so two calls over equal-content records
    (regardless of, say, frozenset insertion order upstream) produce
    identical bytes provided the record's own `canonical_fields()` is
    itself deterministic (as `AgentContext.canonical_fields()` is, by
    sorting its own collections before returning).

    Deterministic string assembly only; no model, no network (invariant
    3.1). Mutates nothing: only reads."""
    tag = record.record_type()
    parts = [f"record_type={tag}"]
    for name, value in record.canonical_fields():
        parts.append(f"{name}={value}")
    body = "\n".join(parts).encode("utf-8")
    return _RECORD_DOMAIN + b"\x00" + body


def compute_record_attestation(record, secret: bytes) -> str:
    """Compute the keyed digest for a record under a trusted secret. This is
    what an honest authoring pipeline calls to attest a record; the harnesses
    call it to build attested fixtures, and `verify_record_attestation`
    recomputes it to check one."""
    h = hashlib.sha256()
    h.update(canonical_record_bytes(record))
    h.update(b"\x00")  # domain separator between content and key
    h.update(secret)
    return h.hexdigest()


@dataclass
class RecordAttestationResult:
    """The outcome of verifying one record's provenance. `verified` True only
    when the record names a trusted authoriser AND its digest matches the
    recomputed one. `reason` records why a record was refused, for the audit
    trail. Mirrors `sink_attestation.AttestationResult`'s shape; kept as a
    distinct type (rather than shared) so each substrate's reason strings can
    name its own record kind without making `sink_attestation.py`, the older
    and more load-bearing module, depend on this newer one (section 7.2)."""

    verified: bool
    reason: str = ""


def verify_record_attestation(record, trusted: TrustedAuthoriserSet) -> RecordAttestationResult:
    """Verify a record's provenance. Fails closed (REQ-2):

      - no authoriser or no attestation on the record (either or both
        absent): REFUSED. An unattested record is not trusted; silence never
        earns trust.
      - an authoriser not in the trusted set: REFUSED. An unknown or forged
        authoriser has no trusted secret to verify against.
      - a digest that does not match the recomputed one: REFUSED. The record
        was altered after it was attested (a raised trust_ceiling, a hollowed
        consequential_sinks set, a swapped agent_id or authoriser), or
        attested under the wrong secret.
      - a trusted authoriser and a matching digest: VERIFIED. This attests WHO
        produced the record and that it is UNALTERED. It attests nothing
        about whether the record's content is TRUE (the identity-versus-
        honesty limit stated in this module's docstring).

    `trusted` is a `sink_attestation.TrustedAuthoriserSet`, imported
    relatively and never redefined (REQ-1). Digest comparison delegates to
    `sink_attestation._constant_time_equals`, never a second comparison loop
    (REQ-4), so a second early-exit bug has nowhere to appear."""
    authoriser = getattr(record, "authoriser", None)
    attestation = getattr(record, "attestation", None)
    record_type = record.record_type() if hasattr(record, "record_type") else "unknown"

    if not authoriser or not attestation:
        return RecordAttestationResult(
            verified=False,
            reason=(
                f"{record_type} record carries no verifiable attestation "
                f"(authoriser or digest absent); an unattested record is refused "
                f"(fail closed, D103, extending D94 direction C)"
            ),
        )

    secret = trusted.secret_for(authoriser)
    if secret is None:
        return RecordAttestationResult(
            verified=False,
            reason=(
                f"{record_type} record names authoriser {authoriser!r}, which is not "
                f"in the trusted authoriser set; an unknown or forged authoriser is "
                f"refused (fail closed, D103, extending D94 direction C)"
            ),
        )

    expected = compute_record_attestation(record, secret)
    if not _constant_time_equals(expected, attestation):
        return RecordAttestationResult(
            verified=False,
            reason=(
                f"{record_type} record attestation does not verify against authoriser "
                f"{authoriser!r}; the record was altered after attestation or attested "
                f"under the wrong key (config-tamper, refused fail closed, D103, "
                f"extending D94 direction C)"
            ),
        )

    return RecordAttestationResult(verified=True)
