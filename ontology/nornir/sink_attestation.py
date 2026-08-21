"""Direction C: attest WHO declared a sink, and refuse an unattested or tampered declaration.

Where this sits in the seam, and what it is NOT. `ADVERSARIAL_REVIEW.md` 5.1 is the root: sink
and flow declarations are trusted input. D89 (B and A) and D93 (D) attacked the HONESTY of a
declaration, is what it claims TRUE of the sink. This module attacks the other half of the seam,
the INTEGRITY and PROVENANCE of a declaration: was it written or changed by someone permitted to
write it. That is a DIFFERENT adversary from the content attacker and from the dishonest author.
It is the configuration-tamper / supply-chain adversary (5.8): whoever can edit a sink
declaration, a flow edge, the ontology or the agent's sink set out of band.

The load-bearing honesty limit, stated first because it decides what C is worth. Attestation
binds IDENTITY and INTEGRITY, never HONESTY. A verified attestation proves "authoriser X
declared this and it has not been altered since", NOT "what X declared is true of the sink". So:

  - C CLOSES the config-tamper adversary: a declaration changed by someone with no trusted key,
    or altered after it was attested, no longer verifies and is refused at load.
  - C DOES NOT CLOSE the malicious-authoriser adversary: an authoriser who legitimately holds a
    trusted key and declares a money sink `display_only` produces a perfectly valid attestation
    of a lie. That is what B (derive consequentiality from the primitive) and D (verify the
    primitive against observed behaviour) address, structurally and by evidence. C pairs with
    them; it does not replace them.

So the seam's honesty is B+D and its integrity is C. Neither subsumes the other.

The mechanism, and why it is a keyed digest and not public-key signing. Each declaration carries
an `authoriser` id and an `attestation` digest. The digest is `hashlib` (stdlib SHA-256) over the
declaration's CANONICAL bytes concatenated with a per-authoriser secret held only in a trusted
set loaded at startup. Verification recomputes the digest from the declaration as loaded and the
trusted secret for its named authoriser, and accepts only on an exact match. This is a keyed
integrity check (HMAC-shaped), which is enough for the config-tamper threat: altering ANY
attested field changes the canonical bytes so the digest no longer matches, and an authoriser
with no entry in the trusted set has no secret to verify against, so an unknown or forged
authoriser is refused. It is DELIBERATELY not full public-key non-repudiation: a keyed digest
proves the holder of the shared secret produced it, not a globally-verifiable signature. The
real deployment would likely use asymmetric keys and a signing pipeline (the "verified set at
load" idea, 5.7); this proves the discipline and the fail-closed load behaviour without deciding
that infrastructure now, exactly as D93 built D's test-harness form and left the runtime form as
a deployment requirement.

Invariant 3.1. `hashlib` is a hashing primitive, not a model and not a network module; it reaches
neither. It is on `ALLOWED_IMPORT_ROOTS` as a reviewed trust-boundary decision (D94, in the
spirit of D71), and the guard's negative control documents that it is intentionally permitted.
No model is on this path: attestation is a digest comparison, not a judgement.

Fail closed, never a blacklist (invariant 3.5, D54/D55). A declaration is trusted only when it
POSITIVELY verifies against a trusted authoriser. Silence never earns trust: an unattested
declaration (no authoriser, no digest), an unknown authoriser, or a digest that does not match
is REFUSED, not admitted with a warning. Nothing enumerates forbidden authorisers; trust is
earned by a positive match against the trusted set.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


@dataclass(frozen=True)
class TrustedAuthoriser:
    """One authoriser the runtime trusts to declare sinks. `authoriser_id` is the identity a
    declaration names; `secret` is the shared secret its attestation is keyed on. In a real
    deployment the secret would be replaced by a public key and the digest by a signature; the
    trusted set is the "verified set at load" (5.7). The secret never leaves the trusted set and
    is never written into a declaration."""

    authoriser_id: str
    secret: bytes


@dataclass
class TrustedAuthoriserSet:
    """The authorisers the runtime trusts, loaded at startup. A declaration whose named
    authoriser is absent here cannot be verified and is refused (fail closed)."""

    authorisers: dict = field(default_factory=dict)  # authoriser_id -> secret bytes

    def trust(self, authoriser: TrustedAuthoriser) -> None:
        self.authorisers[authoriser.authoriser_id] = authoriser.secret

    def secret_for(self, authoriser_id: str) -> "bytes | None":
        return self.authorisers.get(authoriser_id)

    def is_trusted(self, authoriser_id: str) -> bool:
        return authoriser_id in self.authorisers


def canonical_bytes(declaration) -> bytes:
    """The canonical byte encoding of the ATTESTED content of a declaration. The digest is taken
    over exactly these fields, so altering any one of them (renaming the sink, flipping the
    effect primitive, adding or dropping a parameter, changing the consequential flag) changes
    the bytes and breaks the attestation. The `authoriser` is included so a valid attestation
    cannot be replayed under a different authoriser id, but `attestation` itself is NOT (it is
    the digest we are about to compute or check). Ordering is fixed and parameters are sorted so
    the encoding is deterministic and independent of set iteration order.

    Deterministic string assembly only; no model, no network (invariant 3.1)."""
    params = ",".join(sorted(declaration.parameters))
    prim = declaration.effect_primitive if declaration.effect_primitive is not None else ""
    fields = [
        f"name={declaration.name}",
        f"parameters={params}",
        f"consequential_by_default={declaration.consequential_by_default}",
        f"effect_primitive={prim}",
        f"authoriser={declaration.authoriser or ''}",
    ]
    return "\n".join(fields).encode("utf-8")


def compute_attestation(declaration, secret: bytes) -> str:
    """Compute the keyed digest for a declaration under a trusted secret. This is what an
    honest authoring pipeline would call to attest a declaration; the harness uses it to build
    attested declarations, and verification recomputes it to check one."""
    h = hashlib.sha256()
    h.update(canonical_bytes(declaration))
    h.update(b"\x00")  # domain separator between content and key
    h.update(secret)
    return h.hexdigest()


@dataclass
class AttestationResult:
    """The outcome of verifying one declaration's provenance. `verified` True only when the
    declaration names a trusted authoriser AND its digest matches the recomputed one.
    `reason` records why a declaration was refused, for the audit trail and review queue."""

    verified: bool
    reason: str = ""


def verify_attestation(declaration, trusted: TrustedAuthoriserSet) -> AttestationResult:
    """Verify a declaration's provenance at load time. Fails closed.

      - no authoriser or no attestation on the declaration: REFUSED. An unattested declaration
        is not trusted; silence never earns trust.
      - an authoriser not in the trusted set: REFUSED. An unknown or forged authoriser has no
        trusted secret to verify against.
      - a digest that does not match the recomputed one: REFUSED. The declaration was altered
        after it was attested (the config-tamper catch), or attested under the wrong secret.
      - a trusted authoriser and a matching digest: VERIFIED. This attests WHO declared it and
        that it is UNALTERED. It attests nothing about whether the declaration is TRUE (the
        malicious-authoriser limit; that is B and D's job).

    Digest comparison via `hashlib`, no model on the path (invariant 3.1)."""
    authoriser = getattr(declaration, "authoriser", None)
    attestation = getattr(declaration, "attestation", None)

    if not authoriser or not attestation:
        return AttestationResult(
            verified=False,
            reason=(f"sink {declaration.name!r} carries no verifiable attestation "
                    f"(authoriser or digest absent); an unattested declaration is refused "
                    f"(fail closed, D94 direction C)"),
        )

    secret = trusted.secret_for(authoriser)
    if secret is None:
        return AttestationResult(
            verified=False,
            reason=(f"sink {declaration.name!r} names authoriser {authoriser!r}, which is not in "
                    f"the trusted authoriser set; an unknown or forged authoriser is refused "
                    f"(fail closed, D94 direction C)"),
        )

    expected = compute_attestation(declaration, secret)
    if not _constant_time_equals(expected, attestation):
        return AttestationResult(
            verified=False,
            reason=(f"sink {declaration.name!r} attestation does not verify against authoriser "
                    f"{authoriser!r}; the declaration was altered after attestation or attested "
                    f"under the wrong key (config-tamper, refused fail closed, D94 direction C)"),
        )

    return AttestationResult(verified=True)


def _constant_time_equals(a: str, b: str) -> bool:
    """Compare two hex digests without an early-exit on the first differing character, so the
    comparison does not leak how many leading characters matched via timing. `hashlib` gives us
    the digest; the comparison is ours, and it is a plain deterministic loop (no model)."""
    if len(a) != len(b):
        return False
    result = 0
    for x, y in zip(a, b):
        result |= ord(x) ^ ord(y)
    return result == 0
