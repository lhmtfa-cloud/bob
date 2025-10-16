# pdf_uploader.py

import os
import requests
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import logging
import tempfile
import math

# --- Importações da ReportLab ---
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- CONSTANTE GLOBAL PARA TAMANHO DO BLOCO ---
PAGINAS_POR_BLOCO = 10

# --- Configuração de Fontes ---
try:
    arial_path = 'arial.ttf'
    if not os.path.exists(arial_path) and os.name == 'nt':
        arial_path = 'C:/Windows/Fonts/arial.ttf'
    
    if os.path.exists(arial_path):
        pdfmetrics.registerFont(TTFont('Arial', arial_path))
        FONT_FAMILY = 'Arial'
    else:
        print("Alerta: Fonte Arial não encontrada. Usando Helvetica como fallback.")
        FONT_FAMILY = 'Helvetica'
except Exception as e:
    print(f"Alerta ao registrar fonte: {e}. Usando Helvetica como fallback.")
    FONT_FAMILY = 'Helvetica'


def gerar_pdf_marcado_com_reportlab(texto_completo_extraido: str, pdf_output_path: str):
    """
    Cria um PDF de alta fidelidade a partir do texto extraído, usando ReportLab.
    """
    doc = SimpleDocTemplate(pdf_output_path,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    
    styles = getSampleStyleSheet()
    style = styles['Normal']
    style.fontName = FONT_FAMILY
    style.fontSize = 6
    style.leading = 10

    paginas_texto = texto_completo_extraido.split('---')
    
    flowables = []
    for i, texto_pagina in enumerate(paginas_texto):
        if not texto_pagina.strip():
            continue
        
        texto_formatado = texto_pagina.strip().replace('\n', '<br/>')
        p = Paragraph(texto_formatado, style)
        flowables.append(p)
        
        if i < len(paginas_texto) - 1:
            flowables.append(PageBreak())

    try:
        doc.build(flowables)
        logger.info(f"PDF com ReportLab gerado em: {pdf_output_path}")
    except Exception as e:
        logger.error(f"Falha CRÍTICA ao salvar o PDF com ReportLab em {pdf_output_path}: {e}", exc_info=True)
        raise

load_dotenv()
CHATPDF_API_KEY1 = os.getenv('CHATPDF_API_KEY1')
CHATPDF_API_KEY2 = os.getenv('CHATPDF_API_KEY2')
CHATPDF_API_KEY3 = os.getenv('CHATPDF_API_KEY3')
PROXY_USER = os.getenv('PROXY_USER')
PROXY_PASS = os.getenv('PROXY_PASS')
PROXY_HOST = os.getenv('PROXY_HOST')
PROXY_PORT = os.getenv('PROXY_PORT')
CHATPDF_UPLOAD_URL = 'https://api.chatpdf.com/v1/sources/add-file'
REQUESTS_TIMEOUT = 15
proxies = None
if PROXY_HOST and PROXY_PORT:
    proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}" if PROXY_USER and PROXY_PASS else f"http://{PROXY_HOST}:{PROXY_PORT}"
    proxies = {"http": proxy_url, "https": proxy_url}

# --- FUNÇÃO MODIFICADA ---
def upload_pdf_file_sync(path_to_file_str: str, user_api_key: str | None = None):
    """
    Função de upload modificada para priorizar a chave do usuário e registrar as tentativas.
    """
    path_to_file = Path(path_to_file_str)
    
    # --- INÍCIO DA LÓGICA DE SELEÇÃO DE CHAVE API ---
    api_keys_to_try = []
    key_sources = [] # Para ajudar no logging

    # 1. Adiciona a chave do usuário como prioridade, se existir
    if user_api_key:
        api_keys_to_try.append(user_api_key)
        key_sources.append("Chave do Usuário")

    # 2. Adiciona as chaves globais, evitando duplicatas
    global_keys = [
        ("Chave Global 1", CHATPDF_API_KEY1),
        ("Chave Global 2", CHATPDF_API_KEY2),
        ("Chave Global 3", CHATPDF_API_KEY3)
    ]
    for name, key in global_keys:
        if key and key not in api_keys_to_try:
            api_keys_to_try.append(key)
            key_sources.append(name)

    if not api_keys_to_try:
        logger.error("Nenhuma chave de API (nem de usuário, nem global) está configurada.")
        return None, None
    # --- FIM DA LÓGICA DE SELEÇÃO DE CHAVE API ---
    
    for i, key_value in enumerate(api_keys_to_try):
        key_name_for_log = key_sources[i]
        logger.info(f"Tentando upload de '{path_to_file.name}' com a '{key_name_for_log}'...")

        current_headers = {'x-api-key': key_value}
        try:
            with open(path_to_file, 'rb') as f:
                files_payload = [('file', (path_to_file.name, f, 'application/octet-stream'))]
                response = requests.post(CHATPDF_UPLOAD_URL, headers=current_headers, files=files_payload, proxies=proxies, timeout=REQUESTS_TIMEOUT)
                response.raise_for_status()
                data = response.json()
                source_id = data.get('sourceId')
                if source_id:
                    logger.info(f"✅ Upload bem-sucedido com a '{key_name_for_log}': {path_to_file.name} → ID: {source_id}")
                    return source_id, key_value
        except Exception as e:
            logger.warning(f"Falha no upload com a '{key_name_for_log}': {e}")
    
    logger.error(f"❌ Todas as tentativas de upload para {path_to_file.name} falharam.")
    return None, None
async def processar_e_enviar_texto_em_blocos(
    texto_completo: str, 
    codigo_processamento: str,
    user_api_key: str | None = None # Novo parâmetro para a chave do usuário
) -> tuple[list[str], list[str | None]]:
    """
    Divide o texto, gera PDFs e faz o upload, agora com delay dinâmico e
    suporte para chave de API do usuário.
    """
    paginas_logicas_brutas = texto_completo.split('---')
    paginas_logicas = [p for p in paginas_logicas_brutas if p.strip()]

    # --- LINHA DE LOG ADICIONADA ---
    logger.info(f"[{codigo_processamento}] Texto extraído resultou em {len(paginas_logicas)} páginas com conteúdo (de um total de {len(paginas_logicas_brutas)} páginas brutas).")

    if not paginas_logicas:
        logger.warning("Nenhuma página lógica encontrada no texto extraído.")
        return [], []

    num_blocos = math.ceil(len(paginas_logicas) / PAGINAS_POR_BLOCO)


    source_ids = []
    keys_usadas_para_sources = []
    
    with tempfile.TemporaryDirectory(prefix=f"pdf_parts_{codigo_processamento}_") as temp_dir:
        num_part = 0
        for i in range(0, len(paginas_logicas), PAGINAS_POR_BLOCO):
            num_part += 1
            bloco_de_paginas = paginas_logicas[i : i + PAGINAS_POR_BLOCO]
            
            texto_do_bloco = "---".join(bloco_de_paginas)
            
            caminho_pdf_bloco = os.path.join(temp_dir, f"bloco_{num_part}.pdf")
            logger.info(f"Gerando PDF para o bloco {num_part}/{num_blocos}...")
            gerar_pdf_marcado_com_reportlab(texto_do_bloco, caminho_pdf_bloco)
            
            # Passa a chave do usuário para a função de upload
            source_id, key_usada = upload_pdf_file_sync(caminho_pdf_bloco, user_api_key)
            if source_id:
                source_ids.append(source_id)
                keys_usadas_para_sources.append(key_usada)
            

            
    return source_ids, keys_usadas_para_sources