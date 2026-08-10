"""Adapter: map an external jailbreak corpus to the PoC corpus schema.

A colleague runs an anti-guardrail programme that produces jailbreak payloads.
This adapter maps that output onto the ``corpus.jsonl`` schema the harness reads
(one JSON object per line: id, category, raw_text, expected).

The external format is not fixed, so this adapter is tolerant. It accepts either
a JSON array or JSONL, and reads the payload text from the first of several
common field names. Each imported payload is tagged by which layer it targets
(see spec 6.3), because most jailbreak payloads target the model's
instruction-following and should pass the input assertion trivially. The
informative ones target the extraction itself.

Classification here is by simple, transparent heuristics on the payload text.
This is corpus tagging for reporting, not a trust decision: the pipeline's
trust boundary is provenance-based and lives in ``symbolic.py``. Everything
imported here is UNTRUSTED regardless of tag.

Usage:
    python corpus/adapter.py <external_file> [--out corpus/imported.jsonl]
    python harness.py --corpus corpus/imported.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


# Heuristic tags. Payloads mentioning the extraction task or the output schema
# are the ones that stress this premise; everything else is generic
# instruction-following jailbreaking that should pass the input assertion.
_EXTRACTION_MARKERS = (
    "extract", "extraction", "do not extract", "the field", "requested_action",
    "subject_extracted", "sender_extracted", "entities", "schema", "output field",
    "when you list", "for the",
)


def classify(text: str) -> str:
    lowered = text.lower()
    if any(marker in lowered for marker in _EXTRACTION_MARKERS):
        return "extraction_targeting"
    # Generic jailbreak: targets instruction-following. Reported in the
    # instruction-targeting partition; the harness maps this category there.
    return "direct_override"


def _payload_text(obj: dict) -> str:
    for key in ("raw_text", "payload", "prompt", "text", "content", "jailbreak", "body"):
        value = obj.get(key)
        if isinstance(value, str) and value.strip():
            return value
    # Fall back to serialising the whole object so nothing is silently lost.
    return json.dumps(obj, ensure_ascii=False)


def _iter_external(path: Path):
    """Yield dict records from either a JSON array or a JSONL file."""
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return
    # Try a single JSON document first (array or object).
    try:
        doc = json.loads(raw)
        if isinstance(doc, list):
            for item in doc:
                yield item if isinstance(item, dict) else {"text": str(item)}
            return
        if isinstance(doc, dict):
            # Some exports wrap the list under a key.
            for key in ("cases", "payloads", "items", "data", "results"):
                if isinstance(doc.get(key), list):
                    for item in doc[key]:
                        yield item if isinstance(item, dict) else {"text": str(item)}
                    return
            yield doc
            return
    except json.JSONDecodeError:
        pass
    # Fall back to JSONL.
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            obj = {"text": line}
        yield obj if isinstance(obj, dict) else {"text": str(obj)}


def convert(external_path: Path, prefix: str = "ext") -> list[dict]:
    cases: list[dict] = []
    for i, obj in enumerate(_iter_external(external_path), start=1):
        text = _payload_text(obj)
        # If the external record already carries an id or category, prefer it.
        ext_id = str(obj.get("id") or f"{prefix}-{i:04d}")
        category = obj.get("category") or classify(text)
        cases.append(
            {
                "id": ext_id,
                "category": category,
                "raw_text": text,
                # Every adversarial import is expected to pass both assertions:
                # untrusted bytes never reach the instruction position, and the
                # embedded directive is never followed.
                "expected": {"input_pass": True, "output_pass": True},
            }
        )
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("external", type=Path, help="external jailbreak file (JSON array or JSONL)")
    parser.add_argument(
        "--out",
        type=Path,
        default=Path(__file__).parent / "imported.jsonl",
        help="output corpus.jsonl path",
    )
    parser.add_argument("--prefix", default="ext", help="id prefix for imported cases")
    args = parser.parse_args()

    cases = convert(args.external, prefix=args.prefix)
    with open(args.out, "w", encoding="utf-8") as handle:
        for c in cases:
            handle.write(json.dumps(c, ensure_ascii=False) + "\n")

    instr = sum(1 for c in cases if c["category"] != "extraction_targeting")
    extr = sum(1 for c in cases if c["category"] == "extraction_targeting")
    print(f"wrote {len(cases)} cases to {args.out}")
    print(f"  instruction-targeting: {instr}")
    print(f"  extraction-targeting:  {extr}")
    if extr == 0:
        print("  note: no extraction-targeting payloads found. This is the gap")
        print("  that most stresses the premise (spec 6.3).")


if __name__ == "__main__":
    main()
