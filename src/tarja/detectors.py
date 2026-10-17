"""Identificação por padrões e contexto com intervalos no texto original."""

import re

from tarja.models import ENTITIES, Candidate, Detection

DIGITS = "0123456789"
# Espaços, inclusive o inseparável, e caracteres invisíveis (hífen opcional, largura
# zero, BOM) que editores e PDFs inserem entre dígitos. Os quantificadores
# possessivos (*+) evitam retrocesso exponencial em sequências longas de espaços.
HSPACE = r"[ \t\x0b\x0c\u00a0\u00ad\u1680\u2000-\u200d\u202f\u205f\u2060\u3000\ufeff]"
BREAK = r"(?:\r\n|[\n\r\x85\u2028\u2029])"
# Permite uma quebra de linha, mas não a separação dupla entre blocos.
SPACE = rf"{HSPACE}*+(?:{BREAK}{HSPACE}*+)?"
DASH = r"[\-\u2010-\u2015\u2212\ufe58\ufe63\uff0d]"
PUNCT = rf"(?:[.,/\u00b7\u2024\u2219\u22c5\u2044\u2215\uff0c\uff0e\uff0f]|{DASH})"
SEP = rf"{HSPACE}*+{PUNCT}?{SPACE}"
# Rótulos não podem estar dentro de palavras, mas podem vir colados a dígitos.
START = r"(?<![^\W\d_])"
END = r"(?![^\W\d_])"
NUMBER_WORD = r"n(?:[úu]mero|r|\.?[º°o])?\.?"
# Ligação curta entre rótulo e valor: espaços, "nº", dois-pontos, travessão e parênteses.
TIGHT = rf"(?:{SPACE}(?:[:)\]]|{DASH}|{NUMBER_WORD}{END}))*+{SPACE}"
LABELS = {
    "CPF": r"C\.?\s?P\.?\s?F\.?|CIC",
    "CNPJ": r"CNPJ",
    "RG": r"R\.?\s?G\.?|registro\s+geral|identidade",
    "CNH": r"CNH|carteira\s+(?:nacional\s+)?de\s+habilita[çc][ãa]o|carteira\s+de\s+motorista",
    "TITULO_ELEITOR": r"t[íi]tulo(?:\s+(?:de\s+)?eleito(?:r|ral))?|inscri[çc][ãa]o\s+eleitoral",
    "OUTROS": r"telefone|celular|matr[íi]cula",
}


def _label(entity: str) -> str:
    return rf"{START}(?:{LABELS[entity]}){END}"


def _gap(*crossable: str) -> str:
    """Até 30 caracteres não numéricos sem atravessar o rótulo de outro identificador."""
    others = "|".join(label for key, label in LABELS.items() if key not in crossable)
    return rf"{SPACE}(?:(?!{START}(?:{others}){END})[^\d\r\n]){{0,30}}?{SPACE}"


