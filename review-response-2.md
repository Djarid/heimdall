# Heimdall: Second Response, Re-review After Remediation

**Author:** adversarial reviewer (repository-access round 2)
**Date:** August 2026
**Version:** 1.0
**Reads with:** `review-response.md` (the first repository-access review), commit `494dc59` (D68, D69, the remediation under review), `NEUROSYMBOLIC_FILTER_INVARIANTS.md`, `DECISIONS.md`, `STATUS.md`

---

## 1. What this is and how it was done

The project lead states the issues from the first repository-access review are remediated. This is a full re-review carried out from scratch. Every claim was checked against the current artifact and a live run, not against the earlier findings and not against the commit message. Where the remediation commit asserts a behaviour ("verified to bite", "3/12 to 1/16"), that behaviour was reproduced independently rather than taken on trust.

The method: read the diff of the remediation commit `494dc59`, read the new and changed code in full, ran the harness, wrote fresh adversarial probes the author had not seen and tested the new AST guard against planted inputs and evasion patterns.

The short version: the remediation is real and largely good-faith. The two headline gaps are genuinely addressed, the coverage false precision is gone from code and docs and the false-inert rate dropped. But the re-review found three new issues, one of which is a bypass in the new guard that maps directly onto the invariant's own wording, and one of which is a discipline failure the project's own conventions forbid.

---

## 2. What was genuinely fixed (verified, not assumed)

### 2.1 Invariant 3.1 now has an executable guard, and it bites

`ontology/nornir/symbolic_guard.py` exists and is wired as a fatal harness obligation (`run_symbolic_guard`, `harness.py`). It is a real AST scan, not a grep. Verified independently:

- Baseline is clean: `scan()` returns no violations on the current tree.
- Scope is correct: 27 authorisation-path files, `poc/symbolic.py` included, `poc/neural.py` and `e2e_harness.py` excluded.
- It bites. Planted `import mlx_lm`, `from mlx_lm import load`, `import openai`, `from anthropic import ...`, `import torch` and a `subprocess.run(["ollama", ...])` shell-out are each caught (a five-import plus subprocess set).
- It does not false-positive: `import neo4j`, `from neo4j import GraphDatabase`, a benign `from ontology.yggdrasil import load` and a plain "model" comment are each clean. This is the exact discrimination that justifies AST over grep, and it holds.

The acceptance clause in `NEUROSYMBOLIC_FILTER_INVARIANTS.md:43` is corrected honestly: it now says the AST check exists and runs in the harness, and states plainly that there is no CI, so nothing runs it on commit or push. The earlier overclaim of "static analysis in CI" and "the PoC's AST check" is gone. This is a straight, honest fix of the first review's headline finding.

### 2.2 The false-inert break was a rule-set asymmetry, and the fix ports the existing discipline

The first review found that only the communications inert rule carried a "no imperative" guard, and the scheduling, finance and publication inert rules were bare keyword matches. Verified in the diff: `carries_imperative_or_consequence` is promoted to `rules.py` and applied in all four domains' inert rules (`communications.py`, `finance.py`, `scheduling.py`, `publication.py`). This is applying the rule set's own existing discipline consistently, not a keyword blacklist, so it does not breach invariant 3.5.

The measured effect is real. The harness now reports 1/16 false-inert, down from 3/12. The three cases the first review named (`fi-13`, `fi-14`, `fi-15`) now route to review rather than typing inert.

### 2.3 The corpus growth is honest, and the residual is left red

This is the strongest part of the remediation. After porting the guard, the author added four fresh cases (`fi-16` to `fi-19`) that the guard was not tuned against, to test for circularity. Three are caught. One, `fi-19` (a passively-phrased standing order), still types inert, so the suite is left RED and D67-fix stays OPEN. The corpus note for `fi-19` states this plainly and calls it the G2 point demonstrated in the artifact: a self-authored corpus tuned to zero is re-opened by a fresh probe, so the rate is a lower bound. This is exactly the honesty the project's conventions call for.

