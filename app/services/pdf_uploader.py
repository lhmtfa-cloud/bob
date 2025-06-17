import os
import requests
from pathlib import Path
from dotenv import load_dotenv
from PyPDF2 import PdfReader, PdfWriter 
import asyncio 
import logging
from fpdf import FPDF
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
from app.services import limpar

def forcar_quebra_em_palavras_largas(texto: str, max_largura: int = 80) -> str:
    palavras = texto.split(" ")
    resultado = []
    for palavra in palavras:
        if len(palavra) > max_largura:
            partes = [palavra[i:i+max_largura] for i in range(0, len(palavra), max_largura)]
            resultado.extend(partes)
        else:
            resultado.append(palavra)
    return " ".join(resultado)
def gerar_pdf_com_marcacoes(pdf_input_path: str, pdf_output_path: str, formato_marcador: str = "### Página {}"):
    reader = PdfReader(pdf_input_path)
    total_paginas = len(reader.pages)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    for i in range(total_paginas):
        texto_pagina_original = reader.pages[i].extract_text()
        if texto_pagina_original is None or texto_pagina_original.strip() == "":
            texto_pagina_original = "[Página sem conteúdo textual visível ou extração resultou em vazio]"
        else:
            texto_pagina_original = texto_pagina_original.strip()
        pdf.add_page()
        pdf.set_font("Arial", "B", 12) 
        marcador_texto = formato_marcador.format(i + 1)
        marcador_limpo = limpar.limpar_texto_para_pdf(marcador_texto)
        try:
            pdf.multi_cell(0, 10, marcador_limpo, align='L') 
        except Exception as e:
            logger.error(f"Erro ao renderizar MARCADOR '{marcador_limpo}' na pág. {i+1} do PDF: {repr(e)}")
            pdf.set_text_color(255, 0, 0)
            pdf.multi_cell(0, 10, f"[ERRO NO MARCADOR DA PAGINA {i+1}]")
            pdf.set_text_color(0, 0, 0)
        pdf.ln(4) 
        pdf.set_font("Arial", "", 11) 
        linhas_do_texto_original = texto_pagina_original.split('\n')
        for idx_linha, linha_original in enumerate(linhas_do_texto_original):
            linha_limpa = limpar.limpar_texto_para_pdf(linha_original)
            if not linha_limpa.strip():
                pdf.ln(3)
                continue
            linha_processada = forcar_quebra_em_palavras_largas(linha_limpa, max_largura=85) 
            try:
                pdf.multi_cell(0, 8, linha_processada)
            except Exception as e:
                logger.error(f"Erro ao renderizar LINHA {idx_linha + 1} (pág. {i+1}) no PDF: {repr(e)}\nConteúdo problemático (limpo e quebrado): {linha_processada[:150]}...")
                try:
                    pdf.set_font("Arial", "I", 9) 
                    pdf.set_text_color(255, 0, 0) 
                    pdf.multi_cell(0, 6, f"[AVISO: Erro ao renderizar a linha anterior. Conteúdo original (parte): {linha_original[:100]}...]")
                    pdf.set_text_color(0, 0, 0) 
                    pdf.set_font("Arial", "", 11) 
                except:
                    logger.error(f"Falha crítica ao tentar adicionar aviso de erro de linha no PDF (pág. {i+1}).")
    try:
        pdf.output(pdf_output_path)
        logger.info(f"PDF com marcações (revisado) gerado em: {pdf_output_path}")
    except Exception as e:
        logger.error(f"Falha CRÍTICA ao salvar o PDF final em {pdf_output_path}: {e}", exc_info=True)
        raise 
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
async def processar_pdf_em_partes_e_enviar_path(
    pdf_path_str: str, 
    delay_segundos_entre_uploads: int = 1  
) -> tuple[list[str], list[str | None]]: 
    logger.info(f"Iniciando processo completo com marcações para: {pdf_path_str}")
    temp_file_path = Path(pdf_path_str)
    if not temp_file_path.exists():
        logger.error(f"O arquivo {temp_file_path} não existe.")
        return [], [] 
    split_dir = Path("./data/split_pdfs")
    marcados_dir = Path("./data/marcados_com_tags")
    split_dir.mkdir(parents=True, exist_ok=True)
    marcados_dir.mkdir(parents=True, exist_ok=True)
    partes_paths_str = dividir_pdf_em_blocos_sync(str(temp_file_path), str(split_dir), paginas_por_bloco=10)
    if not partes_paths_str:
        logger.error("Nenhuma parte foi gerada.")
        return [], [] 
    source_ids = []
    keys_usadas_para_sources = [] 
    num_total_partes = len(partes_paths_str)
    for i, parte_path_str in enumerate(partes_paths_str):
        parte_path = Path(parte_path_str)
        try:
            logger.info(f"Processando parte {i+1}/{num_total_partes}: {parte_path.name}")
            logger.info(f"Iniciando upload para parte {i+1}/{num_total_partes}: {parte_path.name}")
            source_id, key_usada = upload_pdf_file_sync(str(parte_path)) 

            if source_id:
                source_ids.append(source_id)
                keys_usadas_para_sources.append(key_usada)
                logger.info(f"Upload da parte {i+1}/{num_total_partes} bem-sucedido. Source ID: {source_id}")
            else:
                logger.warning(f"Upload da parte {i+1}/{num_total_partes} falhou ou não retornou Source ID.")

        except Exception as e:
            logger.error(f"Erro ao processar/upload da parte {parte_path.name} (parte {i+1}/{num_total_partes}): {e}", exc_info=True)
        finally:
            if delay_segundos_entre_uploads > 0 and i < num_total_partes - 1:
                logger.info(f"Aguardando {delay_segundos_entre_uploads}s antes do próximo upload...")
                await asyncio.sleep(delay_segundos_entre_uploads)
    logger.info(f"Processo de upload de todas as partes concluído. Total Source IDs obtidos: {len(source_ids)}.")
    return source_ids, keys_usadas_para_sources