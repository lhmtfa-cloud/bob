import os
import requests
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
CHATPDF_API_KEY = os.getenv('CHATPDF_API_KEY')
PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_HOST = os.getenv('PROXY_HOST')
PROXY_PORT = os.getenv('PROXY_PORT')

CHATPDF_UPLOAD_URL = 'https://api.chatpdf.com/v1/sources/add-file'

# Configure proxy
proxies = {
    "http": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
    "https": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
}

async def upload_pdf(file):
    # Save uploaded file temporarily
    temp_dir = Path("./data/uploads")
    #print("___________________________________________________________________________________________________________________________________")
    #print(temp_dir)
    #print("___________________________________________________________________________________________________________________________________")
    temp_dir.mkdir(parents=True, exist_ok=True)
    temp_path = temp_dir / file.filename

    with temp_path.open("wb") as f:
        f.write(await file.read())

    files = [
        ('file', ('file', temp_path.open('rb'), 'application/octet-stream'))
    ]
    headers = {
        'x-api-key': CHATPDF_API_KEY
    }

    try:
        response = requests.post(CHATPDF_UPLOAD_URL, headers=headers, files=files, proxies=proxies)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"Erro ao fazer upload do PDF para ChatPDF: {e}")
        return None

    if response.status_code == 200:
        source_id = response.json()['sourceId']
        print('Uploaded PDF. Source ID:', source_id)
        return source_id
    else:
        print('Upload Failed:', response.status_code, response.text)
        return None