### 2.4 The coverage false precision is gone

Verified: no live "94.7%" remains in code or the outcome docs. `harness.py` now computes a Wilson interval (`_wilson_interval`) and prints "36/38 classified to a known type (95% Wilson interval 83 to 99 percent)". The three remaining textual "94.7 percent" mentions are all in the negating context ("not 94.7 percent, which is false precision"), which is correct usage. `ontology/OUTCOME.md`, `STATUS.md` and the invariants doc are updated.

---

## 3. New findings from this re-review

### 3.1 The 3.1 guard misses indirect model calls, which the invariant explicitly covers (medium-high)

Invariant 3.1's own text (`NEUROSYMBOLIC_FILTER_INVARIANTS.md:39`) requires "no call to any language model, **direct or indirect**", and the acceptance clause names "no **inference call**". The guard catches direct imports and model-runner subprocesses. It misses two indirect paths, both verified against the actual `_scan_module`:

- **Dynamic import.** `importlib.import_module("mlx_lm")` and `__import__("openai")` are both MISSED. These are the textbook indirect import, and "direct or indirect" is the invariant's own wording.
- **HTTP call to a hosted inference endpoint.** `requests.post("https://api.openai.com/v1/chat", ...)`, `urllib.request.urlopen("https://api.anthropic.com")` and `httpx.post(...)` are all MISSED. This is the most likely way a symbolic module would actually reach a model without importing a client SDK, and it is precisely the "call an inference endpoint" case the acceptance clause claims to cover. A hosted-model call needs no forbidden import at all, so the import-centred guard cannot see it.

The guard is genuinely useful against the accidental or careless case (a developer importing `mlx_lm`). It does not hold against the case the invariant is written to exclude. The acceptance clause should either narrow its own wording to "no model-client import or model-runner subprocess" (honest about what the guard does), or the guard should add egress detection on the authorisation path. Given invariant 3.8 already promises Fenrir has no network egress and the symbolic layer is not the tainted reader, a defensible position is that the symbolic packages should make no outbound HTTP call at all, which is AST-detectable and would close the endpoint gap without a blacklist of hostnames.

### 3.2 The 3.1 guard has no negative control in the suite, which the project's own discipline mandates (medium)

This is a discipline failure, not a code bug, and it matters because it is the exact class of gap the first review was about: a check described as enforced that is not enforced where it counts.

Invariant 3.10 and `AGENTS.md` state the rule: "a pass proves nothing without a control that would fail." The harness honours this everywhere it matters. The 8.3 soundness check registers a deliberately-unsound rule and confirms it is caught (`harness.py:442`). The 3.6 Gjoll gate carries a mandatory unsafe control. The 3.5 fail-closed property test fails against an eager catch-all.

The new 3.1 obligation (`run_symbolic_guard`) has no such control. It calls `scan()`, and reports PASS when the result is empty. It never plants a violation and confirms the guard catches it. The "verified to bite" evidence lives in the commit message and in a manual test the reviewer ran, not in the suite. Consequences:

- A future regression that neuters the guard (an exception swallowed in `_scan_module`, a scope list that silently drops files, an allowlist that grows too broad) would leave the obligation reporting PASS with nothing scanned meaningfully, and the suite would stay green on that line.
- By the project's own standard ("a soundness suite that cannot catch an unsound rule is theatre", `harness.py:459`), a guard obligation that never demonstrates it catches a planted model import is theatre in the same sense.

The fix is small and matches the existing pattern: in `run_symbolic_guard`, scan a temporary file containing `import mlx_lm`, assert it is caught, then proceed with the real scan, exactly as 8.3 injects and catches its unsound rule.

### 3.3 The recorded false-inert rate is a lower bound, and a fresh probe already beats it (informational, correctly disclosed)

