"""Find a Tender (FTS) source adapter (OCDS).

Open Government Licence v3.0 (verified at the API's top-level `license` field).
Higher-value / above-threshold UK public contracts, OCDS format — same shape as
Contracts Finder, so it shares OcdsSource.
"""

from __future__ import annotations

import httpx

from odr.sources.ocds import OcdsSource
from odr.types import SourceMeta

_META = SourceMeta(
    id="find-a-tender",
    name="Find a Tender",
    url="https://www.find-tender.service.gov.uk",
    access_method="OCDS API",
    licence="OGL v3.0",
    attribution=(
        "Contains public sector information licensed under the Open Government Licence v3.0."
    ),
)


class FindATender(OcdsSource):
    def __init__(self, client: httpx.Client | None = None) -> None:
        super().__init__(
            meta=_META,
            base_url="https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages",
            ocid_prefix="ocds-h6vhtk-",
            notice_base="https://www.find-tender.service.gov.uk/Notice/",
            since_param="updatedFrom",
            client=client,
        )