CPF_SHAPE = rf"[0-9]{{3}}{SEP}[0-9]{{3}}{SEP}[0-9]{{3}}{SEP}[0-9]{{2}}"
CPF_VALUE = re.compile(CPF_SHAPE)
# Letras que o OCR confunde com dígitos; só valem num CPF claramente formatado.
OCR_DIGIT = r"[0-9OoIl]"
OCR_LOOKALIKES = str.maketrans("OoIl", "0011")
CPF_PATTERN = re.compile(
    rf"(?:(?<![^\W_])|(?<=[Cc][Pp][Ff]))(?:[Nn]\.?[º°oO]?\.?{HSPACE}*+)?"
    rf"(?P<value>{OCR_DIGIT}{{3}}(?P<s1>{SEP}){OCR_DIGIT}{{3}}(?P<s2>{SEP})"
    rf"{OCR_DIGIT}{{3}}(?P<s3>{SEP}){OCR_DIGIT}{{2}})(?![0-9])"
)
# Zeros à esquerda perdidos em planilhas: 9 ou 10 dígitos, somente após rótulo de CPF.
SHORT_CPF_PATTERN = re.compile(
    rf"{_label('CPF')}{TIGHT}(?P<value>[0-9]{{9,10}}"
    rf"|[0-9]{{1,2}}(?:{SEP}[0-9]{{3}}){{2}}{SEP}[0-9]{{2}})(?![0-9])",
    re.I,
)
CPF_LABEL_BEFORE = re.compile(rf"{_label('CPF')}{TIGHT}$", re.I)
CNPJ_PATTERN = re.compile(
    rf"(?<![0-9])[0-9]{{2}}{SEP}[0-9]{{3}}{SEP}[0-9]{{3}}{SEP}[0-9]{{4}}{SEP}[0-9]{{2}}(?![0-9])"
)
CONTEXT_VALUES = {
    "CNH": CPF_SHAPE,
    "TITULO_ELEITOR": rf"[0-9](?:{SEP}[0-9]){{11}}",
    "RG": rf"[0-9]{{1,3}}(?:{SEP}[0-9]{{3}}){{2}}(?:(?:{HSPACE}*+{DASH}{SPACE})?[0-9Xx]{{1,2}})?",
}
# Prefixo de UF no RG (MG-12.345.678), que permanece visível.
UF_PREFIX = rf"(?:[A-Z]{{2}}{HSPACE}*+(?:{DASH}|/)?{HSPACE}*+)?"
CONTEXT_PATTERNS = tuple(
    (
        entity,
        re.compile(
            rf"{_label(entity)}(?P<gap>{_gap(entity)}){UF_PREFIX if entity == 'RG' else ''}"
            rf"(?P<value>{value})(?![0-9])",
            re.I,
        ),
    )
    for entity, value in CONTEXT_VALUES.items()
)
TIGHT_GAP = re.compile(TIGHT)
COMBINED_WITH_CPF = re.compile(
    rf"(?:{LABELS['CPF']})[^\w\r\n]{{0,3}}(?:(?:ou|e)[^\w\r\n]{{1,3}})?$", re.I
)
# Valor após o rótulo, com letras que o OCR costuma trocar por dígitos.
LABEL_VALUE_PATTERNS = {
    entity: re.compile(
        rf"{_label(entity)}{_gap(entity, 'CNPJ') if entity == 'CPF' else _gap(entity)}"
        rf"(?P<token>[0-9](?:{SEP}[0-9OoIlSsBbGgZzq]){{3,24}})",
        re.I,
    )
    for entity in ENTITIES
}
EXCLUDED_LABEL = re.compile(r"(?:\btelefone|\bcelular|\bmatr[íi]cula|\bc/c|R\$)\s*[:\-]?\s*$", re.I)
PUNCT_RE = re.compile(PUNCT)
COMMA = re.compile(r"[,\uff0c]")
DOT = re.compile(r"[.\u00b7\u2024\u2219\u22c5\uff0e]")


def cpf_checksum_valid(value: str) -> bool:
    """Aceita letras de OCR e completa zeros à esquerda perdidos (9 ou 10 dígitos)."""
    digits = [int(c) for c in value.translate(OCR_LOOKALIKES) if c in DIGITS]
    if 9 <= len(digits) < 11:
        digits = [0] * (11 - len(digits)) + digits
    if len(digits) != 11 or len(set(digits)) == 1:
        return False
    for size in (9, 10):
        remainder = sum(digits[i] * (size + 1 - i) for i in range(size)) % 11
        if digits[size] != (0 if remainder < 2 else 11 - remainder):
            return False
    return True


def is_standard_cpf(value: str) -> bool:
    """Onze dígitos e nenhuma letra: só esse formato admite a máscara parcial."""
    return sum(c in DIGITS for c in value) == 11 and not any(c.isalpha() for c in value)


def _overlaps(start: int, end: int, spans: list[tuple[int, int]]) -> bool:
    return any(start < b and end > a for a, b in spans)


