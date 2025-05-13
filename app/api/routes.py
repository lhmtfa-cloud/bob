import os
import tempfile
import zipfile
import shutil
import json
import re
import uuid
import asyncio

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse

from app.services import pdf_uploader, question_answering, summarizer
from app.services.pdf_generator import PDFGenerator
from app.services.state_tracker import (
    set_processing_state,
    get_processing_state,
    ProcessingStage,
)

router = APIRouter()
storage_dir = "/tmp/processed_zips"
os.makedirs(storage_dir, exist_ok=True)


def ajustar_numeros_de_pagina(raw_contexto_str: str) -> str:
    blocks = re.findall(r"(\{[\s\S]*?\})", raw_contexto_str)
    if not blocks:
        return raw_contexto_str

    page_offset = 0
    processed_first_document_header = False
    adjusted_block_strings = []

    for block_str in blocks:
        modified_block_str = block_str
        if "Tipo do documento:" in block_str:
            if processed_first_document_header:
                page_offset += 10
            else:
                processed_first_document_header = True

        elif "página:" in block_str:
            match = re.search(r"(página:\s*)(\d+)", modified_block_str)
            if match:
                prefix = match.group(1)
                original_page_num_str = match.group(2)
                try:
                    original_page_num = int(original_page_num_str)
                    new_page_num = original_page_num + page_offset
                    modified_block_str = re.sub(
                        r"(página:\s*)\d+", f"{prefix}{new_page_num}", modified_block_str, count=1
                    )
                except ValueError:
                    pass

        adjusted_block_strings.append(modified_block_str)

    return "\n\n".join(adjusted_block_strings)


@router.post("/process-pdf", status_code=202)
async def start_pdf_processing(file: UploadFile = File(...)):
    code = str(uuid.uuid4())
    set_processing_state(code, ProcessingStage.RECEIVED)

    temp_file_path = os.path.join(tempfile.gettempdir(), f"{code}_{file.filename}")
    with open(temp_file_path, "wb") as f:
        f.write(await file.read())

    asyncio.create_task(process_pdf_background(temp_file_path, code))

    return {
        "message": "Processamento iniciado",
        "tracking_code": code,
        "status_url": f"/processing-status/{code}",
        "download_url": f"/download/{code}",
    }


@router.get("/processing-status/{code}")
async def get_status(code: str):
    status = get_processing_state(code)
    if not status:
        raise HTTPException(status_code=404, detail="Código não encontrado")
    return {"code": code, "status": status}


@router.get("/download/{code}")
async def download_zip(code: str):
    status = get_processing_state(code)
    if status != ProcessingStage.FINISHED:
        raise HTTPException(status_code=400, detail="Arquivo ainda não está pronto")

    zip_path = os.path.join(storage_dir, f"{code}.zip")
    if not os.path.exists(zip_path):
        raise HTTPException(status_code=404, detail="Arquivo ZIP não encontrado")

    return FileResponse(
        path=zip_path,
        filename=f"processed_output_{code}.zip",
        media_type="application/zip"
    )


async def process_pdf_background(temp_file_path: str, code: str):
    temp_dir = None
    generated_pdf_path = None
    zip_file_path = os.path.join(storage_dir, f"{code}.zip")

    try:
        doc_ids = await pdf_uploader.processar_pdf_em_partes_e_enviar_path(temp_file_path)

        set_processing_state(code, ProcessingStage.QA_PROCESSING)
        extracted_data_list = []

        qa_tasks = [
            asyncio.to_thread(question_answering.ask_questions, doc_id)
            for doc_id in doc_ids
        ]

        extracted_data_list = await asyncio.gather(*qa_tasks)

        contexto_original = "\n\n".join(extracted_data_list)
        contexto_ajustado = ajustar_numeros_de_pagina(contexto_original)

        set_processing_state(code, ProcessingStage.SUMMARIZING)
        structured_summary = await asyncio.to_thread(summarizer.generate_summary, contexto_ajustado)

        set_processing_state(code, ProcessingStage.GENERATING_PDF)
        pdf_generator = PDFGenerator()
        generated_pdf_path = await pdf_generator.create_summary_pdf(structured_summary)

        if not os.path.exists(generated_pdf_path):
            raise FileNotFoundError("PDF não foi gerado.")

        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_name = "summary.pdf"
            context_name = "context.txt"
            summary_name = (
                "structured_summary.json" if isinstance(structured_summary, (dict, list)) else "structured_summary.txt"
            )

            path_to_pdf = os.path.join(temp_dir, pdf_name)
            path_to_context = os.path.join(temp_dir, context_name)
            path_to_summary = os.path.join(temp_dir, summary_name)

            shutil.copy(generated_pdf_path, path_to_pdf)

            with open(path_to_context, "w", encoding="utf-8") as f:
                f.write(contexto_ajustado)

            with open(path_to_summary, "w", encoding="utf-8") as f:
                if isinstance(structured_summary, (dict, list)):
                    json.dump(structured_summary, f, indent=4, ensure_ascii=False)
                else:
                    f.write(str(structured_summary))

            with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.write(path_to_pdf, arcname=pdf_name)
                zf.write(path_to_context, arcname=context_name)
                zf.write(path_to_summary, arcname=summary_name)

        set_processing_state(code, ProcessingStage.FINISHED)

    except Exception as e:
        print(f"Erro no processamento de {code}: {e}")
        set_processing_state(code, ProcessingStage.ERROR)

    finally:
        try:
            os.remove(temp_file_path)
        except Exception:
            pass
        if generated_pdf_path and os.path.exists(generated_pdf_path):
            try:
                os.remove(generated_pdf_path)
            except Exception:
                pass