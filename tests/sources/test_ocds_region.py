from typing import Any

from odr.sources.contracts_finder import ContractsFinder


def _release(region: str) -> dict[str, Any]:
    return {
        "ocid": "ocds-b5fd17-x",
        "date": "2026-01-02T00:00:00Z",
        "tender": {
            "title": "Test notice",
            "items": [{"id": "1", "deliveryAddresses": [{"region": region}]}],
        },
    }


def test_normalise_extracts_itl1_region_code() -> None:
    doc = ContractsFinder().normalise(_release("South East"))
    assert doc.region_code == "UKJ"


def test_normalise_handles_nuts_code_region() -> None:
    doc = ContractsFinder().normalise(_release("UKL24"))
    assert doc.region_code == "UKL"


def test_normalise_region_none_when_absent_or_country_level() -> None:
    assert ContractsFinder().normalise(_release("England")).region_code is None
    assert ContractsFinder().normalise({"ocid": "x", "tender": {"title": "t"}}).region_code is None
