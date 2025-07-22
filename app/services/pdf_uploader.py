# pdf_uploader.py

import os
import requests
from pathlib import Path
from dotenv import load_dotenv
import asyncio
import logging
import tempfile

# --- Importações da ReportLab ---
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
    Esta função agora será usada tanto para o PDF final quanto para os blocos temporários.
    """
    doc = SimpleDocTemplate(pdf_output_path,
                            leftMargin=15*mm, rightMargin=15*mm,
                            topMargin=15*mm, bottomMargin=15*mm)
    
    styles = getSampleStyleSheet()
    style = styles['Normal']
    style.fontName = FONT_FAMILY
    style.fontSize = 10
    style.leading = 12

    # O separador '---' define o fim de uma página lógica
    paginas_texto = texto_completo_extraido.split('---')
    
    flowables = []
    for i, texto_pagina in enumerate(paginas_texto):
        if not texto_pagina.strip():
            continue
        
        texto_formatado = texto_pagina.strip().replace('\n', '<br/>')
        p = Paragraph(texto_formatado, style)
        flowables.append(p)
        
        # Adiciona quebra de página física entre as páginas lógicas, exceto após a última
        if i < len(paginas_texto) - 1:
            flowables.append(PageBreak())

    try:
        doc.build(flowables)
        logger.info(f"PDF com ReportLab gerado em: {pdf_output_path}")
    except Exception as e:
        logger.error(f"Falha CRÍTICA ao salvar o PDF com ReportLab em {pdf_output_path}: {e}", exc_info=True)
        raise

# As configurações de API e Proxy permanecem as mesmas
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
    proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}:{PROXY_PORT}" if PROXY_USER and PROXY_PASS else f"http://{PROXY_HOST}:{PROXY_PORT}"
    proxies = {"http": proxy_url, "https": proxy_url}

def upload_pdf_file_sync(path_to_file_str: str):
    path_to_file = Path(path_to_file_str)
    api_keys_to_try = [k for k in [CHATPDF_API_KEY1, CHATPDF_API_KEY2, CHATPDF_API_KEY3] if k]
    if not api_keys_to_try:
        logger.error("Nenhuma chave de API do ChatPDF está configurada.")
        return None, None
    
    for key_name, key_value in enumerate(api_keys_to_try):
        current_headers = {'x-api-key': key_value}
        try:
            with open(path_to_file, 'rb') as f:
                files_payload = [('file', (path_to_file.name, f, 'application/octet-stream'))]
                response = requests.post(CHATPDF_UPLOAD_URL, headers=current_headers, files=files_payload, proxies=proxies, timeout=REQUESTS_TIMEOUT)
                response.raise_for_status()
                data = response.json()
                source_id = data.get('sourceId')
                if source_id:
                    logger.info(f"✅ Upload bem-sucedido para ChatPDF: {path_to_file.name} → ID: {source_id}")
                    return source_id, key_value
        except Exception as e:
            logger.warning(f"Falha no upload com chave {key_name+1}: {e}")
    
    logger.error(f"❌ Todas as tentativas de upload para {path_to_file.name} falharam.")
    return None, None

# ===== NOVA FUNÇÃO PRINCIPAL =====
async def processar_e_enviar_texto_em_blocos(
    texto_completo: str, 
    codigo_processamento: str,
    paginas_logicas_por_bloco: int = 10,
    delay_segundos_entre_uploads: int = 1
) -> tuple[list[str], list[str | None]]:
    """
    Divide o texto extraído com base nas marcações '### Página', gera um PDF para cada bloco
    de texto e faz o upload para o ChatPDF.
    """
    # 1. Divide o texto completo em páginas lógicas usando o separador '---'
    paginas_logicas = texto_completo.split('---')
    paginas_logicas = [p for p in paginas_logicas if p.strip()] # Remove páginas vazias

    if not paginas_logicas:
        logger.warning("Nenhuma página lógica encontrada no texto extraído.")
        return [], []

    source_ids = []
    keys_usadas_para_sources = []
    
    # Cria um diretório temporário para os PDFs dos blocos
    with tempfile.TemporaryDirectory(prefix=f"pdf_parts_{codigo_processamento}_") as temp_dir:
        num_part = 0
        # 2. Agrupa as páginas lógicas em blocos de 'paginas_logicas_por_bloco'
        for i in range(0, len(paginas_logicas), paginas_logicas_por_bloco):
            num_part += 1
            bloco_de_paginas = paginas_logicas[i : i + paginas_logicas_por_bloco]
            
            # 3. Junta o texto do bloco novamente com o separador
            texto_do_bloco = "---".join(bloco_de_paginas)
            
            # 4. Gera um PDF temporário para este bloco
            caminho_pdf_bloco = os.path.join(temp_dir, f"bloco_{num_part}.pdf")
            logger.info(f"Gerando PDF para o bloco {num_part}...")
            gerar_pdf_marcado_com_reportlab(texto_do_bloco, caminho_pdf_bloco)
            
            # 5. Faz o upload do PDF do bloco
            source_id, key_usada = upload_pdf_file_sync(caminho_pdf_bloco)
            if source_id:
                source_ids.append(source_id)
                keys_usadas_para_sources.append(key_usada)
            
            # O arquivo PDF do bloco é automaticamente removido quando o `TemporaryDirectory` é fechado
            
            if delay_segundos_entre_uploads > 0 and (i + paginas_logicas_por_bloco) < len(paginas_logicas):
                await asyncio.sleep(delay_segundos_entre_uploads)
            
    return source_ids, keys_usadas_para_sources