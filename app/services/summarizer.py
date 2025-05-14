import requests
import json
from pathlib import Path
from dotenv import load_dotenv
import os
import asyncio
import logging

try:
    from app.prompts.LLM import pergunta, corrigir
except ImportError:
    logging.warning("app.prompts.LLM não encontrado ou não contém 'pergunta' e 'corrigir'. Usando placeholders.")
    pergunta = "Crie uma tabela com os dados do arquivo?"
    corrigir = "Revise a informação anterior e forneça uma versão corrigida, mais precisa e concisa."

try:
    import tiktoken
    tiktoken_available = True
except ImportError:
    tiktoken_available = False
    logging.warning("Tiktoken não está instalado. A estimativa de tokens não funcionará como esperado.")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def estimate_tokens_openai_style(text: str, model_name: str = "gpt-3.5-turbo") -> int:
    if not tiktoken_available:
        return len(text) // 4
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    num_tokens = len(encoding.encode(text))
    return num_tokens

load_dotenv()
caminho_atual = Path(__file__).resolve().parent
PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_HOST = os.getenv('PROXY_HOST')
PROXY_PORT = os.getenv('PROXY_PORT')

LOCAL_LLM_URL = os.getenv('LOCAL_LLM_URL', 'http://10.11.15.76:1234/v1/chat/completions')
LLM_REQUEST_TIMEOUT = int(os.getenv('LLM_REQUEST_TIMEOUT', '300'))

proxies = {
    "http": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
    "https": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
} if PROXY_USER and PROXY_HOST and PROXY_PORT else None

MODEL_NAME_FOR_TOKEN_ESTIMATION = "gpt-3.5-turbo"
MAX_TOTAL_TOKENS_THRESHOLD = 9000
TARGET_CONTEXTO_CHUNK_TOKENS = 8000

async def ask_local_llm(contexto: str, prompt_usuario: str):
    if not LOCAL_LLM_URL:
        logging.error("LOCAL_LLM_URL não está configurado.")
        return None
        
    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        "model": "local-model", 
        "messages": [
            {"role": "system", "content": f"Use o seguinte texto/documento para responder à pergunta:\n\n{contexto}"},
            {"role": "user", "content": prompt_usuario}
        ],
        "temperature": 0.2,
        "max_tokens": 2000 
    }

    use_proxies = None
    if LOCAL_LLM_URL.startswith('http://127.0.0.1') or \
       LOCAL_LLM_URL.startswith('http://localhost') or \
       LOCAL_LLM_URL.startswith('http://10.') or \
       LOCAL_LLM_URL.startswith('http://192.168.'): 
        use_proxies = None
    else:
        use_proxies = proxies 
    
    try:
        loop = asyncio.get_event_loop()
        logging.info(f"Enviando requisição para LLM. Timeout: {LLM_REQUEST_TIMEOUT}s. URL: {LOCAL_LLM_URL}")
        response = await loop.run_in_executor(
            None, 
            lambda: requests.post(
                LOCAL_LLM_URL, 
                headers=headers, 
                json=payload, 
                proxies=use_proxies, 
                timeout=LLM_REQUEST_TIMEOUT 
            )
        )
        response.raise_for_status() 
        reply = response.json()['choices'][0]['message']['content']
        return reply
    except requests.exceptions.Timeout:
        logging.error(f'Timeout ({LLM_REQUEST_TIMEOUT}s) ao comunicar com LLM Local: {LOCAL_LLM_URL}')
        return None
    except requests.exceptions.RequestException as e:
        logging.error(f'Erro ao comunicar com LLM Local: {e}')
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f'Detalhes do erro: Status {e.response.status_code}, Resposta: {e.response.text}')
        return None
    except (KeyError, IndexError, json.JSONDecodeError) as e:
        logging.error(f'Erro ao processar resposta do LLM Local: {e} - Resposta: {response.text if "response" in locals() and hasattr(response, "text") else "N/A"}')
        return None

