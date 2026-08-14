# Heimdall: Third Response, Re-review of the D70 Guard Fixes

**Author:** adversarial reviewer (repository-access round 3)
**Date:** August 2026
**Version:** 1.0
**Reads with:** `review-response-2.md` (the second review, whose two findings D70 answered), commit `63b421d` (D70, under review), and the follow-up fix committed with this report (D71)

---

## 1. What this is and how it was done

The team states the two findings from the second review (`review-response-2.md`: the 3.1 guard missing indirect model calls, and the 3.1 obligation having no negative control) are fixed. This is a full re-review from scratch. I did not trust the "fixed" claim or the commit message. I read the D70 diff, ran the harness, ran the two reported findings back through the guard to confirm closure, then wrote fresh evasion probes the team had not seen to test whether the fix holds against the whole class it claims to cover.

Result: both reported findings are genuinely closed. But the same probing that confirmed them found a third gap, of the exact kind the project is built to avoid, and I have fixed it in the follow-up committed alongside this report (D71).

---

## 2. The two second-review findings are genuinely closed

### 2.1 Indirect model calls are now caught (finding 3.1 of the second review)

Verified against `_scan_module` directly. All four bypasses the second review named are now caught:

- `importlib.import_module("mlx_lm")`: CAUGHT (dynamic-import call node).
- `__import__("openai")`: CAUGHT.
- `requests.post("https://api.openai.com")`: CAUGHT (network-module import).
- `urllib.request.urlopen(...)` and `httpx.post(...)`: CAUGHT.

I also tried to defeat the extension, and the common evasions hold: aliased `import requests as r`, `from requests import post`, `from importlib import import_module`, aliased `importlib as il`, and `http.client`/`socket` are all caught. The dynamic-import detection keys on the call target, so aliasing the module does not evade it.

### 2.2 The negative control now runs inside the suite (finding 3.2 of the second review)

Verified. `control_check()` exists in `symbolic_guard.py` and is called by `run_symbolic_guard` before it trusts a clean scan. It plants each violation class (direct import, from-import, dynamic import, inference HTTP, model subprocess) and asserts each is caught, and plants three benign controls (graph-DB driver, store binding, "model" comment) and asserts none is flagged. The harness prints a PASS line for it, and I confirmed `control_check()` returns no failures on the current tree. This closes the discipline gap: the guard now proves it bites inside the suite, not only in a commit message, matching the 8.3 pattern the second review pointed to.

Both fixes are real. This is a good remediation of what was reported.

---

## 3. New finding: the network detection was still a blacklist, and missed most egress (fixed here as D71)

### 3.1 What was wrong

D70's commit message says the fix "forbids the whole class rather than blacklisting model hostnames". The invariant 3.1 acceptance clause said "no outbound network call (any import of `requests`/`httpx`/`urllib`/`http`/`socket` and the like)". Both claim whole-class coverage. The code did not deliver it. `NETWORK_MODULE_ROOTS` was an enumerated set of about 10 module names, and `_network_root` flagged an import only if its root was in that set. So the network detection was a blacklist of module names, which is the same shape as a blacklist of hostnames: it fails on the next name not listed.

I confirmed the miss by probing egress modules outside the set. All of these were MISSED by the D70 guard:

- `boto3` (AWS Bedrock hosted inference) and `google` (Vertex AI / Gemini), the two most likely hosted-inference SDKs, neither needing a listed network import.
- `pycurl`, `treq` and any third-party HTTP client.
- `smtplib`, `ftplib`, `telnetlib`, `poplib`, `imaplib`, `nntplib`, `xmlrpc.client`: stdlib egress.
- `ssl`, `asyncio`, `webbrowser`, `ctypes`: further egress or FFI-to-egress paths.

This is invariant 3.5's blacklist trap reproduced one layer over, on the guard that exists specifically to enforce the anti-blacklist discipline. A hosted-inference call via `boto3` on the authorisation path would have passed the guard clean, which is precisely the indirect model call the invariant forbids.

### 3.2 The fix (D71)

Enforcement is inverted from a blacklist to a known-good allowlist. I first scanned the real authorisation path and found it imports only 12 module roots, all benign standard library plus the graph-DB substrate: `__future__`, `collections`, `dataclasses`, `email`, `enum`, `json`, `pathlib`, `re`, `sys`, `typing`, `neo4j`, `memgraph_store`. An allowlist is therefore feasible without false positives.

