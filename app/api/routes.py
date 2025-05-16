import os
import tempfile
import zipfile
import shutil
import json
import re
import uuid
import asyncio
import traceback

from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse

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
    try:
        with open(temp_file_path, "wb") as f:
            contents = await file.read()
            f.write(contents)
    except Exception as e:
        print(f"Erro ao salvar arquivo temporário {temp_file_path} para {code}: {e}")
        set_processing_state(code, ProcessingStage.ERROR)
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
        set_processing_state(code, ProcessingStage.ERROR) # Marcar como erro se o zip não existe quando deveria
        raise HTTPException(status_code=404, detail="Arquivo ZIP final não encontrado. O processamento pode ter falhado.")

    return FileResponse(
        path=zip_path,
        filename=f"processed_output_{code}.zip",
        media_type="application/zip"
    )

async def process_pdf_background(temp_file_path: str, code: str, original_filename: str):
    generated_pdf_path_original = None
    zip_file_final_path = os.path.join(storage_dir, f"{code}.zip")

    all_source_ids = []
    _keys_used_temp = []
    extracted_data_list_for_context = []
    contexto_ajustado = "Contexto não pôde ser gerado devido a falhas no processamento."
    structured_summary = {"error": "Resumo não pôde ser gerado.", "details": "Etapa de sumarização não foi concluída ou falhou."}

    try:
        set_processing_state(code, ProcessingStage.UPLOADING)
        try:
            _source_ids_temp, _keys_used_temp = await pdf_uploader.processar_pdf_em_partes_e_enviar_path(temp_file_path)
            if _source_ids_temp and _keys_used_temp and len(_source_ids_temp) == len(_keys_used_temp):
                all_source_ids = _source_ids_temp
                print(f"[{code}] PDF uploader processou e obteve {len(all_source_ids)} source_id(s).")
            else:
                error_msg = f"Falha ao obter IDs de documento e chaves de API. IDs: {_source_ids_temp}, Chaves: {_keys_used_temp}"
                print(f"[{code}] Erro (Uploader): {error_msg}")
                extracted_data_list_for_context.append(f"Erro no Uploader: {error_msg}")
        except Exception as e_uploader:
            print(f"[{code}] Erro crítico durante o upload do PDF (pdf_uploader): {e_uploader}")
            traceback.print_exc()
            extracted_data_list_for_context.append(f"Erro crítico no Uploader: {str(e_uploader)}")
            raise # Re-lança para ser pego pelo try/except externo e marcar como ERRO

        set_processing_state(code, ProcessingStage.QA_PROCESSING)
        if all_source_ids:
            print(f"[{code}] Iniciando extração de dados para {len(all_source_ids)} documento(s)...")
            
            async def perform_qa_for_doc(doc_id, api_key, proc_code):
                try:
                    if not api_key:
                        message = f"Chave de API ausente para doc_id {doc_id}."
                        print(f"[{proc_code}] Aviso (QA): {message}")
                        return f"Para Doc ID {doc_id}: {message}"
                    
                    print(f"[{proc_code}] Fazendo perguntas para doc_id: {doc_id}...")
                    extracted_data = await question_answering.ask_questions(doc_id, api_key)
                    if extracted_data:
                        return extracted_data
                    else:
                        message = f"Nenhum dado extraído para doc_id {doc_id}."
                        print(f"[{proc_code}] Aviso (QA): {message}")
                        return f"Para Doc ID {doc_id}: {message}"
                except Exception as e_qa_doc:
                    message = f"Erro ao fazer perguntas para doc_id {doc_id}: {e_qa_doc}"
                    print(f"[{proc_code}] Erro (QA doc {doc_id}): {message}")
                    return f"Para Doc ID {doc_id}: Erro na extração - {str(e_qa_doc)}"

            qa_coroutines = []
            for i in range(len(all_source_ids)):
                doc_id = all_source_ids[i]
                api_key_for_doc = _keys_used_temp[i] if i < len(_keys_used_temp) else None
                qa_coroutines.append(perform_qa_for_doc(doc_id, api_key_for_doc, code))
            
            qa_results = await asyncio.gather(*qa_coroutines)
            extracted_data_list_for_context.extend(filter(None, qa_results))

        elif not extracted_data_list_for_context:
            extracted_data_list_for_context.append("Nenhum documento foi processado pelo uploader, perguntas não realizadas.")

        if extracted_data_list_for_context:
            contexto_original_temp = "\n\n".join(filter(None, extracted_data_list_for_context))
            contexto_ajustado = ajustar_numeros_de_pagina(contexto_original_temp)
            if not contexto_ajustado.strip():
                contexto_ajustado = "Contexto final vazio ou contém apenas mensagens de erro/aviso."
        else:
            contexto_ajustado = "Não foi possível coletar dados para formar o contexto."
        print(f"[{code}] Contexto preparado para sumarização (primeiros 100 chars): {contexto_ajustado[:100]}...")
        
        set_processing_state(code, ProcessingStage.SUMMARIZING)
        try:
            is_context_meaningful = contexto_ajustado and \
                                   "não pôde ser gerado" not in contexto_ajustado.lower() and \
                                   "nenhum documento foi processado" not in contexto_ajustado.lower() and \
                                   "contexto final vazio" not in contexto_ajustado.lower() and \
                                   len(contexto_ajustado.strip()) > 10

            if is_context_meaningful:
                print(f"[{code}] Gerando resumo com LLM (summarizer)...")
                _summary_candidate = await summarizer.generate_summary(contexto_ajustado, all_source_ids if all_source_ids else [])
                if _summary_candidate:
                    structured_summary = _summary_candidate
                    print(f"[{code}] Resumo gerado com sucesso pelo LLM.")
                else:
                    message = "O sumarizador (LLM) retornou um resultado vazio ou inválido."
                    print(f"[{code}] Erro (Summarizer): {message}")
                    structured_summary = {"error": message, "context_provided_to_llm": contexto_ajustado}
            else:
                message = "Sumarização (LLM) pulada: contexto insuficiente ou contém apenas erros."
                print(f"[{code}] Aviso (Summarizer): {message}")
                structured_summary = {"error": message, "reason": contexto_ajustado}
        except Exception as e_summarizer:
            message = f"Erro ao gerar resumo com LLM (summarizer): {e_summarizer}"
            print(f"[{code}] Erro (Summarizer): {message}")
            traceback.print_exc()
            structured_summary = {"error": message, "context_used_for_llm": contexto_ajustado}

        set_processing_state(code, ProcessingStage.GENERATING_PDF)
        try:
            print(f"[{code}] Tentando gerar PDF do resumo...")
            pdf_generator = PDFGenerator()
            _generated_pdf_path = await pdf_generator.create_summary_pdf(structured_summary)
            if _generated_pdf_path and os.path.exists(_generated_pdf_path):
                generated_pdf_path_original = _generated_pdf_path
                print(f"[{code}] PDF do resumo gerado com sucesso: {generated_pdf_path_original}")
            else:
                print(f"[{code}] Erro (PDF Generator): PDFGenerator não criou o arquivo PDF ou retornou um caminho inválido.")
        except Exception as e_pdf:
            print(f"[{code}] Erro crítico ao gerar PDF do resumo (PDF Generator): {e_pdf}")
            traceback.print_exc()
            if 'structured_summary' in locals():
                try:
                    summary_to_print = structured_summary
                    print(f"[{code}] Resumo que causou erro no PDF: {json.dumps(summary_to_print, indent=2, ensure_ascii=False) if isinstance(summary_to_print, (dict, list)) else str(summary_to_print)}")
                except Exception: pass
        
        set_processing_state(code, ProcessingStage.ZIPPING)
        print(f"[{code}] Iniciando criação do arquivo ZIP...")
        with tempfile.TemporaryDirectory() as temp_zip_creation_dir:
            pdf_name_in_zip = "relatorio_resumo.pdf"
            context_name_in_zip = "contexto_extracao.txt"
            summary_name_in_zip = "resumo_estruturado.json" if isinstance(structured_summary, (dict, list)) and not ("error" in structured_summary and len(structured_summary) <= 2) else "resumo_estruturado.txt"

            files_to_zip_info = []

            if generated_pdf_path_original and os.path.exists(generated_pdf_path_original):
                path_to_pdf_in_temp_dir = os.path.join(temp_zip_creation_dir, pdf_name_in_zip)
                try:
                    shutil.copy(generated_pdf_path_original, path_to_pdf_in_temp_dir)
                    files_to_zip_info.append((path_to_pdf_in_temp_dir, pdf_name_in_zip))
                except Exception as e_copy_pdf:
                    print(f"[{code}] Erro ao copiar PDF para ZIP: {e_copy_pdf}")
            
            path_to_context_in_temp_dir = os.path.join(temp_zip_creation_dir, context_name_in_zip)
            try:
                with open(path_to_context_in_temp_dir, "w", encoding="utf-8") as f_context:
                    f_context.write(contexto_ajustado)
                files_to_zip_info.append((path_to_context_in_temp_dir, context_name_in_zip))
            except Exception as e_write_context:
                print(f"[{code}] Erro ao escrever contexto para ZIP: {e_write_context}")

            path_to_summary_in_temp_dir = os.path.join(temp_zip_creation_dir, summary_name_in_zip)
            try:
                with open(path_to_summary_in_temp_dir, "w", encoding="utf-8") as f_summary:
                    if isinstance(structured_summary, (dict, list)):
                        json.dump(structured_summary, f_summary, indent=4, ensure_ascii=False)
                    else:
                        f_summary.write(str(structured_summary))
                files_to_zip_info.append((path_to_summary_in_temp_dir, summary_name_in_zip))
            except Exception as e_write_summary:
                print(f"[{code}] Erro ao escrever resumo para ZIP: {e_write_summary}")

            if not files_to_zip_info:
                print(f"[{code}] Aviso: Nenhum arquivo de resultado principal para adicionar ao ZIP. Criando arquivo de status.")
                status_content = f"Processamento do arquivo '{original_filename}' (código: {code}) concluído com falhas significativas.\n"
                status_content += f"IDs Processados: {all_source_ids if all_source_ids else 'Nenhum'}\n"
                status_content += f"Contexto Gerado: {contexto_ajustado[:200]}...\n"
                status_content += f"Resumo Tentado: {json.dumps(structured_summary, indent=2,ensure_ascii=False) if isinstance(structured_summary, (dict, list)) else str(structured_summary)}\n"
                
                status_file_name_in_zip = "status_processamento.txt"
                path_to_status_in_temp_dir = os.path.join(temp_zip_creation_dir, status_file_name_in_zip)
                try:
                    with open(path_to_status_in_temp_dir, "w", encoding="utf-8") as f_status:
                        f_status.write(status_content)
                    files_to_zip_info.append((path_to_status_in_temp_dir, status_file_name_in_zip))
                except Exception as e_write_status_zip:
                     print(f"[{code}] Erro crítico ao escrever arquivo de status para ZIP: {e_write_status_zip}")
            
            with zipfile.ZipFile(zip_file_final_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for file_path, arcname in files_to_zip_info:
                    if os.path.exists(file_path):
                        zf.write(file_path, arcname=arcname)
                    else:
                        print(f"[{code}] Aviso: Arquivo {file_path} para ZIP não encontrado.")
            
        set_processing_state(code, ProcessingStage.FINISHED)
        print(f"[{code}] Processamento concluído. ZIP salvo em: {zip_file_final_path}")

    except Exception as e_main_processing:
        print(f"[{code}] Erro principal no processamento de {code} ({original_filename}): {e_main_processing}")
        traceback.print_exc()
        set_processing_state(code, ProcessingStage.ERROR)
    finally:
        try:
            if os.path.exists(temp_file_path):
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