"""build_filters parsing (the CLI/MCP filter inputs → Filters)."""

from __future__ import annotations

from datetime import date

from odr.query import build_filters


def test_build_filters_none_when_empty() -> None:
    assert build_filters() is None


def test_build_filters_parses_dates_and_sources() -> None:
    filters = build_filters(date_from="2026-01-01", sources=["contracts-finder", "find-a-tender"])
    assert filters is not None
    assert filters.date_from == date(2026, 1, 1)
    assert filters.date_to is None
    assert filters.sources == ("contracts-finder", "find-a-tender")
