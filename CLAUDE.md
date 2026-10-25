# Orientações para o Claude Code

Tarja: CLI local em Python que censura CPF, RG, CNH e título de eleitor em PDFs, imagens, TXT/MD e documentos Office, e gera um relatório para revisão humana. Para uso e comportamento, veja o [README](README.md). Para decisões técnicas, veja [docs/arquitetura.md](docs/arquitetura.md); a seção "Critérios de detecção" explica por que cada regra existe. Responda ao usuário em português.

## Comandos

```bash
uv sync --locked                                     # recria o .venv
TEST_TESSDATA="$PWD/.runtime/tessdata" uv run pytest  # suíte com OCR real
uv run pytest                                         # sem OCR: os testes dependentes são pulados
uv run ruff check . && uv run ruff format --check .
uv build && uv run python scripts/check_distribution.py
TEST_TESSDATA="$PWD/.runtime/tessdata" uv run --isolated --python 3.11 --locked pytest  # versão mínima
```

- Os modelos `por` e `eng` ficam em `.runtime/tessdata/`, fora do Git. Para baixá-los de novo, siga o passo do CI em `.github/workflows/tests.yml`, que confere os SHA-256.
- O LibreOffice não está instalado nesta máquina, então o teste real de DOCX roda só no CI em Linux.
- Esperado no CI: no Linux, nenhum teste pulado; no Windows, 1 pulado (LibreOffice).

## Princípios que não podem regredir

- **Na dúvida, censurar.** Um falso negativo (CPF visível) é muito pior que um falso positivo. Toda regra nova de exclusão precisa de teste mostrando que não esconde CPF real, e números de auditoria (valores em reais, boletos, processos) não podem ser censurados. Siga os testes parametrizados de `tests/test_detectors.py`.
- **A saída do PDF é sempre uma imagem estática da página já censurada.** O que não é desenhado não vaza; o que é desenhado por cima (campos, anotações) precisa ser incorporado antes, com `flatten_annotations`.
- **Relatórios, erros e console nunca contêm valores encontrados, texto extraído ou nomes de arquivos de entrada.**
- **Testes e exemplos usam só dados fictícios.** Nunca processar ou versionar documentos reais; o `.gitignore` bloqueia PDFs, imagens e documentos soltos.

## Convenções

- Código, comentários, docstrings, mensagens e documentação em português, no estilo compacto já existente. Mensagens de commit em inglês, no formato `tipo: resumo`.
- Finais de linha LF em todos os arquivos (`.gitattributes`). Confira depois de editar no Windows.
- Nenhum caractere invisível ou tipográfico literal no código: escreva `\u00a0`, `\u2013` etc. como escape em strings raw de regex ou normais. Ao gerar esses escapes, confira o arquivo: já houve conversão acidental em caracteres literais.
- Testes que gravam texto devem usar `write_bytes`/`read_bytes`; no Windows, `write_text` converte `\n` em `\r\n` e desloca as posições.
- Para saída UTF-8 de scripts avulsos, use `python -X utf8`. Com `-I`, a variável `PYTHONIOENCODING` é ignorada.
- As fontes padrão do PDF (base-14) gravam o travessão como ponto médio (U+00B7). Para testar um caractere específico num PDF, confira o texto extraído.
- Mudanças de comportamento entram na seção "Não publicado" do `CHANGELOG.md`.

## Fluxo de trabalho

1. Branch a partir da `main` atualizada; commits com a linha `Co-Authored-By` indicada pelo Claude Code.
2. Push e PR com `gh pr create`. Se o `gh` não estiver no PATH: `export PATH="$PATH:/c/Program Files/GitHub CLI"`.
3. Conferir o CI pelo log (`gh run view <id> --log`), incluindo a contagem de testes e a versão do Python de cada job.
4. **O merge é feito pelo usuário no GitHub**, com "Squash and merge"; o modo automático bloqueia merges pelo Claude. Depois, atualizar a `main` local e apagar a branch.
5. Release, só com OK explícito do usuário:
   - a versão vai para `pyproject.toml`, `src/tarja/__init__.py`, o README e o CHANGELOG, seguida de `uv lock`;
   - registro em `docs/validacao.md`;
   - tag anotada `vX.Y.Z` e `gh release create` com o wheel e o sdist de `uv build`.

## Fora do Git

- `archive/`: versões antigas, só local.
- `.runtime/tessdata/`: modelos de OCR.
- `data/`: entradas e saídas locais.
- `.cache/`, `.venv/`, `dist/`: gerados.

## Pendência conhecida

A sensibilidade em documentos reais nunca foi medida. Isso exige uma amostra realista, com as ocorrências marcadas pelo usuário; [docs/portfolio.md](docs/portfolio.md) descreve como medir.
