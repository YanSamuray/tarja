"""Normaliza orientação e páginas de imagens antes de aplicar o OCR local."""

import io
import tempfile
import warnings
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import pymupdf
from PIL import Image, ImageOps, ImageSequence

from tarja.models import Policy, ProcessingError


@contextmanager
def image_as_pdf(source: Path, policy: Policy) -> Iterator[Path]:
    if policy.ocr == "never":
        raise ProcessingError("Imagens exigem OCR; use --ocr auto ou always.")
    with tempfile.TemporaryDirectory(prefix="tarja-image-") as directory:
        converted = Path(directory) / "image.pdf"
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with Image.open(source) as image, pymupdf.open() as pdf:
                    if getattr(image, "n_frames", 1) > 300:
                        raise ProcessingError("A imagem deve conter no máximo 300 páginas/quadros.")
                    for frame in ImageSequence.Iterator(image):
                        # Fundo branco para transparência; EXIF e outros metadados não são copiados.
                        normalized = ImageOps.exif_transpose(frame.copy()).convert("RGBA")
                        clean = Image.new("RGB", normalized.size, "white")
                        clean.paste(normalized, mask=normalized.getchannel("A"))
                        stream = io.BytesIO()
                        clean.save(stream, format="PNG")
                        page = pdf.new_page(
                            width=clean.width * 72 / policy.dpi,
                            height=clean.height * 72 / policy.dpi,
                        )
                        page.insert_image(page.rect, stream=stream.getvalue())
                    pdf.save(converted, deflate=True)
        except ProcessingError:
            raise
        except Exception:
            raise ProcessingError("Imagem inválida ou grande demais para processamento.") from None
        yield converted
