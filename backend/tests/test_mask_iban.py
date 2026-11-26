from app.importers.common import mask_iban


def test_mask_iban_keeps_country_and_last_four():
    assert mask_iban("DE89 3704 0044 0532 0130 00") == "DE" + "*" * 16 + "3000"
    assert "37040044" not in mask_iban("DE89370400440532013000")


def test_mask_iban_short_or_empty():
    assert mask_iban(None) == ""
    assert mask_iban("") == ""
    assert mask_iban("DE12") == "****"
