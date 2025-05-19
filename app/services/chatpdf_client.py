import httpx
import os
from pathlib import Path
from dotenv import load_dotenv
from httpx import Proxy

load_dotenv()

PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_HOST = os.getenv('PROXY_HOST')
PROXY_PORT = os.getenv('PROXY_PORT')

CHATPDF_MESSAGE_URL = 'https://api.chatpdf.com/v1/chats/message'

def build_proxy_url():
    if PROXY_HOST and PROXY_PORT:
        if PROXY_USER and PROXY_PASS:
            return f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        else:
            return f"http://{PROXY_HOST}:{PROXY_PORT}"
    return None

async def ask_chatpdf(source_id: str, question: str, chatpdf_api_key: str):
    if not chatpdf_api_key:
        raise ValueError("CHATPDF_API_KEY é necessária para ask_chatpdf.")

    headers = {
        'x-api-key': chatpdf_api_key,
        'Content-Type': 'application/json'
    }
    data = {
        'sourceId': source_id,
        'messages': [{'role': 'user', 'content': question}]
    }

    proxy_url_str = build_proxy_url()
    transport = None

    if proxy_url_str:
        proxy_obj = Proxy(url=proxy_url_str)
        transport = httpx.AsyncHTTPTransport(proxy=proxy_obj)

    timeout_config = httpx.Timeout(15.0, read=60.0)

    async with httpx.AsyncClient(transport=transport, timeout=timeout_config) as client:
        try:
            response = await client.post(CHATPDF_MESSAGE_URL, headers=headers, json=data)
            response.raise_for_status()
            return response.json()['content']
        except httpx.ReadTimeout:
            raise
        except httpx.HTTPStatusError as e:
            raise
        except Exception as e:
            raise

async def process_pdf(source_id: str, chatpdf_api_key: str, prompt_text: str, file_path: Path = None):
    summary = await ask_chatpdf(source_id, prompt_text, chatpdf_api_key)
    return source_id, summary