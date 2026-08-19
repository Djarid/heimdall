"""Test harness for direction C: attest WHO declared a sink, refuse unattested or tampered ones.

Run from the repo root:

    python -m ontology.tests.sink_attestation_harness

Where C sits, and what it is not. `ADVERSARIAL_REVIEW.md` 5.1 is the root seam: sink and flow
declarations are trusted input. D89 (B and A) and D93 (D) attacked the HONESTY of a declaration.
C attacks the other half, the INTEGRITY and PROVENANCE: was the declaration written or changed
by someone permitted to write it (the configuration-tamper / supply-chain adversary, 5.8). Each
obligation below plants one integrity failure and asserts it is refused at load, with the
mandatory honest control that a properly attested declaration loads cleanly.

The load-bearing limit, tested explicitly rather than hidden (obligation 5): attestation binds
IDENTITY and INTEGRITY, never HONESTY. A trusted authoriser who attests a LIE produces a valid
attestation, and C admits it, because C proves WHO said it, not that it is TRUE. That is exactly
what B and D exist to catch, and the obligation asserts the division of labour so a reader cannot
mistake C for a honesty check.
"""

from __future__ import annotations

from ..nornir.sink_attestation import (
    TrustedAuthoriser,
    TrustedAuthoriserSet,
    compute_attestation,
    verify_attestation,
)
from ..nornir.sink_declaration import (
    MOVE_MONEY,
    DISPLAY_ONLY,
    SinkDeclaration,
    SinkRegistry,
    effective_consequential,
)


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


PLATFORM_SECRET = b"platform-signing-secret-not-in-any-declaration"


def build_trusted() -> TrustedAuthoriserSet:
    t = TrustedAuthoriserSet()
    t.trust(TrustedAuthoriser(authoriser_id="platform-security", secret=PLATFORM_SECRET))
    return t


def attested(name, parameters, effect_primitive, authoriser, secret,
             consequential_by_default=True) -> SinkDeclaration:
    """Build a declaration and attach a real attestation computed under `secret`. This models
    what an honest authoring pipeline does: declare, then attest under the authoriser's key."""
    d = SinkDeclaration(
        name=name, parameters=frozenset(parameters),
        consequential_by_default=consequential_by_default,
        effect_primitive=effect_primitive, authoriser=authoriser,
    )
    digest = compute_attestation(d, secret)
    # Rebuild with the digest set (the declaration is frozen).
    return SinkDeclaration(
        name=d.name, parameters=d.parameters,
        consequential_by_default=d.consequential_by_default,
        effect_primitive=d.effect_primitive, authoriser=d.authoriser,
        attestation=digest,
    )


def test_honest_attested_declaration_loads(rep: Report) -> None:
    """The mandatory control. A declaration attested by a trusted authoriser verifies and loads
    via declare_attested. Without this, the gate would be pure friction."""
    rep.line("=== 1. Control: a properly attested declaration verifies and loads ===")
    trusted = build_trusted()
    d = attested("sink:payments.execute", {"amount", "destination"}, MOVE_MONEY,
                 "platform-security", PLATFORM_SECRET)
    res = verify_attestation(d, trusted)
    rep.check(res.verified, "a trusted-authoriser attestation verifies")
    reg = SinkRegistry()
    reg.declare_attested(d, trusted)   # must not raise
    rep.check(reg.is_declared("sink:payments.execute"),
              "and declare_attested admits it into the registry")
    rep.line()


def test_tampered_declaration_refused(rep: Report) -> None:
    """The config-tamper catch. A declaration is attested honestly, then a field is altered after
    the fact (a money sink downgraded to display_only by an out-of-band edit). The digest no
    longer matches the altered bytes, so it is refused."""
    rep.line("=== 2. A declaration altered after attestation is REFUSED (config tamper) ===")
    trusted = build_trusted()
    honest = attested("sink:payments.execute", {"amount"}, MOVE_MONEY,
                      "platform-security", PLATFORM_SECRET)
    # The tamper: keep the (valid) digest, but flip the effect primitive to display_only, as an
    # attacker editing the config file would. The digest was computed over MOVE_MONEY.
    tampered = SinkDeclaration(
        name=honest.name, parameters=honest.parameters,
        consequential_by_default=honest.consequential_by_default,
        effect_primitive=DISPLAY_ONLY,           # altered
        authoriser=honest.authoriser,
        attestation=honest.attestation,          # stale digest, over the old bytes
    )
    res = verify_attestation(tampered, trusted)
    rep.check(not res.verified, "the tampered declaration does not verify")
    rep.check("altered" in res.reason or "tamper" in res.reason,
              "and the reason names it as a tamper")
    reg = SinkRegistry()
    try:
        reg.declare_attested(tampered, trusted)
        rep.check(False, "declare_attested should have refused the tampered declaration")
    except ValueError:
        rep.check(True, "declare_attested REFUSES the tampered declaration (fail closed)")
    rep.line()


