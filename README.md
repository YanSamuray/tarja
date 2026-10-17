# Tarja

**Censura local de identificadores pessoais em documentos.**

O Tarja nasceu para reduzir o trabalho manual de ocultação de documentos pessoais realizado por auditores fiscais e consultores. Busca os identificadores selecionados, aplica a censura e gera um relatório para revisão, preservando o arquivo original.

Versão atual: **0.3.0**. Requer **Python >=3.14** e utiliza **uv** para ambiente, dependências e execução. A versão testada localmente é Python 3.14.2. O nome da distribuição Python é `tarja-documentos`; o comando e o pacote são `tarja`.

## Começar

Instale o [uv](https://docs.astral.sh/uv/getting-started/installation/), clone o projeto e prepare o ambiente:

```powershell
git clone https://github.com/YanSamuray/tarja.git
cd tarja
uv python install 3.14
uv sync --locked
uv run tarja --help
uv run tarja --formats
```

O arquivo `.python-version` seleciona a série 3.14. O `pyproject.toml` estabelece o mínimo >=3.14, e `uv.lock` registra as versões resolvidas das dependências. Não é necessário ativar o ambiente virtual manualmente. Para instalar somente as dependências de execução, use `uv sync --locked --no-dev`.

## Escolher os documentos pessoais

**Por padrão, somente CPF é habilitado.** As flags acrescentam outras categorias:

```powershell
# Somente CPF
uv run tarja entrada.pdf saida.pdf

# CPF + RG + CNH
uv run tarja entrada.pdf saida.pdf --rg --cnh

# CPF + título de eleitor
uv run tarja entrada.pdf saida.pdf --titulo-eleitor

# Todas as quatro categorias
uv run tarja entrada.pdf saida.pdf --todos

# Seleção exata, sem CPF implícito
uv run tarja entrada.pdf saida.pdf --entities RG CNH

# CPF completo, em vez de parcial
uv run tarja entrada.pdf saida.pdf --cpf-mode full
```

`--cpf` explicita o padrão. `--all` é um alias de `--todos`. Não combine `--entities` com essas flags.

| Identificador | Regra |
| --- | --- |
| CPF | 11 dígitos, com ou sem separadores, inclusive travessões, espaços inseparáveis e uma quebra de linha; após rótulo de CPF, também 9 ou 10 dígitos (zeros à esquerda perdidos em planilhas); máscara parcial dos primeiros 3 e últimos 2 dígitos, ou completa |
| RG | Censura completa; exige rótulo como `RG`, `R.G.`, `registro geral` ou `identidade`; aceita prefixo de UF (`MG-`); cobertura limitada dos formatos estaduais |
| CNH | Censura completa de 11 dígitos precedidos de `CNH`, `carteira nacional de habilitação` ou `carteira de motorista` |
| Título de eleitor | Censura completa de 12 dígitos precedidos de `título de eleitor`, `título eleitoral` ou `inscrição eleitoral` |

Na dúvida, o número é censurado. CPFs com dígitos verificadores inválidos também são censurados e sinalizados, pois podem resultar de erro de digitação ou OCR. Um valor com formato de CPF é tratado como CPF mesmo sob os rótulos `CPF/CNPJ`, `RG` (a Carteira de Identidade Nacional usa o CPF como número) ou `CNH`, quando formatado. CPFs fora do padrão de 11 dígitos, como os com zeros perdidos ou letras trocadas pelo OCR (`O` por `0`), recebem censura completa mesmo na política parcial. Em rótulos combinados, como `CPF e RG: X e Y`, cada valor segue o rótulo na mesma posição; se a ordem divergir, o formato do número decide.

CNPJ, valores monetários (`123.456.789,00`) e linhas de boleto não são censurados. Após rótulos de telefone, celular, matrícula, conta (`c/c`) ou `R$`, um número com formato de CPF só fica sem censura quando o DV é inválido, e mesmo assim entra no relatório como ponto para conferência. Nomes, endereços, telefones, e-mails, rostos, assinaturas e códigos QR não são detectados nesta versão.

## Formatos de entrada e saída

| Entrada | Saída | Dependências e limites |
| --- | --- | --- |
| PDF | PDF estático | OCR quando a página contém conteúdo visual |
| PNG, JPG/JPEG, TIFF/TIF, BMP, WEBP | PDF estático | OCR obrigatório; inclui páginas/quadros múltiplos, como TIFF |
| TXT | TXT UTF-8 | Substituição dos valores no texto |
| Markdown (`.md`) | Markdown UTF-8 | Somente o texto do arquivo; imagens, anexos e conteúdos de links não são processados |
| DOCX, ODT, RTF | PDF estático | LibreOffice instalado localmente; conversão para PDF antes da censura |

```powershell
uv run tarja texto.txt texto-censurado.txt --todos
uv run tarja notas.md notas-censuradas.md --cnh
uv run tarja imagem.png imagem-censurada.pdf --todos --tessdata .runtime/tessdata
uv run tarja documento.docx documento-censurado.pdf --rg --cnh
```

Não há exportação para DOCX editável, censura de planilhas ou apresentações nesta versão. A integração real com LibreOffice é executada no CI em Linux; no Windows local ela não foi executada. Consulte as [evidências de validação](docs/validacao.md).

## Processar pastas

Crie `data/input` e coloque os arquivos de entrada nessa pasta. A pasta de saída é criada pelo programa.

```powershell
uv run tarja data/input data/output --todos
uv run tarja data/input data/output --rg --cnh --recursive --tessdata .runtime/tessdata
```

Sem argumentos, usa `data/input` e `data/output` relativos à raiz de execução. A pasta de saída deve ficar fora da entrada. O modo recursivo preserva as subpastas, e uma falha de arquivo não interrompe os demais.

Arquivos convertidos mantêm a extensão original no nome: `relatorio.docx` vira `relatorio.docx.pdf`, e `relatorio.png` vira `relatorio.png.pdf`. Assim não colidem com um `relatorio.pdf` da mesma pasta. PDF, TXT e MD preservam o nome. Resultados existentes nunca são sobrescritos.

## OCR local

Baixe os modelos `por.traineddata` e `eng.traineddata` do [repositório oficial do Tesseract](https://github.com/tesseract-ocr/tessdata_fast/tree/4.1.0) para `.runtime/tessdata/`, ou use outra pasta local:

```powershell
uv run tarja entrada.pdf saida.pdf --tessdata .runtime/tessdata --todos
```

- `--ocr auto`: usa OCR em páginas com imagens, mesmo com texto digital; em páginas sem texto com desenhos; em páginas com texto convertido em curvas; e em páginas com fontes sem mapeamento Unicode, cujo texto extraído não corresponde ao exibido.
- `--ocr always`: força OCR em todas as páginas, útil para camadas de texto defeituosas que escapem a esses critérios.
- `--ocr never`: recusa imagens e PDFs que exijam OCR; não os exporta silenciosamente sem inspeção.
- `--language por+eng`: idiomas dos modelos disponíveis.
- `--dpi 300`: resolução de OCR/exportação, de 150 a 600 DPI.

Em páginas submetidas a OCR, **CPF recebe censura completa**, inclusive quando a política é parcial, pois as caixas dos dígitos reconhecidos são aproximadas. Isso é registrado no relatório. A extração nativa também é considerada, e ocorrências sobrepostas são deduplicadas na contagem. Os modelos não são baixados automaticamente.

## LibreOffice opcional

Para DOCX, ODT e RTF, instale [LibreOffice](https://www.libreoffice.org/download/download-libreoffice/). O Tarja procura o executável no PATH e em locais usuais de Windows/macOS. Também aceita caminho explícito:

```powershell
uv run tarja entrada.docx saida.pdf --todos --libreoffice "C:\Program Files\LibreOffice\program\soffice.com"
```

A conversão ocorre sem interface gráfica, em um perfil temporário separado, com prazo de 120 segundos. Os intermediários são apagados ao concluir ou falhar. Revise a diagramação: a conversão pode alterar fontes, quebras de página e outros detalhes. PDF convertido com imagens poderá exigir os modelos de OCR.

## O que é removido

PDFs são reconstruídos a partir das imagens das páginas **já censuradas**. A tarja não é uma anotação removível que revele o texto original. A saída não leva texto oculto, metadados originais, anexos ou revisões do PDF. Essa escolha perde pesquisa, seleção de texto, acessibilidade semântica e assinaturas digitais, e pode aumentar o tamanho do arquivo.

TXT e MD têm os caracteres dos valores selecionados substituídos por `*`, sem armazenar o texto anterior no resultado. A saída é UTF-8 sem BOM, preservando as quebras de linha existentes. Mídias referenciadas por Markdown continuam fora do escopo.

**Todo resultado exige revisão humana.** A remoção das ocorrências encontradas não prova que todas as informações pessoais foram detectadas. CPF parcialmente censurado não torna o documento anônimo. Limites: 100 MB por entrada, até 300 páginas/quadros; PDFs criptografados, com formulários ou anotações requerem preparação manual.

## Relatórios

Cada execução grava `report-<id>.json` na saída. Inclui versão do esquema (atualmente 3), política, hashes de entrada/saída, formato, duração, contagens, regiões, pontos para conferência e avisos. Não contém os valores encontrados, texto extraído nem nomes dos arquivos de entrada. A numeração segue a ordem do lote, e o hash permite identificar o original.

Os pontos para conferência (`candidates`) indicam números suspeitos que **não** foram censurados, para orientar a revisão:

- `excluded_label`: formato de CPF após rótulo de telefone, matrícula ou similar, com DV inválido;
- `entity_disabled`: número com formato de CPF classificado como uma categoria não selecionada, como a CNH;
- `unrecognized_value`: rótulo seguido de um valor não reconhecido, como um CPF com dígitos a mais ou ilegível no OCR.

Cada ponto traz somente a categoria, o motivo e a posição. O console informa quantos pontos há em cada arquivo.

PDFs usam coordenadas por página. TXT/MD usam uma unidade lógica de texto e intervalos de caracteres, contados após a remoção do BOM. Os status são `requires_review` ou `failed`; não existe aprovação automática para compartilhamento.

Avisos estão descritos em [formatos e arquitetura](docs/arquitetura.md). Códigos de saída: `0` processamento concluído; `1` pelo menos um arquivo falhou; `2` configuração/entrada inválida ou falha de acesso/relatório.

## Desenvolvimento

```powershell
uv sync --locked
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv build
uv run python scripts/check_distribution.py
```

Para testar OCR real no PowerShell:

```powershell
$env:TEST_TESSDATA = (Resolve-Path '.runtime/tessdata').Path
uv run pytest
```

Em Bash: `TEST_TESSDATA="$PWD/.runtime/tessdata" uv run pytest`. A integração real Office usa LibreOffice detectado automaticamente ou a variável `TEST_LIBREOFFICE`. Testes dependentes de ferramentas ausentes são explicitamente pulados.

Demonstração sintética, com todas as categorias habilitadas:

```powershell
uv run python examples/create_demo.py output/demo
```

## Estrutura

```text
src/tarja/            Pacote instalado e núcleo de censura
src/tarja/formats/    Adaptadores de imagens, texto e LibreOffice
tests/               Testes do projeto ativo
docs/                Arquitetura, validação e estudo de caso
examples/            Demonstração com dados fictícios
scripts/             Verificação dos artefatos de distribuição
archive/             Histórico preservado apenas localmente, fora do Git
data/                Entradas e saídas locais, fora do versionamento
.github/workflows/   CI para Python 3.14 em Windows e Linux
.python-version      Série Python usada pelo uv
pyproject.toml       Metadados e dependências
uv.lock              Versões resolvidas
```

`archive/` não é publicado e não participa dos testes, da análise de código ou da distribuição Python. `.venv/`, `.cache/`, `.runtime/` e `output/` são diretórios locais gerados, também fora do versionamento. O `.gitignore` também bloqueia documentos e imagens soltos; os exemplos públicos são gerados por código com conteúdo fictício. O layout `src/` permite testar o pacote instalado e evita misturá-lo com o histórico.

Leia o [histórico da reorganização](docs/historico.md), as [decisões técnicas atuais](docs/arquitetura.md) e o [estudo de caso para portfólio](docs/portfolio.md). O impacto em HH é relatado pelo autor; não há números medidos publicados. Autor: Yan Samuray.

## Licença

Copyright (c) 2026 Yan Samuray. Distribuído sob a [GNU Affero General Public License v3.0](LICENSE), identificador SPDX `AGPL-3.0-only`. As dependências mantêm suas próprias licenças. O PyMuPDF é disponibilizado sob AGPL ou licença comercial, conforme a [documentação oficial](https://pymupdf.readthedocs.io/en/latest/about.html#license-and-copyright).
