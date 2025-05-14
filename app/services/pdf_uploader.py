import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from PyPDF2 import PdfReader, PdfWriter
# fastapi.UploadFile não é mais necessário diretamente nesta função combinada se passamos o path
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

CHATPDF_API_KEY1 = os.getenv('CHATPDF_API_KEY1')
CHATPDF_API_KEY2 = os.getenv('CHATPDF_API_KEY2')
CHATPDF_API_KEY3 = os.getenv('CHATPDF_API_KEY3')
PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_HOST = os.getenv('PROXY_HOST')
PROXY_PORT = os.getenv('PROXY_PORT')

CHATPDF_UPLOAD_URL = 'https://api.chatpdf.com/v1/sources/add-file'
REQUESTS_TIMEOUT = 30

proxies = None
if PROXY_HOST and PROXY_PORT:
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
    logger.info(f"Iniciando divisão do PDF: {pdf_path_str}")
    pdf_path = Path(pdf_path_str)
    output_dir = Path(output_dir_str)
    output_dir.mkdir(parents=True, exist_ok=True)

    partes_paths_str = []
    try:
        reader = PdfReader(pdf_path_str)
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
        raise
    
    logger.info(f"PDF dividido em {len(partes_paths_str)} partes.")
    return partes_paths_str

def upload_pdf_file_sync(path_to_file_str: str):
    path_to_file = Path(path_to_file_str)
    logger.info(f"Iniciando upload do arquivo: {path_to_file.name} para ChatPDF")

    api_keys_to_try = []
    if CHATPDF_API_KEY1: api_keys_to_try.append(("CHATPDF_API_KEY1", CHATPDF_API_KEY1))
    if CHATPDF_API_KEY2: api_keys_to_try.append(("CHATPDF_API_KEY2", CHATPDF_API_KEY2))
    if CHATPDF_API_KEY3: api_keys_to_try.append(("CHATPDF_API_KEY3", CHATPDF_API_KEY3))
    
    if not api_keys_to_try:
        logger.error("Nenhuma chave de API do ChatPDF está configurada.")
        return None, None

    final_response = None
    request_succeeded = False
    successful_key_value = None

    for key_name, key_value in api_keys_to_try:
        logger.info(f"Tentando upload com {key_name} para {path_to_file.name}...")
        current_headers = {'x-api-key': key_value}
        
        file_object_for_upload = None
        try:
            file_object_for_upload = open(path_to_file, 'rb')
            files_payload = [
                ('file', (path_to_file.name, file_object_for_upload, 'application/octet-stream'))
            ]

            response_attempt = requests.post(
                CHATPDF_UPLOAD_URL,
                headers=current_headers,
                files=files_payload,
                proxies=proxies,
                timeout=REQUESTS_TIMEOUT
            )
            response_attempt.raise_for_status()  
            
            logger.info(f"Sucesso na tentativa com {key_name} para {path_to_file.name}.")
            final_response = response_attempt
            request_succeeded = True
            successful_key_value = key_value 
            break 

        except requests.exceptions.HTTPError as http_err:
            error_text_preview = http_err.response.text[:200] if hasattr(http_err.response, 'text') else "Sem detalhes de texto."
            logger.warning(f"Erro HTTP com {key_name} para {path_to_file.name}: Status {http_err.response.status_code}. Detalhes: {error_text_preview}")
            if http_err.response.status_code in [401, 403]:
                logger.info(f"{key_name} inválida/não autorizada. Tentando próxima...")
        except requests.exceptions.Timeout:
            logger.error(f"Timeout na tentativa com {key_name} para {path_to_file.name}.")
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Erro de requisição com {key_name} para {path_to_file.name}: {req_err}")
        except IOError as io_err:
            logger.error(f"Erro de I/O ao abrir/ler o arquivo {path_to_file.name} para tentativa com {key_name}: {io_err}")
            break 
        finally:
            if file_object_for_upload:
                file_object_for_upload.close()

    if request_succeeded and final_response:
        try:
            data = final_response.json()
            source_id = data.get('sourceId')
            if source_id:
                logger.info(f"✅ Upload bem-sucedido para ChatPDF: {path_to_file.name} → ID: {source_id} (usando chave que termina em ...{successful_key_value[-4:] if successful_key_value else 'N/A'})")
                return source_id, successful_key_value
            else:
                logger.error(f"❌ Falha no upload (sourceId ausente na resposta) de {path_to_file.name}: {final_response.status_code} {final_response.text[:200]}")
                return None, None
        except ValueError: 
            logger.error(f"❌ Falha ao decodificar JSON da resposta para {path_to_file.name}: {final_response.text[:200]}")
            return None, None
    else:
        logger.error(f"❌ Todas as tentativas de upload para {path_to_file.name} falharam.")
        return None, None

async def processar_pdf_em_partes_e_enviar_path(file_path_str: str) -> tuple[list[str], list[str]]:
    logger.info(f"Iniciando processamento assíncrono para o arquivo salvo: {file_path_str}")

    temp_file_path = Path(file_path_str)
    if not temp_file_path.exists():
        logger.error(f"O arquivo {temp_file_path} não existe.")
        return [], []

    output_dir_split = Path("./data/split_pdfs") 
    output_dir_split.mkdir(parents=True, exist_ok=True)

    paginas_por_bloco = 10
    partes_paths_str = []

    try:
        logger.info(f"Agendando divisão do PDF {temp_file_path} em thread separada.")
        partes_paths_str = await asyncio.to_thread(
            dividir_pdf_em_blocos_sync, str(temp_file_path), str(output_dir_split), paginas_por_bloco
        )
    except Exception as e:
        logger.error(f"Falha ao dividir o PDF no thread executor: {e}", exc_info=True)
        return [], []

    if not partes_paths_str:
        logger.warning("Nenhuma parte do PDF foi gerada.")
        return [], []

    final_source_ids = []
    final_keys_used = []
    
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
                logger.error(f"Erro durante um upload no asyncio.gather: {result}", exc_info=result)
            elif result: 
                source_id, key_used = result
                if source_id and key_used:
                    final_source_ids.append(source_id)
                    final_keys_used.append(key_used)
                elif source_id and not key_used:
                    logger.warning(f"Upload bem-sucedido para source_id {source_id} mas nenhuma chave foi registrada.")
                    final_source_ids.append(source_id)
    except Exception as e:
        logger.error(f"Erro ao executar uploads em paralelo com asyncio.gather: {e}", exc_info=True)

    logger.info("Iniciando limpeza dos arquivos temporários das partes divididas.")
    try:
        for parte_path_str in partes_paths_str:
            parte_path_obj = Path(parte_path_str)
            if parte_path_obj.exists():
                try: parte_path_obj.unlink()
                except OSError as ose: logger.error(f"Erro ao remover parte {parte_path_obj}: {ose}")
                else: logger.info(f"Parte do PDF {parte_path_obj} removida.")
        logger.info("Limpeza de arquivos das partes divididas concluída.")
    except Exception as e:
        logger.error(f"Erro durante a limpeza dos arquivos das partes divididas: {e}", exc_info=True)

    logger.info(f"Processamento concluído. Source IDs obtidos: {final_source_ids}, Chaves usadas: {len(final_keys_used)} (detalhes nos logs)")
    return final_source_ids, final_keys_used