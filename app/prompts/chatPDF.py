pBase = """
Sua tarefa é analisar o documento de texto fornecido e estruturar sua resposta em dois tipos de blocos: um bloco de cabeçalho e múltiplos blocos de página.

**1. Bloco de Cabeçalho (Obrigatório, sempre no início):**
Sua resposta DEVE SEMPRE começar com um bloco de cabeçalho, inferindo as seguintes informações do conteúdo:
{
Tipo do documento: [Tipo de documento, ex: Projeto de Lei]
Remetente: [Nome ou entidade remetente]
Data do envio: [A data mais proeminente, se houver]
Destinatário: [Nome ou entidade destinatária]
}

**2. Blocos de Página (Repetir para cada página):**
Após o cabeçalho, para cada marcador "### Página X" que você encontrar, gere um bloco de dados de página.
**REGRA CRÍTICA:** Para o campo "página", você pode tentar usar o número do marcador, mas foque em analisar o conteúdo.

O formato para cada bloco de página é:
{
página: [Número da página que você está analisando]
quem assinou: [nomes ou "ninguém"]
leis: [leis, decretos, normas ou "nenhuma"]
órgãos envolvidos: [órgãos ou "nenhum"]
data: [datas ou "nenhuma"]
cálculo: [valores ou "nenhum"]
resumo da página: [resumo do conteúdo da página]
}

Sua resposta final deve ser o bloco de cabeçalho único seguido por uma lista contínua dos blocos de página.
"""