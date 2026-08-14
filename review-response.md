# Heimdall: Response to the Adversarial Review Brief

**Author:** adversarial reviewer (repository-access round)
**Date:** August 2026
**Version:** 1.0
**Reads with:** `ADVERSARIAL_REVIEW.md` (v2.1, the brief under review), `NEUROSYMBOLIC_FILTER_INVARIANTS.md`, `DECISIONS.md`, `STATUS.md` and the artifacts under `poc/` and `ontology/`

---

## 1. What this is

This is the review the brief asked for and said it had not yet had: one written with repository access, checking every claim against the artifact rather than the prose. The brief's own closing verdict (v2.1, section 9) is that the next unit of real information is "a reviewer with repository access". This is that pass.

The finding in one line: the design's documentation is more honest than most, and its central admitted weakness (false-inert classification) is genuinely reproduced by the code. But there are real gaps between claim and repository, and the most serious is that the acceptance criterion for the load-bearing invariant does not exist in the repository at all.

The findings are grouped by kind: (A) claims the code actively contradicts, (B) claims stated as complete that the repository does not hold and (C) the acknowledged break, verified and characterised more precisely than the brief does.

---

## 2. Category A: claims contradicted by the artifact

### 2.1 Invariant 3.1's acceptance criterion does not exist: no AST check, no CI, anywhere

This is the strongest overclaim, and it sits on the invariant everything depends on (`AGENTS.md`: "the symbolic layer never contains a language model... the load-bearing rule of the whole architecture").

`NEUROSYMBOLIC_FILTER_INVARIANTS.md` line 43 states the acceptance criterion in the present tense: "Static analysis in CI fails the build if the symbolic or boundary packages import a model client, call an inference endpoint or shell out to one. The PoC's AST check is the minimum bar."

Neither exists in the repository:

- There is no AST check in any file. A search of every Python file for `ast` returns only substrings inside words such as `last` and `fast`. No module parses the source of the symbolic or boundary packages to assert the absence of a model import.
- There is no CI of any kind. There is no `.github/` directory, no workflow file and no `pyproject.toml`, `tox.ini`, `setup.cfg` or equivalent. Nothing runs the harness or any static check on commit or push.

The PoC's own specification is honest about this: `poc/SPEC.md` line 218 says invariant 3.1 is "Verified by inspection: no model imports, no API calls, no subprocess to a model." Inspection is a one-time human read, not a check. The invariants document elevates that human read first into "the PoC's AST check" and then into "static analysis in CI". Neither artefact was ever built.

The brief compounds this rather than catching it. Section 8, finding 3, warns that model-drafted rules "would breach invariant 3.1 in substance while passing its runtime AST check" (also section 5, line 149). That warning presumes a runtime AST check exists. It does not. So the protection for invariant 3.1 today is human inspection alone, in a repository with no CI, and the brief's caveat is written against a control that was never implemented.

**Severity: high.** The invariant the architecture rests on has an acceptance criterion described as present and automated, which is absent and manual.

### 2.2 The false-inert break is a concrete rule-set asymmetry, not the abstract problem the brief describes

The brief (section 5.2 and decision D67) frames the 3/12 break in general terms: "the inert-earning signal is itself a content pattern an attacker can satisfy", and the fix is "an OPEN design change to how inertness is earned". That is true as far as it goes, but the code shows a plainer and more mechanical defect.

The communications inert rule was hardened against co-present requests. `ontology/nornir/domain_rules/communications.py` line 88, `_is_informational`, requires an informational signal AND `not _IMPERATIVE`: a message that both informs and asks is treated as asking, and falls through to the fail-closed default.

The other three inert rules carry no such exclusion:

- `scheduling.py` line 45, `_is_calendar_entry`: a single calendar keyword match, no imperative check.
- `finance.py` line 75, `_is_statement`: a single statement keyword match, no imperative check.
- `publication.py` line 69, `_is_informational_publication`: a single publication keyword match, no imperative check.

