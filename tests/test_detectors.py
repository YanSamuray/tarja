import pytest

from tarja.detectors import cpf_checksum_valid, detect_identifiers, mask_cpf_digits


@pytest.mark.parametrize(
    "value",
    [
        "123.456.789-00",
        "12345678900",
        "123 456 789 00",
        "123.456.789/00",
        "123.456.\n789-00",
    ],
)
def test_cpf_formats(value):
    text = f"CPF: {value}"
    matches = detect_identifiers(text)
    assert len(matches) == 1
    assert text[matches[0].start : matches[0].end] == value


@pytest.mark.parametrize(
    "value",
    [
        "123456789001",
        "12345678900123",
        "12.345.678/9001-23",
        "Matrícula: 12345678900",
        "telefone: 11987654321",
        "R$ 12345678900",
        "123.456.\n\n789-00",
    ],
)
def test_avoid_other_numbers(value):
    assert detect_identifiers(value) == []


@pytest.mark.parametrize(
    ("text", "entity", "value"),
    [
        ("RG: 12.345.678-9", "RG", "12.345.678-9"),
        ("RG 1.234.567-X", "RG", "1.234.567-X"),
        ("RG: 12345678", "RG", "12345678"),
        ("CNH: 12345678900", "CNH", "12345678900"),
        ("Título de eleitor: 1234 5678 9012", "TITULO_ELEITOR", "1234 5678 9012"),
    ],
)
def test_context_resolves_ambiguous_identifiers(text, entity, value):
    matches = detect_identifiers(text)
    assert len(matches) == 1
    assert matches[0].entity == entity
    assert text[matches[0].start : matches[0].end] == value


def test_disabled_cnh_is_not_reclassified_as_cpf():
    assert detect_identifiers("CNH: 12345678900", ("CPF",)) == []


def test_checksum_is_evidence_not_a_reason_to_skip_redaction():
    assert cpf_checksum_valid("529.982.247-25")
    assert not cpf_checksum_valid("11111111111")
    assert detect_identifiers("CPF: 12345678900")[0].checksum_valid is False


def test_mask_preserves_original_format():
    assert mask_cpf_digits("123.456.789/00") == "***.456.789/**"
    assert mask_cpf_digits("123") == "123"


def test_numero_prefix_does_not_hide_the_cpf_from_detection():
    text = "CPF: nº123.456.789-00"
    matches = detect_identifiers(text)
    assert len(matches) == 1
    assert text[matches[0].start : matches[0].end] == "123.456.789-00"
