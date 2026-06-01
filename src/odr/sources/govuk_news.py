"""GOV.UK / MoD news source adapter (prose via the GOV.UK Search API).

GOV.UK content is Crown copyright under the Open Government Licence v3.0
(https://www.gov.uk/help/terms-conditions). News stories + press releases from
the Ministry of Defence, newest first. Long-form prose, so it uses WindowChunker.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from datetime import date, datetime
from typing import Any

import httpx

from odr.ingest.chunk import Chunker, WindowChunker
from odr.types import Document, SourceMeta

_BASE = "https://www.gov.uk/api/search.json"
_FIELDS = "title,link,public_timestamp,description,indexable_content"
_META = SourceMeta(
    id="govuk-mod",
    name="GOV.UK · MoD news",
    url="https://www.gov.uk",
    access_method="Search API",
    licence="OGL v3.0",
    attribution=(
        "Contains public sector information licensed under the Open Government Licence v3.0."
    ),
)


class GovUkNews:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client or httpx.Client(
            timeout=30.0,
            headers={"Accept": "application/json", "User-Agent": "open-defence-radar"},
        )

    @property
    def meta(self) -> SourceMeta:
        return _META

    @property
    def chunker(self) -> Chunker:
        return WindowChunker()  # long-form prose

    def fetch(
        self, since: date | None = None, limit: int | None = None
    ) -> Iterator[Mapping[str, Any]]:
        start = 0
        page = 100
        yielded = 0
        while True:
            resp = self._client.get(
                _BASE,
                params={
                    "filter_organisations": "ministry-of-defence",
                    "filter_content_store_document_type": ["news_story", "press_release"],
                    "order": "-public_timestamp",
                    "fields": _FIELDS,
                    "count": page,
                    "start": start,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            if not results:
                return
            for record in results:
                published = self._parse_date(record.get("public_timestamp"))
                if since is not None and published is not None and published < since:
                    return  # newest-first: everything after is older than `since`
                yield record
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            start += page
            if start >= data.get("total", 0):
                return

    def normalise(self, raw: Mapping[str, Any]) -> Document:
        title = raw.get("title") or "(untitled)"
        link = raw.get("link") or ""
        url = link if str(link).startswith("http") else f"https://www.gov.uk{link}"
        parts = [title, raw.get("description") or "", raw.get("indexable_content") or ""]
        text = "\n".join(p for p in parts if p)
        return Document(
            source_id=_META.id,
            source_ref=link or title,
            title=title,
            url=url,
            text=text,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            published_at=self._parse_date(raw.get("public_timestamp")),
            raw=dict(raw),
        )

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except ValueError:
            return None
