# Ontology test suite

The four test obligations of invariant 3.11, which is where the live guarantee
actually lives: the filter's guarantee is exactly as strong as the ontology's
coverage. Building the ontology and testing it are the same activity.

- **Coverage measurement.** Fraction of assertions classified to a known type
  versus UNCLASSIFIED, tracked over time. A reported number, not pass/fail. The
  hard invariant: uncovered content fails safe, to review, never to a trusted or
  actionable type.
- **Classification correctness.** A labelled corpus (assertion to expected type)
  including adversarial cases engineered to force misclassification, above all
  cases trying to type an action-critical value as an inert label. A downgrade
  is a critical finding.
- **Reasoner soundness.** Every derived fact must be entailed by the rules. A
  derived fact that confers trust or in-scope status and does not follow fails
  the suite.
- **Flow-to-sink reachability.** Agent-scoped and cross-domain. The mandatory
  adversarial case is state staging across a domain boundary (decision D30).

`corpora/` holds the labelled and adversarial corpora with ground truth. The
classification-correctness corpus is new: the PoC injection corpus has no
ground-truth type labels, so it cannot serve here (section 8.2).

Nascent: stub. This is Phase 2/3 work and cannot run before the ontology and
substrate exist.
