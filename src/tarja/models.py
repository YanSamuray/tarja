"""Configuração e resultados; os relatórios não guardam os valores detectados."""

from dataclasses import dataclass, field
from typing import Literal

ENTITIES = ("CPF", "RG", "CNH", "TITULO_ELEITOR")


@dataclass(frozen=True)
class Policy:
    entities: tuple[str, ...] = ("CPF",)
    cpf_mode: Literal["partial", "full"] = "partial"
    ocr: Literal["auto", "always", "never"] = "auto"
    language: str = "por+eng"
    tessdata: str | None = None
    dpi: int = 300

    def __post_init__(self):
        if not self.entities or set(self.entities) - set(ENTITIES):
            raise ValueError("Selecione pelo menos um tipo de documento reconhecido.")
        if self.cpf_mode not in ("partial", "full"):
            raise ValueError("Modo de CPF inválido.")
        if self.ocr not in ("auto", "always", "never"):
            raise ValueError("Modo de OCR inválido.")
        if not 150 <= self.dpi <= 600:
            raise ValueError("A resolução deve ficar entre 150 e 600 DPI.")


@dataclass(frozen=True)
class Detection:
    entity: str
    start: int
    end: int
    checksum_valid: bool | None = None


@dataclass(frozen=True)
class Candidate:
    """Número suspeito que não foi censurado; o relatório indica onde conferir."""

    entity: str
    start: int
    end: int
    reason: str


@dataclass
class PageReport:
    page: int
    extraction: str
    counts: dict[str, int] = field(default_factory=dict)
    regions: list[dict] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class DocumentReport:
    input_sha256: str
    output_sha256: str
    pages: list[PageReport]
    elapsed_seconds: float
    status: str = "requires_review"
    output_format: str = "image_only_pdf"
    input_format: str = "pdf"
    warnings: list[str] = field(default_factory=list)


class ProcessingError(RuntimeError):
    """Mensagem de erro controlada, sem trechos do documento de entrada."""
