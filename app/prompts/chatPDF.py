pBase = """
Leia todo o prompt antes de começar. Você vai analisar um documento PDF onde cada seção foi **manualmente marcada** com "### Página X", indicando o conteúdo **equivalente à página X do documento original**.

Sua tarefa é ler **cada bloco identificado por "### Página X"** e retornar as informações extraídas em um formato estruturado.

Regras obrigatórias:

- Leia **apenas o conteúdo entre cada `### Página X`** e o próximo marcador `### Página Y` ou o fim do documento.
- Nunca antecipe, misture ou complete com informações de outros blocos.
- Não use informações de blocos futuros nem tente inferir o que não está claramente visível.
- Mesmo que um bloco pareça irrelevante, ele deve ser analisado.

Página com assinatura = **somente se o conteúdo for exclusivamente uma assinatura isolada** (sem tabelas, textos, listas etc). Se houver qualquer outra informação, resuma normalmente.

Formato obrigatório da resposta:

{
Tipo do documento: [ex: Compra]
Remetente: [nome ou entidade]
Data do envio: [data]
Destinatário: [nome ou entidade]
}
{
página: [número da página]
quem assinou: [nomes ou “ninguém”]
leis: [leis, decretos, normas citadas ou “nenhuma”]
órgãos envolvidos: [nomes de órgãos públicos ou entidades]
data: [datas mencionadas]
cálculo: [valores mencionados, exemplo: “gasto previsto de R$10.000,00”, "valor médio de 26,30 reais"]
resumo da página: [resuma com clareza o conteúdo textual do bloco identificado como Página X. Se contiver apenas uma assinatura isolada, escreva: “Página com assinatura”]
}

> Repita esse segundo bloco para *todas* as páginas (blocos), mesmo que não tenham conteúdo relevante. Preencha campos ausentes com “nenhum” ou “em branco”.

> O campo “Tipo do documento” deve ser inferido com base na combinação entre a “Palavra-chave” e “Detalhamento” da **primeira página (bloco 1)**. Se não encontrar essa informação, deixe em branco.

> O campo “Cálculo” deve ser preenchido quando houver qualquer menção a valores, preços, gastos, orçamentos etc.

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
órgãos envolvidos: Picaimba
data: xx/xx/xxxx
cálculo: nenhum
resumo da página: coisas aconteceram
}
{
página: 2
quem assinou: ...
leis: ...
órgãos envolvidos: ...
data: ...
cálculo: ...
resumo da página: ...
}
...
{
página: 10
quem assinou: ...
leis: ...
órgãos envolvidos: ...
data: ...
cálculo: ...
resumo da página: ...
}

IMPORTANTE:
- O conteúdo analisado deve vir exclusivamente de cada bloco `### Página X`.
- Nunca misture blocos ou use informações de fora do trecho marcado.
- Responda como se cada bloco fosse uma página real.
"""
