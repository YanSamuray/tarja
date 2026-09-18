"""Extração por página com Tesseract integrado ao PyMuPDF, sem serviço remoto."""

from dataclasses import dataclass

import pymupdf

from tarja.models import Policy, ProcessingError


@dataclass
class PageText:
    text: str
    boxes: list[tuple | None]
    lines: list[int]
    used_ocr: bool


def requires_ocr(page: pymupdf.Page) -> bool:
    # Até uma página com cabeçalho digital pode conter uma imagem com dados pessoais.
    return bool(page.get_image_info()) or (
        not page.get_text().strip() and bool(page.get_drawings())
    )


def extract_page(page: pymupdf.Page, policy: Policy) -> PageText:
    needs_ocr = requires_ocr(page)
    if needs_ocr and policy.ocr == "never":
        raise ProcessingError("Página com conteúdo visual exige OCR; nenhum PDF foi exportado.")
    use_ocr = policy.ocr == "always" or needs_ocr
    kwargs = {}
    if use_ocr:
        try:
            kwargs["textpage"] = page.get_textpage_ocr(
                language=policy.language, dpi=policy.dpi, full=True, tessdata=policy.tessdata
            )
        except Exception:
            raise ProcessingError(
                "OCR indisponível. Configure --tessdata com os modelos por e eng do Tesseract."
            ) from None
    raw = page.get_text("rawdict", sort=True, **kwargs)
    if use_ocr:
        # Mantém também a extração nativa: uma leitura OCR pior não deve fazer
        # desaparecer uma ocorrência digital válida. O exportador deduplica por região.
        raw["blocks"].extend(page.get_text("rawdict", sort=True)["blocks"])
    text, boxes, lines = [], [], []
    line_number = 0
    for block in raw["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                for char in span["chars"]:
                    for codepoint in char["c"]:
                        text.append(codepoint)
                        boxes.append(char["bbox"])
                        lines.append(line_number)
            text.append("\n")
            boxes.append(None)
            lines.append(line_number)
            line_number += 1
        text.append("\n")
        boxes.append(None)
        lines.append(line_number)
    content = "".join(text)
    if needs_ocr and not content.strip():
        raise ProcessingError(
            "OCR não encontrou texto no conteúdo visual; revisão manual necessária."
        )
    return PageText(content, boxes, lines, use_ocr)
