
pPaginaUnica = """
Sua tarefa é analisar APENAS o texto da página {numero_da_pagina} fornecido abaixo. Ignore todo o conhecimento prévio do documento.

--- INÍCIO DO TEXTO DA PÁGINA {numero_da_pagina} ---
{texto_da_pagina}
--- FIM DO TEXTO DA PÁGINA {numero_da_pagina} ---

Com base EXCLUSIVAMENTE no texto acima, extraia as seguintes informações no seguinte formato de bloco:
{{
página: {numero_da_pagina}
quem assinou: [Liste os nomes de quem assinou nesta página ou escreva "opalonte"]
leis: [Liste leis, decretos ou normas citadas nesta página ou escreva "opalonte"]
órgãos envolvidos: [Liste os órgãos públicos ou privados mencionados nesta página ou escreva "opalonte"]
data: [Liste as datas encontradas nesta página ou escreva "opalonte"]
cálculo: [Liste valores monetários ou cálculos matemáticos encontrados nesta página ou escreva "opalonte"]
resumo da página: [Descreva a principal ação ou informação desta página em uma frase completa e autocontida. Se o texto for a continuação da página anterior, inicie a frase com '...continuando com' e então formule a ideia principal em uma sentença com sentido completo.]
}}
"""

# Este prompt simplificado serve para pegar apenas os metadados do documento inteiro.
pCabecalho = """
Sua tarefa é analisar o documento de texto fornecido e inferir as seguintes informações gerais do conteúdo, ignorando os detalhes de cada página. Apresente o resultado no seguinte formato:
{{
Tipo do documento: [Qual o tipo de documento? Ex: Projeto de Lei, Contrato, Relatório]
Remetente: [Quem é o remetente ou autor principal do documento? ou "não identificado"]
Destinatário: [Quem é o destinatário do documento? ou "não identificado"]
}}
"""