def split_contexto_por_tokens(texto_completo: str, max_tokens_chunk: int, model_name: str) -> list[str]:
    chunks = []
    current_char_index = 0
    text_len = len(texto_completo)

    if not texto_completo.strip():
        return []

    while current_char_index < text_len:
        remaining_text = texto_completo[current_char_index:]
        tokens_remaining_text = estimate_tokens_openai_style(remaining_text, model_name)

        if tokens_remaining_text <= max_tokens_chunk:
            chunks.append(remaining_text)
            break

        best_split_char_index = -1
        temp_offset_search = current_char_index
        while True:
            next_brace_pos_local = texto_completo.find('}', temp_offset_search)
            if next_brace_pos_local == -1:
                break
            candidate_chunk_text = texto_completo[current_char_index : next_brace_pos_local + 1]
            tokens_candidate_chunk = estimate_tokens_openai_style(candidate_chunk_text, model_name)
            if tokens_candidate_chunk <= max_tokens_chunk:
                best_split_char_index = next_brace_pos_local
                temp_offset_search = next_brace_pos_local + 1
                if temp_offset_search >= text_len:
                    break
            else:
                break
        
        if best_split_char_index != -1:
            chunk_to_add = texto_completo[current_char_index : best_split_char_index + 1]
            chunks.append(chunk_to_add)
            current_char_index = best_split_char_index + 1
        else:
            first_brace_in_remaining = texto_completo.find('}', current_char_index)
            if first_brace_in_remaining != -1 :
                chunk_to_add = texto_completo[current_char_index : first_brace_in_remaining + 1]
                logging.warning(
                    f"Segmento de char {current_char_index} a {first_brace_in_remaining + 1} "
                    f"(tokens: {estimate_tokens_openai_style(chunk_to_add, model_name)}) "
                    f"pode exceder o limite de {max_tokens_chunk} tokens. "
                    "Forçando quebra no primeiro '}}' encontrado pois não houve melhor ponto."
                )
                chunks.append(chunk_to_add)
                current_char_index = first_brace_in_remaining + 1
            else:
                chunk_to_add = texto_completo[current_char_index:]
                logging.error(
                    f"Não foi possível dividir o texto restante (a partir do char {current_char_index}, "
                    f"tokens: {tokens_remaining_text}) dentro do limite de {max_tokens_chunk} tokens "
                    "respeitando a regra de quebra após '}' pois não há '}' ou o primeiro já excede. "
                    "Adicionando o restante como um único chunk."
                )
                chunks.append(chunk_to_add)
                current_char_index = text_len
                
    return [c for c in chunks if c.strip()]

