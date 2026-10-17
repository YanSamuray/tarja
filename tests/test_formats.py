import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pymupdf
import pytest
from PIL import Image

from tarja.formats import batch_output_path, censor_document
from tarja.formats.office import find_libreoffice, office_as_pdf
from tarja.main import main
from tarja.models import ENTITIES, Policy, ProcessingError

SAMPLE = (
    "CPF: 123.456.789-00\r\nRG: 12.345.678-9\r\nCNH: 98765432100\r\n"
    "Título de eleitor: 1234 5678 9012\r\nItem 123, parcela 00.\r\n"
)


@pytest.mark.parametrize("suffix", [".txt", ".md"])
def test_text_replaces_values_without_losing_unrelated_content(tmp_path, suffix):
    source, target = tmp_path / f"input{suffix}", tmp_path / f"output{suffix}"
    source.write_bytes(SAMPLE.encode("utf-8"))
    report = censor_document(source, target, Policy(entities=ENTITIES))
    content = target.read_bytes().decode("utf-8")
    assert "CPF: ***.456.789-**\r\n" in content
    assert "RG: **.***.***-*\r\n" in content
    assert "CNH: ***********\r\n" in content
    assert "Título de eleitor: **** **** ****\r\n" in content
    assert "Item 123, parcela 00.\r\n" in content
    assert source.read_bytes() == SAMPLE.encode("utf-8")
    assert report.input_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert report.input_format == suffix[1:]
    assert report.output_format == "utf8_text"
    assert report.pages[0].counts == dict.fromkeys(ENTITIES, 1)


def test_text_full_cpf_mode_and_utf8_bom(tmp_path):
    source, target = tmp_path / "a.txt", tmp_path / "b.txt"
    source.write_bytes("CPF: 123.456.789-00".encode("utf-8-sig"))
    censor_document(source, target, Policy(cpf_mode="full"))
    assert target.read_text(encoding="utf-8") == "CPF: ***.***.***-**"


def test_invalid_encoding_does_not_export(tmp_path):
    source, target = tmp_path / "a.txt", tmp_path / "b.txt"
    source.write_bytes(b"CPF: 12345678900\xff")
    with pytest.raises(ProcessingError, match="UTF-8"):
        censor_document(source, target)
    assert not target.exists()


def test_windows_line_breaks_and_markdown_emphasis(tmp_path):
    source, target = tmp_path / "a.md", tmp_path / "b.md"
    source.write_bytes(b"CPF: 123.456.\r\n789-00\r\n_987.654.321-00_\r\n")
    report = censor_document(source, target, Policy(cpf_mode="full"))
    assert target.read_bytes() == b"CPF: ***.***.\r\n***-**\r\n_***.***.***-**_\r\n"
    assert report.pages[0].counts == {"CPF": 2}


def test_irregular_cpf_is_fully_masked_and_suspects_are_located(tmp_path):
    source, target = tmp_path / "a.txt", tmp_path / "b.txt"
    source.write_bytes(b"CPF: 1234567890\ntelefone: 11987654321\n")
    report = censor_document(source, target)
    assert target.read_bytes() == b"CPF: **********\ntelefone: 11987654321\n"
    page = report.pages[0]
    assert page.warnings == [
        "cpf_irregular_expanded_to_full",
        "unredacted_candidates_require_review",
    ]
    candidate = {"entity": "CPF", "reason": "excluded_label", "start": 26, "end": 37}
    assert page.candidates == [candidate]


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ([], ["CPF"]),
        (["--rg"], ["CPF", "RG"]),
        (["--cnh"], ["CPF", "CNH"]),
        (["--rg", "--cnh"], ["CPF", "RG", "CNH"]),
        (["--titulo-eleitor"], ["CPF", "TITULO_ELEITOR"]),
        (["--todos"], list(ENTITIES)),
        (["--entities", "RG"], ["RG"]),
    ],
)
def test_cli_entity_switches(tmp_path, flags, expected):
    source, target = tmp_path / "a.txt", tmp_path / "b.txt"
    source.write_bytes(SAMPLE.encode("utf-8"))
    assert main([str(source), str(target), *flags]) == 0
    report = json.loads(next(tmp_path.glob("report-*.json")).read_text(encoding="utf-8"))
    assert report["schema_version"] == 3
    assert report["policy"]["entities"] == expected
    assert set(report["documents"][0]["pages"][0]["counts"]) == set(expected)
    if "CNH" not in expected:
        assert "CNH: 98765432100" in target.read_text(encoding="utf-8")


def test_conflicting_selectors_are_rejected():
    with pytest.raises(SystemExit) as error:
        main(["--entities", "RG", "--cnh"])
    assert error.value.code == 2


def test_batch_destinations_do_not_collide(tmp_path):
    expected = {"a.pdf": "a.pdf", "a.docx": "a.docx.pdf", "a.png": "a.png.pdf", "a.md": "a.md"}
    for source, target in expected.items():
        assert batch_output_path(tmp_path / source, tmp_path, tmp_path / "out").name == target


def test_new_formats_refuse_wrong_extension_and_overwrite(tmp_path):
    source = tmp_path / "a.txt"
    source.write_text(SAMPLE, encoding="utf-8")
    with pytest.raises(ProcessingError, match="saída .txt"):
        censor_document(source, tmp_path / "b.pdf")
    with pytest.raises(ProcessingError, match="diferentes"):
        censor_document(source, source)
    target = tmp_path / "exists.txt"
    target.write_text("preservar", encoding="utf-8")
    with pytest.raises(ProcessingError, match="já existe"):
        censor_document(source, target)
    assert target.read_text() == "preservar"


