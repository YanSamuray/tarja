"""Adaptadores de formatos; todos reutilizam as mesmas regras de identificação."""

from pathlib import Path
from time import perf_counter

from tarja.censor import censor_pdf, sha256
from tarja.formats.images import image_as_pdf
from tarja.formats.office import office_as_pdf
from tarja.formats.text import censor_text_file
from tarja.models import DocumentReport, Policy, ProcessingError

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".webp"})
TEXT_EXTENSIONS = frozenset({".txt", ".md"})
OFFICE_EXTENSIONS = frozenset({".docx", ".odt", ".rtf"})
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | TEXT_EXTENSIONS | OFFICE_EXTENSIONS | {".pdf"}


def output_suffix(source: Path) -> str:
    suffix = source.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ProcessingError("Formato de entrada não suportado. Consulte --formats.")
    return suffix if suffix in TEXT_EXTENSIONS else ".pdf"


def batch_output_path(source: Path, input_dir: Path, output_dir: Path) -> Path:
    relative = source.relative_to(input_dir)
    suffix = output_suffix(source)
    # relatorio.docx -> relatorio.docx.pdf: evita colisão com relatorio.pdf ou .png.
    if source.suffix.lower() != suffix:
        relative = relative.with_name(relative.name + suffix)
    return output_dir / relative


def censor_document(
    source: str | Path,
    target: str | Path,
    policy: Policy | None = None,
    *,
    libreoffice: str | Path | None = None,
) -> DocumentReport:
    source, target = Path(source).resolve(), Path(target).resolve()
    policy = policy or Policy()
    try:
        expected = output_suffix(source)
        if source == target:
            raise ProcessingError("Entrada e saída devem ser arquivos diferentes.")
        if not source.is_file():
            raise ProcessingError("O arquivo de entrada não existe.")
        if target.suffix.lower() != expected:
            raise ProcessingError(f"Este formato de entrada exige saída {expected}.")
        if target.exists():
            raise ProcessingError("O arquivo de saída já existe; escolha outro destino.")
        if source.stat().st_size > 100 * 1024 * 1024:
            raise ProcessingError("O limite desta versão é 100 MB por arquivo.")
        suffix = source.suffix.lower()
        if suffix == ".pdf":
            return censor_pdf(source, target, policy)
        if suffix in TEXT_EXTENSIONS:
            return censor_text_file(source, target, policy)
        started = perf_counter()
        original_hash = sha256(source)
        converter = (
            image_as_pdf(source, policy)
            if suffix in IMAGE_EXTENSIONS
            else office_as_pdf(source, libreoffice)
        )
        with converter as pdf:
            report = censor_pdf(pdf, target, policy)
        report.input_sha256 = original_hash
        report.input_format = suffix.removeprefix(".")
        report.elapsed_seconds = round(perf_counter() - started, 3)
        if suffix in OFFICE_EXTENSIONS:
            report.warnings.append("office_conversion_requires_layout_review")
        return report
    except ProcessingError:
        raise
    except Exception:
        raise ProcessingError(
            "Falha ao processar o arquivo; verifique a entrada e o destino."
        ) from None