That asymmetry is exactly why the three failing corpus cases are `fi-13` (communications, worded to slip past the imperative guard), `fi-14` (publication) and `fi-15` (scheduling), while the communications euphemism cases `fi-01` to `fi-08` fail closed to review. The break is not a uniform polarity flaw across the design. It is that three of four inert rules never received the guard the fourth did.

This matters for the proposed fix. D67-fix is framed as a design change and warns against a keyword blacklist. Porting the existing `not _IMPERATIVE` discipline to the other three inert rules is neither a design change nor a blacklist: it is applying the rule set's own existing pattern consistently. The abstract framing makes the remedy sound heavier than the defect requires.

### 2.3 "94.7 percent" false precision still ships in the running artifact

The brief (section 4 and invariant 3.11) correctly criticises reporting coverage as "94.7 percent" on n=38 as false precision, and prescribes 36/38 with a Wilson interval. The correction is applied in the brief's prose. It is not applied in the code or the outcome documents the brief points readers to:

- `ontology/nornir/engine.py` line 52, `coverage()`, returns the float.
- `ontology/tests/harness.py` line 160 prints `Coverage (8.1): 94.7%`.
- `ontology/OUTCOME.md` line 13 and `STATUS.md` line 60 both still state "94.7%".

The running harness, executed for this review, prints "Coverage (8.1): 94.7% classified to a known type (36/38)". So the correction lives in the layer the brief controls, while the artifacts it cites as ground truth still commit the error. This is the brief's own finding G1 (the claims layer moves, the artifact does not) recurring on the very number the brief claims to have fixed.

---

## 3. Category B: claims stated as complete that the repository does not hold

### 3.1 The "structural" fail-closed enforcement never covered the inert positive rules

`DECISIONS.md` (consistency check 2) and invariant 3.5 claim the fail-closed discipline "is now enforced structurally, not by review alone (D55): a fail-closed property test in the harness". The D55 property test is `ontology/tests/harness.py` line 248, `run_failclosed_property`. It generates neutral request scaffolding with nonsense tokens and a communications sender, and asserts that an unmatched request never receives an inert type. It exercises the communications fail-closed default only. It never asserts that an inert positive rule (calendar, statement, publication) excludes a co-present consequence signal.

That is precisely the hole decision D67 later found by a separate corpus. So the "enforced structurally, not by review alone" claim held only for the one rule that did not break, and the guardrail's scope was narrower than the invariant's wording implied. The break was not caught by the structural guardrail that D55 claims makes review unnecessary. It was caught by a different, later corpus.

### 3.2 The gate's declarations have no schema or attestation, not even a stub

The brief ranks sink and flow declaration honesty first (section 5.1, "the root"), and states the gate is a four-term conjunction with only one proven term (section 2). Both are accurate against the code. `ontology/nornir/gjoll.py` lines 80 to 117 confirm the four terms: sink is consequential (declared, from `agent_consequential_sinks`), the parameter is consumed as an action (declared, from `proposal.consumes`), the value is untrusted-derived (structural, from the trust level) and the value is action-critical (computed by reachability).

Worth stating more plainly than the brief does: `ActionProposal.consumes` and `ActionProposal.sink` are a raw caller-supplied `dict` and string (`gjoll.py` line 68), with no validation, schema, signing or behaviour derivation anywhere in the repository. The brief calls for a published sink-declaration schema as future work (`STATUS.md` recommended next step 3). The current state is not "schema exists but is unverified"; it is "no schema, no stub, no validation". Three of the gate's four terms are unattested trusted input, and two of those three arrive as an unchecked dictionary.

### 3.3 The cross-batch guarantee holds only in the mode the default suite does not run

The brief (section 5.5) says the per-batch default does not catch cross-batch staging, framing it as "a precondition (persistent mode), not a default". The code confirms this and sharpens it. `ontology/nornir/engine.py` lines 180 to 187 build the flow graph only from the current batch's assertions, and the default backend (`flow_backends.py`, `in_memory`) holds no state across calls. The persistent-store path that does catch cross-batch staging is `ontology/tests/memgraph_integration_harness.py`, which the brief itself notes (line 164) "skips cleanly when Memgraph is absent".