def test_formats_help_and_unsupported_type(tmp_path, capsys):
    assert main(["--formats"]) == 0
    assert "DOCX" in capsys.readouterr().out
    with pytest.raises(ProcessingError, match="não suportado"):
        censor_document(tmp_path / "a.xlsx", tmp_path / "b.pdf")


def synthetic_image():
    with pymupdf.open() as doc:
        page = doc.new_page(width=420, height=160)
        page.insert_text((30, 60), "CPF: 123.456.789-00", fontsize=22)
        page.insert_text((30, 110), "Referencia 123", fontsize=16)
        pixmap = page.get_pixmap(dpi=150, alpha=False)
        return Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)


@pytest.mark.ocr
@pytest.mark.parametrize("suffix", ["png", "jpg", "jpeg", "tif", "tiff", "bmp", "webp"])
def test_real_image_ocr(tmp_path, suffix):
    tessdata = os.environ.get("TEST_TESSDATA")
    if not tessdata:
        pytest.skip("Defina TEST_TESSDATA para executar OCR real.")
    source, target = tmp_path / f"input.{suffix}", tmp_path / "out.pdf"
    synthetic_image().save(source)
    original = source.read_bytes()
    report = censor_document(source, target, Policy(tessdata=tessdata, dpi=150))
    assert report.input_format == suffix
    assert report.input_sha256 == hashlib.sha256(original).hexdigest()
    assert report.pages[0].counts == {"CPF": 1}
    assert source.read_bytes() == original
    with pymupdf.open(target) as doc:
        page = doc[0]
        assert not page.get_text()
        textpage = page.get_textpage_ocr(language="por+eng", tessdata=tessdata, full=True)
        recognized = page.get_text(textpage=textpage)
        assert "123.456.789" not in recognized
        assert "Referencia 123" in recognized


def test_image_requires_ocr(tmp_path):
    source, target = tmp_path / "input.png", tmp_path / "out.pdf"
    synthetic_image().save(source)
    with pytest.raises(ProcessingError, match="exigem OCR"):
        censor_document(source, target, Policy(ocr="never"))
    assert not target.exists()


@pytest.mark.ocr
def test_multiframe_tiff(tmp_path):
    tessdata = os.environ.get("TEST_TESSDATA")
    if not tessdata:
        pytest.skip("Defina TEST_TESSDATA para executar OCR real.")
    image = synthetic_image()
    source, target = tmp_path / "input.tiff", tmp_path / "out.pdf"
    image.save(source, save_all=True, append_images=[image])
    report = censor_document(source, target, Policy(tessdata=tessdata, dpi=150))
    assert len(report.pages) == 2
    assert [page.counts for page in report.pages] == [{"CPF": 1}, {"CPF": 1}]


def test_office_converter_contract_and_temporary_cleanup(tmp_path, monkeypatch):
    source = tmp_path / "input.docx"
    source.write_bytes(b"synthetic input handled by stub")
    monkeypatch.setattr("tarja.formats.office.find_libreoffice", lambda explicit: Path("soffice"))

    def fake_run(command, **kwargs):
        assert "--headless" in command
        assert kwargs["timeout"] == 120
        assert kwargs["capture_output"] is True
        output_dir = Path(command[command.index("--outdir") + 1])
        with pymupdf.open() as doc:
            doc.new_page().insert_text((30, 50), "CPF: 123.456.789-00")
            doc.save(output_dir / "input.pdf")
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr("tarja.formats.office.subprocess.run", fake_run)
    with office_as_pdf(source) as converted:
        temporary = converted.parent
        assert converted.exists()
    assert not temporary.exists()
    report = censor_document(source, tmp_path / "out.pdf", Policy(dpi=150))
    assert report.input_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert report.input_format == "docx"
    assert report.warnings == ["office_conversion_requires_layout_review"]


@pytest.mark.parametrize("failure", ["timeout", "exit", "no_file"])
def test_office_failure_never_exports(tmp_path, monkeypatch, failure):
    source, target = tmp_path / "input.docx", tmp_path / "out.pdf"
    source.write_bytes(b"synthetic")
    monkeypatch.setattr("tarja.formats.office.find_libreoffice", lambda explicit: Path("soffice"))

    def fake_run(command, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 120)
        return SimpleNamespace(returncode=1 if failure == "exit" else 0)

    monkeypatch.setattr("tarja.formats.office.subprocess.run", fake_run)
    with pytest.raises(ProcessingError):
        censor_document(source, target)
    assert not target.exists()


def test_missing_office_executable(tmp_path):
    with pytest.raises(ProcessingError, match="não foi encontrado"):
        find_libreoffice(tmp_path / "missing-soffice")


@pytest.mark.office
def test_real_docx_conversion(tmp_path):
    try:
        executable = find_libreoffice(os.environ.get("TEST_LIBREOFFICE"))
    except ProcessingError:
        pytest.skip("LibreOffice não instalado: integração real não executada.")
    source = tmp_path / "input.docx"
    with zipfile.ZipFile(source, "w") as package:
        package.writestr(
            "[Content_Types].xml",
            (
                '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                '<Default Extension="rels" '
                'ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
                '<Override PartName="/word/document.xml" ContentType="application/'
                'vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
                "</Types>"
            ),
        )
        package.writestr(
            "_rels/.rels",
            (
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/'
                'officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                "</Relationships>"
            ),
        )
        package.writestr(
            "word/document.xml",
            (
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                "<w:body><w:p><w:r><w:t>CPF: 123.456.789-00</w:t></w:r></w:p></w:body></w:document>"
            ),
        )
    report = censor_document(source, tmp_path / "out.pdf", libreoffice=executable)
    assert report.pages[0].counts == {"CPF": 1}
