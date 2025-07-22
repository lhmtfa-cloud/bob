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
    """Extrai o valor de um campo de metadados do texto."""
    pattern = re.compile(rf"^\s*{re.escape(field)}:\s*(.*)", re.IGNORECASE | re.MULTILINE)
    match = pattern.search(text)
    if match:
        # Retorna o valor removendo espaços extras e quebras de linha.
        return match.group(1).strip()
    return "--"


async def ask_local_llm(contexto: str, prompt_usuario: str):
    """Envia uma requisição para o LLM local."""
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
    except (httpx.RequestError, httpx.HTTPStatusError) as e:
        logging.error(f'Erro ao comunicar com LLM Local: {e}')
        if hasattr(e, 'response') and e.response is not None:
            logging.error(f'Detalhes: Status {e.response.status_code}, Resposta: {e.response.text}')
        return None
    except (KeyError, IndexError) as e:
        logging.error(f'Erro ao processar resposta do LLM: {e}')
        return None


async def generate_summary(extracted_data: str, doc_id: str):
    """
    Gera um resumo narrativo da cronologia e monta o markdown final.
    """
    if not extracted_data or not extracted_data.strip():
        return "[ERRO: DADOS EXTRAÍDOS VAZIOS OU INVÁLIDOS]"

    # 1. Divide o texto em metadados (antes) e cronologia (depois)
    metadata_text, cronologia_text = limpar.dividir_em_antes_e_depois_do_resumo(extracted_data)
    
    # 2. Extrai os campos de metadados diretamente do texto
    tipo = _extract_metadata(metadata_text, "tipo do documento")
    leis = _extract_metadata(metadata_text, "leis")
    assinaturas = _extract_metadata(metadata_text, "quem assinou")

    # 3. Limpa e prepara a cronologia vinda do ChatPDF
    cronologia_para_resumo = cronologia_text.replace("resumo da página:", "", 1).strip()
    # Remove o "}" final, se houver
    if cronologia_para_resumo.endswith("}"):
        cronologia_para_resumo = cronologia_para_resumo[:-1].strip()

    # 4. Gera o resumo narrativo usando o LLM
    resumo_narrativo = "[Nenhum resumo pôde ser gerado.]"
    if cronologia_para_resumo:
        resumo_narrativo = await ask_local_llm(cronologia_para_resumo, pergunta3)
        if not resumo_narrativo:
            resumo_narrativo = "[Falha ao gerar o resumo narrativo pelo LLM.]"

    # 5. Monta o Markdown final com os dados
    markdown_final = f"""| item | detalhes |
|---|---|
| tipo do documento | {tipo} |
| Leis | {leis} |
| Assinaturas | {assinaturas} |
| Resumo | {resumo_narrativo} |
| Cronologia | {cronologia_para_resumo} |"""
    
    return markdown_final