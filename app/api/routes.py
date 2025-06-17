import os
import tempfile
import zipfile
import shutil
import json
import re
import uuid
import asyncio
import traceback
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
        print(f"Erro ao salvar arquivo temporário {temp_file_path} para {code}: {e}")
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

    return FileResponse(
        path=zip_path,
        filename=f"processed_output_{code}.zip",
        media_type="application/zip"
    )

async def process_pdf_background(temp_file_path: str, code: str, original_filename: str):
    generated_pdf_path_original = None
    zip_file_final_path = os.path.join(storage_dir, f"{code}.zip")
    
    print(f"[{code}] Iniciando processamento direto para: {original_filename}")
    num_paginas = 0
    try:
        with open(temp_file_path, 'rb') as f_pdf:
                reader = PdfReader(f_pdf)
                num_paginas = len(reader.pages)
        set_processing_state(code, ProcessingStage.UPLOADING)
        all_source_ids, _keys_used_temp = await pdf_uploader.processar_pdf_em_partes_e_enviar_path(temp_file_path)
        print(f"[{code}] PDF uploader processou e obteve {len(all_source_ids)} source_id(s).")

        set_processing_state(code, ProcessingStage.QA_PROCESSING)
        extracted_data_list_for_context = []
        if all_source_ids:
            print(f"[{code}] Iniciando extração de dados para {len(all_source_ids)} documento(s)...")
            qa_coroutines = []
            for i, doc_id in enumerate(all_source_ids):
                api_key_for_doc = _keys_used_temp[i] 
                qa_coroutines.append(execute_qa_for_document_direct(doc_id, api_key_for_doc, code))
            
            qa_results = await asyncio.gather(*qa_coroutines)
            extracted_data_list_for_context.extend(res for res in qa_results if res) 
        
        contexto_original_temp = "\n\n".join(filter(None, extracted_data_list_for_context))
        contexto_ajustado_pag = limpar.ajustar_numeros_de_pagina(contexto_original_temp)
        contexto_ajustado_filtro = limpar.filtrar_contexto_por_pagina(contexto_ajustado_pag, num_paginas)
        contexto_ajustar = limpar.ajustar(contexto_ajustado_filtro)
        contexto_ajustado = limpar.padronizar_indicadores_de_pagina(contexto_ajustar)

        set_processing_state(code, ProcessingStage.SUMMARIZING)
        print(f"[{code}] Gerando resumo com LLM (summarizer)...")
        structured_summary = await summarizer.generate_summary(contexto_ajustado, all_source_ids if all_source_ids else [])
        print(f"[{code}] Resumo gerado com sucesso pelo LLM.")
        
        set_processing_state(code, ProcessingStage.GENERATING_PDF)
        print(f"[{code}] Tentando gerar PDF do resumo...")
        pdf_generator = PDFGenerator()
        generated_pdf_path_original = await pdf_generator.create_summary_pdf(structured_summary)
        print(f"[{code}] PDF do resumo gerado: {generated_pdf_path_original}")
        
        set_processing_state(code, ProcessingStage.ZIPPING)
        print(f"[{code}] Iniciando criação do arquivo ZIP...")
        with tempfile.TemporaryDirectory() as temp_zip_creation_dir:
            pdf_name_in_zip = "relatorio_resumo.pdf"
            context_name_in_zip = "contexto_extracao.txt"
            is_summary_complex_json = isinstance(structured_summary, (dict, list)) and not ("error" in structured_summary and len(structured_summary) <= 2)
            summary_name_in_zip = "resumo_estruturado.json" if is_summary_complex_json else "resumo_estruturado.txt"

            files_to_zip_info = []

            path_to_pdf_in_temp_dir = os.path.join(temp_zip_creation_dir, pdf_name_in_zip)
            shutil.copy(generated_pdf_path_original, path_to_pdf_in_temp_dir)
            files_to_zip_info.append((path_to_pdf_in_temp_dir, pdf_name_in_zip))
            
            path_to_context_in_temp_dir = os.path.join(temp_zip_creation_dir, context_name_in_zip)
            with open(path_to_context_in_temp_dir, "w", encoding="utf-8") as f_context:
                f_context.write(contexto_ajustado)
            files_to_zip_info.append((path_to_context_in_temp_dir, context_name_in_zip))

            path_to_summary_in_temp_dir = os.path.join(temp_zip_creation_dir, summary_name_in_zip)
            with open(path_to_summary_in_temp_dir, "w", encoding="utf-8") as f_summary:
                if isinstance(structured_summary, (dict, list)):
                    json.dump(structured_summary, f_summary, indent=4, ensure_ascii=False)
                else:
                    f_summary.write(str(structured_summary))
            files_to_zip_info.append((path_to_summary_in_temp_dir, summary_name_in_zip))
            
            with zipfile.ZipFile(zip_file_final_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path, arcname in files_to_zip_info:
                    zf.write(file_path, arcname=arcname)
            
        set_processing_state(code, ProcessingStage.FINISHED)
        print(f"[{code}] Processamento 'direto' concluído. ZIP salvo em: {zip_file_final_path}")

    finally:
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                print(f"[{code}] Arquivo temporário '{temp_file_path}' removido.")
            except Exception as e_remove_temp:
                print(f"[{code}] Erro ao remover arquivo temporário '{temp_file_path}': {e_remove_temp}")
        
        if generated_pdf_path_original and os.path.exists(generated_pdf_path_original):
            try:
                os.remove(generated_pdf_path_original)
                print(f"[{code}] PDF original gerado '{generated_pdf_path_original}' limpo.")
            except Exception as e_remove_pdf_orig:
                print(f"[{code}] Erro ao remover PDF original gerado '{generated_pdf_path_original}': {e_remove_pdf_orig}")