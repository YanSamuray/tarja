"""Remove regiões e exporta uma cópia estática sem objetos do PDF original."""

import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from time import perf_counter

import pymupdf
from PIL import Image, ImageChops

from tarja import __version__
from tarja.detectors import (  # noqa: F401
    detect_identifiers,
    is_standard_cpf,
    mask_cpf_digits,
    scan_identifiers,
)
from tarja.models import Detection, DocumentReport, PageReport, Policy, ProcessingError
from tarja.ocr import PageText, extract_page


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def partial_cpf(extracted: PageText, detection: Detection, policy: Policy) -> bool:
    """A máscara parcial exige caixas de caracteres exatas e um CPF de 11 dígitos."""
    return (
        detection.entity == "CPF"
        and policy.cpf_mode == "partial"
        and not extracted.used_ocr
        and is_standard_cpf(extracted.text[detection.start : detection.end])
    )


def redaction_rects(
    extracted: PageText, detection: Detection, policy: Policy
) -> list[pymupdf.Rect]:
    indices = [i for i in range(detection.start, detection.end) if extracted.boxes[i]]
    if partial_cpf(extracted, detection, policy):
        digits = [i for i in indices if extracted.text[i] in "0123456789"]
        indices = digits[:3] + digits[-2:]
    return span_rects(extracted, indices)


def span_rects(extracted: PageText, indices: list[int]) -> list[pymupdf.Rect]:
    # Nunca procura substrings pela página: cada retângulo vem desta ocorrência.
    groups: list[list[int]] = []
    for index in indices:
        if (
            groups
            and index == groups[-1][-1] + 1
            and extracted.lines[index] == extracted.lines[groups[-1][-1]]
        ):
            groups[-1].append(index)
        else:
            groups.append([index])
    rects = []
    for group in groups:
        rect = pymupdf.Rect(extracted.boxes[group[0]])
        for index in group[1:]:
            rect |= pymupdf.Rect(extracted.boxes[index])
        if extracted.used_ocr:
            # Caixas OCR são estimativas: remove todo o identificador com margem.
            rect += (-2, -2, 2, 2)
        else:
            # Evita tocar caracteres vizinhos que compartilham a borda da caixa.
            rect += (0.05, 0.05, -0.05, -0.05)
        if not rect.is_empty:
            rects.append(rect)
    return rects


def already_covered(rects: list[pymupdf.Rect], previous: list[pymupdf.Rect]) -> bool:
    """OCR e extração nativa podem achar a mesma ocorrência; conta-se uma vez."""
    return all(
        any((rect & other).get_area() >= 0.5 * rect.get_area() for other in previous)
        for rect in rects
    )


def render_png(page: pymupdf.Page, dpi: int) -> bytes:
    """PNG da página; sem cor, em tons de cinza, que ocupa cerca de metade do espaço.

    Com R = G = B em todos os pixels a conversão não perde informação, e a tarja
    continua preta. Páginas com qualquer cor permanecem em RGB.
    """
    pixmap = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False)
    red, green, blue = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples).split()
    neutral = (
        ImageChops.difference(red, green).getbbox() is None
        and ImageChops.difference(green, blue).getbbox() is None
    )
    return (pymupdf.Pixmap(pymupdf.csGRAY, pixmap) if neutral else pixmap).tobytes("png")


def flatten_annotations(doc: pymupdf.Document) -> tuple[set[int], set[int]]:
    """Aplica tarjas pendentes e incorpora campos e anotações visíveis ao conteúdo.

    Sem isso, o valor de um campo seria desenhado por cima da tarja na página exportada,
    e uma tarja marcada por outra pessoa, mas não aplicada, deixaria o texto visível.
    """
    pending, flattened = set(), set()
    for page in doc:
        if any(True for _ in page.annots(types=[pymupdf.PDF_ANNOT_REDACT])):
            page.apply_redactions(images=2, graphics=0, text=0)
            pending.add(page.number)
        if page.first_annot or page.first_widget:
            flattened.add(page.number)
    if flattened:
        doc.bake(annots=True, widgets=True)
    return pending, flattened


