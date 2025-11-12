import re
import fitz
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def extrair_texto_com_marcacao_de_paginas(pdf_path: str) -> str:
    try:
        doc = fitz.open(pdf_path)
        blocos_de_saida = []
        for i, page in enumerate(doc.pages()):
            texto_da_pagina = page.get_text("text").strip()
            blocos_de_saida.append(f"### Página {i+1}\n{texto_da_pagina if texto_da_pagina else '[sem conteúdo]'}\n---")
        doc.close()
        return "\n".join(blocos_de_saida)
    except Exception as e:
        logging.error(f"Erro ao extrair texto do PDF: {e}", exc_info=True)
        return ""

def filtrar_contexto_por_pagina(contexto_str: str, max_paginas: int) -> str:
    if not contexto_str: return ""
    blocos_validos = []
    todos_os_blocos = re.findall(r"(\{[\s\S]*?\})", contexto_str)
    
    for i, bloco in enumerate(todos_os_blocos):
        if i == 0:
            blocos_validos.append(bloco)
            continue
        
        match_pagina = re.search(r"página:\s*(\d+)", bloco, re.IGNORECASE)
        if match_pagina and int(match_pagina.group(1)) <= max_paginas:
            blocos_validos.append(bloco)
            
    return "\n\n".join(blocos_validos)

def estruturar_dados_finais(contexto_corrigido_e_filtrado: str) -> dict:

    if not contexto_corrigido_e_filtrado:
        return {}

    todos_os_blocos = re.findall(r"(\{[\s\S]+?\})", contexto_corrigido_e_filtrado)
    if not todos_os_blocos: return {}
        
    cabecalho_texto = todos_os_blocos[0]
    tipo_doc_match = re.search(r"Tipo do documento:\s*(.*)", cabecalho_texto, re.IGNORECASE)
    cabecalho_dict = {
        "tipo do documento": tipo_doc_match.group(1).strip() if tipo_doc_match else "--"
    }
    
    blocos_de_pagina = todos_os_blocos[1:]
    
    chaves_a_extrair = ["quem assinou", "leis", "órgãos envolvidos", "data", "cálculo", "resumo da página"]
    dados_agregados = {chave: [] for chave in chaves_a_extrair}
    placeholders_to_skip = {"opalonte"}

    for bloco in blocos_de_pagina:
        num_pagina_match = re.search(r"página:\s*(\d+)", bloco, re.IGNORECASE)
        if not num_pagina_match: continue
        num_pagina = num_pagina_match.group(1)

        for chave in chaves_a_extrair:
            padrao = re.compile(rf"{chave}:\s*([\s\S]+?)(?=\n[^\n:]+:|\s*\}})", re.IGNORECASE)
            match = padrao.search(bloco)
            if not match: continue

            val_bruto = match.group(1)
            
            val_limpo = val_bruto.strip().strip(',').strip()
            
            while len(val_limpo) > 1 and (
                (val_limpo.startswith('[') and val_limpo.endswith(']')) or
                (val_limpo.startswith('"') and val_limpo.endswith('"'))
            ):
                val_limpo = val_limpo[1:-1].strip()

            check_val = val_limpo.lower()
            for p in placeholders_to_skip:
                check_val = check_val.replace(p, "")
            check_val = check_val.strip(" ,.-'\"")
            era_placeholder = not check_val

            if val_limpo and not era_placeholder and re.search(r'[a-zA-Z0-9]', val_limpo):
                dados_agregados[chave].append(f"{val_limpo} (Página {num_pagina})")

    for chave in dados_agregados:
        dados_agregados[chave].sort(key=lambda x: int(re.search(r'\(Página (\d+)\)', x).group(1)))
    
    return {
        "cabecalho": cabecalho_dict,
        "dados_agregados": dados_agregados
    }