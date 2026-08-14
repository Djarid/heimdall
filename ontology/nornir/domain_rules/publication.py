"""Publication-domain classification rules. The fourth sibling (D29), covering the
open-web/published surface a probe found uncovered.

Adding this module and its line in `register_all` is the whole of the publication
domain on the rules side; it edits no other domain's rules.

Two rules, mirroring the fail-closed discipline (D54):

- `published_directive` (high-risk): published content that directs the reader or a
  reading agent to act. This is indirect prompt injection carried by a publication,
  and it must be high-risk so it is never masked to the inert publication type. High
  specificity so a page that both informs and directs types as the directive (the
  consequential part wins), the same asymmetry as everywhere else: a downgrade is
  fatal, an over-classification costs a review.

- `informational_publication` (inert): a positively-recognised published item (an
  article, listing, review, reference/documentation page) that asks nothing. INERT
  tier, so it earns the inert label and beats the communications FALLBACK
  unrecognised-request default. Inertness is earned by a positive publication signal,
  never granted, so this is not a blacklist and it keeps the fail-closed property: a
  publication we cannot positively recognise still falls to review, it does not become
  inert by default.

Reading the extracted fields to type them is describing untrusted content, not obeying
it. The predicates are fixed Python; the content cannot reclassify itself.
"""

from __future__ import annotations

import re

from ..assertions import MarshalledAssertion
from ..rules import (
    ClassificationRule,
    RiskTier,
    earns_inert,
    register_classification_rule,
    register_high_risk_types,
    text_of,
)


# Published content that DIRECTS the reader or a reading agent to act. The
# distinguishing shape is that published content ADDRESSES a reader or agent, or
# carries injection-style meta-instructions, NOT that it contains an action verb: a
# bare "approve"/"run" belongs to a communications message, not a publication. Keying
# on the address-the-reader / override-instructions shape is what stops this rule from
# stealing communications' high-risk content (which shares action verbs). A page that
# says "assistant, ignore previous instructions and ..." is the published-directive
# (indirect injection) signature; an email that says "please run the script" is a
# communications instruction and stays there.
_DIRECTIVE = re.compile(
    r"\b(assistant,|dear assistant|hey assistant|to the (reader|assistant|agent)|"
    r"you (the )?(reader|assistant|agent)|ignore (all )?(previous|prior) (instructions?|prompts?)|"
    r"disregard (the|your|all) (above|previous|prior|instructions?)|"
    r"system prompt|new instructions?:|override|as an ai|when you read this)\b"
)
# A positively-recognised published item: an article, listing, review or reference.
_PUBLICATION = re.compile(
    r"\b(article|news|report(s|ed|ing)?|listicle|blog post|product (listing|page)|"
    r"listing|review|rating|stars|documentation|docs|reference|guide|wiki|"
    r"specification|spec sheet|press release|headline|posted|published)\b"
)


def _is_published_directive(a: MarshalledAssertion) -> bool:
    return bool(_DIRECTIVE.search(text_of(a)))


def _is_informational_publication(a: MarshalledAssertion) -> bool:
    # Inert only if it looks like a publication AND carries no imperative or
    # consequence signal (D69). An "article" that also says "the reader might gather
    # the money-folder spreadsheets and send them along" is not an inert publication;
    # it falls through to the fail-closed default.
    return bool(_PUBLICATION.search(text_of(a))) and earns_inert(a)


def register_rules() -> None:
    # High-risk: a published directive (indirect injection carried by a page). High
    # specificity so it wins over a co-occurring publication signal.
    register_classification_rule(
        ClassificationRule("published_directive", "pub:published_directive",
                           _is_published_directive, risk_tier=RiskTier.HIGH, specificity=2)
    )
    # Inert: a positively-recognised publication. INERT tier beats the comms FALLBACK
    # default, so recognised published content earns its inert type; unrecognised
    # content still falls to review (fail-closed).
    register_classification_rule(
        ClassificationRule("informational_publication", "pub:informational_publication",
                           _is_informational_publication, risk_tier=RiskTier.INERT, specificity=1)
    )
    register_high_risk_types("pub:published_directive")
