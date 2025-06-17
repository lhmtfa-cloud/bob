pergunta1 = (
    "Gere uma tabela em formato Markdown com os dados extraídos do documento até a seção de cálculo. "
    "A estrutura da tabela deve ser rigorosamente delimitada por barras verticais (|), com:\n"
    "- A primeira linha contendo os cabeçalhos: 'item', 'detalhes'.\n"
    "- A segunda linha contendo os separadores: |---|---| (um por coluna).\n"
    "- Na coluna 'item' deve conter: 'tipo do documento', 'Leis', 'Assinaturas', 'Órgãos envolvidos', 'Datas', 'Cálculo'\n\n"
    "Restrições obrigatórias:\n"
    "- A tabela será processada por regex, então a estrutura com | no início, entre colunas e no fim deve ser mantida estritamente.\n"
    "- Nenhum conteúdo explicativo antes ou depois da tabela.\n"
    "- Cada item deve estar contido em uma única linha da tabela.\n\n"
    "Itens obrigatórios no conteúdo:\n"
    "- Tipo do documento (somente o primeiro encontrado nas primeiras páginas)\n"
    "- Todas as leis, normas e decretos citados, com as páginas\n"
    "- Nome de todas as pessoas que assinaram, com as páginas\n"
    "- Todos os órgãos citados, com as páginas\n"
    "- Todas as datas citadas\n"
    "- Todos os cálculos, fórmulas ou menções a cálculos, com as páginas\n"
    "Certifique-se de que todos os campos estejam devidamente preenchidos, sem omissões."
)


corrigir1 = (
    "Junte as tabelas anteriores em uma só, no formato Markdown, até a seção de cálculo. "
    "Siga exatamente esta estrutura:\n"
    "- Cabeçalhos: 'item', 'detalhes'\n"
    "- Separadores: |---|---|\n"
    "- Itens: 'tipo do documento', 'Leis', 'Assinaturas', 'Órgãos envolvidos', 'Datas', 'Cálculo'\n\n"
    "Regras obrigatórias:\n"
    "- A estrutura com barras verticais deve ser mantida perfeitamente para processamento por regex.\n"
    "- Nenhum conteúdo antes ou depois da tabela.\n"
    "- Cada item deve estar em uma única linha, sem quebras internas.\n\n"
    "Incluir:\n"
    "- Apenas o primeiro tipo de documento identificado\n"
    "- Todas as leis e decretos com as páginas\n"
    "- Todos os nomes e páginas das assinaturas\n"
    "- Todos os órgãos mencionados\n"
    "- Todas as datas\n"
    "- Todos os cálculos e menções de fórmulas com páginas\n"
    "Nada pode ser deixado de fora."
)

pergunta2 = (
    "Gere uma tabela em formato Markdown com os resumos cronológicos de todas as páginas do documento. "
    "A estrutura da tabela deve ser rigorosamente delimitada por barras verticais (|), com:\n"
    "- A primeira linha com os cabeçalhos: 'item', 'detalhes'\n"
    "- A segunda linha com os separadores: |---|---|\n"
    "- A coluna 'item' deve conter 'Resumo'\n\n"
    "Instruções:\n"
    "- Agrupe os resumos por ordem crescente de página\n"
    "- Comece sempre pela página 1\n"
    "- Mantenha cada resumo em linha única, sem quebras internas\n"
    "- Inclua indicação das páginas cobertas no campo de detalhes\n"
    "Nada de explicações ou textos fora da tabela."
)


corrigir2 = (
    "Junte os resumos em uma única tabela Markdown com cabeçalhos 'item' e 'detalhes', separados por barras verticais. "
    "A tabela deve conter apenas uma linha com 'Resumo', e a descrição cronológica completa no campo 'detalhes'.\n\n"
    "Instruções obrigatórias:\n"
    "- Siga rigorosamente o padrão com barras: |item|detalhes|\n"
    "- Nenhum conteúdo fora da tabela\n"
    "- Todos os resumos devem estar concatenados por ordem de página\n"
    "- Incluir as páginas às quais os resumos pertencem\n"
    "- O campo 'detalhes' deve conter o resumo contínuo de todas as páginas\n"
    "Certifique-se de não omitir nenhuma página."
)

