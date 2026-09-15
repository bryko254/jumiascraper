from shared.countries import COUNTRIES
from shared.prices import parse_price


def test_kenya_ksh():
    assert parse_price("KSh 11,200", COUNTRIES["ke"]) == 11200.0


def test_nigeria_naira():
    assert parse_price("₦ 125,000", COUNTRIES["ng"]) == 125000.0


def test_egypt_egp():
    assert parse_price("EGP 4,499.50", COUNTRIES["eg"]) == 4499.5


def test_ghana_cedi():
    assert parse_price("GH₵ 1,250", COUNTRIES["gh"]) == 1250.0


def test_morocco_dhs():
    assert parse_price("Dhs 899", COUNTRIES["ma"]) == 899.0


def test_uganda_ush():
    assert parse_price("USh 450,000", COUNTRIES["ug"]) == 450000.0


def test_cfa_space_thousands():
    assert parse_price("85 000 CFA", COUNTRIES["ci"]) == 85000.0


def test_cfa_dot_thousands():
    assert parse_price("79.000 CFA", COUNTRIES["sn"]) == 79000.0


def test_empty_and_junk():
    assert parse_price("") is None
    assert parse_price("N/A") is None
    assert parse_price(None) is None
    assert parse_price(1999) == 1999.0
