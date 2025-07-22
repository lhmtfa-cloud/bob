# limpar.py

import re
import os
import glob
import fitz  # PyMuPDF
import logging
import json
import unicodedata

# As funções abaixo permanecem as mesmas
# --- NOVA FUNÇÃO UNIFICADA E SIMPLIFICADA ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def converter_contexto_para_tabela_markdown(contexto_str: str) -> str:
    contexto_str = re.sub(r"}\s*{", "}, {", contexto_str.strip())
    contexto_str = "[" + contexto_str + "]" 

    try:
        blocos = json.loads(contexto_str)
    except Exception as e:
        print("Erro ao decodificar JSON do contexto:", e)
        return ""

    cabecalho = "| Item | Detalhes |\n|--|--|"
    linhas = []

    for bloco in blocos:
        for chave, valor in bloco.items():
            if isinstance(valor, str):
                linhas.append(f"| **{chave}** | {valor} |")

    return "\n".join([cabecalho] + linhas)


def limpar_texto_para_pdf(texto: str) -> str:
    if texto is None: return "" 
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join(c for c in texto if unicodedata.category(c)[0] != 'C') 
    texto = re.sub(r'[^\x00-\x7F\u00C0-\u00FF\u20AC\u2013\u2014]', '?', texto) 
    texto = texto.replace('\u2028', ' ').replace('\u2029', ' ') 
    return texto

def dividir_em_antes_e_depois_do_resumo(texto_completo: str):
    keyword = "resumo da página:" 
    match = re.search(re.escape(keyword), texto_completo, re.IGNORECASE) 

    if match:
        posicao_inicio_keyword = match.start()
        antes = texto_completo[:posicao_inicio_keyword].strip()
        depois = texto_completo[posicao_inicio_keyword:].strip() 
        return antes, depois
    else:
        return texto_completo.strip(), "" 
    

def padronizar_indicadores_de_pagina(conteudo_do_texto: str) -> str:
    if not isinstance(conteudo_do_texto, str):
        return ""

    padrao = re.compile(r'(P[áa]gina\s+\d+):', re.IGNORECASE)

    substituicao = r'(\1)'

    texto = padrao.sub(substituicao, conteudo_do_texto)

    delimitador = "```"
    primeira_ocorrencia_idx = texto.find(delimitador)
    inicio_do_texto = texto[:primeira_ocorrencia_idx + len(delimitador)]
    resto_do_texto = texto[primeira_ocorrencia_idx + len(delimitador):]
    resto_sem_delimitadores = resto_do_texto.replace(delimitador, "")
    texto_final = inicio_do_texto + resto_sem_delimitadores

    return texto_final


def extrair_valor_tabela(texto: str, campo: str) -> str:
    padrao = re.compile(rf"\|\s*{re.escape(campo)}\s*\|\s*(.*?)\s*\|", re.IGNORECASE)
    match = padrao.search(texto)
    if match:
        return match.group(1).strip()
    return "--"

import re
import fitz  # PyMuPDF

def extrair_texto_com_marcacao_de_paginas(pdf_path: str) -> str:
    try:
        doc = fitz.open(pdf_path)
        blocos_de_saida = []
        for i, page in enumerate(doc.pages()):
            blocos_de_texto = page.get_text("blocks")
            blocos_de_texto.sort(key=lambda b: (b[1], b[0]))
            texto_da_pagina = "\n".join([b[4].strip() for b in blocos_de_texto])
            blocos_de_saida.append(f"### Página {i+1}\n{texto_da_pagina if texto_da_pagina.strip() else '[sem conteúdo]'}\n---")
        doc.close()
        return "\n".join(blocos_de_saida)
    except Exception as e:
        print(f"Erro ao extrair texto do PDF: {e}")
        return ""

def filtrar_contexto_por_pagina(contexto_str: str, max_paginas: int) -> str:
    if not contexto_str: return ""
    blocos_validos = []
    # Encontra todos os blocos (cabeçalho ou página)
    todos_os_blocos = re.findall(r"(\{[\s\S]*?\})", contexto_str)
    for bloco in todos_os_blocos:
        match_pagina = re.search(r"página:\s*(\d+)", bloco, re.IGNORECASE)
        if match_pagina:
            if int(match_pagina.group(1)) <= max_paginas:
                blocos_validos.append(bloco)
        else: # Mantém blocos que não são de página (ex: cabeçalho)
            blocos_validos.append(bloco)
    return "\n\n".join(blocos_validos)

def estruturar_dados_finais(contexto_corrigido_e_filtrado: str) -> str:
    if not contexto_corrigido_e_filtrado: return ""
    
    output_parts = []
    
    cabecalho_match = re.search(r"(\{[\s\S]*?Tipo do documento:[\s\S]*?\})", contexto_corrigido_e_filtrado)
    output_parts.append(cabecalho_match.group(0) if cabecalho_match else "{\nTipo do documento: --\n}")
        
    listas = { "quem assinou": [], "leis": [], "órgãos envolvidos": [], "data": [], "cálculo": [], "resumo da página": [] }
    placeholders_to_skip = {"nenhum", "nenhuma", "ninguém", "--"}

    def extrair_numero_pagina(texto: str) -> int:
        match = re.search(r'\(Página (\d+)\)$', texto)
        return int(match.group(1)) if match else float('inf')

    blocos_de_pagina = re.findall(r"(\{[\s\S]*?página:[\s\S]*?\})", contexto_corrigido_e_filtrado)
    for bloco in blocos_de_pagina:
        num_pagina_match = re.search(r"página:\s*(\d+)", bloco)
        if not num_pagina_match: continue
        num_pagina = num_pagina_match.group(1)
        
        for chave in listas:
            padrao = re.compile(rf"^\s*{chave.replace(' ', r'\s*')}\s*:\s*(.+)", re.IGNORECASE | re.MULTILINE)
            for linha in bloco.splitlines():
                match = padrao.match(linha)
                if match:
                    val = match.group(1).strip().strip('}')
                    if val and val.lower() not in placeholders_to_skip:
                        listas[chave].append(f"{val} (Página {num_pagina})")

    for chave in listas:
        listas[chave].sort(key=extrair_numero_pagina)

    bloco_dados_linhas = ["{"]
    for chave, lista_valores in listas.items():
        if lista_valores:
            bloco_dados_linhas.append(f"{chave}: {', '.join(lista_valores)}")
    bloco_dados_linhas.append("}")
    
    output_parts.append("\n".join(bloco_dados_linhas))
    return "\n\n".join(output_parts)