The consequence: the configuration that holds the cross-batch guarantee is the one the core suite does not exercise on a default run. `STATUS.md` line 52 states cross-batch staging "is caught" (D64). That is true only for a mode that requires Memgraph and podman, and that the green (or in this case red) core suite does not touch. The default deployment is both the shipped one and the untested one for this attack.

---

## 4. Category C: the acknowledged break, verified

Running `poc/.venv/bin/python -m ontology.tests.harness` reproduces the claimed state exactly: the false-inert rate is 3/12 (cases `fi-13`, `fi-14`, `fi-15`), and the suite exits FAIL. This matches decision D67, `STATUS.md` and the brief. The suite is left red and names the finding, which is the honest outcome the repository's own conventions call for.

Two caveats the brief already makes, confirmed here:

- The 3/12 is a lower bound. One author wrote both the rules and the corpus (`ontology/tests/corpora/false_inert_adversarial.json`, the `independence_discipline` field states this). A corpus labelled by someone who has not read the rules would likely push the rate higher.
- The corpus is small (12 consequential cases), so the rate carries a wide confidence interval. This is the same false-precision problem the brief raises against "94.7 percent", now on the security-critical number. The brief quotes 3/12 repeatedly without an interval, having just criticised 94.7 percent for exactly that omission.

---

## 5. Summary judgement

The findings that change the design story rather than increment it are the first and the fourth:

1. **The invariant 3.1 enforcement does not exist** (2.1). The acceptance criterion is stated as automated CI static analysis; the repository has no AST check and no CI. The brief re-asserts a non-existent runtime check while caveating it. The real protection for the architecture's load-bearing rule is a one-time human read.
2. **The false-inert break is a rule-set asymmetry** (2.2), not the abstract design problem the brief describes: three inert rules lack the imperative guard the fourth has, and the prescribed fix is heavier than the defect warrants.
3. **The "94.7 percent" false precision still ships** in the code and the outcome documents the brief claims to have corrected (2.3).
4. **The D55 structural fail-closed enforcement never covered the inert positive rules** (3.1), which is why a separate corpus (D67) was needed to find the break.
5. **The gate's declarations have no schema or attestation, not even a stub** (3.2), and **the cross-batch guarantee holds only in the mode the default suite does not run** (3.3).

The brief's own "least welcome finding" (section 8, finding 3) is built on a control that was never implemented. That is the headline: the substantive defence of invariant 3.1 is human inspection alone, in a repository with no CI, described throughout as automated static analysis.

---

## 6. Recommended actions

In descending order of how much each closes a claim-to-artifact gap:

1. **Build the invariant 3.1 check and wire it to run.** An AST pass over the symbolic and boundary packages (`ontology/`, the Bifrost boundary) asserting no model-client import, no inference call and no subprocess to a model, plus a CI configuration that runs it and the harness on every commit. Until this exists, restate the invariant 3.1 acceptance criterion in the present tense honestly as "verified by human inspection, no automated check", and remove the references to a runtime AST check from `ADVERSARIAL_REVIEW.md` sections 5 and 8.
2. **Port the `not _IMPERATIVE` guard to the calendar, statement and publication inert rules** and re-measure the false-inert rate. If it drops, D67-fix was narrower than framed and should be reclassified.
3. **Replace "94.7 percent" with "36/38" and a Wilson interval** in `engine.py`, `harness.py`, `ontology/OUTCOME.md` and `STATUS.md`, matching the brief's own prescription.
4. **Extend the D55 property test to inert positive rules:** assert that no inert type is assigned when a consequence or imperative signal co-occurs, so the structural guardrail covers the case that broke.
5. **Publish the sink-declaration schema and add validation at the gate boundary,** so `ActionProposal.consumes` is not an unchecked dictionary.
