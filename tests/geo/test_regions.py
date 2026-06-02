from odr.geo import REGIONS, Region, classify


def test_twelve_itl1_regions_with_centroids():
    assert len(REGIONS) == 12
    codes = {r.code for r in REGIONS}
    expected = {"UKC", "UKD", "UKE", "UKF", "UKG", "UKH", "UKI", "UKJ", "UKK", "UKL", "UKM", "UKN"}
    assert codes == expected
    for r in REGIONS:
        lat, lon = r.centroid
        assert 49.0 < lat < 61.0 and -8.5 < lon < 2.0  # within UK bounds


def test_classify_accepts_name_case_insensitive():
    r = classify("south east")
    assert isinstance(r, Region) and r.code == "UKJ" and r.name == "South East"


def test_classify_accepts_itl1_code():
    assert classify("UKI").name == "London"


def test_classify_truncates_longer_nuts_codes():
    assert classify("UKL24").code == "UKL"  # → Wales
    assert classify("UKH15").code == "UKH"  # → East of England


def test_classify_returns_none_for_country_or_unknown():
    assert classify("UK") is None
    assert classify("England") is None
    assert classify("") is None
    assert classify("Atlantis") is None
