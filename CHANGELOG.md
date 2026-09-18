# Alterações

## 0.3.0 - 2026-09-18

- Nome Tarja, comando `tarja`, pacote `tarja` e distribuição `tarja-documentos`.
- Um projeto na raiz com layout `src/`; versões anteriores preservadas em `archive/`.
- Python mínimo 3.14, `.python-version`, execução por uv e novo lockfile.
- CPF por padrão; `--rg`, `--cnh`, `--titulo-eleitor` e `--todos` habilitam outras buscas.
- `--entities` permanece disponível para seleção exata.
- Entradas PNG, JPEG, TIFF, BMP e WEBP, inclusive múltiplos quadros, com saída PDF.
- TXT/Markdown UTF-8 com substituição de identificadores no texto.
- Adaptador opcional de DOCX/ODT/RTF via LibreOffice, com saída PDF e aviso de revisão de layout.
- Nomes de saída sem colisão entre extensões diferentes e relatório com formato original.
- Novo build exclui dados locais e versões arquivadas da distribuição.

## 0.2.0

Reconstrução do motor PDF com OCR por página, detecção por coordenadas, saída estática, relatórios e testes sintéticos. Snapshot e evidências originais em `archive/v0.2/`.
