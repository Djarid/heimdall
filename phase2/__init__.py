"""Phase 2 detection layer: Fenrir (sandbox reader) and Huginn (canary and
attempt-introspection monitoring).

This package builds the reading path and its monitoring to the depth the Phase 2
Detailed Design specifies (`plans/dd/fenrir.md`), under the scoped R-1 exception
(decision D74): a fail-closed detector arms no consequential capability, so it may
be built before the D67-fix arming gate closes, and it is itself D67-fix direction
(d), the attempt-introspection catch.

What is here:

- `canary.py`   the signed top/tail canary wrap (Himinbjörg owns construction in
                Phase 3; here it is a functional stand-in with the same shape).
- `fenrir.py`   the sandbox reader's `extract` contract and its structural
                properties (empty capability set, fresh context, tainted output).
- `huginn.py`   canary monitoring (the six hard signals) and the
                attempt-introspection tripwire (the null-surface detector).

What is deliberately NOT here (stays Phase 2/3, gated by R-1, D74):

- Real network segmentation and the egress-policy test (deployment; invariant 3.8
  is DEMONSTRATED in shape, not deployment). The shape is tested: empty capability
  set, no egress role.
- Himinbjörg constructing and signing the canary (Phase 3). The wrap is stubbed
  with an explicit boundary marker.
- Muninn episode memory, drift detection and Odin (Phase 5).
- True grammar-constrained decoding. The PoC's proven per-field bounded-generation
  stand-in is reused, exactly as `fenrir.md` section 3.1 says Phase 2 does.

The detection logic is model-agnostic: Fenrir takes an emission-producer, so the
same tripwire and canary monitor run against a deterministic MOCK (the always-run
suite) and against the real mlx model (the optional demonstration).
"""
