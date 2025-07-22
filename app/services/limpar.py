# limpar.py

import re
import os
import glob
import fitz  # PyMuPDF
import logging
import json
import unicodedata

# As funções abaixo permanecem as mesmas
def ajustar_numeros_de_pagina(raw_contexto_str: str) -> str:
    blocks = re.findall(r"(\{[\s\S]*?\})", raw_contexto_str)
    if not blocks:
        return raw_contexto_str

    page_offset = 0
    processed_first_document_header = False
    adjusted_block_strings = []

    for block_str in blocks:
        modified_block_str = block_str
        if "Tipo do documento:" in block_str:
            if processed_first_document_header:
                page_offset += 10
            else:
                processed_first_document_header = True
        elif "página:" in block_str:
            match = re.search(r"(página:\s*)(\d+)", modified_block_str)
            if match:
                prefix = match.group(1)
                original_page_num_str = match.group(2)
                original_page_num = int(original_page_num_str)
                new_page_num = original_page_num + page_offset
                modified_block_str = re.sub(
                    r"(página:\s*)\d+", f"{prefix}{new_page_num}", modified_block_str, count=1
                )
        adjusted_block_strings.append(modified_block_str)
    return "\n\n".join(adjusted_block_strings)


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

def ajustar(raw_contexto_str: str) -> str:
    output_parts = []
    remaining_text = raw_contexto_str

    default_first_block = "{\nTipo do documento: --\nRemetente:--\nData do envio: --\nDestinatário: --\n}"
    
    first_block_match = re.search(r"^\s*{\s*([\s\S]*?)\s*}\s*", remaining_text, re.MULTILINE)

    if first_block_match:
        block_content_str = first_block_match.group(1).strip()
        output_parts.append("{\n" + block_content_str + "\n}")
        remaining_text = remaining_text[first_block_match.end():].strip()
    else:
        output_parts.append(default_first_block)

    quem_assinou_list = []
    leis_list = []
    orgaos_envolvidos_list = []
    datas_list = []
    calculos_list = []
    resumos_pagina_list = []

    page_block_regex = re.compile(r"{\s*([\s\S]*?)\s*}", re.MULTILINE)
    
    placeholders_to_skip = {"nenhum", "nenhuma", "ninguém"}

    for block_match in page_block_regex.finditer(remaining_text):
        block_content = block_match.group(1).strip()
        block_lines = block_content.splitlines()

        current_page_num_str = None
        temp_resumo_lines = []
        collecting_resumo = False

        for line in block_lines:
            page_num_match = re.match(r"^\s*página\s*:\s*(\d+)\s*$", line, re.IGNORECASE)
            if page_num_match:
                current_page_num_str = page_num_match.group(1)
                break 
        
        if not current_page_num_str:
            continue

        for line_idx, line in enumerate(block_lines):
            if collecting_resumo:
                is_new_key = any(
                    re.match(p, line, re.IGNORECASE) for p in [
                        r"^\s*página\s*:", r"^\s*quem assinou\s*:", r"^\s*leis\s*:",
                        r"^\s*órgãos envolvidos\s*:", r"^\s*data\s*:", r"^\s*cálculo\s*:"
                    ]
                )
                if is_new_key:
                    if temp_resumo_lines:
                        resumo_val = "\n".join(temp_resumo_lines).strip()
                        if resumo_val.lower() not in placeholders_to_skip and resumo_val:
                            resumos_pagina_list.append(f"{resumo_val} (Página {current_page_num_str})")
                    temp_resumo_lines = []
                    collecting_resumo = False
                else:
                    temp_resumo_lines.append(line.strip())
                    if line_idx == len(block_lines) - 1 and temp_resumo_lines:
                        resumo_val = "\n".join(temp_resumo_lines).strip()
                        if resumo_val.lower() not in placeholders_to_skip and resumo_val:
                            resumos_pagina_list.append(f"{resumo_val} (Página {current_page_num_str})")
                        temp_resumo_lines = []
                        collecting_resumo = False
                    continue

            if match := re.match(r"^\s*quem assinou\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip()
                if val.lower() not in placeholders_to_skip and val:
                    quem_assinou_list.append(f"{val} (Página {current_page_num_str})")
                continue

            if match := re.match(r"^\s*leis\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip()
                if val.lower() not in placeholders_to_skip and val:
                    leis_list.append(f"{val} (Página {current_page_num_str})")
                continue

            if match := re.match(r"^\s*órgãos envolvidos\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip()
                if val.lower() not in placeholders_to_skip and val:
                    orgaos_envolvidos_list.append(f"{val} (Página {current_page_num_str})")
                continue

            if match := re.match(r"^\s*resumo da página\s*:\s*(.*)\s*$", line, re.IGNORECASE):
                collecting_resumo = True
                initial = match.group(1).strip()
                if initial:
                    temp_resumo_lines.append(initial)
                if line_idx == len(block_lines) - 1 and temp_resumo_lines:
                    resumo_val = "\n".join(temp_resumo_lines).strip()
                    if resumo_val.lower() not in placeholders_to_skip and resumo_val:
                        resumos_pagina_list.append(f"{resumo_val} (Página {current_page_num_str})")
                    temp_resumo_lines = []
                    collecting_resumo = False
                continue

            if match := re.match(r"^\s*data\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip()
                if val.lower() not in placeholders_to_skip and val:
                    datas_list.append(f"{val} (Página {current_page_num_str})")
                continue

            if match := re.match(r"^\s*cálculo\s*:\s*(.+)\s*$", line, re.IGNORECASE):
                val = match.group(1).strip()
                if val.lower() not in placeholders_to_skip and val:
                    calculos_list.append(f"{val} (Página {current_page_num_str})")
                continue

        if collecting_resumo and temp_resumo_lines:
            resumo_val = "\n".join(temp_resumo_lines).strip()
            if resumo_val.lower() not in placeholders_to_skip and resumo_val:
                resumos_pagina_list.append(f"{resumo_val} (Página {current_page_num_str})")

    second_block_lines = ["{"]
    second_block_lines.append(f"quem assinou: {', '.join(quem_assinou_list) if quem_assinou_list else '--'}")
    second_block_lines.append(f"leis: {', '.join(leis_list) if leis_list else '--'}")
    second_block_lines.append(f"órgãos envolvidos: {', '.join(orgaos_envolvidos_list) if orgaos_envolvidos_list else '--'}")
    second_block_lines.append(f"data: {', '.join(datas_list) if datas_list else '--'}")
    second_block_lines.append(f"cálculo: {', '.join(calculos_list) if calculos_list else '--'}")
    second_block_lines.append(f"resumo da página: {', '.join(resumos_pagina_list) if resumos_pagina_list else '--'}")
    second_block_lines.append("}")
    output_parts.append("\n".join(second_block_lines))

    return "\n\n".join(output_parts)


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