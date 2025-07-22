# routes.py

import os
import tempfile
import zipfile
import shutil
import re
import uuid
import asyncio
from pathlib import Path

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
from app.services.pdf_uploader import PAGINAS_POR_BLOCO

router = APIRouter()
storage_dir = "/tmp/processed_zips"
os.makedirs(storage_dir, exist_ok=True)

async def execute_qa_for_document_direct(doc_id: str, api_key: str | None, proc_code: str, chunk_index: int) -> tuple[int, str]:
    print(f"[{proc_code}] Fazendo perguntas para doc_id: {doc_id} (Bloco {chunk_index})...")
    try:
        if not api_key:
            raise ValueError(f"Chave de API ausente para o Bloco {chunk_index}")
        extracted_data = await question_answering.ask_questions(doc_id, api_key)
        return (chunk_index, extracted_data or "")
    except Exception as e:
        print(f"[{proc_code}] Erro no QA para o Bloco {chunk_index}: {e}")
        return (chunk_index, "")

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
        raise HTTPException(status_code=404, detail="Código de processamento não encontrado.")
    return {"code": code, "status": status.value if isinstance(status, ProcessingStage) else str(status)}

@router.get("/download/{code}")
async def download_zip(code: str):
    status = get_processing_state(code)
    if status != ProcessingStage.FINISHED:
        error_detail = "Arquivo ainda não está pronto."
        if status == ProcessingStage.ERROR:
            error_detail = "Ocorreu um erro durante o processamento."
        elif status is None:
            error_detail = "Código de processamento não encontrado."
        raise HTTPException(status_code=400, detail=error_detail)
    zip_path = os.path.join(storage_dir, f"{code}.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Arquivo ZIP não encontrado.")
    return FileResponse(path=zip_path, filename=f"processed_output_{code}.zip", media_type="application/zip")

async def process_pdf_background(temp_file_path: str, code: str, original_filename: str):
    generated_pdf_path_original = None
    pdf_marcado_path = str(Path(temp_file_path).with_name(f"{code}_marcado.pdf"))
    zip_file_final_path = os.path.join(storage_dir, f"{code}.zip")
    
    try:
        set_processing_state(code, ProcessingStage.PREPARING)
        texto_extraido_completo = limpar.extrair_texto_com_marcacao_de_paginas(temp_file_path)
        num_paginas_logicas = len([p for p in texto_extraido_completo.split('---') if p.strip()])
        pdf_uploader.gerar_pdf_marcado_com_reportlab(texto_extraido_completo, pdf_marcado_path)

        set_processing_state(code, ProcessingStage.UPLOADING)
        all_source_ids, _keys_used_temp = await pdf_uploader.processar_e_enviar_texto_em_blocos(
            texto_extraido_completo, code
        )

        set_processing_state(code, ProcessingStage.QA_PROCESSING)
        contexto_bruto_lista = []
        if all_source_ids:
            qa_coroutines = [
                execute_qa_for_document_direct(doc_id, _keys_used_temp[i], code, i)
                for i, doc_id in enumerate(all_source_ids)
            ]
            resultados_com_indice = await asyncio.gather(*qa_coroutines)
            resultados_com_indice.sort(key=lambda x: x[0])
            contexto_bruto_lista = [res[1] for res in resultados_com_indice]

        print(f"[{code}] Corrigindo e estruturando o contexto...")
        
        partes_finais_contexto = []
        page_offset = 0
        pegou_primeiro_cabecalho = False

        for resposta_bloco in contexto_bruto_lista:
            if not resposta_bloco.strip():
                page_offset += PAGINAS_POR_BLOCO
                continue

            if not pegou_primeiro_cabecalho:
                cabecalho_match = re.search(r"(\{[\s\S]*?Tipo do documento:[\s\S]*?\})", resposta_bloco)
                if cabecalho_match:
                    partes_finais_contexto.append(cabecalho_match.group(1))
                    pegou_primeiro_cabecalho = True
            
            paginas_neste_bloco = re.findall(r"(\{[\s\S]*?página:[\s\S]*?\})", resposta_bloco)
            
            for bloco_pagina in paginas_neste_bloco:
                bloco_corrigido = re.sub(
                    r"(página:\s*)(\d+)",
                    lambda m: f"{m.group(1)}{int(m.group(2)) + page_offset}",
                    bloco_pagina, 1
                )
                partes_finais_contexto.append(bloco_corrigido)

            page_offset += PAGINAS_POR_BLOCO
        
        contexto_corrigido_e_unido = "\n\n".join(partes_finais_contexto)
        
        contexto_filtrado = limpar.filtrar_contexto_por_pagina(contexto_corrigido_e_unido, num_paginas_logicas)
        contexto_estruturado = limpar.estruturar_dados_finais(contexto_filtrado)
        
        set_processing_state(code, ProcessingStage.SUMMARIZING)
        structured_summary = await summarizer.generate_summary(contexto_estruturado, code)
        
        set_processing_state(code, ProcessingStage.GENERATING_PDF)
        pdf_generator = PDFGenerator()
        generated_pdf_path_original = await pdf_generator.create_summary_pdf(structured_summary)
        
        set_processing_state(code, ProcessingStage.ZIPPING)
        with tempfile.TemporaryDirectory() as temp_dir:
            shutil.copy(generated_pdf_path_original, os.path.join(temp_dir, "relatorio_resumo.pdf"))
            shutil.copy(pdf_marcado_path, os.path.join(temp_dir, "documento_marcado_ocr.pdf"))
            with open(os.path.join(temp_dir, "resumo_markdown.md"), "w", encoding="utf-8") as f: f.write(structured_summary)
            with open(os.path.join(temp_dir, "resposta_chatpdf_bruta_ordenada.txt"), "w", encoding="utf-8") as f: f.write("\n\n--- FIM DO BLOCO ---\n\n".join(contexto_bruto_lista))
            with open(os.path.join(temp_dir, "resposta_chatpdf_corrigida.txt"), "w", encoding="utf-8") as f: f.write(contexto_corrigido_e_unido)
            with zipfile.ZipFile(zip_file_final_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file in Path(temp_dir).iterdir(): zf.write(file, arcname=file.name)
            
        set_processing_state(code, ProcessingStage.FINISHED)
    except Exception as e:
        print(f"ERRO CRÍTICO NO PROCESSAMENTO: {e}")
        set_processing_state(code, ProcessingStage.ERROR)
        import traceback
        traceback.print_exc()
    finally:
        for p in [temp_file_path, pdf_marcado_path, generated_pdf_path_original]:
            if p and os.path.exists(p): os.remove(p)