The harness reports 1/16, and the corpus note for `fi-19` correctly calls this a lower bound. Confirming that disclosure is not merely rhetorical: a fresh probe written for this re-review found a second uncaught case the corpus does not contain. "this article describes a script that quietly forwards all invoices" types as `pub:informational_publication` (inert), skipping gate and review. The mechanism is that `carries_imperative_or_consequence` matches `forward (the|all)` but not the third-person "forwards all", and more generally misses passive and descriptive consequence phrasing ("the standing order is set to go out", "a script that forwards the invoices" both return False).

This is not a failure of the remediation. It is the predicted behaviour, and the author disclosed it in advance. It is recorded here for one reason: any statement of the rate must say "at least 1/16 on this corpus, higher on fresh probes", never "1/16". The current docs do say reduced-not-closed and lower-bound, so this finding confirms the disclosure rather than contradicting it. It also reinforces that D67-fix must be the design change, not another widening of the regex, which is the treadmill invariant 3.5 forbids.

---

## 4. Findings from the first review that were correctly left open, not silently dropped

The remediation did not claim to fix everything, and the docs are honest about what remains. Verified that these are documented as open, not quietly closed:

- **Gate declarations have no schema or validation.** `gjoll.py` still takes a raw `dict` for `consumes` with no schema, validation or stub. `DECISIONS.md` consistency check 5 now states this explicitly ("the gate's declarations have no schema or validation, not even a stub"). Correctly open.
- **Cross-batch guarantee holds only in persistent mode.** Unchanged, and now stated in the same consistency check ("the cross-batch guarantee holds only in the persistent mode the default suite does not run"). Correctly open.
- **No CI.** Stated plainly in both the 3.1 acceptance clause and consistency check 5 ("there is no CI, so even the checks that exist run only when a human runs them"). Correctly open.
- **D55 property test scope.** The fail-closed property test remains focused on the communications catch-all. The inert-rule co-signal case is now covered by the false-inert corpus obligation rather than by a property test, which is a reasonable division. Not a regression.

Leaving these open and documented is the right call. They are named as limits in `DECISIONS.md` and the invariants, not presented as done.

---

## 5. Verdict

The remediation is honest and substantially correct. The two headline gaps from the first review are genuinely closed at the level claimed: the 3.1 guard exists and bites against the careless case, and the false-inert asymmetry is fixed by porting the existing discipline. The coverage false precision is gone. Nothing was silently patched to green; the residual break is left red with a fresh case proving it, which is the behaviour the project is built to produce.

The re-review changes the score on two points that should be addressed before invariant 3.1 can be called machine-checked in substance rather than in the common case:

1. **The 3.1 guard does not cover indirect model calls** (dynamic import, HTTP to an inference endpoint), which the invariant's own "direct or indirect" wording and "inference call" acceptance clause claim to cover (3.1). Either narrow the clause to match the guard, or extend the guard to detect authorisation-path egress.
2. **The 3.1 obligation has no negative control** (3.2), breaking the project's own mandatory-control discipline on the very check that enforces the load-bearing invariant. A planted-import control in the harness closes it and matches the existing 8.3 pattern.

Both are small to fix. Neither undoes the remediation. The first is the more serious because it is a real bypass of the guarantee the guard is supposed to make machine-checked; the second is the more embarrassing because the project's own standard names an uncontrolled check as theatre.

---

## 6. Recommended actions, in priority order

1. **Add a negative control to `run_symbolic_guard`** (3.2). Scan a temp file with `import mlx_lm`, assert it is caught, then run the real scan. Smallest change, closes a self-inflicted discipline gap, matches the 8.3 pattern.
2. **Close or scope the indirect-call gap** (3.1). Preferred: add AST detection of outbound HTTP calls (`requests`, `urllib`, `httpx`, `http.client`) and of dynamic import (`importlib.import_module`, `__import__`) on the authorisation path, and treat any as a violation, since the symbolic layer should make no model call by any route. Alternative if that is deferred: reword the 3.1 acceptance clause to claim only what the guard does (import and subprocess detection), so it does not overclaim "inference call" again.
3. **State the false-inert rate only as a lower bound** wherever a single figure appears (3.3). The docs already do this; keep it, and do not let "1/16" harden into a headline number.
