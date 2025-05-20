import re
import os
import glob

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

def remover_blocos_metadados_string(conteudo_string):
    padrao_bloco = re.compile(
        r"{\s*\n"
        r"\s*Tipo do documento:.*?\n"
        r"\s*Remetente:.*?\n"
        r"\s*Data do envio:.*?\n"
        r"\s*Destinatário:.*?\n"
        r"\s*}",
        re.DOTALL
    )

    blocos_encontrados = list(padrao_bloco.finditer(conteudo_string))

    if not blocos_encontrados or len(blocos_encontrados) == 1:
        return conteudo_string

    conteudo_modificado = conteudo_string
    for i in range(len(blocos_encontrados) - 1, 0, -1):
        bloco_para_remover = blocos_encontrados[i]
        conteudo_modificado = conteudo_modificado[:bloco_para_remover.start()] + \
                              conteudo_modificado[bloco_para_remover.end():]

def limpar_arquivos_temporarios(temp_file_path, generated_pdf_path_original, code="GERAL"):
    if temp_file_path and os.path.exists(temp_file_path):
        try:
            os.remove(temp_file_path)
            print(f"[{code}] Arquivo temporário '{temp_file_path}' removido.")
        except Exception as e_remove_temp:
            print(f"[{code}] Erro ao remover arquivo temporário '{temp_file_path}': {e_remove_temp}")
    elif temp_file_path:
        print(f"[{code}] Arquivo temporário '{temp_file_path}' não encontrado para remoção.")

    if generated_pdf_path_original and os.path.exists(generated_pdf_path_original):
        try:
            os.remove(generated_pdf_path_original)
            print(f"[{code}] PDF original gerado '{generated_pdf_path_original}' limpo.")
        except Exception as e_remove_pdf_orig:
            print(f"[{code}] Erro ao remover PDF original gerado '{generated_pdf_path_original}': {e_remove_pdf_orig}")
    elif generated_pdf_path_original:
        print(f"[{code}] PDF original gerado '{generated_pdf_path_original}' não encontrado para remoção.")
