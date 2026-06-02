from fastapi.testclient import TestClient

from odr.types import Answer, GroundednessReport
from odr.web.app import create_app


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
