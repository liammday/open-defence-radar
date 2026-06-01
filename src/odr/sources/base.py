"""The Source contract — one adapter per open data source.

`fetch` performs (paginated) HTTP and yields raw source records; `normalise`
maps a raw record to the common `Document` schema and computes its content hash.
`meta` carries provenance (licence, access method) for the `source` table.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from datetime import date
from typing import Any, Protocol

from odr.types import Document, SourceMeta


class Source(Protocol):
    @property
    def meta(self) -> SourceMeta: ...

    def fetch(
        self, since: date | None = None, limit: int | None = None
    ) -> Iterator[Mapping[str, Any]]: ...

    def normalise(self, raw: Mapping[str, Any]) -> Document: ...
