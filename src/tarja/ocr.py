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


# Segmentos de retas e curvas preenchidos a partir dos quais o desenho pode ser texto.
# Um CPF convertido em curvas tem cerca de 200; tabelas e gráficos de barras usam
# retângulos, que não entram na conta.
OUTLINE_SEGMENTS = 60


def requires_ocr(page: pymupdf.Page) -> bool:
    # Até uma página com cabeçalho digital pode conter uma imagem com dados pessoais.
    if page.get_image_info():
        return True
    text = page.get_text()
    if not text.strip():
        return bool(page.get_drawings())
    # Fontes sem mapeamento Unicode e texto convertido em curvas ficam visíveis na
    # página exportada, mas não aparecem corretamente na extração nativa.
    return unreliable_text(text) or has_vector_outlines(page)


def unreliable_text(text: str) -> bool:
    """Caracteres de substituição ou de controle indicam glifos sem mapeamento Unicode."""
    return sum(c == "\ufffd" or (c < " " and c not in "\t\n\r") for c in text) >= 3


def has_vector_outlines(page: pymupdf.Page) -> bool:
    segments = 0
    for drawing in page.get_drawings():
        if drawing.get("fill") is not None:
            segments += sum(item[0] in ("l", "c", "qu") for item in drawing["items"])
            if segments >= OUTLINE_SEGMENTS:
                return True
    return False


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
