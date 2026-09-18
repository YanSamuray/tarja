# Histórico do Tarja

O projeto começou como scripts para censura de CPF em PDFs. Uma segunda tentativa acrescentou outros identificadores pessoais, como RG, CNH e título de eleitor. Essas versões resolveram uma necessidade real, mas ficaram com regras e estruturas diferentes.

A reconstrução 0.2 separou detecção, extração e remoção, corrigiu a busca global de fragmentos numéricos e o tratamento de PDFs mistos, e introduziu relatórios e testes sintéticos. A versão 0.3 adotou o nome Tarja, Python 3.14, uv, layout `src/`, seleção de categorias e adaptadores para outros formatos.

As versões anteriores foram preservadas localmente em `archive/`. O repositório público contém somente a versão ativa, sua documentação, testes e geradores de exemplos fictícios. Os arquivos históricos, documentos de entrada, resultados, modelos de OCR e ambientes virtuais não são publicados.

Consulte [CHANGELOG.md](../CHANGELOG.md) para as alterações da versão atual e [arquitetura.md](arquitetura.md) para as decisões técnicas.