def test_unknown_authoriser_refused(rep: Report) -> None:
    """A declaration attested by someone not in the trusted set (a forged or rogue authoriser)
    is refused: they have no trusted secret to verify against."""
    rep.line("=== 3. An unknown / forged authoriser is REFUSED ===")
    trusted = build_trusted()
    rogue = attested("sink:payments.execute", {"amount"}, MOVE_MONEY,
                     "attacker", b"attacker-chosen-secret")
    res = verify_attestation(rogue, trusted)
    rep.check(not res.verified, "an attestation from an untrusted authoriser does not verify")
    rep.check("not in the trusted" in res.reason,
              "and the reason names the untrusted authoriser")
    rep.line()


def test_unattested_declaration_refused(rep: Report) -> None:
    """Silence never earns trust. A bare declaration with no authoriser and no digest (the
    current pre-C shape) is refused when attestation is enforced."""
    rep.line("=== 4. An unattested declaration is REFUSED (silence never earns trust) ===")
    trusted = build_trusted()
    bare = SinkDeclaration(name="sink:payments.execute", parameters=frozenset({"amount"}),
                           effect_primitive=MOVE_MONEY)  # no authoriser, no attestation
    res = verify_attestation(bare, trusted)
    rep.check(not res.verified, "an unattested declaration does not verify")
    rep.check("no verifiable attestation" in res.reason,
              "and the reason names the missing attestation")
    rep.line()


def test_malicious_authoriser_limit(rep: Report) -> None:
    """The honest limit, asserted rather than hidden. A TRUSTED authoriser declares a money sink
    as display_only, a LIE, and attests it correctly under their real key. C verifies it, because
    C proves WHO declared it and that it is UNALTERED, not that it is TRUE. The point of the
    obligation: show C admits the lie AND that B still catches it (consequentiality derived from
    the effect primitive is display_only here, so B would be fooled too, which is precisely why
    D93's behaviour verification, not C, is the honesty backstop). C's job is integrity; the
    division of labour is the design, not a gap."""
    rep.line("=== 5. Honest limit: a TRUSTED authoriser's LIE still verifies (C is not honesty) ===")
    trusted = build_trusted()
    # A trusted authoriser attests a money mover AS display_only. The attestation is valid.
    lie = attested("sink:payments.disguised", {"amount"}, DISPLAY_ONLY,
                   "platform-security", PLATFORM_SECRET, consequential_by_default=False)
    res = verify_attestation(lie, trusted)
    rep.check(res.verified,
              "the lie is correctly ATTESTED (C proves who said it, not that it is true)")
    reg = SinkRegistry()
    reg.declare_attested(lie, trusted)
    # B, reading the declared display_only primitive, is also fooled: this is why C is necessary
    # but not sufficient, and why D (verify against behaviour) is the honesty backstop for a sink
    # whose declared primitive lies.
    rep.check(effective_consequential("sink:payments.disguised", reg, frozenset()) is False,
              "B alone is fooled by the display_only lie (as expected): C+B do not catch a "
              "malicious authoriser; D93's behaviour verification is the backstop")
    rep.line()


def main() -> int:
    rep = Report()
    rep.line("Direction C: attest WHO declared a sink, refuse unattested or tampered (D94)")
    rep.line("Closes the config-tamper / supply-chain axis of the root seam; pairs with B and D.")
    rep.line("")

    test_honest_attested_declaration_loads(rep)
    test_tampered_declaration_refused(rep)
    test_unknown_authoriser_refused(rep)
    test_unattested_declaration_refused(rep)
    test_malicious_authoriser_limit(rep)

    rep.dump()
    print()
    if rep.failures:
        print(f"SUITE FAIL: {rep.failures} failing check(s).")
        return 1
    print("SUITE PASS: a declaration altered after attestation, one from an unknown/forged")
    print("authoriser, and an unattested declaration are all REFUSED at load (fail closed), while")
    print("a properly attested one loads (no friction). The keyed digest (hashlib SHA-256 over")
    print("the declaration's canonical bytes plus a per-authoriser secret) closes the")
    print("config-tamper / supply-chain adversary of the root seam (5.1).")
    print("HONEST LIMIT, asserted in obligation 5: attestation binds IDENTITY and INTEGRITY, not")
    print("HONESTY. A TRUSTED authoriser who attests a LIE still verifies, and B is fooled by the")
    print("declared primitive, so C does NOT catch a malicious authoriser; that is D93's")
    print("behaviour verification. C is integrity, B and D are honesty. It is also a keyed digest,")
    print("not public-key non-repudiation: the asymmetric-key signing pipeline stays a deployment")
    print("requirement (5.7), as the runtime form of D stays a deployment requirement.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
