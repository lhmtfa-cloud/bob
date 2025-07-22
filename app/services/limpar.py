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
def estruturar_dados_finais(contexto_corrigido: str) -> str:
    """
    Recebe o contexto com números de página já corrigidos e apenas
    agrega, ordena e formata a saída final.
    """
    if not contexto_corrigido: return ""
    
    output_parts = []
    
    # Pega o cabeçalho (já está no início do texto)
    cabecalho_match = re.search(r"(\{[\s\S]*?Tipo do documento:[\s\S]*?\})", contexto_corrigido)
    if cabecalho_match:
        output_parts.append(cabecalho_match.group(1))
    else:
        output_parts.append("{\nTipo do documento: --\nRemetente: --\nData do envio: --\nDestinatário: --\n}")
        
    quem_assinou_list, leis_list, orgaos_envolvidos_list, datas_list, calculos_list, resumos_pagina_list = [], [], [], [], [], []
    placeholders_to_skip = {"nenhum", "nenhuma", "ninguém", "--"}

    def extrair_numero_pagina(texto: str) -> int:
        match = re.search(r'\(Página (\d+)\)$', texto)
        return int(match.group(1)) if match else float('inf')

    # Itera sobre os blocos de PÁGINA
    blocos_de_pagina = re.findall(r"(\{[\s\S]*?página:[\s\S]*?\})", contexto_corrigido)
    for bloco_str in blocos_de_pagina:
        current_page_num_str = re.search(r"página:\s*(\d+)", bloco_str).group(1)
        
        for line in bloco_str.splitlines():
            # A lógica de extração com regex continua a mesma
            if match := re.match(r"^\s*quem assinou\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip().strip('}')
                if val.lower() not in placeholders_to_skip and val: quem_assinou_list.append(f"{val} (Página {current_page_num_str})")
            elif match := re.match(r"^\s*leis\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip().strip('}')
                if val.lower() not in placeholders_to_skip and val: leis_list.append(f"{val} (Página {current_page_num_str})")
            elif match := re.match(r"^\s*órgãos envolvidos\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip().strip('}')
                if val.lower() not in placeholders_to_skip and val: orgaos_envolvidos_list.append(f"{val} (Página {current_page_num_str})")
            elif match := re.match(r"^\s*data\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip().strip('}')
                if val.lower() not in placeholders_to_skip and val: datas_list.append(f"{val} (Página {current_page_num_str})")
            elif match := re.match(r"^\s*cálculo\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip().strip('}')
                if val.lower() not in placeholders_to_skip and val: calculos_list.append(f"{val} (Página {current_page_num_str})")
            elif match := re.match(r"^\s*resumo da página\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip().strip('}')
                if val.lower() not in placeholders_to_skip and val: resumos_pagina_list.append(f"{val} (Página {current_page_num_str})")

    # Ordena as listas
    quem_assinou_list.sort(key=extrair_numero_pagina)
    leis_list.sort(key=extrair_numero_pagina)
    orgaos_envolvidos_list.sort(key=extrair_numero_pagina)
    datas_list.sort(key=extrair_numero_pagina)
    calculos_list.sort(key=extrair_numero_pagina)
    resumos_pagina_list.sort(key=extrair_numero_pagina)

    # Monta o bloco de dados final
    bloco_de_dados_linhas = ["{"]
    if quem_assinou_list: bloco_de_dados_linhas.append(f"quem assinou: {', '.join(quem_assinou_list)}")
    if leis_list: bloco_de_dados_linhas.append(f"leis: {', '.join(leis_list)}")
    if orgaos_envolvidos_list: bloco_de_dados_linhas.append(f"órgãos envolvidos: {', '.join(orgaos_envolvidos_list)}")
    if datas_list: bloco_de_dados_linhas.append(f"data: {', '.join(datas_list)}")
    if calculos_list: bloco_de_dados_linhas.append(f"cálculo: {', '.join(calculos_list)}")
    if resumos_pagina_list: bloco_de_dados_linhas.append(f"resumo da página: {', '.join(resumos_pagina_list)}")
    bloco_de_dados_linhas.append("}")
    
    output_parts.append("\n".join(bloco_de_dados_linhas))

    return "\n\n".join(output_parts)

def filtrar_contexto_por_pagina(contexto_str: str, numero_max_paginas_documento: int) -> str:
    if not contexto_str:
        return ""

    blocos = contexto_str.strip().split('\n\n')
    blocos_validos = []

    for bloco in blocos:
        if not bloco.strip(): 
            continue

        match_pagina = re.search(r"página:\s*(\d+)", bloco, re.IGNORECASE)

        if match_pagina:
            try:
                numero_pagina_bloco = int(match_pagina.group(1))
                if numero_pagina_bloco <= numero_max_paginas_documento:
                    blocos_validos.append(bloco)
            except ValueError:

                blocos_validos.append(bloco)
        else:
            blocos_validos.append(bloco)

    return "\n\n".join(blocos_validos)
import re

def processar_e_estruturar_contexto(raw_contexto_str: str, paginas_por_bloco: int) -> str:
    """
    Função robusta e unificada que processa o texto bruto da IA.
    1. Separa cabeçalhos e blocos de página.
    2. Mantém apenas o primeiro cabeçalho.
    3. Corrige a numeração das páginas reiniciada usando um offset.
    4. Agrega e ordena todas as informações.
    5. Formata a saída final, omitindo campos vazios.
    """
    if not raw_contexto_str:
        return ""

    todos_os_blocos = re.findall(r"(\{[\s\S]*?\})", raw_contexto_str)
    
    # 1. Separa cabeçalhos e páginas
    blocos_de_cabecalho = [b for b in todos_os_blocos if 'Tipo do documento:' in b]
    blocos_de_pagina_raw = [b for b in todos_os_blocos if 'página:' in b]

    # 2. Seleciona o cabeçalho final (o primeiro encontrado)
    cabecalho_final = blocos_de_cabecalho[0] if blocos_de_cabecalho else "{\nTipo do documento: --\nRemetente: --\nData do envio: --\nDestinatário: --\n}"

    # 3. Corrige a numeração das páginas de forma robusta
    blocos_de_pagina_corrigidos = []
    page_offset = 0
    ultima_pagina_original = 0
    for bloco_str in blocos_de_pagina_raw:
        match = re.search(r"página:\s*(\d+)", bloco_str)
        if not match: continue

        pagina_original_atual = int(match.group(1))

        # A condição de reinício é se a página atual for menor que a anterior
        if pagina_original_atual < ultima_pagina_original:
            page_offset += paginas_por_bloco
        
        pagina_corrigida = pagina_original_atual + page_offset
        
        bloco_corrigido = re.sub(r"(página:\s*)(\d+)", f"\\g<1>{pagina_corrigida}", bloco_str, 1)
        blocos_de_pagina_corrigidos.append(bloco_corrigido)
        
        ultima_pagina_original = pagina_original_atual

    # 4. Agrega e Ordena os dados das páginas já corrigidas
    quem_assinou_list, leis_list, orgaos_envolvidos_list, datas_list, calculos_list, resumos_pagina_list = [], [], [], [], [], []
    placeholders_to_skip = {"nenhum", "nenhuma", "ninguém", "--"}

    def extrair_numero_pagina(texto: str) -> int:
        match = re.search(r'\(Página (\d+)\)$', texto)
        return int(match.group(1)) if match else float('inf')

    for bloco_corrigido in blocos_de_pagina_corrigidos:
        current_page_num_str = re.search(r"página:\s*(\d+)", bloco_corrigido).group(1)
        
        # Extrai os dados de cada linha do bloco corrigido
        for line in bloco_corrigido.splitlines():
            if match := re.match(r"^\s*quem assinou\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip().strip('}')
                if val.lower() not in placeholders_to_skip and val: quem_assinou_list.append(f"{val} (Página {current_page_num_str})")
            elif match := re.match(r"^\s*leis\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip().strip('}')
                if val.lower() not in placeholders_to_skip and val: leis_list.append(f"{val} (Página {current_page_num_str})")
            elif match := re.match(r"^\s*órgãos envolvidos\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip().strip('}')
                if val.lower() not in placeholders_to_skip and val: orgaos_envolvidos_list.append(f"{val} (Página {current_page_num_str})")
            elif match := re.match(r"^\s*data\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip().strip('}')
                if val.lower() not in placeholders_to_skip and val: datas_list.append(f"{val} (Página {current_page_num_str})")
            elif match := re.match(r"^\s*cálculo\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip().strip('}')
                if val.lower() not in placeholders_to_skip and val: calculos_list.append(f"{val} (Página {current_page_num_str})")
            elif match := re.match(r"^\s*resumo da página\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip().strip('}')
                if val.lower() not in placeholders_to_skip and val: resumos_pagina_list.append(f"{val} (Página {current_page_num_str})")

    # A ordenação garante a cronologia correta no final
    quem_assinou_list.sort(key=extrair_numero_pagina)
    leis_list.sort(key=extrair_numero_pagina)
    orgaos_envolvidos_list.sort(key=extrair_numero_pagina)
    datas_list.sort(key=extrair_numero_pagina)
    calculos_list.sort(key=extrair_numero_pagina)
    resumos_pagina_list.sort(key=extrair_numero_pagina)

    # 5. Monta o bloco de dados final, omitindo campos vazios
    bloco_de_dados_linhas = ["{"]
    if quem_assinou_list: bloco_de_dados_linhas.append(f"quem assinou: {', '.join(quem_assinou_list)}")
    if leis_list: bloco_de_dados_linhas.append(f"leis: {', '.join(leis_list)}")
    if orgaos_envolvidos_list: bloco_de_dados_linhas.append(f"órgãos envolvidos: {', '.join(orgaos_envolvidos_list)}")
    if datas_list: bloco_de_dados_linhas.append(f"data: {', '.join(datas_list)}")
    if calculos_list: bloco_de_dados_linhas.append(f"cálculo: {', '.join(calculos_list)}")
    if resumos_pagina_list: bloco_de_dados_linhas.append(f"resumo da página: {', '.join(resumos_pagina_list)}")
    bloco_de_dados_linhas.append("}")
    
    bloco_de_dados_final = "\n".join(bloco_de_dados_linhas)

    return f"{cabecalho_final}\n\n{bloco_de_dados_final}"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===== FUNÇÃO MODIFICADA (VERSÃO 2) =====
def extrair_texto_com_marcacao_de_paginas(pdf_path: str) -> str:
    """
    Extrai texto de um PDF usando PyMuPDF, capturando todos os blocos de texto
    e ordenando-os para garantir a extração completa e na ordem correta.
    """
    logger.info(f"Extraindo texto com marcação de páginas de: {pdf_path} (usando PyMuPDF - modo de blocos)")
    try:
        doc = fitz.open(pdf_path)
        blocos_de_saida = []

        for i, page in enumerate(doc.pages()):
            # 1. Extrai todos os blocos de texto. Cada 'bloco' é um parágrafo.
            # O retorno é uma lista de tuplas: (x0, y0, x1, y1, "texto", num_bloco, tipo_bloco)
            blocos_de_texto = page.get_text("blocks")
            
            # 2. Ordena os blocos pela sua posição na página (de cima para baixo, depois da esquerda para a direita)
            # Isso garante a ordem de leitura correta.
            blocos_de_texto.sort(key=lambda b: (b[1], b[0]))
            
            # 3. Junta o texto de todos os blocos ordenados
            texto_completo_da_pagina = "\n".join([b[4].strip() for b in blocos_de_texto])
            texto_completo_da_pagina = texto_completo_da_pagina.strip()

            # Adiciona a marcação de página e o conteúdo extraído
            blocos_de_saida.append(f"### Página {i+1}\n{texto_completo_da_pagina if texto_completo_da_pagina else '[sem conteúdo de texto visível]'}\n---")

        doc.close()
        return "\n".join(blocos_de_saida)

    except Exception as e:
        logger.error(f"Erro ao extrair texto do PDF com PyMuPDF: {e}", exc_info=True)
        return ""
# =======================================


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

def _clean_llm_summary_chunk(chunk_text: str) -> str:
    if not chunk_text or not chunk_text.strip():
        return ""

    processed_text = chunk_text
    padrao = r"Página (\d+):"
    substituicao = r"(Página \1)"


    processed_text = re.sub(padrao, substituicao, processed_text)

    processed_text = re.sub(r'^\s*\|\s*item\s*\|.*$', '', processed_text, flags=re.MULTILINE | re.IGNORECASE)
    processed_text = re.sub(r'^\s*\|\s*---\s*\|.*$', '', processed_text, flags=re.MULTILINE)
    processed_text = re.sub(r'```markdown|```', '', processed_text)
    processed_text = re.sub(r'```', '', processed_text)

    processed_text = re.sub(r'-{10,}', ' ', processed_text)  
    processed_text = processed_text.replace('--', ' ')           

    processed_text = processed_text.replace('| Resumo |', '')
    processed_text = processed_text.replace('|', '')

    processed_text = re.sub(r'\s+', ' ', processed_text).strip()

    return processed_text