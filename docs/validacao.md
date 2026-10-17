# Validação do Tarja

A versão 0.3.0 foi validada localmente em 18/09/2026, no Windows, com CPython 3.14.2 e dependências instaladas por `uv sync --locked`.

## Resultado da 0.3.0

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

Os testes e exemplos usam conteúdo sintético. Não foram processados documentos reais nem medidos precisão, falsos negativos ou HH poupadas. Os resultados da versão 0.2 estão preservados localmente em `archive/v0.2/docs/validacao.md`.

## Publicação e CI

O projeto foi publicado em [YanSamuray/tarja](https://github.com/YanSamuray/tarja), sob AGPL-3.0-only. A [execução inicial do GitHub Actions](https://github.com/YanSamuray/tarja/actions/runs/35340615730), referente ao commit `ad73c7c`, concluiu com sucesso em Windows e Linux com Python 3.14: instalação pelo lock, Ruff, testes, build e inspeção dos artefatos. O workflow não instala modelos de OCR nem LibreOffice; os testes que dependem dessas ferramentas seguem as condições de disponibilidade descritas acima. A validação de OCR real relatada nesta página foi executada localmente.

## Versão 0.4.0

Registro de 17/10/2026. Escopo: correção de lacunas de detecção, pontos para conferência no relatório, formulários e anotações incorporados antes da censura, saída em tons de cinza, Python mínimo 3.11 e CI com as ferramentas reais. O workflow baixa os modelos `tessdata_fast` 4.1.0, conferidos pelos SHA-256 acima, e instala o LibreOffice no Linux.

### Execuções locais

No Windows, sem LibreOffice instalado:

| Ambiente | Resultado |
| --- | --- |
| CPython 3.14.2, com OCR real | 153 aprovados, 1 pulado (conversão real de DOCX) |
| CPython 3.14.2, sem `TEST_TESSDATA` | 142 aprovados, 12 pulados |
| CPython 3.11.14, ambiente isolado, com OCR real | 153 aprovados, 1 pulado |

### GitHub Actions

Na [execução 39005867605](https://github.com/YanSamuray/tarja/actions/runs/39005867605), commit `50ecd6a`, os seis jobs da matriz foram aprovados. O log de cada job confirma a versão do Python usada.

| Sistema | Python | Resultado |
| --- | --- | --- |
| Linux | 3.11.17, 3.12.15, 3.13.16, 3.14.8 | 154 aprovados, nenhum pulado |
| Windows | 3.11.9, 3.14.8 | 153 aprovados, 1 pulado (LibreOffice, não instalado no Windows) |

No Linux, a conversão DOCX → PDF pelo LibreOffice é executada de fato e seguida da censura. A primeira execução registrada foi a [39002493922](https://github.com/YanSamuray/tarja/actions/runs/39002493922). Ruff, build e inspeção dos artefatos foram aprovados em todos os jobs.

Os testes continuam sintéticos: não foram processados documentos reais nem medidas precisão, falsos negativos ou HH poupadas.