`ALLOWED_IMPORT_ROOTS` is now the enforcement boundary: any absolute import whose root is not on it is a violation. Relative (intra-package) imports are exempt. Dynamic import and model subprocesses are still caught at the call node. The forbidden and network sets are kept only to produce a more specific message for the obvious cases; they are no longer the boundary. This forbids the whole indirect-egress class by construction, which is what D70 claimed but did not do.

The allowlist has the correct polarity for this project (invariant 3.5): safety is earned by a positive match, and an unlisted import is a violation rather than a silent pass, so a new dependency is a deliberate trust-boundary decision made in review.

### 3.3 Verification of the fix

- The real tree stays clean: `scan()` returns zero violations, because the 12 real import roots are all allowlisted.
- Every previously-missed egress module is now caught: `boto3`, `google`, `pycurl`, `smtplib`, `ftplib`, `ssl`, `ctypes`, `telnetlib`, `xmlrpc.client`, `poplib`, `asyncio`, `webbrowser` all flag.
- Everything the second-review fix caught still catches: direct model imports, from-imports, dynamic import, `requests`/`httpx`, model subprocess.
- Benign imports and relative imports stay clean: `json`, `re`, `dataclasses`, `neo4j`, `memgraph_store`, `typing`, `from . import ...`, `from ..yggdrasil.core import ...` and "model" comments are all unflagged.
- The negative control gains two unlisted-egress probes (`boto3`, `smtplib`) so the suite proves the allowlist bites, not just the enumerated names.
- End-to-end: planting `import ssl` into a real authorisation-path file (`ontology/nornir/assertions.py`) makes the harness report a CRITICAL guard violation, and the tree is clean again after restore. This proves the harness obligation, not just the unit function, catches an egress path the old blacklist missed.

The suite remains RED for one reason only, the known false-inert 1/16 (D67-fix, open), exactly as before. The guard obligation passes with the strengthened control.

---

## 4. Documentation brought back into line

Per the currency rule, the claims that overreached are corrected to match the artifact:

- Invariant 3.1 acceptance now describes allowlist enforcement and states plainly that the earlier enumerated network blacklist was the 3.5 trap, fixed in D71.
- `symbolic_guard.py` module docstring and the `NETWORK_MODULE_ROOTS` comment now say the network set is only for messaging and is not the boundary.
- `DECISIONS.md` adds D71 and annotates D70 that its "whole class" claim was not true in the artifact and is superseded on the network dimension.
- `STATUS.md` records the third review and the allowlist inversion, and the decision count is updated to 71.

---

## 5. Verdict

The team's D70 work genuinely closed both second-review findings: indirect model calls (dynamic import, HTTP to a listed endpoint) are caught, and the guard now carries a negative control that runs in the suite. That is a correct fix of what was reported.

The gap that remained was in the part D70 described most confidently: the "whole class" network claim was, in the code, a ten-name blacklist that missed `boto3`, `google`, `smtplib`, `ctypes` and every other egress module not enumerated. It is now an allowlist and forbids the class by construction (D71), verified against a fresh probe battery and end to end in the harness.

The pattern across three reviews is worth naming, because it is the useful signal here: each round the claim layer has run slightly ahead of the artifact ("static analysis in CI" with no CI; "the whole class" with an enumerated list). The fixes have been real each time, but the wording has consistently claimed a little more than the code did. The allowlist inversion removes the specific instance; the general lesson is that a guard's coverage claim should be stated as what it enforces (an allowlist of known-good), not as what it forbids (a list that is always one name short).

No new open finding remains on the 3.1 guard after D71. The load-bearing invariant is now machine-checked by an allowlist with a negative control, on the authorisation path, with the honest caveat that there is still no CI running it and that authoring provenance (a model that drafted a rule a human pasted in) is a separate, acknowledged, unclosed hole.

---

## 6. Residual items (unchanged, correctly open, not introduced here)

- **No CI.** The guard and harness run only when a human runs them. Wiring CI is the obvious next step and would make all the checks, including this guard, run on push.
- **False-inert 1/16.** Reduced by D69, not closed; D67-fix is the open design problem and must not be another regex widening.
- **Authoring provenance.** No import or call scan can detect a model that drafted a rule pasted in by hand. Acknowledged in the 3.1 clause and D68.
- **Gate declaration schema, cross-batch default mode, origin-trust granularity.** All still open and documented in `DECISIONS.md` consistency check 5, not touched by this round.
