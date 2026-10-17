import pytest

from tarja.detectors import (
    cpf_checksum_valid,
    detect_identifiers,
    is_standard_cpf,
    mask_cpf_digits,
    scan_identifiers,
)
from tarja.models import ENTITIES


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
        ("Identidade: 12.345.678-9", "RG", "12.345.678-9"),
        ("R.G.: 12.345.678-9", "RG", "12.345.678-9"),
        ("Carteira de identidade nº 12.345.678-9", "RG", "12.345.678-9"),
        ("Identidade (RG): 12.345.678-9", "RG", "12.345.678-9"),
        ("RG (SSP/SP) nº 12.345.678-9", "RG", "12.345.678-9"),
        ("RG: MG-12.345.678", "RG", "12.345.678"),
        ("RG: 1234567890", "RG", "1234567890"),
        ("RG: 12.345.678 2ª via", "RG", "12.345.678"),
        ("Título eleitoral: 1234 5678 9012", "TITULO_ELEITOR", "1234 5678 9012"),
        ("Inscrição eleitoral nº 123456789012", "TITULO_ELEITOR", "123456789012"),
        ("Título de Eleitor n.º 1234.5678.9012", "TITULO_ELEITOR", "1234.5678.9012"),
        ("Carteira Nacional de Habilitação (CNH) nº 12345678900", "CNH", "12345678900"),
        ("CNH categoria B nº 12345678900", "CNH", "12345678900"),
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


def found(text, entities=ENTITIES):
    return [(m.entity, text[m.start : m.end]) for m in detect_identifiers(text, entities)]


@pytest.mark.parametrize(
    ("text", "value"),
    [
        # Rótulos combinados e a CIN, cujo número é o próprio CPF.
        ("CPF/CNPJ: 123.456.789-00", "123.456.789-00"),
        ("CPF e RG: 123.456.789-00", "123.456.789-00"),
        ("RG: 123.456.789-00", "123.456.789-00"),
        ("Registro Geral: 12345678900", "12345678900"),
        ("CNH: 123.456.789-00", "123.456.789-00"),
        # Separadores tipográficos, invisíveis e de OCR.
        ("CPF: 123.456.789\u201300", "123.456.789\u201300"),
        ("CPF: 123.456.789\u201000", "123.456.789\u201000"),
        ("CPF: 123.456.789\u201100", "123.456.789\u201100"),
        ("CPF: 123.456.789\u221200", "123.456.789\u221200"),
        ("CPF: 123\u00a0456\u00a0789\u00a000", "123\u00a0456\u00a0789\u00a000"),
        ("CPF: 123.456.\u200b789-00", "123.456.\u200b789-00"),
        ("CPF: 222.333.444\u00b705", "222.333.444\u00b705"),
        ("CPF: 123,456,789-00", "123,456,789-00"),
        ("CPF: 123.456.\r\n789-00", "123.456.\r\n789-00"),
        # Rótulo colado, ênfase do Markdown e célula seguinte colada.
        ("CPF123.456.789-00", "123.456.789-00"),
        ("_123.456.789-00_", "123.456.789-00"),
        ("__12345678900__", "12345678900"),
        ("CPF: 123.456.789-00RG", "123.456.789-00"),
        # Letras lidas pelo OCR e zeros à esquerda perdidos em planilhas.
        ("CPF: 123.456.789-O0", "123.456.789-O0"),
        ("l23.456.789-00", "l23.456.789-00"),
        ("CPF: 1234567890", "1234567890"),
        ("CPF n.º 123456789", "123456789"),
        # O DV válido prevalece sobre o rótulo de telefone.
        ("telefone: 52998224725", "52998224725"),
        # Formato monetário só é aceito com rótulo explícito de CPF.
        ("CPF: 123.456.789,00", "123.456.789,00"),
    ],
)
def test_cpf_variants_that_used_to_leak(text, value):
    assert found(text) == [("CPF", value)]


@pytest.mark.parametrize(
    "text",
    [
        "R$ 123.456.789,00",
        "Valor empenhado: 123.456.789,00",
        "Total: 1.123.456.789,00",
        "USD 123,456,789.00",
        "Processo 0001234-56.2024.8.26.0100",
        "Processo SEI 12345.678901/2024-12",
        "CPF/CNPJ: 12.345.678/0001-90",
        "34191.79001 01043.510047 91020.150008 1 83950000012345",
        "Chave de acesso 3519 0812 3456 7800 0123 5500 1000 0000 0110 0000 0000",
        "Inscrição estadual: 062.307.904/0081",
        "CNS 123 4567 8901 2345",
        "NIS 123.45678.90-1",
        "Telefone: (11) 98765-4321",
        "informar o CPF do responsável",
        "Título II, art. 123",
        "x 123.456.\r\n\r\n789-00",
    ],
)
def test_audit_numbers_are_neither_redacted_nor_flagged(text):
    assert scan_identifiers(text) == ([], [])


@pytest.mark.parametrize(
    ("text", "entities", "expected"),
    [
        ("RG: 123.456.789-00", ("RG",), [("RG", "123.456.789-00")]),
        ("CNH: 123.456.789-00", ("CNH",), [("CNH", "123.456.789-00")]),
        ("RG: 12345678900", ("CPF",), [("CPF", "12345678900")]),
        # O rótulo de CNH só impede a censura como CPF quando é inequívoco.
        ("CPF/CNH: 12345678900", ("CPF",), [("CPF", "12345678900")]),
        ("CNH categoria B: 12345678900", ("CPF",), [("CPF", "12345678900")]),
        ("CNH: não possui. CPF 12345678900", ("CPF",), [("CPF", "12345678900")]),
        (
            "CPF: 123.456.789-00RG: 12.345.678-9",
            ENTITIES,
            [("CPF", "123.456.789-00"), ("RG", "12.345.678-9")],
        ),
    ],
)
def test_classification_respects_selection_without_hiding_cpfs(text, entities, expected):
    assert found(text, entities) == expected


@pytest.mark.parametrize(
    ("text", "entities", "expected"),
    [
        ("telefone: 11987654321", ENTITIES, ("CPF", "excluded_label", "11987654321")),
        ("CNH: 12345678900", ("CPF",), ("CNH", "entity_disabled", "12345678900")),
        ("CPF: 123.456.789-001", ENTITIES, ("CPF", "unrecognized_value", "123.456.789-001")),
        ("CPF:\n123.45G.789-0O", ENTITIES, ("CPF", "unrecognized_value", "123.45G.789-0O")),
        ("CPF do sócio: 1234567890", ENTITIES, ("CPF", "unrecognized_value", "1234567890")),
    ],
)
def test_unredacted_suspects_become_review_candidates(text, entities, expected):
    detections, candidates = scan_identifiers(text, entities)
    assert detections == []
    assert [(c.entity, c.reason, text[c.start : c.end]) for c in candidates] == [expected]


def test_checksum_accepts_ocr_letters_and_lost_leading_zeros():
    assert cpf_checksum_valid("012.345.678-90")
    assert cpf_checksum_valid("1234567890")
    assert cpf_checksum_valid("O12.345.678-9O")
    assert detect_identifiers("CPF: 1234567890")[0].checksum_valid is True


def test_only_standard_cpfs_admit_partial_mask():
    assert is_standard_cpf("123.456.\n789-00")
    assert not is_standard_cpf("1234567890")
    assert not is_standard_cpf("123.456.789-O0")


def test_long_runs_of_spaces_do_not_hang_detection():
    text = "RG" + " " * 20000 + "x" + " CPF: 123.456.789-09" * 500
    assert len(detect_identifiers(text)) == 500
