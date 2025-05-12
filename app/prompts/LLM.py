pergunta = (
    "Gere uma tabela em formato Markdown com os dados extraídos do resumo do documento. "
    "A estrutura da tabela deve ser rigorosamente delimitada por barras verticais (|), com:\n"
    "- A primeira linha contendo os cabeçalhos: 'item', 'detalhes'.\n"
    "- A segunda linha contendo os separadores: |---|---|---| (um por coluna).\n"
    "- Cada linha subsequente deve conter os dados correspondentes de forma linear, sem quebras de linha internas nas células.\n\n"
    
    "Restrições obrigatórias:\n"
    "- Não insira '<br>', '\\n' ou qualquer outro tipo de quebra de linha.\n"
    "- A tabela será processada por regex, então a estrutura com | no início, entre colunas e no fim deve ser mantida estritamente.\n"
    "- Nenhum conteúdo explicativo antes ou depois da tabela.\n"
    "- Cada item deve estar contido em uma única linha da tabela.\n\n"
    
    "Itens obrigatórios no conteúdo:\n"
    "- Tipo do documento\n"
    "- Todas as leis, normas e decretos citados\n"
    "- Nome de todas as pessoas que assinaram o documento\n"
    "- Todas as justificativas presentes no texto\n\n"
    
    "Certifique-se de que todos os campos estejam devidamente preenchidos, e que não haja omissões nos dados críticos."
)