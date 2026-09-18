# Validação do Tarja 0.3.0

Executada localmente em 18/09/2026, no Windows, com CPython 3.14.2 e dependências instaladas por `uv sync --locked`.

## Resultado

- **66 testes aprovados; 1 teste pulado.**
- OCR real executado com os modelos locais `por` e `eng`.
- O teste pulado é a conversão real de DOCX pelo LibreOffice, que não está instalado nesta máquina. O adaptador foi testado com execução simulada, verificando o comando, os hashes, a limpeza dos temporários, o timeout, os erros e a ausência de resultados em caso de falha.
- Análise estática e formatação executadas com Ruff.
- Wheel e distribuição de fontes gerados com `uv build`.
- Conteúdo dos dois artefatos inspecionado para excluir histórico, documentos locais, caches e resultados.

## Cobertura

CPF com formatos diferentes, prefixo `nº`, quebra de linha, repetição e DV inválido; contexto de RG, CNH e título; exclusão de números alheios; preservação de originais; pixels de saída; ausência de texto e anexos no PDF exportado; páginas mistas; rotação; falhas de leitura e OCR; recusa de formulários; isolamento de erros no lote; regras de sobrescrita.

Na versão 0.3 foram acrescentados testes para flags de seleção, TXT/MD, UTF-8/BOM, preservação de CRLF, formato de saída, colisões de nomes, PNG, JPG, JPEG, TIF, TIFF, BMP, WEBP e TIFF com dois quadros. Os testes reais das imagens executam OCR também na saída e verificam que o CPF censurado deixou de ser reconhecido, enquanto uma referência não sensível permanece legível.

## Reproduzir

```powershell
uv sync --locked
$env:TEST_TESSDATA = (Resolve-Path '.runtime/tessdata').Path
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv build
uv run python scripts/check_distribution.py
```

Sem `TEST_TESSDATA`, os testes de OCR real são pulados explicitamente. A integração Office é habilitada se o LibreOffice for encontrado ou indicado por `TEST_LIBREOFFICE`. O adaptador não deve ser apresentado como validado de ponta a ponta nesta máquina até esse teste ser executado.

Modelos locais usados: `tesseract-ocr/tessdata_fast`, tag `4.1.0`. SHA-256:

```text
eng 7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2
por c4932b937207a9514b7514d518b931a99938c02a28a5a5a553f8599ed58b7deb
```

Os testes e exemplos usam conteúdo sintético. Não foram processados documentos reais nem medidos precisão, falsos negativos ou HH poupadas. O workflow para Windows/Linux foi atualizado para Python 3.14, mas não foi executado no GitHub nesta sessão. Os resultados da versão 0.2 estão preservados em `archive/v0.2/docs/validacao.md`.
