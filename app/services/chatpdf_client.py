import requests
import os
from pathlib import Path
from dotenv import load_dotenv
from app.prompts.chatPDF import pBase

load_dotenv()

# Caminhos e variáveis de ambiente
CHATPDF_API_KEY = os.getenv('CHATPDF_API_KEY')

PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_HOST = os.getenv('PROXY_HOST')
PROXY_PORT = os.getenv('PROXY_PORT')

CHATPDF_UPLOAD_URL = 'https://api.chatpdf.com/v1/sources/add-file'
CHATPDF_MESSAGE_URL = 'https://api.chatpdf.com/v1/chats/message'

proxies = {
    "http": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
    "https": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
}



def ask_chatpdf(source_id: str, question: str):
    headers = {
        'x-api-key': CHATPDF_API_KEY,
        'Content-Type': 'application/json'
    }
    data = {
        'sourceId': source_id,
        'messages': [{'role': 'user', 'content': question}]
    }

    response = requests.post(CHATPDF_MESSAGE_URL, headers=headers, json=data, proxies=proxies)
    response.raise_for_status()
    return response.json()['content']

def process_pdf(file_path: Path, source_id):
    prompt = str(pBase)
    summary = ask_chatpdf(source_id, prompt)

    
    return source_id, summary
