from airace.rxnorm_structured_product import parse_strength_and_form


def test_explicit_iv_strength():
    assert parse_strength_and_form("levofloxacin 750mg iv") == {
        "amount": 750.0, "unit": "mg", "routes": {"injection"}, "forms": {"injection"}
    }


def test_explicit_oral_tablet_strength():
    value = parse_strength_and_form("Zestril 10mg x 1 viên, uống sáng")
    assert value is not None
    assert value["amount"] == 10.0
    assert value["routes"] == {"oral"}
    assert value["forms"] == {"tablet"}


def test_missing_route_and_form_abstains():
    assert parse_strength_and_form("metoclopramide 10mg") is None
