pergunta = (
    "Gere uma tabela em formato Markdown com os dados extraídos do resumo do documento. "
    "A estrutura da tabela deve ser rigorosamente delimitada por barras verticais (|), com:\n"
    "- A primeira linha contendo os cabeçalhos: 'item', 'detalhes'.\n"
    "- A segunda linha contendo os separadores: |---|---|---| (um por coluna).\n"
    "- Na coluna 'item' deve ter 'tipo do documento', 'Leis', 'Assinaturas' e 'Resumo'\n"
    "- A segunda linha contendo os separadores: |---|---|---| (um por coluna).\n"
    "- Cada linha subsequente deve conter os dados correspondentes de forma linear, sem quebras de linha internas nas células.\n\n"
    
    "Restrições obrigatórias:\n"
    "- A tabela será processada por regex, então a estrutura com | no início, entre colunas e no fim deve ser mantida estritamente.\n"
    "- Nenhum conteúdo explicativo antes ou depois da tabela.\n"
    "- Cada item deve estar contido em uma única linha da tabela.\n\n"

    "Itens obrigatórios no conteúdo:\n"
    "- As páginas as quais as informações leis e assinaturas estão.\n"
    "- Tipo do documento\n"
    "- Todas as leis, normas e decretos citados\n"
    "- Nome de todas as pessoas que assinaram o documento\n"
    "- TODAS as leis, normas e decretos citados\n"
    "- As páginas as quais as informações do resumo estão\n"
    "- O resumo em ordem cronológica\n"
    "- As páginas as quais as informações do resumo estão\n\n"
    
    "Certifique-se de que todos os campos estejam devidamente preenchidos, e que não haja omissões nos dados críticos."

    
)


corrigir =(
"corrija a tabela, colocando as informações no formato:\n." \
"Gere uma tabela em formato Markdown com os dados extraídos do resumo do documento. "
    "A estrutura da tabela deve ser rigorosamente delimitada por barras verticais (|), com:\n"
    "- A primeira linha contendo os cabeçalhos: 'item', 'detalhes'.\n"
    "- A segunda linha contendo os separadores: |---|---|---| (um por coluna).\n"
    "- Na coluna 'item' deve ter 'tipo do documento', 'Leis', 'Assinaturas' e 'Resumo'\n"
    "- A segunda linha contendo os separadores: |---|---|---| (um por coluna).\n"
    "- Cada linha subsequente deve conter os dados correspondentes de forma linear, sem quebras de linha internas nas células.\n\n"
    
    "Restrições obrigatórias:\n"
    "- A tabela será processada por regex, então a estrutura com | no início, entre colunas e no fim deve ser mantida estritamente.\n"
    "- Nenhum conteúdo explicativo antes ou depois da tabela.\n"
    "- Cada item deve estar contido em uma única linha da tabela.\n\n"

    "Itens obrigatórios no conteúdo:\n"
    "- As páginas as quais as informações leis e assinaturas estão.\n"
    "- Tipo do documento\n"
    "- Todas as leis, normas e decretos citados\n"
    "- Nome de todas as pessoas que assinaram o documento\n"
    "- TODAS as leis, normas e decretos citados\n"
    "- As páginas as quais as informações do resumo estão\n"
    "- O resumo em ordem cronológica\n"
    "- As páginas as quais as informações do resumo estão\n\n"
    
    "Certifique-se de que todos os campos estejam devidamente preenchidos, e que não haja omissões nos dados críticos."

    

)