async def generate_summary(extracted_data: str, doc_id: str):
    if not extracted_data or not extracted_data.strip():
        logging.warning(f"Dados extraídos (contexto) vazios ou inválidos para doc_id: {doc_id}. Retornando.")
        return "[ERRO: DADOS EXTRAÍDOS VAZIOS OU INVÁLIDOS]"

    contexto_principal = extracted_data
    
    logging.info(f"Iniciando geração de resumo para doc_id: {doc_id}.")
    logging.info(f"Conectado ao modelo local em: {LOCAL_LLM_URL} com timeout de {LLM_REQUEST_TIMEOUT}s.")

    tokens_contexto = estimate_tokens_openai_style(contexto_principal, MODEL_NAME_FOR_TOKEN_ESTIMATION)
    tokens_pergunta = estimate_tokens_openai_style(pergunta, MODEL_NAME_FOR_TOKEN_ESTIMATION)
    estimativa_total_inicial = tokens_contexto + tokens_pergunta
    
    logging.info(f"Estimativa de tokens para contexto (doc_id: {doc_id}): {tokens_contexto}")
    logging.info(f"Estimativa de tokens para 'pergunta' (doc_id: {doc_id}): {tokens_pergunta}")
    logging.info(f"Estimativa total inicial (contexto + pergunta) (doc_id: {doc_id}): {estimativa_total_inicial}")

    resposta_final = ""

    if estimativa_total_inicial <= MAX_TOTAL_TOKENS_THRESHOLD:
        logging.info(f"Contexto dentro do limite de {MAX_TOTAL_TOKENS_THRESHOLD} tokens. Processando como um único bloco para doc_id: {doc_id}.")
        
        resposta_inicial = await ask_local_llm(contexto_principal, pergunta)
        
        if resposta_inicial is None:
            logging.error(f"Falha ao obter resposta inicial para o contexto completo (doc_id: {doc_id}).")
            resposta_final = f"[ERRO NA ETAPA DE PERGUNTA INICIAL PARA O CONTEXTO COMPLETO DOC_ID: {doc_id}]"
        else:
            resposta_final = resposta_inicial
        
        logging.info(f"Processamento de bloco único concluído para doc_id: {doc_id}. Sem etapa de correção neste caso.")

    else:
        logging.info(f"Contexto excede o limite de {MAX_TOTAL_TOKENS_THRESHOLD} tokens para doc_id: {doc_id}. Iniciando divisão em chunks de até {TARGET_CONTEXTO_CHUNK_TOKENS} tokens de contexto.")
        
        chunks_de_contexto = split_contexto_por_tokens(contexto_principal, TARGET_CONTEXTO_CHUNK_TOKENS, MODEL_NAME_FOR_TOKEN_ESTIMATION)
        
        if not chunks_de_contexto:
            logging.error(f"Divisão do contexto resultou em zero chunks para doc_id: {doc_id}. Contexto original (primeiros 200 chars): {contexto_principal[:200]}")
            return f"[ERRO: FALHA AO DIVIDIR O CONTEXTO EM CHUNKS PARA DOC_ID: {doc_id}]"

        logging.info(f"Contexto dividido em {len(chunks_de_contexto)} chunks para doc_id: {doc_id}.")
        lista_respostas_iniciais_dos_chunks = []

        for i, chunk_ctx in enumerate(chunks_de_contexto):
            logging.info(f"Processando chunk {i+1}/{len(chunks_de_contexto)} para doc_id: {doc_id} (etapa inicial)...")
            tokens_chunk_ctx = estimate_tokens_openai_style(chunk_ctx, MODEL_NAME_FOR_TOKEN_ESTIMATION)
            logging.info(f"  Tokens estimados para o chunk de contexto {i+1} (doc_id: {doc_id}): {tokens_chunk_ctx}")
            
            resposta_inicial_chunk = await ask_local_llm(chunk_ctx, pergunta)

            if resposta_inicial_chunk is None:
                logging.error(f"  Falha ao obter resposta inicial para o chunk {i+1} (doc_id: {doc_id}).")
                lista_respostas_iniciais_dos_chunks.append(f"[ERRO NA PERGUNTA INICIAL PARA CHUNK {i+1} DOC_ID: {doc_id}]")
            else:
                lista_respostas_iniciais_dos_chunks.append(resposta_inicial_chunk)
            logging.info(f"  Etapa inicial do chunk {i+1} concluída para doc_id: {doc_id}.")

        logging.info(f"Todas as respostas iniciais dos chunks coletadas para doc_id: {doc_id}. Concatenando para correção final...")
        texto_concatenado_para_correcao = "\n\n---\n[CHUNK SEPARADOR]\n---\n\n".join(filter(None, lista_respostas_iniciais_dos_chunks))

        if not texto_concatenado_para_correcao.strip():
            logging.error(f"Texto concatenado das respostas iniciais dos chunks está vazio para doc_id: {doc_id}. Não é possível prosseguir com a correção.")
            resposta_final = "[ERRO: NENHUMA RESPOSTA VÁLIDA DOS CHUNKS PARA CORRIGIR]"
        else:
            logging.info(f"Enviando texto concatenado das respostas dos chunks para 'correção' final (doc_id: {doc_id})...")
            resposta_final_corrigida = await ask_local_llm(texto_concatenado_para_correcao, corrigir)

            if resposta_final_corrigida is None:
                logging.error(f"Falha ao obter resposta corrigida final para o texto concatenado (doc_id: {doc_id}). Usando o texto concatenado não corrigido.")
                resposta_final = texto_concatenado_para_correcao
            else:
                resposta_final = resposta_final_corrigida
        
        logging.info(f"Processamento de todos os chunks e correção final concluídos para doc_id: {doc_id}.")

    logging.info(f"Retornando resultado final para doc_id: {doc_id} (primeiros 100 chars: {str(resposta_final)[:100]}...).")
    return resposta_final