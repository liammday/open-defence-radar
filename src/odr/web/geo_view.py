"""Trust-dashboard choropleth view-model: the 12 UK ITL-1 regions as a tile
grid, shaded by corpus document count.

A tile-grid (rather than a true-boundary map) is deliberate: it is self-authored
(no third-party asset to licence), tiny, and — crucially — region-level by
construction, so it cannot imply any geographic precision finer than a region.
That keeps the surface analytic, not operational.
"""

from __future__ import annotations

from dataclasses import dataclass

from odr.geo import REGIONS
from odr.types import RegionStat

_NAMES = {r.code: r.name for r in REGIONS}

# (code → (col, row)) — a schematic UK layout, north at the top: Scotland top,
# Northern Ireland to its west, then England's regions, London/South down south.
_LAYOUT: dict[str, tuple[int, int]] = {
    "UKM": (2, 0),  # Scotland
    "UKN": (0, 1),  # Northern Ireland
    "UKC": (2, 1),  # North East
    "UKD": (1, 2),  # North West
    "UKE": (2, 2),  # Yorkshire and the Humber
    "UKL": (0, 3),  # Wales
    "UKG": (1, 3),  # West Midlands
    "UKF": (2, 3),  # East Midlands
    "UKH": (3, 3),  # East of England
    "UKK": (1, 4),  # South West
    "UKJ": (2, 4),  # South East
    "UKI": (3, 4),  # London
}


_STOPWORDS = {"and", "of", "the"}


def _abbr(name: str) -> str:
    """A short tile label: initials of significant words (e.g. 'South East' → 'SE')."""
    words = [w for w in name.split() if w.lower() not in _STOPWORDS]
    if len(words) == 1:
        return words[0][:3].upper()
    return "".join(w[0] for w in words if w[:1].isalpha()).upper()[:4]


@dataclass(frozen=True)
class RegionCell:
    """One tile in the grid: a region, its count, grid position, and 0..1 shade."""

    code: str
    name: str
    abbr: str
    count: int
    col: int
    row: int
    intensity: float  # 0..1, count / max placed count (drives fill-opacity)


@dataclass(frozen=True)
class GeoView:
    cells: tuple[RegionCell, ...]
    unspecified: int
    placed_total: int

    @property
    def has_data(self) -> bool:
        return self.placed_total > 0 or self.unspecified > 0


def build_geo_view(stats: list[RegionStat]) -> GeoView:
    """Assemble the choropleth view-model from a store region breakdown.

    Every one of the 12 regions gets a cell (count 0 if absent); the ``code=None``
    "unspecified" bucket is surfaced separately, not placed on the grid.
    """
    counts = {s.code: s.document_count for s in stats if s.code is not None}
    unspecified = next((s.document_count for s in stats if s.code is None), 0)
    peak = max(counts.values(), default=0)
    cells = tuple(
        RegionCell(
            code=code,
            name=_NAMES[code],
            abbr=_abbr(_NAMES[code]),
            count=counts.get(code, 0),
            col=col,
            row=row,
            intensity=(counts.get(code, 0) / peak) if peak else 0.0,
        )
        for code, (col, row) in _LAYOUT.items()
    )
    placed_total = sum(c.count for c in cells)
    return GeoView(cells=cells, unspecified=unspecified, placed_total=placed_total)
