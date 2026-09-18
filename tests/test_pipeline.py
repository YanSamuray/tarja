import json
import os
from dataclasses import asdict

import pymupdf
import pytest
from pypdf import PdfReader

from tarja.censor import censor_pdf, redaction_rects, sha256
from tarja.detectors import detect_identifiers
from tarja.main import main
from tarja.models import ENTITIES, Policy, ProcessingError
from tarja.ocr import extract_page


@pytest.fixture
def pdf(tmp_path):
    source = tmp_path / "entrada.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page(width=420, height=260)
        page.insert_text((30, 45), "CPF: 123.456.789-00", fontsize=15)
        page.insert_text((30, 95), "Preservar: 123 unidades, item 00", fontsize=15)
        page.insert_text((30, 140), "RG: 12.345.678-9", fontsize=15)
        page.insert_text((30, 180), "CNH: 12345678900", fontsize=15)
        doc.set_metadata({"author": "123.456.789-00", "title": "Dado sensivel"})
        doc.embfile_add("anexo.txt", b"123.456.789-00")
        doc.save(source)
    return source


def test_only_the_cpf_occurrence_is_targeted(pdf):
    with pymupdf.open(pdf) as doc:
        extracted = extract_page(doc[0], Policy())
        detected = detect_identifiers(extracted.text)[0]
        rects = redaction_rects(extracted, detected, Policy())
        assert len(rects) == 2
        assert all(rect.y1 < 60 for rect in rects)
        for rect in rects:
            doc[0].add_redact_annot(rect, fill=(0, 0, 0))
        doc[0].apply_redactions()
        text = doc[0].get_text()
        assert "456.789" in text
        assert "123 unidades, item 00" in text
        assert "123.456.789-00" not in text


def test_export_contains_only_sanitized_pixels_and_neutral_metadata(pdf, tmp_path):
    output = tmp_path / "saida.pdf"
    before = sha256(pdf)
    report = censor_pdf(pdf, output, Policy(entities=ENTITIES, dpi=150))
    assert sha256(pdf) == before
    assert report.input_sha256 == before
    assert report.output_sha256 == sha256(output)
    assert report.pages[0].counts == {"CPF": 1, "RG": 1, "CNH": 1}
    assert report.status == "requires_review"
    assert "123.456.789-00" not in json.dumps(asdict(report))
    reader = PdfReader(output)
    assert len(reader.pages) == 1
    assert reader.pages[0].extract_text() == ""
    assert not reader.attachments
    assert not reader.metadata.author
    assert "Dado sensivel" not in str(reader.metadata)
    with pymupdf.open(output) as doc:
        # Testa os pixels embutidos, não apenas uma anotação cobrindo a imagem.
        image = pymupdf.Pixmap(doc, doc[0].get_images()[0][0])
        x0, y0, x1, y1 = report.pages[0].regions[0]["bbox"]
        x = round((x0 + x1) / 2 * 150 / 72)
        y = round((y0 + y1) / 2 * 150 / 72)
        assert image.pixel(x, y)[:3] == (0, 0, 0)
        assert doc[0].first_annot is None


def test_preserves_unrelated_region_pixels(pdf, tmp_path):
    output = tmp_path / "out.pdf"
    censor_pdf(pdf, output, Policy(dpi=150))
    with pymupdf.open(pdf) as original, pymupdf.open(output) as redacted:
        before = original[0].get_pixmap(dpi=150, alpha=False)
        after = pymupdf.Pixmap(redacted, redacted[0].get_images()[0][0])
        # A faixa com "123 unidades, item 00" deve ser idêntica.
        assert before.width == after.width
        y0, y1 = 75 * 150 // 72, 103 * 150 // 72
        assert (
            before.samples[y0 * before.stride : y1 * before.stride]
            == (after.samples[y0 * after.stride : y1 * after.stride])
        )


def test_refuses_overwrite_and_source_as_target(pdf, tmp_path):
    with pytest.raises(ProcessingError, match="diferentes"):
        censor_pdf(pdf, pdf)
    output = tmp_path / "exists.pdf"
    output.write_bytes(b"preservar")
    with pytest.raises(ProcessingError, match="já existe"):
        censor_pdf(pdf, output)
    assert output.read_bytes() == b"preservar"


def make_mixed_pdf(path):
    with pymupdf.open() as doc:
        page = doc.new_page(width=420, height=260)
        page.insert_text((30, 45), "Pagina digital sem identificadores", fontsize=15)
        with pymupdf.open() as scan:
            page = scan.new_page(width=420, height=260)
            page.insert_text((30, 80), "CPF: 123.456.789-00", fontsize=22)
            image = page.get_pixmap(dpi=300).tobytes("png")
        page = doc.new_page(width=420, height=260)
        page.insert_image(page.rect, stream=image)
        # Reproduz o problema do cabeçalho que fazia o script pular OCR.
        page.insert_text((30, 30), "Cabecalho digital", fontsize=12)
        doc.save(path)


def test_mixed_pdf_never_silently_skips_scan(tmp_path):
    source, target = tmp_path / "mixed.pdf", tmp_path / "out.pdf"
    make_mixed_pdf(source)
    with pytest.raises(ProcessingError, match="exige OCR"):
        censor_pdf(source, target, Policy(ocr="never", dpi=150))
    assert not target.exists()
    assert not list(tmp_path.glob(".censor-*"))


def test_missing_ocr_does_not_export_partial_success(tmp_path):
    source, target = tmp_path / "mixed.pdf", tmp_path / "out.pdf"
    make_mixed_pdf(source)
    with pytest.raises(ProcessingError, match="OCR indisponível"):
        censor_pdf(source, target, Policy(tessdata=str(tmp_path / "missing")))
    assert not target.exists()


