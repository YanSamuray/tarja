"""Conversão opcional de documentos de texto pelo LibreOffice instalado localmente."""

import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from tarja.models import ProcessingError


def find_libreoffice(explicit: str | Path | None = None) -> Path:
    if explicit:
        binary = Path(explicit).expanduser().resolve()
        if binary.is_file():
            return binary
        raise ProcessingError("Executável informado em --libreoffice não foi encontrado.")
    for command in ("soffice", "libreoffice"):
        found = shutil.which(command)
        if found:
            return Path(found)
    for candidate in (
        Path("C:/Program Files/LibreOffice/program/soffice.com"),
        Path("C:/Program Files (x86)/LibreOffice/program/soffice.com"),
        Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"),
    ):
        if candidate.is_file():
            return candidate
    raise ProcessingError(
        "DOCX, ODT e RTF exigem LibreOffice. Instale-o e, se necessário, use --libreoffice."
    )


@contextmanager
def office_as_pdf(source: Path, executable: str | Path | None = None) -> Iterator[Path]:
    binary = find_libreoffice(executable)
    with tempfile.TemporaryDirectory(prefix="tarja-office-") as directory:
        folder = Path(directory)
        profile = folder / "profile"
        (profile / "user").mkdir(parents=True)
        (profile / "user" / "registrymodifications.xcu").write_text(
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<oor:items xmlns:oor="http://openoffice.org/2001/registry">'
            '<item oor:path="/org.openoffice.Office.Common/Security/Scripting">'
            '<prop oor:name="MacroSecurityLevel" oor:op="fuse"><value>3</value></prop>'
            "</item></oor:items>",
            encoding="utf-8",
        )
        try:
            completed = subprocess.run(
                [
                    str(binary),
                    f"-env:UserInstallation={profile.as_uri()}",
                    "--headless",
                    "--nologo",
                    "--nodefault",
                    "--norestore",
                    "--convert-to",
                    "pdf:writer_pdf_Export",
                    "--outdir",
                    str(folder),
                    str(source),
                ],
                capture_output=True,
                timeout=120,
                check=False,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except subprocess.TimeoutExpired:
            raise ProcessingError("Conversão pelo LibreOffice excedeu 120 segundos.") from None
        except OSError:
            raise ProcessingError("Não foi possível iniciar o LibreOffice.") from None
        converted = folder / f"{source.stem}.pdf"
        if completed.returncode != 0 or not converted.is_file() or not converted.stat().st_size:
            raise ProcessingError("LibreOffice não produziu um PDF válido para processamento.")
        yield converted
