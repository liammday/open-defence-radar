"""UK Contracts Finder source adapter (OCDS).

Open Government Licence v3.0 (verified at the API's top-level `license` field:
http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Publisher: Cabinet Office. OCDS-format procurement notices + awards.
"""

from __future__ import annotations

import httpx

from odr.sources.ocds import OcdsSource
from odr.types import SourceMeta

_META = SourceMeta(
    id="contracts-finder",
    name="UK Contracts Finder",
    url="https://www.contractsfinder.service.gov.uk",
    access_method="OCDS API",
    licence="OGL v3.0",
    attribution=(
        "Contains public sector information licensed under the Open Government Licence v3.0."
    ),
)


class ContractsFinder(OcdsSource):
    def __init__(self, client: httpx.Client | None = None) -> None:
        super().__init__(
            meta=_META,
            base_url="https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search",
            ocid_prefix="ocds-b5fd17-",
            notice_base="https://www.contractsfinder.service.gov.uk/Notice/",
            since_param="publishedFrom",
            client=client,
        )
