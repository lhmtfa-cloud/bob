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

