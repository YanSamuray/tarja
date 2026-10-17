# Alterações

## 0.4.0 - 2026-10-17

### Corrigido

- CPFs que passavam sem censura: rótulos `CPF/CNPJ`, `CPF e RG`, `RG` com o número do CPF (Carteira de Identidade Nacional) e `CNH` formatada.
- Separadores não reconhecidos no CPF:
  - travessões, hífen inseparável e sinal de menos;
  - ponto médio, espaço inseparável e caracteres invisíveis;
  - vírgula lida pelo OCR e quebra de linha `\r\n`;
  - rótulo colado (`CPF123...`) e ênfase do Markdown (`_123..._`).
- Páginas com texto convertido em curvas ou com fontes sem mapeamento Unicode passam a exigir OCR no modo `auto`; antes, o CPF exibido não era detectado.
- Linhas de boleto deixam de ser censuradas como CPF.
- Listas após rótulos combinados (`CPF e RG: X e Y`, `RG/CPF: X / Y`): cada valor segue o rótulo na mesma posição, e o formato decide quando a ordem diverge. Antes, só o primeiro valor era censurado.
- Custo da detecção linear no número de ocorrências; antes era quadrático (20 mil linhas com identificadores: de 93 s para 2 s).

### Alterado

- Python mínimo 3.11 (antes 3.14), sem mudança nas versões das dependências. O CI testa 3.11 a 3.14 no Linux e 3.11 e 3.14 no Windows; `.python-version` continua em 3.14 para desenvolvimento.
- Páginas sem cor são exportadas em tons de cinza, sem perda: PDFs cerca de 45% menores (10 páginas: de 3,8 MB para 2,1 MB). Páginas com cor continuam em RGB.
- PDFs com campos de formulário ou anotações deixam de ser recusados: esses elementos são incorporados à página antes da censura (aviso `annotations_flattened`). Tarjas marcadas e não aplicadas são aplicadas antes da busca (aviso `existing_redactions_applied`). Formulários XFA continuam recusados.
- Novos rótulos:
  - RG: `R.G.`, `identidade`, prefixo de UF;
  - CNH: `carteira nacional de habilitação`, `carteira de motorista`;
  - título de eleitor: `título eleitoral`, `inscrição eleitoral`.
- Até 30 caracteres entre o rótulo e o valor, sem atravessar outro rótulo.
- CPF rotulado com 9 ou 10 dígitos (zeros à esquerda perdidos) e com letras trocadas pelo OCR é censurado por completo, com o aviso `cpf_irregular_expanded_to_full`.
- Rótulos de telefone, matrícula e semelhantes só evitam a censura quando o DV é inválido.
- Relatório no esquema 3, com `candidates` (pontos para conferência, sem valores) e o aviso `unredacted_candidates_require_review`. O console informa quantos pontos há em cada arquivo.
- CI baixa os modelos de OCR conferidos por SHA-256 e instala o LibreOffice no Linux, executando os testes de integração real.

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
