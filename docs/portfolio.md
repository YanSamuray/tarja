# Tarja: automação de censura documental

## Apresentação curta

Desenvolvi o Tarja, uma ferramenta em Python para automatizar a ocultação de identificadores pessoais em documentos. O projeto nasceu de uma necessidade operacional: auditores fiscais e consultores realizavam essa tarefa manualmente em PDFs, consumindo tempo especializado. Segundo a experiência relatada pelo autor, a automação reduziu de forma relevante esse trabalho. Na reconstrução, separei as regras de detecção da manipulação de PDF, corrigi a localização das ocorrências, introduzi OCR por página e testes de regressão, e acrescentei um relatório para apoiar a revisão humana. A versão 0.3 adotou o uv, a seleção de categorias por flags e a entrada de imagens, texto e documentos Office via LibreOffice. A 0.4 fechou lacunas de detecção encontradas em revisão técnica, passou a apontar no relatório os números suspeitos que não foram censurados e ampliou a compatibilidade para Python 3.11 ou superior.

## Problema e contribuição

**Problema:** preparar documentos para compartilhamento exigia localizar identificadores pessoais e ocultá-los sem alterar trechos necessários à leitura. O processo manual tinha custo de tempo e estava sujeito a omissões.

**Contribuição técnica:** detecção por padrões e contexto, mapeamento de caracteres para coordenadas, OCR local, geração de cópia estática e processamento em lote com isolamento de erros. Os testes verificam também o que deve ser preservado, como números sem relação com um CPF.

**Decisão de engenharia:** escolher as ferramentas pelo papel no fluxo. Bibliotecas de conversão documental não substituem, por si só, a remoção do conteúdo do PDF. O reconhecimento precisa de regras específicas e de avaliação no conjunto de documentos do usuário.

**Impacto observado:** redução do trabalho manual de profissionais especializados, conforme relato do autor. Não foram fornecidos dados suficientes para publicar número de horas economizadas, percentual de ganho, economia financeira ou precisão.

## Como medir o impacto

Comparar amostras equivalentes por número de páginas, quantidade de identificadores e qualidade da digitalização. Cronometrar o fluxo completo: preparação, execução, revisão e correções. Separar o tempo de máquina do tempo de trabalho humano; quando há sobreposição, não somar os dois indiscriminadamente.

`HH poupadas = (minutos de trabalho humano no fluxo manual - minutos de trabalho humano no fluxo assistido) / 60`

Para estimar um período, multiplicar a diferença média pelo volume de documentos comparáveis, informando o tamanho da amostra e a variação. Só calcular economia financeira quando existir um custo-hora informado e autorizado para divulgação.

Avaliar também:

- Ocorrências pessoais deixadas visíveis, por tipo de identificador.
- Trechos censurados indevidamente.
- Tempo humano de revisão e correção.
- Diferenças entre PDFs digitais, digitalizados e mistos.
- Arquivos que exigiram tratamento manual ou não puderam ser processados.

## Evidências para publicar

A demonstração reproduzível em `examples/create_demo.py` usa somente conteúdo fictício. Apresentar antes/depois, arquitetura, decisões, testes e limites conhecidos. Usar apenas nomes de instituições, processos e materiais cuja divulgação tenha sido autorizada. Não atribuir endosso institucional ao uso relatado.

O diferencial demonstrável é ter identificado uma tarefa recorrente de alto custo de tempo, entregue utilidade operacional e depois reconstruído a solução com critérios verificáveis. A versão atual é uma base funcional para validação; o estudo de caso não deve apresentá-la como certificação de conformidade ou garantia de anonimização completa.
