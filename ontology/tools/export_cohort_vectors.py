# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Jason Huxley and the Heimdall authors.

"""Export Vor's cohort golden vectors for the Rust re-expression (D110, spec section
3.5, issue #25).

Run from the repo root:

    python -m ontology.tools.export_cohort_vectors

What this does, and why it lives here rather than under `ontology/tests/`. It calls
`ontology.nornir.authorisation_record`'s own `canonical_record_bytes` and
`compute_record_attestation` over a shim record defined in this file, and
`ontology.nornir.sink_attestation`'s own `canonical_bytes` and `compute_attestation`
for the cross-substrate demonstration, and writes the result as golden vectors to
`crates/hierarchy-vor/vectors/cohort_vectors.json`. It is a build-time generator, not
a suite obligation: `ontology/tests/harness.py`'s `main()` registry is this
repository's operative definition of an obligation, and an unregistered module under
`ontology/tests/` would be exactly the trap D102 closed. `ontology/tools/` is also
outside `symbolic_guard.py`'s scan roots, so the invariant 3.1 scanned-file count
stays unchanged (spec section 2.1 question three).

The narrower parity claim (spec section 2.1 question three, section 4.3's schema
notes). There is no Python `CohortDefinition` and there never will be: D105 rules
the hierarchy plane is Rust, and this build's own `AgentContext` has no cohort
notion. So these vectors replay the *substrate mechanism*
(`canonical_record_bytes`/`compute_record_attestation`) over `_ShimCohortRecord`, a
record built ONLY for this export, not a real component's captured call history.
The emitted file's own `claim` field says so, verbatim, so a reader of the committed
JSON never has to reconstruct that scope from this docstring, which may drift or be
deleted.

What is NOT reimplemented here (REQ-28). This file calls
`authorisation_record.canonical_record_bytes`, `authorisation_record.compute_
record_attestation`, `sink_attestation.canonical_bytes` and `sink_attestation.
compute_attestation` directly. It contains no local domain-separator constant, no
local sort-then-join loop over a collection field beyond what `_ShimCohortRecord`
itself is responsible for (exactly as `AgentContext.canonical_fields()` sorts its
own collections before returning them -- a record's own contractual job under
`canonical_record_bytes`'s documented interface, not a duplication of that
function's own encoding), and no local digest routine.

The shim record, and why it is here and nowhere else (REQ-28, spec section 2.1
question three). `_ShimCohortRecord` honours the two-method `AttestedRecord`
interface (`record_type()`, `canonical_fields()`) `authorisation_record.py`
requires. It is deliberately generic over its `record_type` tag (not hardcoded to
`RECORD_TYPE_COHORT_DEFINITION`) so the SAME class can build the REQ-32 case 7
cross-type pair (identical fields, two different tags) without a second shim class.

The cross-substrate case (REQ-32 case 8) and why it is not one of the `vectors`
array entries. `sink_attestation.canonical_bytes` has no record-type prefix and no
shared domain separator with `authorisation_record`'s substrate (that is precisely
the point of REQ-12's cross-substrate separation): its byte layout
("name=...\nparameters=...\n...") cannot be replayed through the generic
`AttestedRecord` interface the `vectors` array entries use on the Rust side
(`crates/hierarchy-vor/unit_tests/substrate_parity.rs`'s `build_generic_record` +
`canonical_record_bytes`, which is fixed by that already-committed test file and is
not this agent's to change). So the cross-substrate demonstration is computed here,
directly, by calling `sink_attestation`'s own functions over content comparable to
vector `V-1` (same authoriser id, the real cohort id as the declaration name, and
the real permitted actions as the declaration's parameter set), and the resulting
digest is asserted to differ from `V-1`'s own attestation before the file is
written. The result is recorded in the emitted file's top-level `cross_substrate_
check` block, deliberately outside `vectors`, with a `claim` field stating exactly
this reasoning so a reader of the JSON does not have to reconstruct it from this
docstring either.

The authoring mode (REQ-31) and why it writes nothing. `attest_real_cohort()`
computes the real `heimdall-dev` cohort's attestation under the REAL secret,
sourced the same way the Rust loader sources it (`HEIMDALL_COHORT_SECRET_FILE`
naming a path outside the repository working tree, section 2.2). It prints the
resulting digest for pasting into `crates/hierarchy-vor/src/cohort.rs`'s
`COMMITTED_ATTESTATION` constant (a later issue) and touches no file: the real
secret and the real attestation must never end up in `cohort_vectors.json` or
anywhere else this tool writes, because that file's whole point is to be replayable
on a machine that does NOT have the real secret (section 2.2's "what this does not
close" residual two, restated for the Python side).
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

from ontology.nornir import sink_attestation
from ontology.nornir.authorisation_record import (
    RECORD_TYPE_AGENT_CONTEXT,
    RECORD_TYPE_COHORT_DEFINITION,
    RECORD_TYPE_PROMOTION,
    canonical_record_bytes,
    compute_record_attestation,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTHORISATION_RECORD_PY = REPO_ROOT / "ontology" / "nornir" / "authorisation_record.py"
SINK_ATTESTATION_PY = REPO_ROOT / "ontology" / "nornir" / "sink_attestation.py"
VECTOR_FILE = REPO_ROOT / "crates" / "hierarchy-vor" / "vectors" / "cohort_vectors.json"

# REQ-42 (`.opencode/plans/rust-promotion-gate-spec.md`): the promotion-record
# vector file this ADDITIVE section emits, alongside (never in place of) the
# ten existing cohort vectors above. A distinct file, a distinct fixture
# secret (below) and a distinct shim class (`_ShimPromotionRecord`), so
# nothing in this section touches a single byte of the cohort export path.
PROMOTION_VECTOR_FILE = REPO_ROOT / "crates" / "hierarchy-vor" / "vectors" / "promotion_vectors.json"
PROMOTION_SCHEMA_VERSION = 1
EXPECTED_PROMOTION_VECTOR_COUNT = 5

SCHEMA_VERSION = 1

# REQ-32: a single named constant the exporter fails non-zero against, rather than
# an inline literal that could rot independently of the vectors actually built.
# Six single vectors (cases 1 to 6) plus two pairs (case 7's cross-type pair, case
# 9's mutated-field pair) = 10. Case 8 (cross-substrate) is deliberately NOT counted
# here: see the module docstring for why it lives in `cross_substrate_check`
# instead of the `vectors` array.
EXPECTED_VECTOR_COUNT = 10

# Section 2.2, mirrored from `crates/hierarchy-vor/src/authoriser.rs`'s
# `SECRET_PATH_ENV_VAR` and `MIN_SECRET_BYTES` exactly, so the authoring mode
# sources the real secret the same way the Rust loader does.
SECRET_PATH_ENV_VAR = "HEIMDALL_COHORT_SECRET_FILE"
MIN_SECRET_BYTES = 32

# The real heimdall-dev cohort's content (spec section 4.1's `cohort.rs` table,
# REQ-20). Fixed here, once, and used by BOTH `export_vectors` (vector V-1,
# attested under the FIXTURE secret) and `attest_real_cohort` (attested under the
# REAL secret): the same content, two different secrets, so a change to either
# function's use of it cannot silently drift from the other's.
REAL_COHORT_ID = "heimdall-dev"
REAL_PERMITTED_ACTIONS = ("action:git.commit", "action:git.push")
REAL_TRUST_CEILING = "TAINTED"
REAL_CONSEQUENTIAL_SINKS = ("sink:git.commit", "sink:git.push")
REAL_AUTHORISER_ID = "heimdall-dev-authoriser"

# NON-PRODUCTION. This secret exists only so every vector in `cohort_vectors.json`
# is replayable on a machine that does not, and must not, have the real
# `heimdall-dev` secret (section 2.2's mechanism-parity/real-verification split).
# It is committed deliberately, labelled as such in the emitted file itself
# (`fixture_secret_note`), and is never used by `attest_real_cohort`.
FIXTURE_SECRET = (
    b"NON-PRODUCTION fixture secret for cohort_vectors.json -- never the real "
    b"heimdall-dev secret, committed deliberately for vector replay parity"
)


# REQ-42: the promotion-record section's own NON-PRODUCTION fixture secret,
# on `FIXTURE_SECRET`'s own convention (same structure and same "never the
# real heimdall-dev secret" discipline, adapted to name promotion_vectors.json
# rather than cohort_vectors.json, exactly as that file's own committed
# fixture_secret_hex already fixes byte for byte -- this constant reproduces
# the already-committed `crates/hierarchy-vor/vectors/promotion_vectors.json`
# exactly, never a second, incompatible secret). Never used by
# `attest_real_cohort`, and never mixed with the cohort section's own
# `FIXTURE_SECRET` above.
PROMOTION_FIXTURE_SECRET = (
    b"NON-PRODUCTION fixture secret for promotion_vectors.json -- never the "
    b"real heimdall-dev secret, committed deliberately for vector replay "
    b"parity"
)


class ExporterError(RuntimeError):
    """Raised to abort the export loudly (never a partial file, never a silent drop)."""


class SecretRefusalError(RuntimeError):
    """Raised by the real-secret loader on any of REQ-14's refusal conditions. The
    message never contains a byte of the secret (REQ-18's discipline, mirrored)."""


# ---------------------------------------------------------------------------------
# The shim record (REQ-28). Defined here and nowhere else.
# ---------------------------------------------------------------------------------


class _ShimCohortRecord:
    """The exporter's own stand-in for a real `CohortDefinition`, honouring the
    two-method `AttestedRecord`-equivalent interface `authorisation_record.py`
    requires (`record_type()`, `canonical_fields()`). Defined here and nowhere else
    (REQ-28).

    Field order and per-field encoding mirror `AgentContext.canonical_fields()`
    (`ontology/yggdrasil/control_surface.py`) and Rust's
    `crate::types::CohortDefinition::canonical_fields()` exactly: `cohort_id`,
    `permitted_actions` (sorted, comma-joined), `trust_ceiling`,
    `consequential_sinks` (sorted, comma-joined), `authoriser` (empty string when
    absent). This class does not reimplement `canonical_record_bytes`'s own
    encoding (the domain separator, the `record_type=` prefix line, the newline
    join): those stay inside `authorisation_record.canonical_record_bytes`, called,
    never duplicated here. Sorting and joining a record's OWN collection fields
    before returning them is the record's contractual responsibility under that
    function's documented interface (see its docstring), exactly as
    `AgentContext.canonical_fields()` already does, so doing the same here is
    honouring the interface, not reimplementing the substrate.

    `record_type` is a constructor parameter, not hardcoded to
    `RECORD_TYPE_COHORT_DEFINITION`, so ONE shim class can build REQ-32 case 7's
    cross-type pair (identical fields under two different record-type tags)
    without a second shim class."""

    def __init__(
        self,
        cohort_id: str,
        permitted_actions,
        trust_ceiling: str,
        consequential_sinks,
        authoriser: "str | None" = None,
        *,
        record_type: str = RECORD_TYPE_COHORT_DEFINITION,
    ) -> None:
        self.cohort_id = cohort_id
        self.permitted_actions = list(permitted_actions)
        self.trust_ceiling = trust_ceiling
        self.consequential_sinks = list(consequential_sinks)
        self.authoriser = authoriser
        self._record_type = record_type

    def record_type(self) -> str:
        return self._record_type

    def canonical_fields(self) -> "tuple[tuple[str, str], ...]":
        return (
            ("cohort_id", self.cohort_id),
            ("permitted_actions", ",".join(sorted(self.permitted_actions))),
            ("trust_ceiling", self.trust_ceiling),
            ("consequential_sinks", ",".join(sorted(self.consequential_sinks))),
            ("authoriser", self.authoriser or ""),
        )


# ---------------------------------------------------------------------------------
# REQ-42 (`.opencode/plans/rust-promotion-gate-spec.md`): the promotion-record
# shim, additive and parallel to `_ShimCohortRecord` above, never sharing a
# class with it (the two record shapes have different field sets; `authoriser`
# is a constructor default here as it is there, and `record_type` is likewise
# a constructor parameter, not hardcoded, so the SAME class can build the two
# cross-type replay pairing vectors -- P-3, tagged promotion_record, and
# alongside a separately-built `_ShimCohortRecord` for P-4's cohort_definition
# side -- without a second shim class for the promotion side of the pairing).
# ---------------------------------------------------------------------------------


class _ShimPromotionRecord:
    """The exporter's own stand-in for a real `PromotionRecord` (which exists
    only in Rust, `crates/hierarchy-vor/src/promotion.rs`; no Python class for
    it exists or will, D105). Honours the same two-method `AttestedRecord`-
    equivalent interface `authorisation_record.py` requires
    (`record_type()`, `canonical_fields()`), on `_ShimCohortRecord`'s own
    pattern.

    Field order and per-field encoding match
    `.opencode/plans/rust-promotion-gate-spec.md` section 4.3's schema table
    exactly: `assertion_id`, `content_digest`, `promoted_to` (an opaque
    string here too, exactly as it is opaque in `crates/hierarchy-vor/`),
    `valid_from`, `valid_until` (both rendered as their plain decimal string,
    no separators), `authoriser` (empty string when absent). `attestation` is
    deliberately excluded from `canonical_fields()`, exactly as
    `_ShimCohortRecord` excludes it: it is the digest being computed or
    checked, not part of what it covers."""

    def __init__(
        self,
        assertion_id: str,
        content_digest: str,
        promoted_to: str,
        valid_from: int,
        valid_until: int,
        authoriser: "str | None" = None,
        *,
        record_type: str = RECORD_TYPE_PROMOTION,
    ) -> None:
        self.assertion_id = assertion_id
        self.content_digest = content_digest
        self.promoted_to = promoted_to
        self.valid_from = valid_from
        self.valid_until = valid_until
        self.authoriser = authoriser
        self._record_type = record_type

    def record_type(self) -> str:
        return self._record_type

    def canonical_fields(self) -> "tuple[tuple[str, str], ...]":
        return (
            ("assertion_id", self.assertion_id),
            ("content_digest", self.content_digest),
            ("promoted_to", self.promoted_to),
            ("valid_from", str(self.valid_from)),
            ("valid_until", str(self.valid_until)),
            ("authoriser", self.authoriser or ""),
        )


# ---------------------------------------------------------------------------------
# Small pure helpers.
# ---------------------------------------------------------------------------------


def _sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vector(
    vector_id: str,
    case: str,
    record: _ShimCohortRecord,
    *,
    attested: bool,
) -> dict:
    """Build one vector entry by calling the substrate's own functions, never
    reimplementing them (REQ-28, REQ-30)."""
    canonical_bytes = canonical_record_bytes(record)
    attestation = (
        compute_record_attestation(record, FIXTURE_SECRET) if attested else None
    )
    return {
        "id": vector_id,
        "case": case,
        "record_type": record.record_type(),
        "fields": [list(pair) for pair in record.canonical_fields()],
        "canonical_bytes_hex": canonical_bytes.hex(),
        "attestation": attestation,
    }


# ---------------------------------------------------------------------------------
# REQ-32: the nine named cases.
# ---------------------------------------------------------------------------------


def _build_vectors() -> list[dict]:
    vectors: list[dict] = []

    # Case 1: the real heimdall-dev cohort's exact content, attested under the
    # FIXTURE secret (never the real one). This is the vector
    # `real_cohort_content_matches_crate_types_cohort_definition_encoding`
    # (`crates/hierarchy-vor/unit_tests/substrate_parity.rs`) locates by its
    # `cohort_id` field and cross-checks against `crate::cohort`'s own constants.
    vectors.append(
        _vector(
            "V-1",
            "the real heimdall-dev cohort's exact content, attested under the "
            "fixture secret (never the real production secret)",
            _ShimCohortRecord(
                REAL_COHORT_ID,
                REAL_PERMITTED_ACTIONS,
                REAL_TRUST_CEILING,
                REAL_CONSEQUENTIAL_SINKS,
                REAL_AUTHORISER_ID,
            ),
            attested=True,
        )
    )

    # Case 2: both collections empty.
    vectors.append(
        _vector(
            "V-2",
            "both collections empty, pinning the empty-string encoding for an "
            "empty collection field (REQ-9)",
            _ShimCohortRecord(
                "vor-vector-empty-collections",
                (),
                "TAINTED",
                (),
                "vor-vector-test-authoriser",
            ),
            attested=True,
        )
    )

    # Case 3: collection members supplied unsorted, pinning the sort.
    vectors.append(
        _vector(
            "V-3",
            "collection members supplied unsorted, pinning that the record sorts "
            "(Python sorted()) before joining, matching Rust's Vec::sort() (REQ-9)",
            _ShimCohortRecord(
                "vor-vector-unsorted-members",
                ("action:zulu.op", "action:alpha.op", "action:mike.op"),
                "TAINTED",
                ("sink:zulu.op", "sink:alpha.op"),
                "vor-vector-test-authoriser",
            ),
            attested=True,
        )
    )

    # Case 4: non-ASCII collection members, pinning code-point order. UTF-8's byte
    # ordering agrees with Unicode code-point ordering for valid UTF-8, so Python's
    # sorted() and Rust's str Ord agree here too; this vector pins that rather than
    # leaving it asserted (REQ-9).
    vectors.append(
        _vector(
            "V-4",
            "non-ASCII collection members, pinning that Python's sorted() "
            "code-point order and Rust's str Ord over UTF-8 bytes agree (REQ-9)",
            _ShimCohortRecord(
                "vor-vector-non-ascii-members",
                (
                    "action:café.op",
                    "action:Ångström.op",
                    "action:日本語.op",
                    "action:Zebra.op",
                ),
                "TAINTED",
                ("sink:Ångström.op", "sink:café.op"),
                "vor-vector-test-authoriser",
            ),
            attested=True,
        )
    )

    # Case 5: a member containing a comma, pinning the inherited comma-join
    # encoding ambiguity (REQ-10). Not fixed here: fixing it would break every
    # existing AgentContext attestation. This vector's own case text records the
    # ambiguity rather than hiding it.
    vectors.append(
        _vector(
            "V-5",
            "a member containing a comma, pinning the inherited comma-join "
            "encoding ambiguity (REQ-10): this canonical encoding is NOT injective, "
            "and this vector demonstrates the shared behaviour rather than fixing it",
            _ShimCohortRecord(
                "vor-vector-comma-member",
                ("action:git.commit,extra", "action:git.push"),
                "TAINTED",
                ("sink:git.push",),
                "vor-vector-test-authoriser",
            ),
            attested=True,
        )
    )

    # Case 6: an unattested record (authoriser absent), pinning the `authoriser=`
    # empty-string encoding. No attestation is computed for this vector: an
    # unattested record carries none in the first place.
    vectors.append(
        _vector(
            "V-6",
            "authoriser absent, pinning the authoriser= empty-string encoding for "
            "an unattested record",
            _ShimCohortRecord(
                "vor-vector-unattested",
                ("action:git.commit",),
                "TAINTED",
                ("sink:git.commit",),
                None,
            ),
            attested=False,
        )
    )

    # Case 7: a cross-type pair. Identical fields, two different record-type tags,
    # demonstrating cross-type separation (REQ-12): the two records' canonical
    # bytes differ only in the `record_type=` line, and their attestations differ.
    cross_type_kwargs = dict(
        cohort_id="vor-vector-cross-type-content",
        permitted_actions=("action:git.commit",),
        trust_ceiling="TAINTED",
        consequential_sinks=("sink:git.commit",),
        authoriser="vor-vector-test-authoriser",
    )
    vectors.append(
        _vector(
            "V-7a",
            "cross-type pair (side A): identical fields to V-7b, tagged "
            "cohort_definition, demonstrating cross-type separation (REQ-12)",
            _ShimCohortRecord(**cross_type_kwargs, record_type=RECORD_TYPE_COHORT_DEFINITION),
            attested=True,
        )
    )
    vectors.append(
        _vector(
            "V-7b",
            "cross-type pair (side B): identical fields to V-7a, tagged "
            "agent_context, demonstrating cross-type separation (REQ-12)",
            _ShimCohortRecord(**cross_type_kwargs, record_type=RECORD_TYPE_AGENT_CONTEXT),
            attested=True,
        )
    )
    if vectors[-2]["canonical_bytes_hex"] == vectors[-1]["canonical_bytes_hex"]:
        raise ExporterError(
            "V-7a and V-7b's canonical bytes are identical: the cross-type pair "
            "must differ in the record_type= line (REQ-8, REQ-12)"
        )
    if vectors[-2]["attestation"] == vectors[-1]["attestation"]:
        raise ExporterError(
            "V-7a and V-7b share an attestation digest: cross-type separation is "
            "not demonstrated (REQ-12)"
        )

    # Case 9: a mutated-field pair, differing in exactly one field
    # (`trust_ceiling`), on which the negative control of REQ-34 rests.
    vectors.append(
        _vector(
            "V-9a",
            "mutated-field pair (base): trust_ceiling=TAINTED, on which REQ-34's "
            "negative control rests",
            _ShimCohortRecord(
                "vor-vector-mutated-field-base",
                ("action:git.commit",),
                "TAINTED",
                ("sink:git.commit",),
                "vor-vector-test-authoriser",
            ),
            attested=True,
        )
    )
    vectors.append(
        _vector(
            "V-9b",
            "mutated-field pair (mutated): trust_ceiling=TRUSTED, differing from "
            "V-9a in exactly this one field, on which REQ-34's negative control rests",
            _ShimCohortRecord(
                "vor-vector-mutated-field-base",
                ("action:git.commit",),
                "TRUSTED",
                ("sink:git.commit",),
                "vor-vector-test-authoriser",
            ),
            attested=True,
        )
    )
    if vectors[-2]["attestation"] == vectors[-1]["attestation"]:
        raise ExporterError(
            "V-9a and V-9b share an attestation digest despite differing in "
            "trust_ceiling: the mutated-field pair does not demonstrate a real "
            "mutation (REQ-32 case 9)"
        )

    return vectors


def _build_cross_substrate_check(cohort_vector: dict) -> dict:
    """REQ-32 case 8, REQ-12's cross-substrate half. Content comparable to `V-1`
    (same authoriser id, the real cohort id as the declaration name, the real
    permitted actions as the declaration's parameter set), attested through
    `sink_attestation`'s OWN functions under the SAME fixture secret, asserted to
    differ from `V-1`'s own attestation before this exporter ever writes a file.
    See the module docstring for why this lives outside the `vectors` array."""
    from ontology.nornir.sink_declaration import SinkDeclaration

    declaration = SinkDeclaration(
        name=REAL_COHORT_ID,
        parameters=frozenset(REAL_PERMITTED_ACTIONS),
        consequential_by_default=True,
        effect_primitive=None,
        authoriser=REAL_AUTHORISER_ID,
        attestation=None,
    )
    canonical_bytes = sink_attestation.canonical_bytes(declaration)
    attestation = sink_attestation.compute_attestation(declaration, FIXTURE_SECRET)

    if attestation == cohort_vector["attestation"]:
        raise ExporterError(
            "the cross-substrate attestation collides with V-1's own attestation: "
            "cross-substrate separation is not demonstrated (REQ-12)"
        )

    return {
        "claim": (
            "comparable content (the same authoriser id, the real cohort id as "
            "the declaration name, and the real permitted actions as the "
            "declaration's parameter set) attested through sink_attestation's own "
            "canonical encoding and domain separator, under the SAME fixture "
            "secret as V-1, yields a DIFFERENT digest than V-1's own attestation "
            "(asserted above, not merely stated here), demonstrating cross-"
            "substrate separation (REQ-12). This block is deliberately OUTSIDE the "
            "vectors array: sink_attestation's canonical byte layout carries no "
            "record_type prefix and shares no domain separator with "
            "authorisation_record's substrate, so it cannot be replayed through "
            "the generic AttestedRecord interface the vectors array entries use "
            "on the Rust side."
        ),
        "comparable_vector_id": "V-1",
        "sink_declaration_fields": {
            "name": declaration.name,
            "parameters": sorted(declaration.parameters),
            "consequential_by_default": declaration.consequential_by_default,
            "effect_primitive": declaration.effect_primitive,
            "authoriser": declaration.authoriser,
        },
        "sink_attestation_canonical_bytes_hex": canonical_bytes.hex(),
        "sink_attestation_attestation_hex": attestation,
    }


def build_vectors() -> dict:
    """Assemble the full vector document. Raises `ExporterError` (never emits a
    partial result) on a vector-count mismatch or a demonstration that failed to
    show the separation it claims (REQ-32)."""
    vectors = _build_vectors()

    if len(vectors) != EXPECTED_VECTOR_COUNT:
        raise ExporterError(
            f"built {len(vectors)} vector(s), expected {EXPECTED_VECTOR_COUNT} "
            f"(EXPECTED_VECTOR_COUNT); update the named constant only after "
            f"deliberately adding or removing a REQ-32 case, never silently"
        )

    cohort_vector = next(v for v in vectors if v["id"] == "V-1")
    cross_substrate_check = _build_cross_substrate_check(cohort_vector)

    return {
        "schema_version": SCHEMA_VERSION,
        "claim": (
            "substrate mechanism parity over a shim record (_ShimCohortRecord, "
            "ontology/tools/export_cohort_vectors.py); NOT a real Python cohort's "
            "call history, because no Python CohortDefinition exists or ever will "
            "(D105 rules the hierarchy plane is Rust; spec section 2.1 question "
            "three)"
        ),
        "generated_from": {
            "authorisation_record_py_sha256": _sha256_of(AUTHORISATION_RECORD_PY),
            "sink_attestation_py_sha256": _sha256_of(SINK_ATTESTATION_PY),
        },
        "fixture_secret_hex": FIXTURE_SECRET.hex(),
        "fixture_secret_note": (
            "NON-PRODUCTION fixture secret, committed deliberately; the real "
            "heimdall-dev secret is never in this repository"
        ),
        "expected_count": EXPECTED_VECTOR_COUNT,
        "vectors": vectors,
        "cross_substrate_check": cross_substrate_check,
    }


def _write_atomically(
    data: dict, target: Path, *, ensure_ascii: bool = False, prefix: str = ".cohort_vectors."
) -> None:
    """Write to a temp file in the same directory, then move into place (REQ-33):
    a partial file that happens to parse would be a silently narrowed parity claim.

    `ensure_ascii` and `prefix` are additive, optional parameters (REQ-42):
    the cohort export above never passes either, so its own call site
    (`export_vectors`) reproduces the original behaviour byte for byte
    (`ensure_ascii=False`, the original hardcoded temp-file prefix). Only the
    promotion export's own call site (`export_promotion_vectors`) passes
    `ensure_ascii=True`, matching the already-committed
    `promotion_vectors.json`'s own non-ASCII-escaped encoding exactly."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=prefix, suffix=".json.tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=ensure_ascii)
            f.write("\n")
        os.replace(tmp_name, target)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(tmp_name)
        raise


def export_vectors() -> dict:
    """Build every REQ-32 case, self-check the separation claims, and write the
    result atomically to `crates/hierarchy-vor/vectors/cohort_vectors.json`
    (REQ-29, REQ-33)."""
    data = build_vectors()
    _write_atomically(data, VECTOR_FILE)
    return data


# ---------------------------------------------------------------------------------
# REQ-42: the promotion-record vectors. Additive, parallel to the cohort
# section above, and written to a SEPARATE file
# (`crates/hierarchy-vor/vectors/promotion_vectors.json`) under a SEPARATE
# fixture secret (`PROMOTION_FIXTURE_SECRET`). Five cases (P-1 to P-5),
# matching the already-committed vector file's own `expected_count`: a
# well-formed record (P-1), a non-ASCII `assertion_id` (P-2), the two
# cross-type replay pairings of REQ-19 (P-3 promotion side, P-4 cohort side),
# and an unattested record pinning the empty-authoriser encoding (P-5).
# ---------------------------------------------------------------------------------

def _promotion_vector(
    vector_id: str,
    case: str,
    record,
    *,
    attested: bool,
) -> dict:
    """Build one promotion vector entry by calling the substrate's own
    functions, never reimplementing them, on `_vector`'s own pattern above."""
    canonical_bytes = canonical_record_bytes(record)
    attestation = (
        compute_record_attestation(record, PROMOTION_FIXTURE_SECRET) if attested else None
    )
    return {
        "id": vector_id,
        "case": case,
        "record_type": record.record_type(),
        "fields": [list(pair) for pair in record.canonical_fields()],
        "canonical_bytes_hex": canonical_bytes.hex(),
        "attestation": attestation,
    }


def _build_promotion_vectors() -> list[dict]:
    """The five REQ-42 promotion cases (P-1 to P-5), matching
    `crates/hierarchy-vor/vectors/promotion_vectors.json`'s own committed
    content exactly: this function's job is to prove those committed vectors
    CAN be regenerated from this exporter byte for byte, never to introduce a
    sixth case or to narrow one of the five."""
    vectors: list[dict] = []

    # P-1: a well-formed promotion record, attested under the (promotion-
    # section-specific) fixture secret.
    vectors.append(
        _promotion_vector(
            "P-1",
            "a well-formed promotion record, attested under the fixture secret "
            "(never the real production secret)",
            _ShimPromotionRecord(
                "vor-promotion-vector-well-formed",
                "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcd",
                "TRUSTED",
                1000,
                2000,
                "vor-promotion-vector-authoriser",
            ),
            attested=True,
        )
    )

    # P-2: a non-ASCII assertion_id, pinning UTF-8 byte-identical encoding on
    # both sides (REQ-9's discipline, applied to promotion records).
    vectors.append(
        _promotion_vector(
            "P-2",
            "a non-ASCII assertion_id, pinning UTF-8 byte-identical encoding on "
            "both sides (REQ-9 applied to promotion records)",
            _ShimPromotionRecord(
                "vor-promotion-vector-\u00e9\u00e8\u4e2d\u6587",
                "cafebabecafebabecafebabecafebabecafebabecafebabecafebabecafebab",
                "CANONICAL",
                0,
                9999999999,
                "vor-promotion-vector-authoriser",
            ),
            attested=True,
        )
    )

    # P-3 / P-4: the two cross-type replay pairings of REQ-19. P-3 is the
    # promotion side (tagged promotion_record); P-4 is the cohort side
    # (tagged cohort_definition, built through `_ShimCohortRecord`, never
    # through `_ShimPromotionRecord`, because the two record shapes genuinely
    # differ and a real PromotionRecord could never carry cohort_definition's
    # field set). Content deliberately differs between the two (a promotion
    # record and a cohort definition do not share a field set), so this
    # pairing demonstrates the record-TYPE-TAG barrier (the prefix in
    # `canonical_record_bytes`), not a same-content-different-tag pairing
    # (that narrower demonstration is `export_cohort_vectors`'s own V-7a/V-7b
    # pair above, over the cohort's own field set).
    vectors.append(
        _promotion_vector(
            "P-3",
            "cross-type replay pairing 1 of 2 (REQ-19, EC-18): this "
            "promotion_record's own attestation must NOT verify when presented "
            "as a cohort_definition's attestation, even under the same "
            "authoriser and the same secret",
            _ShimPromotionRecord(
                "vor-promotion-vector-cross-type",
                "deadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeefdeadbeef",
                "VOUCHED",
                500,
                600,
                "vor-promotion-vector-authoriser",
            ),
            attested=True,
        )
    )
    # `_promotion_vector` reads only `record.record_type()` and
    # `record.canonical_fields()` (via `canonical_record_bytes`), exactly like
    # `canonical_record_bytes` itself, so it works unchanged over a
    # `_ShimCohortRecord` too: no third, near-duplicate vector-building
    # function is needed for P-4's cohort-shaped side of the pairing.
    vectors.append(
        _promotion_vector(
            "P-4",
            "cross-type replay pairing 2 of 2 (REQ-19, EC-18): this "
            "cohort_definition's own attestation must NOT verify when presented "
            "as a promotion_record's attestation, even under the same "
            "authoriser and the same secret",
            _ShimCohortRecord(
                "vor-promotion-vector-cross-type-cohort",
                ("action:git.commit",),
                "TAINTED",
                ("sink:git.commit",),
                "vor-promotion-vector-authoriser",
            ),
            attested=True,
        )
    )
    if vectors[-2]["attestation"] == vectors[-1]["attestation"]:
        raise ExporterError(
            "P-3 and P-4's attestations collide: cross-type replay separation "
            "is not demonstrated (REQ-19)"
        )

    # P-5: an unattested promotion record (empty authoriser), pinning canonical
    # bytes only -- no attestation field emitted, on V-6's own pattern above.
    vectors.append(
        _promotion_vector(
            "P-5",
            "an unattested promotion record (empty authoriser), pinning "
            "canonical bytes only -- no attestation field emitted",
            _ShimPromotionRecord(
                "vor-promotion-vector-unattested",
                "0000000000000000000000000000000000000000000000000000000000000f",
                "TAINTED",
                1,
                2,
                None,
            ),
            attested=False,
        )
    )

    return vectors


def build_promotion_vectors() -> dict:
    """Assemble the full promotion-vector document (REQ-42). Raises
    `ExporterError` (never emits a partial result) on a vector-count mismatch
    or a demonstration that failed to show the separation it claims, on
    `build_vectors`'s own pattern above."""
    vectors = _build_promotion_vectors()

    if len(vectors) != EXPECTED_PROMOTION_VECTOR_COUNT:
        raise ExporterError(
            f"built {len(vectors)} promotion vector(s), expected "
            f"{EXPECTED_PROMOTION_VECTOR_COUNT} "
            f"(EXPECTED_PROMOTION_VECTOR_COUNT); update the named constant only "
            f"after deliberately adding or removing a REQ-42 case, never silently"
        )

    return {
        "schema_version": PROMOTION_SCHEMA_VERSION,
        "claim": (
            "substrate mechanism parity over a shim promotion record "
            "(_ShimPromotionRecord, ontology/tools/export_cohort_vectors.py's "
            "additive promotion-record emission section, REQ-42); NOT a real "
            "Python PromotionRecord's call history, because no Python "
            "PromotionRecord class exists or will (D105 rules the hierarchy "
            "plane is Rust; spec section 4.4)"
        ),
        "generated_from": {
            "authorisation_record_py_sha256": _sha256_of(AUTHORISATION_RECORD_PY),
        },
        "fixture_secret_hex": PROMOTION_FIXTURE_SECRET.hex(),
        "fixture_secret_note": (
            "NON-PRODUCTION fixture secret, committed deliberately; the real "
            "heimdall-dev secret is never in this repository"
        ),
        "expected_count": EXPECTED_PROMOTION_VECTOR_COUNT,
        "vectors": vectors,
    }


def export_promotion_vectors() -> dict:
    """Build every REQ-42 promotion case, self-check the separation claim, and
    write the result atomically to
    `crates/hierarchy-vor/vectors/promotion_vectors.json` (REQ-29, REQ-33's
    own atomic-write discipline, reused via `_write_atomically`, never a
    second implementation). Additive: never touches `VECTOR_FILE`
    (`cohort_vectors.json`) or any of the ten existing cohort vectors."""
    data = build_promotion_vectors()
    _write_atomically(
        data, PROMOTION_VECTOR_FILE, ensure_ascii=True, prefix=".promotion_vectors."
    )
    return data


# ---------------------------------------------------------------------------------
# REQ-31: the authoring mode. Sources the REAL secret the same way the Rust loader
# does, computes the REAL cohort's attestation under it, prints it, and writes
# NOTHING to disk.
# ---------------------------------------------------------------------------------


def _strip_one_trailing_line_ending(raw: bytes) -> bytes:
    """REQ-17, mirrored: strips exactly one trailing line ending (`\\n` or
    `\\r\\n`) and nothing else."""
    if raw.endswith(b"\r\n"):
        return raw[:-2]
    if raw.endswith(b"\n"):
        return raw[:-1]
    return raw


def _load_real_secret() -> bytes:
    """Sources the real secret exactly the way
    `crates/hierarchy-vor/src/authoriser.rs::load_trusted_set_from_env` /
    `load_trusted_set_from_path` do (section 2.2), refusing fail closed on the
    same conditions REQ-14 lists. Raises `SecretRefusalError` on every refusal;
    never falls back to a default and never logs a byte of the secret (REQ-18)."""
    path_value = os.environ.get(SECRET_PATH_ENV_VAR, "")
    if not path_value:
        raise SecretRefusalError(
            f"{SECRET_PATH_ENV_VAR} is not set, or is set to an empty value; "
            f"refusing rather than falling back to a default secret path "
            f"(REQ-14 case 1)"
        )

    path = Path(path_value)

    # Case 2: the path must exist and be a regular file.
    try:
        st = path.stat()
    except OSError as exc:
        raise SecretRefusalError(
            f"{path} does not exist, or its metadata could not be read ({exc}); "
            f"refusing (REQ-14 case 2)"
        ) from exc
    if not stat.S_ISREG(st.st_mode):
        raise SecretRefusalError(
            f"{path} exists but is not a regular file; refusing (REQ-14 case 2)"
        )

    # Case 3 / REQ-15: refuse a path resolving inside the repository working
    # tree. This is a development-time guard, not a deployment security control
    # (section 2.2 residual two): it exists so this authoring tool cannot be
    # pointed at a source-tree-constant secret by mistake.
    resolved = path.resolve()
    if resolved == REPO_ROOT or REPO_ROOT in resolved.parents:
        raise SecretRefusalError(
            f"{path} resolves inside the repository working tree; refusing "
            f"(REQ-14 case 3, REQ-15; a development-time guard, not a deployment "
            f"security control)"
        )

    # Case 4 and 5 / REQ-16: Unix permission bits, or their absence, refused
    # rather than silently skipped.
    if os.name == "posix":
        mode = st.st_mode
        if mode & (stat.S_IRWXG | stat.S_IRWXO):
            raise SecretRefusalError(
                f"{path} grants group or other access "
                f"(mode {stat.S_IMODE(mode):o}); refusing (REQ-14 case 4, REQ-16)"
            )
    else:
        raise SecretRefusalError(
            "this platform provides no Unix permission metadata; refusing "
            "rather than silently skipping the permissions check, because a "
            "skipped check is the fail-open shape (REQ-14 case 5, REQ-16)"
        )

    # Case 7: the file could not actually be read.
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise SecretRefusalError(
            f"{path} could not be read ({exc}); refusing (REQ-14 case 7)"
        ) from exc

    # Case 6 / REQ-17: strip exactly one trailing line ending, then refuse a
    # secret shorter than MIN_SECRET_BYTES or entirely whitespace.
    stripped = _strip_one_trailing_line_ending(raw)
    if len(stripped) < MIN_SECRET_BYTES or stripped.isspace():
        raise SecretRefusalError(
            f"the secret at {path} is shorter than {MIN_SECRET_BYTES} bytes "
            f"after stripping a single trailing line ending, or is entirely "
            f"whitespace; refusing (REQ-14 case 6, REQ-17)"
        )

    return stripped


def _real_cohort_record() -> _ShimCohortRecord:
    """The real heimdall-dev cohort's content (spec section 4.1's `cohort.rs`
    table), built through the SAME shim class every vector uses, so the authoring
    mode exercises the identical encoding path REQ-28 requires everywhere else."""
    return _ShimCohortRecord(
        REAL_COHORT_ID,
        REAL_PERMITTED_ACTIONS,
        REAL_TRUST_CEILING,
        REAL_CONSEQUENTIAL_SINKS,
        REAL_AUTHORISER_ID,
    )


def attest_real_cohort() -> int:
    """REQ-31's authoring mode: computes the real heimdall-dev cohort's
    attestation under the REAL secret and prints it for pasting into
    `crates/hierarchy-vor/src/cohort.rs`'s `COMMITTED_ATTESTATION` constant. Writes
    nothing to disk: neither the secret nor the resulting attestation is ever
    written into `cohort_vectors.json` or anywhere else. Returns 1 and prints a
    refusal reason (never the secret) on any of REQ-14's conditions; returns 0 and
    prints the 64-hex-character digest on success."""
    try:
        secret = _load_real_secret()
    except SecretRefusalError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1

    record = _real_cohort_record()
    attestation = compute_record_attestation(record, secret)
    print(
        "Real heimdall-dev cohort attestation, computed under the secret named by "
        f"{SECRET_PATH_ENV_VAR} (paste into cohort.rs's COMMITTED_ATTESTATION):"
    )
    print(attestation)
    return 0


def main(argv: "list[str] | None" = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Export Vor's cohort golden vectors, or (with --attest-real-cohort) "
            "run the out-of-band authoring mode that prints the real cohort's "
            "attestation and writes nothing."
        )
    )
    parser.add_argument(
        "--attest-real-cohort",
        action="store_true",
        help=(
            "REQ-31's authoring mode: compute and print the real heimdall-dev "
            "cohort's attestation under the real secret. Never writes to disk."
        ),
    )
    args = parser.parse_args(argv)

    if args.attest_real_cohort:
        return attest_real_cohort()

    try:
        data = export_vectors()
    except ExporterError as exc:
        print(f"EXPORT FAILED: {exc}", file=sys.stderr)
        return 1

    print(
        f"Exported {len(data['vectors'])} vector(s) to "
        f"{VECTOR_FILE.relative_to(REPO_ROOT)}"
    )
    print(
        f"  authorisation_record.py sha256: "
        f"{data['generated_from']['authorisation_record_py_sha256']}"
    )
    print(
        f"  sink_attestation.py sha256:     "
        f"{data['generated_from']['sink_attestation_py_sha256']}"
    )

    # REQ-42: the additive promotion-record export, run in the same
    # invocation, alongside (never in place of) the cohort export above.
    try:
        promotion_data = export_promotion_vectors()
    except ExporterError as exc:
        print(f"PROMOTION VECTOR EXPORT FAILED: {exc}", file=sys.stderr)
        return 1

    print(
        f"Exported {len(promotion_data['vectors'])} promotion vector(s) to "
        f"{PROMOTION_VECTOR_FILE.relative_to(REPO_ROOT)}"
    )
    print(
        f"  authorisation_record.py sha256: "
        f"{promotion_data['generated_from']['authorisation_record_py_sha256']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
