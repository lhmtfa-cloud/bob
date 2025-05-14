import requests
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_HOST = os.getenv('PROXY_HOST')
PROXY_PORT = os.getenv('PROXY_PORT')

CHATPDF_MESSAGE_URL = 'https://api.chatpdf.com/v1/chats/message'

proxies = None
if PROXY_HOST and PROXY_PORT:
    if PROXY_USER and PROXY_PASS:
        proxies = {
            "http": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
            "https": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        }
    else:
        proxies = {
            "http": f"http://{PROXY_HOST}:{PROXY_PORT}",
            "https": f"http://{PROXY_HOST}:{PROXY_PORT}"
        }

def ask_chatpdf(source_id: str, question: str, chatpdf_api_key: str):
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

    response = requests.post(CHATPDF_MESSAGE_URL, headers=headers, json=data, proxies=proxies)
    response.raise_for_status()
    return response.json()['content']

def process_pdf(source_id: str, chatpdf_api_key: str, prompt_text: str, file_path: Path = None):
    # file_path é opcional aqui, pode ser usado para logs se necessário, mas não para a API call.
    summary = ask_chatpdf(source_id, prompt_text, chatpdf_api_key)
    return source_id, summary
