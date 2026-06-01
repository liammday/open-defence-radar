"""UK Contracts Finder source adapter.

Open Government Licence v3.0 (verified at the API's top-level `license` field:
http://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
Publisher: Cabinet Office. OCDS-format procurement notices + awards.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from datetime import date, datetime
from typing import Any

import httpx

from odr.types import Document, SourceMeta

_BASE = "https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search"
_OCID_PREFIX = "ocds-b5fd17-"
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


class ContractsFinder:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=30.0,
            headers={"Accept": "application/json", "User-Agent": "open-defence-radar"},
        )

    @property
    def meta(self) -> SourceMeta:
        return _META

    def fetch(
        self, since: date | None = None, limit: int | None = None
    ) -> Iterator[Mapping[str, Any]]:
        first_params: dict[str, Any] = {"limit": 100}
        if since is not None:
            first_params["publishedFrom"] = since.isoformat()
        url: str | None = _BASE
        params: dict[str, Any] | None = first_params
        yielded = 0
        while url:
            resp = self._client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            for release in data.get("releases", []):
                yield release
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            url = (data.get("links") or {}).get("next")
            params = None  # links.next already encodes the query

    def normalise(self, raw: Mapping[str, Any]) -> Document:
        tender = raw.get("tender") or {}
        title = tender.get("title") or "(untitled notice)"
        description = tender.get("description") or ""
        buyer = (raw.get("buyer") or {}).get("name") or ""
        suppliers = [
            s.get("name")
            for award in (raw.get("awards") or [])
            for s in (award.get("suppliers") or [])
            if s.get("name")
        ]
        value = tender.get("value") or {}

        lines = [title]
        if buyer:
            lines.append(f"Buyer: {buyer}")
        if description:
            lines.append(description)
        if value.get("amount") is not None:
            lines.append(f"Value: {value.get('amount')} {value.get('currency', '')}".strip())
        if suppliers:
            lines.append(f"Awarded to: {', '.join(suppliers)}")
        text = "\n".join(lines)

        ocid = raw.get("ocid") or ""
        return Document(
            source_id=_META.id,
            source_ref=ocid,
            title=title,
            url=self._notice_url(ocid),
            text=text,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            published_at=self._parse_date(raw.get("date")),
            raw=dict(raw),
        )

    @staticmethod
    def _notice_url(ocid: str) -> str:
        guid = ocid[len(_OCID_PREFIX) :] if ocid.startswith(_OCID_PREFIX) else ocid
        return f"https://www.contractsfinder.service.gov.uk/Notice/{guid}"

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
