# routes.py

import os
import tempfile
import zipfile
import shutil
import json
import uuid
import asyncio
from pathlib import Path
from PyPDF2 import PdfReader

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from app.services import limpar
from app.services import pdf_uploader
from app.services import question_answering
from app.services import summarizer
from app.services.pdf_generator import PDFGenerator
from app.services.state_tracker import (
    set_processing_state,
    get_processing_state,
    ProcessingStage,
)

router = APIRouter()
storage_dir = "/tmp/processed_zips"
os.makedirs(storage_dir, exist_ok=True)

async def execute_qa_for_document_direct(doc_id: str, api_key: str | None, proc_code: str) -> str:
    if not api_key:
        raise ValueError(f"[{proc_code}] Chave de API ausente para doc_id {doc_id} durante QA.")
    
    print(f"[{proc_code}] Fazendo perguntas para doc_id: {doc_id}...")
    extracted_data = await question_answering.ask_questions(doc_id, api_key)
    
    if not extracted_data:
        raise ValueError(f"[{proc_code}] Nenhum dado extraído para doc_id {doc_id} durante QA.")
    return extracted_data

@router.post("/process-pdf", status_code=202)
async def start_pdf_processing(file: UploadFile = File(...)):
    code = str(uuid.uuid4())
    set_processing_state(code, ProcessingStage.RECEIVED)

    temp_file_path = os.path.join(tempfile.gettempdir(), f"{code}_{file.filename}")
    try:
        with open(temp_file_path, "wb") as f:
            contents = await file.read()
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar arquivo: {str(e)}")

    asyncio.create_task(process_pdf_background(temp_file_path, code, file.filename))

    return {
        "message": "Processamento iniciado",
        "tracking_code": code,
        "status_url": f"/processing-status/{code}",
        "download_url": f"/download/{code}",
    }

@router.get("/processing-status/{code}")
async def get_status(code: str):
    status = get_processing_state(code)
    if status is None:
        raise HTTPException(status_code=404, detail="Código de processamento não encontrado ou estado inválido.")
    return {"code": code, "status": status.value if isinstance(status, ProcessingStage) else str(status)}

@router.get("/download/{code}")
async def download_zip(code: str):
    status = get_processing_state(code)
    if status != ProcessingStage.FINISHED:
        error_detail = "Arquivo ainda não está pronto para download."
        if status == ProcessingStage.ERROR:
            error_detail = "Ocorreu um erro durante o processamento do arquivo."
        elif status is None:
            error_detail = "Código de processamento não encontrado."
        raise HTTPException(status_code=400, detail=error_detail)

    zip_path = os.path.join(storage_dir, f"{code}.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Arquivo ZIP final não encontrado.")

    return FileResponse(path=zip_path, filename=f"processed_output_{code}.zip", media_type="application/zip")

async def process_pdf_background(temp_file_path: str, code: str, original_filename: str):
    generated_pdf_path_original = None
    # Este continua sendo o caminho para o PDF *completo* que vai no ZIP final
    pdf_marcado_path = str(Path(temp_file_path).with_name(f"{code}_marcado.pdf"))
    zip_file_final_path = os.path.join(storage_dir, f"{code}.zip")
    
    print(f"[{code}] Iniciando processamento para: {original_filename}")
    try:
        set_processing_state(code, ProcessingStage.PREPARING)
        texto_extraido_completo = limpar.extrair_texto_com_marcacao_de_paginas(temp_file_path)

        # Geramos o PDF marcado completo para o usuário ter no ZIP
        pdf_uploader.gerar_pdf_marcado_com_reportlab(texto_extraido_completo, pdf_marcado_path)
        print(f"[{code}] PDF marcado de alta fidelidade (completo) gerado em: {pdf_marcado_path}")

        # ===== ETAPA DE UPLOAD MODIFICADA =====
        set_processing_state(code, ProcessingStage.UPLOADING)
        # Chamamos a nova função que trabalha com o TEXTO, não com um caminho de PDF
        all_source_ids, _keys_used_temp = await pdf_uploader.processar_e_enviar_texto_em_blocos(
            texto_extraido_completo, code
        )
        print(f"[{code}] Texto processado e enviado em {len(all_source_ids)} bloco(s) para o ChatPDF.")
        # ======================================

        set_processing_state(code, ProcessingStage.QA_PROCESSING)
        contexto_bruto = ""
        if all_source_ids:
            qa_coroutines = [execute_qa_for_document_direct(doc_id, _keys_used_temp[i], code) for i, doc_id in enumerate(all_source_ids)]
            qa_results = await asyncio.gather(*qa_coroutines)
            contexto_bruto = "\n\n".join(filter(None, qa_results))
        
        print(f"[{code}] Limpando e estruturando o contexto recebido do ChatPDF...")
        num_paginas_original = len(PdfReader(temp_file_path).pages)
        contexto_ajustado_pag = limpar.ajustar_numeros_de_pagina(contexto_bruto)
        contexto_ajustado_filtro = limpar.filtrar_contexto_por_pagina(contexto_ajustado_pag, num_paginas_original)
        contexto_estruturado = limpar.ajustar(contexto_ajustado_filtro)

        set_processing_state(code, ProcessingStage.SUMMARIZING)
        structured_summary = await summarizer.generate_summary(contexto_estruturado, code)
        
        set_processing_state(code, ProcessingStage.GENERATING_PDF)
        pdf_generator = PDFGenerator()
        generated_pdf_path_original = await pdf_generator.create_summary_pdf(structured_summary)
        
        set_processing_state(code, ProcessingStage.ZIPPING)
        with tempfile.TemporaryDirectory() as temp_zip_creation_dir:
            shutil.copy(generated_pdf_path_original, os.path.join(temp_zip_creation_dir, "relatorio_resumo.pdf"))
            # O PDF marcado completo ainda é adicionado ao ZIP
            shutil.copy(pdf_marcado_path, os.path.join(temp_zip_creation_dir, "documento_marcado_ocr.pdf"))
            
            with open(os.path.join(temp_zip_creation_dir, "resumo_markdown.md"), "w", encoding="utf-8") as f:
                f.write(structured_summary)
            
            with open(os.path.join(temp_zip_creation_dir, "resposta_chatpdf_bruta.txt"), "w", encoding="utf-8") as f:
                f.write(contexto_bruto)

            with zipfile.ZipFile(zip_file_final_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path in Path(temp_zip_creation_dir).glob("*"):
                    zf.write(file_path, arcname=file_path.name)
            
        set_processing_state(code, ProcessingStage.FINISHED)

    finally:
        for p in [temp_file_path, pdf_marcado_path, generated_pdf_path_original]:
            if p and os.path.exists(p):
                os.remove(p)