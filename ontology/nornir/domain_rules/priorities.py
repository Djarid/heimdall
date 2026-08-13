"""Classification-rule priority bands, shared across domains.

Rules run in priority order (lower first) and the first match wins. When two domains
both offer a rule, the order between them must be deliberate, not an accident of
import order. These bands give every domain the same discipline: register high-risk
rules in the HIGH_RISK band, the domain's ordinary catch in the CATCH_ALL band.

Within a band, registration order breaks ties. A domain that needs a rule to beat
another domain's rule of the same kind must justify the priority in its module.

The load-bearing rule of the ordering (invariant 3.11): a high-risk classification
must always beat a low-risk or catch-all classification, so an action-critical value
is never laundered into an inert type by a broad rule matching first. That is why the
HIGH_RISK band is numerically far below the CATCH_ALL band, with room to spare.
"""

from __future__ import annotations

# Lower runs first. Wide gaps leave room to insert bands later without renumbering.
HIGH_RISK = 100      # payment/credential/instruction/state-change: must win
DOMAIN_SPECIFIC = 500  # a domain's ordinary, non-high-risk typed catch
CATCH_ALL = 900      # "it is at least a communication / a scheduling item"
