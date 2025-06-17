import asyncio
import logging
import os
import re
from pathlib import Path

from app.prompts.LLM import corrigir1, pergunta1, pergunta2
from app.services import limpar
from dotenv import load_dotenv

from app.services import sum_modulo
import tiktoken

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

LOCAL_LLM_URL = os.getenv('LOCAL_LLM_URL', 'http://10.11.15.76:1234/v1/chat/completions')
LLM_REQUEST_TIMEOUT = int(os.getenv('LLM_REQUEST_TIMEOUT', '300'))
MODEL_NAME_FOR_TOKEN_ESTIMATION = "gpt-3.5-turbo"
MAX_TOTAL_TOKENS_THRESHOLD = 9000
TARGET_CONTEXTO_CHUNK_TOKENS = 8000
TARGET_SUMMARY_CHUNK_TOKENS = 1000

def estimate_tokens_openai_style(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

async def ask_local_llm(contexto: str, prompt_usuario: str):
    if not LOCAL_LLM_URL:
        logging.error("LOCAL_LLM_URL não está configurado.")
        return None

    headers = {'Content-Type': 'application/json'}
    payload = {
        "model": "local-model",
        "messages": [
            {"role": "system", "content": f"Use o seguinte texto/documento para responder à pergunta:\n\n{contexto}"},
            {"role": "user", "content": prompt_usuario}
        ],
        "temperature": 0.1,
        "max_tokens": 2000
    }

    try:
        import httpx
        async with httpx.AsyncClient(timeout=LLM_REQUEST_TIMEOUT) as client:
            logging.info(f"Enviando requisição para LLM: {LOCAL_LLM_URL}")
            response = await client.post(LOCAL_LLM_URL, headers=headers, json=payload)
            response.raise_for_status()
            reply = response.json()['choices'][0]['message']['content']
            return reply
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.error(f'Erro ao comunicar com LLM Local: {e}')
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f'Detalhes: Status {e.response.status_code}, Resposta: {e.response.text}')
        return None
    except (KeyError, IndexError) as e:
        logging.error(f'Erro ao processar resposta do LLM: {e}')
        return None

async def generate_summary(extracted_data: str, doc_id: str):
    if not extracted_data or not extracted_data.strip():
        return "[ERRO: DADOS EXTRAÍDOS VAZIOS OU INVÁLIDOS]"

    antes_do_resumo, depois_do_resumo = limpar.dividir_em_antes_e_depois_do_resumo(extracted_data)
    
    resposta_parte1 = "[PARTE 1 ANTES DO RESUMO VAZIA]"
    if antes_do_resumo.strip():
        total_p1 = estimate_tokens_openai_style(antes_do_resumo, MODEL_NAME_FOR_TOKEN_ESTIMATION) + \
                   estimate_tokens_openai_style(pergunta1, MODEL_NAME_FOR_TOKEN_ESTIMATION)

        if total_p1 <= MAX_TOTAL_TOKENS_THRESHOLD:
            resposta_parte1 = await ask_local_llm(antes_do_resumo, pergunta1) or \
                              f"[ERRO NA PERGUNTA DIRETA NA PARTE 1 - DOC_ID {doc_id}]"
        else:
            chunks_p1 = sum_modulo.split_contexto_por_tokens(antes_do_resumo, TARGET_CONTEXTO_CHUNK_TOKENS, MODEL_NAME_FOR_TOKEN_ESTIMATION)
            if not chunks_p1:
                resposta_parte1 = f"[ERRO NA DIVISÃO EM CHUNKS DA PARTE 1 - DOC_ID {doc_id}]"
            else:
                tasks = [ask_local_llm(chunk, pergunta1) for chunk in chunks_p1]
                respostas_brutas_p1 = await asyncio.gather(*tasks)
                
                respostas_chunks_p1 = [
                    resp or f"[ERRO NO CHUNK {j+1} DA PARTE 1 - DOC_ID {doc_id}]"
                    for j, resp in enumerate(respostas_brutas_p1)
                ]
                
                concatenado_p1 = "\n\n---\n[CHUNK SEPARADOR]\n---\n\n".join(respostas_chunks_p1)
                resposta_parte1 = await ask_local_llm(concatenado_p1, corrigir1) or concatenado_p1

    resumo_final_textos = []
    if depois_do_resumo.strip():
        summary_chunks = sum_modulo.split_prose_text(depois_do_resumo, TARGET_SUMMARY_CHUNK_TOKENS, MODEL_NAME_FOR_TOKEN_ESTIMATION)

        if not summary_chunks:
            resumo_final_textos.append(f"[ERRO NA DIVISÃO EM CHUNKS DA PARTE 2 - DOC_ID {doc_id}]")
        else:
            tasks_p2 = [ask_local_llm(chunk, pergunta2) for chunk in summary_chunks]
            respostas_brutas_p2 = await asyncio.gather(*tasks_p2)

            for resposta_chunk_p2 in respostas_brutas_p2:
                if resposta_chunk_p2 and not resposta_chunk_p2.startswith("[ERRO"):
                    texto_limpo = limpar._clean_llm_summary_chunk(resposta_chunk_p2)
                    if texto_limpo:
                        resumo_final_textos.append(texto_limpo)
                elif resposta_chunk_p2:
                    resumo_final_textos.append(resposta_chunk_p2)

    resumo_cell_content = " ".join(resumo_final_textos) if resumo_final_textos else \
                         "[Nenhum resumo detalhado pôde ser gerado.]"
    
    tipo = limpar.extrair_valor_tabela(resposta_parte1, "tipo do documento")
    leis = limpar.extrair_valor_tabela(resposta_parte1, "leis")
    assinaturas = limpar.extrair_valor_tabela(resposta_parte1, "assinaturas")
    
    markdown_final = f"""| item | detalhes |
|---|---|
| tipo do documento | {tipo} |
| Leis | {leis} |
| Assinaturas | {assinaturas} |
| Resumo | {resumo_cell_content} |"""
    
    return markdown_final