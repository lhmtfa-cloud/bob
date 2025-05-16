pBase = """
Leia todo o prompt antes de começar. Sua tarefa é analisar um documento PDF (geralmente com 10 páginas ou menos) e me retornar as informações extraídas em um formato estruturado. A análise deve ser feita página por página, com foco em precisão. Ignore cabeçalhos, rodapés e elementos decorativos.
Certifiquesse de não adicionar páginas que não existem.
Formato obrigatório da resposta:

{
Tipo do documento: [ex: Compra]
Remetente: [nome ou entidade]
Data do envio: [data]
Destinatário: [nome ou entidade]
}
{
página: [número da página]
resumo da página: [texto resumido do conteudo da página]
quem assinou: [nomes ou “ninguém”]
leis: [leis citadas ou “nenhuma”]
órgãos envolvidos: [nomes de órgãos públicos ou entidades]
data: [datas mencionadas]
cálculo: [valores mencionados, exemplo: “gasto previsto de R$10.000,00”]
}

> Repita esse segundo bloco para *todas* as páginas, mesmo que a página não contenha dados relevantes. Se algum campo estiver ausente, preencha com “nenhum” ou “em branco”.

> O campo “Tipo do documento” deve ser inferido com base na combinação entre a “Palavra-chave” e “Detalhamento” da primeira página do PDF. Se não encontrar essa informação, deixe em branco.

> O campo “Cálculo” deve ser preenchido quando houver menções a valores, preços, gastos, orçamentos, etc. Exemplo: “O custo total será de R$15.000,00”.

> Seja meticuloso. Priorize exatidão acima de velocidade.

Exemplo esperado:

{
Tipo do documento: Compra
Remetente: João
Data do envio: 28/02/2004
Destinatário: Julia
}
{
página: 1
quem assinou: ninguém
leis: nenhuma
órgãos envolvidos: Picaimba, Governo do Estado, UEL.
resumo da página: Essa página descreve os requisitos para a aprovação da lei.
data: xx/xx/xxxx, yy/yy/yyyy
cálculo: Compra de 10 kg de mostarda.
}
{
página: 2
quem assinou: ...
leis: ...
órgãos envolvidos: ...
resumo da página: Essa página continua descrevevendo os requisitos para a aprovação da lei.
data: ...
cálculo: ...
}
...
{
página: 10
quem assinou: ...
leis: ...
órgãos envolvidos: ...
resumo da página: Essa página descreve Os beneficios da compra de algodão na pitaibia do sul
data: ...
cálculo: ...
}

>faça para *TODAS* as 10 páginas 
>verifique se você não adicionou páginas que não existem.
>verifique se você adicionou informações nas páginas erradas.
"""
