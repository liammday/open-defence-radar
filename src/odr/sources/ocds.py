"""Shared base for OCDS procurement sources (Contracts Finder, Find a Tender).

Both publish the Open Contracting Data Standard: a release package with a
top-level `license` and `links.next` cursor, and `releases[]` each carrying
ocid / tender / buyer / awards. Concrete sources differ only in base URL, OCID
prefix, public notice-URL base, and the "since" query parameter name.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator, Mapping
from datetime import date, datetime
from typing import Any

import httpx

from odr.types import Document, SourceMeta


class OcdsSource:
    def __init__(
        self,
        *,
        meta: SourceMeta,
        base_url: str,
        ocid_prefix: str,
        notice_base: str,
        since_param: str,
        client: httpx.Client | None = None,
    ) -> None:
        self._meta = meta
        self._base_url = base_url
        self._ocid_prefix = ocid_prefix
        self._notice_base = notice_base
        self._since_param = since_param
        self._client = client or httpx.Client(
            timeout=30.0,
            headers={"Accept": "application/json", "User-Agent": "open-defence-radar"},
        )

    @property
    def meta(self) -> SourceMeta:
        return self._meta

    def fetch(
        self, since: date | None = None, limit: int | None = None
    ) -> Iterator[Mapping[str, Any]]:
        first_params: dict[str, Any] = {"limit": 100}
        if since is not None:
            first_params[self._since_param] = since.isoformat()
        url: str | None = self._base_url
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
            source_id=self._meta.id,
            source_ref=ocid,
            title=title,
            url=self._notice_url(ocid),
            text=text,
            content_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            published_at=self._parse_date(raw.get("date")),
            raw=dict(raw),
        )

    def _notice_url(self, ocid: str) -> str:
        guid = ocid[len(self._ocid_prefix) :] if ocid.startswith(self._ocid_prefix) else ocid
        return f"{self._notice_base}{guid}"

    @staticmethod
    def _parse_date(value: Any) -> date | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value).date()
        except ValueError:
            return None