def censor_pdf(
    input_pdf_path: str | Path,
    output_pdf_path: str | Path,
    policy: Policy | None = None,
) -> DocumentReport:
    """Gera PDF novo; preserva a entrada e recusa sobrescritas e saídas parciais."""
    policy = policy or Policy()
    source, target = Path(input_pdf_path).resolve(), Path(output_pdf_path).resolve()
    if source == target:
        raise ProcessingError("Entrada e saída devem ser arquivos diferentes.")
    if target.exists():
        raise ProcessingError("O arquivo de saída já existe; escolha outro destino.")
    if not source.is_file() or source.suffix.lower() != ".pdf":
        raise ProcessingError("A entrada deve ser um arquivo PDF existente.")
    started = perf_counter()
    temporary = None
    reports = []
    try:
        if source.stat().st_size > 100 * 1024 * 1024:
            raise ProcessingError("O limite desta versão é 100 MB por arquivo.")
        input_hash = sha256(source)
        with pymupdf.open(source) as original, pymupdf.open() as result:
            if not original.is_pdf or original.needs_pass:
                raise ProcessingError("PDF criptografado ou inválido; forneça uma cópia acessível.")
            if not 1 <= len(original) <= 300:
                raise ProcessingError("O PDF deve conter de 1 a 300 páginas.")
            if original.xref_get_key(original.pdf_catalog(), "AcroForm/XFA")[0] != "null":
                raise ProcessingError(
                    "Formulário XFA não é exibido corretamente: "
                    "exporte uma cópia estática antes de processar."
                )
            pending, flattened = flatten_annotations(original)
            for page in original:
                rotation = page.rotation
                page.set_rotation(0)
                extracted = extract_page(page, policy)
                report = PageReport(page.number + 1, "ocr" if extracted.used_ocr else "native")
                if page.number in pending:
                    report.warnings.append("existing_redactions_applied")
                if page.number in flattened:
                    report.warnings.append("annotations_flattened")
                if not extracted.text.strip():
                    report.warnings.append("no_text_detected")
                if extracted.used_ocr:
                    report.warnings.append("ocr_requires_visual_review")
                detections, candidates = scan_identifiers(extracted.text, policy.entities)
                covered: list[pymupdf.Rect] = []
                for detection in detections:
                    rects = redaction_rects(extracted, detection, policy)
                    if not rects:
                        raise ProcessingError(
                            "Não foi possível localizar uma ocorrência na página."
                        )
                    if not already_covered(rects, covered):
                        report.counts[detection.entity] = report.counts.get(detection.entity, 0) + 1
                    if detection.checksum_valid is False:
                        report.warnings.append("cpf_checksum_invalid_masked")
                    if detection.entity == "CPF" and policy.cpf_mode == "partial":
                        if extracted.used_ocr:
                            report.warnings.append("ocr_cpf_expanded_to_full")
                        elif not partial_cpf(extracted, detection, policy):
                            report.warnings.append("cpf_irregular_expanded_to_full")
                    for rect in rects:
                        page.add_redact_annot(rect, fill=(0, 0, 0), cross_out=False)
                        report.regions.append(
                            {
                                "entity": detection.entity,
                                "bbox": [round(v, 2) for v in rect],
                            }
                        )
                    covered.extend(rects)
                # Números suspeitos não censurados: só a posição, nunca o valor.
                reviewed = list(covered)
                for candidate in candidates:
                    indices = range(candidate.start, candidate.end)
                    rects = span_rects(extracted, [i for i in indices if extracted.boxes[i]])
                    if not rects or already_covered(rects, reviewed):
                        continue
                    for rect in rects:
                        report.candidates.append(
                            {
                                "entity": candidate.entity,
                                "reason": candidate.reason,
                                "bbox": [round(v, 2) for v in rect],
                            }
                        )
                    reviewed.extend(rects)
                if report.candidates:
                    report.warnings.append("unredacted_candidates_require_review")
                if detections:
                    page.apply_redactions(images=2, graphics=0, text=0)
                # Copia somente os pixels já censurados: não leva texto oculto,
                # metadados, anexos, links ou revisões do documento original.
                exported = result.new_page(width=page.rect.width, height=page.rect.height)
                exported.insert_image(exported.rect, stream=render_png(page, policy.dpi))
                exported.set_rotation(rotation)
                report.warnings = sorted(set(report.warnings))
                reports.append(report)
            result.set_metadata({"producer": f"Tarja {__version__}"})
            target.parent.mkdir(parents=True, exist_ok=True)
            handle, name = tempfile.mkstemp(prefix=".censor-", suffix=".pdf", dir=target.parent)
            os.close(handle)
            temporary = Path(name)
            result.save(temporary, garbage=4, deflate=True)
        with pymupdf.open(temporary) as verified:
            if len(verified) != len(reports) or any(p.get_text().strip() for p in verified):
                raise ProcessingError("A validação estrutural do PDF de saída falhou.")
            if verified.embfile_count() or verified.get_xml_metadata():
                raise ProcessingError("A validação dos objetos do PDF de saída falhou.")
        output_hash = sha256(temporary)
        # Criação exclusiva: uma corrida nunca sobrescreve outro resultado.
        with target.open("xb") as destination, temporary.open("rb") as stream:
            try:
                shutil.copyfileobj(stream, destination)
            except BaseException:
                destination.close()
                target.unlink(missing_ok=True)
                raise
        return DocumentReport(input_hash, output_hash, reports, round(perf_counter() - started, 3))
    except ProcessingError:
        raise
    except Exception:
        raise ProcessingError(
            "Falha ao processar o PDF; verifique o arquivo e o acesso ao destino."
        ) from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