@pytest.mark.ocr
def test_real_ocr_mixed_pdf(tmp_path):
    tessdata = os.environ.get("TEST_TESSDATA")
    if not tessdata:
        pytest.skip("Defina TEST_TESSDATA para executar OCR real com por+eng.")
    source, target = tmp_path / "mixed.pdf", tmp_path / "out.pdf"
    make_mixed_pdf(source)
    report = censor_pdf(source, target, Policy(tessdata=tessdata))
    assert [page.extraction for page in report.pages] == ["native", "ocr"]
    assert report.pages[1].counts["CPF"] == 1
    assert "ocr_cpf_expanded_to_full" in report.pages[1].warnings
    with pymupdf.open(target) as doc:
        page = doc[1]
        textpage = page.get_textpage_ocr(language="por+eng", tessdata=tessdata, full=True)
        text = page.get_text(textpage=textpage)
        assert "123.456.789" not in text
        assert "12345678900" not in text
        image = pymupdf.Pixmap(doc, doc[1].get_images()[0][0])
        x0, y0, x1, y1 = report.pages[1].regions[0]["bbox"]
        assert image.pixel(round((x0 + x1) / 2 * 300 / 72), round((y0 + y1) / 2 * 300 / 72)) == (
            0,
            0,
            0,
        )


def test_rotated_page_and_full_cpf_mode(pdf, tmp_path):
    rotated, target = tmp_path / "rotated.pdf", tmp_path / "out.pdf"
    with pymupdf.open(pdf) as doc:
        doc[0].set_rotation(90)
        doc.save(rotated)
    report = censor_pdf(rotated, target, Policy(cpf_mode="full", dpi=150))
    assert len([r for r in report.pages[0].regions if r["entity"] == "CPF"]) == 1
    with pymupdf.open(target) as doc:
        assert doc[0].rotation == 90
        assert doc[0].rect.width == 260


def test_form_is_not_silently_flattened(tmp_path):
    source, target = tmp_path / "form.pdf", tmp_path / "out.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        widget = pymupdf.Widget()
        widget.field_name = "cpf"
        widget.field_type = pymupdf.PDF_WIDGET_TYPE_TEXT
        widget.field_value = "12345678900"
        widget.rect = pymupdf.Rect(30, 30, 200, 60)
        page.add_widget(widget)
        doc.save(source)
    with pytest.raises(ProcessingError, match="formulários"):
        censor_pdf(source, target)
    assert not target.exists()


def test_batch_continues_after_bad_file_and_excludes_values_from_report(pdf, tmp_path):
    batch, output = tmp_path / "batch", tmp_path / "output"
    batch.mkdir()
    (batch / "a.pdf").write_bytes(b"not a pdf")
    (batch / "b.PDF").write_bytes(pdf.read_bytes())
    assert main([str(batch), str(output), "--dpi", "150", "--todos"]) == 1
    assert (output / "b.PDF").exists()
    report = json.loads(next(output.glob("report-*.json")).read_text(encoding="utf-8"))
    assert [d["status"] for d in report["documents"]] == ["failed", "requires_review"]
    assert "12345678900" not in json.dumps(report)
    assert str(pdf) not in json.dumps(report)


def test_recursive_output_cannot_reenter_input(tmp_path):
    assert main([str(tmp_path), str(tmp_path / "out"), "--recursive"]) == 2


def test_missing_input_returns_error(tmp_path):
    assert main([str(tmp_path / "missing"), str(tmp_path / "out")]) == 2


@pytest.mark.ocr
def test_forced_ocr_keeps_native_evidence_without_double_counting(pdf, tmp_path):
    tessdata = os.environ.get("TEST_TESSDATA")
    if not tessdata:
        pytest.skip("Defina TEST_TESSDATA para executar OCR real com por+eng.")
    report = censor_pdf(
        pdf, tmp_path / "ocr.pdf", Policy(entities=ENTITIES, ocr="always", tessdata=tessdata)
    )
    assert report.pages[0].counts == {"CPF": 1, "RG": 1, "CNH": 1}


def test_two_distinct_equal_cpfs_are_both_redacted(tmp_path):
    source, target = tmp_path / "two.pdf", tmp_path / "out.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((30, 50), "CPF: 123.456.789-00")
        page.insert_text((30, 100), "CPF: 123.456.789-00")
        doc.save(source)
    report = censor_pdf(source, target, Policy(dpi=150))
    assert report.pages[0].counts == {"CPF": 2}
    assert len(report.pages[0].regions) == 4


def test_split_cpf_maps_back_to_its_two_lines(tmp_path):
    source, target = tmp_path / "split.pdf", tmp_path / "out.pdf"
    with pymupdf.open() as doc:
        page = doc.new_page()
        page.insert_text((30, 50), "CPF: 123.456.\n789-00", fontsize=12)
        page.insert_text((30, 140), "Item 123 e parcela 00", fontsize=12)
        doc.save(source)
    report = censor_pdf(source, target, Policy(dpi=150))
    assert report.pages[0].counts == {"CPF": 1}
    assert all(r["bbox"][3] < 100 for r in report.pages[0].regions)


def test_read_error_becomes_controlled_failure(pdf, tmp_path, monkeypatch):
    def denied(path):
        raise PermissionError("sensitive-original-file-name.pdf")

    monkeypatch.setattr("tarja.censor.sha256", denied)
    with pytest.raises(ProcessingError, match="Falha ao processar") as error:
        censor_pdf(pdf, tmp_path / "out.pdf")
    assert "sensitive-original" not in str(error.value)
