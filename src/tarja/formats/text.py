"""Substitui valores no texto UTF-8, sem manter uma cópia oculta do conteúdo."""

import hashlib
from pathlib import Path
from time import perf_counter

from tarja.censor import sha256
from tarja.detectors import is_standard_cpf, mask_cpf_digits, scan_identifiers
from tarja.models import DocumentReport, PageReport, Policy, ProcessingError


def censor_text_file(source: Path, target: Path, policy: Policy) -> DocumentReport:
    started = perf_counter()
    try:
        original = source.read_bytes()
        text = original.decode("utf-8-sig")
    except UnicodeError:
        raise ProcessingError(
            "Texto inválido: converta o arquivo para UTF-8 antes de processar."
        ) from None
    if "\x00" in text:
        raise ProcessingError("A entrada não parece ser texto UTF-8 simples.")
    detections, candidates = scan_identifiers(text, policy.entities)
    page = PageReport(page=1, extraction="text")
    for detection in reversed(detections):
        value = text[detection.start : detection.end]
        partial = detection.entity == "CPF" and policy.cpf_mode == "partial"
        if partial and is_standard_cpf(value):
            replacement = mask_cpf_digits(value)
        else:
            if partial:
                page.warnings.append("cpf_irregular_expanded_to_full")
            replacement = "".join("*" if char.isalnum() else char for char in value)
        text = text[: detection.start] + replacement + text[detection.end :]
        page.counts[detection.entity] = page.counts.get(detection.entity, 0) + 1
        page.regions.append(
            {"entity": detection.entity, "start": detection.start, "end": detection.end}
        )
        if detection.checksum_valid is False:
            page.warnings.append("cpf_checksum_invalid_masked")
    page.regions.reverse()
    # A substituição preserva o comprimento, então os intervalos valem também na saída.
    page.candidates = [
        {"entity": c.entity, "reason": c.reason, "start": c.start, "end": c.end} for c in candidates
    ]
    if page.candidates:
        page.warnings.append("unredacted_candidates_require_review")
    page.warnings = sorted(set(page.warnings))
    target.parent.mkdir(parents=True, exist_ok=True)
    encoded = text.encode("utf-8")
    with target.open("xb") as stream:
        try:
            stream.write(encoded)
        except BaseException:
            stream.close()
            target.unlink(missing_ok=True)
            raise
    warnings = []
    if source.suffix.lower() == ".md":
        warnings.append("markdown_linked_content_not_processed")
    return DocumentReport(
        input_sha256=hashlib.sha256(original).hexdigest(),
        output_sha256=sha256(target),
        pages=[page],
        elapsed_seconds=round(perf_counter() - started, 3),
        output_format="utf8_text",
        input_format=source.suffix.lower().removeprefix("."),
        warnings=warnings,
    )
