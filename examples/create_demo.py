"""Demonstração reproduzível: usa exclusivamente conteúdo fictício."""

import json
from dataclasses import asdict
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from tarja.censor import censor_pdf
from tarja.models import ENTITIES, Policy


def create_demo(destination: Path):
    destination.mkdir(parents=True, exist_ok=True)
    original = destination / "demo-original.pdf"
    redacted = destination / "demo-censurado.pdf"
    if original.exists() or redacted.exists():
        raise FileExistsError("A demonstração já existe. Use outro diretório de saída.")
    width, height = A4
    doc = canvas.Canvas(str(original), pagesize=A4)
    doc.setTitle("Demonstração com dados fictícios")
    navy = colors.HexColor("#163543")
    teal = colors.HexColor("#137D81")
    gray = colors.HexColor("#556671")
    doc.setFillColor(navy)
    doc.rect(0, height - 190, width, 190, fill=1, stroke=0)
    doc.setFillColor(colors.HexColor("#8FE0D0"))
    doc.setFont("Helvetica-Bold", 10)
    doc.drawString(48, height - 50, "TARJA / DEMONSTRACAO")
    doc.setFillColor(colors.white)
    doc.setFont("Helvetica-Bold", 28)
    doc.drawString(48, height - 94, "Censura de documentos")
    doc.setFont("Helvetica", 12)
    doc.drawString(48, height - 124, "Automacao de uma tarefa real de revisao documental.")
    doc.drawString(48, height - 146, "Esta amostra contem somente dados ficticios.")
    doc.setFillColor(teal)
    doc.setFont("Helvetica-Bold", 11)
    doc.drawString(48, height - 236, "01 / IDENTIFICADORES PARA CENSURA")
    rows = [
        "CPF: 123.456.789-00",
        "RG: 12.345.678-9",
        "CNH: 12345678900",
        "Titulo de eleitor: 1234 5678 9012",
    ]
    for index, text in enumerate(rows):
        y = height - 278 - index * 47
        doc.setFillColor(colors.HexColor("#F1F5F5"))
        doc.roundRect(48, y - 12, width - 96, 38, 6, fill=1, stroke=0)
        doc.setFillColor(navy)
        doc.setFont("Helvetica", 14)
        doc.drawString(64, y, text)
    doc.setFillColor(teal)
    doc.setFont("Helvetica-Bold", 11)
    doc.drawString(48, height - 497, "02 / CONTEUDO QUE DEVE PERMANECER")
    doc.setFillColor(navy)
    doc.setFont("Helvetica", 13)
    doc.drawString(48, height - 532, "Referencia: item 123, parcela 00, total de 25 paginas.")
    doc.drawString(48, height - 558, "Responsavel: Pessoa Exemplo. Unidade: Setor Demonstrativo.")
    doc.setFillColor(gray)
    doc.setFont("Helvetica", 10)
    for index, text in enumerate(
        [
            "Na politica parcial, permanecem os seis digitos centrais do CPF.",
            "RG, CNH e titulo de eleitor recebem censura completa.",
            "A copia de saida deve passar por revisao visual antes de ser compartilhada.",
        ]
    ):
        doc.drawString(48, height - 623 - index * 19, text)
    doc.setStrokeColor(colors.HexColor("#DCE5E7"))
    doc.line(48, 70, width - 48, 70)
    doc.setFillColor(gray)
    doc.setFont("Helvetica", 9)
    doc.drawString(48, 50, "AMOSTRA SINTETICA | Sem vinculo com pessoas ou processos reais")
    doc.drawRightString(width - 48, 50, "01")
    doc.save()
    report = censor_pdf(original, redacted, Policy(entities=ENTITIES))
    (destination / "demo-report.json").write_text(
        json.dumps(asdict(report), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Demonstração criada em: {destination.resolve()}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path, nargs="?", default=Path("output/demo"))
    create_demo(parser.parse_args().output)
