import requests
import json
from pathlib import Path
from dotenv import load_dotenv
import os
import asyncio

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()
caminho_atual = Path(__file__).resolve().parent
PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_HOST = os.getenv('PROXY_HOST')
PROXY_PORT = os.getenv('PROXY_PORT')

LOCAL_LLM_URL = 'http://10.11.15.76:1234/v1/chat/completions'

proxies = {
    "http": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
    "https": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
} if PROXY_USER else None  # Só usa proxy se proxy estiver configurado

# --- FUNCTIONS ---

async def ask_local_llm(contexto, pergunta):
    headers = {
        'Content-Type': 'application/json'
    }
    payload = {
        "model": "local-model",
        "messages": [
            {"role": "system", "content": f"Use o seguinte resumo para responder às perguntas:\n\n{contexto}"},
            {"role": "user", "content": pergunta}
        ],
        "temperature": 0.2,
        "max_tokens": 1000
    }

    # Não usar proxy para localhost
    use_proxies = None if LOCAL_LLM_URL.startswith('http://127.0.0.1') else proxies

    response = requests.post(LOCAL_LLM_URL, headers=headers, json=payload, proxies=use_proxies)
    
    if response.status_code == 200:
        reply = response.json()['choices'][0]['message']['content']
        return reply
    else:
        print('Erro ao comunicar com LLM Local:', response.status_code, response.text)
        return None


async def generate_summary(extracted_data, doc_id):
    resumo_mais_recente = extracted_data
    source_id = doc_id

    if not resumo_mais_recente:
        return

    contexto = resumo_mais_recente
    #print(contexto)
    if not contexto:
        return

    print(f"Conectado ao modelo local.")
    
    # Salva a pergunta e a resposta
    pergunta = "Crie uma tabela com os dados do resumo"
    resposta = await ask_local_llm(contexto, pergunta)

    return resposta

