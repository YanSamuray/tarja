"""Identificação por padrões e contexto com intervalos no texto original."""

import re

from tarja.models import ENTITIES, Detection

# Permite uma quebra de linha, mas não a separação dupla entre blocos.
SPACE = r"[ \t]*(?:\n[ \t]*)?"
SEP = r"[ \t]*[.\-/]?[ \t]*(?:\n[ \t]*)?"
CPF_PATTERN = re.compile(
    rf"(?<!\w)(?:n[º°][ \t]*)?"
    rf"(?P<value>[0-9]{{3}}{SEP}[0-9]{{3}}{SEP}[0-9]{{3}}{SEP}[0-9]{{2}})(?!\w)",
    re.I,
)
CNPJ_PATTERN = re.compile(
    rf"(?<!\w)[0-9]{{2}}{SEP}[0-9]{{3}}{SEP}[0-9]{{3}}{SEP}[0-9]{{4}}{SEP}[0-9]{{2}}(?!\w)"
)
LABEL_SEPARATOR = rf"{SPACE}(?:n[º°o.]?{SPACE})?[:\-]?{SPACE}"
CONTEXT_PATTERNS = (
    (
        "CNH",
        re.compile(
            rf"\b(?:CNH|carteira nacional de habilita[çc][ãa]o){LABEL_SEPARATOR}"
            r"(?P<value>[0-9]{11})(?!\w)",
            re.I,
        ),
    ),
    (
        "TITULO_ELEITOR",
        re.compile(
            rf"\b(?:t[íi]tulo(?:{SPACE}de{SPACE}eleitor)?){LABEL_SEPARATOR}"
            rf"(?P<value>[0-9]{{4}}{SEP}[0-9]{{4}}{SEP}[0-9]{{4}})(?!\w)",
            re.I,
        ),
    ),
    (
        "RG",
        re.compile(
            rf"\b(?:RG|registro geral){LABEL_SEPARATOR}"
            rf"(?P<value>[0-9]{{1,2}}{SEP}[0-9]{{3}}{SEP}[0-9]{{3}}"
            rf"(?:{SPACE}-{SPACE})?[0-9Xx]?)(?!\w)",
            re.I,
        ),
    ),
)
EXCLUDED_LABEL = re.compile(
    r"(?:\bCNPJ|\bCNH|\bRG|\btelefone|\bcelular|\bmatr[íi]cula|\bc/c|R\$)\s*[:\-]?\s*$", re.I
)


def cpf_checksum_valid(value: str) -> bool:
    digits = [int(c) for c in value if c in "0123456789"]
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for size in (9, 10):
        remainder = sum(digits[i] * (size + 1 - i) for i in range(size)) % 11
        if digits[size] != (0 if remainder < 2 else 11 - remainder):
            return False
    return True


def detect_identifiers(text: str, entities: tuple[str, ...] = ENTITIES) -> list[Detection]:
    """RG/CNH/título exigem rótulo; CPFs suspeitos são censurados mesmo com DV inválido."""
    detections = []
    reserved = [m.span() for m in CNPJ_PATTERN.finditer(text)]
    for entity, pattern in CONTEXT_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span("value")
            if any(start < b and end > a for a, b in reserved):
                continue
            reserved.append((start, end))
            if entity in entities:
                detections.append(Detection(entity, start, end))
    if "CPF" in entities:
        for match in CPF_PATTERN.finditer(text):
            start, end = match.span("value")
            if any(start < b and end > a for a, b in reserved):
                continue
            if EXCLUDED_LABEL.search(text[max(0, start - 50) : start]):
                continue
            detections.append(
                Detection("CPF", start, end, cpf_checksum_valid(match.group("value")))
            )
    return sorted(detections, key=lambda item: item.start)


def mask_cpf_digits(cpf_text: str) -> str:
    """Compatibilidade com a função antiga; preserva a pontuação original."""
    if sum(c in "0123456789" for c in cpf_text) != 11:
        return cpf_text
    result, index = [], 0
    for char in cpf_text:
        if char in "0123456789":
            result.append("*" if index < 3 or index >= 9 else char)
            index += 1
        else:
            result.append(char)
    return "".join(result)
