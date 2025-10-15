# app/services/question_answering.py

import re
import asyncio
from app.services.chatpdf_client import process_pdf 
from app.prompts.chatPDF import pPaginaUnica, pCabecalho


async def ask_questions(
    source_id: str, 
    chatpdf_api_key: str, 
    texto_do_bloco_atual: str,
    num_blocos_qa: int
):
    """
    VERSÃO SIMPLIFICADA: Processa um bloco de texto e extrai dados APENAS das páginas,
    sem extrair o cabeçalho.
    """
    print(f"Iniciando processamento de PÁGINAS para o source_id: {source_id}")

    paginas_do_bloco = texto_do_bloco_atual.split('---')
    respostas_das_paginas = []
    tasks = []

    for texto_pagina_individual in paginas_do_bloco:
        texto_limpo = texto_pagina_individual.strip()
        if not texto_limpo:
            continue

        match = re.search(r'###\s*Página\s*(\d+)', texto_limpo)
        if match:
            numero_pagina_real = match.group(1)
        else:
            print(f"AVISO: Não foi possível encontrar o número da página no trecho: {texto_limpo[:100]}...")
            continue

        prompt_final = pPaginaUnica.format(
            numero_da_pagina=numero_pagina_real,
            texto_da_pagina=texto_limpo
        )
        
        task = process_pdf(
            source_id=source_id, 
            num_blocos_qa=num_blocos_qa,
            chatpdf_api_key=chatpdf_api_key,
            prompt_text=prompt_final
        )
        tasks.append(task)

    print(f"Enviando {len(tasks)} requisições de página para a API...")
    resultados = await asyncio.gather(*tasks, return_exceptions=True)
    
    for res in resultados:
        if isinstance(res, Exception):
            print(f"Erro em uma das chamadas de página: {res}")
        else:
            _source_id, summary_str = res
            respostas_das_paginas.append(summary_str)
    
    print("Processamento de todas as páginas do bloco concluído.")
    
    # Retorna APENAS os resultados das páginas
    return "\n\n".join(respostas_das_paginas)