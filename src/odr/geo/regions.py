"""UK ITL-1 (NUTS-1) region gazetteer — names, codes, centroids, and a
normaliser from OCDS region strings / NUTS codes to one of the 12 regions.

Pure, no I/O. ITL-1 code↔name and region centroids are ONS open data
(Open Government Licence v3.0) — see README "Sources & licensing". The altitude
is deliberately region-level: nothing here can resolve finer than one of 12
regions, which is what keeps the geospatial feature analytic, not operational.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Region:
    """One UK ITL-1 region: its code, display name, and approximate centroid."""

    code: str  # ITL-1 / NUTS-1 code, e.g. "UKJ"
    name: str  # canonical display name, e.g. "South East"
    centroid: tuple[float, float]  # (lat, lon), approx region centre


REGIONS: tuple[Region, ...] = (
    Region("UKC", "North East", (54.93, -1.75)),
    Region("UKD", "North West", (54.00, -2.70)),
    Region("UKE", "Yorkshire and the Humber", (53.80, -1.30)),
    Region("UKF", "East Midlands", (52.90, -0.80)),
    Region("UKG", "West Midlands", (52.50, -2.10)),
    Region("UKH", "East of England", (52.20, 0.45)),
    Region("UKI", "London", (51.51, -0.12)),
    Region("UKJ", "South East", (51.30, -0.70)),
    Region("UKK", "South West", (50.90, -3.50)),
    Region("UKL", "Wales", (52.13, -3.78)),
    Region("UKM", "Scotland", (56.82, -4.18)),
    Region("UKN", "Northern Ireland", (54.61, -6.66)),
)

_BY_CODE = {r.code: r for r in REGIONS}
_BY_NAME = {r.name.lower(): r for r in REGIONS}
# Common alias spellings seen in OCDS deliveryAddresses.region values.
_ALIASES = {
    "yorkshire and humber": "UKE",
    "yorkshire": "UKE",
    "east": "UKH",
}


def classify(value: str | None) -> Region | None:
    """Map a region name or NUTS/ITL code to a Region, or None if not resolvable.

    Accepts "London", "South East", "UKI", or a longer NUTS code truncated to
    its ITL-1 prefix ("UKL24" → "UKL"). Country-level ("UK", "England") and
    unknown values return None.
    """
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    upper = v.upper()
    if upper.startswith("UK") and len(upper) >= 3:
        prefix = upper[:3]
        if prefix in _BY_CODE:
            return _BY_CODE[prefix]
    lower = v.lower()
    if lower in _BY_NAME:
        return _BY_NAME[lower]
    if lower in _ALIASES:
        return _BY_CODE[_ALIASES[lower]]
    return None
