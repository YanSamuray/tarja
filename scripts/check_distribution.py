"""Confere os artefatos reais de build para evitar distribuir histórico ou dados locais."""

import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def main():
    artifacts = sorted(Path("dist").glob("*.whl")) + sorted(Path("dist").glob("*.tar.gz"))
    if not artifacts:
        raise SystemExit("Execute uv build antes desta verificação.")
    forbidden = {"archive", "data", "output", ".cache", ".runtime", ".venv", "__pycache__"}
    for artifact in artifacts:
        if artifact.suffix == ".whl":
            with zipfile.ZipFile(artifact) as package:
                names = package.namelist()
        else:
            with tarfile.open(artifact) as package:
                names = package.getnames()
        if any(forbidden.intersection(PurePosixPath(name).parts) for name in names):
            raise SystemExit(f"Build contém pastas proibidas: {artifact.name}")
        if not any(name.endswith("tarja/main.py") for name in names):
            raise SystemExit(f"Pacote Tarja ausente em {artifact.name}")
        print(f"{artifact.name}: OK ({len(names)} arquivos; sem histórico ou dados locais)")


if __name__ == "__main__":
    main()