def _plausible_cpf(match: re.Match, labeled: bool) -> bool:
    """Descarta formas que, sem rótulo de CPF, costumam ser valores ou outros códigos."""
    separators = [match.group(name) for name in ("s1", "s2", "s3")]
    punctuated = [bool(PUNCT_RE.search(separator)) for separator in separators]
    digits = sum(c in DIGITS for c in match.group("value"))
    if digits < 11 and (digits < 9 or sum(punctuated) < 2):
        return False
    if labeled:
        return True
    # 123.456.789,00 e 123,456,789.00 são valores monetários.
    if COMMA.search(separators[2]) or (
        COMMA.search(separators[0]) and COMMA.search(separators[1]) and DOT.search(separators[2])
    ):
        return False
    # Separação parcial só com espaços aparece em boletos e tabelas, não em CPFs.
    return any(punctuated) or sum(map(bool, separators)) in (0, 3)


def scan_identifiers(
    text: str, entities: tuple[str, ...] = ENTITIES
) -> tuple[list[Detection], list[Candidate]]:
    """Ocorrências a censurar e números suspeitos que ficaram de fora, para conferência.

    RG, CNH e título exigem rótulo. Na dúvida, censura: CPFs com DV inválido também
    entram, e um valor com formato de CPF é CPF mesmo sob rótulo de RG (a CIN usa o
    CPF como número) ou de CNH formatada.
    """
    detections: list[Detection] = []
    candidates: list[Candidate] = []
    reserved = [m.span() for m in CNPJ_PATTERN.finditer(text)]
    for entity, pattern in CONTEXT_PATTERNS:
        for match in pattern.finditer(text):
            start, end = match.span("value")
            if _overlaps(start, end, reserved):
                continue
            value = match.group("value")
            cpf_like = bool(CPF_VALUE.fullmatch(value))
            # Só a CNH usa 11 dígitos sem pontuação; os demais formatos de CPF são CPF.
            if "CPF" in entities and cpf_like and (entity != "CNH" or not value.isdigit()):
                detections.append(Detection("CPF", start, end, cpf_checksum_valid(value)))
            elif entity in entities:
                detections.append(Detection(entity, start, end))
            elif not TIGHT_GAP.fullmatch(match.group("gap")) or COMBINED_WITH_CPF.search(
                text[max(0, match.start() - 12) : match.start()]
            ):
                # Rótulo distante ou combinado ("CPF/CNH"): o número pode ser um CPF.
                continue
            elif "CPF" in entities and cpf_like:
                candidates.append(Candidate(entity, start, end, "entity_disabled"))
            reserved.append((start, end))
    if "CPF" in entities:
        for match in CPF_PATTERN.finditer(text):
            start, end = match.span("value")
            if _overlaps(start, end, reserved):
                continue
            labeled = bool(CPF_LABEL_BEFORE.search(text[max(0, start - 20) : start]))
            if not _plausible_cpf(match, labeled):
                continue
            valid = cpf_checksum_valid(match.group("value"))
            # Telefones e matrículas só deixam de ser censurados com DV inválido.
            if not (valid or labeled) and EXCLUDED_LABEL.search(text[max(0, start - 50) : start]):
                candidates.append(Candidate("CPF", start, end, "excluded_label"))
                continue
            detections.append(Detection("CPF", start, end, valid))
            reserved.append((start, end))
        for match in SHORT_CPF_PATTERN.finditer(text):
            start, end = match.span("value")
            if not _overlaps(start, end, reserved):
                valid = cpf_checksum_valid(match.group("value"))
                detections.append(Detection("CPF", start, end, valid))
                reserved.append((start, end))
    for entity in entities:
        for match in LABEL_VALUE_PATTERNS[entity].finditer(text):
            start, end = match.span("token")
            if sum(c in DIGITS for c in match.group("token")) < 6:
                continue
            known = reserved + [(c.start, c.end) for c in candidates]
            if not _overlaps(start, end, known):
                candidates.append(Candidate(entity, start, end, "unrecognized_value"))
    return (
        sorted(detections, key=lambda item: item.start),
        sorted(candidates, key=lambda item: item.start),
    )


def detect_identifiers(text: str, entities: tuple[str, ...] = ENTITIES) -> list[Detection]:
    """Somente as ocorrências a censurar; os candidatos estão em scan_identifiers."""
    return scan_identifiers(text, entities)[0]


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
