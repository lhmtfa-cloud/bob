pBase = """
Leia todas as instruções cuidadosamente antes de começar. Este é um documento PDF com até 10 páginas. Sua tarefa é analisar página por página e retornar as informações extraídas em formato estruturado, conforme modelo abaixo.

> IMPORTANTE:
- Leia TODAS as páginas, sem pular nenhuma.
- Só escreva "imagem ilegível" quando realmente não for possível extrair **nenhum texto** da página.
- NÃO diga "nada relevante". Se houver texto, extraia um resumo.
- NÃO misture informações entre páginas. Verifique se cada dado está no lugar certo.
- Respeite fielmente a numeração da página no PDF.
- O foco é PRECISÃO, não velocidade.

---

> MODELO OBRIGATÓRIO:

{
Tipo do documento: [Ex: Compra, Contrato, Ofício, etc. Inferir a partir da 1ª página. Se não for possível, deixe em branco.]
Remetente: [nome ou entidade que envia]
Data do envio: [data mencionada no início ou assinatura]
Destinatário: [nome ou entidade que recebe]
}

{
página: [número]
resumo da página: [resuma com suas próprias palavras o conteúdo da página]
quem assinou: [nomes de quem assinou ou “ninguém”]
leis: [leis citadas ou “nenhuma”]
órgãos envolvidos: [nomes de órgãos públicos ou entidades mencionadas, ou “nenhum”]
data: [todas as datas mencionadas na página, ou “nenhuma”]
cálculo: [valores, preços, orçamentos ou “nenhum”]
}

> Repita esse segundo bloco para CADA página (1 a 10), mesmo que seja imagem ou contenha pouco conteúdo.

> Use “imagem ilegível” apenas se a IA não conseguir ler nada da página.

> O campo “cálculo” deve incluir qualquer menção a valores monetários, quantidades, índices, projeções, etc.

> É de extrema importância que *TODAS* as leis sejam anotadas

> O campo “Tipo do documento” deve ser baseado em palavras como “Contrato”, “Requisição”, “Ofício”, “Ata”, “Nota Técnica”, “Relatório”, etc., preferencialmente da primeira página.

---

> Exemplo prático de resposta:

{
Tipo do documento: Compra Direta  
Remetente: UEL 
Data do envio: 14/12/2046  
Destinatário: nenhum  
}

{
página: 1  
resumo da página: Documento que autoriza compra direta de algodão.  
quem assinou: João, Caroline 
leis: nenhuma  
órgãos envolvidos: UEL  
data: 14/03/2025  
cálculo: aquisição de 20 pacotes de algodão 
}

[repita esse bloco até a página 10]


"""
