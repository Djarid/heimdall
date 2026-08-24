"""Export Gjoll's golden gate vectors for the Rust re-expression (D109, spec section 3.4).

Run from the repo root:

    python -m ontology.tools.export_gate_vectors

What this does, and why it lives here rather than under `ontology/tests/`. It wraps
`ontology.nornir.gjoll`'s public entry points (`evaluate`, `enforce`), re-runs the
three harnesses that already exercise the gate (`ontology.tests.harness::run_gjoll`,
`ontology.tests.control_surface_harness`, `ontology.tests.effect_probe_harness`),
captures every one of the 22 gate calls those harnesses make, and writes them as
golden vectors to `crates/boundary-gjoll/vectors/gate_vectors.json`. It is a build-time
generator, not a suite obligation: `ontology/tests/harness.py`'s `main()` registry is
this repository's operative definition of an obligation, and an unregistered module
under `ontology/tests/` would be exactly the trap D102 closed. `ontology/tools/` is
also outside `symbolic_guard.py`'s scan roots, so the invariant 3.1 scanned-file count
stays unchanged.

How calls are captured, and why a naive monkeypatch is not enough. Both
`control_surface_harness.py` and `effect_probe_harness.py` bind `evaluate`/`enforce`
at MODULE level (`from ontology.nornir.gjoll import ... evaluate, enforce ...`), so a
patch applied to `gjoll.evaluate`/`gjoll.enforce` AFTER those modules have already been
imported once would never be seen by them: a `from X import Y` binds a name to whatever
object `X.Y` was AT IMPORT TIME, and rebinding `X.Y` later does not retroactively change
an already-bound reference. This module therefore ALWAYS (re)imports those two harness
modules AFTER patching `gjoll`'s module attributes, using `importlib.reload` so a
process that already imported them (a prior harness run in the same interpreter) still
picks up the patched functions. `ontology.tests.harness::run_gjoll` imports `enforce`
LOCALLY inside its own function body, so it re-resolves the current `gjoll.enforce` on
every call and needs no reload.

Call-site identity, not call order, decides each vector's id. The 22 call sites are
named by (repo-relative file, line number), read once from the checked-out source at
the time this spec's vector inventory was counted (spec section 4.1). A call captured
at a mapped site becomes exactly the named vector; a call captured at a site on
`EXCLUDED_CALL_SITES` (the one gate call the spec's section 4.3 names as excluded from
the parity claim) is discarded; a call captured anywhere else is a count-drift event
and aborts the export loudly (REQ-18), because a harness gaining or losing a gate call
must never rot the vector file silently.

What is NOT reimplemented here (REQ-19, DRY risk 1, the brief's top pre-mortem risk):
`effective_consequential`, `_consequential_from_stamps` and `verify_declaration` are
called directly from the real Python modules; this file contains no local union-of-
stamps loop and no local effect-primitive membership table. The only thing this file
DOES reimplement is the three-condition rule's own per-parameter loop (`shadow_apply`),
which is the intended self-check (REQ-20): the same simple rule the Rust `rule::apply`
will implement, checked here in Python first against the real decisions it must
reproduce, using only the four fields (REQ-8) the rule core is allowed to see.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import os
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GJOLL_PY = REPO_ROOT / "ontology" / "nornir" / "gjoll.py"
SINK_DECLARATION_PY = REPO_ROOT / "ontology" / "nornir" / "sink_declaration.py"
VECTOR_FILE = REPO_ROOT / "crates" / "boundary-gjoll" / "vectors" / "gate_vectors.json"

SCHEMA_VERSION = 1
EXPECTED_LAYER_ONE_COUNT = 22
EXPECTED_LAYER_TWO_COUNT = 6

# The registry-supplied subset replayable at layer two (spec section 4.2). `E-1` is
# deliberately absent even though its real call supplies a registry: its blocked
# verdict depends on the D93 behavioural observation, which REQ-17 reserves rather
# than builds, so it replays at layer one only (the verdict it produced is an input).
LAYER_TWO_VECTOR_IDS: frozenset[str] = frozenset({"G-4", "G-5", "G-6", "C-9c", "C-11", "C-12"})

# Every `evaluate`/`enforce` call site the three harnesses make, keyed by
# (repo-relative path, line number), read from the checked-out source (spec section
# 4.1). A call captured at any OTHER site is a count-drift event (REQ-18) and aborts
# the export; this map is deliberately exhaustive, not permissive.
CALL_SITE_MAP: dict[tuple[str, int], str] = {
    ("ontology/tests/harness.py", 583): "G-1",
    ("ontology/tests/harness.py", 598): "G-2",
    ("ontology/tests/harness.py", 619): "G-3",
    ("ontology/tests/harness.py", 646): "G-4",
    ("ontology/tests/harness.py", 669): "G-5",
    ("ontology/tests/harness.py", 690): "G-6",
    ("ontology/tests/control_surface_harness.py", 228): "C-1",
    ("ontology/tests/control_surface_harness.py", 251): "C-2",
    ("ontology/tests/control_surface_harness.py", 274): "C-3",
    ("ontology/tests/control_surface_harness.py", 308): "C-4a",
    ("ontology/tests/control_surface_harness.py", 309): "C-4b",
    ("ontology/tests/control_surface_harness.py", 336): "C-5",
    ("ontology/tests/control_surface_harness.py", 370): "C-6",
    ("ontology/tests/control_surface_harness.py", 408): "C-7a",
    ("ontology/tests/control_surface_harness.py", 418): "C-7b",
    ("ontology/tests/control_surface_harness.py", 451): "C-8",
    ("ontology/tests/control_surface_harness.py", 470): "C-9a",
    ("ontology/tests/control_surface_harness.py", 474): "C-9b",
    ("ontology/tests/control_surface_harness.py", 487): "C-9c",
    ("ontology/tests/control_surface_harness.py", 595): "C-11",
    ("ontology/tests/control_surface_harness.py", 644): "C-12",
    ("ontology/tests/effect_probe_harness.py", 167): "E-1",
}
assert len(CALL_SITE_MAP) == EXPECTED_LAYER_ONE_COUNT, "CALL_SITE_MAP must name exactly 22 sites"
assert LAYER_TWO_VECTOR_IDS <= set(CALL_SITE_MAP.values())
assert len(LAYER_TWO_VECTOR_IDS) == EXPECTED_LAYER_TWO_COUNT

# The one real gate call the spec's section 4.3 names as an explicit, positive
# exclusion from the parity claim: `_report_narrowed_residual`'s forged-stamp
# reproduction, which reproduces D97's residual on the designed-out no-registry
# branch and is reported, not asserted, by the harness itself.
EXCLUDED_CALL_SITES: frozenset[tuple[str, int]] = frozenset({
    ("ontology/tests/control_surface_harness.py", 688),
})

# Short, traceable claims per vector (spec section 4.1/4.2's table), carried into the
# emitted file so a reader (or the Rust implementer) does not have to cross-reference
# the spec to know what each vector is checking.
VECTOR_CLAIMS: dict[str, str] = {
    "G-1": "D10 safe wiring: inert consumption at an unrelated sink",
    "G-2": "D10 unsafe control: staged cross-domain value consumed as action at the payment sink",
    "G-3": "not-pure-friction control: untrusted but non-action-critical value consumed as action",
    "G-4": "D89-B: dishonestly-flagged money sink with an empty agent set",
    "G-5": "D89-A: action-critical value declared inert at a consequential sink",
    "G-6": "D89-A anti-friction control: non-action-critical value declared inert",
    "C-1": "D100 closed case: hollowed agent_consequential_sinks, no registry",
    "C-2": "inert-sink anti-conflation control",
    "C-3": "empty-stamp no-friction control",
    "C-4a": "attested-empty stamp authorises",
    "C-4b": "absent stamp fails closed",
    "C-5": "hand-built, no stamp, fail closed",
    "C-6": "one unstamped parameter not outvoted by a stamped sibling",
    "C-7a": "union widens sink_is_consequential",
    "C-7b": "the widened union does not over-block",
    "C-8": "no-known-provenance fail-closed reason, zero classified consumed parameters",
    "C-9a": "union/argument mismatch, non-blocking note (notes not re-expressed in Rust)",
    "C-9b": "union/argument match, no note",
    "C-9c": "registry path: notes always empty",
    "C-11": "registry path is blind to the classify-time stamp",
    "C-12": "a stamp naming the sink is not ORed into the registry derivation",
    "E-1": "D93: a sink observed to move money is blocked though declared display_only",
}
assert set(VECTOR_CLAIMS) == set(CALL_SITE_MAP.values())


class ExporterError(RuntimeError):
    """Raised to abort the export loudly (never a partial file, never a silent drop)."""


class UnclassifiableReasonError(ExporterError):
    """A real Gjoll reason string matched none of the four `ReasonKind`s (REQ-22)."""


# ---------------------------------------------------------------------------------
# REQ-11 / REQ-22: total classification of a Python reason string into one of the
# four reason kinds, each paired with the parameter (or sink) identifier it names.
# Order matters: the two gjoll.py per-parameter reasons are checked before the five
# sink_declaration.py validation reasons, but there is no overlap between them.
# ---------------------------------------------------------------------------------
_REASON_PATTERNS: tuple[tuple[str, "re.Pattern[str]"], ...] = (
    ("inert_contradicts_reachability", re.compile(
        r"declares untrusted-derived, action-critical value '(?P<param>[^']*)'.*?"
        r"as CONSUME_INERT")),
    ("action_on_action_critical_tainted", re.compile(
        r"consumes untrusted-derived, action-critical value '(?P<param>[^']*)'.*?"
        r"as an ACTION instruction")),
    ("no_known_provenance", re.compile(
        r"^parameter '(?P<param>[^']*)' consumed as ACTION has no known provenance")),
    ("declaration_invalid", re.compile(
        r"^sink '(?P<param>[^']*)' is not declared in the sink registry")),
    ("declaration_invalid", re.compile(
        r"^parameter '(?P<param>[^']*)' declares consume mode '[^']*', which is not one of")),
    ("declaration_invalid", re.compile(
        r"^parameter '(?P<param>[^']*)' is declared in consumes but is not a known classified")),
    ("declaration_invalid", re.compile(
        r"^sink '(?P<param>[^']*)' declares parameters \[.*?\] that the proposal does not "
        r"account for")),
    ("declaration_invalid", re.compile(
        r"^proposal declares parameters \[.*?\] that sink '(?P<param>[^']*)' does not accept")),
)


def classify_reason(reason: str) -> tuple[str, str]:
    """Classify one real Gjoll reason string into `(kind, parameter_id)`. Total: a
    reason matching none of the four kinds raises `UnclassifiableReasonError` rather
    than being emitted as an unknown or dropped (REQ-22, AC-22)."""
    for kind, pattern in _REASON_PATTERNS:
        m = pattern.search(reason)
        if m:
            return kind, m.group("param")
    raise UnclassifiableReasonError(f"reason string matches no known ReasonKind: {reason!r}")


def shadow_apply(
    verdict: bool, consumes: dict, classified: dict
) -> tuple[bool, list[tuple[str, str]]]:
    """The self-check's own reimplementation of the three-condition rule plus the
    D89-A inert-contradiction check (REQ-20) -- deliberately the ONE thing this file
    does reimplement, because it is the whole point of the self-check: reproduce the
    real decision from only the four rule-core fields (REQ-8) and the already-derived
    verdict, never from `effective_consequential` or `_consequential_from_stamps`
    (those are called, never reimplemented; see the module docstring).

    `classified` maps a consumed parameter id to a dict with `trust_level` and
    `action_critical` (the two of REQ-8's four fields the rule logic itself reads);
    a parameter absent from `classified` is unresolved (EC-6), handled exactly as
    `gjoll.evaluate`'s own per-parameter loop handles it."""
    reasons: list[tuple[str, str]] = []
    for param_id, mode in consumes.items():
        c = classified.get(param_id)
        if mode != "ACTION":
            if c is None:
                continue  # genuinely inert: no provenance to make it action-critical
            untrusted = c["trust_level"] == "trust:TAINTED"
            if verdict and untrusted and c["action_critical"]:
                reasons.append(("inert_contradicts_reachability", param_id))
            continue
        if c is None:
            reasons.append(("no_known_provenance", param_id))
            continue
        untrusted = c["trust_level"] == "trust:TAINTED"
        if verdict and untrusted and c["action_critical"]:
            reasons.append(("action_on_action_critical_tainted", param_id))
    return (not reasons), reasons


def control_check() -> list[str]:
    """Negative controls (invariant 3.10, D10): before trusting the self-check and
    the reason classifier, confirm each can actually fail. Returns a list of failure
    descriptions (empty if both bite)."""
    failures: list[str] = []

    # The self-check control: a deliberately WRONG verdict must make the shadow
    # rule's outcome diverge from the outcome it is supposed to reproduce.
    classified = {
        "p1": {"assertion_id": "p1", "type_name": "t", "trust_level": "trust:TAINTED",
               "action_critical": True},
    }
    consumes = {"p1": "ACTION"}
    real_authorised = False  # the real decision, if verdict were True, would block
    shadow_authorised, _ = shadow_apply(False, consumes, classified)  # the wrong verdict
    if shadow_authorised == real_authorised:
        failures.append(
            "self-check control did NOT catch a deliberately wrong verdict: shadow_apply "
            "with verdict=False wrongly agreed with a decision that should have blocked"
        )

    # The classifier control: an unclassifiable reason string must raise, never pass.
    try:
        classify_reason("this sentence names no reason kind this exporter knows about")
    except UnclassifiableReasonError:
        pass
    else:
        failures.append("reason classifier FAILED to reject an unclassifiable reason string")

    return failures


def _relpath(filename: str) -> str:
    return str(Path(filename).resolve().relative_to(REPO_ROOT)).replace(os.sep, "/")


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _capture_gate_calls() -> dict[str, dict]:
    """Patch `ontology.nornir.gjoll`'s `evaluate`/`enforce`, re-run the three
    harnesses, and return every captured call keyed by vector id. See the module
    docstring for why the two module-level-importing harnesses are reloaded AFTER
    patching, and why the depth guard below prevents `enforce`'s own internal call to
    `evaluate` from being recorded as a second, spurious vector for the same call
    site."""
    import inspect

    import ontology.nornir.gjoll as gjoll_mod

    original_evaluate = gjoll_mod.evaluate
    original_enforce = gjoll_mod.enforce
    evaluate_sig = inspect.signature(original_evaluate)
    enforce_sig = inspect.signature(original_enforce)
    depth = {"n": 0}
    records: dict[str, dict] = {}

    def _handle(kind: str, sig: "inspect.Signature", frame, args, kwargs, result) -> None:
        relpath = _relpath(frame.f_code.co_filename)
        lineno = frame.f_lineno
        key = (relpath, lineno)
        if key in EXCLUDED_CALL_SITES:
            return
        vector_id = CALL_SITE_MAP.get(key)
        if vector_id is None:
            raise ExporterError(
                f"unmapped Gjoll gate call site at {relpath}:{lineno} (a {kind} call not "
                f"named in CALL_SITE_MAP): a harness gained a gate call this exporter does "
                f"not know about. Update CALL_SITE_MAP and the spec's vector inventory, or "
                f"investigate why a new call site appeared (REQ-18)."
            )
        if vector_id in records:
            raise ExporterError(
                f"duplicate capture for vector {vector_id!r} at {relpath}:{lineno}: the same "
                f"vector id was already captured from a different call"
            )
        bound = sig.bind(*args, **kwargs)
        bound.apply_defaults()
        a = bound.arguments
        records[vector_id] = {
            "origin": f"{relpath}:{lineno} (in {frame.f_code.co_name})",
            "kind": kind,
            "proposal": a["proposal"],
            "classified_by_id": a["classified_by_id"],
            "agent_consequential_sinks": a["agent_consequential_sinks"],
            "sink_registry": a.get("sink_registry"),
            "effect_observations": a.get("effect_observations"),
            "decision": result,
        }

    def wrapped_evaluate(*args, **kwargs):
        if depth["n"] > 0:
            return original_evaluate(*args, **kwargs)
        frame = sys._getframe(1)
        result = original_evaluate(*args, **kwargs)
        _handle("evaluate", evaluate_sig, frame, args, kwargs, result)
        return result

    def wrapped_enforce(*args, **kwargs):
        frame = sys._getframe(1)
        depth["n"] += 1
        try:
            result = original_enforce(*args, **kwargs)
        finally:
            depth["n"] -= 1
        _handle("enforce", enforce_sig, frame, args, kwargs, result)
        return result

    gjoll_mod.evaluate = wrapped_evaluate
    gjoll_mod.enforce = wrapped_enforce
    try:
        from ontology.nornir import Nornir, MarshalledAssertion  # noqa: F401
        from ontology.yggdrasil import load

        with contextlib.redirect_stdout(io.StringIO()):
            harness_mod = importlib.import_module("ontology.tests.harness")
            harness_mod = importlib.reload(harness_mod)
            nornir = Nornir(load())
            harness_mod.run_gjoll(nornir, harness_mod.Report())

            csh = importlib.import_module("ontology.tests.control_surface_harness")
            csh = importlib.reload(csh)
            csh.main()

            eph = importlib.import_module("ontology.tests.effect_probe_harness")
            eph = importlib.reload(eph)
            eph.main()
    finally:
        gjoll_mod.evaluate = original_evaluate
        gjoll_mod.enforce = original_enforce

    return records


def _compute_verdict(record: dict) -> bool:
    """Derive the consequentiality verdict Gjoll actually used for this call, calling
    only the real Python functions (REQ-19): `effective_consequential` on the
    registry path, `_consequential_from_stamps` otherwise, then (mirroring
    `gjoll.evaluate`'s own few lines, never reimplementing `verify_declaration`
    itself) OR-ing in the D93 behavioural override when an observation is present."""
    from ontology.nornir.gjoll import _consequential_from_stamps
    from ontology.nornir.sink_declaration import effective_consequential

    proposal = record["proposal"]
    sink_registry = record["sink_registry"]
    if sink_registry is not None:
        verdict = effective_consequential(
            proposal.sink, sink_registry, record["agent_consequential_sinks"]
        )
    else:
        verdict, _notes = _consequential_from_stamps(
            proposal, record["classified_by_id"], record["agent_consequential_sinks"]
        )

    effect_observations = record["effect_observations"]
    if effect_observations is not None:
        from ontology.nornir.effect_probe import verify_declaration

        observation = effect_observations.get(proposal.sink)
        if observation is not None:
            declaration = sink_registry.get(proposal.sink) if sink_registry is not None else None
            verification = verify_declaration(declaration, observation)
            if verification.verified_consequential:
                verdict = True
    return verdict


def _classified_map(record: dict) -> dict[str, dict]:
    """The four REQ-8 fields per consumed parameter present in `classified_by_id`; a
    parameter the proposal consumes but which is absent from `classified_by_id` is
    left out entirely (EC-6: unresolved, replayed faithfully, not an error)."""
    proposal = record["proposal"]
    classified_by_id = record["classified_by_id"]
    out: dict[str, dict] = {}
    for param_id in proposal.consumes:
        c = classified_by_id.get(param_id)
        if c is not None:
            out[param_id] = {
                "assertion_id": c.assertion_id,
                "type_name": c.type_name,
                "trust_level": c.trust_level,
                "action_critical": c.action_critical,
            }
    return out


def _registry_repr(sink_registry) -> dict:
    return {
        "declarations": [
            {
                "name": d.name,
                "parameters": sorted(d.parameters),
                "consequential_by_default": d.consequential_by_default,
                "effect_primitive": d.effect_primitive,
            }
            for d in sink_registry.declarations.values()
        ]
    }


def build_vectors() -> dict:
    """Capture, self-check and assemble the full vector document. Raises
    `ExporterError` (never emits a partial result) on any count mismatch, self-check
    failure or unclassifiable reason (REQ-18, REQ-20, REQ-21, REQ-22)."""
    control_failures = control_check()
    if control_failures:
        raise ExporterError(
            "negative controls did not bite; refusing to trust the self-check or the "
            "reason classifier: " + "; ".join(control_failures)
        )

    records = _capture_gate_calls()

    expected_ids = set(CALL_SITE_MAP.values())
    missing = expected_ids - set(records)
    extra = set(records) - expected_ids
    if missing or extra:
        raise ExporterError(
            f"captured {len(records)} vector(s), expected {EXPECTED_LAYER_ONE_COUNT}. "
            f"missing={sorted(missing)} extra={sorted(extra)}"
        )

    sensitive_directions: set[str] = set()
    vectors: list[dict] = []

    for vector_id in sorted(records, key=lambda v: (len(v), v)):
        record = records[vector_id]
        proposal = record["proposal"]
        decision = record["decision"]
        consumes = dict(proposal.consumes)
        classified = _classified_map(record)
        verdict = _compute_verdict(record)

        real_reasons = [classify_reason(r) for r in decision.reasons]
        shadow_authorised, shadow_reasons = shadow_apply(verdict, consumes, classified)

        if shadow_authorised != decision.authorised or sorted(shadow_reasons) != sorted(real_reasons):
            raise ExporterError(
                f"self-check FAILED for vector {vector_id!r}: shadow rule gave "
                f"authorised={shadow_authorised} reasons={sorted(shadow_reasons)}, real "
                f"decision gave authorised={decision.authorised} reasons={sorted(real_reasons)} "
                f"(REQ-20)"
            )

        flipped_authorised, _flipped_reasons = shadow_apply(not verdict, consumes, classified)
        verdict_sensitive = flipped_authorised != shadow_authorised
        if verdict_sensitive:
            if shadow_authorised and not flipped_authorised:
                sensitive_directions.add("authorised_to_blocked")
            elif (not shadow_authorised) and flipped_authorised:
                sensitive_directions.add("blocked_to_authorised")

        expected = {
            "authorised": decision.authorised,
            "reasons": [{"kind": k, "parameter": p} for k, p in real_reasons],
        }
        vector: dict = {
            "id": vector_id,
            "origin": record["origin"],
            "claim": VECTOR_CLAIMS[vector_id],
            "layer_one": {
                "verdict": verdict,
                "verdict_sensitive": verdict_sensitive,
                "proposal": {
                    "action_id": proposal.action_id,
                    "sink": proposal.sink,
                    "consumes": consumes,
                    "declared_safe": proposal.declared_safe,
                },
                "classified": classified,
                "expected": expected,
            },
        }
        if vector_id in LAYER_TWO_VECTOR_IDS:
            vector["layer_two"] = {
                "registry": _registry_repr(record["sink_registry"]),
                "expected": expected,
            }
        vectors.append(vector)

    layer_two_count = sum(1 for v in vectors if "layer_two" in v)
    if layer_two_count != EXPECTED_LAYER_TWO_COUNT:
        raise ExporterError(
            f"assembled {layer_two_count} layer-two vector(s), expected "
            f"{EXPECTED_LAYER_TWO_COUNT}"
        )

    required_directions = {"authorised_to_blocked", "blocked_to_authorised"}
    missing_directions = required_directions - sensitive_directions
    if missing_directions:
        raise ExporterError(
            f"no captured vector is verdict-sensitive in direction(s) "
            f"{sorted(missing_directions)} (REQ-21): a flip in each direction must be "
            f"demonstrated by at least one real vector, not asserted"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_from": {
            "gjoll_py_sha256": _sha256_of(GJOLL_PY),
            "sink_declaration_py_sha256": _sha256_of(SINK_DECLARATION_PY),
        },
        "expected_counts": {
            "layer_one": EXPECTED_LAYER_ONE_COUNT,
            "layer_two": EXPECTED_LAYER_TWO_COUNT,
        },
        "vectors": vectors,
    }


def _write_atomically(data: dict, target: Path) -> None:
    """Write to a temp file in the same directory, then move into place (EC-12): a
    partial file that happens to parse would be a silently narrowed parity claim."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=".gate_vectors.", suffix=".json.tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
            f.write("\n")
        os.replace(tmp_name, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)
        raise


def export_vectors() -> dict:
    data = build_vectors()
    _write_atomically(data, VECTOR_FILE)
    return data


def main() -> int:
    try:
        data = export_vectors()
    except ExporterError as exc:
        print(f"EXPORT FAILED: {exc}", file=sys.stderr)
        return 1
    layer_two = sum(1 for v in data["vectors"] if "layer_two" in v)
    print(
        f"Exported {len(data['vectors'])} layer-one vector(s) ({layer_two} with a "
        f"layer-two section) to {VECTOR_FILE.relative_to(REPO_ROOT)}"
    )
    print(f"  gjoll.py sha256:            {data['generated_from']['gjoll_py_sha256']}")
    print(f"  sink_declaration.py sha256: {data['generated_from']['sink_declaration_py_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
