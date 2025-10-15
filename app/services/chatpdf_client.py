#chatpdf_client.py

import httpx
import os
from pathlib import Path
from dotenv import load_dotenv
from httpx import Proxy
import asyncio

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

async def ask_chatpdf(source_id: str, question: str, chatpdf_api_key: str, retries: int = 3, backoff_factor: float = 0.5):
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

    timeout_config = httpx.Timeout(15.0, read=60.0) #

    last_exception = None

    async with httpx.AsyncClient(transport=transport, timeout=timeout_config) as client:
        for attempt in range(retries):
            try:
                response = await client.post(CHATPDF_MESSAGE_URL, headers=headers, json=data) #
                response.raise_for_status() #
                return response.json()['content'] #
            except httpx.HTTPStatusError as e:
                last_exception = e
                # Retry only on 5xx server errors
                if 500 <= e.response.status_code < 600:
                    wait_time = backoff_factor * (2 ** attempt)
                    print(f"ChatPDF request failed with {e.response.status_code}. Retrying in {wait_time:.2f} seconds... (Attempt {attempt + 1}/{retries})")
                    await asyncio.sleep(wait_time)
                else:
                    # Don't retry for 4xx client errors (e.g., bad request, auth error)
                    raise
            except httpx.ReadTimeout as e: #
                last_exception = e
                wait_time = backoff_factor * (2 ** attempt)
                print(f"ChatPDF request timed out. Retrying in {wait_time:.2f} seconds... (Attempt {attempt + 1}/{retries})")
                await asyncio.sleep(wait_time)
            except Exception as e: # Generic catch for other network issues perhaps, then re-raise
                last_exception = e
                raise # Or handle more specifically if needed

        if last_exception: # If all retries failed
            raise last_exception

async def process_pdf(source_id: str, num_blocos_qa, chatpdf_api_key: str, prompt_text: str, file_path: Path = None):
    
    delay_segundos_qa = 0  # Delay base
    if num_blocos_qa >= 5:
        additional_delay = min(5, (num_blocos_qa - 4) * 1)
        delay_segundos_qa += additional_delay

    summary = await ask_chatpdf(source_id, prompt_text, chatpdf_api_key)
    await asyncio.sleep(delay_segundos_qa)

    return source_id, summary