"""Interface de linha de comando, incluindo processamento em lote."""

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from tarja import __version__
from tarja.formats import (
    SUPPORTED_EXTENSIONS,
    batch_output_path,
    censor_document,
    output_suffix,
)
from tarja.models import ENTITIES, Policy, ProcessingError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tarja", description="Tarja: censura local de identificadores pessoais."
    )
    parser.add_argument("--version", action="version", version=f"Tarja {__version__}")
    parser.add_argument("--formats", action="store_true", help="Listar formatos e dependências.")
    parser.add_argument("input", nargs="?", type=Path, default=Path("data/input"))
    parser.add_argument("output", nargs="?", type=Path, default=Path("data/output"))
    parser.add_argument("--cpf", action="store_true", help="Buscar CPF (habilitado por padrão).")
    parser.add_argument("--rg", action="store_true", help="Acrescentar busca por RG.")
    parser.add_argument("--cnh", action="store_true", help="Acrescentar busca por CNH.")
    parser.add_argument(
        "--titulo-eleitor", action="store_true", help="Acrescentar título de eleitor."
    )
    parser.add_argument(
        "--todos", "--all", action="store_true", help="Habilitar as quatro categorias."
    )
    parser.add_argument(
        "--entities",
        nargs="+",
        choices=ENTITIES,
        help="Selecionar categorias exatas, sem CPF implícito; não combinar com as flags acima.",
    )
    parser.add_argument("--cpf-mode", choices=("partial", "full"), default="partial")
    parser.add_argument("--ocr", choices=("auto", "always", "never"), default="auto")
    parser.add_argument("--language", default="por+eng")
    parser.add_argument("--tessdata", type=Path)
    parser.add_argument("--dpi", type=int, default=300)
    parser.add_argument("--recursive", action="store_true")
    parser.add_argument(
        "--libreoffice", type=Path, help="Caminho para soffice, soffice.com ou soffice.exe."
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.formats:
        print("PDF -> PDF estático; OCR local para conteúdo visual.")
        print("PNG, JPG/JPEG, TIFF/TIF, BMP, WEBP -> PDF estático; OCR obrigatório.")
        print("TXT, MD -> mesmo formato, em UTF-8; somente o texto é processado.")
        print("DOCX, ODT, RTF -> PDF estático; requer LibreOffice instalado.")
        return 0
    flags = {"CPF": args.cpf, "RG": args.rg, "CNH": args.cnh, "TITULO_ELEITOR": args.titulo_eleitor}
    if args.entities and (args.todos or any(flags.values())):
        parser.error("Use --entities ou as flags de documentos, sem combiná-los.")
    entities = (
        tuple(args.entities)
        if args.entities
        else (ENTITIES if args.todos else tuple(e for e in ENTITIES if e == "CPF" or flags[e]))
    )
    source, target = args.input.resolve(), args.output.resolve()
    try:
        policy = Policy(
            entities,
            args.cpf_mode,
            args.ocr,
            args.language,
            str(args.tessdata.resolve()) if args.tessdata else None,
            args.dpi,
        )
        if not source.exists():
            raise ProcessingError("Diretório ou arquivo de entrada não encontrado.")
        if source.is_file():
            expected = output_suffix(source)
            if target.suffix.lower() != expected:
                raise ProcessingError(
                    f"Para este arquivo de entrada, indique um arquivo {expected} na saída."
                )
            pairs = [(source, target)]
            report_dir = target.parent
        else:
            if target == source or target.is_relative_to(source):
                raise ProcessingError("O destino do lote deve ficar fora da pasta de entrada.")
            files = source.rglob("*") if args.recursive else source.iterdir()
            pairs = [
                (p, batch_output_path(p, source, target))
                for p in sorted(files)
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
            ]
            report_dir = target
        if not pairs:
            raise ProcessingError("Nenhum arquivo de formato suportado encontrado.")
        report_dir.mkdir(parents=True, exist_ok=True)
        run_id = uuid4().hex
        report_path = report_dir / f"report-{run_id}.json"
        report = {
            "schema_version": 2,
            "run_id": run_id,
            "created_at": datetime.now(UTC).isoformat(),
            "policy": {k: v for k, v in asdict(policy).items() if k != "tessdata"},
            "documents": [],
        }
        failed = 0
        for number, (input_path, output_path) in enumerate(pairs, 1):
            try:
                result = censor_document(
                    input_path, output_path, policy, libreoffice=args.libreoffice
                )
                report["documents"].append({"document": number, **asdict(result)})
                count = sum(sum(p.counts.values()) for p in result.pages)
                print(f"[{number}/{len(pairs)}] {count} ocorrência(s); cópia gerada para revisão.")
            except ProcessingError as error:
                failed += 1
                report["documents"].append(
                    {"document": number, "status": "failed", "error": str(error)}
                )
                print(f"[{number}/{len(pairs)}] Erro: {error}")
        with report_path.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2)
        print(f"Relatório: {report_path}")
        print("Revise cada cópia antes de compartilhar. PDFs exportados são estáticos.")
        return 1 if failed else 0
    except (ProcessingError, ValueError, OSError) as error:
        print(
            f"Erro: {error if not isinstance(error, OSError) else 'Falha de acesso aos arquivos.'}"
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
