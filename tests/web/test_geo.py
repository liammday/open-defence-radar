from fastapi.testclient import TestClient

from odr.types import Answer, GroundednessReport, RegionStat
from odr.web.app import SiteContext, create_app
from odr.web.geo_view import build_geo_view


def _fake_query(topic, k, filters):
    _fake_query.seen = filters
    return Answer(
        text="ok", citations=(), groundedness=GroundednessReport(0, 0, 0), retrieved=()
    )


def test_query_route_forwards_region():
    app = create_app(query_fn=_fake_query)
    client = TestClient(app)
    r = client.post("/query", json={"topic": "x", "region": "South East"})
    assert r.status_code == 200
    assert _fake_query.seen is not None and _fake_query.seen.region == "South East"


def test_query_route_no_filters_when_region_absent():
    app = create_app(query_fn=_fake_query)
    client = TestClient(app)
    r = client.post("/query", json={"topic": "x"})
    assert r.status_code == 200
    assert _fake_query.seen is None


def test_geo_view_buckets_and_unspecified():
    stats = [
        RegionStat("UKI", "London", 7),
        RegionStat("UKJ", "South East", 1),
        RegionStat(None, "Region not specified", 46),
    ]
    view = build_geo_view(stats)
    assert view.placed_total == 8 and view.unspecified == 46
    london = next(c for c in view.cells if c.code == "UKI")
    assert london.count == 7 and london.intensity > 0  # 0..1 ramp, peak=7 → 1.0
    south_east = next(c for c in view.cells if c.code == "UKJ")
    assert 0 < south_east.intensity < london.intensity  # 1/7 < 7/7


def test_geo_view_all_twelve_regions_present_even_when_empty():
    view = build_geo_view([RegionStat(None, "Region not specified", 3)])
    assert len(view.cells) == 12 and view.placed_total == 0 and view.unspecified == 3


def test_trust_page_renders_choropleth_and_a11y_table():
    def ctx() -> SiteContext:
        return SiteContext(
            source_count=3,
            document_count=54,
            provenance=(),
            trust=None,
            geo=build_geo_view(
                [RegionStat("UKI", "London", 7), RegionStat(None, "Region not specified", 47)]
            ),
        )

    client = TestClient(create_app(context_provider=ctx))
    html = client.get("/trust").text
    assert "London" in html and "Region not specified" in html
    assert 'class="tilemap"' in html  # the inline SVG choropleth
    assert "<table" in html  # a11y text-table fallback
    assert "47" in html  # unspecified count surfaced
