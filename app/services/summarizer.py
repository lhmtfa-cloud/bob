# summarizer.py

import asyncio
import logging
import os
import re
from pathlib import Path

from app.prompts.LLM import pergunta3
from app.services import limpar
from dotenv import load_dotenv

import tiktoken

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
load_dotenv()

LOCAL_LLM_URL = os.getenv('LOCAL_LLM_URL', 'http://10.11.15.76:1234/v1/chat/completions')
LLM_REQUEST_TIMEOUT = int(os.getenv('LLM_REQUEST_TIMEOUT', '300'))


def _extract_metadata(text: str, field: str) -> str:
    pattern = re.compile(rf"^\s*{re.escape(field)}:\s*(.*)", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    if match:
        return match.group(1).strip()
    return "--"

def _sort_entries_by_page_number(text: str) -> str:
    if not text or text == '--':
        return text

    entries_raw = re.findall(r'.*?\(Página\s+\d+\)', text)
    if not entries_raw:
        return text

    entries = [entry.strip().lstrip(',').strip() for entry in entries_raw]

    def get_page_num(entry):
        match = re.search(r'\(Página\s+(\d+)\)', entry)
        return int(match.group(1)) if match else float('inf')

    try:
        sorted_entries = sorted(entries, key=get_page_num)
        return ", ".join(sorted_entries)
    except (ValueError, TypeError):
        return text

async def ask_local_llm(contexto: str, prompt_usuario: str):
    if not LOCAL_LLM_URL:
        logging.error("LOCAL_LLM_URL não está configurado.")
        return None

    headers = {'Content-Type': 'application/json'}
    payload = {
        "model": "local-model",
        "messages": [
            {"role": "system", "content": f"Use o seguinte texto para responder à pergunta:\n\n{contexto}"},
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
    except Exception as e:
        logging.error(f'Erro ao comunicar com LLM Local: {e}')
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f'Detalhes: Status {e.response.status_code}, Resposta: {e.response.text}')
        return None

async def generate_summary(extracted_data: str, doc_id: str):
    if not extracted_data or not extracted_data.strip():
        return "[ERRO: DADOS EXTRAÍDOS VAZIOS OU INVÁLIDOS]"

    metadata_text, cronologia_text = limpar.dividir_em_antes_e_depois_do_resumo(extracted_data)
    
    tipo = _extract_metadata(metadata_text, "tipo do documento")
    leis = _sort_entries_by_page_number(_extract_metadata(metadata_text, "leis"))
    assinaturas = _sort_entries_by_page_number(_extract_metadata(metadata_text, "quem assinou"))

    cronologia_para_resumo_raw = cronologia_text.replace("resumo da página:", "", 1).strip()
    if cronologia_para_resumo_raw.endswith("}"):
        cronologia_para_resumo_raw = cronologia_para_resumo_raw[:-1].strip()

    cronologia_para_resumo = _sort_entries_by_page_number(cronologia_para_resumo_raw)

    resumo_narrativo = "[Nenhum resumo pôde ser gerado.]"
    if cronologia_para_resumo:
        resumo_narrativo = await ask_local_llm(cronologia_para_resumo, pergunta3)
        if not resumo_narrativo:
            resumo_narrativo = "[Falha ao gerar o resumo narrativo pelo LLM.]"

    markdown_final = f"""| item | detalhes |
|---|---|
| tipo do documento | {tipo} |
| Leis | {leis} |
| Assinaturas | {assinaturas} |
| Resumo | {resumo_narrativo} |
| Cronologia | {cronologia_para_resumo} |"""
    
    return markdown_final