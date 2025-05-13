import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from PyPDF2 import PdfReader, PdfWriter
from fastapi import UploadFile
import asyncio # Importado para asyncio.to_thread
import logging # Importado para logging

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Carregar variáveis de ambiente
load_dotenv()

CHATPDF_API_KEY = os.getenv('CHATPDF_API_KEY')
PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_HOST = os.getenv('PROXY_HOST')
PROXY_PORT = os.getenv('PROXY_PORT')

CHATPDF_UPLOAD_URL = 'https://api.chatpdf.com/v1/sources/add-file'
REQUESTS_TIMEOUT = 30 # Adicionado timeout padrão para requests (em segundos)

# Configurar proxy (se necessário)
proxies = None
if PROXY_HOST and PROXY_PORT: # Apenas configura proxy se host e porta estiverem definidos
    if PROXY_USER and PROXY_PASS:
        proxies = {
            "http": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}",
            "https": f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}"
        }
        logger.info("Proxy configurado com autenticação.")
    else:
        proxies = {
            "http": f"http://{PROXY_HOST}:{PROXY_PORT}",
            "https": f"http://{PROXY_HOST}:{PROXY_PORT}"
        }
        logger.info("Proxy configurado sem autenticação.")
else:
    logger.info("Nenhuma configuração de proxy encontrada ou incompleta. Operando sem proxy.")


def dividir_pdf_em_blocos_sync(pdf_path_str: str, output_dir_str: str, paginas_por_bloco: int = 10):
    """
    Função síncrona para dividir PDF. Renomeada para _sync para clareza.
    Recebe caminhos como strings, pois Path objects podem não ser seguros entre threads sem cuidado.
    """
    logger.info(f"Iniciando divisão do PDF: {pdf_path_str}")
    pdf_path = Path(pdf_path_str)
    output_dir = Path(output_dir_str)
    output_dir.mkdir(parents=True, exist_ok=True)

    partes_paths_str = []
    try:
        reader = PdfReader(pdf_path_str) # PyPDF2 pode aceitar string diretamente
        total_paginas = len(reader.pages)
        logger.info(f"Total de páginas no PDF: {total_paginas}")
        num_blocos = (total_paginas + paginas_por_bloco - 1) // paginas_por_bloco

        for i in range(num_blocos):
            logger.info(f"Processando bloco {i+1}/{num_blocos}")
            writer = PdfWriter()
            inicio = i * paginas_por_bloco
            fim = min(inicio + paginas_por_bloco, total_paginas)

            for j in range(inicio, fim):
                writer.add_page(reader.pages[j])

            output_file_path = output_dir / f"{pdf_path.stem}_parte_{i+1}.pdf"
            with output_file_path.open("wb") as f_out:
                writer.write(f_out)
            partes_paths_str.append(str(output_file_path))
            logger.info(f"Bloco {i+1} salvo em: {output_file_path}")

    except Exception as e:
        logger.error(f"Erro ao dividir o PDF {pdf_path_str}: {e}", exc_info=True)
        raise # Re-levanta a exceção para ser tratada no chamador
    
    logger.info(f"PDF dividido em {len(partes_paths_str)} partes.")
    return partes_paths_str

def upload_pdf_file_sync(path_to_file_str: str):
    """
    Função síncrona para fazer upload do arquivo PDF. Renomeada para _sync.
    Recebe caminho como string.
    """
    path_to_file = Path(path_to_file_str)
    logger.info(f"Iniciando upload do arquivo: {path_to_file.name}")
    files = [
        ('file', (path_to_file.name, open(path_to_file, 'rb'), 'application/octet-stream'))
    ]
    headers = {
        'x-api-key': CHATPDF_API_KEY
    }

    try:
        response = requests.post(
            CHATPDF_UPLOAD_URL,
            headers=headers,
            files=files,
            proxies=proxies,
            timeout=REQUESTS_TIMEOUT # Adicionado timeout
        )
        response.raise_for_status() # Levanta exceção para erros HTTP 4xx/5xx
    except requests.exceptions.Timeout:
        logger.error(f"Timeout ao fazer upload do PDF {path_to_file.name} para ChatPDF.")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Erro de requisição ao fazer upload do PDF {path_to_file.name} para ChatPDF: {e}")
        return None
    finally:
        # Fecha o arquivo aberto em 'files'
        # O 'files' é uma lista de tuplas, e o segundo elemento da tupla é o file object
        if files and hasattr(files[0][1][1], 'close'):
            files[0][1][1].close()


    if response.status_code == 200:
        data = response.json()
        source_id = data.get('sourceId')
        if source_id:
            logger.info(f"✅ Upload bem-sucedido: {path_to_file.name} → ID: {source_id}")
            return source_id
        else:
            logger.error(f"❌ Falha no upload (sourceId ausente na resposta) de {path_to_file.name}: {response.status_code} {response.text}")
            return None
    else:
        # Este else pode não ser alcançado se raise_for_status() funcionar como esperado
        logger.error(f"❌ Falha no upload de {path_to_file.name}: {response.status_code} {response.text}")
        return None


async def processar_pdf_em_partes_e_enviar_path(file_path_str: str) -> list[str]:
    logger.info(f"Iniciando processamento assíncrono para o arquivo salvo: {file_path_str}")

    temp_file_path = Path(file_path_str)
    if not temp_file_path.exists():
        logger.error(f"O arquivo {temp_file_path} não existe.")
        return []

    # Define diretório de saída para as partes do PDF
    output_dir_split = Path("./data/split_pdfs")
    output_dir_split.mkdir(parents=True, exist_ok=True)

    paginas_por_bloco = 10
    partes_paths_str = []

    try:
        logger.info(f"Dividindo PDF {temp_file_path} em blocos de {paginas_por_bloco} páginas.")
        partes_paths_str = await asyncio.to_thread(
            dividir_pdf_em_blocos_sync, str(temp_file_path), str(output_dir_split), paginas_por_bloco
        )
    except Exception as e:
        logger.error(f"Erro ao dividir o PDF: {e}", exc_info=True)
        return []

    if not partes_paths_str:
        logger.warning("Nenhuma parte do PDF foi gerada.")
        return []

    source_ids = []
    upload_tasks = []

    for parte_path_str in partes_paths_str:
        logger.info(f"Agendando upload do arquivo {parte_path_str} em thread separada.")
        upload_tasks.append(
            asyncio.to_thread(upload_pdf_file_sync, parte_path_str)
        )

    try:
        results = await asyncio.gather(*upload_tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Erro durante upload: {result}", exc_info=True)
            elif result:
                source_ids.append(result)
    except Exception as e:
        logger.error(f"Erro ao executar uploads: {e}", exc_info=True)

    # Limpeza dos arquivos (original e partes)
    logger.info("Iniciando limpeza dos arquivos temporários.")
    try:
        if temp_file_path.exists():
            temp_file_path.unlink()
            logger.info(f"Arquivo original removido: {temp_file_path}")
        for parte_path_str in partes_paths_str:
            parte_path = Path(parte_path_str)
            if parte_path.exists():
                parte_path.unlink()
                logger.info(f"Parte removida: {parte_path}")
        logger.info("Limpeza concluída.")
    except Exception as e:
        logger.error(f"Erro durante a limpeza: {e}", exc_info=True)

    logger.info(f"Processamento finalizado. Source IDs: {source_ids}")
    return source_ids

